"""
groot2_server — ZMQ Groot2 可视化服务器

与 reminder_bt_driver 配合使用，通过 ZMQ 协议向 Groot2 或 bt_monitor_server
暴露行为树的结构和节点状态，支持实时观察节点颜色变化。

协议: ZMQ REP, TCP port 1669
格式: Groot2 ZMQ 协议 (proto=2)

运行: ros2 run robot_reminder_bt groot2_server
"""

import rclpy, os, json, time, struct, random
from rclpy.node import Node
from std_msgs.msg import String
import threading

try:
    import zmq
except ImportError:
    zmq = None
    print("[Groot2] WARNING: pyzmq not installed. Install: pip3 install pyzmq")


class Groot2Server(Node):
    """ZMQ 服务器，向 Groot2 暴露行为树状态"""

    def __init__(self):
        super().__init__("groot2_server")

        self.declare_parameter("zmq_port", 1669)
        self.declare_parameter("bt_status_topic", "/robot/bt_status")

        self.zmq_port = self.get_parameter("zmq_port").value
        status_topic = self.get_parameter("bt_status_topic").value

        # 最新 BT 状态缓存
        self._bt_status = {
            "node_statuses": {},
            "pending_count": 0,
            "reminder_title": "",
            "reminder_status": "",
        }

        # 订阅 BT driver 的状态话题
        self.create_subscription(String, status_topic, self._on_bt_status, 10)

        # ZMQ 树缓存（Groot2 请求 FULLTREE 时返回）
        self._tree_xml = ""

        # 启动 ZMQ 服务器线程
        self._running = True
        self._thread = threading.Thread(target=self._zmq_loop, daemon=True)
        self._thread.start()

        self.get_logger().info(f"Groot2 ZMQ server on port {self.zmq_port}")

    def _on_bt_status(self, msg: String):
        """缓存 BT driver 发布的最新状态"""
        try:
            data = json.loads(msg.data)
            self._bt_status = data
        except Exception:
            pass

    def _build_tree_xml(self):
        # Build Groot2 XML dynamically from node_statuses with _uid
        ns = self._bt_status.get("node_statuses", {})
        nk = list(ns.keys())
        lines = ['<?xml version="1.0"?>',
                 '<root BTCPP_format="4">',
                 '  <BehaviorTree ID="ReminderBT">']
        if nk:
            uid_map = {name: i+1 for i, name in enumerate(nk)}
            # Group into controls vs leafs
            control_types = {"Sequence", "Fallback", "ReactiveSequence"}
            controls = [k for k in nk if any(ct in k for ct in control_types)]
            leafs = [k for k in nk if k not in controls]
            root_name = controls[0] if controls else nk[0]
            root_uid = uid_map[root_name]
            root_info = ns.get(root_name, {})
            root_attrs = f'name="{root_name}" _uid="{root_uid}"'
            if root_info: root_attrs += f' status="{root_info.get("status", "IDLE")}"'
            lines.append(f'    <ReactiveSequence ID="{root_name}" {root_attrs}>')
            children = controls[1:] + leafs if controls else nk[1:]
            for child in children:
                cuid = uid_map[child]
                cinfo = ns.get(child, {})
                # Map class name to Groot2 type
                if "Condition" in child: ctype = "Condition"
                elif "Sequence" in child or "Fallback" in child or "Reactive" in child: ctype = "ReactiveSequence"
                elif "Async" in child or "Generate" in child: ctype = "AsyncAction"
                else: ctype = "Action"
                cattrs = f'ID="{child}" name="{child}" _uid="{cuid}"'
                if cinfo: cattrs += f' status="{cinfo.get("status", "IDLE")}"'
                lines.append(f"      <{ctype} {cattrs}/>")
            lines.append("    </ReactiveSequence>")
        lines.append("  </BehaviorTree>")
        lines.append("</root>")
        return "\n".join(lines)
    def _zmq_loop(self):
        if zmq is None:
            return
        ctx = ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(f"tcp://0.0.0.0:{self.zmq_port}")
        sock.setsockopt(zmq.LINGER, 0)

        tree_uuid = os.urandom(16)

        while self._running and rclpy.ok():
            try:
                msg = sock.recv_multipart()
                if not msg:
                    continue
                req = msg[0]
                if len(req) < 6:
                    continue

                proto = req[0]
                req_type = chr(req[1])
                req_uid = struct.unpack('<I', req[2:6])[0]
                payload = req[6:] if len(req) > 6 else b''

                if req_type == 'T':  # FULLTREE 请求
                    xml = self._build_tree_xml().encode('utf-8')
                    header = struct.pack('<BBL', 2, ord('T'), req_uid)
                    reply = header + tree_uuid + struct.pack('<I', len(xml)) + xml
                    sock.send(reply)

                elif req_type == 'S':  # STATUS 请求
                    ns = self._bt_status.get("node_statuses", {})
                    status_data = b''
                    ns = self._bt_status.get("node_statuses", {})
                    uid_map = {}
                    for idx, cls_name in enumerate(ns.keys()):
                        uid_map[cls_name] = idx + 1
                    # Handle both old and new status formats
                    status_values = {"SUCCESS": 2, "FAILURE": 3, "RUNNING": 1, "IDLE": 0, "SKIPPED": 4}
                    status_values = {"SUCCESS": 2, "FAILURE": 3, "RUNNING": 1,
                                     "IDLE": 0, "SKIPPED": 4}
                    for cls_name, uid in uid_map.items():
                        info = ns.get(cls_name, {})
                        s = info.get("status", "IDLE")
                        sv = status_values.get(s, 0)
                        status_data += struct.pack('<HB', uid, sv)

                    header = struct.pack('<BBL', 2, ord('S'), req_uid)
                    reply = header + tree_uuid + struct.pack('<I', len(status_data)) + status_data
                    sock.send(reply)

                elif req_type == 'B':  # BLACKBOARD（全量转发）
                    bb_data = json.dumps(self._bt_status, ensure_ascii=False).encode('utf-8')
                    header = struct.pack('<BBL', 2, ord('B'), req_uid)
                    reply = header + tree_uuid + struct.pack('<I', len(bb_data)) + bb_data
                    sock.send(reply)

                else:
                    sock.send(b'')

            except zmq.ZMQError:
                break
            except Exception as e:
                self.get_logger().error(f"ZMQ error: {e}")
                try:
                    sock.send(b'')
                except Exception:
                    pass

        sock.close(linger=0)
        ctx.term()

    def destroy_node(self):
        self._running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Groot2Server()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

