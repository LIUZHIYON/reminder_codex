import json, time, threading, sqlite3, os, sys, logging

logging.basicConfig(level=logging.INFO, format="[WS] %(asctime)s %(message)s")
log = logging.getLogger(__name__)

SERVER_HTTP = "http://47.118.26.156:8000"
SERVER_WS = "ws://47.118.26.156:8000"
SERIAL = "6976f96f-bc80-56e3-9b27-13d12cdde9d3"
DB_PATH = "/home/cat/reminder_system/data/reminders.db"
AUDIO_DIR = "/home/cat/reminder_system/audio/"

class BoardWSClient:
    def __init__(self):
        self.ws = None
        self.running = False

    def get_ws_token(self):
        try:
            import urllib.request
            url = f"{SERVER_HTTP}/api/v1/aipet/ws/auth/{SERIAL}"
            r = urllib.request.urlopen(url, timeout=10)
            data = json.loads(r.read())
            return data.get("data","")
        except Exception as e:
            log.error(f"Get WS token error: {e}")
            return ""

    def insert_reminder(self, msg):
        """Insert reminder from server_command into SQLite.
        Follows AI-Pet-WebSocket Section 4.1.1 (reminder) format.
        """
        try:
            # command_params.reminder_data is the standard location (Section 4.1.1)
            cp = msg.get("command_params") or msg.get("commandParams") or {}
            rd = cp.get("reminder_data") or msg.get("reminder_data") or {}
            title = rd.get("title","") or rd.get("content","") or msg.get("title","") or msg.get("content","")
            content = rd.get("content","") or title
            rtime = rd.get("reminder_time","") or rd.get("reminderTime","") or msg.get("reminder_time","")
            rsrc = cp.get("reminder_source", "app_chat")  # Section 22.6 adds this field
            if not title or not rtime:
                log.warning(f"Incomplete reminder: {title} / {rtime}")
                return None
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO reminders (content, reminder_time, status) VALUES (?,?,?)",
                      (content, rtime, "pending"))
            conn.commit()
            rid = c.lastrowid
            conn.close()
            log.info(f"Saved reminder #{rid}: {title[:30]} @ {rtime} (source={rsrc})")
            return rid
        except Exception as e:
            log.error(f"Insert error: {e}")
            return None

    def on_message(self, ws, raw):
        try:
            msg = json.loads(raw)
        except:
            return
        t = msg.get("type","")
        log.info(f"WS msg: {t}")
        if t == "auth" and msg.get("success"):
            log.info("AUTH OK - board connected")
        elif t == "heartbeat":
            pass
        elif t == "server_command":
            cmd = msg.get("command","")
            cid = msg.get("command_id","")
            log.info(f"Command: {cmd} id={cid}")
            if cmd == "reminder":
                rid = self.insert_reminder(msg)
                # Section 3.6: command_response format
                resp = {
                    "type": "command_response",
                    "command_id": cid,
                    "command": cmd,
                    "status": "success" if rid else "failed",
                    "result": {"received": bool(rid), "board_id": rid, "played": False, "user_acknowledged": False} if rid else {},
                    "error": None if rid else "Failed to save reminder"
                }
                ws.send(json.dumps(resp))
                if rid:
                    log.info(f"Response sent for reminder #{rid} (Section 3.6)")

    def on_error(self, ws, error):
        log.error(f"WS error: {error}")

    def on_close(self, ws, *args):
        log.info("WS closed")

    def on_open(self, ws):
        log.info("WS opened, authenticating...")
        token = self.get_ws_token()
        if token:
            ws.send(json.dumps({"type":"auth","access_token":token}))

    def run(self):
        import websocket
        self.running = True
        while self.running:
            try:
                url = f"{SERVER_WS}/api/v1/aipet/ws/{SERIAL}"
                self.ws = websocket.WebSocketApp(url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close)
                log.info(f"Connecting to {url}...")
                self.ws.run_forever()
            except Exception as e:
                log.error(f"WS error: {e}")
            if self.running:
                time.sleep(5)

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

if __name__ == "__main__":
    client = BoardWSClient()
    try:
        client.run()
    except KeyboardInterrupt:
        client.stop()
        log.info("Stopped")
