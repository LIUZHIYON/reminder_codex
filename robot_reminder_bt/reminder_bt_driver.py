"""
reminder_bt_driver — ROS2 节点驱动行为树

功能:
1. 订阅 /robot/command 接收提醒
2. 使用行为树处理提醒调度
3. 发布 /robot/command_response 回复结果
4. 本地持久化存储
"""

import rclpy, sys, os, json, time, threading
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_engine import BehaviorTree, NodeStatus
from reminder_bt_nodes import *


class ReminderBTDriver(Node):
    """行为树驱动节点"""

    def __init__(self):
        super().__init__("reminder_bt_driver")

        # 参数
        self.declare_parameter("data_dir", "/data/reminders")
        self.declare_parameter("tick_interval_ms", 200)
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("response_topic", "/robot/command_response")

        data_dir = self.get_parameter("data_dir").value
        tick_ms = self.get_parameter("tick_interval_ms").value
        cmd_topic = self.get_parameter("command_topic").value
        resp_topic = self.get_parameter("response_topic").value

        os.makedirs(data_dir, exist_ok=True)

        # 加载持久化的提醒列表
        self._reminders_file = os.path.join(data_dir, "pending_reminders.json")
        pending = self._load_reminders()

        # QoS
        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST, depth=10)

        # 发布者
        self.resp_pub = self.create_publisher(String, resp_topic, qos)

        # 订阅者
        self.cmd_sub = self.create_subscription(String, cmd_topic, self._on_cmd, qos)

        # 构建行为树
        self._pub_node = PublishStatus()
        self._pub_node.set_publisher(self.resp_pub)
        tree = self._build_tree(self._pub_node)
        self.blackboard = {
            "data_dir": data_dir,
            "pending_reminders": pending,
        }
        self.bt = BehaviorTree(tree, self.blackboard)

        # 定时 tick
        self._tick_timer = self.create_timer(tick_ms / 1000.0, self._tick)
        self.get_logger().info(f"BT Driver ready. {len(pending)} reminders loaded. Tick={tick_ms}ms")

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
        """接收提醒命令，加入待处理列表"""
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
        self.get_logger().info(f"Reminder received: {title[:20]} @ {rtime}")

    def _tick(self):
        """定时执行行为树"""
        try:
            self.bt.tick_once()
            self._save_reminders()
        except Exception as e:
            self.get_logger().error(f"BT tick error: {e}")

    def _build_tree(self, pub_node):
        """构建提醒处理行为树"""
        check_new = CheckNewReminder()
        check_time = CheckTimeCondition()
        mark_exe = MarkExecuting()
        build_tts = BuildTtsText()
        gen_tts = GenerateTTS()
        save = SavePersistence()
        reschedule = RescheduleRepeating()
        check_repeat = CheckRepeating()

        # 重复提醒树: CheckTime -> Mark -> Build -> TTS -> Save -> Reschedule -> Publish
        repeat_seq = Sequence("RepeatPath")
        repeat_seq.add_child(mark_exe)
        repeat_seq.add_child(build_tts)
        repeat_seq.add_child(gen_tts)
        repeat_seq.add_child(save)
        repeat_seq.add_child(reschedule)
        repeat_seq.add_child(pub_node)

        # 非重复: CheckTime -> Mark -> Build -> TTS -> Save -> Publish
        no_repeat_seq = Sequence("NoRepeatPath")
        no_repeat_seq.add_child(mark_exe)
        no_repeat_seq.add_child(build_tts)
        no_repeat_seq.add_child(gen_tts)
        no_repeat_seq.add_child(save)
        no_repeat_seq.add_child(pub_node)

        # 根据是否重复分支
        repeat_fallback = Fallback("RepeatOrNot")
        repeat_fallback.add_child(repeat_seq)    # 重复路径
        repeat_fallback.add_child(no_repeat_seq) # 非重复路径

        # 主流程: CheckTime -> 播放分支
        main_seq = ReactiveSequence("ReminderProcess")
        main_seq.add_child(check_time)
        main_seq.add_child(repeat_fallback)

        # 检查是否有新提醒
        # 先检查 check_new，有新提醒则设置到黑板
        process_seq = ReactiveSequence("ProcessReminders")
        process_seq.add_child(check_new)
        process_seq.add_child(main_seq)

        return process_seq


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
