#!/usr/bin/env python3
"""
reminder_ws_daemon — 独立 WebSocket 守护进程

连接远程服务器，接收提醒消息，发布到 ROS2 话题。
独立于同事的 ws_daemon_bridge，不重名，不共用。

云端 ⇋ reminder_ws_daemon (WebSocket)
          │ /aipet/ws/relay_delivery → aipet_reminder_node
          │ /aipet/ws/command_delivery → aipet_reminder_node
          │ /aipet/ws/relay_result ← aipet_reminder_node
"""

import rclpy, json, time, threading
from rclpy.node import Node
from std_msgs.msg import String
from datetime import datetime

try:
    import websocket
except ImportError:
    websocket = None

try:
    import urllib.request
except ImportError:
    urllib = None


class ReminderWSDaemon(Node):
    """独立 WebSocket 守护，连接远程服务器"""

    def __init__(self):
        super().__init__("reminder_ws_daemon")

        self.declare_parameter("server_host", "47.118.26.156")
        self.declare_parameter("server_port", 8000)
        self.declare_parameter("serial_number", "6976f96f-bc80-56e3-9b27-13d12cdde9d1")
        self.declare_parameter("heartbeat_interval", 30.0)

        self.server_host = self.get_parameter("server_host").value
        self.server_port = self.get_parameter("server_port").value
        self.serial = self.get_parameter("serial_number").value
        self.hb_interval = self.get_parameter("heartbeat_interval").value

        # 发布器：ws → ROS2 话题
        self._relay_pub = self.create_publisher(String, "/aipet/ws/relay_delivery", 10)
        self._cmd_pub = self.create_publisher(String, "/aipet/ws/command_delivery", 10)
        self._config_pub = self.create_publisher(String, "/aipet/ws/config_response", 10)

        # 订阅器：ROS2 话题 → ws（回传结果）
        self.create_subscription(String, "/aipet/ws/relay_result", self._on_ws_result, 10)
        self.create_subscription(String, "/aipet/ws/voice_trigger", self._on_voice_trigger, 10)

        # WebSocket 连接
        self._ws = None
        self._connected = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._thread.start()

        # 心跳
        self._hb_timer = self.create_timer(self.hb_interval, self._send_heartbeat)

        self.get_logger().info(f"reminder_ws_daemon 已启动 ({self.server_host}:{self.server_port})")

    def _fetch_token(self):
        url = (f"http://{self.server_host}:{self.server_port}"
               f"/api/v1/aipet/ws/auth/{self.serial}")
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

            url = (f"ws://{self.server_host}:{self.server_port}"
                   f"/api/v1/aipet/ws/{self.serial}")
            self.get_logger().info(f"连接 WS: {url[:60]}...")

            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=lambda ws: self._on_open(ws, token),
                    on_message=lambda ws, msg: self._on_message(msg),
                    on_error=lambda ws, err: self.get_logger().error(f"WS错误: {err}"),
                    on_close=lambda ws, code, msg: self.get_logger().info(f"WS关闭: {code}"),
                )
                self._ws.run_forever(ping_interval=25, ping_timeout=10)
            except Exception as e:
                self.get_logger().error(f"WS异常: {e}")

            if not self._stop.is_set():
                self.get_logger().info("5秒后重连...")
                time.sleep(5)

    def _on_open(self, ws, token):
        self.get_logger().info("WS已连接，发送认证...")
        ws.send(json.dumps({"type": "auth", "access_token": token}))

    def _on_message(self, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "auth":
            if data.get("success"):
                self._connected = True
                self.get_logger().info("认证成功")
                # 请求配置
                if self._ws:
                    self._ws.send(json.dumps({"type": "config_request"}))
            else:
                self.get_logger().error("认证失败")

        elif msg_type == "reminder_delivery":
            msg = String()
            msg.data = message
            self._relay_pub.publish(msg)
            self.get_logger().info(f"收到提醒: {data.get('reminder_data',{}).get('title','')[:20]}")

        elif msg_type == "server_command":
            msg = String()
            msg.data = message
            self._cmd_pub.publish(msg)
            self.get_logger().info(f"收到指令: {data.get('command','')}")

        elif msg_type == "relay_message_delivery":
            msg = String()
            msg.data = message
            self._relay_pub.publish(msg)
            self.get_logger().info(f"收到传话")

        elif msg_type == "config_request" and data.get("success"):
            config = data.get("data", {})
            msg = String()
            msg.data = json.dumps(config, ensure_ascii=False)
            self._config_pub.publish(msg)
            self.get_logger().info(f"收到配置: {config.get('pet_nickname','')}")

        elif msg_type == "chat":
            self.get_logger().info(f"收到聊天: {data.get('content','')[:30]}")

    def _send_heartbeat(self):
        if self._connected and self._ws:
            try:
                self._ws.send(json.dumps({"type": "heartbeat"}))
            except Exception:
                pass

    def _on_ws_result(self, msg: String):
        """转发 aipet_reminder_node 的执行结果到云端"""
        if self._connected and self._ws:
            try:
                self._ws.send(msg.data)
            except Exception:
                pass

    def _on_voice_trigger(self, msg: String):
        if self._connected and self._ws:
            try:
                self._ws.send(msg.data)
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
