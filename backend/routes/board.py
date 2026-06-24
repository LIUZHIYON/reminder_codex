import asyncio
import os, json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import paramiko

router = APIRouter(prefix="/api/board-reminders", tags=["board-reminders"])

BOARD_HOST = "192.168.1.160"
BOARD_USER = "cat"
BOARD_PASS = "temppwd"
BOARD_BASE_DIR = "/home/cat/reminder_system"
BOARD_DB_PATH = BOARD_BASE_DIR + "/data/reminders.db"
BOARD_AUDIO_DIR = BOARD_BASE_DIR + "/audio/"

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "board_reminders.json")

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _ssh_exec(cmd):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        client.close()
        return out, err
    except Exception as e:
        return None, str(e)

def _ssh_exec_py(py_code):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        sftp = client.open_sftp()
        remote_path = "/tmp/_board_q.py"
        with sftp.open(remote_path, "w") as f:
            f.write(py_code)
        sftp.close()
        _, stdout, stderr = client.exec_command("python3 " + remote_path)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        client.exec_command("rm -f " + remote_path)
        client.close()
        return out, err
    except Exception as e:
        return None, str(e)

def _check_online():
    out, err = _ssh_exec("echo online_ok")
    return bool(out and "online_ok" in out)

def _sftp_get(remote_path, local_path):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        sftp = client.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        client.close()
        return True
    except Exception as e:
        return False

def _ssh_update_reminder(command_id, new_status, content="", reminder_time=""):
    """Update board SQLite reminder status via SSH using SFTP temp script.
    Tries command_id first, then falls back to content+reminder_time matching.
    """
    import re as _re
    if not command_id and not content:
        return False
    safe_c = content.replace("'", "\\'").replace('"', '\\"')
    safe_t = reminder_time.replace("'", "\\'").replace('"', '\\"')
    # Build Python script to run on board
    lines = [
        "import sqlite3",
        "conn=sqlite3.connect('" + BOARD_DB_PATH + "')",
        "c=conn.cursor()",
        "try:",
        "    c.execute('ALTER TABLE reminders ADD COLUMN command_id TEXT')",
        "    conn.commit()",
        "except:",
        "    pass",
        "# Try by command_id first",
        "c.execute('UPDATE reminders SET status=? WHERE command_id=?', ('" + new_status + "','" + command_id + "'))",
        "if c.rowcount==0 and '" + safe_c + "':",
        "    c.execute('UPDATE reminders SET status=? WHERE content=? AND reminder_time=?', ('" + new_status + "','" + safe_c + "','" + safe_t + "'))",
        "conn.commit()",
        "conn.close()",
        "print('ok')",
    ]
    py_code = "\n".join(lines)

    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        sftp = client.open_sftp()
        remote_path = "/tmp/_upd_status.py"
        with sftp.open(remote_path, 'w') as f:
            f.write(py_code)
        sftp.close()
        _, stdout, stderr = client.exec_command('python3 ' + remote_path)
        out = stdout.read().decode()
        err = stderr.read().decode()[:500]
        client.exec_command('rm -f ' + remote_path)
        client.close()
        if err:
            print("SSH update stderr:", err)
        return True
    except Exception as e:
        print("SSH update failed:", e)
        return False
def _ssh_delete_reminder(content, reminder_time):
    """Delete reminder from board SQLite via SSH matching content+time."""
    safe_c = content.replace("'", "\\'")
    safe_t = reminder_time.replace("'", "\\'")
    py_code = (
        "import sqlite3\n"
        "conn=sqlite3.connect('" + BOARD_DB_PATH + "')\n"
        "c=conn.cursor()\n"
        "c.execute(\"DELETE FROM reminders WHERE content=? AND reminder_time=?\", ('" + safe_c + "','" + safe_t + "'))\n"
        "affected=c.rowcount\n"
        "if affected==0:\n"
        "    c.execute(\"DELETE FROM reminders WHERE reminder_time=?\", ('" + safe_t + "',))\n"
        "conn.commit()\n"
        "conn.close()\n"
        "print(affected if affected>0 else 0)\n"
    )
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        sftp = client.open_sftp()
        remote_path = "/tmp/_del_reminder.py"
        with sftp.open(remote_path, "w") as f:
            f.write(py_code)
        sftp.close()
        _, stdout, stderr = client.exec_command("python3 " + remote_path)
        out = stdout.read().decode()
        err = stderr.read().decode()[:500]
        client.exec_command("rm -f " + remote_path)
        client.close()
        if err:
            print("SSH delete stderr:", err)
        return out.strip()
    except Exception as e:
        print("SSH delete failed:", e)
        return "0"

