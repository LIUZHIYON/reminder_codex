import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Kill robot_websocket node
c.exec_command("pkill -f websocket_node 2>/dev/null; pkill -f board_ws_client 2>/dev/null", timeout=5)
time.sleep(1)

# Start board_ws_client (the one we know works)
c.exec_command("setsid python3 /home/cat/reminder_system/board_ws_client.py >> /home/cat/reminder_system/logs/ws_client.log 2>&1 &", timeout=5)
time.sleep(2)

# Check if running
stdin, stdout, stderr = c.exec_command("ps aux | grep board_ws_client | grep -v grep", timeout=5)
proc = stdout.read().decode().strip()
print("Running:", proc[:100] if proc else "NO")

# Check log
stdin, stdout, stderr = c.exec_command("tail -10 /home/cat/reminder_system/logs/ws_client.log 2>/dev/null", timeout=5)
print("Log:", stdout.read().decode()[:400])

c.close()
