#!/usr/bin/env python3
"""
去重提醒脚本
在板子上直接运行：python3 scripts/dedup_reminders.py
"""
import sqlite3

db_path = "/home/cat/reminder_system/data/reminders.db"
conn = sqlite3.connect(db_path)

before = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
print("去重前提醒数:", before)

# 去重
conn.execute("""
    DELETE FROM reminders WHERE id NOT IN (
        SELECT MIN(id) FROM reminders GROUP BY message_id, content, reminder_time
    )
""")
print("删除重复数:", conn.total_changes)

after = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
print("去重后提醒数:", after)

# 重建表增加 UNIQUE 约束
rows = conn.execute("SELECT * FROM reminders").fetchall()

conn.executescript("DROP TABLE IF EXISTS reminders_old")
conn.executescript("ALTER TABLE reminders RENAME TO reminders_old")
conn.executescript("""
    CREATE TABLE reminders (
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
    CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
    CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time);
""")

for r in rows:
    conn.execute("""
        INSERT OR IGNORE INTO reminders (id, message_id, content, reminder_time, status, triggered_at, audio_file, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, r)

conn.execute("DROP TABLE IF EXISTS reminders_old")
conn.commit()
final = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
print("重建后提醒数:", final)

stats = conn.execute("SELECT status, COUNT(*) FROM reminders GROUP BY status").fetchall()
for s, c in stats:
    print("  {}: {}".format(s, c))

conn.close()
print("去重完成!")
