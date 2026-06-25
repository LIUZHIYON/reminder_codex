import time
import json, time, threading, os, sys
import requests as _rq
_rq_orig_get = _rq.get; _rq_orig_post = _rq.post
def _rq_no_proxy_get(u, **k): k["proxies"] = {"http":None,"https":None}; return _rq_orig_get(u, **k)
def _rq_no_proxy_post(u, **k): k["proxies"] = {"http":None,"https":None}; return _rq_orig_post(u, **k)
_rq.get = _rq_no_proxy_get; _rq.post = _rq_no_proxy_post
rq = _rq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, websocket

API = "http://47.118.26.156:8000/api/v1"
SERIAL = "6976f96f-bc80-56e3-9b27-13d12cdde9d3"
PORT = 8001

_utoken = [""]; _last_refresh = [0]; _reminders = []

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}")

def refresh(force=False):
    """Get auth token. Always tries to login first. Falls back to cached token on failure."""
    now = time.time()
    # Always try fresh login first
    if force or now - _last_refresh[0] > 30:
        for attempt in range(2):
            try:
                r = rq.get(f"{API}/aipet/app/auth/13900139000/888888", timeout=10)
                d = r.json()
                token = d.get("data","")
                if d.get("success") and token:
                    _utoken[0] = token
                    _last_refresh[0] = time.time()
                    return True
            except Exception as e:
                log(f"Auth error (attempt {attempt+1}): {e}")
            if attempt == 0:
                time.sleep(1)
    # Fallback: use cached token if available
    if _utoken[0]:
        return True
    _utoken[0] = ""
    return False


