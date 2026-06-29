#!/bin/bash

source /opt/ros/humble/setup.bash 2>/dev/null
source /home/cat/ros2_ws/install/setup.bash 2>/dev/null

echo "========================================"
echo "  🎤 语音播报测试"
echo "========================================"

# 如果节点还没跑，先启动
if ! ros2 node list 2>/dev/null | grep -q voice_bridge; then
    echo "启动语音桥..."
    ros2 launch robot_voice_bridge voice_bridge.launch.py &
    sleep 3
fi

# 测试1: 基础文本播报
echo ""
echo "--- 测试1: 基础文本播报 ---"
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak '{text: "你好世界，我是机器人小助手"}'
