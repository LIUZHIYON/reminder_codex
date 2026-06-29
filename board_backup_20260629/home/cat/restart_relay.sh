#!/bin/bash
# 强杀所有传话相关进程（含 wrapper shell）
for p in $(ps aux | grep -E 'ws_daemon|relay_node|relay_voice_bridge' | grep -v grep | awk '{print $2}'); do
  kill -9 $p 2>/dev/null
done
sleep 3
rm -f ~/relay_mw.db

source /opt/ros/humble/setup.bash
setsid python3 ~/talk_with/ros_ws/install/robot_aipet_relay/lib/python3.10/site-packages/robot_aipet_relay/ws_daemon.py >> ~/ws_daemon.log 2>&1 &
sleep 4

source ~/talk_with/ros_ws/install/setup.bash
setsid relay_node --ros-args -p server_host:=47.118.26.156 -p server_port:=8000 -p serial_number:=6976f96f-bc80-56e3-9b27-13d12cdde9d1 >> ~/relay_node.log 2>&1 &
sleep 3

setsid relay_voice_bridge >> ~/voice_bridge.log 2>&1 &
sleep 2

echo "=== 各实例数 ==="
echo "ws_daemon: $(ps aux | grep ws_daemon.py | grep -v grep | wc -l)"
echo "relay_node: $(ps aux | grep bin/relay_node | grep -v grep | wc -l)"
echo "relay_voice: $(ps aux | grep relay_voice_bridge | grep -v grep | wc -l)"
echo ALL_DONE
