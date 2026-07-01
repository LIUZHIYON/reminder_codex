"""
reminder_bt_driver — ROS2 BehaviorTree reminder driver (纯话题通信版)

架构:
  relay_node (WebSocket) ──aipet/command_delivery──┐
                                                     ├──→ reminder_bt_driver
  relay_node ───────────────/robot/command───────────┘       │
                                                             │ Action /voice/speak
                                                             ▼
                                                     robot_voice_bridge

特点：
  - 纯话题通信，无数据库/JSON 持久化
  - 黑板变量全内存管理
  - 发布 /robot/bt_status 供监控
  - 支持 Groot2 ZMQ 可视化
"""

import rclpy, sys, os, json, time, threading, struct

try:
    import zmq
except ImportError:
    zmq = None
try:
    import msgpack
except ImportError:
    msgpack = None
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

        # === 参数 ===
        self.declare_parameter("tick_interval_ms", 200)
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("relay_topic", "aipet/command_delivery")
        self.declare_parameter("response_topic", "/robot/command_response")
        self.declare_parameter("status_topic", "/robot/bt_status")

        tick_ms = self.get_parameter("tick_interval_ms").value
        cmd_topic = self.get_parameter("command_topic").value
        relay_topic = self.get_parameter("relay_topic").value
        resp_topic = self.get_parameter("response_topic").value
        status_topic = self.get_parameter("status_topic").value

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST, depth=10)

        # === 发布者 ===
        self.resp_pub = self.create_publisher(String, resp_topic, qos)
        self.status_pub = self.create_publisher(String, status_topic, qos)

        # === 订阅者：支持两个来源 ===
        # 1) 来自 relay_node 的 /robot/command
        self.create_subscription(String, cmd_topic, self._on_cmd, qos)
        # 2) 来自 relay_node 的 aipet/command_delivery（reminder 指令转发）
        self.create_subscription(String, relay_topic, self._on_relay_cmd, qos)

        # === 黑板 ===
        self.blackboard = {
            "pending_reminders": [],
            "current_reminder": {},
            "reminder_id": "",
            "reminder_title": "",
            "reminder_content": "",
            "reminder_time": "",
            "reminder_status": "",
            "is_repeating": False,
            "repeat_type": "",
            "tts_text": "",
            "completed_count": 0,
            "failed_count": 0,
        }

        # === PublishStatus 节点注入发布者 ===
        self._pub_node = PublishStatus()
        self._pub_node.set_publisher(self.resp_pub)

        # === 构建行为树 ===
        tree = self._build_tree(self._pub_node)
        self.bt = BehaviorTree(tree, self.blackboard)

        # === 定时 tick ===
        self._tick_timer = self.create_timer(tick_ms / 1000.0, self._tick)

        # BT status now published on every tick via _tick()

        # === Embedded ZMQ server for Groot2 Monitor ===
        self._zmq_port = 1667
        self._zmq_running = True
        self._zmq_thread = threading.Thread(target=self._zmq_loop, daemon=True)
        self._zmq_thread.start()

        self.get_logger().info(
            f"BT Driver ready (纯话题通信, tick={tick_ms}ms, zmq={self._zmq_port})")

    # ────────── 命令接收 ──────────

    def _on_cmd(self, msg: String):
        """来自 /robot/command 的提醒"""
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        self._add_reminder(data)

    def _on_relay_cmd(self, msg: String):
        """来自 aipet/command_delivery 的提醒（relay_node 转发）"""
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        cmd = data.get("command", "") or data.get("command_type", "")
        if cmd != "reminder":
            return
        self._add_reminder(data)

    def _add_reminder(self, data: dict):
        """将提醒加入黑板（内存），无数据库/JSON 写入"""
        params = data.get("params", {})
        rd = params.get("reminder_data", {})
        title = rd.get("title", rd.get("content", ""))
        content = rd.get("content", "")
        rtime = rd.get("reminder_time", "")
        cid = data.get("command_id", f"local_{int(time.time())}")
        rp = rd.get("repeatType", rd.get("repeat_type", ""))
        ri = bool(rp and rp != "none")

        rec = {
            "command_id": cid,
            "title": title,
            "content": content,
            "reminder_time": rtime,
            "is_repeating": ri,
            "repeat_type": rp,
            "status": "received",
            "received_at": datetime.now().isoformat(),
        }
        self.blackboard["pending_reminders"].insert(0, rec)
        self.get_logger().info(f"Reminder: {title[:20]} @ {rtime}")

    # ────────── BT tick ──────────

    def _tick(self):
        try:
            status = self.bt.tick_once()
            # Publish BT status on every tick (200ms) for real-time monitoring
            self._publish_bt_status()
        except Exception as e:
            self.get_logger().error(f"BT error: {e}")

    # ────────── BT 状态发布（供监控）──────────

    def _publish_bt_status(self):
        """发布行为和黑板状态到 /robot/bt_status（每tick实时更新）"""
        bb = self.blackboard
        status = {
            "timestamp": time.time(),
            "pending_count": len(bb.get("pending_reminders", [])),
            "current_reminder": bb.get("current_reminder", {}),
            "reminder_id": bb.get("reminder_id", ""),
            "reminder_title": bb.get("reminder_title", ""),
            "reminder_content": bb.get("reminder_content", ""),
            "reminder_time": bb.get("reminder_time", ""),
            "reminder_status": bb.get("reminder_status", ""),
            "is_repeating": bb.get("is_repeating", False),
            "repeat_type": bb.get("repeat_type", ""),
            "tts_text": bb.get("tts_text", ""),
            "completed_count": bb.get("completed_count", 0),
            "failed_count": bb.get("failed_count", 0),
            "has_pending": any(
                r.get("status") in ("pending", "received")
                for r in bb.get("pending_reminders", [])
            ),
            "node_statuses": self._collect_node_statuses(),
            "tree_structure": self._collect_tree_structure(),
        }
        try:
            self.status_pub.publish(
                String(data=json.dumps(status, ensure_ascii=False)))
        except Exception:
            pass

    def _collect_node_statuses(self):
        """收集所有 BT 节点的当前状态（用于可视化）"""
        result = {}
        root = getattr(self.bt, "root", None)
        if root:
            self._walk_node(root, result)
        return result

    def _collect_tree_structure(self):
        # Collect nested tree structure for XML generation
        root = getattr(self.bt, "root", None)
        if root:
            return self._walk_structure(root)
        return {}

    def _walk_structure(self, node):
        cls_name = type(node).__name__
        name = getattr(node, "name", cls_name)
        children = []
        for child in getattr(node, "_children", []):
            children.append(self._walk_structure(child))
        # Determine node type for Groot2
        if "Condition" in cls_name: ntype = "Condition"
        elif "Sequence" in cls_name or "Fallback" in cls_name or "Reactive" in cls_name: ntype = "ReactiveSequence"
        elif "Async" in cls_name or "Generate" in cls_name: ntype = "AsyncAction"
        else: ntype = "Action"
        return {"name": name, "type": ntype, "class": cls_name, "children": children}

    def _walk_node(self, node, result: dict):
        result[type(node).__name__] = {
            "name": getattr(node, "name", ""),
            "status": getattr(node, "status", NodeStatus.IDLE).value,
        }
        for child in getattr(node, "_children", []):
            self._walk_node(child, result)

    # ────────── 行为树结构 ──────────

    def _build_tree(self, pub_node):
        check_new = CheckNewReminder()
        check_time = CheckTimeCondition()
        mark_exe = MarkExecuting()
        build_tts = BuildTtsText()
        gen_tts = GenerateTTS()
        reschedule = RescheduleRepeating()

        # 重复提醒路径：执行 → TTS → 重算下次
        repeat_seq = Sequence("RepeatPath")
        repeat_seq.add_child(mark_exe)
        repeat_seq.add_child(build_tts)
        repeat_seq.add_child(gen_tts)
        repeat_seq.add_child(reschedule)
        repeat_seq.add_child(pub_node)

        # 非重复提醒路径：执行 → TTS → 发布
        no_repeat_seq = Sequence("NoRepeatPath")
        no_repeat_seq.add_child(mark_exe)
        no_repeat_seq.add_child(build_tts)
        no_repeat_seq.add_child(gen_tts)
        no_repeat_seq.add_child(pub_node)

        # 分支：先尝试重复路径，失败则走非重复路径
        repeat_fallback = Fallback("RepeatBranch")
        repeat_fallback.add_child(repeat_seq)
        repeat_fallback.add_child(no_repeat_seq)

        # 主流程：到时间了就执行
        main_seq = ReactiveSequence("ReminderProcess")
        main_seq.add_child(check_time)
        main_seq.add_child(repeat_fallback)

        # 根：检查新提醒 → 处理
        root = ReactiveSequence("ProcessReminders")
        root.add_child(check_new)
        root.add_child(main_seq)
        return root


    # === ZMQ Groot2 Server (embedded) ===

    def _zmq_loop(self):
        if zmq is None:
            return
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(f"tcp://0.0.0.0:{self._zmq_port}")
        sock.setsockopt(zmq.LINGER, 0)
        tree_uuid = os.urandom(16)

        while self._zmq_running and rclpy.ok():
            try:
                msg = sock.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.ZMQError:
                time.sleep(0.05)
                continue
            if not msg:
                continue
            req = msg[0]
            if len(req) < 6:
                continue
            proto = req[0]
            req_type = chr(req[1])
            req_uid = struct.unpack("<I", req[2:6])[0]

            try:
                if req_type == "T":  # FULLTREE
                    xml = self._zmq_build_xml().encode("utf-8")
                    header = struct.pack("<BBL", 2, ord("T"), req_uid)
                    reply_header = header + tree_uuid + struct.pack("<I", len(xml))
                    sock.send_multipart([reply_header, xml])

                elif req_type == "S":  # STATUS
                    ns = self._collect_node_statuses()
                    uid_map = {}
                    for idx, cls_name in enumerate(ns.keys()):
                        uid_map[cls_name] = idx + 1
                    status_data = b""
                    status_values = {"SUCCESS": 2, "FAILURE": 3, "RUNNING": 1, "IDLE": 0, "SKIPPED": 4}
                    for cls_name, uid in uid_map.items():
                        info = ns.get(cls_name, {})
                        s = info.get("status", "IDLE")
                        sv = status_values.get(s, 0)
                        status_data += struct.pack("<HB", uid, sv)
                    header = struct.pack("<BBL", 2, ord("S"), req_uid)
                    reply_header = header + tree_uuid + struct.pack("<I", len(status_data))
                    sock.send_multipart([reply_header, status_data or b""])

                elif req_type == "B":  # BLACKBOARD
                    bb = self.blackboard
                    simple = {}
                    for k, v in bb.items():
                        if k in ("pending_reminders", "current_reminder"):
                            continue
                        if not isinstance(v, (str, int, float, bool, type(None))):
                            continue
                        simple[k] = v
                    wrapper = {"ReminderBT": simple}
                    if msgpack:
                        bb_data = msgpack.dumps(wrapper)
                    else:
                        bb_data = json.dumps(wrapper, ensure_ascii=False).encode("utf-8")
                    header = struct.pack("<BBL", 2, ord("B"), req_uid)
                    reply_header = header + tree_uuid + struct.pack("<I", len(bb_data))
                    sock.send_multipart([reply_header, bb_data])

                else:
                    sock.send(b"")
            except Exception:
                try:
                    sock.send(b"")
                except:
                    pass

        sock.close(linger=0)
        ctx.term()

    def _zmq_build_xml(self):
        ts = self._collect_tree_structure()
        lines = ['<?xml version="1.0"?>',
                 '<root BTCPP_format="4">',
                 '  <BehaviorTree ID="ReminderBT">']
        self._uid_counter = 0
        if ts:
            self._zmq_xml_node(lines, ts, 2)
        lines.append("  </BehaviorTree>")
        lines.append("</root>")
        return "\n".join(lines)

    def _zmq_xml_node(self, lines, node, indent):
        self._uid_counter += 1
        uid = self._uid_counter
        name = node.get("name", "node")
        ntype = node.get("type", "Action")
        status = "IDLE"
        ns = self._collect_node_statuses()
        cls_name = node.get("class", "")
        if cls_name in ns:
            status = ns[cls_name].get("status", "IDLE")
        attrs = f'ID="{name}" name="{name}" _uid="{uid}" status="{status}"'
        children = node.get("children", [])
        pad = "  " * indent
        if children:
            lines.append(f"{pad}<{ntype} {attrs}>")
            for child in children:
                self._zmq_xml_node(lines, child, indent + 1)
            lines.append(f"{pad}</{ntype}>")
        else:
            lines.append(f"{pad}<{ntype} {attrs}/>")


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
