#!/usr/bin/env python3
"""
reminder_ws_daemon — 独立 WebSocket 守护进程

按 AI-Pet-WebSocket 协议文档实现:
- 连接: ws://47.118.26.156:8000/api/v1/aipet/ws/{serial}
- 认证: GET /api/v1/aipet/ws/auth/{serial} → token
- 下行: §4.2 reminder_delivery → /reminder/ws/delivery
- 上行: §3.7 reminder_response ← /reminder/ws/result

不依赖同事 ws_daemon_bridge。
"""

import rclpy, json, time, threading
from rclpy.node import Node
from std_msgs.msg import String

try:
    import websocket
except ImportError:
    websocket = None

try:
    import urllib.request
except ImportError:
    urllib = None


class ReminderWSDaemon(Node):

    def __init__(self):
        super().__init__("reminder_ws_daemon")

        self.declare_parameter("server_host", "47.118.26.156")
        self.declare_parameter("server_port", 8000)
        self.declare_parameter("serial_number", "6976f96f-bc80-56e3-9b27-13d12cdde9d1")
        self.declare_parameter("heartbeat_interval", 30.0)

        self._host = self.get_parameter("server_host").value
        self._port = self.get_parameter("server_port").value
        self._serial = self.get_parameter("serial_number").value
        self._hb = self.get_parameter("heartbeat_interval").value

        # 下行: WS → ROS2
        self._relay_pub = self.create_publisher(String, "/reminder/ws/delivery", 10)
        self._cmd_pub = self.create_publisher(String, "/reminder/ws/command", 10)

        # 上行: ROS2 → WS
        self.create_subscription(String, "/reminder/ws/result", self._on_ws_result, 10)

        # WebSocket
        self._ws = None
        self._connected = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._thread.start()

        self._hb_timer = self.create_timer(self._hb, self._send_heartbeat)

        self.get_logger().info(f"reminder_ws_daemon 已启动 {self._host}:{self._port}")

    # ── WebSocket 连接 ──

    def _fetch_token(self):
        url = f"http://{self._host}:{self._port}/api/v1/aipet/ws/auth/{self._serial}"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read())
            return data.get("data", "")
        except Exception as e:
            self.get_logger().error(f"获取token失败: {e}")
            return ""

    def _ws_loop(self):
        if websocket is None:
            self.get_logger().error("websocket-client 未安装")
            return
        while not self._stop.is_set():
            token = self._fetch_token()
            if not token:
                time.sleep(10)
                continue
            url = f"ws://{self._host}:{self._port}/api/v1/aipet/ws/{self._serial}"
            self.get_logger().info(f"连接 WS...")
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=lambda ws: ws.send(json.dumps({"type": "auth", "access_token": token})),
                    on_message=lambda ws, msg: self._on_ws_msg(msg),
                    on_error=lambda ws, err: None,
                    on_close=lambda ws, code, msg: None,
                )
                self._ws.run_forever(ping_interval=25, ping_timeout=10)
            except Exception:
                pass
            if not self._stop.is_set():
                time.sleep(5)

    # ── 下行: WS消息 → ROS2话题 ──

    def _on_ws_msg(self, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "auth":
            if data.get("success"):
                self._connected = True
                self.get_logger().info("认证成功")

        # §4.2 reminder_delivery — 待办事提醒下发
        elif msg_type == "reminder_delivery":
            rid = data.get("reminder_id", "")
            rd = data.get("reminder_data", {})
            self.get_logger().info(f"提醒下发: {rd.get('title','')[:20]} @ {rd.get('reminder_time','')}")

            msg = String()
            msg.data = message  # 原样转发
            self._relay_pub.publish(msg)

            # 回复 ACK
            self._send_ack("reminder_delivery", data)

        # §4.1 server_command
        elif msg_type == "server_command":
            cmd = data.get("command", "")
            self.get_logger().info(f"指令: {cmd}")
            msg = String()
            msg.data = message
            self._cmd_pub.publish(msg)

        # §4.3 relay_message_delivery — 传话
        elif msg_type == "relay_message_delivery":
            self.get_logger().info(f"传话: {data.get('content','')[:30]}")
            msg = String()
            msg.data = message
            self._relay_pub.publish(msg)

    # ── 上行: ROS2话题 → WS消息 → 服务器 ──

    def _on_ws_result(self, msg: String):
        """接收提醒执行结果，按 §3.7 格式发回服务器"""
        if not self._connected or not self._ws:
            return
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        # 构建 §3.7 reminder_response
        response = {
            "type": "reminder_response",
            "reminder_id": data.get("reminder_id", ""),
            "status": data.get("status", "completed"),
            "result": data.get("result", {"played": True}),
        }
        error = data.get("error", "")
        if error:
            response["error"] = error

        try:
            self._ws.send(json.dumps(response, ensure_ascii=False))
            self.get_logger().info(f"结果已回传: {response['reminder_id']} = {response['status']}")
        except Exception:
            pass

    def _send_ack(self, msg_type, data):
        if self._connected and self._ws:
            try:
                ack = {"type": "ack", "message": msg_type,
                       "message_id": data.get("reminder_id") or data.get("message_id", ""),
                       "timestamp": time.time()}
                self._ws.send(json.dumps(ack))
            except Exception:
                pass

    def _send_heartbeat(self):
        if self._connected and self._ws:
            try:
                self._ws.send(json.dumps({"type": "heartbeat"}))
            except Exception:
                pass

    def destroy_node(self):
        self._stop.set()
        if self._ws:
            self._ws.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReminderWSDaemon()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
