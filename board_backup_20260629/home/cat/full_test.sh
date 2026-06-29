#!/bin/bash

source /opt/ros/humble/setup.bash
source /home/cat/ros2_ws/install/setup.bash 2>/dev/null

cleanup() {
    kill %1 %2 %3 2>/dev/null || true
}
trap cleanup EXIT

echo "=== 启动所有节点 ==="
ros2 launch robot_audio_node robot_audio_node.launch.py &
sleep 2

ros2 launch robot_doubao_tts_node tts_patched.launch.py &
sleep 3

ros2 launch robot_voice_bridge voice_bridge.launch.py &
sleep 3

echo ""
echo "=== 节点列表 ==="
ros2 node list

echo ""
echo "=== 测试说话 ==="
echo '发送: 你好世界，我是机器人小助手，系统启动完成'
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak '{text: "你好世界，我是机器人小助手，系统启动完成"}'

sleep 5

echo ""
echo "=== 测试2: 音量调节 ==="
ros2 service call /audio/set_volume robot_audio_node/srv/SetVolume '{volume: 70}'

echo ""
echo "=== 测试3: 播报第二句话 ==="
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak '{text: "当前音量已设置为百分之七十，准备就绪"}'

echo ""
echo "=== 测试完成 ==="
