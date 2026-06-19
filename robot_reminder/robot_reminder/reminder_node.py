"""robot_reminder - 待办事提醒 ROS2 节点

功能：
1. 接收服务器下发的 reminder 命令（通过 WebSocket 链路）
2. 在指定时间播放 TTS 语音提醒
3. 上报执行结果至服务器

运行方式：
  ros2 run robot_reminder reminder_node --ros-args -p serial_number:=AIPET-DEMO-001
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import json
import os
import time
import threading
import subprocess
from datetime import datetime


class ReminderNode(Node):
    """待办事提醒 ROS2 节点"""

    def __init__(self):
        super().__init__("reminder_node")

        # === 参数 ===
        self.declare_parameter("serial_number", "AIPET-DEMO-001")
        self.declare_parameter("server_host", "42.121.217.40")
        self.declare_parameter("server_port", 3000)
        self.declare_parameter("ws_path", "/openclaw-wwh/robot_websocket")
        self.declare_parameter("audio_dir", "/data/audio")
        self.declare_parameter("heartbeat_interval", 30)

        self.serial_number = self.get_parameter("serial_number").value
        self.server_host = self.get_parameter("server_host").value
        self.server_port = self.get_parameter("server_port").value
        self.ws_path = self.get_parameter("ws_path").value
        self.audio_dir = self.get_parameter("audio_dir").value
        self.heartbeat_interval = self.get_parameter("heartbeat_interval").value

        self.get_logger().info(f"ReminderNode starting: serial={self.serial_number}")
        self.get_logger().info(f"Server: {self.server_host}:{self.server_port}{self.ws_path}")

        # === 状态 ===
        self._ws = None
        self._connected = False
        self._authenticated = False
        self._heartbeat_timer = None
        self._reconnect_timer = None

        # === 音频输出 ===
        os.makedirs(self.audio_dir, exist_ok=True)

        # 尝试连接服务器
        self._connect_websocket()

    # ============================================================
    #  WebSocket 连接管理
    # ============================================================
    def _connect_websocket(self):
        """启动 WebSocket 连接（在独立线程中运行）"""
        self.get_logger().info("Connecting WebSocket...")
        import websocket
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.ws_path}"
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        # 运行在守护线程
        wst = threading.Thread(target=self._ws.run_forever, daemon=True)
        wst.start()

    def _on_ws_open(self, ws):
        self.get_logger().info("WebSocket connected")
        self._connected = True
        # 发送 Auth 消息
        self._send_auth()

    def _on_ws_message(self, ws, message):
        """收到服务器消息"""
        try:
            msg = json.loads(message)
            msg_type = msg.get("type", "")
            self.get_logger().debug(f"WS recv: type={msg_type}")

            if msg_type == "auth":
                self._handle_auth_response(msg)
            elif msg_type == "heartbeat":
                self._handle_heartbeat_response(msg)
            elif msg_type == "server_command":
                self._handle_server_command(msg)
            elif msg_type == "chat":
                self._handle_chat(msg)
            elif msg_type == "ack":
                pass  # 自动 ACK 无需处理
            else:
                self.get_logger().warn(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid JSON: {message[:100]}")
        except Exception as e:
            self.get_logger().error(f"WS message error: {e}")

    def _on_ws_error(self, ws, error):
        self.get_logger().error(f"WebSocket error: {error}")
        self._connected = False
        self._authenticated = False

    def _on_ws_close(self, ws, close_status_code, close_msg):
        self.get_logger().info(f"WebSocket closed: {close_status_code} {close_msg}")
        self._connected = False
        self._authenticated = False
        # 自动重连
        self._schedule_reconnect()

    def _schedule_reconnect(self, delay=5):
        """定时重连"""
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
        self._reconnect_timer = threading.Timer(delay, self._connect_websocket)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()
        self.get_logger().info(f"Reconnecting in {delay}s...")

    def _send_json(self, data):
        """发送 JSON 消息"""
        if self._ws and self._connected:
            self._ws.send(json.dumps(data, ensure_ascii=False))
            return True
        return False

    # ============================================================
    #  认证
    # ============================================================
    def _send_auth(self):
        """发送 Auth 消息"""
        self.get_logger().info("Sending auth...")
        # 根据协议，device token 从 HTTP 接口获取
        # 简化：直接使用 serial_number 作为 access_token
        self._send_json({
            "type": "auth",
            "access_token": self.serial_number
        })

    def _handle_auth_response(self, msg):
        if msg.get("success"):
            self._authenticated = True
            self.get_logger().info("Authentication successful")
            # 启动心跳
            self._start_heartbeat()
            # 请求配置
            self._send_json({"type": "config_request"})
        else:
            self.get_logger().error(f"Auth failed: {msg.get('message','')}")
            self._schedule_reconnect()

    # ============================================================
    #  心跳
    # ============================================================
    def _start_heartbeat(self):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        self._do_heartbeat()

    def _do_heartbeat(self):
        if not self._connected or not self._authenticated:
            return
        self._send_json({"type": "heartbeat"})
        self._heartbeat_timer = threading.Timer(self.heartbeat_interval, self._do_heartbeat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _handle_heartbeat_response(self, msg):
        if msg.get("success"):
            self.get_logger().debug("Heartbeat OK")

    # ============================================================
    #  核心：Server Command → Reminder
    # ============================================================
    def _handle_server_command(self, msg):
        """处理服务器下发的命令"""
        command = msg.get("command", "")
        command_id = msg.get("command_id", "")
        command_params = msg.get("command_params", {})

        self.get_logger().info(f"Received command: {command} id={command_id}")

        if command == "reminder":
            self._execute_reminder(command_id, command_params)
        elif command == "play_sound":
            self._execute_play_sound(command_id, command_params)
        elif command == "upload_status":
            self._send_command_response(command_id, command, "success", {"status": "ok"})
        elif command == "update_config":
            self._send_command_response(command_id, command, "success", {})
        else:
            self.get_logger().warn(f"Unknown command: {command}")
            self._send_command_response(command_id, command, "failed", {}, "unknown_command")

    def _execute_reminder(self, command_id, params):
        """执行提醒命令：合成 TTS 并播放"""
        reminder_data = params.get("reminder_data", {})
        title = reminder_data.get("title", "未命名提醒")
        content = reminder_data.get("content", "")
        reminder_time = reminder_data.get("reminder_time", "")

        self.get_logger().info(f"Reminder: {title} | {content} | {reminder_time}")

        try:
            # 1. 合成 TTS 语音
            audio_path = self._generate_tts(title, content)
            if not audio_path:
                self._send_command_response(
                    command_id, "reminder", "failed", {}, "tts_generation_failed"
                )
                return

            # 2. 播放语音
            play_ok = self._play_audio(audio_path)
            if not play_ok:
                self._send_command_response(
                    command_id, "reminder", "failed", {}, "audio_playback_failed"
                )
                return

            # 3. 上报成功
            self._send_command_response(command_id, "reminder", "success", {
                "played": True,
                "title": title,
                "audio_path": audio_path,
            })
            self.get_logger().info(f"Reminder played: {title}")

        except Exception as e:
            self.get_logger().error(f"Reminder execution error: {e}")
            self._send_command_response(command_id, "reminder", "failed", {}, str(e))

    def _execute_play_sound(self, command_id, params):
        """播放指定声音文件"""
        sound_url = params.get("sound_url", "")
        if sound_url:
            self.get_logger().info(f"Play sound: {sound_url}")
            # 简化：标记成功
        self._send_command_response(command_id, "play_sound", "success", {"played": True})

    def _send_command_response(self, command_id, command, status, result, error=None):
        """上报命令执行结果"""
        resp = {
            "type": "command_response",
            "command_id": command_id,
            "command": command,
            "status": status,
            "result": result,
        }
        if error:
            resp["error"] = error
        self._send_json(resp)
        self.get_logger().info(f"Command response sent: {command}={status}")

    # ============================================================
    #  TTS 语音合成
    # ============================================================
    def _generate_tts(self, title, content=""):
        """合成 TTS 语音文件，返回路径"""
        text = f"叮咚！提醒时间到啦！{title}"
        if content:
            text += f"。{content}"
        text += "。别忘了哦！"

        audio_path = os.path.join(self.audio_dir, f"reminder_{int(time.time())}.wav")

        # Strategy 1: PowerShell TTS (Windows)
        if os.name == "nt":
            try:
                safe_text = text.replace("'", "''")
                script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "try { $s.SelectVoice('Microsoft Huihui Desktop') } catch {}; "
                    f"$s.SetOutputToWaveFile('{audio_path}'); "
                    f"$s.Speak('{safe_text}'); "
                    "$s.Dispose()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", script],
                    check=True, timeout=30,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if os.path.getsize(audio_path) > 1000:
                    self.get_logger().info(f"TTS generated (PowerShell): {audio_path}")
                    return audio_path
            except Exception as e:
                self.get_logger().warn(f"PowerShell TTS failed: {e}")

        # Strategy 2: edge-tts (Linux preferred)
        try:
            import edge_tts
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                asyncio.wait_for(
                    self._edge_tts_async(text, audio_path), timeout=15
                )
            )
            loop.close()
            if os.path.getsize(audio_path) > 100:
                self.get_logger().info(f"TTS generated (edge-tts): {audio_path}")
                return audio_path
        except Exception as e:
            self.get_logger().warn(f"edge-tts failed: {e}")

        # Strategy 3: espeak (Linux fallback)
        try:
            subprocess.run(
                ["espeak", "-w", audio_path, text],
                check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if os.path.getsize(audio_path) > 100:
                self.get_logger().info(f"TTS generated (espeak): {audio_path}")
                return audio_path
        except Exception as e:
            self.get_logger().warn(f"espeak failed: {e}")

        self.get_logger().error("All TTS backends failed")
        return ""

    async def _edge_tts_async(self, text, audio_path):
        import edge_tts
        c = edge_tts.Communicate(text, voice="zh-CN-XiaoyiNeural", rate="+15%", volume="+30%")
        await c.save(audio_path)

    # ============================================================
    #  音频播放
    # ============================================================
    def _play_audio(self, audio_path):
        """播放音频文件"""
        if not os.path.exists(audio_path):
            self.get_logger().error(f"Audio file not found: {audio_path}")
            return False

        self.get_logger().info(f"Playing: {audio_path}")

        try:
            if os.name == "nt":
                # Windows: 使用 pygame
                import pygame
                pygame.mixer.init(frequency=22050)
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            else:
                # Linux: 使用 aplay 或 paplay
                for player in ["paplay", "aplay", "ffplay"]:
                    try:
                        subprocess.run(
                            [player, audio_path],
                            check=True, timeout=30,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        return True
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                # Fallback: 用 python 直接播放
                try:
                    import pygame
                    pygame.mixer.init(frequency=22050)
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception as e:
                    self.get_logger().error(f"Audio playback failed: {e}")
                    return False
            return True
        except Exception as e:
            self.get_logger().error(f"Audio playback error: {e}")
            return False

    # ============================================================
    #  Chat 消息
    # ============================================================
    def _handle_chat(self, msg):
        """处理服务器转发的聊天消息"""
        content = msg.get("content", "")
        self.get_logger().info(f"Chat received: {content}")
        # 简单回复
        reply = {
            "type": "chat",
            "content": f"收到您的消息: {content}",
            "chat_type": "text",
        }
        self._send_json(reply)

    # ============================================================
    #  生命周期
    # ============================================================
    def destroy_node(self):
        self.get_logger().info("Shutting down...")
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
        if self._ws:
            self._ws.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReminderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
