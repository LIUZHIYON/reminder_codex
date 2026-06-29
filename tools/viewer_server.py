"""只读查看服务 - 替代后端8000，没有scheduler，不会和行为树冲突"""
import os, json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Board Reminder Viewer (Read-Only)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE_FILE = r"E:\LuBanCat\BT_ros2\reminder_codex-1.1\board_reminders.json"

@app.get("/api/board-reminders")
def list_reminders():
    if os.path.exists(CACHE_FILE):
        try:
            data = json.load(open(CACHE_FILE, "r", encoding="utf-8"))
            return data
        except:
            return []
    return []

@app.get("/api/board-reminders/status")
def status():
    count = 0
    if os.path.exists(CACHE_FILE):
        try:
            count = len(json.load(open(CACHE_FILE, "r", encoding="utf-8")))
        except:
            pass
    return {"online": True, "host": "192.168.1.191", "mode": "bt", "reminder_count": count}

@app.get("/")
def index():
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>提醒查看器 - 行为树模式</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{padding:20px;background:#f5f5f5}
h1{color:#333;margin-bottom:10px}
.status{background:#e8f5e9;padding:10px 15px;border-radius:8px;margin-bottom:20px;font-size:14px;color:#2e7d32}
.status span{font-weight:bold}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #eee;font-size:13px}
th{background:#f8f9fa;color:#666;font-weight:600}
tr:hover{background:#f0f7ff}
.badge{padding:2px 8px;border-radius:4px;font-size:12px}
.c0{background:#e8f5e9;color:#2e7d32}
.c1{background:#fff3e0;color:#e65100}
.c2{background:#e3f2fd;color:#1565c0}
</style>
</head>
<body>
<h1>板子提醒查看器</h1>
<div class="status">模式: <span>行为树 (robot_reminder_bt)</span> | 只读不播报</div>
<table>
<thead><tr><th>ID</th><th>标题</th><th>时间</th><th>状态</th></tr></thead>
<tbody id="list"></tbody>
</table>
<script>
fetch('/api/board-reminders').then(r=>r.json()).then(d=>{
    document.getElementById('list').innerHTML=d.map(r=>
        '<tr><td>'+(r.command_id||r.id||'')+'</td><td>'+(r.title||r.content||'')+'</td><td>'+(r.reminder_time||'').replace('T',' ')+'</td><td><span class="badge c'+(r.status=='completed'?0:1)+'">'+(r.status||'')+'</span></td></tr>'
    ).join('');
}).catch(e=>{document.getElementById('list').innerHTML='<tr><td colspan="4">Error: '+e+'</td></tr>'});
</script>
</body>
</html>"""
    return HTMLResponse(html)

if __name__ == "__main__":
    print(f"[Viewer] Port 8002 | {CACHE_FILE} | BT mode")
    uvicorn.run(app, host="0.0.0.0", port=8002)
