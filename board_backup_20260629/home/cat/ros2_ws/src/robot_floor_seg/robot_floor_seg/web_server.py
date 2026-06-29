import os
import cv2
import threading
import numpy as np
from flask import Flask, Response, render_template_string, jsonify

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Wall/Floor Segmentation</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0d1117;color:#e6edf3;padding:20px}
h1{font-size:1.4em;margin-bottom:4px}
.subtitle{color:#8b949e;font-size:.85em;margin-bottom:16px}
.row{display:flex;gap:20px;flex-wrap:wrap}
.col-left{flex:2;min-width:300px}
.col-right{flex:1;min-width:200px}
.vid-box{border-radius:12px;overflow:hidden;border:1px solid #30363d;position:relative;background:#161b22}
#stream{display:block;width:100%}
.stat{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 16px;text-align:center;min-width:80px;flex:1;margin-top:12px}
.stat-v{font-size:1.4em;font-weight:600;color:#58a6ff}
.stat-l{font-size:.7em;color:#8b949e;text-transform:uppercase}
.btn{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:1em;font-weight:600;transition:all .2s;border:none;margin-top:12px}
.btn.on{background:#238636;color:#fff}
.btn.off{background:#da3633;color:#fff}
.btn:hover{filter:brightness(1.2)}
#status{margin-top:12px;font-size:.9em}
.green{color:#3fb950}
.red{color:#f85149}
</style>
</head>
<body>
<h1>Wall/Floor Segmentation</h1>
<div class="subtitle">v2 model &middot; RK3576 NPU</div>
<div class="row">
<div class="col-left">
<div class="vid-box"><img id="stream" src="/video_feed" style="width:100%"></div>
<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-top:12px">
<button class="btn on" id="toggle-btn" onclick="toggleSeg()">Running</button>
<span id="status"><span class="green">&#9679;</span> Inference ON</span>
</div>
</div>
<div class="col-right">
<div class="stat"><div class="stat-v" id="fps">0.0</div><div class="stat-l">FPS</div></div>
<div class="stat"><div class="stat-v" id="det">0</div><div class="stat-l">Detections</div></div>
<div class="stat"><div class="stat-v" id="latency">0</div><div class="stat-l">Latency ms</div></div>
</div>
</div>
<script>
function toggleSeg(){
fetch("/toggle").then(function(r){return r.json()}).then(function(d){
var btn=document.getElementById("toggle-btn");
var st=document.getElementById("status");
if(d.enabled){
btn.textContent="Running";btn.className="btn on";
st.innerHTML='<span class="green">&#9679;</span> Inference ON';
}else{
btn.textContent="Stopped";btn.className="btn off";
st.innerHTML='<span class="red">&#9679;</span> Inference OFF';
}
document.getElementById("stream").src="/video_feed?"+Date.now();
});
}
setInterval(function(){
fetch("/stats").then(function(r){return r.json()}).then(function(d){
document.getElementById("fps").textContent=d.fps;
document.getElementById("det").textContent=d.n;
document.getElementById("latency").textContent=d.latency;
});
},500);
</script>
</body>
</html>
"""


class WebServer:
    def __init__(self, get_frame_fn, host="0.0.0.0", port=8080):
        self.get_frame = get_frame_fn
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
        self._thread = None

    def _setup_routes(self):
        app = self.app

        @app.route("/")
        def index():
            return render_template_string(HTML)

        @app.route("/video_feed")
        def video_feed():
            def gen():
                while True:
                    frame_data = self.get_frame()
                    if frame_data:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")
                    import time
                    time.sleep(0.05)
            return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

        @app.route("/toggle")
        def toggle():
            state = self.get_frame(toggle=True)
            return jsonify(enabled=state)

        @app.route("/stats")
        def stats():
            s = self.get_frame(stats=True)
            return jsonify(fps=round(s.get("fps", 0), 1),
                          n=s.get("n", 0),
                          latency=round(s.get("latency", 0), 1))

    def start(self):
        from waitress import serve
        serve(self.app, host=self.host, port=self.port, threads=4)
