"""Set volume to 90 on board 192.168.1.163"""
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
pwd = "temppwd"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.163', username='cat', password="temppwd", timeout=10)

sftp = ssh.open_sftp()
vol_script = """import rclpy
from robot_audio_node.srv import SetVolume
rclpy.init()
n = rclpy.create_node("vol_set")
c = n.create_client(SetVolume, "/audio/set_volume")
if c.wait_for_service(timeout_sec=5):
    r = SetVolume.Request()
    r.volume = 90
    f = c.call_async(r)
    rclpy.spin_until_future_complete(n, f, timeout_sec=5)
    if f.result():
        print(f"OK: volume={r.volume} success={f.result().success}")
    else:
        print("FAIL: no response")
else:
    print("FAIL: service not available")
n.destroy_node()
rclpy.shutdown()
"""
with sftp.open('/tmp/set_vol_163.py', 'w') as f:
    f.write(vol_script)
sftp.close()

print("Setting volume to 90...")
i,o,e = ssh.exec_command(
    'bash -c "source /opt/ros/humble/setup.bash && python3 /tmp/set_vol_163.py"',
    timeout=10
)
ec = o.channel.recv_exit_status()
print(o.read().decode('utf-8','replace').strip())

print("\nVerifying...")
i2,o2,e2 = ssh.exec_command(
    'bash -c "source /opt/ros/humble/setup.bash && ros2 service call /audio/get_volume robot_audio_node/srv/GetVolume {} 2>&1"',
    timeout=8
)
ec2 = o2.channel.recv_exit_status()
print(o2.read().decode('utf-8','replace').strip())

ssh.close()
