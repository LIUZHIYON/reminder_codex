import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('robot_audio_node'),
        'config',
        'robot_audio_node.yaml',
    )
    return LaunchDescription([
        Node(
            package='robot_audio_node',
            executable='robot_audio_node',
            name='robot_audio_node',
            output='screen',
            parameters=[config],
        ),
    ])
