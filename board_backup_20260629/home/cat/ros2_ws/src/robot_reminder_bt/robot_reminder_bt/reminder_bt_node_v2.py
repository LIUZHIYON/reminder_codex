"""
reminder_bt_node_v2.py — ROS2 行为树节点 (v2 — 话题通信版)

v2 改动:
  - 移除 HTTP 依赖，全部通过 ROS2 话题通信
  - 黑板状态由话题订阅回调直接更新
  - 发布 /reminder/blackboard/action 通知黑板节点执行动作
  - 发布 /tts/text 触发 doubao TTS
  - 发布 /robot/command (command_response) 通知 websocket_node

运行: ros2 run robot_reminder_bt reminder_bt_node_v2
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
import json, time

from bt_engine import print_tree
from reminder_tree_v2 import build_reminder_tree_v2


class ReminderBTNodeV2(Node):
    """ROS2 行为树节点 v2 — 全话题通信"""

    def __init__(self):
        super().__init__("reminder_bt_node_v2")

        # 参数
        self.declare_parameter("tick_interval_ms", 200)
        self.declare_parameter("tts_text_topic", "/tts/text")
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("blackboard_state_topic", "/reminder/blackboard/state")
        self.declare_parameter("blackboard_action_topic", "/reminder/blackboard/action")
        self.declare_parameter("tts_feedback_topic", "/reminder/tts/feedback")

        tick_ms = self.get_parameter("tick_interval_ms").value
        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10)

        # ── 黑板 (由话题订阅回调更新) ──
        self.blackboard = {
            "blackboard_state": {},
            "tts_feedback": {},
            "current_reminder": {},
            "pending_count": 0,
            "tts_text": "",
            "tts_sent_time": 0,
        }

        # ── 发布者 ──
        self.tts_pub = self.create_publisher(String, self.get_parameter("tts_text_topic").value, qos)
        self.cmd_pub = self.create_publisher(String, self.get_parameter("command_topic").value, qos)
        self.action_pub = self.create_publisher(String, self.get_parameter("blackboard_action_topic").value, qos)
        self.bt_status_pub = self.create_publisher(String, "/robot/bt_status", qos)

        # 注入发布函数到黑板
        self.blackboard["tts_pub"] = lambda text: self.tts_pub.publish(String(data=text))
        self.blackboard["cmd_pub"] = lambda data: self.cmd_pub.publish(String(data=data))
        self.blackboard["action_pub"] = lambda data: self.action_pub.publish(String(data=data))

        # ── 订阅者 ──
        self.create_subscription(String, self.get_parameter("blackboard_state_topic").value,
            self._on_blackboard_state, qos)
        self.create_subscription(String, self.get_parameter("tts_feedback_topic").value,
            self._on_tts_feedback, qos)

        # ── 构建行为树 ──
        self.bt = build_reminder_tree_v2(blackboard=self.blackboard)

        self._tick_count = 0
        self.create_timer(tick_ms / 1000.0, self._tick_bt)
        self.create_timer(5.0, self._publish_bt_status)

        self.get_logger().info("行为树节点 v2 已启动 (全话题通信)")

    def _on_blackboard_state(self, msg: String):
        try:
            state = json.loads(msg.data)
            self.blackboard["blackboard_state"] = state
            cur = state.get("current_reminder")
            if cur and cur.get("title"):
                self.blackboard["current_reminder"] = cur
            self.blackboard["pending_count"] = state.get("pending_count", 0)
        except json.JSONDecodeError:
            pass

    def _on_tts_feedback(self, msg: String):
        try:
            self.blackboard["tts_feedback"] = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _tick_bt(self):
        self._tick_count += 1
        try:
            self.bt.tick_once()
        except Exception as e:
            self.get_logger().error(f"BT tick error: {e}")

    def _publish_bt_status(self):
        status = {
            "tick_count": self._tick_count,
            "pending_count": self.blackboard.get("pending_count", 0),
            "current": self.blackboard.get("current_reminder", {}).get("title", ""),
            "timestamp": time.time(),
        }
        self.bt_status_pub.publish(String(data=json.dumps(status, ensure_ascii=False)))

    def destroy_node(self):
        self.get_logger().info("行为树节点 v2 关闭")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReminderBTNodeV2()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
