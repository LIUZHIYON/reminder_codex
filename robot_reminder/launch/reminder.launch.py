"""reminder.launch.py - 提醒节点启动文件"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("serial_number", default_value="AIPET-DEMO-001"),
        DeclareLaunchArgument("server_host", default_value="42.121.217.40"),
        DeclareLaunchArgument("server_port", default_value="3000"),
        DeclareLaunchArgument("ws_path", default_value="/openclaw-wwh/robot_websocket"),

        Node(
            package="robot_reminder",
            executable="reminder_node",
            name="reminder_node",
            output="screen",
            parameters=[{
                "serial_number": LaunchConfiguration("serial_number"),
                "server_host": LaunchConfiguration("server_host"),
                "server_port": LaunchConfiguration("server_port"),
                "ws_path": LaunchConfiguration("ws_path"),
            }],
        ),
    ])
