"""
提醒系统 - 配置
"""
import os

# 板子上的项目路径
BASE_DIR = "/home/cat/reminder_system"

# 板子 IP 地址
BOARD_IP = "192.168.1.39"
BOARD_USER = "cat"
BOARD_PASS = "temppwd"

# SQLite 数据库路径
DB_PATH = os.path.join(BASE_DIR, "data", "reminders.db")

# JSON 文件路径（定时读取的聊天记录）
JSON_FILE_PATH = os.path.join(BASE_DIR, "data", "chat_logs.json")

# Flask 服务端口
WEB_PORT = 5000
WEB_HOST = "0.0.0.0"

# TTS 配置
TTS_PROVIDER = "doubao"  # edge | espeak | api
TTS_API_URL = "http://localhost:9880/tts"  # 如果使用外部 TTS API
TTS_VOICE = "zh-CN-XiaoxiaoNeural"  # edge-tts 中文女声（晓晓）

# 调度器间隔（秒）
SCHEDULER_INTERVAL = 30

# 音频播放设备
AUDIO_DEVICE = "default"  # 使用 aplay 或 pulseaudio
# 如果没有声音，尝试以下值:
#   "hw:0,0"  - 直接硬件设备0
#   "plughw:0,0" - 插件方式
#   "pulse"   - PulseAudio
#   在板子上运行 `aplay -l` 查看可用设备

# 音频播放设置
AUDIO_MAX_RETRIES = 2
AUDIO_PLAYER = "auto"  # auto | aplay | paplay | ffplay | mplayer

# edge-tts 超时（秒）
EDGE_TTS_TIMEOUT = 30

# 板子音频初始化命令（启动时执行）
# 用于设置音量、开启扬声器等
VOLUME_INIT_CMDS = [
    ("amixer sset 'spk switch' on", "开启扬声器"),
    ("amixer sset 'aw_dev_0_rx_volume' 818", "设置音量80%"),
] 

# TTS 播报时是否先初始化音量
INIT_VOLUME_ON_STARTUP = True
