"""
blackboard_node.py — 提醒系统黑板节点 (ROS2)

作为行为树的黑板，管理共享状态：
- 待处理提醒队列 (来自 /robot/command)
- 当前处理的提醒
- 播放状态、机器人状态

话题:
  发布: /reminder/blackboard/state, /reminder/tts/request
  订阅: /robot/command, /reminder/blackboard/action, /reminder/tts/feedback, /robot/status

用法: ros2 run robot_reminder_bt blackboard_node
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
import json, time
from typing import Optional, Dict, Any, List


class BlackboardNode(Node):
    def __init__(self):
        super().__init__("reminder_blackboard")
        self.declare_parameter("state_publish_interval", 1.0)
        self.declare_parameter("max_reminders", 50)

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10)

        # 内部状态
        self._pending: List[Dict] = []
        self._current: Optional[Dict] = None
        self._history: List[Dict] = []
        self._robot_online = False
        self._ws_connected = False
        self._is_playing = False
        self._last_tts_result = None
        self._tick_count = 0

        # 发布者
        self.state_pub = self.create_publisher(String, "/reminder/blackboard/state", qos)
        self.tts_req_pub = self.create_publisher(String, "/reminder/tts/request", qos)

        # 订阅者
        self.cmd_sub = self.create_subscription(String, "/robot/command", self._on_command, qos)
        self.action_sub = self.create_subscription(String, "/reminder/blackboard/action", self._on_action, qos)
        self.tts_fb_sub = self.create_subscription(String, "/reminder/tts/feedback", self._on_tts_feedback, qos)
        self.status_sub = self.create_subscription(String, "/robot/status", self._on_robot_status, qos)

        # 定时器
        self.create_timer(self.get_parameter("state_publish_interval").value, self._publish_state)
        self.create_timer(5.0, self._heartbeat)
        self.get_logger().info("黑板节点已启动")

    def _on_command(self, msg: String):
        """接收 /robot/command — 来自 websocket_node 的提醒命令"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        cmd = data.get("command", "")
        cid = data.get("command_id", "")
        params = data.get("command_params") or data.get("params", {})
        if cmd == "reminder":
            rd = params.get("reminder_data", {}) if isinstance(params, dict) else {}
            title = rd.get("title", "") or rd.get("content", "") or params.get("title", "")
            content = rd.get("content", "") or title
            rtime = rd.get("reminder_time", "") or params.get("reminder_time", "")
            if title:
                self._pending.append({"command_id": cid, "title": title, "content": content,
                    "reminder_time": rtime, "received_at": time.time(), "source": "websocket"})
                if len(self._pending) > self.get_parameter("max_reminders").value:
                    self._pending = self._pending[-self.get_parameter("max_reminders").value:]
                self.get_logger().info(f"收到提醒: [{cid}] {title[:30]} (队列: {len(self._pending)})")
        elif cmd == "bt_reset":
            self._reset()
        elif cmd == "bt_status":
            self._publish_state()

    def _on_action(self, msg: String):
        """接收行为树节点动作请求"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        act = data.get("action", "")
        if act == "fetch_next":
            if self._pending and not self._is_playing:
                self._current = self._pending.pop(0)
                self._is_playing = True
                self.get_logger().info(f"取提醒: [{self._current.get('command_id')}]")
            else:
                self._current = None
        elif act == "mark_complete":
            if self._current:
                self._current["completed_at"] = time.time()
                self._current["status"] = "completed"
                self._history.append(self._current)
                if len(self._history) > 100:
                    self._history = self._history[-100:]
                self._current = None
                self._is_playing = False
                self.get_logger().info(f"标记完成: {data.get('command_id','')}")
        elif act == "mark_failed":
            if self._current:
                self._current["status"] = "failed"
                self._history.append(self._current)
                self._current = None
                self._is_playing = False
        elif act == "tts_request":
            text = data.get("text", "")
            if text:
                self.tts_req_pub.publish(String(data=json.dumps({"text": text, "timestamp": time.time()})))
        elif act == "reset":
            self._reset()

    def _on_tts_feedback(self, msg: String):
        try:
            self._last_tts_result = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_robot_status(self, msg: String):
        try:
            s = json.loads(msg.data)
            self._robot_online = s.get("online", self._robot_online)
            self._ws_connected = s.get("ws_connected", self._ws_connected)
        except json.JSONDecodeError:
            pass

    def _publish_state(self):
        self._tick_count += 1
        state = {
            "tick": self._tick_count, "timestamp": time.time(),
            "pending_count": len(self._pending),
            "has_current": self._current is not None,
            "current_reminder": {"command_id": self._current.get("command_id",""),
                "title": self._current.get("title",""), "content": self._current.get("content","")}
                if self._current else None,
            "is_playing": self._is_playing, "history_count": len(self._history),
            "robot_online": self._robot_online, "ws_connected": self._ws_connected,
        }
        self.state_pub.publish(String(data=json.dumps(state, ensure_ascii=False)))

    def _heartbeat(self):
        self.get_logger().debug(f"#{self._tick_count} 队列:{len(self._pending)} 播放:{self._is_playing}")

    def _reset(self):
        self._pending.clear(); self._current = None; self._is_playing = False
        self._last_tts_result = None; self._tick_count = 0

    def destroy_node(self):
        self.get_logger().info("黑板节点关闭")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BlackboardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
