import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=5)

# Kill old Flask, start new
c.exec_command("fuser -k 5000/tcp 2>/dev/null", timeout=5)
time.sleep(1)

# Check if web_app.py syntax is fixed
stdin, stdout, stderr = c.exec_command("python3 -m py_compile /home/cat/reminder_system/app/web_app.py 2>&1 || echo SYNTAX_ERROR", timeout=5)
print("Syntax:", stdout.read().decode().strip())

# Start run.py
c.exec_command("cd /home/cat/reminder_system && nohup python3 run.py > logs/run.log 2>&1 &", timeout=5)
time.sleep(3)

# Test Flask
stdin, stdout, stderr = c.exec_command("curl -s -w '%{http_code}' http://127.0.0.1:5000/api/reminders -o /dev/null 2>/dev/null || echo FAIL", timeout=5)
print("Flask status:", stdout.read().decode().strip())

# Test POST
stdin, stdout, stderr = c.exec_command("curl -s -X POST http://127.0.0.1:5000/api/reminders/create -H 'Content-Type: application/json' -d '{\"content\":\"final_test\",\"reminder_time\":\"2026-06-23T23:00\"}' 2>/dev/null || echo FAIL", timeout=5)
print("POST:", stdout.read().decode()[:100])

c.close()
