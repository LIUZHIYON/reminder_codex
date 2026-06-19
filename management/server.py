import os
os.environ['no_proxy'] = '47.118.26.156'
os.environ['NO_PROXY'] = '47.118.26.156'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
import sys, json, time, threading, websocket
import requests as rq
import requests as _rq
# Patch: bypass local proxy

_rq_orig_get = _rq.get
_rq_orig_post = _rq.post
def _rq_no_proxy_get(url, **kw): kw['proxies'] = {'http':None,'https':None}; return _rq_orig_get(url, **kw)
def _rq_no_proxy_post(url, **kw): kw['proxies'] = {'http':None,'https':None}; return _rq_orig_post(url, **kw)
_rq.get = _rq_no_proxy_get
_rq.post = _rq_no_proxy_post
rq = _rq
import sys, json, time, threading, websocket
import requests as rq
import os as _os; _os.environ['no_proxy'] = '47.118.26.156'  # bypass proxy for server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

API = "http://47.118.26.156:8000/api/v1"
SERIAL = "6976f96f-bc80-56e3-9b27-13d12cdde9d3"
PORT = 8001

state = {"online":False, "last_seen":"", "reminders":[]}
_ws = [None]; _utoken = [""]

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}")

def refresh():
    try:
        r = rq.get(f"{API}/aipet/app/auth/13800138000/888888", timeout=10)
        d = r.json()
        if d.get("success"):
            _utoken[0] = d.get("data","")
            return True
        log(f"Auth fail: {d.get('msg','')}")
    except Exception as e:
        log(f"Auth error: {e}")
    _utoken[0] = ""
    return False

def get_pid():
    refresh()
    if not _utoken[0]: return None
    try:
        r = rq.get(f"{API}/aipet/app/myaipets", headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        pets = r.json().get("data",[])
        return pets[0].get("id") if pets else None
    except:
        return None

def ws_run():
    while True:
        try:
            r = rq.get(f"{API}/aipet/ws/auth/{SERIAL}", timeout=10)
            tk = r.json().get("data","")
            if not tk:
                log("No WS token, retry 5s")
                time.sleep(5)
                continue
            url = f"ws://47.118.26.156:8000/api/v1/aipet/ws/{SERIAL}"
            _ws[0] = websocket.WebSocketApp(url,
                on_open=lambda s: s.send(json.dumps({"type":"auth","access_token":tk})),
                on_message=lambda s,m: on_msg(json.loads(m)),
                on_error=lambda s,e: log(f"WS err: {e}"),
                on_close=lambda *a: log("WS closed"))
            log("WS connecting...")
            _ws[0].run_forever()
        except Exception as e:
            log(f"WS error: {e}")
        time.sleep(5)

def on_msg(msg):
    t = msg.get("type","")
    log(f"WS {t}: {json.dumps(msg, ensure_ascii=False)[:200]}")
    if t == "auth" and msg.get("success"):
        state["online"] = True
        state["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        log("AUTH OK!")
    elif t == "heartbeat":
        state["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    elif t == "server_command":
        cmd = msg.get("command",""); cid = msg.get("command_id","")
        if cmd == "reminder":
            print("[DEBUG] WS MSG:" + json.dumps(msg, ensure_ascii=False)[:300])
            rd = msg.get("reminder_data") or {}
            cp = msg.get("commandParams") or msg.get("command_params") or {}
            rd = rd or cp.get("reminder_data") or cp.get("reminderData") or cp
            if not rd.get("title"):
                rd = {"title": msg.get("title",""), "content": msg.get("content",""), "reminder_time": msg.get("reminder_time","")}
            rec = {"command_id":cid, "title":rd.get("title",""), "content":rd.get("content",""),
                   "reminder_time":rd.get("reminder_time","") or rd.get("reminderTime",""), "received_at":time.strftime("%Y-%m-%dT%H:%M:%S"), "status":"received"}
            log(f"REMINDER: {rec['title']}")
            state["reminders"].insert(0, rec)
            state["reminders"] = state["reminders"][:50]
            try:
                fp = os.path.join(os.path.dirname(__file__), "reminders.json")
                with open(fp, "w", encoding="utf-8") as f: json.dump(state["reminders"], f, ensure_ascii=False)
            except: pass
            if _ws[0]:
                _ws[0].send(json.dumps({"type":"command_response","command_id":cid,"command":cmd,"status":"success","result":{"received":True}}))

threading.Thread(target=ws_run, daemon=True).start()

app = FastAPI(title="RM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    refresh()

@app.get("/api/status")
def st():
    return JSONResponse({"online":state["online"], "last_seen":state["last_seen"], "pet_id":get_pid(), "reminders":len(state["reminders"])})

@app.get("/api/reminders")
def reminders():
    return JSONResponse(state["reminders"])

@app.post("/api/send-reminder")
def send(data: dict):
    title = data.get("title",""); rtime = data.get("reminder_time",""); content = data.get("content","")
    if not title or not rtime: raise HTTPException(400,"title+time required")
    if not refresh(): raise HTTPException(500,"Login failed")
    pid = get_pid()
    if not pid: raise HTTPException(500,"No device")
    payload = {"sessionId":"mgmt_"+str(int(time.time())), "messageType":"command", "commandType":"reminder", "content":title, "commandParams":{"reminder_data":{"title":title, "content":content, "reminder_time":rtime, "repeat_type":data.get("repeat_type","")}}}
    r = rq.post(f"{API}/aipet/app/chatWith/{pid}", headers={"Authorization":f"Bearer {_utoken[0]}", "Content-Type":"application/json"}, json=payload, timeout=10)
    result = r.json()
    if result.get("success"): return JSONResponse({"success":True, "data":result.get("data",{})})
    raise HTTPException(500, result.get("msg","Failed"))

@app.get("/")
def index():
    try:
        fp = os.path.join(os.path.dirname(__file__), "index.html")
        return HTMLResponse(open(fp, encoding="utf-8").read())
    except Exception as e:
        print(f"[ERROR] index.html: {e}")
        return HTMLResponse("<h1>Reminder Management</h1><p>Server running. <a href=\"/api/status\">API Status</a></p>")

if __name__ == "__main__":
    log(f"http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)









