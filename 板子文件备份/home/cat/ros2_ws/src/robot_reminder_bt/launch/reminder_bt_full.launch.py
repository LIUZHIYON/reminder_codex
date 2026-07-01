"""reminder_bt_full.launch.py — 启动行为树驱动 + Groot2 监控"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("tick_interval_ms", default_value="200"),
        DeclareLaunchArgument("command_topic", default_value="/robot/command"),
        DeclareLaunchArgument("response_topic", default_value="/robot/command_response"),
        DeclareLaunchArgument("zmq_port", default_value="1669"),

        # 行为树驱动节点（纯话题版，无数据库）
        Node(
            package="robot_reminder_bt",
            executable="reminder_bt_driver",
            name="reminder_bt_driver",
            output="screen",
            parameters=[{
                "tick_interval_ms": LaunchConfiguration("tick_interval_ms"),
                "command_topic": LaunchConfiguration("command_topic"),
                "response_topic": LaunchConfiguration("response_topic"),
                "relay_topic": "aipet/command_delivery",
                "status_topic": "/robot/bt_status",
            }],
        ),

        # Groot2 ZMQ 可视化服务器
        Node(
            package="robot_reminder_bt",
            executable="groot2_server",
            name="groot2_server",
            output="screen",
            parameters=[{
                "zmq_port": LaunchConfiguration("zmq_port"),
                "bt_status_topic": "/robot/bt_status",
            }],
        ),
    ])
