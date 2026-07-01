"""
reminder_bt_node.py — ROS2 行为树节点

集成行为树引擎与 ROS2 系统：
  - 每 100ms tick 一次行为树
  - 通过 /tts/text 话题与 doubao_tts_node 通信
  - 通过 /robot/command 话题与 websocket_node 通信
  - 通过 HTTP API 与提醒系统（Flask:5000）通信

运行:
  ros2 run robot_reminder_bt reminder_bt_node
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
import json

from .bt_engine import NodeStatus, print_tree
from .reminder_tree import build_reminder_tree
from .reminder_nodes import HttpClient


class ReminderBTNode(Node):
    """ROS2 行为树节点"""

    def __init__(self):
        super().__init__("reminder_bt_node")

        # ── 参数 ──
        self.declare_parameter("reminder_api_url", "http://localhost:5000")
        self.declare_parameter("tick_interval_ms", 100)
        self.declare_parameter("check_interval_ms", 2000)
        self.declare_parameter("tts_text_topic", "/tts/text")
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("status_topic", "/robot/status")
        self.declare_parameter("websocket_chat_topic", "/robot/chat")

        self.api_url = self.get_parameter("reminder_api_url").value
        tick_ms = self.get_parameter("tick_interval_ms").value
        self.tts_text_topic = self.get_parameter("tts_text_topic").value
        self.command_topic = self.get_parameter("command_topic").value

        # ── HTTP 客户端 ──
        self.http_client = HttpClient(base_url=self.api_url)

        # ── 发布者 ──
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.tts_pub = self.create_publisher(String, self.tts_text_topic, qos)
        self.status_pub = self.create_publisher(String, "/robot/bt_status", qos)

        # ── 订阅者 ──
        self.cmd_sub = self.create_subscription(
            String, self.command_topic, self._on_command, qos
        )
        self.status_sub = self.create_subscription(
            String,
            self.get_parameter("status_topic").value,
            self._on_external_status,
            qos
        )

        # ── 构建行为树 ──
        self.bt = build_reminder_tree(
            http_client=self.http_client,
            ws_client=None,
            tts_topic_pub=self.tts_pub,
        )

        self._tick_count = 0
        self._last_check_time = 0

        # ── 定时器 tick ──
        self.create_timer(tick_ms / 1000.0, self._tick_bt)

        self.get_logger().info("=" * 50)
        self.get_logger().info("ReminderBTNode 已启动")
        self.get_logger().info(f"  提醒 API: {self.api_url}")
        self.get_logger().info(f"  TTS 话题: {self.tts_text_topic}")
        self.get_logger().info(f"  命令话题: {self.command_topic}")
        self.get_logger().info(f"  Tick 间隔: {tick_ms}ms")
        self.get_logger().info("=" * 50)

        # 打印树结构
        self.get_logger().info("\n" + print_tree(self.bt.root))

    def _tick_bt(self):
        """每个定时器周期 tick 一次行为树"""
        self._tick_count += 1

        # 发布状态（每 50 tick 一次，约 5s）
        if self._tick_count % 50 == 0:
            msg = String()
            msg.data = json.dumps({
                "tick_count": self._tick_count,
                "bt_status": self.bt.root.status.value,
            })
            self.status_pub.publish(msg)

        status = self.bt.tick_once()
        if status == NodeStatus.SUCCESS:
            self.get_logger().debug("BT tick: SUCCESS")
        elif status == NodeStatus.FAILURE:
            self.get_logger().debug("BT tick: FAILURE (无待办)")

    def _on_command(self, msg: String):
        """接收外部命令（来自 websocket_node 的 /robot/command）"""
        try:
            cmd = json.loads(msg.data)
            command = cmd.get("command", "")
            if command == "reminder":
                # 手动触发立即检查
                self._last_check_time = 0
                self.get_logger().info(f"收到 reminder 命令，触发检查")
            elif command == "bt_reset":
                self.bt.halt()
                self.get_logger().info("行为树已重置")
            elif command == "bt_status":
                self._print_bt_status()
        except json.JSONDecodeError:
            self.get_logger().warn(f"命令解析失败: {msg.data[:100]}")

    def _on_external_status(self, msg: String):
        """接收外部状态更新（写入黑板）"""
        try:
            data = json.loads(msg.data)
            self.bt.blackboard.update(data)
        except json.JSONDecodeError:
            pass

    def _print_bt_status(self):
        """打印行为树状态"""
        self.get_logger().info("=" * 40)
        self.get_logger().info("行为树状态:")
        self.get_logger().info(print_tree(self.bt.root))
        self.get_logger().info(f"  Tick 计数: {self._tick_count}")
        self.get_logger().info(f"  黑板内容: {json.dumps(self.bt.blackboard, indent=2, ensure_ascii=False)}")
        self.get_logger().info("=" * 40)

    def destroy_node(self):
        self.bt.halt()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReminderBTNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
