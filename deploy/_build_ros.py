import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Install rclpy if needed and build
steps = [
    'bash -c "source /opt/ros/humble/setup.bash && python3 -c \"import rclpy; print(\\\"rclpy_ok\\\")\"" 2>/dev/null',
    'which colcon 2>/dev/null',
]
for cmd in steps:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {cmd[:50]} === {out[:100]} {err[:100]}")

# Check if rclpy can be installed via pip
stdin, stdout, stderr = c.exec_command("pip3 install rclpy 2>&1 | tail -3", timeout=30)
print("pip install rclpy:", stdout.read().decode()[:200])

c.close()
