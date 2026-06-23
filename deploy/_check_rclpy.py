import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.64", username="cat", password="temppwd", timeout=10)

script = '\n'.join([
    'import sys',
    'sys.path.insert(0, "/opt/ros/humble/lib/python3.10/site-packages")',
    'try:',
    '    import rclpy',
    '    print("rclpy version:", rclpy.__version__)',
    'except ImportError as e:',
    '    print("rclpy not found:", e)',
    'import os',
    'p = "/opt/ros/humble/lib/python3.10/site-packages"',
    'if os.path.exists(p): print("pkgs:", os.listdir(p)[:20])',
])

sftp = c.open_sftp()
with sftp.open("/tmp/_check_rclpy.py", "w") as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/_check_rclpy.py", timeout=10)
print(stdout.read().decode()[:500])
c.exec_command("rm -f /tmp/_check_rclpy.py")
c.close()