class BoardReminderSync(BaseModel):
    command_id: str = ""
    title: str
    content: str = ""
    reminder_time: str = ""
    file_path: str = ""
    received_at: str = ""
    status: str = "received"

@router.post("/sync")
async def sync_board_reminder(data: BoardReminderSync):
    records = _load_cache()
    if data.command_id:
        records = [r for r in records if r.get("command_id") != data.command_id]
    # Determine initial status based on board online
    online = _check_online()
    init_status = "sent" if online else "pending"
    rec = {
        "command_id": data.command_id,
        "title": data.title,
        "content": data.content,
        "reminder_time": data.reminder_time,
        "file_path": data.file_path,
        "received_at": data.received_at or datetime.now().isoformat(),
        "status": init_status,
        "sync_at": datetime.now().isoformat(),
    }
    records.insert(0, rec)
    records = records[:100]
    _save_cache(records)
    if data.title and data.reminder_time:
        try:
            from services.tts import generate_audio_sync
            aid = abs(hash(data.reminder_time + data.title)) % 10000
            audio_path = generate_audio_sync(aid, data.title, data.content)
            if audio_path:
                rec["audio_file"] = audio_path
                _save_cache(records)
        except Exception as _e:
            print("Sync TTS error: " + str(_e))
    return {"success": True, "count": len(records)}

@router.post("/status-update")
async def status_update(data: dict):
    """Update a board reminder status and sync to board SQLite via SSH."""
    command_id = data.get("command_id", "")
    new_status = data.get("status", "")
    if not command_id or not new_status:
        raise HTTPException(400, "command_id and status required")
    content = data.get("content", "")
    reminder_time = data.get("reminder_time", "")
    # Update cache immediately
    records = _load_cache()
    for r in records:
        if r.get("command_id") == command_id:
            r["status"] = new_status
            r["status_updated_at"] = datetime.now().isoformat()
            break
    _save_cache(records)
    # SSH in background - don't block the server
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _ssh_update_reminder, command_id, new_status, content, reminder_time)
    return {"success": True}

@router.post("/delete-record")
async def delete_board_record(data: dict):
    """Delete a reminder from board SQLite by content+reminder_time."""
    content_text = data.get("content", "")
    reminder_time = data.get("reminder_time", "")
    if not content_text or not reminder_time:
        raise HTTPException(400, "content and reminder_time required")
    records = _load_cache()
    records = [r for r in records if r.get("command_id") != data.get("command_id", "")]
    _save_cache(records)
    deleted = _ssh_delete_reminder(content_text, reminder_time)
    return {"success": True, "deleted": deleted}

@router.get("/presence")
async def get_presence():
    pf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "board_presence.json")
    if os.path.exists(pf):
        try:
            return json.load(open(pf, "r", encoding="utf-8"))
        except:
            pass
    return {"present": True, "updated_at": ""}

@router.post("/presence")
async def set_presence(data: dict):
    present = data.get("present", True)
    pf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "board_presence.json")
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    with open(pf, "w", encoding="utf-8") as f:
        json.dump({"present": present, "updated_at": datetime.now().isoformat()}, f)
    return {"success": True, "present": present}

@router.get("/status")
async def board_status():
    online = _check_online()
    info = {"online": online, "host": BOARD_HOST}
    if online:
        q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM reminders'); print(c.fetchone()[0]); conn.close()"
        out, err = _ssh_exec_py(q)
        if out:
            try:
                info["reminder_count"] = int(out.strip())
            except:
                pass
    return info

@router.get("")
async def list_board_reminders():
    loop = asyncio.get_event_loop()
    cache = _load_cache()
    try:
        data = await loop.run_in_executor(None, _list_board_from_ssh)
        if data is not None:
            return data
    except:
        pass
    return cache


