#!/bin/bash
while true; do
  pgrep -f "robot_doubao_tts_node" > /dev/null || setsid bash -c "" + setup + "; ros2 launch robot_doubao_tts_node tts.launch.py > /dev/null 2>&1 &"
  pgrep -f "robot_audio_node" > /dev/null || setsid bash -c "" + setup + "; ros2 launch robot_audio_node robot_audio_node.launch.py > /dev/null 2>&1 &"
  pgrep -f "robot_voice_bridge" > /dev/null || setsid bash -c "" + setup + "; ros2 launch robot_voice_bridge voice_bridge.launch.py > /dev/null 2>&1 &"
  sleep 60
done
