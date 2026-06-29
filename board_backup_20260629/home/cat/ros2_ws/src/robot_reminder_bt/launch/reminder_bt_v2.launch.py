"""
reminder_bt_v2.launch.py — v2 行为树启动文件

启动:
  1. blackboard_node — 黑板节点 (共享状态管理)
  2. reminder_bt_node_v2 — 行为树节点 (全话题通信)

配合运行 (终端 3):
  ros2 launch robot_websocket websocket_service.launch.py

用法:
  ros2 launch robot_reminder_bt reminder_bt_v2.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # 黑板节点参数
    state_interval = LaunchConfiguration("state_interval", default="1.0")
    max_reminders = LaunchConfiguration("max_reminders", default="50")

    # 行为树节点参数
    tick_interval = LaunchConfiguration("tick_interval_ms", default="200")
    tts_topic = LaunchConfiguration("tts_topic", default="/tts/text")
    cmd_topic = LaunchConfiguration("cmd_topic", default="/robot/command")

    return LaunchDescription([
        # 参数声明
        DeclareLaunchArgument("state_interval", default_value="1.0",
            description="黑板状态发布间隔(秒)"),
        DeclareLaunchArgument("max_reminders", default_value="50",
            description="最大缓存提醒数"),
        DeclareLaunchArgument("tick_interval_ms", default_value="200",
            description="行为树 tick 间隔(毫秒)"),
        DeclareLaunchArgument("tts_topic", default_value="/tts/text",
            description="TTS 文本话题"),
        DeclareLaunchArgument("cmd_topic", default_value="/robot/command",
            description="机器人命令话题"),

        # 1. 黑板节点
        Node(
            package="robot_reminder_bt",
            executable="blackboard_node",
            name="reminder_blackboard",
            output="screen",
            parameters=[{
                "state_publish_interval": state_interval,
                "max_reminders": max_reminders,
            }],
        ),

        # 2. 行为树节点 v2
        Node(
            package="robot_reminder_bt",
            executable="reminder_bt_node_v2",
            name="reminder_bt_node_v2",
            output="screen",
            parameters=[{
                "tick_interval_ms": tick_interval,
                "tts_text_topic": tts_topic,
                "command_topic": cmd_topic,
            }],
        ),
    ])
