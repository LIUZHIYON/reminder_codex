import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)
cmds = [
    "which ros2 2>/dev/null && ros2 --version || echo ROS2_NOT_FOUND",
    "python3 --version",
    "pip3 list 2>/dev/null | grep -i websocket",
    "pip3 list 2>/dev/null | grep -i aiohttp",
    "ls /opt/ros/ 2>/dev/null || echo NO_ROS_OPT",
    "echo $ROS_DISTRO",
]
for cmd in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {cmd[:50]} ===")
    if out: print(out[:300])
    if err: print(f"ERR: {err[:200]}")
c.close()
