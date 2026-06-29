#!/bin/bash
source /opt/ros/humble/setup.bash
source /home/cat/ros2_ws/install/setup.bash 2>/dev/null

cleanup() { kill %1 %2 %3 %4 2>/dev/null; }
trap cleanup EXIT

echo "=== Audio node ==="
ros2 launch robot_audio_node robot_audio_node.launch.py &
sleep 2

echo "=== TTS (patched, status remapped to /tts/status_raw) ==="
ros2 launch robot_doubao_tts_node tts_patched.launch.py &
sleep 2

# Remap the TTS status topic
ros2 run robot_doubao_tts_node tts_node_patched \
  --ros-args -r /tts/status:=/tts/status_raw &
sleep 2

echo "=== Status filter ==="
python3 /opt/ros/humble/lib/robot_voice_bridge/voice_bridge_with_filter.py &
sleep 1

echo "=== Voice bridge (reads /tts/status, TTS publishes on /tts/status_raw) ==="
ros2 launch robot_voice_bridge voice_bridge.launch.py &
sleep 3

echo "=== All nodes started ==="
ros2 node list

# Keep running
echo "Press Ctrl+C to stop"
wait
