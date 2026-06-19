import os, json, time
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import paramiko

router = APIRouter(prefix="/api/board-reminders", tags=["board-reminders"])

BOARD_HOST = "192.168.1.40"
BOARD_USER = "cat"
BOARD_PASS = "temppwd"
BOARD_REMINDER_FILE = "/home/cat/reminder_data/reminders.json"
BOARD_AUDIO_DIR = "/home/cat/reminder_data/audio/"

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
        print(f"[Board] SFTP failed: {e}")
        return False

def _sftp_put(remote_path, data_str):
    """Write a string to a remote file via SFTP."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        sftp = client.open_sftp()
        with sftp.open(remote_path, "w") as f:
            f.write(data_str)
        sftp.close()
        client.close()
        return True
    except Exception as e:
        print(f"[Board] SFTP put failed: {e}")
        return False

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
    rec = {
        "command_id": data.command_id,
        "title": data.title,
        "content": data.content,
        "reminder_time": data.reminder_time,
        "file_path": data.file_path,
        "received_at": data.received_at or datetime.now().isoformat(),
        "status": data.status,
        "sync_at": datetime.now().isoformat(),
    }
    records.insert(0, rec)
    records = records[:100]
    _save_cache(records)
    return {"success": True, "count": len(records)}

@router.get("/status")
async def board_status():
    online = _check_online()
    info = {"online": online, "host": BOARD_HOST}
    if online:
        out, err = _ssh_exec("cat " + BOARD_REMINDER_FILE + " 2>/dev/null || echo '[]'")
        count = 0
        if out:
            try:
                count = len(json.loads(out))
            except:
                pass
        info["reminder_count"] = count
    return info

@router.get("")
async def list_board_reminders():
    out, err = _ssh_exec("cat " + BOARD_REMINDER_FILE + " 2>/dev/null || echo '[]'")
    if out:
        try:
            data = json.loads(out)
            for item in data:
                rid = item.get("command_id", "") or str(item.get("id", ""))
                item["file_path"] = BOARD_AUDIO_DIR + "reminder_" + rid + ".mp3"
                item["board_host"] = BOARD_HOST
            _save_cache(data)
            return data
        except:
            pass
    return _load_cache()

@router.delete("/{command_id}")
async def delete_board_reminder(command_id: str):
    out, err = _ssh_exec("cat " + BOARD_REMINDER_FILE + " 2>/dev/null || echo '[]'")
    if not out:
        raise HTTPException(500, detail="Cannot read board reminders")
    try:
        recs = json.loads(out)
    except:
        raise HTTPException(500, detail="Invalid JSON on board")
    before = len(recs)
    recs = [r for r in recs if r.get("command_id", "") != command_id]
    if len(recs) == before:
        raise HTTPException(404, detail="Not found on board")
    ok = _sftp_put(BOARD_REMINDER_FILE, json.dumps(recs, ensure_ascii=False, indent=2))
    if not ok:
        raise HTTPException(500, detail="Failed to write back to board")
    return {"success": True}

@router.post("/{command_id}/play")
async def play_board_reminder(command_id: str):
    out, err = _ssh_exec("ls " + BOARD_AUDIO_DIR + "reminder_" + command_id + ".* 2>/dev/null")
    audio_remote = (out or "").strip().split("\n")[0] if out else ""
    if not audio_remote:
        raise HTTPException(404, detail="Audio file not found on board")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_dir = os.path.join(base_dir, "..")
    local_dir = os.path.join(project_dir, "audio")
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, "board_" + command_id + os.path.splitext(audio_remote)[1])
    ok = _sftp_get(audio_remote, local_path)
    if not ok:
        raise HTTPException(500, detail="Failed to download audio from board")
    from player import player
    player.play(local_path, False)
    return {"success": True, "message": "Playing: " + os.path.basename(local_path)}
