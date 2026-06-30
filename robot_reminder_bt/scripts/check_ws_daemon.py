#!/usr/bin/env python3
"""检查 ws_daemon_bridge 是否运行，没有则启动"""

import rclpy, time, subprocess, sys, os

rclpy.init(args=[])
node = rclpy.create_node("startup_check")

# Wait for node discovery
time.sleep(3)

# Check node list
node_names = node.get_node_names()
has_ws = any("/ws_daemon_bridge" in n for n in node_names)
has_reminder = any("aipet_reminder_node" in n for n in node_names)
has_bt = any("reminder_bt_driver" in n for n in node_names)

print(f"ws_daemon_bridge: {'RUNNING' if has_ws else 'NOT RUNNING'}")
print(f"aipet_reminder_node: {'RUNNING' if has_reminder else 'NOT RUNNING'}")
print(f"reminder_bt_driver: {'RUNNING' if has_bt else 'NOT RUNNING'}")

if not has_ws:
    print("Starting ws_daemon_bridge...")
    # Start from colleague's workspace (if not running)
    ws_cmd = (
        "source /opt/ros/humble/setup.bash && "
        "source /home/cat/talk_with/ros_ws/install/setup.bash && "
        "nohup python3 /home/cat/talk_with/ros_ws/install/robot_aipet_relay/lib/python3.10/"
        "site-packages/robot_aipet_relay/ws_daemon.py > /dev/null 2>&1 &"
    )
    subprocess.Popen(["bash", "-c", ws_cmd])
    print("  Started")

node.destroy_node()
rclpy.shutdown()
