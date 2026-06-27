# -*- coding: utf-8 -*-
"""
WebSocket 消息处理器集合
提供常用的消息处理器实现
"""

import json
from typing import Dict, Any, Callable
from abc import ABC, abstractmethod
from datetime import datetime

import rclpy
from std_msgs.msg import String, Bool, Float32
from geometry_msgs.msg import Pose, Vector3
from sensor_msgs.msg import BatteryState


class BaseMessageHandler(ABC):
    """消息处理器基类"""
    
    def __init__(self, node: rclpy.node.Node):
        self.node = node
        self.logger = node.get_logger()
    
    @abstractmethod
    def handle(self, message: Dict[str, Any]):
        """处理消息"""
        pass
    
    def publish_json(self, topic: str, data: Dict[str, Any]):
        """发布 JSON 数据到话题"""
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        # 注意：需要子类实现具体的发布逻辑
        self.logger.debug(f"发布到 {topic}: {data}")


class ServerCommandHandler(BaseMessageHandler):
    """
    服务端指令处理器
    
    处理来自服务器的控制指令，如：
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
    - print: 打印文件（新增）
    """
    
    def __init__(self, node: rclpy.node.Node, command_callback: Callable = None):
        super().__init__(node)
        self.command_callback = command_callback
        
        # 创建发布者
        self.command_pub = node.create_publisher(
            String, 
            '/robot/command', 
            10
        )
        
        # 创建打印命令发布者 - 用于向 printer 节点发送打印命令
        self.print_command_pub = node.create_publisher(
            String,
            '/server/print_command',
            10
        )
    
    def handle(self, message: Dict[str, Any]):
        """处理服务端指令"""
        command = message.get('command')
        command_id = message.get('command_id')
        params = message.get('command_params', {})
        
        self.logger.info(f"处理服务端指令: {command} (ID: {command_id})")
        self.logger.info(f"DEBUG - 完整消息: {json.dumps(message, ensure_ascii=False)}")
        self.logger.info(f"DEBUG - 参数: {json.dumps(params, ensure_ascii=False)}")
        
        # 特殊处理打印命令（直接方式）
        if command == 'print':
            return self._handle_print_command(message, command_id, params)
        
        # 兼容方案：检测伪装成 reminder 的打印命令
        # 当服务器未部署 PRINT 类型时，使用 reminder + 特殊标记传递打印信息
        if command == 'reminder':
            reminder_data = params.get('reminder_data', {})
            # 检测打印标记：eventDescription == "print"
            if reminder_data.get('eventDescription') == 'print':
                self.logger.info("检测到伪装成 reminder 的打印命令")
                # 构造打印参数
                print_params = {
                    'file_url': reminder_data.get('eventTimeStr', ''),  # URL 放在 eventTimeStr
                    'file_type': reminder_data.get('rawTimeString', '')  # 文件类型放在 rawTimeString
                }
                return self._handle_print_command(message, command_id, print_params)
        
        # 发布到 ROS 话题
        cmd_data = {
            'command': command,
            'command_id': command_id,
            'params': params,
            'timestamp': datetime.now().isoformat(),
            'raw_message': message
        }
        
        msg = String()
        msg.data = json.dumps(cmd_data, ensure_ascii=False)
        self.command_pub.publish(msg)
        
        # 调用回调函数（如果提供）
        if self.command_callback:
            try:
                result = self.command_callback(command, command_id, params)
                return result
            except Exception as e:
                self.logger.error(f"命令回调执行失败: {e}")
        
        return {'status': 'published', 'command': command}
    
    def _handle_print_command(self, message: Dict[str, Any], command_id: str, params: Dict[str, Any]):
        """处理打印命令
        
        从服务器接收到的打印命令格式:
        {
            "command": "print",
            "command_id": "xxx",
            "command_params": {
                "file_url": "https://cdn.52wana.com/...",
                "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
        }
        """
        try:
            file_url = params.get('file_url', '')
            file_type = params.get('file_type', '')
            
            if not file_url:
                self.logger.error("打印命令缺少 file_url 参数")
                return {
                    'status': 'error',
                    'command': 'print',
                    'command_id': command_id,
                    'error': '缺少文件URL'
                }
            
            self.logger.info(f"📄 收到打印命令")
            self.logger.info(f"📄 文件URL: {file_url}")
            self.logger.info(f"📄 文件类型: {file_type}")
            self.logger.info(f"📄 命令ID: {command_id}")
            
            # 构建打印命令数据
            print_data = {
                'file_url': file_url,
                'file_type': file_type,
                'command_id': command_id,
                'timestamp': datetime.now().isoformat()
            }
            
            # 发布到打印话题
            print_msg = String()
            print_msg.data = json.dumps(print_data, ensure_ascii=False)
            self.print_command_pub.publish(print_msg)
            
            self.logger.info(f"📄 打印命令已发布到话题: /server/print_command")
            
            # 同时发布到通用命令话题
            cmd_data = {
                'command': 'print',
                'command_id': command_id,
                'params': params,
                'timestamp': datetime.now().isoformat(),
                'raw_message': message
            }
            
            msg = String()
            msg.data = json.dumps(cmd_data, ensure_ascii=False)
            self.command_pub.publish(msg)
            
            return {
                'status': 'queued',
                'command': 'print',
                'command_id': command_id,
                'file_url': file_url
            }
            
        except Exception as e:
            self.logger.error(f"处理打印命令失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'command': 'print',
                'command_id': command_id,
                'error': str(e)
            }
    
    def get_command_description(self, command: str) -> str:
        """获取命令描述"""
        descriptions = {
            'wake_up': '唤醒机器人',
            'sleep': '机器人进入休眠',
            'play_sound': '播放指定声音',
            'set_mood': '设置心情状态',
            'restart': '重启机器人',
            'update_config': '更新配置信息',
            'upload_status': '上传当前状态',
            'set_volume': '设置音量',
            'set_brightness': '设置亮度',
            'take_photo': '拍照',
            'start_recording': '开始录音',
            'stop_recording': '停止录音',
            'factory_reset': '恢复出厂设置',
            'enter_maintenance': '进入维护模式',
            'exit_maintenance': '退出维护模式',
            'print': '打印文件',  # 新增打印命令描述
        }
        return descriptions.get(command, f'未知指令: {command}')


