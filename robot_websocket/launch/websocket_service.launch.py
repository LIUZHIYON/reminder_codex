# -*- coding: utf-8 -*-
"""
WebSocket 服务启动文件
"""

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """生成启动描述"""
    
    # 获取包路径
    pkg_dir = get_package_share_directory('robot_websocket')
    
    # 默认配置文件路径
    default_config = os.path.join(pkg_dir, 'config', 'websocket_config.yaml')
    
    # 声明启动参数
    declare_base_url = DeclareLaunchArgument(   
        'base_url',
        default_value='https://airobot.lenudo.com',
        description='服务器基础 URL'
    )
    
    declare_serial_number = DeclareLaunchArgument(
        'serial_number',
        default_value='6976f96f-bc80-56e3-9b27-13d12cdde9d9',
        description='设备序列号'
    )
    
    declare_config_file = DeclareLaunchArgument(
        'config_file',
        default_value=default_config,
        description='配置文件路径'
    )
    
    declare_use_config_file = DeclareLaunchArgument(
        'use_config_file',
        default_value='false',
        description='是否使用配置文件'
    )
    
    # 创建节点
    websocket_node = Node(
        package='robot_websocket',
        executable='websocket_node',
        name='websocket_node',
        output='screen',
        parameters=[
            # 基础配置
            {'base_url': LaunchConfiguration('base_url')},
            {'serial_number': LaunchConfiguration('serial_number')},
            {'heartbeat_interval': 30},
            {'reconnect_delay': 3},
            {'max_reconnect_attempts': 10},
            {'enable_auto_reconnect': True},
            {'status_update_interval': 5.0},
            # 话题配置
            {'chat_topic': '/robot/chat'},
            {'command_topic': '/robot/command'},
            {'status_topic': '/robot/status'},
            # 配置文件
            {'config_file': LaunchConfiguration('config_file')},
        ],
        # 如果指定了配置文件，从文件加载参数
        # 注意：ROS 2 参数会覆盖配置文件中的值
    )
    
    return LaunchDescription([
        declare_base_url,
        declare_serial_number,
        declare_config_file,
        declare_use_config_file,
        websocket_node,
    ])
