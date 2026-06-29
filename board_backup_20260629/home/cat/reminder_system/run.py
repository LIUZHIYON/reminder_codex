"""
提醒系统 v1.1 - 主入口
定时提醒 + TTS 语音播报 + Web 管理面板
"""
import sys
import os

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config as cfg
from app.models import ReminderDB
from app.tts_service import TTSService
from app.scheduler import ReminderScheduler
from app.web_app import create_web_app


def print_banner():
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║       🐱 提醒系统 v1.1               ║")
    print("  ║    定时提醒 · TTS 语音播报            ║")
    print("  ╚══════════════════════════════════════╝")
    print()


def main():
    print_banner()

    # 初始化数据库
    db = ReminderDB(cfg.DB_PATH)
    print(f"  📦 DB:     {cfg.DB_PATH}")

    # 初始化 TTS
    tts = TTSService(cfg)
    print(f"  🔊 TTS:    {cfg.TTS_PROVIDER} | 语音: {cfg.TTS_VOICE}")

    # 初始化音频音量
    if hasattr(cfg, 'INIT_VOLUME_ON_STARTUP') and cfg.INIT_VOLUME_ON_STARTUP:
        import subprocess
        for cmd, desc in getattr(cfg, 'VOLUME_INIT_CMDS', []):
            try:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                print(f"  🔈 音频:   {desc}")
            except Exception as e:
                print(f"  ⚠️  音频{desc}失败: {e}")

    # 初始化调度器
    scheduler = ReminderScheduler(db, tts, cfg)
    scheduler.start()

    # 启动 Web 服务
    app = create_web_app(db, scheduler, tts, cfg)
    url = f"http://{cfg.BOARD_IP}:{cfg.WEB_PORT}"
    print(f"  🌐 Web:    {url}")
    print()

    # 启动 Flask
    app.run(
        host=cfg.WEB_HOST,
        port=cfg.WEB_PORT,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  👋 提醒系统已停止")
    except Exception as e:
        print(f"\n  ❌ 启动失败: {e}")
        sys.exit(1)
