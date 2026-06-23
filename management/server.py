import sys, json, time, threading, os, http.client
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

_utoken = [""]; _ws = [None]

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}")

def refresh():
    try:
        r = rq.get(f"{API}/aipet/app/auth/13800138000/888888", timeout=10)
        d = r.json()
        if d.get("success"): _utoken[0] = d.get("data",""); return True
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
            rd = msg.get("reminder_data") or msg.get("commandParams") or {}
            title = rd.get("title","") or rd.get("content","") or msg.get("title","") or msg.get("content","")
            content = rd.get("content","") or title
            rtime = rd.get("reminder_time","") or rd.get("reminderTime","") or msg.get("reminder_time","")
            log(f"REMINDER: {title}")
            # Forward to board via Flask API (not SSH)
            try:
                _body = json.dumps({"content":content,"reminder_time":rtime}, ensure_ascii=False).encode("utf-8")
                _conn = http.client.HTTPConnection("192.168.1.64", 5000, timeout=3)
                _conn.request("POST", "/api/reminders/create", _body, {"Content-Type": "application/json"})
                _resp = _conn.getresponse()
                _resp.read()
                _conn.close()
            except Exception as e:
                log(f"Board Flask error: {e}")
            if _ws[0]:
                _ws[0].send(json.dumps({"type":"command_response","command_id":cid,"command":cmd,"status":"success"}))

threading.Thread(target=ws_run, daemon=True).start()

app = FastAPI(title="RM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    refresh()

@app.get("/api/status")
def st():
    return JSONResponse({"online":bool(_utoken[0]), "pet_id":get_pid()})

@app.post("/api/send-reminder")
def send(data: dict):
    title = data.get("title",""); rtime = data.get("reminder_time",""); content = data.get("content","") or title
    if not title or not rtime: raise HTTPException(400,"title+time required")
    if not refresh(): raise HTTPException(500,"Login failed")
    pid = get_pid()
    if not pid: raise HTTPException(500,"No device")
    payload = {"sessionId":"mgmt_"+str(int(time.time())), "messageType":"command", "commandType":"reminder",
               "content":title, "commandParams":{"reminder_data":{"title":title, "content":content, "reminder_time":rtime, "repeat_type":data.get("repeat_type","")}}}
    r = rq.post(f"{API}/aipet/app/chatWith/{pid}", headers={"Authorization":f"Bearer {_utoken[0]}", "Content-Type":"application/json"}, json=payload, timeout=10)
    result = r.json()
    if result.get("success"):
        # Direct POST to board Flask API (bypass proxy with http.client)
        try:
            _body = json.dumps({"content":title,"reminder_time":rtime}, ensure_ascii=False).encode("utf-8")
            _conn = http.client.HTTPConnection("192.168.1.64", 5000, timeout=3)
            _conn.request("POST", "/api/reminders/create", _body, {"Content-Type": "application/json"})
            _resp = _conn.getresponse()
            _resp.read()
            _conn.close()
        except Exception as e:
            log(f"Board direct POST error: {e}")
        return JSONResponse({"success":True})
    raise HTTPException(500, result.get("msg","Failed"))

@app.get("/")
def index():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read())
    except:
        return HTMLResponse("<h1>RM</h1>")

if __name__ == "__main__":
    log(f"http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
