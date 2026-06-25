path = 'C:\\Users\\29503\\Desktop\\reminder_codex\\_board_speaker.py'
script = '''import subprocess, sys
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
subprocess.Popen(["bash", "-c", full_cmd], close_fds=True, start_new_session=True)
print("OK")
'''
with open(path, 'w', encoding='utf-8') as f:
    f.write(script)
print('Written')
