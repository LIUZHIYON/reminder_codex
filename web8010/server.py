#!/usr/bin/env python3
"""reminder-web 纯 stdlib HTTP 服务器 端口8010"""
import http.server, json, urllib.request, urllib.parse, os

REMOTE = "http://47.118.26.156:8000/api/v1"
token = [""]; phone = [""]; pets = []; current_pet = {}

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200); self.end_headers()
            p = os.path.join(os.path.dirname(__file__), "index.html")
            self.wfile.write(open(p,"rb").read()); return
        if self.path == "/api/status":
            self.send_json({"logged_in":bool(token[0]),"phone":phone[0],"pet":current_pet.get("petName","")}); return
        if self.path.startswith("/api/login"):
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            p = params.get("phone_num",[""])[0]
            try:
                r = self.fetch(f"{REMOTE}/aipet/app/auth/{p}/888888")
                tk = r.get("data","")
                if not tk: self.send_error(401); return
                token[0] = tk; phone[0] = p
                r2 = self.fetch(f"{REMOTE}/aipet/app/myaipets", tk)
                pets.clear(); pets.extend(r2.get("data",[]))
                if pets: current_pet.update(pets[0])
                self.send_json({"success":True,"phone":p,"pets":len(pets)})
            except Exception as e: self.send_error(500, str(e))
            return
        if self.path.startswith("/api/reminders?"):
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = params.get("page",["1"])[0]; size = params.get("size",["50"])[0]
            status = params.get("status",[""])[0]
            pid = current_pet.get("id")
            if not pid or not token[0]: self.send_error(401); return
            try:
                url = f"{REMOTE}/aipet/app/reminders/list/{pid}/{page}/{size}"
                if status: url += f"?status={status}"
                self.send_json(self.fetch(url, token[0]))
            except Exception as e: self.send_error(500, str(e))
            return
        # serve index.html
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/reminders":
            if not token[0]: self.send_error(401); return
            pid = current_pet.get("id")
            if not pid: self.send_error(400); return
            try:
                length = int(self.headers.get("Content-Length",0))
                data = json.loads(self.rfile.read(length))
                payload = {"title":data.get("title",""),"content":data.get("content",""),
                           "reminderTime":data.get("reminder_time",""),"repeatType":data.get("repeat_type","none")}
                r = self.post(f"{REMOTE}/aipet/app/reminders/{pid}", payload, token[0])
                self.send_json(r)
            except Exception as e: self.send_error(500, str(e))
            return

    def do_DELETE(self):
        rid = self.path.split("/api/reminders/")[-1]
        if not rid or not token[0]: self.send_error(401); return
        try:
            self.send_json(self.delete(f"{REMOTE}/aipet/app/reminders/{rid}", token[0]))
        except Exception as e: self.send_error(500, str(e))

    def send_json(self, data):
        self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def fetch(self, url, tk=""):
        req = urllib.request.Request(url)
        if tk: req.add_header("Authorization", f"Bearer {tk}")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def post(self, url, data, tk):
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Authorization":f"Bearer {tk}","Content-Type":"application/json"}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def delete(self, url, tk):
        req = urllib.request.Request(url, headers={"Authorization":f"Bearer {tk}"}, method="DELETE")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

if __name__=="__main__":
    import socketserver
    print("Reminder Web stdlib on http://0.0.0.0:8010")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", 8010), Handler) as httpd:
        httpd.serve_forever()
