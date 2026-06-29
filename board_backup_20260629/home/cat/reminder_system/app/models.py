"""
数据库模型 - SQLite
"""
import sqlite3
import json
import os
from datetime import datetime


class ReminderDB:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY,
                    pet_id INTEGER,
                    user_id INTEGER,
                    message_type TEXT,
                    command_type TEXT,
                    content TEXT,
                    command_params TEXT,
                    sender_type INTEGER,
                    send_time TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    content TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    triggered_at TEXT,
                    audio_file TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (message_id) REFERENCES chat_messages(id),
                    UNIQUE(message_id, content, reminder_time)
                );

                CREATE TABLE IF NOT EXISTS tts_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_id INTEGER,
                    content TEXT,
                    status TEXT,
                    audio_file TEXT,
                    duration_ms INTEGER,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (reminder_id) REFERENCES reminders(id)
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
                CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_sendtime ON chat_messages(send_time);
            """)
            conn.commit()
        finally:
            conn.close()

    def insert_chat_message(self, row):
        """插入一条聊天记录"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO chat_messages
                (id, pet_id, user_id, message_type, command_type, content,
                 command_params, sender_type, send_time, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("id"),
                row.get("petId"),
                row.get("userId"),
                row.get("messageType"),
                row.get("commandType"),
                row.get("content"),
                json.dumps(row.get("commandParams", {}), ensure_ascii=False),
                row.get("senderType"),
                row.get("sendTime"),
                row.get("isRead", 0)
            ))
            conn.commit()
        finally:
            conn.close()

    def insert_reminder(self, message_id, content, reminder_time):
        """插入一条提醒任务（自动去重）"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO reminders (message_id, content, reminder_time)
                VALUES (?, ?, ?)
            """, (message_id, content, reminder_time))
            conn.commit()
        finally:
            conn.close()

    def dedup_reminders(self):
        """清理重复提醒"""
        conn = self._get_conn()
        try:
            conn.execute("""
                DELETE FROM reminders WHERE id NOT IN (
                    SELECT MIN(id) FROM reminders GROUP BY message_id, content, reminder_time
                )
            """)
            conn.commit()
            return conn.total_changes
        finally:
            conn.close()

    def get_pending_reminders(self):
        """获取待触发的提醒"""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM reminders
                WHERE status = 'pending'
                AND reminder_time <= datetime('now', 'localtime')
                ORDER BY reminder_time ASC
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_reminder_status(self, reminder_id, status, audio_file=None):
        """更新提醒状态"""
        conn = self._get_conn()
        try:
            if audio_file:
                conn.execute("""
                    UPDATE reminders SET status=?, triggered_at=datetime('now','localtime'), audio_file=?
                    WHERE id=?
                """, (status, audio_file, reminder_id))
            else:
                conn.execute("""
                    UPDATE reminders SET status=?, triggered_at=datetime('now','localtime')
                    WHERE id=?
                """, (status, reminder_id))
            conn.commit()
        finally:
            conn.close()

    def log_tts(self, reminder_id, content, status, audio_file=None, duration_ms=None):
        """记录TTS日志"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO tts_log (reminder_id, content, status, audio_file, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (reminder_id, content, status, audio_file, duration_ms))
            conn.commit()
        finally:
            conn.close()

    def get_reminders(self, limit=50, offset=0, status=None):
        """获取提醒列表（带分页）"""
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute("""
                    SELECT r.*, c.content as original_content, c.send_time
                    FROM reminders r
                    LEFT JOIN chat_messages c ON r.message_id = c.id
                    WHERE r.status = ?
                    ORDER BY r.created_at DESC
                    LIMIT ? OFFSET ?
                """, (status, limit, offset)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT r.*, c.content as original_content, c.send_time
                    FROM reminders r
                    LEFT JOIN chat_messages c ON r.message_id = c.id
                    ORDER BY r.created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_chat_messages(self, limit=50, offset=0):
        """获取聊天记录列表"""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM chat_messages
                ORDER BY send_time DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_tts_logs(self, limit=50, offset=0):
        """获取TTS日志"""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM tts_log
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self):
        """获取统计信息"""
        conn = self._get_conn()
        try:
            stats = {}
            stats["total_reminders"] = conn.execute("SELECT COUNT(*) as c FROM reminders").fetchone()["c"]
            stats["pending"] = conn.execute("SELECT COUNT(*) as c FROM reminders WHERE status='pending'").fetchone()["c"]
            stats["triggered"] = conn.execute("SELECT COUNT(*) as c FROM reminders WHERE status='triggered'").fetchone()["c"]
            stats["failed"] = conn.execute("SELECT COUNT(*) as c FROM reminders WHERE status='failed'").fetchone()["c"]
            stats["total_messages"] = conn.execute("SELECT COUNT(*) as c FROM chat_messages").fetchone()["c"]
            stats["tts_count"] = conn.execute("SELECT COUNT(*) as c FROM tts_log").fetchone()["c"]
            # 下一次提醒
            next_r = conn.execute("""
                SELECT content, reminder_time FROM reminders
                WHERE status='pending'
                ORDER BY reminder_time ASC LIMIT 1
            """).fetchone()
            stats["next_reminder"] = dict(next_r) if next_r else None
            return stats
        finally:
            conn.close()

    def delete_reminder(self, reminder_id):
        """删除一条提醒"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def add_reminder(self, content, reminder_time):
        """手动添加提醒（自动去重）"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO reminders (content, reminder_time)
                VALUES (?, ?)
            """, (content, reminder_time))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_reminder_by_id(self, reminder_id):
        """根据 ID 获取单条提醒"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?", (reminder_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_reminder(self, reminder_id, content=None, reminder_time=None):
        """更新提醒的内容和/或时间（仅允许 pending 状态的提醒）"""
        conn = self._get_conn()
        try:
            # 先获取当前记录
            existing = conn.execute(
                "SELECT * FROM reminders WHERE id=? AND status='pending'",
                (reminder_id,)
            ).fetchone()
            if not existing:
                return False, "提醒不存在或已触发，无法修改"

            new_content = content if content else existing["content"]
            new_time = reminder_time if reminder_time else existing["reminder_time"]

            # 检查是否与现有 pending 提醒冲突（去重）
            dup = conn.execute("""
                SELECT id FROM reminders
                WHERE content=? AND reminder_time=? AND status='pending' AND id!=?
            """, (new_content, new_time, reminder_id)).fetchone()
            if dup:
                return False, "已存在相同内容和时间的提醒"

            conn.execute("""
                UPDATE reminders SET content=?, reminder_time=?
                WHERE id=?
            """, (new_content, new_time, reminder_id))
            conn.commit()
            return True, "更新成功"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def count_reminders_by_status(self):
        """按状态统计"""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM reminders GROUP BY status
            """).fetchall()
            return {r["status"]: r["count"] for r in rows}
        finally:
            conn.close()
