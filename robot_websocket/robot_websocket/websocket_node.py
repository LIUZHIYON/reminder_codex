# -*- coding: utf-8 -*-
"""
AI宠物机器人 WebSocket ROS 2 节点
集成 WebSocket 客户端与 ROS 2 系统
"""

import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Pose, Vector3
from sensor_msgs.msg import BatteryState

from robot_websocket.websocket_client import WebSocketClient, WebSocketConfig, MessageType
from robot_utils.yaml_utils.yaml_tool import update_yaml, read_yaml, write_yaml
from robot_utils.get_device_info import host_tag


class WebSocketNode(Node):
    """
    WebSocket ROS 2 节点
    
    功能：
    1. 管理 WebSocket 连接
    2. 订阅 ROS 2 话题并转发到服务器
    3. 接收服务器指令并发布到 ROS 2 话题
    4. 处理服务端命令
    """
    
    def __init__(self):
        super().__init__('websocket_node')
        
        # 声明参数
        self._declare_parameters()
        
        # 加载配置
        self.config = self._load_config()
        
        # 创建 WebSocket 客户端
        self.ws_client = WebSocketClient(self.config, self.get_logger())
        
        # 注册消息处理器
        self._register_message_handlers()
        
        # 创建发布者
        self._create_publishers()
        
        # 创建订阅者
        self._create_subscribers()
        
        # 创建定时器
        self._create_timers()
        
        # 状态缓存
        self._status_cache: Dict[str, Any] = {}
        self._last_status_update = 0
        
        self.get_logger().info("WebSocket 节点已初始化")
        
        # 启动 WebSocket 客户端
        self.ws_client.start()
    
    def _declare_parameters(self):
        """声明 ROS 2 参数"""
        self.declare_parameter('base_url', 'http://localhost:8000')
        self.declare_parameter('serial_number', host_tag())
        self.declare_parameter('heartbeat_interval', 30)
        self.declare_parameter('reconnect_delay', 3)
        self.declare_parameter('max_reconnect_attempts', 10)
        self.declare_parameter('enable_auto_reconnect', True)
        self.declare_parameter('config_file', '')
        self.declare_parameter('status_update_interval', 5.0)
        self.declare_parameter('chat_topic', '/robot/chat')
        self.declare_parameter('command_topic', '/robot/command')
        self.declare_parameter('status_topic', '/robot/status')
    
    def _load_config(self) -> WebSocketConfig:
        """加载配置"""
        config_file = self.get_parameter('config_file').value
        
        if config_file:
            try:
                yaml_data = read_yaml(config_file)
                return WebSocketConfig(**yaml_data)
            except Exception as e:
                self.get_logger().warn(f"加载配置文件失败: {e}，使用默认配置")
        
        # 从 ROS 参数加载
        return WebSocketConfig(
            base_url=self.get_parameter('base_url').value,
            serial_number=self.get_parameter('serial_number').value,
            heartbeat_interval=self.get_parameter('heartbeat_interval').value,
            reconnect_delay=self.get_parameter('reconnect_delay').value,
            max_reconnect_attempts=self.get_parameter('max_reconnect_attempts').value,
            enable_auto_reconnect=self.get_parameter('enable_auto_reconnect').value
        )
    
    def _register_message_handlers(self):
        """注册 WebSocket 消息处理器"""
        # 服务端指令处理器
        self.ws_client.on(MessageType.SERVER_COMMAND.value, self._handle_server_command)
        # 聊天响应处理器
        self.ws_client.on(MessageType.CHAT.value, self._handle_chat_response)
        # 配置响应处理器
        self.ws_client.on(MessageType.CONFIG_REQUEST.value, self._handle_config_response)
    
    def _create_publishers(self):
        """创建 ROS 2 发布者"""
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # 服务端命令发布
        self.command_pub = self.create_publisher(
            String, 
            self.get_parameter('command_topic').value, 
            qos
        )
        
        # 连接状态发布
        self.connection_status_pub = self.create_publisher(
            Bool, 
            '/websocket/connected', 
            qos
        )
        
        # 聊天响应发布
        self.chat_response_pub = self.create_publisher(
            String, 
            '/websocket/chat_response', 
            qos
        )
        
        # 配置响应发布
        self.config_response_pub = self.create_publisher(
            String, 
            '/websocket/config_response', 
            qos
        )
        
        # 打印机命令发布
        self.print_command_pub = self.create_publisher(
            String,
            '/printer/print',  # 修改为与蓝牙打印机订阅的话题一致
            qos
        )
        
        # 打印机状态订阅
        self.print_status_sub = self.create_subscription(
            String,
            '/printer/status',
            self._on_printer_status,
            qos
        )
    
    def _create_subscribers(self):
        """创建 ROS 2 订阅者"""
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # 订阅聊天消息
        self.chat_sub = self.create_subscription(
            String,
            self.get_parameter('chat_topic').value,
            self._on_chat_message,
            qos
        )
        
        # 订阅状态更新
        self.status_sub = self.create_subscription(
            String,
            self.get_parameter('status_topic').value,
            self._on_status_message,
            qos
        )
        
        # 订阅电池状态
        self.battery_sub = self.create_subscription(
            BatteryState,
            '/battery/state',
            self._on_battery_state,
            qos
        )
        
        # 订阅姿态信息
        self.pose_sub = self.create_subscription(
            Pose,
            '/robot/pose',
            self._on_pose_message,
            qos
        )
    
    def _create_timers(self):
        """创建定时器"""
        # 状态上报定时器
        status_interval = self.get_parameter('status_update_interval').value
        self.status_timer = self.create_timer(status_interval, self._on_status_timer)
        
        # 连接状态检查定时器
        self.connection_timer = self.create_timer(1.0, self._on_connection_timer)
    
    # ==================== 消息处理器 ====================
    
    def _handle_server_command(self, message: Dict[str, Any]):
        """
        处理服务端指令
        
        支持的指令：
        - wake_up: 唤醒
        - sleep: 休眠
        - play_sound: 播放声音
        - set_mood: 设置心情
        - restart: 重启
        - update_config: 更新配置
        - upload_status: 上传状态
        - set_volume: 设置音量
        - set_brightness: 设置亮度
        - take_photo: 拍照
        - print: 打印图片
        """
        # 打印收到的完整消息结构
        self.get_logger().info("=" * 60)
        self.get_logger().info("【收到服务端指令】")
        self.get_logger().info(f"消息类型: {message.get('type', 'unknown')}")
        self.get_logger().info(f"完整消息结构:\n{json.dumps(message, indent=2, ensure_ascii=False)}")
        self.get_logger().info("=" * 60)
        
        command = message.get('command')
        command_id = message.get('command_id')
        params = message.get('command_params', {})
        
        self.get_logger().info(f"处理服务端指令: {command} (ID: {command_id})")
        self.get_logger().info(f"指令参数: {json.dumps(params, indent=2, ensure_ascii=False)}")
        
        # 发布到 ROS 话题
        cmd_msg = String()
        cmd_data = {
            'command': command,
            'command_id': command_id,
            'params': params,
            'timestamp': datetime.now().isoformat(),
            'raw_message': message  # 保留原始消息
        }
        cmd_msg.data = json.dumps(cmd_data)
        self.command_pub.publish(cmd_msg)
        
        # 执行指令并发送响应
        self._execute_command(command, command_id, params)
    
    def _execute_command(self, command: str, command_id: str, params: Dict[str, Any]):
        """执行服务端指令"""
        try:
            result = {
                'executed_at': datetime.now().isoformat(),
                'status': 'completed',
                'params_received': params
            }
            self.get_logger().info(f"指令执行结果: {command}")
            # 根据指令类型执行相应操作
            if command == 'wake_up':
                self.get_logger().info("执行唤醒指令")
                # TODO: 调用唤醒服务
                
            elif command == 'sleep':
                self.get_logger().info("执行休眠指令")
                # TODO: 调用休眠服务
                
            elif command == 'upload_status':
                self.get_logger().info("执行状态上报指令")
                self._send_status_update()
                
            elif command == 'update_config':
                self.get_logger().info("执行配置更新指令")
                self._request_config()
                
            elif command == 'play_sound':
                sound_id = params.get('sound_id')
                self.get_logger().info(f"执行播放声音指令: {sound_id}")
                # TODO: 调用音频服务
                
            elif command == 'set_mood':
                mood = params.get('mood')
                self.get_logger().info(f"执行设置心情指令: {mood}")
                # TODO: 更新心情状态
                
            elif command == 'set_volume':
                volume = params.get('volume')
                self.get_logger().info(f"执行设置音量指令: {volume}")
                # TODO: 调用音量控制服务
                
            elif command == 'set_brightness':
                brightness = params.get('brightness')
                self.get_logger().info(f"执行设置亮度指令: {brightness}")
                # TODO: 调用亮度控制服务
                
            elif command == 'take_photo':
                self.get_logger().info("执行拍照指令")
                # TODO: 调用摄像头服务
                
            elif command == 'print':
                self.get_logger().info("执行打印指令")
                self._handle_print_command(command_id, params)
                
            else:
                self.get_logger().warn(f"未知指令: {command}")
                result['status'] = 'unknown_command'
            
            # 发送指令响应
            self.ws_client.send_command_response_sync(
                command_id=command_id,
                command=command,
                status='success',
                result=result
            )
            
        except Exception as e:
            self.get_logger().error(f"执行指令失败: {e}")
            self.ws_client.send_command_response_sync(
                command_id=command_id,
                command=command,
                status='failed',
                result={'error': str(e)}
            )
    
    def _handle_chat_response(self, message: Dict[str, Any]):
        """处理聊天响应"""
        content = message.get('data', {}).get('content', '')
        self.get_logger().debug(f"收到聊天响应: {content}")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(message.get('data', {}))
        self.chat_response_pub.publish(msg)
    
    def _handle_config_response(self, message: Dict[str, Any]):
        """处理配置响应"""
        self.get_logger().debug("收到配置响应")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(message.get('data', {}))
        self.config_response_pub.publish(msg)
    
    # ==================== ROS 订阅回调 ====================
    
    def _on_chat_message(self, msg: String):
        """处理聊天消息"""
        try:
            data = json.loads(msg.data)
            content = data.get('content', '')
            chat_type = data.get('type', 'text')
            
            self.get_logger().debug(f"发送聊天消息: {content}")
            
            # 发送到服务器
            response = self.ws_client.send_chat_sync(
                content=content,
                chat_type=chat_type,
                require_ack=False
            )
            
            if response and not response.get('success'):
                self.get_logger().warn(f"发送聊天消息失败: {response}")
                
        except json.JSONDecodeError:
            # 如果不是 JSON，直接作为文本发送
            self.ws_client.send_chat_sync(
                content=msg.data,
                chat_type='text',
                require_ack=False
            )
        except Exception as e:
            self.get_logger().error(f"处理聊天消息失败: {e}")
    
    def _on_status_message(self, msg: String):
        """处理状态消息"""
        try:
            status = json.loads(msg.data)
            self._status_cache.update(status)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"解析状态消息失败: {e}")
    
    def _on_battery_state(self, msg: BatteryState):
        """处理电池状态"""
        self._status_cache['battery_level'] = int(msg.percentage)
        self._status_cache['battery_voltage'] = msg.voltage
        self._status_cache['battery_current'] = msg.current
    
    def _on_pose_message(self, msg: Pose):
        """处理姿态消息"""
        self._status_cache['position'] = {
            'x': msg.position.x,
            'y': msg.position.y,
            'z': msg.position.z
        }
        self._status_cache['orientation'] = {
            'x': msg.orientation.x,
            'y': msg.orientation.y,
            'z': msg.orientation.z,
            'w': msg.orientation.w
        }
    
    def _handle_print_command(self, command_id: str, params: Dict[str, Any]):
        """
        处理打印指令
        
        支持的打印参数：
        - file_url: 文件URL（必填，支持图片和PDF）
        - file_type: 文件类型（如 'application/pdf', 'image/jpeg'）
        - print_source: 打印来源（如 'app_chat'）
        - print_mode: 打印模式 ('standard', 'high_quality', 'fast')
        - scale: 缩放比例 (0.1 - 2.0)
        - rotation: 旋转角度 (0, 90, 180, 270)
        - priority: 优先级 ('high', 'normal', 'low')
        - timeout: 超时时间（秒）
        - wait_for_result: 是否等待打印完成 (默认 True)
        """
        try:
            # 支持新的 file_url 和旧的 image_url
            file_url = params.get('file_url') or params.get('image_url')
            if not file_url:
                self.get_logger().error("打印指令缺少 file_url/image_url 参数")
                self.ws_client.send_command_response_sync(
                    command_id=command_id,
                    command='print',
                    status='failed',
                    result={'error': '缺少 file_url/image_url 参数'}
                )
                return
            
            # 获取文件类型
            file_type = params.get('file_type', 'image/jpeg')
            print_source = params.get('print_source', 'unknown')
            priority = params.get('priority', 'normal')
            timeout = params.get('timeout', 30)
            
            # 打印参数
            print_mode = params.get('print_mode', 'standard')
            scale = params.get('scale', 1.0)
            rotation = params.get('rotation', 0)
            contrast = params.get('contrast', 0)
            brightness = params.get('brightness', 0)
            wait_for_result = params.get('wait_for_result', True)
            
            self.get_logger().info(f"发送打印命令")
            self.get_logger().info(f"文件URL: {file_url}")
            self.get_logger().info(f"文件类型: {file_type}")
            self.get_logger().info(f"打印来源: {print_source}")
            self.get_logger().info(f"优先级: {priority}")
            self.get_logger().info(f"打印参数: mode={print_mode}, scale={scale}")
            
            # 发布到打印机话题
            # 蓝牙打印机期望直接的 URL 字符串
            msg = String()
            msg.data = file_url  # 直接发送 URL
            self.print_command_pub.publish(msg)
            
            self.get_logger().info(f"已发送打印命令到 /printer/print: {file_url}")
            
            # 可选：同时发布结构化消息到 /printer/command 用于其他组件
            print_cmd = {
                'command': 'print_file',
                'command_id': command_id,
                'file_url': file_url,
                'file_type': file_type,
                'print_source': print_source,
                'priority': priority,
                'timeout': timeout,
                'options': {
                    'print_mode': print_mode,
                    'scale': scale,
                    'rotation': rotation,
                    'contrast': contrast,
                    'brightness': brightness
                },
                'timestamp': datetime.now().isoformat(),
                'wait_for_result': wait_for_result
            }
            
            # 发布到 /printer/command 用于其他需要结构化数据的组件
            cmd_msg = String()
            cmd_msg.data = json.dumps(print_cmd)
            # 检查是否有 command_pub，如果没有可以创建一个
            if hasattr(self, 'print_structured_pub'):
                self.print_structured_pub.publish(cmd_msg)
            
            # 如果不需要等待结果，立即返回成功
            if not wait_for_result:
                self.ws_client.send_command_response_sync(
                    command_id=command_id,
                    command='print',
                    status='success',
                    result={
                        'status': 'queued',
                        'message': '打印任务已加入队列',
                        'file_type': file_type,
                        'priority': priority
                    }
                )
            
        except Exception as e:
            self.get_logger().error(f"处理打印指令失败: {e}")
            self.ws_client.send_command_response_sync(
                command_id=command_id,
                command='print',
                status='failed',
                result={'error': str(e)}
            )
    
    def _on_printer_status(self, msg: String):
        """处理打印机状态回调"""
        try:
            status = json.loads(msg.data)
            command_id = status.get('command_id')
            print_status = status.get('status')
            message = status.get('message', '')
            
            self.get_logger().info(f"打印机状态: {print_status} - {message}")
            
            # 如果有关联的命令ID，发送命令响应
            if command_id:
                if print_status == 'completed':
                    self.ws_client.send_command_response_sync(
                        command_id=command_id,
                        command='print',
                        status='success',
                        result={
                            'status': 'completed',
                            'message': message,
                            'completed_at': datetime.now().isoformat()
                        }
                    )
                elif print_status == 'failed':
                    self.ws_client.send_command_response_sync(
                        command_id=command_id,
                        command='print',
                        status='failed',
                        result={
                            'error': message,
                            'failed_at': datetime.now().isoformat()
                        }
                    )
                elif print_status == 'processing':
                    # 可以在这里发送进度更新（如果需要）
                    pass
            
            # 更新状态缓存
            self._status_cache['printer_status'] = print_status
            self._status_cache['printer_message'] = message
            self._status_cache['printer_last_update'] = datetime.now().isoformat()
            
        except json.JSONDecodeError as e:
            self.get_logger().error(f"解析打印机状态失败: {e}")
        except Exception as e:
            self.get_logger().error(f"处理打印机状态失败: {e}")
    
    def _on_status_timer(self):
        """定时上报状态"""
        if not self.ws_client.state.is_connected:
            return
        
        if not self._status_cache:
            return
        
        self._send_status_update()
    
    def _send_status_update(self):
        """发送状态更新到服务器"""
        try:
            # 添加时间戳
            status_data = {
                **self._status_cache,
                'timestamp': datetime.now().isoformat(),
                'robot_time': self.get_clock().now().to_msg().sec
            }
            
            self.ws_client.send_status_update_sync(
                status=status_data,
                require_ack=False
            )
            
            self.get_logger().debug(f"状态已更新: {status_data}")
            
        except Exception as e:
            self.get_logger().error(f"发送状态更新失败: {e}")
    
    def _on_connection_timer(self):
        """检查连接状态"""
        is_connected = self.ws_client.state.is_connected
        
        # 发布连接状态
        msg = Bool()
        msg.data = is_connected
        self.connection_status_pub.publish(msg)
    
    def _request_config(self):
        """请求配置信息"""
        try:
            message = {
                'type': MessageType.CONFIG_REQUEST.value,
                'aipet_id': self.ws_client._aipet_id
            }
            self.ws_client.send_sync(message)
        except Exception as e:
            self.get_logger().error(f"请求配置失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取节点统计信息"""
        return {
            'websocket': self.ws_client.get_stats(),
            'status_cache': self._status_cache
        }
    
    def destroy_node(self):
        """销毁节点"""
        self.get_logger().info("正在销毁 WebSocket 节点...")
        self.ws_client.stop()
        super().destroy_node()


def main(args=None):
    """主函数"""
    rclpy.init(args=args)
    
    node = WebSocketNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("收到中断信号")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
