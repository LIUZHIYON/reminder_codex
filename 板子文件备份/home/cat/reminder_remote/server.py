#!/usr/bin/env python3
import json, time
import requests as rq
from flask import Flask, request, jsonify

API = "http://47.118.26.156:8000/api/v1"
_utoken = [""]; _pets = []; _pid = [None]; _phone = [""]
app = Flask(__name__)
def log(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

@app.route("/api/login")
def login():
    phone = request.args.get("phone_num","")
    try:
        r = rq.get(f"{API}/aipet/app/auth/{phone}/888888", timeout=10)
        tk = r.json().get("data","")
        if not tk: return jsonify({"success":False})
        _utoken[0]=tk; _phone[0]=phone
        r2 = rq.get(f"{API}/aipet/app/myaipets", headers={"Authorization":f"Bearer {tk}"}, timeout=10)
        _pets.clear(); _pets.extend(r2.json().get("data",[]))
        if _pets: _pid[0]=_pets[0].get("id")
        log(f"Login: {phone}")
        return jsonify({"success":True,"phone":phone})
    except Exception as e:
        return jsonify({"success":False,"msg":str(e)})

@app.route("/api/status")
def status():
    return jsonify({"logged_in":bool(_utoken[0]),"phone":_phone[0],"pid":_pid[0]})

@app.route("/api/reminders")
def list_reminders():
    if not _utoken[0] or not _pid[0]: return jsonify({"success":False})
    try:
        r = rq.get(f"{API}/aipet/app/reminders/list/{_pid[0]}/1/50",
                   headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success":False,"msg":str(e)})

@app.route("/api/reminders", methods=["POST"])
def send_reminder():
    if not _utoken[0] or not _pid[0]: return jsonify({"success":False})
    data = request.get_json(force=True,silent=True) or {}
    t = data.get("title",""); c = data.get("content","") or t
    rt = data.get("reminder_time",""); rp = data.get("repeat_type","none")
    if not t or not rt: return jsonify({"success":False,"msg":"title+time"})
    payload = {"title":t,"content":c,"reminderTime":rt,"repeatType":rp}
    try:
        r = rq.post(f"{API}/aipet/app/reminders/{_pid[0]}",
                     headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                     json=payload, timeout=10)
        result = r.json()
        rid = result.get("data",{}).get("id") or result.get("id","?")
        log(f"Sent: {t[:20]} id={rid}")
        # Immediate push via command API
        try:
            rq.post(f"{API}/aipet/app/command/{_pid[0]}/reminder",
                    headers={"Authorization":f"Bearer {_utoken[0]}","Content-Type":"application/json"},
                    json={"reminder_data":payload}, timeout=5)
            log(f"Pushed immediately: {rid}")
        except Exception as e:
            log(f"Push failed: {e}")
        return jsonify({"success":True,"reminder_id":rid})
    except Exception as e:
        return jsonify({"success":False,"msg":str(e)})

@app.route("/api/reminders/<rid>", methods=["DELETE"])
def delete_reminder(rid):
    try:
        rq.delete(f"{API}/aipet/app/reminders/{rid}",
                  headers={"Authorization":f"Bearer {_utoken[0]}"}, timeout=10)
        return jsonify({"success":True})
    except: return jsonify({"success":False})

@app.route("/")
def index():
    return open(__file__.replace("server.py","index.html"), encoding="utf-8").read()

if __name__ == "__main__":
    print("  8001 Flask on http://0.0.0.0:8001")
    app.run(host="0.0.0.0", port=8001, debug=False)