class ChatResponseHandler(BaseMessageHandler):
    """
    聊天响应处理器
    
    处理来自服务器的聊天响应消息
    """
    
    def __init__(self, node: rclpy.node.Node, response_callback: Callable = None):
        super().__init__(node)
        self.response_callback = response_callback
        
        # 创建发布者
        self.response_pub = node.create_publisher(
            String,
            '/websocket/chat_response',
            10
        )
    
    def handle(self, message: Dict[str, Any]):
        """处理聊天响应"""
        data = message.get('data', {})
        content = data.get('content', '')
        
        self.logger.info(f"收到聊天响应: {content[:50]}...")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        self.response_pub.publish(msg)
        
        # 调用回调函数（如果提供）
        if self.response_callback:
            try:
                self.response_callback(data)
            except Exception as e:
                self.logger.error(f"聊天回调执行失败: {e}")


class ConfigResponseHandler(BaseMessageHandler):
    """
    配置响应处理器
    
    处理来自服务器的配置响应消息
    """
    
    def __init__(self, node: rclpy.node.Node, config_callback: Callable = None):
        super().__init__(node)
        self.config_callback = config_callback
        
        # 创建发布者
        self.config_pub = node.create_publisher(
            String,
            '/websocket/config_response',
            10
        )
    
    def handle(self, message: Dict[str, Any]):
        """处理配置响应"""
        data = message.get('data', {})
        
        self.logger.info(f"收到配置响应: {data}")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        self.config_pub.publish(msg)
        
        # 调用回调函数（如果提供）
        if self.config_callback:
            try:
                self.config_callback(data)
            except Exception as e:
                self.logger.error(f"配置回调执行失败: {e}")


class NotificationHandler(BaseMessageHandler):
    """
    通知处理器
    
    处理来自服务器的通知消息
    """
    
    def __init__(self, node: rclpy.node.Node, notification_callback: Callable = None):
        super().__init__(node)
        self.notification_callback = notification_callback
        
        # 创建发布者
        self.notification_pub = node.create_publisher(
            String,
            '/websocket/notification',
            10
        )
    
    def handle(self, message: Dict[str, Any]):
        """处理通知消息"""
        data = message.get('data', {})
        notification_type = data.get('notification_type', 'unknown')
        title = data.get('title', '')
        content = data.get('content', '')
        
        self.logger.info(f"收到通知 [{notification_type}]: {title} - {content[:50]}...")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        self.notification_pub.publish(msg)
        
        # 调用回调函数（如果提供）
        if self.notification_callback:
            try:
                self.notification_callback(data)
            except Exception as e:
                self.logger.error(f"通知回调执行失败: {e}")


