#!/bin/bash
source /opt/ros/humble/setup.bash
source ~/talk_with/ros_ws/install/setup.bash
kill $(pgrep -f relay_node) 2>/dev/null
sleep 1
relay_node --ros-args -p server_host:=47.118.26.156 -p server_port:=8000 -p serial_number:=6976f96f-bc80-56e3-9b27-13d12cdde9d1 >> ~/relay_node.log 2>&1
