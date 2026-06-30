#!/usr/bin/env python3
"""reminder-backend 端口8000 — 纯 stdlib HTTP 服务器"""
import http.server, json, urllib.request, urllib.parse, os, time

REMOTE = "http://47.118.26.156:8000/api/v1"
token = [""]; phone = [""]; pets = []; current_pet = {}

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")

    def do_GET(self):
        # Frontend
        if self.path == "/" or self.path == "/index.html":
            return self.send_html("index.html")
        # API
        if self.path == "/api/status":
            return self.send_json({"logged_in":bool(token[0]),"phone":phone[0],"pet":current_pet.get("petName","")})
        if self.path.startswith("/api/login"):
            return self.handle_login()
        if self.path.startswith("/api/reminders") and "?" in self.path:
            return self.handle_list_reminders()
        if self.path.startswith("/api/board-reminders"):
            return self.send_json([])
        # Static files
        if self.path.startswith("/css/") or self.path.startswith("/js/"):
            p = os.path.join(os.path.dirname(__file__), self.path.lstrip("/"))
            if os.path.exists(p):
                self.send_response(200); self.end_headers()
                self.wfile.write(open(p,"rb").read()); return
        # Default
        return self.send_html("index.html")

    def do_POST(self):
        if self.path == "/api/reminders" or self.path == "/api/send-reminder":
            return self.handle_create()
        self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/reminders/"):
            rid = self.path.split("/api/reminders/")[-1]
            return self.handle_delete(rid)
        self.send_error(404)

    # ── helpers ──
    def send_html(self, filename):
        p = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(p):
            p = os.path.join(os.path.dirname(__file__), "frontend", filename)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(open(p,"rb").read())

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def fetch(self, url, tk=""):
        req = urllib.request.Request(url)
        if tk: req.add_header("Authorization", f"Bearer {tk}")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def api_post(self, url, data, tk):
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Authorization":f"Bearer {tk}","Content-Type":"application/json"}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def api_delete(self, url, tk):
        req = urllib.request.Request(url, headers={"Authorization":f"Bearer {tk}"}, method="DELETE")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    # ── handlers ──
    def handle_login(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        p = params.get("phone_num",[""])[0]
        if not p:
            body = self.read_body()
            p = body.get("phone","")
        try:
            r = self.fetch(f"{REMOTE}/aipet/app/auth/{p}/888888")
            tk = r.get("data","")
            if not tk: return self.send_json({"success":False,"msg":"login fail"})
            token[0] = tk; phone[0] = p
            r2 = self.fetch(f"{REMOTE}/aipet/app/myaipets", tk)
            pets.clear(); pets.extend(r2.get("data",[]))
            if pets: current_pet.update(pets[0])
            self.send_json({"success":True,"phone":p,"pets":len(pets),"pet_name":current_pet.get("petName","")})
        except Exception as e: self.send_json({"success":False,"msg":str(e)})

    def handle_list_reminders(self):
        if not token[0]: return self.send_json({"error":"login first"})
        pid = current_pet.get("id")
        if not pid: return self.send_json({"error":"no pet"})
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        page = params.get("page",["1"])[0]; size = params.get("size",["50"])[0]
        status = params.get("status",[""])[0]
        try:
            url = f"{REMOTE}/aipet/app/reminders/list/{pid}/{page}/{size}"
            if status: url += f"?status={status}"
            self.send_json(self.fetch(url, token[0]))
        except Exception as e: self.send_json({"error":str(e)})

    def handle_create(self):
        if not token[0]: return self.send_json({"success":False,"msg":"login first"})
        pid = current_pet.get("id")
        if not pid: return self.send_json({"success":False,"msg":"no pet"})
        data = self.read_body()
        title = data.get("title",""); content = data.get("content","")
        rtime = data.get("reminder_time","") or data.get("reminderTime","")
        rtype = data.get("repeat_type","none") or data.get("repeatType","none")
        if not title or not rtime:
            return self.send_json({"success":False,"msg":"title and time required"})
        payload = {"title":title,"content":content or title,"reminderTime":rtime,"repeatType":rtype}
        try:
            r = self.api_post(f"{REMOTE}/aipet/app/reminders/{pid}", payload, token[0])
            self.send_json({"success":True,"reminder_id":r.get("data",{}).get("id",""),"data":r})
        except Exception as e: self.send_json({"success":False,"msg":str(e)})

    def handle_delete(self, rid):
        if not token[0]: return self.send_json({"error":"login first"})
        try:
            self.send_json(self.api_delete(f"{REMOTE}/aipet/app/reminders/{rid}", token[0]))
        except Exception as e: self.send_json({"error":str(e)})

if __name__=="__main__":
    import socketserver
    socketserver.TCPServer.allow_reuse_address = True
    print("Backend on http://0.0.0.0:8000")
    with socketserver.TCPServer(("0.0.0.0", 8000), Handler) as httpd:
        httpd.serve_forever()
