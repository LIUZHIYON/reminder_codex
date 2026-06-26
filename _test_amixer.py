import json, urllib.request, time

req = urllib.request.Request("http://127.0.0.1:8000/api/board-reminders/75/play", method="POST")
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read())
print(f"Play: {json.dumps(result, ensure_ascii=False)}")

time.sleep(2)

import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.70", username="cat", password="temppwd", timeout=5)

# Check the log
_, stdout, _ = cli.exec_command("cat /tmp/_speak_run.log 2>/dev/null || echo NO_LOG")
log = stdout.read().decode("utf-8", errors="replace")
print("=== LOG ===")
print(log if log.strip() else "(empty)")

# Check ALSA state
_, stdout, _ = cli.exec_command("amixer get Speaker 2>/dev/null | grep Mono")
print("ALSA SPEAKER:", stdout.read().decode()[:100])

# Check if the nohup cmd in the log shows amixer
_, stdout, _ = cli.exec_command("grep amixer /tmp/_speak_run.log 2>/dev/null || echo 'NO AMIXER IN LOG'")
print("AMIXER IN LOG:", stdout.read().decode()[:200])

cli.close()