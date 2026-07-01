"""reminder_bt.launch.py — 启动行为树提醒节点"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("data_dir", default_value="/data/reminders"),
        DeclareLaunchArgument("tick_interval_ms", default_value="200"),

        Node(
            package="robot_reminder_bt",
            executable="reminder_bt_driver",
            name="reminder_bt_driver",
            output="screen",
            parameters=[{
                "data_dir": LaunchConfiguration("data_dir"),
                "tick_interval_ms": LaunchConfiguration("tick_interval_ms"),
                "command_topic": "/robot/command",
                "response_topic": "/robot/command_response",
            }],
        ),
    ])
