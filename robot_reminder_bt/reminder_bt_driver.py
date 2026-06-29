"""
reminder_bt_driver - ROS2 BehaviorTree driver node + ZMQ Monitor bridge
"""
import rclpy, sys, os, json, time, threading, struct
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_engine import BehaviorTree, NodeStatus, Sequence, Fallback, ReactiveSequence
from reminder_bt_nodes import *

try:
    import zmq
except ImportError:
    zmq = None
    print("[ZMQ] pip3 install pyzmq 后安装 ZMQ 功能")


class ReminderBTDriver(Node):

    def __init__(self):
        super().__init__("reminder_bt_driver")

        self.declare_parameter("data_dir", "/data/reminders")
        self.declare_parameter("tick_interval_ms", 200)
        self.declare_parameter("command_topic", "/robot/command")
        self.declare_parameter("response_topic", "/robot/command_response")
        self.declare_parameter("zmq_port", 1667)
        self.declare_parameter("zmq_pub_port", 1668)

        data_dir = self.get_parameter("data_dir").value
        tick_ms = self.get_parameter("tick_interval_ms").value
        cmd_topic = self.get_parameter("command_topic").value
        resp_topic = self.get_parameter("response_topic").value
        zmq_port = self.get_parameter("zmq_port").value
        zmq_pub_port = self.get_parameter("zmq_pub_port").value

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

        # ── 初始化 ZMQ Monitor 桥接 ──
        self._zmq_port = zmq_port
        self._zmq_pub_port = zmq_pub_port
        self._assign_tree_uids(self.bt)
        self._generate_tree_xml()
        # 关键修复：包装每个节点的 execute()，自动记录 self.status
        self._patch_node_execute(self.bt)
        self._start_zmq_server()

        self._tick_timer = self.create_timer(tick_ms / 1000.0, self._tick)
        self.get_logger().info(
            f"BT Driver ready. {len(pending)} reminders. Tick={tick_ms}ms"
            f"  ZMQ monitor on port {zmq_port}")

    # ─────────────────────────────────────────
    #  ZMQ Monitor Bridge
    # ─────────────────────────────────────────

    def _patch_node_execute(self, tree: BehaviorTree):
        """包装每个节点的 execute()，自动将返回值写入 self.status。
        因为 bt_engine 的 execute() 实现都没有更新 self.status。
        """
        def walk(node):
            old_execute = node.execute
            def new_execute():
                result = old_execute()
                node.status = result
                return result
            node.execute = new_execute
            for child in getattr(node, '_children', []):
                walk(child)
        walk(tree.root)

    def _assign_tree_uids(self, tree: BehaviorTree):
        """递归为所有树节点分配唯一 UID"""
        self._uid_counter = 0
        self._uid_to_node = {}
        self._node_to_uid = {}

        def walk(node):
            self._uid_counter += 1
            uid = self._uid_counter
            self._uid_to_node[uid] = node
            self._node_to_uid[id(node)] = uid
            node._bt_uid = uid
            children = getattr(node, '_children', None)
            if children:
                for child in children:
                    walk(child)

        walk(tree.root)
        self.get_logger().info(f"[ZMQ] Assigned {self._uid_counter} UIDs")

    def _generate_tree_xml(self):
        """从实际树结构生成完整 XML"""
        STATUS_MAP = {0: "IDLE", 1: "RUNNING", 2: "SUCCESS", 3: "FAILURE", 4: "SKIPPED"}

        def node_xml(node):
            cls = type(node).__name__
            name = getattr(node, 'name', cls)
            uid = self._node_to_uid.get(id(node), 0)
            children = getattr(node, '_children', None)
            if children and len(children) > 0:
                inner = ''.join(node_xml(c) for c in children)
                return f'<{cls} name="{name}" _uid="{uid}">{inner}</{cls}>'
            return f'<{cls} name="{name}" _uid="{uid}" />'

        self._tree_uuid = os.urandom(16)
        self._tree_xml = '<?xml version="1.0"?><root BTCPP_format="4">' \
                         '<BehaviorTree ID="reminder_bt">'
        self._tree_xml += node_xml(self.bt.root)
        self._tree_xml += '</BehaviorTree></root>'

    def _collect_status_buffer(self) -> bytes:
        """读取当前各节点的 status 状态，打包成二进制 buffer"""
        buf = b''
        for uid in sorted(self._uid_to_node.keys()):
            node = self._uid_to_node[uid]
            st = getattr(node, 'status', None)
            if isinstance(st, NodeStatus):
                sv = {"IDLE": 0, "RUNNING": 1, "SUCCESS": 2, "FAILURE": 3,
                       "SKIPPED": 4}.get(st.value, 0)
            else:
                sv = 0
            buf += struct.pack('<HB', uid, sv)
        return buf

    def _collect_blackboard_msgpack(self) -> bytes:
        """将黑板数据打包为 MessagePack"""
        try:
            import msgpack
            bb = dict(self.blackboard)
            # 清理不可序列化的值
            cleaned = {}
            for k, v in bb.items():
                if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    cleaned[k] = v
                elif isinstance(v, bytes):
                    cleaned[k] = v.hex()
                else:
                    cleaned[k] = str(v)
            return msgpack.packb(cleaned)
        except Exception as e:
            self.get_logger().warning(f"[ZMQ] msgpack 打包失败: {e}")
            return b''

    def _build_reply(self, req_type: int, req_uid: int, payload: bytes) -> bytes:
        """构建单帧回复: header(6) + uuid(16) + content_len(4) + payload"""
        reply = struct.pack('<BBL', 2, req_type, req_uid)
        reply += self._tree_uuid
        reply += struct.pack('<I', len(payload))
        reply += payload
        return reply

    def _send_multipart(self, sock, reply_bytes: bytes):
        """分两帧发送：header(22) + 内容"""
        header_part = reply_bytes[:22]
        content_part = reply_bytes[26:]  # 跳过4字节长度
        sock.send_multipart([header_part, content_part])

    def _zmq_server_loop(self):
        """ZMQ REP 服务器主循环（独立线程运行）"""
        if zmq is None:
            return

        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(f"tcp://0.0.0.0:{self._zmq_port}")
        self.get_logger().info(f"[ZMQ] Server ready on port {self._zmq_port}")

        while True:
            try:
                msg = sock.recv_multipart()
                if not msg:
                    continue
                req = msg[0]
                if len(req) < 6:
                    self._send_multipart(sock, self._build_reply(0, 0, b''))
                    continue

                proto, req_type, req_uid = struct.unpack('<BBL', req[:6])

                if req_type == ord('T'):
                    # FULLTREE
                    xml_bytes = self._tree_xml.encode('utf-8')
                    reply = self._build_reply(req_type, req_uid, xml_bytes)
                    self._send_multipart(sock, reply)

                elif req_type == ord('S'):
                    # STATUS - 只读当前状态，不 tick（由 ROS2 定时器驱动）
                    buf = self._collect_status_buffer()
                    reply = self._build_reply(req_type, req_uid, buf)
                    self._send_multipart(sock, reply)

                elif req_type == ord('B'):
                    # BLACKBOARD - 返回 msgpack
                    bb_raw = self._collect_blackboard_msgpack()
                    reply = self._build_reply(req_type, req_uid, bb_raw)
                    self._send_multipart(sock, reply)

                else:
                    # 未知类型
                    reply = self._build_reply(req_type, req_uid, b'')
                    self._send_multipart(sock, reply)

            except zmq.ZMQError as e:
                self.get_logger().error(f"[ZMQ] Error: {e}")
                try:
                    sock.close()
                except Exception:
                    pass
                time.sleep(1)
                ctx = zmq.Context()
                sock = ctx.socket(zmq.REP)
                sock.bind(f"tcp://0.0.0.0:{self._zmq_port}")
                self.get_logger().info("[ZMQ] Socket recreated")
            except Exception as e:
                self.get_logger().error(f"[ZMQ] {e}")
                try:
                    self._send_multipart(sock, self._build_reply(0, 0, b''))
                except Exception:
                    pass

    def _start_zmq_server(self):
        """启动 ZMQ 服务器线程"""
        if zmq is None:
            self.get_logger().warning("[ZMQ] pyzmq 未安装，跳过 ZMQ 服务器")
            return
        t = threading.Thread(target=self._zmq_server_loop, daemon=True)
        t.start()
        self.get_logger().info("[ZMQ] 服务器线程已启动")

    # ─────────────────────────────────────────
    #  原 ROS2 功能（未改动）
    # ─────────────────────────────────────────

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
        reschedule = RescheduleRepeating()

        repeat_seq = Sequence("RepeatPath")
        repeat_seq.add_child(mark_exe)
        repeat_seq.add_child(build_tts)
        repeat_seq.add_child(gen_tts)
        repeat_seq.add_child(reschedule)
        repeat_seq.add_child(pub_node)

        no_repeat_seq = Sequence("NoRepeatPath")
        no_repeat_seq.add_child(mark_exe)
        no_repeat_seq.add_child(build_tts)
        no_repeat_seq.add_child(gen_tts)
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
