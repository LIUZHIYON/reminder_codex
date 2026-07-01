#!/usr/bin/env python3
"""
reminder_auto_node.py — 定时提醒自动播报 ROS2 节点

无需行为树，直接循环检查提醒 API，到时间就播报。

运行: ros2 run robot_reminder_bt reminder_auto_node
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import requests
import json
from datetime import datetime


class ReminderAutoNode(Node):
    """定时检查 → 到点播报"""

    def __init__(self):
        super().__init__('reminder_auto_node')

        # 参数
        self.declare_parameter('api_url', 'http://192.168.1.191:5000')
        self.declare_parameter('check_interval_sec', 2.0)
        self.declare_parameter('tts_topic', '/tts/text')
        self.declare_parameter('command_topic', '/robot/command')

        self.api_url = self.get_parameter('api_url').value
        interval = self.get_parameter('check_interval_sec').value

        # 发布者
        self.tts_pub = self.create_publisher(String, '/tts/text', 10)
        self.cmd_pub = self.create_publisher(String, '/robot/command', 10)

        # 定时器
        self.create_timer(interval, self.check_and_play)

        self.get_logger().info('reminder_auto_node 已启动')
        self.get_logger().info(f'  检查间隔: {interval}s')
        self.get_logger().info(f'  提醒 API: {self.api_url}')

    def check_and_play(self):
        """检查待触发提醒，到时间的就播报"""
        try:
            resp = requests.get(
                f'{self.api_url}/api/reminders?status=pending',
                timeout=3
            )
            data = resp.json()
            reminders = data.get('data', [])
        except Exception as e:
            return

        now = datetime.now()

        for reminder in reminders:
            reminder_time_str = reminder.get('reminder_time', '')
            if not reminder_time_str:
                continue

            try:
                reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

            # 到时间了 (或已过时)
            if reminder_time <= now:
                self.trigger_reminder(reminder)

    def trigger_reminder(self, reminder):
        """触发一条提醒播报"""
        rid = reminder.get('id')
        content = reminder.get('content', '您有一条新提醒')
        self.get_logger().info(f'触发提醒 [{rid}]: {content}')

        # 1. 发 TTS -> doubao_tts_node 合成 -> audio_node 播报
        msg = String()
        msg.data = content
        self.tts_pub.publish(msg)

        # 2. 通知 WebSocket -> 服务器
        cmd = String()
        cmd.data = json.dumps({
            'type': 'command_response',
            'command': 'reminder',
            'status': 'success',
            'result': {
                'played': True,
                'content': content,
                'id': rid,
            }
        })
        self.cmd_pub.publish(cmd)

        # 3. 标记已触发
        try:
            requests.post(
                f'{self.api_url}/api/reminders/{rid}/trigger',
                timeout=3
            )
        except Exception as e:
            self.get_logger().warn(f'标记 [{rid}] 失败: {e}')


def main():
    rclpy.init()
    node = ReminderAutoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
