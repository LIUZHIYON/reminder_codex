import subprocess, sys
try:
    with open("/tmp/_tts_input.txt", "r", encoding="utf-8") as f:
        text = f.read().strip()
except:
    text = ""
if not text:
    print("No text")
    sys.exit(1)
dq = chr(34)
sq = chr(39)
safe = text.replace(sq, dq+sq+dq)
target = dq + "data: " + sq + safe + sq + dq
full_cmd = "source /opt/ros/humble/setup.bash && source /home/cat/ros2_ws/install/setup.bash && ros2 topic pub --once /tts/text std_msgs/String " + target + " > /tmp/_tts_topic.log 2>&1 &"
# Use os.fork to completely detach the child
import os as _os
pid = _os.fork()
if pid == 0:
    _os.setsid()
    subprocess.Popen(["bash", "-c", full_cmd], close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _os._exit(0)
print("OK")
