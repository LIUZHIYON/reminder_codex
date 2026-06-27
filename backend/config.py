import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
DATABASE_PATH = os.path.join(BASE_DIR, "reminders.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

TTS_VOICE = "zh-CN-XiaoyiNeural"
TTS_RATE = "+15%"
TTS_VOLUME = "+30%"
SCHEDULER_INTERVAL = 5
HOST = "0.0.0.0"
PORT = 8000
