#!/bin/bash
# test_speaker.sh — 板载喇叭测试脚本
# 会临时停止 robot_audio_node 以释放声卡，测完恢复
# 用法: ./test_speaker.sh

set -e

echo '=============================='
echo '  板载喇叭测试 v1'
echo '  192.168.1.52'
echo '=============================='

# 先配音频
echo ''
echo '[1/4] 配置音频输出...'
amixer sset 'spk switch' on        >/dev/null 2>&1
amixer sset 'Speaker' on           >/dev/null 2>&1
amixer sset 'aw_dev_0_switch' Enable >/dev/null 2>&1
amixer sset 'aw_dev_0_rx_volume' 1023 >/dev/null 2>&1
amixer sset 'aw_dev_0_prof' Music >/dev/null 2>&1
amixer sset 'Headphone' off        >/dev/null 2>&1
echo '  [OK] 音频输出已配置'

# 确认声卡
CARD=$(aplay -l 2>/dev/null | grep -oP 'card \K[0-9]+' | head -1)
echo "  声卡: card ${CARD} => plughw:${CARD},0"

# 临时停掉占用声卡的进程
echo ''
echo '[2/4] 释放声卡...'
AUDIO_PIDS=$(ps aux | grep robot_audio_node | grep -v grep | awk '{print $2}')
if [ -n "${AUDIO_PIDS}" ]; then
  echo "  发现 robot_audio_node (PID: ${AUDIO_PIDS})，临时停止..."
  kill ${AUDIO_PIDS} 2>/dev/null
  sleep 1
  echo '  [OK] 已释放声卡'
else
  echo '  没有其他进程占用，跳过'
fi

# 测试播放
echo ''
echo '[3/4] 播放测试音...'

echo ''
echo '  >>> [1/3] 正弦波 440Hz'
speaker-test -D "plughw:${CARD},0" -c 2 -t sine -l 1 -s 1 2>&1 | tail -3
sleep 0.5

echo ''
echo '  >>> [2/3] 白噪声 (pink noise)'
speaker-test -D "plughw:${CARD},0" -c 2 -t pink -l 1 2>&1 | tail -3
sleep 0.5

echo ''
echo '  >>> [3/3] WAV 文件'
WAV=$(find /usr/share/sounds/alsa -name '*.wav' 2>/dev/null | head -1)
if [ -n "${WAV}" ]; then
  echo "      播放: $(basename ${WAV})"
  aplay -D "plughw:${CARD},0" "${WAV}" 2>&1 | tail -1
else
  echo '      (未找到 WAV 文件)'
fi

echo ''
echo '=============================='
echo '  [4/4] 测试完成!'
echo '=============================='
echo ''
echo '听不到声音? 检查:'
echo '  1. 喇叭物理接线是否正常'
echo '  2. amixer sget aw_dev_0_rx_volume (应为1023)'
echo '  3. amixer sget aw_dev_0_switch (应为Enable)'
echo ''
echo '如需恢复 robot_audio_node，请手动启动:'
echo '  source /opt/ros/humble/setup.bash'
echo '  ros2 launch robot_audio_node robot_audio_node.launch.py &'
echo '=============================='
