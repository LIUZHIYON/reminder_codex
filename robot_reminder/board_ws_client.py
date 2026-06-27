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
        self._ensure_columns()

    def _ensure_columns(self):
        """Add command_id and reported columns if not exist."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            for col in ["command_id TEXT", "reported INTEGER DEFAULT 0"]:
                try:
                    c.execute("ALTER TABLE reminders ADD COLUMN " + col)
                    log.info("Added column: " + col)
                except:
                    pass
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Ensure columns error: {e}")

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

    def insert_reminder(self, msg_or_rid, reminder_data=None):
        """Insert reminder into SQLite.
        Supports both old server_command format and new reminder_delivery format.
        """
        try:
            title = ""
            content = ""
            rtime = ""
            cid = ""
            
            if reminder_data is not None:
                # New format: reminder_delivery
                title = reminder_data.get("title","") or reminder_data.get("content","")
                content = reminder_data.get("content","") or title
                rtime = reminder_data.get("reminder_time","") or reminder_data.get("reminderTime","")
                cid = msg_or_rid  # this is the reminder_id
            else:
                # Old format: server_command {command:"reminder"}
                msg = msg_or_rid
                cp = msg.get("command_params") or msg.get("commandParams") or {}
                rd = cp.get("reminder_data") or msg.get("reminder_data") or {}
                title = rd.get("title","") or rd.get("content","") or msg.get("title","") or msg.get("content","")
                content = rd.get("content","") or title
                rtime = rd.get("reminder_time","") or rd.get("reminderTime","") or msg.get("reminder_time","")
                cid = msg.get("command_id","")
            
            rsrc = "app_chat"
            if not title or not rtime:
                log.warning(f"Incomplete reminder: {title} / {rtime}")
                return None
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO reminders (content, reminder_time, status, command_id) VALUES (?,?,?,?)",
                      (content, rtime, "pending", cid))
            conn.commit()
            rid = c.lastrowid
            conn.close()
            log.info(f"Saved reminder #{rid}: {title[:30]} @ {rtime} (cid={cid})")
            return rid
        except Exception as e:
            log.error(f"Insert error: {e}")
            return None

    def _handle_reminder_delivery(self, msg):
        """Handle new-format reminder_delivery message (Section 4.2)."""
        rid = msg.get("reminder_id", "")
        rd = msg.get("reminder_data", {})
        title = rd.get("title", "") or rd.get("content", "")
        content = rd.get("content", "") or title
        rtime = rd.get("reminder_time", "") or rd.get("reminderTime", "")
        log.info(f"reminder_delivery: {title[:30]} @ {rtime} (rid={rid})")
        
        board_id = self.insert_reminder(rid, rd)
        
        # New format: reminder_response
        resp = {
            "type": "reminder_response",
            "reminder_id": rid,
            "status": "executing" if board_id else "failed",
            "result": {
                "received": bool(board_id),
                "board_id": board_id,
                "status": "executing"
            } if board_id else {},
            "error": None if board_id else "Failed to save reminder"
        }
        if self.ws:
            self.ws.send(json.dumps(resp))
            if board_id:
                log.info(f"reminder_response sent for #{board_id} status=executing")

    def _poll_status_changes(self):
        """Poll reminders that have status changes and report to server."""
        while self.running:
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "SELECT id, command_id, content, status, reminder_time "
                    "FROM reminders "
                    "WHERE command_id IS NOT NULL AND command_id != '' "
                    "AND status IN ('completed','failed','cancelled') "
                    "AND (reported IS NULL OR reported = 0) "
                    "LIMIT 10"
                )
                rows = c.fetchall()
                for row in rows:
                    board_rid, cid_old, content, status, rtime = row
                    if not cid_old:
                        continue
                    # Determine if this is a new-format (reminder_response) or old-format (command_response)
                    # Use reminder_id (cid_old) for the response
                    resp = {
                        "type": "reminder_response",
                        "reminder_id": cid_old,
                        "status": status,
                        "result": {
                            "board_id": board_rid,
                            "content": content,
                            "reminder_time": rtime,
                            "status": status
                        }
                    }
                    if self.ws:
                        self.ws.send(json.dumps(resp))
                        log.info(f"Reported status {status} for rid={cid_old}")
                    # Mark as reported
                    c.execute("UPDATE reminders SET reported=1 WHERE id=?", (board_rid,))
                conn.commit()
                conn.close()
            except Exception as e:
                log.error(f"Poll error: {e}")
            for _ in range(20):
                if not self.running:
                    break
                time.sleep(0.5)

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
        elif t == "reminder_delivery":
            # NEW PROTOCOL Section 4.2: reminder_delivery
            self._handle_reminder_delivery(msg)
        elif t == "server_command":
            # OLD PROTOCOL backward compat: server_command {command:"reminder"}
            cmd = msg.get("command","")
            cid = msg.get("command_id","")
            log.info(f"Legacy command: {cmd} id={cid}")
            if cmd == "reminder":
                board_id = self.insert_reminder(msg, None)
                # Old format: command_response
                resp = {
                    "type": "command_response",
                    "command_id": cid,
                    "command": cmd,
                    "status": "executing" if board_id else "failed",
                    "result": {"received": bool(board_id), "board_id": board_id, "status": "executing"} if board_id else {},
                    "error": None if board_id else "Failed to save reminder"
                }
                ws.send(json.dumps(resp))
                if board_id:
                    log.info(f"Legacy response sent for #{board_id} status=executing")

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
        # Start polling thread
        poll_thread = threading.Thread(target=self._poll_status_changes, daemon=True)
        poll_thread.start()
        log.info("Status poller started")
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