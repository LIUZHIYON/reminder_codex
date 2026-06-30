#!/usr/bin/env python3
"""reminder-web Flask版 端口8010"""
from flask import Flask, request, jsonify, render_template_string
import requests as rq, os

REMOTE = "http://47.118.26.156:8000/api/v1"
app = Flask(__name__)

token = [""]; phone = [""]; pets = []; current_pet = {}

INDEX = open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()

@app.route("/")
def index():
    return INDEX

@app.route("/api/login")
def login():
    p = request.args.get("phone_num","")
    s = request.args.get("sms","888888")
    try:
        r = rq.get(f"{REMOTE}/aipet/app/auth/{p}/{s}", timeout=10)
        tk = r.json().get("data","")
        if not tk: return jsonify({"success":False,"msg":"login fail"}), 401
        token[0] = tk; phone[0] = p
        r2 = rq.get(f"{REMOTE}/aipet/app/myaipets",headers={"Authorization":f"Bearer {tk}"},timeout=10)
        pets.clear(); pets.extend(r2.json().get("data",[]))
        if pets: current_pet.update(pets[0])
        return jsonify({"success":True,"phone":p,"pets":len(pets)})
    except Exception as e: return jsonify({"success":False,"msg":str(e)}), 500

@app.route("/api/reminders")
def list_reminders():
    if not token[0]: return jsonify({"error":"not logged in"}), 401
    pid = current_pet.get("id")
    if not pid: return jsonify({"error":"no pet"}), 400
    page = request.args.get("page","1")
    size = request.args.get("size","50")
    status = request.args.get("status","")
    params = {"status":status} if status else {}
    try:
        r = rq.get(f"{REMOTE}/aipet/app/reminders/list/{pid}/{page}/{size}",
                    headers={"Authorization":f"Bearer {token[0]}"},params=params,timeout=10)
        return jsonify(r.json())
    except Exception as e: return jsonify({"error":str(e)}), 500

@app.route("/api/reminders", methods=["POST"])
def create_reminder():
    if not token[0]: return jsonify({"error":"not logged in"}), 401
    pid = current_pet.get("id")
    if not pid: return jsonify({"error":"no pet"}), 400
    data = request.get_json() or {}
    payload = {"title":data.get("title",""),"content":data.get("content",""),
               "reminderTime":data.get("reminder_time",""),"repeatType":data.get("repeat_type","none")}
    if not payload["title"] or not payload["reminderTime"]:
        return jsonify({"error":"title and time required"}), 400
    try:
        r = rq.post(f"{REMOTE}/aipet/app/reminders/{pid}",
                     headers={"Authorization":f"Bearer {token[0]}","Content-Type":"application/json"},
                     json=payload,timeout=10)
        return jsonify(r.json())
    except Exception as e: return jsonify({"error":str(e)}), 500

@app.route("/api/reminders/<rids>", methods=["DELETE"])
def delete_reminders(rids):
    if not token[0]: return jsonify({"error":"not logged in"}), 401
    try:
        r = rq.delete(f"{REMOTE}/aipet/app/reminders/{rids}",
                       headers={"Authorization":f"Bearer {token[0]}"},timeout=10)
        return jsonify(r.json())
    except Exception as e: return jsonify({"error":str(e)}), 500

@app.route("/api/status")
def status():
    return jsonify({"logged_in":bool(token[0]),"phone":phone[0],
                    "pet":current_pet.get("petName",""),"server":REMOTE})

if __name__=="__main__":
    print("  Reminder Web Flask on http://0.0.0.0:8010")
    from waitress import serve
    serve(app, host="0.0.0.0", port=8010)
