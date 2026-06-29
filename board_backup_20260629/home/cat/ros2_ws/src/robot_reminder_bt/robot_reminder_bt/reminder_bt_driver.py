"""
reminder_bt_driver - ROS2 BehaviorTree driver node
"""

import rclpy, sys, os, json, time, threading
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_engine import BehaviorTree, NodeStatus, Sequence, Fallback, ReactiveSequence
from reminder_bt_nodes import *


class ReminderBTDriver(Node):

    def __init__(self):
        super().__init__("reminder_bt_driver")

        self.declare_parameter("data_dir", "/data/reminders")
        self.declare_parameter("tick_interval_ms", 200)
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("response_topic", "/robot/command_response")

        data_dir = self.get_parameter("data_dir").value
        tick_ms = self.get_parameter("tick_interval_ms").value
        cmd_topic = self.get_parameter("command_topic").value
        resp_topic = self.get_parameter("response_topic").value

        os.makedirs(data_dir, exist_ok=True)

        self._reminders_file = os.path.join(data_dir, "pending_reminders.json")
        pending = self._load_reminders()

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST, depth=10)

        self.resp_pub = self.create_publisher(String, resp_topic, qos)
        self.cmd_sub = self.create_subscription(String, cmd_topic, self._on_cmd, qos)

        self._pub_node = PublishStatus()
        self._pub_node.set_publisher(self.resp_pub)
        tree = self._build_tree(self._pub_node)
        self.blackboard = {"data_dir": data_dir, "pending_reminders": pending}
        self.bt = BehaviorTree(tree, self.blackboard)

        self._tick_timer = self.create_timer(tick_ms / 1000.0, self._tick)
        self.get_logger().info(f"BT Driver ready. {len(pending)} reminders. Tick={tick_ms}ms")

    def _load_reminders(self):
        if os.path.exists(self._reminders_file):
            try:
                with open(self._reminders_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_reminders(self):
        try:
            with open(self._reminders_file, "w", encoding="utf-8") as f:
                json.dump(self.blackboard.get("pending_reminders", []), f,
                          ensure_ascii=False, indent=2)
        except Exception as e:
            self.get_logger().error(f"Save error: {e}")

    def _on_cmd(self, msg: String):
        """Receive reminder from websocket"""
        try:
            data = json.loads(msg.data)
        except:
            return
        cmd = data.get("command", "")
        if cmd != "reminder":
            return
        params = data.get("params", {})
        rd = params.get("reminder_data", {})
        title = rd.get("title", rd.get("content", ""))
        content = rd.get("content", "")
        rtime = rd.get("reminder_time", "")
        cid = data.get("command_id", f"local_{int(time.time())}")
        rp = rd.get("repeatType", rd.get("repeat_type", ""))
        ri = bool(rp and rp != "none")

        rec = {"command_id": cid, "title": title, "content": content,
               "reminder_time": rtime, "is_repeating": ri, "repeat_type": rp,
               "status": "received", "received_at": datetime.now().isoformat()}
        self.blackboard["pending_reminders"].insert(0, rec)
        self._save_reminders()
        self.get_logger().info(f"Reminder: {title[:20]} @ {rtime}")

    def _tick(self):
        try:
            self.bt.tick_once()
        except Exception as e:
            self.get_logger().error(f"BT error: {e}")

    def _build_tree(self, pub_node):
        check_new = CheckNewReminder()
        check_time = CheckTimeCondition()
        mark_exe = MarkExecuting()
        build_tts = BuildTtsText()
        gen_tts = GenerateTTS()
        save = SavePersistence()
        reschedule = RescheduleRepeating()

        repeat_seq = Sequence("RepeatPath")
        repeat_seq.add_child(mark_exe)
        repeat_seq.add_child(build_tts)
        repeat_seq.add_child(gen_tts)
        repeat_seq.add_child(save)
        repeat_seq.add_child(reschedule)
        repeat_seq.add_child(pub_node)

        no_repeat_seq = Sequence("NoRepeatPath")
        no_repeat_seq.add_child(mark_exe)
        no_repeat_seq.add_child(build_tts)
        no_repeat_seq.add_child(gen_tts)
        no_repeat_seq.add_child(save)
        no_repeat_seq.add_child(pub_node)

        repeat_fallback = Fallback("RepeatBranch")
        repeat_fallback.add_child(repeat_seq)
        repeat_fallback.add_child(no_repeat_seq)

        main_seq = ReactiveSequence("ReminderProcess")
        main_seq.add_child(check_time)
        main_seq.add_child(repeat_fallback)

        root = ReactiveSequence("ProcessReminders")
        root.add_child(check_new)
        root.add_child(main_seq)
        return root


def main(args=None):
    rclpy.init(args=args)
    node = ReminderBTDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
