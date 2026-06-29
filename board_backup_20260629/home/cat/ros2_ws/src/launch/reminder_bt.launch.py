"""reminder_bt.launch.py — 启动行为树节点"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        # 启动参数
        DeclareLaunchArgument(
            'api_url',
            default_value='http://192.168.1.70:5000',
            description='提醒系统 API 地址'
        ),
        DeclareLaunchArgument(
            'tick_interval_ms',
            default_value='100',
            description='BT tick 间隔（毫秒）'
        ),
        DeclareLaunchArgument(
            'bt_xml',
            default_value='',
            description='BT.CPP XML 文件路径（留空使用内置树）'
        ),

        # Python 版行为树节点
        Node(
            package='robot_reminder_bt',
            executable='reminder_bt_node',
            name='reminder_bt_node',
            output='screen',
            parameters=[{
                'reminder_api_url': LaunchConfiguration('api_url'),
                'tick_interval_ms': LaunchConfiguration('tick_interval_ms'),
                'check_interval_ms': 2000,
                'tts_text_topic': '/tts/text',
                'command_topic': '/robot/command',
                'status_topic': '/robot/status',
                'websocket_chat_topic': '/robot/chat',
            }],
        ),
    ])
