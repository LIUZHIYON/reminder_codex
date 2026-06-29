"""relay.launch.py — 启动 AI Pet 传话节点"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("server_host", default_value="47.118.26.156"),
        DeclareLaunchArgument("server_port", default_value="8000"),
        DeclareLaunchArgument("serial_number", default_value="AIPET-001"),

        Node(
            package="robot_aipet_relay",
            executable="relay_node",
            name="aipet_relay_node",
            output="screen",
            parameters=[{
                "server_host": LaunchConfiguration("server_host"),
                "server_port": LaunchConfiguration("server_port"),
                "serial_number": LaunchConfiguration("serial_number"),
            }],
        ),
    ])
