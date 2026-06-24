import os, json, logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESENCE_FILE = os.path.join(BASE, "board_presence.json")
CACHE_FILE = os.path.join(BASE, "board_reminders.json")

BOARD_HOST = "192.168.1.226"
BOARD_USER = "cat"
BOARD_PASS = "temppwd"
BOARD_DB_PATH = "/home/cat/reminder_system/data/reminders.db"

def get_presence():
    if os.path.exists(PRESENCE_FILE):
        try:
            d = json.load(open(PRESENCE_FILE, "r", encoding="utf-8"))
            return d.get("present", True)
        except:
            pass
    return True

def set_presence(present):
    os.makedirs(os.path.dirname(PRESENCE_FILE), exist_ok=True)
    with open(PRESENCE_FILE, "w", encoding="utf-8") as f:
        json.dump({"present": present, "updated_at": datetime.now().isoformat()}, f)

def _ssh_update_status(command_id, new_status):
    """SSH into board to update reminder status in SQLite."""
    if not command_id:
        return
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)

        py_code = (
            "import sqlite3\n"
            "conn=sqlite3.connect('" + BOARD_DB_PATH + "')\n"
            "c=conn.cursor()\n"
            "try:\n"
            "    c.execute('ALTER TABLE reminders ADD COLUMN command_id TEXT')\n"
            "    conn.commit()\n"
            "except:\n"
            "    pass\n"
            "c.execute('UPDATE reminders SET status=? WHERE command_id=?', ('" + new_status + "','" + command_id + "'))\n"
            "if c.rowcount==0:\n"
            "    c.execute('UPDATE reminders SET status=? WHERE id=(SELECT MAX(id) FROM reminders)', ('" + new_status + "',))\n"
            "conn.commit()\n"
            "conn.close()\n"
            "print('ok')\n"
        )

        sftp = client.open_sftp()
        remote_path = "/tmp/_upd_status.py"
        with sftp.open(remote_path, "w") as f:
            f.write(py_code)
        sftp.close()
        _, stdout, stderr = client.exec_command("python3 " + remote_path)
        err = stderr.read().decode()[:500]
        client.exec_command("rm -f " + remote_path)
        client.close()
        if err and 'already exists' not in err and 'col' not in err:
            log.warning(f"SSH stderr: {err}")
        log.info(f"SSH status: {command_id} -> {new_status}")
    except Exception as e:
        log.warning(f"SSH failed: {e}")

def _update_remote_status(command_id, new_status):
    """Tell 8001 server to update the reminder status on the remote server."""
    if not command_id:
        return
    try:
        import urllib.request, json as _json
        body = _json.dumps({"reminder_id": command_id, "status": new_status}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8001/api/update-remote-status",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=3)
        result = _json.loads(resp.read())
        log.info(f"Remote status update: {command_id} -> {new_status}: {result.get('msg','')}")
    except Exception as e:
        # 8001 might not be running, which is ok
        log.debug(f"Remote update failed: {e}")

def process_reminders():
    if not os.path.exists(CACHE_FILE):
        return
    try:
        recs = json.load(open(CACHE_FILE, "r", encoding="utf-8"))
    except:
        return
    now = datetime.now()
    changed_records = []
    present = get_presence()
    for r in recs:
        s = r.get("status", "")
        if s not in ("received", "pending", "sent", "executing"):
            continue
        rt = r.get("reminder_time", "")
        if not rt:
            continue
        try:
            rtd = datetime.fromisoformat(rt.replace("T", " "))
        except:
            continue
        if rtd > now:
            continue
        title = r.get("title", "") or r.get("content", "")
        content = r.get("content", "") or title
        if s == "executing":
            nxt = r.get("next_check", "")
            if nxt:
                try:
                    if datetime.fromisoformat(nxt) > now:
                        continue
                except:
                    pass
            tm = r.get("timeout_minutes", 60)
            if rtd and now - rtd > timedelta(minutes=tm):
                r["status"] = "failed"
                r["timeout_reason"] = "absent_too_long"
                changed_records.append((r.get("command_id",""), "failed"))
                print(f"[Presence] Timeout (total): {title}")
                continue
        if not present:
            dc = r.get("presence_delay_count", 0)
            tm = r.get("timeout_minutes", 60)
            if dc * 10 >= tm:
                r["status"] = "failed"
                r["timeout_reason"] = "absent_too_long"
                changed_records.append((r.get("command_id",""), "failed"))
                print(f"[Presence] Timeout: {title}")
                continue
            r["status"] = "executing"
            r["presence_delay_count"] = dc + 1
            r["next_check"] = (datetime.now() + timedelta(minutes=10)).isoformat()
            changed_records.append((r.get("command_id",""), "executing"))
            print(f"[Presence] Executing: {title} #{dc+1}")
            continue
        aid = abs(hash(title + rt)) % 100000
        try:
            from services.tts import generate_audio_sync as _gen
            ap = _gen(aid, title, content)
            if ap:
                from player import player as _pl
                _pl.play(ap, True)
                r["status"] = "completed"
                r["audio_file"] = ap
                changed_records.append((r.get("command_id",""), "completed"))
                print(f"[Presence] Completed: {title}")
        except Exception as e:
            print(f"[Presence] TTS error: {e}")
    if changed_records:
        json.dump(recs, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        for cid, new_st in changed_records:
            if cid:
                try:
                    _ssh_update_status(cid, new_st)
                    _update_remote_status(cid, new_st)
                except Exception as e:
                    log.warning(f"Status sync error for {cid}: {e}")