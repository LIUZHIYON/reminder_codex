#!/bin/bash
source /opt/ros/humble/setup.bash
setsid ros2 launch robot_voice_bridge voice_bridge.launch.py < /dev/null > /dev/null 2>&1 &
sleep 3
setsid ros2 launch robot_doubao_tts_node tts.launch.py < /dev/null > /dev/null 2>&1 &
sleep 2
setsid ros2 launch robot_audio_node robot_audio_node.launch.py < /dev/null > /dev/null 2>&1 &
echo voice_started
