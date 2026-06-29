import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    tts_pkg = get_package_share_directory("robot_doubao_tts_node")
    audio_pkg = get_package_share_directory("robot_audio_node")
    vb_pkg = get_package_share_directory("robot_voice_bridge")

    tts_config = os.path.join(tts_pkg, "config", "tts_config.yaml")
    audio_config = os.path.join(audio_pkg, "config", "audio_config.yaml")
    vb_config = os.path.join(vb_pkg, "config", "voice_bridge_config.yaml")

    return LaunchDescription([
        Node(
            package="robot_audio_node",
            executable="robot_audio_node",
            name="robot_audio_node",
            parameters=[audio_config],
            output="screen",
        ),
        Node(
            package="robot_doubao_tts_node",
            executable="tts_node_patched",
            name="tts_node",
            parameters=[tts_config],
            output="screen",
            emulate_tty=True,
            remappings=[("/tts/status", "/tts/status_internal")],
        ),
        Node(
            package="robot_voice_bridge",
            executable="status_relay.py",
            name="tts_status_relay",
            output="screen",
            emulate_tty=True,
        ),
        Node(
            package="robot_voice_bridge",
            executable="voice_bridge_node",
            name="voice_bridge",
            parameters=[vb_config],
            output="screen",
            emulate_tty=True,
        ),
    ])
