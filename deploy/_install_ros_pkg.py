import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

# Check sudo access
stdin, stdout, stderr = c.exec_command("echo temppwd | sudo -S apt-get install -y ros-humble-rclpy 2>&1 | tail -10", timeout=120)
out = stdout.read().decode("utf-8", errors="replace").strip()
err = stderr.read().decode("utf-8", errors="replace").strip()
print("Install rclpy:", out[:500] if out else err[:200])

time.sleep(2)

# Build
stdin, stdout, stderr = c.exec_command("bash -c 'source /opt/ros/humble/setup.bash && cd ~/ros2_ws && colcon build --packages-select robot_websocket 2>&1 | tail -20'", timeout=120)
out = stdout.read().decode("utf-8", errors="replace").strip()
err = stderr.read().decode("utf-8", errors="replace").strip()
print("Build:", out[:500] if out else err[:200])
c.close()