class AppResponseHandler(BaseMessageHandler):
    """
    APP 业务请求响应处理器
    
    处理来自服务器的 APP 业务请求响应
    """
    
    def __init__(self, node: rclpy.node.Node, app_callback: Callable = None):
        super().__init__(node)
        self.app_callback = app_callback
        
        # 创建发布者
        self.app_response_pub = node.create_publisher(
            String,
            '/websocket/app_response',
            10
        )
    
    def handle(self, message: Dict[str, Any]):
        """处理 APP 响应"""
        data = message.get('data', {})
        message_type = message.get('type', 'unknown')
        
        self.logger.info(f"收到 APP 响应 [{message_type}]")
        
        # 发布到 ROS 话题
        msg = String()
        msg.data = json.dumps(message, ensure_ascii=False)
        self.app_response_pub.publish(msg)
        
        # 调用回调函数（如果提供）
        if self.app_callback:
            try:
                self.app_callback(message_type, data)
            except Exception as e:
                self.logger.error(f"APP 回调执行失败: {e}")


class ErrorHandler(BaseMessageHandler):
    """
    错误消息处理器
    
    处理来自服务器的错误消息
    """
    
    def __init__(self, node: rclpy.node.Node, error_callback: Callable = None):
        super().__init__(node)
        self.error_callback = error_callback
    
    def handle(self, message: Dict[str, Any]):
        """处理错误消息"""
        data = message.get('data', {})
        error_code = data.get('error_code', 'UNKNOWN')
        error_message = data.get('error_message', 'Unknown error')
        
        self.logger.error(f"收到错误 [{error_code}]: {error_message}")
        
        # 调用回调函数（如果提供）
        if self.error_callback:
            try:
                self.error_callback(error_code, error_message, data)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {e}")


class MessageHandlerRegistry:
    """
    消息处理器注册表
    
    管理所有消息处理器的注册和分发
    """
    
    def __init__(self, node: rclpy.node.Node):
        self.node = node
        self.logger = node.get_logger()
        self._handlers: Dict[str, BaseMessageHandler] = {}
    
    def register(self, message_type: str, handler: BaseMessageHandler):
        """注册消息处理器"""
        self._handlers[message_type] = handler
        self.logger.info(f"注册消息处理器: {message_type}")
    
    def unregister(self, message_type: str):
        """注销消息处理器"""
        if message_type in self._handlers:
            del self._handlers[message_type]
            self.logger.info(f"注销消息处理器: {message_type}")
    
    def handle(self, message: Dict[str, Any]):
        """分发消息到对应的处理器"""
        msg_type = message.get('type', 'unknown')
        handler = self._handlers.get(msg_type)
        
        if handler:
            try:
                return handler.handle(message)
            except Exception as e:
                self.logger.error(f"消息处理失败 [{msg_type}]: {e}")
        else:
            self.logger.debug(f"未找到消息处理器: {msg_type}")
    
    def create_default_handlers(self, 
                                command_callback: Callable = None,
                                chat_callback: Callable = None,
                                config_callback: Callable = None,
                                notification_callback: Callable = None,
                                app_callback: Callable = None,
                                error_callback: Callable = None):
        """创建默认的消息处理器"""
        self.register('server_command', ServerCommandHandler(self.node, command_callback))
        self.register('chat', ChatResponseHandler(self.node, chat_callback))
        self.register('config_request', ConfigResponseHandler(self.node, config_callback))
        self.register('notification', NotificationHandler(self.node, notification_callback))
        self.register('app_response', AppResponseHandler(self.node, app_callback))
        self.register('error', ErrorHandler(self.node, error_callback))


# 便捷函数
def create_standard_handlers(node: rclpy.node.Node,
                            command_callback: Callable = None,
                            chat_callback: Callable = None) -> MessageHandlerRegistry:
    """
    创建标准的消息处理器集合
    
    Args:
        node: ROS 2 节点
        command_callback: 服务端指令回调函数
        chat_callback: 聊天响应回调函数
        
    Returns:
        MessageHandlerRegistry: 处理器注册表
    """
    registry = MessageHandlerRegistry(node)
    registry.create_default_handlers(
        command_callback=command_callback,
        chat_callback=chat_callback
    )
    return registry
