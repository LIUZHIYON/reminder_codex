"""BT Monitor - 浣跨敤 BehaviorTreeMonitor 鍓嶇"""
import zmq, struct, random, json, asyncio, os, sys
from aiohttp import web

HOST = "192.168.1.191"
ZMQ_PORT = 1669
HTTP_PORT = 8003

# Path to Monitor's built frontend
FRONTEND_DIR = r"E:\LuBanCat\BT_ros2\BehaviorTreeMonitor\dist"

class Bridge:
    def __init__(self):
        self.connected = False
        self.tree_xml = ""
        self.statuses = {}
        self.last_error = ""
        self.host = HOST
        self.port = ZMQ_PORT
    
    def _send_zmq(self, msg):
        ctx = zmq.Context()
        s = ctx.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.setsockopt(zmq.RCVTIMEO, 5000)
        s.setsockopt(zmq.SNDTIMEO, 3000)
        s.connect(f"tcp://{self.host}:{self.port}")
        s.send_multipart([msg, b''])
        reply = s.recv_multipart()
        s.close(linger=0)
        ctx.term()
        return reply[0] if reply else b''
    
    async def connect(self):
        try:
            hdr = struct.pack('<BBL', 2, ord('T'), random.randint(0, 0xFFFFFFFF))
            reply = self._send_zmq(hdr)
            if len(reply) >= 26:
                xlen = struct.unpack('<I', reply[22:26])[0]
                self.tree_xml = reply[26:26+xlen].decode('utf-8', errors='replace')
                self.connected = True
                self.last_error = ""
                return True
        except Exception as e:
            self.last_error = str(e)
        self.connected = False
        return False
    
    def get_status(self):
        try:
            hdr = struct.pack('<BBL', 2, ord('S'), random.randint(0, 0xFFFFFFFF))
            reply = self._send_zmq(hdr)
            if len(reply) >= 26:
                dlen = struct.unpack('<I', reply[22:26])[0]
                st = {}
                if dlen > 0:
                    data = reply[26:26+dlen]
                    for i in range(0, len(data), 3):
                        if i+2 < len(data):
                            uid = struct.unpack('<H', data[i:i+2])[0]
                            st[str(uid)] = data[i+2]
                self.statuses = st
                return st
        except:
            pass
        return {}

bridge = Bridge()
connected_ws = set()

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    connected_ws.add(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type", "")

                    if msg_type == "connect":
                        bridge.host = data.get("host", HOST)
                        bridge.port = data.get("port", ZMQ_PORT)
                        ok = await bridge.connect()
                        st = bridge.get_status() if ok else {}
                        await ws.send_json({
                            "type": "connection_status",
                            "connected": ok,
                            "tree_xml": bridge.tree_xml if ok else None,
                            "statuses": st,
                            "error": bridge.last_error if not ok else None
                        })

                    elif msg_type == "disconnect":
                        bridge.connected = False
                        await ws.send_json({"type": "connection_status", "connected": False})

                    elif msg_type == "request_tree":
                        st = bridge.get_status()
                        await ws.send_json({
                            "type": "tree_data",
                            "tree_xml": bridge.tree_xml,
                            "statuses": st
                        })

                    elif msg_type == "request_status":
                        st = bridge.get_status()
                        await ws.send_json({
                            "type": "status_data",
                            "statuses": st
                        })

                    elif msg_type == "request_blackboard":
                        try:
                            hdr = struct.pack("<BBL", 2, ord("B"), random.randint(0, 0xFFFFFFFF))
                            reply = bridge._send_zmq(hdr)
                            bb = {}
                            if len(reply) >= 26:
                                dlen = struct.unpack("<I", reply[22:26])[0]
                                if dlen > 0:
                                    bb = json.loads(reply[26:26+dlen])
                            await ws.send_json({
                                "type": "blackboard_data",
                                "blackboard": bb
                            })
                        except Exception:
                            await ws.send_json({
                                "type": "blackboard_data",
                                "blackboard": {}
                            })

                except Exception as e:
                    pass
    finally:
        connected_ws.discard(ws)
    return ws

app = web.Application()
async def index(request):
    return web.FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

app = web.Application()
app.router.add_get("/", index)
app.router.add_static("/assets", os.path.join(FRONTEND_DIR, "assets"))
app.router.add_static("/favicon.svg", FRONTEND_DIR)
app.router.add_get("/ws", ws_handler)

async def status_push():
    # Periodically push status to all connected clients.
    while True:
        await asyncio.sleep(0.5)
        if bridge.connected and connected_ws:
            st = bridge.get_status()
            data = json.dumps({"type": "status_data", "statuses": st})
            for ws in list(connected_ws):
                try:
                    await ws.send_str(data)
                    # Also push blackboard data periodically
                    try:
                        hdr = struct.pack("<BBL", 2, ord("B"), random.randint(0, 0xFFFFFFFF))
                        reply = bridge._send_zmq(hdr)
                        if len(reply) >= 26:
                            dlen = struct.unpack("<I", reply[22:26])[0]
                            if dlen > 0:
                                bb = json.loads(reply[26:26+dlen])
                                bb_data = json.dumps({"type": "blackboard_data", "blackboard": bb})
                                await ws.send_str(bb_data)
                    except:
                        pass
                except Exception:
                    connected_ws.discard(ws)

async def on_startup(app):
    asyncio.create_task(status_push())

app.on_startup.append(on_startup)

if __name__ == '__main__':
    # Set Windows event loop policy for zmq compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print(f"[BT Monitor] http://localhost:{HTTP_PORT}")
    print(f"[BT Monitor] Frontend: {FRONTEND_DIR}")
    web.run_app(app, host='0.0.0.0', port=HTTP_PORT)

