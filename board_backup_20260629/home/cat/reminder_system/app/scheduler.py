"""
定时调度器 - 定时检查并触发提醒
后台线程每 N 秒扫描一次数据库，到期的提醒自动 TTS 播报
"""
import threading
import time
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(self, db, tts_service, config, json_file_path=None):
        self.db = db
        self.tts = tts_service
        self.config = config
        self.json_file_path = json_file_path or config.JSON_FILE_PATH
        self._running = False
        self._thread = None
        self._last_json_check = 0
        self._json_check_interval = 60  # JSON 文件读取间隔（秒）
        self._stats = {
            "total_checks": 0,
            "reminders_triggered": 0,
            "json_imports": 0,
            "last_check_time": None,
            "last_trigger_time": None,
        }

    def get_stats(self):
        """获取调度器运行统计"""
        return {**self._stats, "running": self._running}

    def _check_json_file(self):
        """定时读取 JSON 文件（60 秒间隔）"""
        try:
            from .json_reader import parse_and_store

            if not os.path.exists(self.json_file_path):
                return

            now = time.time()
            if now - self._last_json_check < self._json_check_interval:
                return

            self._last_json_check = now
            count, msg = parse_and_store(self.db, self.json_file_path)
            if count > 0:
                self._stats["json_imports"] += 1
                print(f"   [{datetime.now().strftime('%H:%M:%S')}] JSON导入: {msg}")
        except Exception as e:
            print(f"   [WARN] JSON读取失败: {e}")

    def _check_reminders(self):
        """检查是否有到期的提醒并触发 TTS 播报"""
        try:
            reminders = self.db.get_pending_reminders()
        except Exception as e:
            print(f"   [ERROR] DB查询失败: {e}")
            return

        if not reminders:
            return

        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"   [{now_str}] 发现 {len(reminders)} 条待触发提醒")

        for reminder in reminders:
            try:
                rid = reminder["id"]
                content = reminder["content"]
                rtime = reminder.get("reminder_time", "?")

                print(f"   [{now_str}] 🚀 触发提醒 #{rid}: \"{content[:40]}...\" (预定: {rtime})")

                # TTS 播报
                success, result = self.tts.speak(content)

                if success:
                    self.db.update_reminder_status(rid, "triggered", audio_file=result)
                    self.db.log_tts(rid, content, "success", audio_file=result)
                    self._stats["reminders_triggered"] += 1
                    self._stats["last_trigger_time"] = datetime.now().isoformat()
                    print(f"   ✅ TTS 播报成功: {result}")
                else:
                    self.db.update_reminder_status(rid, "failed")
                    self.db.log_tts(rid, content, "failed", audio_file=result)
                    print(f"   ❌ TTS 播报失败: {result}")

            except Exception as e:
                rid = reminder.get('id', '?')
                print(f"   [ERROR] 处理提醒 #{rid} 异常: {e}")
                try:
                    self.db.update_reminder_status(reminder["id"], "failed")
                    self.db.log_tts(reminder["id"], reminder.get("content", ""), "failed")
                except Exception:
                    pass

    def run_once(self):
        """运行一次完整检查（供外部 API 调用）"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SCHEDULER] 手动触发检查...")
        self._stats["total_checks"] += 1
        self._stats["last_check_time"] = datetime.now().isoformat()
        self._check_json_file()
        self._check_reminders()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SCHEDULER] 检查完成")

    def _loop(self):
        """调度器后台主循环"""
        interval = getattr(self.config, 'SCHEDULER_INTERVAL', 30)
        print(f"🚀 [SCHEDULER] 后台调度器启动 (检查间隔: {interval}s)")

        # 启动时立即执行一次
        try:
            self.run_once()
        except Exception as e:
            print(f"   [SCHEDULER] 首次执行异常: {e}")

        while self._running:
            time.sleep(interval)
            try:
                self._stats["total_checks"] += 1
                self._stats["last_check_time"] = datetime.now().isoformat()
                self._check_json_file()
                self._check_reminders()
            except Exception as e:
                print(f"   [SCHEDULER LOOP ERROR] {e}")

        print("[SCHEDULER] 调度器已停止")

    def start(self):
        """启动调度器（后台 daemon 线程）"""
        if self._running:
            print("[SCHEDULER] 调度器已在运行")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()
        print("[SCHEDULER] 后台调度线程已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        print("[SCHEDULER] 调度器停止信号已发送")

    def is_running(self):
        """调度器是否在运行"""
        return self._running