def _list_board_from_ssh():
    import json
    q = "import sqlite3,json; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('PRAGMA table_info(reminders)'); cols=[r[1] for r in c.fetchall()]; c.execute('SELECT * FROM reminders ORDER BY id DESC LIMIT 50'); rows=c.fetchall(); print(json.dumps([dict(zip(cols,row)) for row in rows],ensure_ascii=False)); conn.close()"
    out, err = _ssh_exec_py(q)
    if not out:
        return None
    try:
        data = json.loads(out)
        for item in data:
            item["board_host"] = BOARD_HOST
            item["title"] = item.get("content", "")
            item["file_path"] = item.get("audio_file", BOARD_AUDIO_DIR)
        old_cache = _load_cache()
        old_map = {}
        for o in old_cache:
            k = o.get("command_id", "") or str(o.get("id", ""))
            if k:
                old_map[k] = o
        merged_ids = set()
        for item in data:
            k = str(item.get("id", ""))
            if k and k in old_map:
                o = old_map[k]
                if o.get("status") in ("completed", "failed", "executing", "cancelled"):
                    item["status"] = o["status"]
            ck = str(item.get("command_id", ""))
            if ck and ck in old_map:
                o = old_map[ck]
                if o.get("status") in ("completed", "failed", "executing", "cancelled"):
                    item["status"] = o["status"]
            for o in old_cache:
                if o.get("command_id") and (o.get("title") or o.get("content")) == (item.get("content") or item.get("title")) and o.get("reminder_time") == item.get("reminder_time"):
                    item["status"] = o.get("status", item.get("status", "received"))
                    if o.get("command_id"):
                        item["command_id"] = o["command_id"]
                    merged_ids.add(id(o))
                    break
        data_ids = {str(x.get("id", "")) for x in data}
        for o in old_cache:
            if o.get("command_id") and str(o.get("id", "")) not in data_ids and id(o) not in merged_ids:
                data.append(o)
        _save_cache(data)
        return data
    except Exception:
        return None

@router.delete("/{reminder_id}")
async def delete_board_reminder(reminder_id: int):
    # Also mark as cancelled in cache
    records = _load_cache()
    for r in records:
        if str(r.get("id", "")) == str(reminder_id):
            r["status"] = "cancelled"
            _save_cache(records)
            break
    q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('DELETE FROM reminders WHERE id = ?',(" + str(reminder_id) + ",)); conn.commit(); print('OK'); conn.close()"
    out, err = _ssh_exec_py(q)
    if not out or "OK" not in out:
        raise HTTPException(500, detail="Board deletion failed")
    return {"success": True}

@router.post("/{reminder_id}/play")
async def play_board_reminder(reminder_id: int):
    """Play board reminder: generate TTS locally if no audio, or download from board."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_dir = os.path.join(base_dir, "..")
    local_dir = os.path.join(project_dir, "audio")
    os.makedirs(local_dir, exist_ok=True)

    # Try to get content from board
    q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content, audio_file FROM reminders WHERE id = ?',(" + str(reminder_id) + ",)); row=c.fetchone(); print(row[0] if row else ''); print(row[1] if row and row[1] else ''); conn.close()"
    out, err = _ssh_exec_py(q)
    if not out:
        raise HTTPException(404, detail="Reminder not found on board")
    lines = out.strip().split("\n")
    content = lines[0] if lines else ""
    audio_remote = lines[1] if len(lines) > 1 else ""

    # If board has audio, download it
    if audio_remote:
        remote_path = audio_remote
        local_path = os.path.join(local_dir, "board_" + str(reminder_id) + os.path.splitext(remote_path)[1])
        ok = _sftp_get(remote_path, local_path)
        if ok and os.path.exists(local_path):
            from player import player
            player.play(local_path, False)
            return {"success": True, "message": "Playing from board: " + os.path.basename(local_path)}

    # No board audio - generate TTS locally
    if not content:
        raise HTTPException(404, detail="No content to play")
    from services.tts import generate_audio_sync
    audio_path = generate_audio_sync(reminder_id, content)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(500, detail="TTS generation failed")
    from player import player
    player.play(audio_path, False)
    return {"success": True, "message": "Playing TTS: " + os.path.basename(audio_path)}

@router.post("/{reminder_id}/generate-tts")
async def generate_board_tts(reminder_id: int):
    """Generate TTS audio locally for a board reminder."""
    q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content FROM reminders WHERE id = ?',(" + str(reminder_id) + ",)); row=c.fetchone(); print(row[0] if row else ''); conn.close()"
    out, err = _ssh_exec_py(q)
    content = (out or "").strip()
    if not content:
        raise HTTPException(404, detail="Reminder not found on board")
    from services.tts import generate_audio_sync
    audio_path = generate_audio_sync(reminder_id, content)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(500, detail="TTS generation failed")
    return {"success": True, "audio_file": audio_path, "content": content}
