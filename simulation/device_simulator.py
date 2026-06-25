#!/usr/bin/env python3
"""模拟设备节点 - 通过 WebSocket 连接到服务器，处理提醒命令

用法:
  python device_simulator.py
  python device_simulator.py --serial AIPET-DEMO-002
  python device_simulator.py --server 47.118.26.156:8000

连接流程:
  1. 连接 WebSocket
  2. 发送 Auth
  3. 定时 Heartbeat（30s）
  4. 接收 server_command → 处理 reminde
  5. 上报 command_response
"""

import json
import sys
import os
import time
import threading
import argparse
import requests
import subprocess


class DeviceSimulator:
    """模拟设备节点"""

    def __init__(self, serial_number="AIPET-DEMO-001", server_host="47.118.26.156",
                 server_port=3000, ws_path="/openclaw-wwh/robot_websocket"):
        self.serial_number = serial_number
        self.server_host = server_host
        self.server_port = server_port
        self.ws_path = ws_path
        self.audio_dir = "./audio"
        self.heartbeat_interval = 30

        self._ws = None
        self._connected = False
        self._authenticated = False
        self._running = True

        os.makedirs(self.audio_dir, exist_ok=True)

    # ── 打印带时间戳 ──
    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ── 主循环 ──
    def start(self):
        import websocket
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.ws_path}"
        self.log(f"Connecting to {ws_url}")

        self._ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        wst = threading.Thread(target=self._ws.run_forever, daemon=True)
        wst.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Shutting down...")
            self._running = False
            if self._ws:
                self._ws.close()

    # ── WebSocket 回调 ──
    def _on_open(self, ws):
        self.log("WebSocket connected")
        self._connected = True
        self._send_auth()

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
            t = msg.get("type", "")
            if t == "auth":
                self._on_auth(msg)
            elif t == "heartbeat":
                self.log("Heartbeat OK")
            elif t == "server_command":
                self._on_command(msg)
            elif t == "chat":
                self.log(f"Chat: {msg.get('content','')}")
        except Exception as e:
            self.log(f"Message error: {e}")

    def _on_error(self, ws, error):
        self.log(f"WebSocket error: {error}")
        self._connected = False
        self._authenticated = False

    def _on_close(self, ws, status, msg):
        self.log(f"WebSocket closed: {status}")
        self._connected = False
        self._authenticated = False
        if self._running:
            self.log("Reconnecting in 5s...")
            time.sleep(5)
            self.start()

    def _send(self, data):
        if self._ws and self._connected:
            self._ws.send(json.dumps(data, ensure_ascii=False))

    # ── Auth ──
    def _send_auth(self):
        # 尝试从 HTTP 接口获取 token
        token = self.serial_number  # fallback
        try:
            r = requests.get(
                f"http://{self.server_host}:8000/api/v1/aipet/ws/auth/{self.serial_number}",
                timeout=5
            )
            if r.ok:
                data = r.json()
                if data.get("success") and data.get("data"):
                    token = data["data"]
                    self.log(f"Got WS token from API")
        except Exception as e:
            self.log(f"Cannot get WS token, using serial: {e}")

        self._send({"type": "auth", "access_token": token})
        self.log("Auth sent")

    def _on_auth(self, msg):
        if msg.get("success"):
            self._authenticated = True
            self.log("Authentication successful!")
            # 启动心跳
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            # 请求配置
            self._send({"type": "config_request"})
        else:
            self.log(f"Auth failed: {msg.get('message','')}")

    # ── Heartbeat ──
    def _heartbeat_loop(self):
        while self._connected and self._authenticated and self._running:
            self._send({"type": "heartbeat"})
            time.sleep(self.heartbeat_interval)

    # ── 处理命令 ──
    def _on_command(self, msg):
        cmd = msg.get("command", "")
        cmd_id = msg.get("command_id", "")
        params = msg.get("command_params", {})
        self.log(f"Command: {cmd} id={cmd_id}")

        if cmd == "reminder":
            self._handle_reminder(cmd_id, params)
        elif cmd == "upload_status":
            self._send_response(cmd_id, cmd, "success", {"status": "online"})
        elif cmd == "update_config":
            self._send_response(cmd_id, cmd, "success", {})
        elif cmd == "play_sound":
            self._send_response(cmd_id, cmd, "success", {"played": True})
        elif cmd == "set_volume":
            v = params.get("volume", 50)
            self.log(f"Set volume: {v}")
            self._send_response(cmd_id, cmd, "success", {"volume": v})
        elif cmd == "set_brightness":
            b = params.get("brightness", 80)
            self.log(f"Set brightness: {b}")
            self._send_response(cmd_id, cmd, "success", {"brightness": b})
        elif cmd == "wake_up":
            self.log("Wake up!")
            self._send_response(cmd_id, cmd, "success", {})
        elif cmd == "sleep":
            self.log("Sleep...")
            self._send_response(cmd_id, cmd, "success", {})
        else:
            self.log(f"Unknown command: {cmd}")
            self._send_response(cmd_id, cmd, "failed", {}, "unknown_command")

    def _handle_reminder(self, command_id, params):
        """执行提醒：合成语音 + 播放"""
        rd = params.get("reminder_data", {})
        title = rd.get("title", "未命名")
        content = rd.get("content", "")
        self.log(f"=== REMINDER ===")
        self.log(f"Title: {title}")
        self.log(f"Content: {content}")
        self.log(f"================")

        # 上报执行中
        self._send_response(command_id, "reminder", "executing", {})

        # 生成 TTS
        audio_path = self._generate_tts(title, content)
        if not audio_path:
            self._send_response(command_id, "reminder", "failed", {}, "tts_failed")
            return

        # 播放
        self._play_audio(audio_path)

        # 上报成功
        self._send_response(command_id, "reminder", "success", {
            "played": True,
            "title": title,
        })
        self.log(f"Reminder done: {title}")

    def _generate_tts(self, title, content=""):
        """TTS 合成"""
        text = f"叮咚！提醒时间到啦！{title}"
        if content:
            text += f"。{content}"
        text += "。别忘了哦！"

        audio_path = os.path.join(self.audio_dir, f"reminder_{int(time.time())}.wav")

        # PowerShell TTS (Windows)
        if os.name == "nt":
            try:
                safe = text.replace("'", "''")
                script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "try { $s.SelectVoice('Microsoft Huihui Desktop') } catch {}; "
                    f"$s.SetOutputToWaveFile('{audio_path}'); "
                    f"$s.Speak('{safe}'); "
                    "$s.Dispose()"
                )
                subprocess.run(["powershell","-NoProfile","-Command",script],
                    check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.getsize(audio_path) > 1000:
                    self.log(f"TTS OK (PowerShell): {os.path.getsize(audio_path)} bytes")
                    return audio_path
            except Exception as e:
                self.log(f"PowerShell TTS failed: {e}")

        self.log("TTS failed - no audio will be played")
        return ""

    def _play_audio(self, audio_path):
        """播放音频"""
        if not os.path.exists(audio_path):
            self.log(f"Audio file not found: {audio_path}")
            return
        self.log(f"Playing: {audio_path}")
        if os.name == "nt":
            try:
                import pygame
                pygame.mixer.init(frequency=22050)
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e:
                self.log(f"Playback error: {e}")

    def _send_response(self, command_id, command, status, result, error=None):
        resp = {"type": "command_response", "command_id": command_id,
                "command": command, "status": status, "result": result}
        if error:
            resp["error"] = error
        self._send(resp)
        self.log(f"Response: {command}={status}")


def main():
    parser = argparse.ArgumentParser(description="Reminder Device Simulator")
    parser.add_argument("--serial", default="AIPET-DEMO-001", help="设备序列号")
    parser.add_argument("--server", default="47.118.26.156:8000", help="服务器地址")
    args = parser.parse_args()

    host, port = args.server.split(":")
    sim = DeviceSimulator(
        serial_number=args.serial,
        server_host=host,
        server_port=int(port),
    )
    sim.start()


if __name__ == "__main__":
    main()


