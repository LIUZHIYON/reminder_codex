"""reminder_standalone.launch.py — 独立提醒启动（不依赖同事 relay_node）"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, TimerAction


def generate_launch_description():
    return LaunchDescription([
        # 1. 检查并启动 ws_daemon_bridge
        ExecuteProcess(
            cmd=["python3", "-c",
                 "import rclpy,time;rclpy.init();n=rclpy.create_node('ck');time.sleep(2);"
                 "has=any('ws_daemon_bridge' in x for x in n.get_node_names());"
                 "if not has:"
                 " import subprocess;subprocess.Popen(['bash','-c',"
                 "'source /opt/ros/humble/setup.bash;source /home/cat/talk_with/ros_ws/install/setup.bash;"
                 "python3 /home/cat/talk_with/ros_ws/install/robot_aipet_relay/lib/python3.10/"
                 "site-packages/robot_aipet_relay/ws_daemon.py >/dev/null 2>&1 &']);"
                 " print('ws_daemon: started')"
                 "else: print('ws_daemon: already running');n.destroy_node();rclpy.shutdown()"],
            name="check_ws_daemon",
            shell=False,
        ),

        # 2. 提醒桥接
        Node(
            package="robot_reminder_bt",
            executable="aipet_reminder_node",
            name="aipet_reminder_node",
            output="screen",
        ),

        # 3. 行为树驱动
        Node(
            package="robot_reminder_bt",
            executable="reminder_bt_driver",
            name="reminder_bt_driver",
            output="screen",
            parameters=[{
                "tick_interval_ms": 200,
                "command_topic": "/robot/command",
                "response_topic": "/robot/command_response",
                "relay_topic": "aipet/command_delivery",
            }],
        ),
    ])
