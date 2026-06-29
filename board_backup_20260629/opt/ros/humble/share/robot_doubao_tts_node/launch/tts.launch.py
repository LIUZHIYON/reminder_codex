import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('robot_doubao_tts_node')
    config = os.path.join(pkg_dir, 'config', 'tts_config.yaml')
    return LaunchDescription([
        Node(
            package='robot_doubao_tts_node',
            executable='tts_node',
            name='tts_node',
            parameters=[config],
            output='screen',
        ),
    ])
