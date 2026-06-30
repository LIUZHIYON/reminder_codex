"""reminder_standalone.launch.py — 独立提醒启动（完全独立，不依赖同事节点）"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # 1. 独立 WebSocket 守护（连接远程服务器）
        Node(
            package="robot_reminder_bt",
            executable="reminder_ws_daemon",
            name="reminder_ws_daemon",
            output="screen",
            parameters=[{
                "server_host": "47.118.26.156",
                "server_port": 8000,
                "serial_number": "6976f96f-bc80-56e3-9b27-13d12cdde9d1",
                "heartbeat_interval": 30.0,
            }],
        ),

        # 2. 提醒桥接
        Node(
            package="robot_reminder_bt",
            executable="aipet_reminder_node",
            name="aipet_reminder_node",
            output="screen",
        ),

        # 3. 行为树驱动
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
