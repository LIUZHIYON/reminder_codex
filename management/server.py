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

_utoken = [""]; _ws = [None]; _reminders = []

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}")

def refresh():
    try:
        r = rq.get(f"{API}/aipet/app/auth/13800138000/888888", timeout=10)
        d = r.json()
        if d.get("success"):
            _utoken[0] = d.get("data","")
            return True
    except Exception as e: log(f"Auth error: {e}")
    _utoken[0] = ""; return False

def get_pid():
    refresh()
    if not _utoken[0]: return None
    try:
        r = rq.get(f"{API}/aipet/app/myaipets", headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        pets = r.json().get("data",[])
        return pets[0].get("id") if pets else None
    except: return None

def ws_run():
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
            rd = msg.get("command_params",{}).get("reminder_data",{})
            title = rd.get("title","") or msg.get("content","")
            content = rd.get("content","") or title
            rtime = rd.get("reminder_time","") or rd.get("reminderTime","")
            log(f"REMINDER: {title}")
            rec = {"command_id":cid,"title":title,"content":content,"reminder_time":rtime,
                   "status":"received","received_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
            _reminders.insert(0, rec)
            try:
                fp = os.path.join(os.path.dirname(__file__),"reminders.json")
                with open(fp,"w",encoding="utf-8") as f: json.dump(_reminders[:50],f,ensure_ascii=False)
            except: pass
            # Push to board Flask + 8000 cache
            try:
                import http.client
                _body = json.dumps({"content":title,"reminder_time":rtime},ensure_ascii=False).encode("utf-8")
                _conn = http.client.HTTPConnection("192.168.1.226",5000,timeout=3)
                _conn.request("POST","/api/reminders/create",_body,{"Content-Type":"application/json"})
                _conn.getresponse().read(); _conn.close()
            except: pass
            try:
                rq.post("http://127.0.0.1:8000/api/board-reminders/sync",
                    json={"title":title,"reminder_time":rtime,"content":title},timeout=2)
            except: pass
            if _ws[0]:
                _ws[0].send(json.dumps({"type":"command_response","command_id":cid,
                    "command":cmd,"status":"success","result":{"received":True}}))

threading.Thread(target=ws_run, daemon=True).start()

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
    if not result.get("success"): raise HTTPException(500, result.get("msg","Failed"))
    reminder_id = result.get("data",{}).get("id")
    if not reminder_id: raise HTTPException(500,"No reminder_id in response")
    
    # Step 2: Send to device (Section 22.6)
    send_r = rq.post(f"{API}/aipet/app/reminders/send/{pid}/{reminder_id}",
                     headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
    send_result = send_r.json()
    log(f"Created reminder #{reminder_id}, send result: {send_result.get('msg','')}")
    
    # Also direct POST to board Flask
    try:
        import http.client
        _body = json.dumps({"content":title,"reminder_time":rtime},ensure_ascii=False).encode("utf-8")
        _conn = http.client.HTTPConnection("192.168.1.226",5000,timeout=3)
        _conn.request("POST","/api/reminders/create",_body,{"Content-Type":"application/json"})
        _resp = _conn.getresponse(); _resp.read(); _conn.close()
    except: pass
    
    # Sync to local cache with command_id = remote reminder_id
    try:
        rq.post("http://127.0.0.1:8000/api/board-reminders/sync",
            json={"command_id":str(reminder_id),"title":title,"reminder_time":rtime,"content":title},timeout=2)
    except: pass
    # Explicitly set remote server status to "sent" (Section 22.4 PUT)
    try:
        rq.put(f"{API}/aipet/app/reminders/{reminder_id}",
               headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
               json={"status":"sent"}, timeout=5)
    except: pass
    
    return JSONResponse({"success":True,"reminder_id":reminder_id,"send_result":send_result.get("msg","")})

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
        return JSONResponse({"success": result.get("success", False), "msg": result.get("msg","")})
    except Exception as e:
        log(f"Remote status update error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/cancel-remote-reminder")
def cancel_remote_reminder(data: dict):
    """Cancel a reminder: mark as cancelled on server + board (only for unplayed reminders)."""
    rid = data.get("reminder_id")
    title = data.get("title", "")
    rtime = data.get("reminder_time", "")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    try:
        # PUT status=cancelled on remote server (Section 22.4)
        r = rq.put(f"{API}/aipet/app/reminders/{rid}",
                   headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                   json={"status":"cancelled"}, timeout=10)
        result = r.json()
        log(f"Cancel #{rid}: {result.get('msg','')}")
        # Sync to board via 8000 cache + SSH
        try:
            rq.post("http://127.0.0.1:8000/api/board-reminders/status-update",
                json={"command_id": str(rid), "status": "cancelled", "content": title, "reminder_time": rtime}, timeout=3)
        except:
            pass
        return JSONResponse({"success": result.get("success", False), "msg": result.get("msg","")})
    except Exception as e:
        log(f"Cancel error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/delete-remote-reminder")
def delete_remote_reminder(data: dict):
    """Delete reminder from remote server (Section 22.5) and sync cancellation to board."""
    rid = data.get("reminder_id")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    try:
        r = rq.delete(f"{API}/aipet/app/reminders/{rid}",
                      headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        log(f"Remote delete #{rid}: {result.get('msg','')}")
        # Sync cancellation to 8000 cache (which syncs to board via SSH)
        try:
            rq.post("http://127.0.0.1:8000/api/board-reminders/status-update",
                json={"command_id": str(rid), "status": "cancelled"}, timeout=3)
        except:
            pass
        return JSONResponse({"success": result.get("success", False), "msg": result.get("msg","")})
    except Exception as e:
        log(f"Remote delete error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/delete-remote-reminder-record")
def delete_remote_reminder_record(data: dict):
    """Permanently delete a reminder from server AND board SQLite."""
    rid = data.get("reminder_id")
    title = data.get("title", "")
    rtime = data.get("reminder_time", "")
    if not rid:
        raise HTTPException(400, "reminder_id required")
    if not refresh():
        raise HTTPException(500, "Login failed")
    try:
        # DELETE from remote server (Section 22.5 - soft delete)
        r = rq.delete(f"{API}/aipet/app/reminders/{rid}",
                      headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        log(f"Remote delete #{rid}: {result.get('msg','')}")
        # Delete from board SQLite via 8000
        try:
            rq.post("http://127.0.0.1:8000/api/board-reminders/delete-record",
                json={"command_id": str(rid), "content": title, "reminder_time": rtime}, timeout=3)
        except:
            pass
        return JSONResponse({"success": result.get("success", False), "msg": result.get("msg","")})
    except Exception as e:
        log(f"Delete error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/remote-reminders")
def remote_reminders():
    if not refresh():
        raise HTTPException(500, "Login failed")
    pid = get_pid()
    if not pid:
        raise HTTPException(500, "No device")
    try:
        r = rq.get(f"{API}/aipet/app/reminders/list/{pid}/1/50",
                   headers={"Authorization": f"Bearer {_utoken[0]}"}, timeout=10)
        result = r.json()
        # Server returns rows at top level: { code, rows: [...], total, ... }
        rows = result.get("rows", [])
        total = result.get("total", 0)
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