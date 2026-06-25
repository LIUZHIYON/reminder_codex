import asyncio
import os, json
import threading
import paramiko
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/board-reminders", tags=["board-reminders"])

BOARD_HOST = "192.168.1.187"
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
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
        client.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
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
    """Generate TTS on board via doubao TTS (ROS2 Action /voice/speak)."""
    text = text.strip()
    if not text:
        raise ValueError("Empty text")
    
    # Escape double quotes for shell inside YAML goal
    safe = text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "'\\''")
    
    # Build ros2 action command - use shell single-quote for YAML
    cmd = (
        "source /opt/ros/humble/setup.bash && "
        "source /home/cat/ros2_ws/install/setup.bash && "
        "ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
        "'{text: \"" + safe + "\"}' "
        "--timeout 30 2>&1"
    )
    
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=10)
        _, stdout, stderr = cli.exec_command(cmd)
        import select
        out = b''
        while True:
            r, _, _ = select.select([stdout.channel], [], [], 35)
            if r:
                chunk = stdout.channel.recv(8192)
                if not chunk: break
                out += chunk
            else:
                break
        output = out.decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')[:300]
        cli.close()
        
        if 'SUCCEEDED' in output or 'success' in output.lower():
            print(f"[BoardSpeak] Doubao TTS OK: {text[:30]}...")
        else:
            print(f"[BoardSpeak] TTS output: {(output+err)[:200]}")
            raise RuntimeError(f"Doubao TTS failed: {(output+err)[:200]}")
    except Exception as e:
        print(f"[BoardSpeak] Error: {e}")
        raise

class BoardReminderSync(BaseModel):
    command_id: str = ""
    title: str
    content: str = ""
    reminder_time: str = ""
    file_path: str = ""
    received_at: str = ""
    status: str = "received"
    repeat_type: str = ""

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
        cli.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=5)
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
    loop = asyncio.get_event_loop()
    # Quick TCP check (port 22, 2s timeout) - dont return cache if board offline
    online = await loop.run_in_executor(None, _quick_online_check)
    if not online:
        return []
    try:
        data = await loop.run_in_executor(None, _list_board_from_ssh)
        if data is not None:
            # Also try to add missing reminders from management server
            try:
                import urllib.request as _ur2
                _r2 = _ur2.urlopen("http://127.0.0.1:8001/api/remote-reminders", timeout=5)
                _rows2 = json.loads(_r2.read()).get("rows", [])
                _board_set2 = set()
                for _item in data:
                    _rt2 = _item.get("reminder_time","").replace("T", " ")
                    _k2 = ((_item.get("content","") or _item.get("title","")), _rt2)
                    _board_set2.add(_k2)
                for _row in _rows2:
                    if _row.get("status") in ("pending", "sent", "executing", "received", "failed", "completed"):
                        _rt2 = (_row.get("reminderTime","") or _row.get("reminder_time","")).replace("T", " ")
                        _stat2 = _row.get("status","")
                        _ct2 = _row.get("content","") or _row.get("title","")
                        _rk2 = (_ct2, _rt2)
                        if _rk2 not in _board_set2:
                            data.append({
                                "id": _row.get("id",""),
                                "command_id": str(_row.get("id","")),
                                "title": _row.get("title","") or _ct2,
                                "content": _ct2,
                                "reminder_time": _rt2,
                                "status": _stat2,
                                "repeat_type": _row.get("repeatType","") or _row.get("repeat_type",""),
                                "board_host": BOARD_HOST,
                            })
                        elif _stat2 in ("completed","failed","cancelled"):
                            for _existing in data:
                                _ert = str(_existing.get("reminder_time","")).replace("T", " ")
                                _ek = ((_existing.get("content","") or _existing.get("title","")), _ert)
                                if _ek == _rk2 and _existing.get("status") not in ("completed","failed","cancelled"):
                                    _existing["status"] = _stat2
                                    break
            except Exception as e:
                print("Management server fallback error:", e)
            # Direct remote API fallback (belts-and-suspenders)
            try:
                import urllib.request as _ur3
                _login3 = _ur3.urlopen("http://47.118.26.156:8000/api/v1/aipet/app/auth/13900139000/888888", timeout=5)
                _tk3 = json.loads(_login3.read()).get("data","")
                if _tk3:
                    _remote_req3 = _ur3.Request("http://47.118.26.156:8000/api/v1/aipet/app/reminders/list/3/1/50",
                        headers={"Authorization": "Bearer " + _tk3})
                    _remote_resp3 = _ur3.urlopen(_remote_req3, timeout=5)
                    _remote_rows3 = json.loads(_remote_resp3.read()).get("rows", [])
                    _board_set3 = set()
                    for _item in data:
                        _rt3 = _item.get("reminder_time","").replace("T", " ")
                        _k3 = ((_item.get("content","") or _item.get("title","")), _rt3)
                        _board_set3.add(_k3)
                    for _row in _remote_rows3:
                        if _row.get("status") in ("pending", "sent", "executing", "received", "failed", "completed"):
                            _rt3 = (_row.get("reminderTime","") or _row.get("reminder_time","")).replace("T", " ")
                            _stat3 = _row.get("status","")
                            _ct3 = _row.get("content","") or _row.get("title","")
                            _rk3 = (_ct3, _rt3)
                            if _rk3 not in _board_set3:
                                data.append({
                                    "id": _row.get("id",""),
                                    "command_id": str(_row.get("id","")),
                                    "title": _row.get("title","") or _ct3,
                                    "content": _ct3,
                                    "reminder_time": _rt3,
                                    "status": _stat3,
                                    "repeat_type": _row.get("repeatType","") or _row.get("repeat_type",""),
                                    "board_host": BOARD_HOST,
                                })
                            elif _stat3 in ("completed","failed","cancelled"):
                                for _existing in data:
                                    _ert3 = str(_existing.get("reminder_time","")).replace("T", " ")
                                    _ek3 = ((_existing.get("content","") or _existing.get("title","")), _ert3)
                                    if _ek3 == _rk3 and _existing.get("status") not in ("completed","failed","cancelled"):
                                        _existing["status"] = _stat3
                                        break
            except Exception as e3:
                print("Direct API fallback error:", e3)
                print("Management server fallback error:", e)
            # Dedup by content+reminder_time
            seen = set()
            deduped = []
            for item in data:
                _rt = str(item.get("reminder_time","")).replace("T", " ")
                _rk = ((item.get("content","") or item.get("title","")), _rt)
                _rk_str = str(_rk)
                if _rk_str not in seen:
                    seen.add(_rk_str)
                    deduped.append(item)
            return deduped
    except:
        pass
    return []

