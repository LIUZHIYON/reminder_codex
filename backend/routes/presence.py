import os, json, logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESENCE_FILE = os.path.join(BASE, "board_presence.json")
CACHE_FILE = os.path.join(BASE, "board_reminders.json")

BOARD_HOST = "192.168.1.64"
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

        # Build Python script to execute on board
        py_code = (
            "import sqlite3\n"
            "conn=sqlite3.connect('" + BOARD_DB_PATH + "')\n"
            "c=conn.cursor()\n"
            "try:\n"
            "    c.execute('ALTER TABLE reminders ADD COLUMN command_id TEXT')\n"
            "    conn.commit()\n"
            "    print('col_added')\n"
            "except:\n"
            "    print('col_exists')\n"
            "c.execute('UPDATE reminders SET status=? WHERE command_id=?', ('" + new_status + "','" + command_id + "'))\n"
            "affected=c.rowcount\n"
            "if affected==0:\n"
            "    c.execute('UPDATE reminders SET status=? WHERE id=(SELECT MAX(id) FROM reminders)', ('" + new_status + "',))\n"
            "    print('fallback_updated')\n"
            "conn.commit()\n"
            "conn.close()\n"
            "print('done')\n"
        )

        # Write script to temp file on board via exec, then run it
        import urllib.parse
        _, stdout, stderr = client.exec_command("python3 << 'EOF'\n" + py_code + "\nEOF")
        out = stdout.read().decode()
        err = stderr.read().decode()[:500]
        if err and 'col_exists' not in err:
            log.warning(f"SSH stderr: {err}")
        client.close()
        log.info(f"SSH status: {command_id} -> {new_status}")
    except Exception as e:
        log.warning(f"SSH failed: {e}")

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
        if s not in ("received", "pending", "executing"):
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
                except Exception as ssh_e:
                    log.warning(f"SSH error for {cid}: {ssh_e}")