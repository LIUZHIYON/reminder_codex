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
        # Build nested Groot2 XML from tree_structure (priority) or flat node_statuses
        tree = self._bt_status.get("tree_structure", {})
        ns = self._bt_status.get("node_statuses", {})
        lines = ['<?xml version="1.0"?>',
                 '<root BTCPP_format="4">',
                 '  <BehaviorTree ID="ReminderBT">']
        self._uid_counter = 0
        if tree:
            self._gen_xml_node(lines, tree, ns, 2)
        elif ns:
            # Fallback: flat list
            self._uid_counter = 0
            for name, info in ns.items():
                self._uid_counter += 1
                ct = info.get("name", name)
                cattrs = f'ID="{ct}" name="{ct}" _uid="{self._uid_counter}" status="{info.get("status","IDLE")}"'
                lines.append(f"    <Action {cattrs}/>")
        lines.append("  </BehaviorTree>")
        lines.append("</root>")
        return "\n".join(lines)

    def _gen_xml_node(self, lines, node, ns, indent):
        self._uid_counter += 1
        uid = self._uid_counter
        cls_name = node.get("class", "Action")
        name = node.get("name", cls_name)
        ntype = node.get("type", "Action")
        info = ns.get(cls_name, {})
        status = info.get("status", "IDLE")
        attrs = f'ID="{name}" name="{name}" _uid="{uid}" status="{status}"'
        children = node.get("children", [])
        pad = "  " * indent
        if children:
            lines.append(f'{pad}<{ntype} {attrs}>')
            for child in children:
                self._gen_xml_node(lines, child, ns, indent + 1)
            lines.append(f'{pad}</{ntype}>')
        else:
            lines.append(f'{pad}<{ntype} {attrs}/>')

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
                    # Send multipart: [header+uuid, xml] for Groot2 compatibility
                    reply_header = header + tree_uuid + struct.pack('<I', len(xml))
                    sock.send_multipart([reply_header, xml])

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
                    reply_header = header + tree_uuid + struct.pack('<I', len(status_data))
                    sock.send_multipart([reply_header, status_data])

                elif req_type == 'B':  # BLACKBOARD - Groot2 format: {subtree: {key: {repr,type}}}
                    raw_bb = self._bt_status
                    formatted_bb = {}
                    for k, v in raw_bb.items():
                        if k == "node_statuses" or k == "tree_structure" or k == "current_reminder":
                            continue
                        if isinstance(v, bool): bb_type = "bool"; bb_repr = "true" if v else "false"
                        elif isinstance(v, (int, float)): bb_type = "number"; bb_repr = str(v)
                        elif isinstance(v, dict): bb_type = "object"; bb_repr = str(v)[:50]
                        elif isinstance(v, list): bb_type = "array"; bb_repr = str(len(v)) + " items"
                        elif v is None or v == "": bb_type = "string"; bb_repr = "(empty)"
                        else: bb_type = "string"; bb_repr = str(v)[:80]
                        formatted_bb[k] = {"repr": bb_repr, "type": bb_type}
                    wrapper = {"ReminderBT": formatted_bb}
                    bb_data = json.dumps(wrapper, ensure_ascii=False).encode('utf-8')
                    header = struct.pack('<BBL', 2, ord('B'), req_uid)
                    reply_header = header + tree_uuid + struct.pack('<I', len(bb_data))
                    sock.send_multipart([reply_header, bb_data])

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

