import subprocess, sys, os
text = sys.argv[1] if len(sys.argv) > 1 else '测试'
safe = text.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))
cmd = 'source /opt/ros/humble/setup.bash && source /home/cat/ros2_ws/install/setup.bash && ros2 topic pub --once /tts/text std_msgs/String "data: \\'' + safe + '\\'" 2>&1'
result = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True, timeout=15)
print('OUT:', result.stdout.strip()[:200])
if result.returncode != 0:
    print('ERR:', result.stderr.strip()[:200])
    sys.exit(1)