_cached_pid = [None]
def get_pid():
    if _cached_pid[0] is not None:
        return _cached_pid[0]
    refresh()
    if not _utoken[0]: return None
    try:
        r = rq.get(f"{API}/aipet/app/myaipets", headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        pets = r.json().get("data",[])
        pid = pets[0].get("id") if pets else None
        if pid:
            _cached_pid[0] = pid
        return pid
    except: return None

def self_save_reminders():
    try:
        fp = os.path.join(os.path.dirname(__file__),"reminders.json")
        with open(fp,"w",encoding="utf-8") as f: json.dump(_reminders[:50],f,ensure_ascii=False)
    except: pass

def _push_to_board(title, rtime):
    try:
        import http.client
        _body = json.dumps({"content":title,"reminder_time":rtime},ensure_ascii=False).encode("utf-8")
        _conn = http.client.HTTPConnection("192.168.1.187",5000,timeout=3)
        _conn.request("POST","/api/reminders/create",_body,{"Content-Type":"application/json"})
        _conn.getresponse().read(); _conn.close()
    except: pass

def _sync_to_8000(cmd_id, title, rtime, repeat_type=""):
    try:
        rq.post("http://127.0.0.1:8000/api/board-reminders/sync",
            json={"command_id":cmd_id,"title":title,"reminder_time":rtime,"content":title,"repeat_type":repeat_type},timeout=2)
    except: pass

    while True:
        try:
            r = rq.get(f"{API}/aipet/ws/auth/{SERIAL}", timeout=10)
            tk = r.json().get("data","")
            if not tk: time.sleep(5); continue
            url = f"ws://47.118.26.156:8000/api/v1/aipet/ws/{SERIAL}"
            _ws[0] = websocket.WebSocketApp(url,
                on_open=lambda s: s.send(json.dumps({"type":"auth","access_token":tk})),
                on_message=lambda s,m: on_msg(json.loads(m)),
                on_error=lambda s,e: log(f"WS err: {e}"),
                on_close=lambda *a: log("WS closed"))
            log("WS connecting...")
            _ws[0].run_forever()
        except Exception as e: log(f"WS error: {e}")
        time.sleep(5)
def on_msg(msg):
    t = msg.get("type","")
    log(f"WS {t}: {json.dumps(msg, ensure_ascii=False)[:200]}")
    if t == "auth" and msg.get("success"):
        log("AUTH OK!")
    elif t == "server_command":
        cmd = msg.get("command",""); cid = msg.get("command_id","")
        if cmd == "reminder":
            # Legacy format - extract from old command_params structure
            rd = msg.get("command_params",{}).get("reminder_data",{})
            title = rd.get("title","") or msg.get("content","")
            rtext = rd.get("content","") or title
            rtime = rd.get("reminder_time","") or rd.get("reminderTime","")
            rtype = rd.get("repeatType","") or rd.get("repeat_type","")
        if not rtype and rid:
            try:
                r2 = rq.get(f"{API}/aipet/app/reminders/{rid}", headers={"Authorization": f"Bearer {_utoken[0]}"}, timeout=3)
                d2 = r2.json()
                rtype = d2.get("data",{}).get("repeatType","") or d2.get("data",{}).get("repeat_type","")
            except:
                pass
            log(f"LEGACY REMINDER: {title}")
            rec = {"command_id":cid,"title":title,"content":rtext,"reminder_time":rtime,
                   "status":"received","received_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
            _reminders.insert(0, rec)
            self_save_reminders()
            _push_to_board(title, rtime)
            _sync_to_8000(cid, title, rtime, rtype)
            if _ws[0]:
                _ws[0].send(json.dumps({"type":"command_response","command_id":cid,
                    "command":cmd,"status":"success","result":{"received":True}}))
    elif t == "reminder_delivery":
        # NEW PROTOCOL Section 4.2: reminder_delivery
        rid = msg.get("reminder_id","")
        rd = msg.get("reminder_data",{})
        title = rd.get("title","") or rd.get("content","")
        rtext = rd.get("content","") or title
        rtime = rd.get("reminder_time","") or rd.get("reminderTime","")
        log(f"REMINDER_DELIVERY: {title}")
        rec = {"command_id":rid,"title":title,"content":rtext,"reminder_time":rtime,
               "status":"received","received_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
        _reminders.insert(0, rec)
        self_save_reminders()
        _push_to_board(title, rtime)
        _sync_to_8000(rid, title, rtime, rtype)
        if _ws[0]:
            _ws[0].send(json.dumps({"type":"reminder_response","reminder_id":rid,
                "status":"received","result":{"received":True}}))

app = FastAPI(title="RM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    refresh()

@app.get("/api/status")
def st():
    return JSONResponse({"online":bool(_utoken[0]),"pet_id":get_pid(),"reminders":len(_reminders)})

@app.get("/api/reminders")
def reminders():
    return JSONResponse(_reminders)

@app.post("/api/send-reminder")
def send(data: dict):
    title = data.get("title",""); rtime = data.get("reminder_time",""); content = data.get("content","") or title
    repeat_type = data.get("repeat_type","none")
    if not title or not rtime: raise HTTPException(400,"title+time required")
    if not refresh(): raise HTTPException(500,"Login failed")
    pid = get_pid()
    if not pid: raise HTTPException(500,"No device")
    
    # Step 1: Create reminder (Section 22.3)
    create_payload = {"title":title,"content":content,"reminderTime":rtime,"repeatType":repeat_type}
    r = rq.post(f"{API}/aipet/app/reminders/{pid}", headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                json=create_payload, timeout=10)
    result = r.json()
    if not result.get("success"):
        # Retry with fresh token if 401
        if refresh(force=True):
            log("Retrying with fresh token...")
            r = rq.post(f"{API}/aipet/app/reminders/{pid}", headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                        json=create_payload, timeout=10)
            result = r.json()
            if not result.get("success"):
                raise HTTPException(500, result.get("msg","Failed"))
        else:
            raise HTTPException(500, "Login failed even after retry")
    if not result.get("success"): raise HTTPException(500, result.get("msg","Failed"))
    reminder_id = result.get("data",{}).get("id")
    if not reminder_id: raise HTTPException(500,"No reminder_id in response")
    
    # Step 2 is removed: Section 22.6 is deprecated.
    # In new protocol, creation (Step 1) auto-sends to device.
    log(f"Created reminder #{reminder_id} (auto-send via new protocol)")
    

    
    # Sync to local cache with command_id = remote reminder_id
    try:
        rq.post("http://127.0.0.1:8000/api/board-reminders/sync",
            json={"command_id":str(reminder_id),"title":title,"reminder_time":rtime,"content":title},timeout=2)
    except: pass
    # Set remote server status based on board reachability
    # If board is reachable (direct POST succeeded) -> sent, otherwise keep pending
    # Check board online via socket (avoids duplicate POST to board Flask)
    board_online_via_post = False
    try:
        import socket
        _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _s.settimeout(3)
        try:
            _s.connect(("192.168.1.187", 5000))
            _s.close()
            board_online_via_post = True
        except:
            _s.close()
    except: pass
    desired_status = "sent" if board_online_via_post else "pending"
    try:
        rq.put(f"{API}/aipet/app/reminders/{reminder_id}",
               headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
               json={"status":desired_status, "sentTime": time.strftime("%Y-%m-%dT%H:%M:%S")}, timeout=5)
        log(f"Status #{reminder_id} -> {desired_status} (board_online={board_online_via_post})")
    except: pass
    
    return JSONResponse({"success":True,"reminder_id":reminder_id})

@app.post("/api/update-remote-status")
def update_remote_status(data: dict):
    """Update reminder status on remote server (Section 22.4 PUT)."""
    rid = data.get("reminder_id")
    status = data.get("status", "")
    if not rid or not status:
        raise HTTPException(400, "reminder_id and status required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    try:
        r = rq.put(f"{API}/aipet/app/reminders/{rid}",
                   headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                   json={"status": status}, timeout=10)
        result = r.json()
        log(f"Remote status update #{rid} -> {status}: {result.get('msg','')}")
        return JSONResponse({"success": True, "msg": result.get("msg","cache_updated")})
    except Exception as e:
        log(f"Remote status update error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/cancel-remote-reminder")
def cancel_remote_reminder(data: dict):
    """Cancel a reminder: mark as cancelled on server + board (no audio playback)."""
    rid = data.get("reminder_id")
    title = data.get("title", "")
    rtime = data.get("reminder_time", "")
    new_status = data.get("new_status", "cancelled")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    refresh()  # Try to refresh, but continue even if fails
    # Try to update remote server status
    try:
        r = rq.put(f"{API}/aipet/app/reminders/{rid}",
                   headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                   json={"status":new_status}, timeout=10)
        result = r.json()
        if result.get("success"):
            log(f"Cancel #{rid}: {result.get('msg','')}")
        else:
            log(f"Cancel #{rid} remote failed: {result.get('msg','')}, updating local cache")
    except Exception as e:
        log(f"Cancel #{rid} remote error: {e}, updating local cache")
    # Sync to board via 8000 cache - use cancelled status directly (not 'restored')
    local_status = new_status
    try:
        rq.post("http://127.0.0.1:8000/api/board-reminders/status-update",
            json={"command_id": str(rid), "status": local_status, "content": title, "reminder_time": rtime}, timeout=3)
    except:
        pass
    return JSONResponse({"success": True, "msg": "Cancelled"})

@app.post("/api/delete-remote-reminder")
def delete_remote_reminder(data: dict):
    """Delete reminder from remote server and remove from board cache."""
    rid = data.get("reminder_id")
    title = data.get("title", "")
    rtime = data.get("reminder_time", "")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    # Try to delete from remote server
    try:
        r = rq.delete(f"{API}/aipet/app/reminders/{rid}",
                      headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        log(f"Remote delete #{rid}: {result.get('msg','')}")
        if not result.get("success"):
            log(f"Remote delete failed (will try local delete)")
    except Exception as e:
        log(f"Remote delete error: {e}")
    # Remove from board cache and SQLite
    try:
        rq.post("http://127.0.0.1:8000/api/board-reminders/delete-record",
            json={"command_id": str(rid), "content": title, "reminder_time": rtime}, timeout=5)
    except:
        pass
    return JSONResponse({"success": True, "msg": "Deleted"})

@app.post("/api/delete-remote-reminder-record")
def delete_remote_reminder_record(data: dict):
    """Permanently delete a reminder from server AND board."""
    rid = data.get("reminder_id")
    title = data.get("title", "")
    rtime = data.get("reminder_time", "")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    try:
        r = rq.delete(f"{API}/aipet/app/reminders/{rid}",
                      headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        log(f"Remote delete #{rid}: {result.get('msg','')}")
        if not result.get("success"):
            raise Exception(result.get("msg","Remote delete failed"))
        try:
            rq.post("http://127.0.0.1:8000/api/board-reminders/delete-record",
                json={"command_id": str(rid), "content": title, "reminder_time": rtime}, timeout=5)
        except:
            pass
        return JSONResponse({"success": True, "msg": "Deleted"})
    except Exception as e:
        log(f"Delete error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/re-login")
def re_login():
    ok = refresh(force=True)
    _cached_pid[0] = None
    return JSONResponse({"online": ok})


@app.get("/api/board-status")
def board_status():
    """Check board online status via socket connection to Flask port."""
    result = {"online": False, "method": "none"}
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        try:
            s.connect(("192.168.1.187", 5000))
            s.close()
            return JSONResponse({"online": True, "method": "direct_flask"})
        except:
            s.close()
    except: pass
    return JSONResponse(result)

@app.get("/api/remote-reminders")
def remote_reminders():
    # Try auth, fall back to cache if fails
    auth_ok = refresh()
    pid = get_pid() if auth_ok else None
    if not auth_ok or not pid:
        # Fall back to board_reminders.json cache
        try:
            _cfb = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "board_reminders.json")
            if os.path.exists(_cfb):
                _cfb_data = json.load(open(_cfb, "r", encoding="utf-8"))
                _fallback_rows = []
                for _c in _cfb_data:
                    _fallback_rows.append({
                        "id": str(_c.get("command_id","") or _c.get("id","")),
                        "title": _c.get("title","") or _c.get("content",""),
                        "content": _c.get("content","") or _c.get("title",""),
                        "reminderTime": _c.get("reminder_time",""),
                        "status": _c.get("status","received"),
                        "repeatType": _c.get("repeat_type",""),
                    })
                if _fallback_rows:
                    return JSONResponse({"success": True, "rows": _fallback_rows, "total": len(_fallback_rows)})
        except Exception as _fe:
            log(f"Cache fallback error: {_fe}")
        raise HTTPException(500, "Login failed")
    try:
        r = rq.get(f"{API}/aipet/app/reminders/list/{pid}/1/50",
                   headers={"Authorization": f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        # Server returns rows at top level: { code, rows: [...], total, ... }
        rows = result.get("rows", [])
        total = result.get("total", 0)
        # Merge remote status with local cache (board_reminders.json)
        try:
            import json as _jm
            _cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "board_reminders.json")
            if os.path.exists(_cache_path):
                _cache = _jm.load(open(_cache_path, "r", encoding="utf-8"))
                _cache_map = {}
                for _c in _cache:
                    _cid = str(_c.get("command_id","") or _c.get("id",""))
                    if _cid:
                        _cache_map[_cid] = _c.get("status","")
                    _ct = _c.get("content","") or _c.get("title","")
                    _cr = (_c.get("reminder_time","") or "").replace("T"," ")
                    _cache_map[_ct + "|" + _cr] = _c.get("status","")
                for _r in rows:
                    _rid = str(_r.get("id",""))
                    _rc = _r.get("content","") or _r.get("title","")
                    _rt = (_r.get("reminderTime","") or _r.get("reminder_time","") or "").replace("T"," ")
                    _rk = _rc + "|" + _rt
                    _local_st = _cache_map.get(_rid) or _cache_map.get(_rk) or ""
                    if _local_st and _local_st in ("completed","failed","triggered","executing"):
                        if _r.get("status","") or "" != _local_st:
                            _r["status"] = _local_st
                            _rs_val = _r.get("status","") or ""
                            log(f"Merged status #" + _rid + ": " + _rs_val + " -> " + _local_st + "")
        except Exception as _me:
            log(f"Cache merge error: {_me}")
        # Fallback: if remote returned nothing, use board cache data
        if not rows:
            try:
                _cfb = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "board_reminders.json")
                if os.path.exists(_cfb):
                    _cfb_data = _jm.load(open(_cfb, "r", encoding="utf-8"))
                    for _c in _cfb_data:
                        rows.append({
                            "id": str(_c.get("command_id","") or _c.get("id","")),
                            "title": _c.get("title","") or _c.get("content",""),
                            "content": _c.get("content","") or _c.get("title",""),
                            "reminderTime": _c.get("reminder_time",""),
                            "status": _c.get("status",""),
                            "repeatType": _c.get("repeat_type",""),
                        })
                    total = len(rows)
            except:
                pass
        return JSONResponse({"success": True, "rows": rows, "total": total})
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/")
def index():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__),"index.html"),encoding="utf-8").read())
    except:
        return HTMLResponse("<h1>RM</h1>")

if __name__ == "__main__":
    log(f"http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