def _quick_online_check():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((BOARD_HOST, 22))
        s.close()
        return result == 0
    except:
        return False


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
                    if "repeat_type" in o:
                        item["repeat_type"] = o["repeat_type"]
            ck = str(item.get("command_id", ""))
            if ck and ck in old_map:
                o = old_map[ck]
                if o.get("status") in ("completed", "failed", "executing", "cancelled"):
                    item["status"] = o["status"]
                    if "repeat_type" in o:
                        item["repeat_type"] = o["repeat_type"]
                    if "repeat_type" in o:
                        item["repeat_type"] = o["repeat_type"]
            for o in old_cache:
                matched = False
                if o.get("reminder_time") and item.get("reminder_time") and o.get("reminder_time") == item.get("reminder_time"):
                    if o.get("command_id") and (o.get("title") or o.get("content")) == (item.get("content") or item.get("title")):
                        matched = True
                    elif o.get("status") in ("completed", "failed", "executing", "cancelled", "sent"):
                        matched = True
                if matched:
                    item["status"] = o.get("status", item.get("status", "received"))
                    if "repeat_type" in o:
                        item["repeat_type"] = o["repeat_type"]
                    if o.get("command_id"):
                        item["command_id"] = o["command_id"]
                    merged_ids.add(id(o))
                    break
        data_ids = {str(x.get("id", "")) for x in data}
        for o in old_cache:
            if o.get("command_id") and str(o.get("id", "")) not in data_ids and id(o) not in merged_ids:
                data.append(o)
        # Fallback: query remote API for missing repeat_type + sync pending to board
        try:
            import urllib.request as _ur
            _login = _ur.urlopen("http://47.118.26.156:8000/api/v1/aipet/app/auth/13900139000/888888", timeout=5)
            _tk = json.loads(_login.read()).get("data","")
            if _tk:
                _remote_req = _ur.Request("http://47.118.26.156:8000/api/v1/aipet/app/reminders/list/3/1/50",
                    headers={"Authorization": "Bearer " + _tk})
                _remote_resp = _ur.urlopen(_remote_req, timeout=5)
                _remote_rows = json.loads(_remote_resp.read()).get("rows", [])
                _rmap = {}
                for _row in _remote_rows:
                    _rid = str(_row.get("id", ""))
                    if _rid:
                        _rmap[_rid] = _row.get("repeatType", "") or _row.get("repeat_type", "")
                for _item in data:
                    _cid = str(_item.get("command_id", ""))
                    if _cid and _cid in _rmap and not _item.get("repeat_type"):
                        _item["repeat_type"] = _rmap[_cid]
                # Sync pending reminders from remote server to board
                _board_set = set()
                for _item in data:
                    _rt = _item.get("reminder_time","").replace("T", " ")
                    _k = ((_item.get("content","") or _item.get("title","")), _rt)
                    _board_set.add(_k)
                for _row in _remote_rows:
                    if _row.get("status") in ("pending", "sent", "executing", "received", "failed", "completed"):
                        _rt = _row.get("reminderTime","") or _row.get("reminder_time","")
                        _ct = _row.get("content","") or _row.get("title","")
                        _rk = (_ct, _rt.replace("T", " "))
                        if _rk not in _board_set:
                            # Push to board Flask API
                            try:
                                _push_b = json.dumps({"content":_ct,"reminder_time":_rt}).encode()
                                _push_r = _ur.Request("http://192.168.1.187:5000/api/reminders/create",
                                    data=_push_b, headers={"Content-Type":"application/json"}, method="POST")
                                _ur.urlopen(_push_r, timeout=5)
                            except:
                                pass
                        # Add pending reminder to response data directly
                        data.append({
                            "id": _row.get("id",""),
                            "command_id": str(_row.get("id","")),
                            "title": _row.get("title","") or _ct,
                            "content": _ct,
                            "reminder_time": _rt.replace("T", " ") if isinstance(_rt, str) else _rt,
                            "status": _row.get("status",""),
                            "repeat_type": _row.get("repeatType","") or _row.get("repeat_type",""),
                            "board_host": BOARD_HOST,
                        })
                        # Update remote status to sent
                        try:
                            _put_b = json.dumps({"status":"sent"}).encode()
                            _put_r = _ur.Request("http://47.118.26.156:8000/api/v1/aipet/app/reminders/"+str(_row.get("id","")),
                                data=_put_b, headers={"Authorization":"Bearer "+_tk,"Content-Type":"application/json"}, method="PUT")
                            _ur.urlopen(_put_r, timeout=5)
                        except:
                            pass
        except:
            pass
        # Dedup before saving cache to prevent accumulation
        seen = set()
        deduped = []
        for item in data:
            _rt = str(item.get("reminder_time","")).replace("T", " ")
            _rk = ((item.get("content","") or item.get("title","")), _rt)
            _rk_str = str(_rk)
            if _rk_str not in seen:
                seen.add(_rk_str)
                deduped.append(item)
        data = deduped
        _save_cache(data)
        return data
    except Exception as e:
        print("_list_board_from_ssh error:", e)
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

    # Try to get content from board (search by id or command_id)
    q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content, audio_file FROM reminders WHERE id = ?',(" + str(reminder_id) + ",)); row=c.fetchone(); print(row[0] if row else ''); print(row[1] if row and row[1] else ''); conn.close()"
    out, err = _ssh_exec_py(q)
    if not out or not out.strip():
        # Try by command_id (string) instead
        q2 = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content, audio_file FROM reminders WHERE command_id = ?',('" + str(reminder_id) + "',)); row=c.fetchone(); print(row[0] if row else ''); print(row[1] if row and row[1] else ''); conn.close()"
        out, err = _ssh_exec_py(q2)
    if not out or not out.strip():
        # Try from cache (board_reminders.json)
        try:
            _cf = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "board_reminders.json")
            if os.path.exists(_cf):
                _cache = json.load(open(_cf, "r", encoding="utf-8"))
                _sid = str(reminder_id)
                for _cr in _cache:
                    if str(_cr.get("command_id","")) == _sid or str(_cr.get("id","")) == _sid:
                        _ct = _cr.get("content","") or _cr.get("title","")
                        if _ct:
                            _board_speak(_ct)
                            return {"success": True, "message": "Board TTS: " + _ct[:30]}
        except HTTPException:
            raise  # Let HTTPException through (from _board_speak)
        except Exception as _cache_e:
            print(f"[CacheFallback] Error: {_cache_e}")
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

    # Play through board TTS
    if not content:
        raise HTTPException(404, detail="No content to play")
    try:
        _board_speak(content)
        return {"success": True, "message": "Board TTS: " + content[:30]}
    except Exception as e_play:
        raise HTTPException(500, detail="Board TTS failed: " + str(e_play))

@router.post("/{reminder_id}/generate-tts")
async def generate_board_tts(reminder_id: int):
    """Generate TTS audio locally for a board reminder."""
    q = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content FROM reminders WHERE id = ?',(" + str(reminder_id) + ",)); row=c.fetchone(); print(row[0] if row else ''); conn.close()"
    out, err = _ssh_exec_py(q)
    if not out or not out.strip():
        # Try by command_id
        q2 = "import sqlite3; conn=sqlite3.connect('" + BOARD_DB_PATH + "'); c=conn.cursor(); c.execute('SELECT content FROM reminders WHERE command_id = ?',('" + str(reminder_id) + "',)); row=c.fetchone(); print(row[0] if row else ''); conn.close()"
        out, err = _ssh_exec_py(q2)
    content = (out or "").strip()
    if not content:
        raise HTTPException(404, detail="Reminder not found on board")
    try:
        _board_speak(content)
        return {"success": True, "message": "Board TTS sent", "content": content}
    except Exception as e_tts:
        raise HTTPException(500, detail="Board TTS failed: " + str(e_tts))
