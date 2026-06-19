import paramiko, os, time

host = "192.168.1.40"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username="cat", password="temppwd", timeout=10)

# Check if websocket-client is installed
stdin, stdout, stderr = client.exec_command("python3 -c \"import websocket; print(websocket.__version__)\" 2>/dev/null || echo NOT_INSTALLED")
result = stdout.read().decode().strip()
print(f"websocket-client: {result}")

# Copy the WS client script
local_path = "C:/Users/29503/Desktop/reminder_codex/robot_reminder/board_ws_client.py"
sftp = client.open_sftp()
sftp.put(local_path, "/home/cat/reminder_system/board_ws_client.py")
sftp.close()
print("Copied board_ws_client.py")

# Also copy a wrapper service script
service_script = """#!/bin/bash
cd /home/cat/reminder_system
while true; do
    python3 board_ws_client.py >> /home/cat/reminder_system/logs/ws_client.log 2>&1
    sleep 5
done
"""
sftp = client.open_sftp()
with sftp.open("/home/cat/reminder_system/start_ws_client.sh", "w") as f:
    f.write(service_script)
sftp.close()
client.exec_command("chmod +x /home/cat/reminder_system/start_ws_client.sh")
print("Created start script")

# Kill old run.py and start WS client + original run.py
print("Stopping old process...")
client.exec_command("pkill -f run.py 2>/dev/null; sleep 1")

# Start WS client in background
stdin, stdout, stderr = client.exec_command("cd /home/cat/reminder_system && nohup python3 board_ws_client.py >> logs/ws_client.log 2>&1 &")
time.sleep(1)
print(f"WS client stdout: {stdout.read().decode()[:100]}")
print(f"WS client stderr: {stderr.read().decode()[:100]}")

# Also restart original run.py (Flask app + scheduler)
stdin, stdout, stderr = client.exec_command("cd /home/cat/reminder_system && nohup python3 run.py >> logs/run.log 2>&1 &")

# Check processes
time.sleep(2)
stdin, stdout, stderr = client.exec_command("ps aux | grep -E \"python.*reminder_system\" | grep -v grep")
print(f"Running processes:\\n{stdout.read().decode()[:500]}")

client.close()
print("Done")
