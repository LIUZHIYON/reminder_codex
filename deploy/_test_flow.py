import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Update config on board to use our server
script = """import yaml
with open('/home/cat/ros2_ws/src/robot_websocket/config/websocket_config.yaml', 'r') as f:
    data = yaml.safe_load(f)
data['base_url'] = 'http://47.118.26.156:8000'
with open('/home/cat/ros2_ws/src/robot_websocket/config/websocket_config.yaml', 'w') as f:
    yaml.dump(data, f)
print('Updated:', data['base_url'])
"""
sftp = c.open_sftp()
with sftp.open("/tmp/_update_config.py", "w") as f:
    f.write(script)
sftp.close()
stdin, stdout, stderr = c.exec_command("python3 /tmp/_update_config.py 2>/dev/null || echo FAILED", timeout=10)
print("Config:", stdout.read().decode().strip())

# Check yaml available
stdin, stdout, stderr = c.exec_command("python3 -c 'import yaml; print(\"yaml OK\")' 2>/dev/null || echo NO_YAML", timeout=5)
print("yaml:", stdout.read().decode().strip())

# Kill old node, restart with new config
c.exec_command("pkill -f websocket_node 2>/dev/null || true", timeout=5)
time.sleep(1)
c.exec_command("setsid /home/cat/reminder_system/start_robot_ws.sh >> /home/cat/reminder_system/logs/robot_ws.log 2>&1 &", timeout=5)
time.sleep(3)

# Check status
stdin, stdout, stderr = c.exec_command("ps aux | grep websocket_node | grep -v grep", timeout=5)
proc = stdout.read().decode().strip()
print("Running:", "YES" if proc else "NO")

stdin, stdout, stderr = c.exec_command("tail -20 /home/cat/reminder_system/logs/robot_ws.log 2>/dev/null || echo NO_LOG", timeout=5)
print("Log:", stdout.read().decode()[:600])

c.close()
