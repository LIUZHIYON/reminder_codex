"""reminder_full_standalone.launch.py — 独立提醒（不依赖同事 relay_node）

节点:
  aipet_reminder_node  ← 桥接 ws_daemon_bridge ↔ BT driver
  reminder_bt_driver   ← 行为树驱动 + ZMQ:1667
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # 提醒桥接（下行/上行）
        Node(
            package="robot_reminder_bt",
            executable="aipet_reminder_node",
            name="aipet_reminder_node",
            output="screen",
        ),
        # 行为树驱动
        Node(
            package="robot_reminder_bt",
            executable="reminder_bt_driver",
            name="reminder_bt_driver",
            output="screen",
            parameters=[{
                "tick_interval_ms": 200,
                "command_topic": "/robot/command",
                "response_topic": "/robot/command_response",
                "relay_topic": "aipet/command_delivery",
            }],
        ),
    ])
