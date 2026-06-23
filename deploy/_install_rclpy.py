import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

stdin, stdout, stderr = c.exec_command("echo temppwd | sudo -S apt-get install -y ros-humble-rclpy 2>&1 | tail -5", timeout=180)
out = stdout.read().decode("utf-8", errors="replace").strip()
err = stderr.read().decode("utf-8", errors="replace").strip()
print("Install:", out if out else err[:200])

stdin, stdout, stderr = c.exec_command("python3 -c 'import rclpy; print(\"rclpy OK:\", rclpy.__version__)' 2>/dev/null || echo FAILED", timeout=5)
print("rclpy:", stdout.read().decode().strip())

# Create startup script with ROS2 sourcing
script = """#!/bin/bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export PYTHONPATH=/opt/ros/humble/lib/python3.10/site-packages:$PYTHONPATH
cd ~/ros2_ws
python3 -m robot_websocket.websocket_node "$@"
"""
sftp = c.open_sftp()
with sftp.open("/home/cat/reminder_system/start_robot_ws.sh", "w") as f:
    f.write(script)
sftp.close()
c.exec_command("chmod +x /home/cat/reminder_system/start_robot_ws.sh")
print("Startup script created")

c.close()
