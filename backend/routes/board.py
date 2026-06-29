import asyncio
import os, json
import threading
import paramiko
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
router = APIRouter(prefix="/api/board-reminders", tags=["board-reminders"])
BOARD_HOST = "192.168.1.191"
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
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
        from services.tts import generate_audio_sync
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
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
_board_speak_lock = threading.Lock()
def _board_speak(text):
    """Speak on board via voice_bridge /voice/speak Action.
    Flow: SSH -> setup_audio.sh -> set_volume 90 -> ros2 action /voice/speak
    """
    text = text.strip()
    if not text:
        return False
    with _board_speak_lock:
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)

            safe = text.replace('"', '\\"')
            cmd = (
                "source /opt/ros/humble/setup.bash; "
                "source /home/cat/ros2_ws/install/setup.bash; "
                "bash /home/cat/setup_audio.sh 2>/dev/null; "
                'timeout 3 ros2 service call /audio/set_volume robot_audio_node/srv/SetVolume "{volume: 90}" 2>&1 > /dev/null; '
                'ros2 action send_goal -f /voice/speak robot_voice_bridge/action/Speak "{text: \\"' + safe + '\\", audio_path: \\"\\"}" -t 30 2>&1; '
                "bash /home/cat/setup_audio.sh 2>/dev/null"
            )
            transport = cli.get_transport()
            if transport:
                transport.set_keepalive(30)
            _, stdout, stderr = cli.exec_command(cmd, timeout=40)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()[:200]
            cli.close()

            if "SUCCEEDED" in out and "success: true" in out:
                print("[BoardSpeak] OK: " + text[:30] + "...")
                return True
            else:
                print("[BoardSpeak] Failed: " + text[:30] + "...")
                if err:
                    print("  stderr: " + err[:100])
                return False
        except Exception as e:
            print("[BoardSpeak] Error: " + str(e))
            return False

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
        "repeat_type": data.repeat_type,
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
    updated = False
    for r in records:
        if r.get("command_id") == command_id:
            r["status"] = new_status
            r["status_updated_at"] = datetime.now().isoformat()
            updated = True
            break
    if reminder_time:
        for r in records:
            if r.get("reminder_time") == reminder_time and r.get("status") != new_status:
                r["status"] = new_status
                r["status_updated_at"] = datetime.now().isoformat()
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
    # Kill any playing audio
    try:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=3)
        cli.exec_command("pactl set-sink-mute 0 1 2>/dev/null; pkill -f paplay 2>/dev/null; pkill -f ffplay 2>/dev/null")
        cli.close()
    except:
        pass
    deleted = _ssh_delete_reminder(content_text, reminder_time)
    return {"success": True, "deleted": deleted}
@router.post("/stop")
async def stop_board_playback():
    """Stop all audio playback on the board."""
    import paramiko
    try:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=2)
        cli.exec_command("pactl set-sink-mute 0 1 2>/dev/null; pkill -f paplay 2>/dev/null; pkill -f ffplay 2>/dev/null; pkill -f 'ros2 action send_goal' 2>/dev/null; pkill -f espeak-ng 2>/dev/null")
        cli.close()
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
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
    """List board reminders from local cache."""
    try:
        data = _load_cache()
        if data:
            for item in data:
                item.setdefault("board_host", BOARD_HOST)
                item.setdefault("title", item.get("content", ""))
            return data
    except:
        pass
    return []
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
    """Play board reminder: try board TTS, fallback to local playback."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_dir = os.path.join(base_dir, "..")
    local_dir = os.path.join(project_dir, "audio")
    os.makedirs(local_dir, exist_ok=True)

    content_to_play = ""
    try:
        _cf = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "board_reminders.json")
        if os.path.exists(_cf):
            _cache = json.load(open(_cf, "r", encoding="utf-8"))
            _sid = str(reminder_id)
            for _cr in _cache:
                if str(_cr.get("command_id","") or "") == _sid or str(_cr.get("id","") or "") == _sid:
                    content_to_play = _cr.get("content","") or _cr.get("title","")
                    break
    except Exception as _ce:
        print(f"[Play] Cache lookup error: {_ce}")
    if not content_to_play:
        raise HTTPException(404, detail="Reminder not found on board")
    # Try board TTS first
    ok = _board_speak(content_to_play)
    if ok:
        return {"success": True, "message": "Board TTS: " + content_to_play[:30]}
    # Fallback: generate TTS locally and play on PC
    print(f"[Play] Board TTS failed, using local fallback for: {content_to_play[:30]}...")
    try:
        from services.tts import generate_audio_sync
        aid = abs(hash(content_to_play)) % 10000
        audio_path = generate_audio_sync(aid, content_to_play, "")
        if audio_path and os.path.exists(audio_path):
            from player import player
            player.play(audio_path, False)
            return {"success": True, "message": "Local TTS: " + content_to_play[:30]}
    except Exception as _fe:
        print(f"[Play] Local fallback error: {_fe}")
    return {"success": False, "message": "Playback failed: " + content_to_play[:20]}


