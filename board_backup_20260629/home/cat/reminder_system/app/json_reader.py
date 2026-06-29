"""
JSON 聊天记录读取与解析模块
"""
import json
import os
import re
from datetime import datetime


def parse_reminder_time(params):
    """从 commandParams 中解析提醒时间"""
    if not params:
        return None

    reminder_data = params.get("reminder_data", params)

    # 可能的字段名
    time_fields = ["remindTime", "remind_time", "time", "timestamp", "at"]
    for field in time_fields:
        val = reminder_data.get(field)
        if val:
            # 如果是时间戳（秒级）
            if isinstance(val, (int, float)) and val > 946684800:
                return datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M:%S")
            # 如果是 ISO 格式
            if isinstance(val, str):
                try:
                    # 尝试标准 ISO 格式
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    pass
            # 直接返回字符串
            if isinstance(val, str):
                return val.replace("T", " ")[:19]

    return None


def read_json_file(filepath):
    """读取 JSON 文件"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_and_store(db, filepath):
    """解析 JSON 文件并将数据存入数据库"""
    data = read_json_file(filepath)
    if not data or not data.get("success"):
        return 0, "文件不存在或格式错误"

    rows = data.get("data", {}).get("rows", [])
    if not rows:
        return 0, "没有数据行"

    inserted = 0
    reminders_created = 0

    for row in rows:
        # 先插入聊天记录
        db.insert_chat_message(row)

        # 如果是 reminder 类型，额外创建提醒
        command_type = row.get("commandType", "")
        if command_type == "reminder":
            params = row.get("commandParams", {})
            reminder_time = parse_reminder_time(params)
            content = row.get("content", "")

            if reminder_time and content:
                db.insert_reminder(
                    message_id=row["id"],
                    content=content,
                    reminder_time=reminder_time
                )
                reminders_created += 1

        inserted += 1

    return inserted, f"已导入 {inserted} 条记录，创建 {reminders_created} 条提醒"
