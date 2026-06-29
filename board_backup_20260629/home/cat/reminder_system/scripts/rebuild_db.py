#!/usr/bin/env python3
"""
板子上运行的修复脚本 - 重建数据库 + 清理缓存
"""
import sqlite3, os, sys

db_path = "/home/cat/reminder_system/data/reminders.db"
bak_path = db_path + ".bak"

# 检查旧数据库
if os.path.exists(bak_path):
    os.remove(bak_path)
if not os.path.exists(db_path):
    print("数据库不存在，退出")
    sys.exit(0)

# 检查是否有触发器/视图残留
conn = sqlite3.connect(db_path)
triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall()
views = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='view'").fetchall()
print("触发器:", triggers if triggers else "无")
print("视图:", views if views else "无")
conn.close()

# 备份
os.rename(db_path, bak_path)
print("已备份到:", bak_path)

# 重建
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
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

    CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
    CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_sendtime ON chat_messages(send_time);
""")
print("新表已创建")

# 恢复数据
old = sqlite3.connect(bak_path)

# chat_messages
try:
    msgs = old.execute("SELECT * FROM chat_messages").fetchall()
    if msgs:
        cols = [d[0] for d in old.execute("PRAGMA table_info(chat_messages)").fetchall()]
        ph = ",".join(["?"] * len(cols))
        for m in msgs:
            conn.execute("INSERT OR IGNORE INTO chat_messages VALUES (%s)" % ph, m)
    print("恢复 chat_messages:", len(msgs))
except Exception as e:
    print("chat_messages 恢复失败:", e)

# reminders
try:
    rows = old.execute("SELECT * FROM reminders").fetchall()
    if rows:
        cols = [d[0] for d in old.execute("PRAGMA table_info(reminders)").fetchall()]
        ph = ",".join(["?"] * len(cols))
        for r in rows:
            conn.execute("INSERT OR IGNORE INTO reminders VALUES (%s)" % ph, r)
    print("恢复 reminders:", len(rows))
except Exception as e:
    print("reminders 恢复失败:", e)

# tts_log
try:
    logs = old.execute("SELECT * FROM tts_log").fetchall()
    if logs:
        cols = [d[0] for d in old.execute("PRAGMA table_info(tts_log)").fetchall()]
        ph = ",".join(["?"] * len(cols))
        for l in logs:
            conn.execute("INSERT OR IGNORE INTO tts_log VALUES (%s)" % ph, l)
    print("恢复 tts_log:", len(logs))
except Exception as e:
    print("tts_log 恢复失败:", e)

conn.commit()
conn.close()
old.close()

# 验证
conn = sqlite3.connect(db_path)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("当前表:", tables)
triggers2 = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
print("触发器数:", triggers2)
print("提醒数:", conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0])
conn.close()
print("重建完成!")
