import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Check WS log
stdin, stdout, stderr = c.exec_command("tail -20 /home/cat/reminder_system/logs/ws_client.log", timeout=5)
print("=== WS LOG ===")
print(stdout.read().decode()[:800])

# Check DB
script = "import sqlite3; conn=sqlite3.connect('/home/cat/reminder_system/data/reminders.db'); c=conn.cursor(); c.execute('SELECT id, content, reminder_time, status FROM reminders ORDER BY id DESC LIMIT 3'); [print(r) for r in c.fetchall()]; c.execute('SELECT count(*) FROM reminders'); print('total:', c.fetchone()[0]); conn.close()"
sftp = c.open_sftp()
with sftp.open("/tmp/_check_final3.py", "w") as f: f.write(script)
sftp.close()
stdin, stdout, stderr = c.exec_command("python3 /tmp/_check_final3.py", timeout=5)
print("=== DB ===")
print(stdout.read().decode()[:500])
c.exec_command("rm -f /tmp/_check_final3.py")

# Create systemd service for WS client
svc = """[Unit]
Description=Board WS Client for AI Pet Reminder
After=network.target

[Service]
Type=simple
User=cat
WorkingDirectory=/home/cat/reminder_system
ExecStart=/usr/bin/python3 /home/cat/reminder_system/board_ws_client.py
Restart=always
RestartSec=5
StandardOutput=append:/home/cat/reminder_system/logs/ws_client.log
StandardError=append:/home/cat/reminder_system/logs/ws_client.log

[Install]
WantedBy=multi-user.target
"""
sftp = c.open_sftp()
with sftp.open("/tmp/board-ws-client.service", "w") as f: f.write(svc)
sftp.close()
c.exec_command("echo temppwd | sudo -S cp /tmp/board-ws-client.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable board-ws-client && sudo systemctl restart board-ws-client", timeout=10)
time.sleep(2)
stdin, stdout, stderr = c.exec_command("systemctl is-active board-ws-client", timeout=5)
print("Service:", stdout.read().decode().strip())

c.close()
