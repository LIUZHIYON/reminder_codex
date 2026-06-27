#!/bin/bash
source /opt/ros/humble/setup.bash
source /home/cat/ros2_ws/install/setup.bash 2>/dev/null
TEXT=$(cat /tmp/_tts_input.txt 2>/dev/null || echo hello)
timeout 15 ros2 topic echo /tts/audio --once > /tmp/_audio_dump.txt 2>/dev/null &
PID=$!
sleep 1
ros2 topic pub --once /tts/text std_msgs/String "data: \"$TEXT\"" 2>/dev/null
wait 612 2>/dev/null
echo CAPTURED
