import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)
cmds = [
    "source /opt/ros/humble/setup.bash && which ros2 2>/dev/null && ros2 --version || echo NO_ROS_CMD",
    "source /opt/ros/humble/setup.bash && python3 -c \"import rclpy; print('rclpy OK:', rclpy.__version__)\" 2>/dev/null || echo NO_RCLPY",
    "ls ~/ros2_ws/src/ 2>/dev/null || echo NO_ROS2_WS",
    "ls ~/ros2_ws/install/ 2>/dev/null || echo NO_INSTALL",
]
for cmd in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {cmd[:60]} ===")
    if out: print(out[:300])
    if err: print(f"ERR: {err[:200]}")
c.close()
