"""Test voice pipeline fully - send voice command via Action"""
import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
pwd = "temppwd"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.209', username='cat', password=pwd, timeout=10)

def run(cmd, timeout=15):
    i,o,e = ssh.exec_command(cmd, timeout=timeout)
    ec = o.channel.recv_exit_status()
    return o.read().decode('utf-8','replace').strip(), e.read().decode('utf-8','replace').strip(), ec

def run_ros(cmd, timeout=15):
    full = 'bash -c "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash && ' + cmd + '"'
    i,o,e = ssh.exec_command(full, timeout=timeout)
    ec = o.channel.recv_exit_status()
    out = o.read().decode('utf-8','replace').strip()
    err = e.read().decode('utf-8','replace').strip()
    return out, err, ec

print("=" * 60)
print("Test 1: Direct Action call to /voice/speak")
print("=" * 60)

# Write a test script that calls the Speak action directly
action_test = '''import rclpy, sys, time
from robot_voice_bridge.action import Speak
from rclpy.action import ActionClient

rclpy.init()
node = rclpy.create_node('test_voice_client')
client = ActionClient(node, Speak, '/voice/speak')

if not client.wait_for_server(timeout_sec=5):
    print("ERROR: /voice/speak server not available")
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(1)

print("Sending speak request...")
goal = Speak.Goal()
goal.text = "喇叭测试，一二三"
goal.audio_path = ""

future = client.send_goal_async(goal, feedback_callback=lambda fb: print(f"FEEDBACK: {fb.feedback.status}"))
rclpy.spin_until_future_complete(node, future, timeout_sec=3)

if not future.result():
    print("ERROR: goal rejected")
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(1)

gh = future.result()
result_future = gh.get_result_async()
rclpy.spin_until_future_complete(node, result_future, timeout_sec=30)

if result_future.result():
    result = result_future.result().result
    print(f"RESULT: success={result.success} message={result.message}")
else:
    print("ERROR: no result after 30s")

node.destroy_node()
rclpy.shutdown()
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_speak_action.py', 'w') as f:
    f.write(action_test)
sftp.close()

print("Running test action client...")
out, err, ec = run_ros("python3 /tmp/test_speak_action.py", timeout=35)
print(f"  Result:\n{out}")

# Check the logs after test
print("\n" + "=" * 60)
print("Logs after action test")
print("=" * 60)
for logf in ["voice_bridge.log", "tts_node.log", "audio_node.log"]:
    out, err, ec = run(f"tail -15 /tmp/voice_logs/{logf} 2>/dev/null")
    print(f"\n--- {logf} ---")
    print(out[-800:] if out else "    (empty)")

ssh.close()
print("\nDone!")
