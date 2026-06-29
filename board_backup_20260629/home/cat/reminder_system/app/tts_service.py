"""
TTS 服务 - 文字转语音
支持 edge-tts（中文女声）、espeak-ng、外部 API
"""
import subprocess
import os
import time
import json
import urllib.request
import threading


class TTSService:
    def __init__(self, config):
        self.config = config
        # 音频输出目录
        self.audio_dir = os.path.join(config.BASE_DIR, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        self._lock = threading.Lock()

    # ==================== 音频播放 ====================

    def _play_wav(self, wav_path):
        """播放 WAV 文件（多种播放器回退，支持重试）"""
        preferred = getattr(self.config, 'AUDIO_PLAYER', 'auto')

        # 所有候选播放器
        all_players = [
            ["aplay", "-D", self.config.AUDIO_DEVICE, wav_path],
            ["aplay", wav_path],
            ["play", wav_path],
            ["paplay", wav_path],
            ["ffplay", "-nodisp", "-autoexit", wav_path],
            ["sox", wav_path, "-d"],
            ["mplayer", "-really-quiet", "-nolirc", wav_path],
        ]

        # 如果指定了首选播放器，把它的放到最前面
        if preferred != 'auto':
            all_players.sort(key=lambda cmd: 0 if cmd[0] == preferred else 1)

        max_retries = getattr(self.config, 'AUDIO_MAX_RETRIES', 2)

        with self._lock:  # 防止同时播放多个音频
            for retry in range(max_retries + 1):
                last_error = None
                for cmd in all_players:
                    try:
                        result = subprocess.run(cmd, capture_output=True, timeout=30)
                        if result.returncode == 0:
                            return True, cmd[0]
                        else:
                            last_error = result.stderr.decode(errors='replace')[:200]
                    except FileNotFoundError:
                        last_error = f"{cmd[0]} 未安装"
                        continue
                    except subprocess.TimeoutExpired:
                        last_error = f"{cmd[0]} 超时"
                        continue

                if retry < max_retries:
                    time.sleep(0.5)

        return False, last_error or "无可用的音频播放器"

    def _play_mp3(self, mp3_path):
        """播放 MP3 文件"""
        preferred = getattr(self.config, 'AUDIO_PLAYER', 'auto')

        players = [
            ["ffplay", "-nodisp", "-autoexit", mp3_path],
            ["play", mp3_path],
            ["mplayer", "-really-quiet", "-nolirc", mp3_path],
        ]

        if preferred != 'auto':
            players.sort(key=lambda cmd: 0 if cmd[0] == preferred else 1)

        with self._lock:
            for cmd in players:
                try:
                    result = subprocess.run(cmd, capture_output=True, timeout=60)
                    if result.returncode == 0:
                        return True, cmd[0]
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            return False, "无可用 MP3 播放器"

    def _play_audio(self, filepath):
        """播放音频文件，根据扩展名选择播放器"""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".wav":
            return self._play_wav(filepath)
        elif ext == ".mp3":
            return self._play_mp3(filepath)
        return False, f"不支持的格式: {ext}"

    # ==================== edge-tts（推荐，中文效果最好） ====================

    def speak_edge(self, text):
        """使用 edge-tts 生成并播放语音（推荐，中文女声效果好）"""
        timestamp = int(time.time() * 1000)
        filename = f"reminder_{timestamp}.mp3"
        filepath = os.path.join(self.audio_dir, filename)

        edge_timeout = getattr(self.config, 'EDGE_TTS_TIMEOUT', 30)

        try:
            # 使用完整 PATH 确保能找到 ~/.local/bin/edge-tts
            env = os.environ.copy()
            env["PATH"] = env.get("PATH", "") + ":" + os.path.expanduser("~/.local/bin")
            # 使用 edge-tts 生成 MP3
            result = subprocess.run(
                ["edge-tts", "--voice", self.config.TTS_VOICE,
                 "--text", text, "--write-media", filepath],
                capture_output=True, timeout=edge_timeout, env=env
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors='replace')
                return False, f"edge-tts 生成失败: {stderr[:200]}"

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                return False, "edge-tts 生成了空文件"

            print(f"[TTS] edge-tts 生成成功: {os.path.getsize(filepath)} bytes")

            # 播放
            ok, player = self._play_audio(filepath)
            if ok:
                return True, filepath

            # 生成成功但播放失败，尝试用 ffmpeg 转 wav 再播
            wav_path = filepath.replace('.mp3', '.wav')
            try:
                subprocess.run(
                    ["ffmpeg", "-i", filepath, "-acodec", "pcm_s16le",
                     "-ar", "44100", "-ac", "1", "-y", wav_path],
                    capture_output=True, timeout=15
                )
                ok, player = self._play_wav(wav_path)
                if ok:
                    return True, wav_path
            except Exception:
                pass

            return False, f"音频已生成但播放失败"

        except FileNotFoundError:
            return False, "edge-tts 未安装 (pip install edge-tts)"
        except subprocess.TimeoutExpired:
            return False, f"edge-tts 生成超时 (>={edge_timeout}s)"
        except Exception as e:
            return False, str(e)

    # ==================== espeak-ng（离线方案，中文效果一般） ====================

    def speak_doubao(self, text):
        import subprocess as _sp
        try:
            s39 = chr(39); s92 = chr(92); s34 = chr(34)
            safe = text.replace(s34, s92+s34).replace(s39, s39+s92+s39*2)
            cmd = (
                'source /opt/ros/humble/setup.bash 2>/dev/null && '
                'source /home/cat/ros2_ws/install/setup.bash 2>/dev/null && '
                'ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak '
                + s39 + '{text: ' + s34 + safe + s34 + '}' + s39 + ' '
                '--timeout 15 2>&1'
            )
            r = _sp.run(['bash', '-c', cmd], capture_output=True, text=True, timeout=15)
            output = r.stdout + r.stderr
            if 'SUCCEEDED' in output or 'Goal accepted' in output:
                print('[TTS] Doubao TTS OK: ' + text[:30] + '...')
                return True, 'doubao_tts'
            else:
                return False, 'Doubao TTS failed: ' + output[-200:]
        except Exception as e:
            return False, 'Doubao TTS error: ' + str(e)

    def speak_espeak(self, text):
        """使用 espeak-ng 生成并播放语音（离线备选）"""
        timestamp = int(time.time() * 1000)
        filename = f"reminder_{timestamp}.wav"
        filepath = os.path.join(self.audio_dir, filename)

        try:
            # 先用 espeak-ng 生成 wav
            result = subprocess.run(
                ["espeak-ng", "-v", "zh", "-s", "150", "-w", filepath, text],
                capture_output=True, timeout=30
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors='replace')
                # 如果中文语音失败，尝试英文
                if "zh" in stderr.lower() or "voice" in stderr.lower():
                    result = subprocess.run(
                        ["espeak-ng", "-v", "en", "-s", "150", "-w", filepath, text],
                        capture_output=True, timeout=30
                    )
                    if result.returncode != 0:
                        return False, f"espeak-ng 生成失败: {result.stderr.decode(errors='replace')[:200]}"
                else:
                    return False, stderr[:200]

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                return False, "espeak-ng 生成了空文件"

            ok, player = self._play_wav(filepath)
            if ok:
                return True, filepath
            return False, f"WAV 已生成但播放失败"

        except FileNotFoundError:
            return False, "espeak-ng 未安装 (sudo apt install espeak-ng)"
        except Exception as e:
            return False, str(e)

    # ==================== 外部 API（自定义 TTS 服务） ====================

    def speak_api(self, text):
        """调用外部的 TTS HTTP API"""
        try:
            data = json.dumps({"text": text, "voice": self.config.TTS_VOICE}).encode()
            req = urllib.request.Request(
                self.config.TTS_API_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio_data = resp.read()

            if not audio_data:
                return False, "API 返回空数据"

            timestamp = int(time.time() * 1000)
            # 根据 Content-Type 判断后缀
            content_type = resp.headers.get("Content-Type", "")
            if "wav" in content_type:
                filename = f"reminder_{timestamp}.wav"
            else:
                filename = f"reminder_{timestamp}.mp3"

            filepath = os.path.join(self.audio_dir, filename)
            with open(filepath, "wb") as f:
                f.write(audio_data)

            ok, player = self._play_audio(filepath)
            if ok:
                return True, filepath
            return False, f"音频已获取但播放失败"
        except Exception as e:
            return False, str(e)

    # ==================== 统一入口 ====================

    def speak(self, text):
        """统一入口：根据配置选择 TTS 方式"""
        if not text or not text.strip():
            return False, "播报内容为空"

        text = text.strip()
        provider = self.config.TTS_PROVIDER
        preview = text[:60] + ('...' if len(text) > 60 else '')
        print(f"[TTS] 🔊 播报: \"{preview}\" (引擎: {provider})")

        if provider == "edge":
            return self.speak_edge(text)
        elif provider == "doubao":
            return self.speak_doubao(text)
        elif provider == "espeak":
            return self.speak_espeak(text)
        elif provider == "api":
            return self.speak_api(text)
        else:
            return False, f"未知 TTS provider: {provider}"

    def speak_espeak(self, text):
        """使用 espeak-ng 生成并播放语音"""
        timestamp = int(time.time())
        filename = f"reminder_{timestamp}.wav"
        filepath = os.path.join(self.audio_dir, filename)

        try:
            # 先用 espeak-ng 生成 wav
            result = subprocess.run(
                ["espeak-ng", "-v", "zh", "-w", filepath, text],
                capture_output=True, timeout=30
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors='replace')
                # 如果中文语音失败，尝试英文
                if "zh" in stderr.lower() or "voice" in stderr.lower():
                    result = subprocess.run(
                        ["espeak-ng", "-v", "en", "-w", filepath, text],
                        capture_output=True, timeout=30
                    )
                    if result.returncode != 0:
                        return False, f"espeak-ng 生成失败: {result.stderr.decode(errors='replace')}"
                else:
                    return False, stderr

            # 播放
            ok, player = self._play_wav(filepath)
            if ok:
                return True, filepath
            return False, f"WAV 已生成但播放失败 (播放器: {player})"
        except FileNotFoundError:
            return False, "espeak-ng 未安装"
        except Exception as e:
            return False, str(e)

    def speak_api(self, text):
        """调用外部的 TTS HTTP API"""
        try:
            data = json.dumps({"text": text, "voice": self.config.TTS_VOICE}).encode()
            req = urllib.request.Request(
                self.config.TTS_API_URL,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio_data = resp.read()

            timestamp = int(time.time())
            filename = f"reminder_{timestamp}.wav"
            filepath = os.path.join(self.audio_dir, filename)
            with open(filepath, "wb") as f:
                f.write(audio_data)

            ok, player = self._play_wav(filepath)
            if ok:
                return True, filepath
            return False, f"音频已获取但播放失败: {player}"
        except Exception as e:
            return False, str(e)

    def speak(self, text):
        """统一入口：根据配置选择 TTS 方式"""
        provider = self.config.TTS_PROVIDER
        print(f"[TTS] 播报: \"{text[:50]}{'...' if len(text)>50 else ''}\" (引擎: {provider})")

        if provider == "edge":
            return self.speak_edge(text)
        elif provider == "doubao":
            return self.speak_doubao(text)
        elif provider == "espeak":
            return self.speak_espeak(text)
        elif provider == "api":
            return self.speak_api(text)
        else:
            return False, f"未知 TTS provider: {provider}"

    def diagnostic(self):
        """诊断音频系统状态，返回可用的工具和问题"""
        result = {
            "tts_provider": self.config.TTS_PROVIDER,
            "audio_device": self.config.AUDIO_DEVICE,
            "tts_tools": {},
            "players": {},
            "issues": []
        }

        # 检查 TTS 引擎
        engines = {
            "espeak-ng": ["espeak-ng", "--version"],
            "edge-tts": ["edge-tts", "--version"],
        }
        for name, cmd in engines.items():
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=5)
                result["tts_tools"][name] = r.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                result["tts_tools"][name] = False

        # 检查播放器
        players = {
            "aplay": ["aplay", "--version"],
            "play": ["play", "--version"],
            "paplay": ["paplay", "--version"],
            "ffplay": ["ffplay", "-version"],
            "mplayer": ["mplayer", "-version"],
            "sox": ["sox", "--version"],
        }
        for name, cmd in players.items():
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=5)
                result["players"][name] = r.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                result["players"][name] = False

        # 检查音频设备
        try:
            r = subprocess.run(["aplay", "-l"], capture_output=True, timeout=5)
            result["aplay_devices"] = r.stdout.decode(errors='replace') if r.returncode == 0 else "N/A"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            result["aplay_devices"] = "aplay 不可用"

        # 收集问题
        if result["tts_provider"] == "espeak" and not result["tts_tools"].get("espeak-ng"):
            result["issues"].append("espeak-ng 未安装，请运行: sudo apt install espeak-ng")
        if result["tts_provider"] == "edge" and not result["tts_tools"].get("edge-tts"):
            result["issues"].append("edge-tts 未安装，请运行: pip install edge-tts")
        if not any(result["players"].values()):
            result["issues"].append("没有可用的音频播放器，请安装: sudo apt install alsa-utils sox")

        return result

    def generate_audio_file(self, text):
        """生成音频文件并返回文件路径（不播放，供 Web 浏览器下载/试听用）
        使用配置的 TTS_PROVIDER 引擎。
        返回: (filepath, None) 成功; (None, error_msg) 失败
        """
        provider = self.config.TTS_PROVIDER
        timestamp = int(time.time() * 1000)

        if provider == "edge":
            # edge-tts 生成 MP3
            filename = f"tts_{timestamp}.mp3"
            filepath = os.path.join(self.audio_dir, filename)
            env = os.environ.copy()
            env["PATH"] = env.get("PATH", "") + ":" + os.path.expanduser("~/.local/bin")
            try:
                result = subprocess.run(
                    ["edge-tts", "--voice", self.config.TTS_VOICE,
                     "--text", text, "--write-media", filepath],
                    capture_output=True, timeout=30, env=env
                )
                if result.returncode != 0 or not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    stderr = result.stderr.decode(errors='replace')
                    return None, f"edge-tts 生成失败: {stderr[:200]}"
                return filepath, None
            except FileNotFoundError:
                return None, "edge-tts 未安装"
            except subprocess.TimeoutExpired:
                return None, "edge-tts 生成超时"
            except Exception as e:
                return None, str(e)

        else:
            # espeak-ng 或其他 fallback 生成 WAV
            filename = f"tts_{timestamp}.wav"
            filepath = os.path.join(self.audio_dir, filename)
            engine = "espeak-ng"
            try:
                result = subprocess.run(
                    [engine, "-v", "zh", "-w", filepath, text],
                    capture_output=True, timeout=30
                )
                if result.returncode != 0:
                    stderr = result.stderr.decode(errors='replace')
                    if "zh" in stderr.lower() or "voice" in stderr.lower():
                        result = subprocess.run(
                            [engine, "-v", "en", "-w", filepath, text],
                            capture_output=True, timeout=30
                        )
                        if result.returncode != 0:
                            return None, f"{engine} 生成失败: {result.stderr.decode(errors='replace')[:200]}"
                    else:
                        return None, stderr[:200]
                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    return None, f"{engine} 生成了空文件"
                return filepath, None
            except FileNotFoundError:
                return None, f"{engine} 未安装"
            except Exception as e:
                return None, str(e)

    def speak_blocking(self, text):
        """阻塞式 TTS（等待播放完成）"""
        return self.speak(text)
