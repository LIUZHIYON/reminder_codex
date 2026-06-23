import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

stdin, stdout, stderr = c.exec_command("ls ~/ros2_ws/install/robot_websocket/ 2>/dev/null || echo NO_BUILD", timeout=5)
print("Install dir:", stdout.read().decode()[:200])

stdin, stdout, stderr = c.exec_command("find ~/ros2_ws/install/robot_websocket -name '*.py' 2>/dev/null | head -10", timeout=5)
print("Built files:", stdout.read().decode()[:300])

stdin, stdout, stderr = c.exec_command("python3 -c 'import rclpy; print(rclpy.__version__)' 2>/dev/null || echo NO_RCLPY", timeout=5)
print("rclpy:", stdout.read().decode().strip())

c.close()
