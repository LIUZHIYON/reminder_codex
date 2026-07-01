"""groot2_server_v2.py — ZMQ bridge for BehaviorTreeMonitor (fixed)"""
import struct, json, time, sys, os, random, traceback

try:
    import zmq
except ImportError:
    print("pip3 install pyzmq"); sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_engine import print_tree
from reminder_tree_v2 import build_reminder_tree_v2

# Build v2 tree
blackboard = {
    "blackboard_state": {"pending_count": 0, "is_playing": False},
    "tts_feedback": {"status": None},
    "current_reminder": {},
    "tts_pub": lambda t: None,
    "cmd_pub": lambda d: None,
    "action_pub": lambda d: None,
}
tree = build_reminder_tree_v2(blackboard=blackboard)
print("V2 tree loaded")

# ── Assign UIDs recursively ──
uid_counter = [0]
uid_to_node = {}
node_to_uid = {}

def walk(node):
    uid_counter[0] += 1
    uid = uid_counter[0]
    uid_to_node[uid] = node
    node_to_uid[id(node)] = uid
    node._bt_uid = uid
    # Walk children
    children = getattr(node, '_children', None)
    if children:
        for child in children:
            walk(child)

walk(tree.root)
print(f"Assigned {uid_counter[0]} UIDs")
print_tree(tree.root)

# ── Generate XML ──
STATUS_MAP = {0: "IDLE", 1: "RUNNING", 2: "SUCCESS", 3: "FAILURE", 4: "SKIPPED"}

def node_xml(node):
    cls = type(node).__name__
    name = getattr(node, 'name', cls)
    uid = node_to_uid.get(id(node), 0)
    children = getattr(node, '_children', None)
    if children and len(children) > 0:
        inner = ''.join(node_xml(c) for c in children)
        return f'<{cls} name="{name}" _uid="{uid}">{inner}</{cls}>'
    return f'<{cls} name="{name}" _uid="{uid}" />'

tree_xml = '<?xml version="1.0"?><root BTCPP_format="4"><BehaviorTree ID="reminder_bt_v2">'
tree_xml += node_xml(tree.root)
tree_xml += '</BehaviorTree></root>'
tree_uuid = os.urandom(16)

# ── ZMQ Server ──
ctx = zmq.Context()
sock = ctx.socket(zmq.REP)
sock.bind("tcp://0.0.0.0:1667")
print(f"ZMQ server ready on port 1667")
print(f"Tree UUID: {tree_uuid.hex()}")
print(f"XML length: {len(tree_xml)}")

while True:
    try:
        # Receive request (blocking)
        # Consume all multipart parts
        msg = sock.recv()
        while sock.getsockopt(zmq.RCVMORE):
            sock.recv()
        if len(msg) < 6:
            sock.send(b'\x00' * 22)
            continue

        proto, req_type, req_uid = struct.unpack('<BBL', msg[:6])
        print(f"REQ: type={chr(req_type)} uid={req_uid} len={len(msg)}")

        if req_type == ord('T'):
            # FULLTREE
            reply = struct.pack('<BBL', 2, req_type, req_uid)
            reply += tree_uuid
            xml_bytes = tree_xml.encode('utf-8')
            reply += struct.pack('<I', len(xml_bytes))
            reply += xml_bytes
            sock.send(reply)
            print(f"  -> TREE reply {len(reply)} bytes")

        elif req_type == ord('S'):
            # STATUS - tick once and collect
            try:
                tree.tick_once()
            except:
                pass

            buf = b''
            for uid in sorted(uid_to_node.keys()):
                node = uid_to_node[uid]
                st = getattr(node, 'status', None)
                if st is not None:
                    sv = st.value if hasattr(st, 'value') else int(st)
                else:
                    sv = 0  # IDLE
                buf += struct.pack('<HB', uid, sv)

            reply = struct.pack('<BBL', 2, req_type, req_uid)
            reply += tree_uuid
            reply += struct.pack('<I', len(buf))
            reply += buf
            sock.send(reply)
            print(f"  -> STATUS reply {len(reply)} bytes, {len(buf)//3} nodes")

        else:
            # Unknown type
            reply = struct.pack('<BBL', 2, req_type, req_uid)
            reply += tree_uuid
            reply += struct.pack('<I', 0)
            sock.send(reply)
            print(f"  -> EMPTY reply")

    except zmq.ZMQError as e:
        print(f"ZMQ Error: {e}")
        try:
            sock.close()
        except:
            pass
        time.sleep(1)
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind("tcp://0.0.0.0:1667")
        print("ZMQ socket recreated")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        try:
            sock.send(b'\x00' * 22)
        except:
            pass
