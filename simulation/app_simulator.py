#!/usr/bin/env python3
"""模拟 APP - 通过 HTTP API 下发提醒命令

用法:
  python app_simulator.py --login 13800138000
  python app_simulator.py --reminder "喝水提醒" --time "2026-06-20T10:00:00"
  python app_simulator.py --list-reminders
  python app_simulator.py --delete-reminder 1
"""

import requests
import json
import sys
import argparse
from datetime import datetime


API_BASE = "http://47.118.26.156:8000/api/v1"
TOKEN = None
AIPET_ID = None


def api(path, method="GET", data=None, need_auth=True):
    """发送 HTTP API 请求"""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if need_auth and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    resp = requests.request(method, url, headers=headers, json=data, timeout=10)
    result = resp.json()
    if not result.get("success", False):
        print(f"[API Error] {result.get('msg', 'unknown')}")
        return None
    return result.get("data")


def cmd_login(phone):
    """手机号验证码登录（验证码固定 888888）"""
    global TOKEN
    print(f"Logging in with phone: {phone}")
    result = api(f"/aipet/app/auth/{phone}/888888", need_auth=False)
    if result:
        TOKEN = result if isinstance(result, str) else result.get("token")
        print(f"Login success. Token: {TOKEN[:20]}...")
        # 获取我的宠物列表
        pets = api("/aipet/app/myaipets")
        if pets and len(pets) > 0:
            global AIPET_ID
            AIPET_ID = pets[0].get("id") or pets[0].get("petId")
            print(f"Pet ID: {AIPET_ID}")
    return bool(TOKEN)


def cmd_send_reminder(title, reminder_time, content="", repeat_type=""):
    """通过 HTTP API 下发提醒命令"""
    if not AIPET_ID:
        print("Error: No pet bound. Please login first.")
        return

    print(f"Sending reminder: {title} @ {reminder_time}")
    data = {
        "commandParams": {
            "reminder_data": {
                "title": title,
                "content": content,
                "reminder_time": reminder_time,
                "repeat_type": repeat_type,
            }
        },
    }
    result = api(f"/aipet/app/command/{AIPET_ID}/reminder", method="POST", data=data)
    if result:
        print(f"Reminder sent! command_id={result.get('commandId', '?')}")
    return result


def cmd_list_reminders():
    """列出待办提醒"""
    result = api(f"/aipet/app/command/pending/{AIPET_ID}" if AIPET_ID else None)
    if result:
        pending = result.get("pendingCommands", [])
        print(f"Pending commands: {len(pending)}")
        for cmd in pending:
            print(f"  [{cmd.get('command')}] id={cmd.get('commandId','')}")
    return result


def cmd_command_history():
    """查询命令历史"""
    result = api(f"/aipet/app/command/history/{AIPET_ID}?limit=10")
    if result:
        history = result.get("history", [])
        print(f"Command history: {len(history)}")
        for h in history:
            print(f"  [{h.get('command')}] {h.get('status')} @ {h.get('created_at','')}")


def main():
    parser = argparse.ArgumentParser(description="Reminder APP Simulator")
    parser.add_argument("--login", help="手机号登录")
    parser.add_argument("--reminder", help="发送提醒命令（标题）")
    parser.add_argument("--time", help="提醒时间 ISO 格式")
    parser.add_argument("--content", help="提醒内容", default="")
    parser.add_argument("--repeat", help="重复类型: daily/weekly/monthly", default="")
    parser.add_argument("--list", action="store_true", help="列出待处理命令")
    parser.add_argument("--history", action="store_true", help="查询命令历史")
    parser.add_argument("--bind", help="绑定宠物 serial_number")

    args = parser.parse_args()

    if args.login:
        if not cmd_login(args.login):
            sys.exit(1)

    if args.bind and AIPET_ID is None and TOKEN:
        result = api(f"/aipet/app/bind/{args.bind}")
        if result:
            global AIPET_ID
            AIPET_ID = result.get("id") or result.get("petId")
            print(f"Bound pet: {AIPET_ID}")

    if args.reminder:
        t = args.time or datetime.now().isoformat()
        cmd_send_reminder(args.reminder, t, args.content, args.repeat)

    if args.list:
        cmd_list_reminders()

    if args.history:
        cmd_command_history()

    if not any([args.login, args.reminder, args.list, args.history, args.bind]):
        parser.print_help()


if __name__ == "__main__":
    main()

