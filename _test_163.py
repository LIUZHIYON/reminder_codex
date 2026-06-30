"""Test voice pipeline on 192.168.1.163"""
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.163', username='cat', password="temppwd", timeout=10)

sftp = ssh.open_sftp()
test_script = """import rclpy, sys
from robot_voice_bridge.action import Speak
from rclpy.action import ActionClient
rclpy.init()
n = rclpy.create_node("test_voice")
c = ActionClient(n, Speak, "/voice/speak")
if not c.wait_for_server(timeout_sec=5):
    print("FAIL: /voice/speak not available")
    sys.exit(1)
print("Sending: 喇叭测试")
g = Speak.Goal()
g.text = "喇叭测试，声音正常"
g.audio_path = ""
f = c.send_goal_async(g)
rclpy.spin_until_future_complete(n, f, timeout_sec=3)
if not f.result():
    print("FAIL: goal rejected")
    sys.exit(1)
gh = f.result()
rf = gh.get_result_async()
rclpy.spin_until_future_complete(n, rf, timeout_sec=30)
if rf.result():
    r = rf.result().result
    print(f"DONE: success={r.success} msg={r.message}")
else:
    print("FAIL: no result")
n.destroy_node()
rclpy.shutdown()
"""
with sftp.open('/tmp/test_163.py', 'w') as f:
    f.write(test_script)
sftp.close()

print("Running voice test on 192.168.1.163...")
i,o,e = ssh.exec_command(
    'bash -c "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null; python3 /tmp/test_163.py"',
    timeout=35
)
ec = o.channel.recv_exit_status()
print(o.read().decode('utf-8','replace').strip())
ssh.close()
