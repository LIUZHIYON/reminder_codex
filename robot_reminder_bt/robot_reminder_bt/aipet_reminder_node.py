#!/usr/bin/env python3
"""
aipet_reminder_node — 提醒桥接节点

架构（不依赖同事的 relay_node/bt_relay_node）:

  云端 ⇋ ws_daemon_bridge (WebSocket)
         │
         │ /aipet/ws/relay_delivery
         ▼
  aipet_reminder_node (本节点) ──→ /robot/command ──→ reminder_bt_driver
         ▲                                              │
         │           /robot/command_response ◄──────────┘
         │
         │ /aipet/ws/relay_result
         ▼
  ws_daemon_bridge ──→ 云端

对比同事链路:
  ws_daemon → aipet_relay → bt_relay (同事)
  ws_daemon → aipet_reminder → reminder_bt_driver (新)
"""

import rclpy, json, time
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from datetime import datetime


class AIPetReminderNode(Node):
    """提醒桥接节点：ws_daemon_bridge ←→ reminder_bt_driver"""

    def __init__(self):
        super().__init__("aipet_reminder_node")

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10)

        # === 订阅 ws_daemon_bridge 下发的消息 ===
        self.create_subscription(
            String, "/aipet/ws/relay_delivery", self._on_ws_delivery, qos)
        self.create_subscription(
            String, "/aipet/ws/command_delivery", self._on_ws_command, qos)

        # === 订阅 BT driver 的执行结果 ===
        self.create_subscription(
            String, "/robot/command_response", self._on_bt_response, qos)

        # === 发布到 BT driver ===
        self._cmd_pub = self.create_publisher(
            String, "/robot/command", qos)

        # === 发布回 ws_daemon_bridge ===
        self._result_pub = self.create_publisher(
            String, "/aipet/ws/relay_result", qos)

        self.get_logger().info("aipet_reminder_node 已启动")

    # ── 下行：ws_daemon → BT driver ──

    def _on_ws_delivery(self, msg: String):
        """接收 ws_daemon_bridge 下发的 relay_message_delivery"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")
        if msg_type == "reminder_delivery":
            self._handle_reminder(data)
        elif msg_type == "relay_message_delivery":
            self._handle_relay(data)
        else:
            self.get_logger().debug(f"未处理的ws消息: {msg_type}")

    def _on_ws_command(self, msg: String):
        """接收 ws_daemon_bridge 下发的 server_command"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if data.get("command") == "reminder":
            rid = data.get("command_id", "")
            params = data.get("params", {})
            rd = params.get("reminder_data", {})
            self._send_to_bt(rid, rd)
        else:
            self.get_logger().debug(f"非reminder指令: {data.get('command','')}")

    def _handle_reminder(self, data: dict):
        """处理 reminder_delivery 消息"""
        rid = data.get("reminder_id", "")
        rd = data.get("reminder_data", {})
        self._send_to_bt(rid, rd)

    def _handle_relay(self, data: dict):
        """处理 relay_message_delivery 消息"""
        rid = data.get("relay_id", "")
        content = data.get("content", "")
        rtime = data.get("reminder_time", "") or datetime.now().isoformat()
        rd = {"title": content[:50] if content else "传话提醒",
              "content": content, "reminder_time": rtime,
              "repeat_type": "none"}
        self._send_to_bt(rid, rd)

    def _send_to_bt(self, cmd_id: str, reminder_data: dict):
        """将提醒发送到 BT driver 的 /robot/command"""
        title = reminder_data.get("title", "") or reminder_data.get("content", "")
        content = reminder_data.get("content", "") or title
        rtime = reminder_data.get("reminder_time", "") or reminder_data.get("reminderTime", "")
        rtype = reminder_data.get("repeat_type", "") or reminder_data.get("repeatType", "none")

        payload = {
            "command": "reminder",
            "command_id": cmd_id,
            "params": {
                "reminder_data": {
                    "title": title,
                    "content": content,
                    "reminder_time": rtime,
                    "repeat_type": rtype,
                }
            }
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._cmd_pub.publish(msg)
        self.get_logger().info(f"→ BT: {title[:20]} @ {rtime}")

    # ── 上行：BT driver → ws_daemon ──

    def _on_bt_response(self, msg: String):
        """接收 BT driver 的执行结果，回传给 ws_daemon_bridge"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        response_type = data.get("type", "command_response")
        cmd_id = data.get("command_id", "")
        cmd = data.get("command", "reminder")
        status = data.get("status", "unknown")
        result = data.get("result", {})

        # 根据原始消息类型决定回传格式
        payload = {
            "type": "relay_message_response" if response_type == "relay" else "command_response",
            "command_id": cmd_id,
            "command": cmd,
            "status": status,
            "result": result,
            "executed_at": datetime.now().isoformat(),
            "source": "reminder_bt_driver",
        }
        response = String()
        response.data = json.dumps(payload, ensure_ascii=False)
        self._result_pub.publish(response)
        self.get_logger().info(f"← WS: {cmd_id} = {status}")


def main(args=None):
    rclpy.init(args=args)
    node = AIPetReminderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
