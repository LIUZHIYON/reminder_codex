"""Launch AI Pet relay node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="robot_aipet_relay",
            executable="relay_node",
            name="aipet_relay_node",
            output="screen",
            parameters=[{
                "server_host": "47.118.26.156",
                "server_port": 8000,
                "serial_number": "6976f96f-bc80-56e3-9b27-13d12cdde9d1",
                "heartbeat_interval": 30.0,
                "auto_reconnect": True,
            }],
        )
    ])
