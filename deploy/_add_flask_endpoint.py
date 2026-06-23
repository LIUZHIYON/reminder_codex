import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Read current web_app.py
stdin, stdout, stderr = c.exec_command("cat /home/cat/reminder_system/app/web_app.py", timeout=10)
web_content = stdout.read().decode("utf-8", errors="replace")
print("Current size:", len(web_content))

# Add POST endpoint for reminders
# Find where to insert - after the GET api_reminders function
insert_marker = "def api_reminders():"
post_handler = """
@app.route(\"/api/reminders/create\", methods=[\"POST\"])
@db.with_connection
def api_create_reminder():
    import json
    data = request.get_json(force=True) or {}
    content = data.get(\"content\", \"\")
    reminder_time = data.get(\"reminder_time\", \"\")
    if not content or not reminder_time:
        return jsonify({\"success\": False, \"error\": \"content+reminder_time required\"}), 400
    conn = db.connect()
    c = conn.cursor()
    c.execute(\"INSERT INTO reminders (content, reminder_time, status) VALUES (?,?,?)\", (content, reminder_time, \"pending\"))
    conn.commit()
    rid = c.lastrowid
    conn.close()
    return jsonify({\"success\": True, \"id\": rid, \"content\": content, \"reminder_time\": reminder_time})
"""

# Insert after the GET function ends
old = "def api_reminders()"
new = old + post_handler
web_content = web_content.replace(old, new, 1)

# Write back
sftp = c.open_sftp()
with sftp.open("/home/cat/reminder_system/app/web_app.py", "w") as f:
    f.write(web_content)
sftp.close()
print("web_app.py updated with POST endpoint")

# Restart run.py
c.exec_command("pkill -f run.py 2>/dev/null; sleep 1; setsid python3 /home/cat/reminder_system/run.py >> /home/cat/reminder_system/logs/run.log 2>&1 &", timeout=5)
time.sleep(2)

# Verify
stdin, stdout, stderr = c.exec_command("curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:5000/api/reminders/create -H 'Content-Type: application/json' -d '{\"content\":\"test\",\"reminder_time\":\"2026-06-23T15:00\"}' 2>/dev/null || echo FAIL", timeout=5)
print("POST create:", stdout.read().decode().strip())

c.close()
