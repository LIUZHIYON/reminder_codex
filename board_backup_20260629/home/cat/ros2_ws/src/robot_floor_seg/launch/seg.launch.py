from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = get_package_share_directory('robot_floor_seg') + '/config/params.yaml'

    return LaunchDescription([
        Node(
            package='robot_floor_seg',
            executable='seg_node',
            name='wall_floor_seg_node',
            output='screen',
            parameters=[config],
        ),
    ])
