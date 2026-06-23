import re
content = open("C:/Users/29503/Desktop/reminder_codex/robot_websocket/robot_websocket/websocket_client.py", "r", encoding="utf-8").read()
for m in re.finditer(r"(ws|wss|http)[^\042\047\040\011]*", content):
    print(m.group())
