# -*- coding: utf-8 -*-
"""
AI宠物机器人 WebSocket 客户端
用于与后端服务器进行实时通信
"""

import asyncio
import json
import time
import uuid
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import rclpy
from rclpy.node import Node


class MessageType(Enum):
    """WebSocket 消息类型枚举"""
    AUTH = "auth"
    HEARTBEAT = "heartbeat"
    CONFIG_REQUEST = "config_request"
    STATUS_UPDATE = "status_update"
    CHAT = "chat"
    COMMAND_RESPONSE = "command_response"
    NOTIFICATION = "notification"
    ERROR = "error"
    ACK = "ack"
    SERVER_COMMAND = "server_command"
    APP_REQUEST = "app_request"


@dataclass
class WebSocketConfig:
    """WebSocket 配置"""
    base_url: str = "http://localhost:8000"
    serial_number: str = "6976f96f-bc80-56e3-9b27-13d12cdde9d9"
    heartbeat_interval: int = 30  # 心跳间隔（秒）
    reconnect_delay: int = 3  # 重连延迟（秒）
    max_reconnect_attempts: int = 10  # 最大重连次数
    ack_timeout: int = 5  # ACK 超时时间（秒）
    enable_auto_reconnect: bool = True  # 是否启用自动重连
    connection_timeout: int = 10  # 连接超时（秒）


@dataclass
class ConnectionState:
    """连接状态"""
    is_connected: bool = False
    is_authenticated: bool = False
    last_heartbeat: Optional[float] = None
    connection_time: Optional[datetime] = None
    reconnect_count: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors_count: int = 0


class WebSocketClient:
    """
    AI宠物机器人 WebSocket 客户端
    
    功能特性：
    1. 自动获取认证 Token
    2. WebSocket 连接管理
    3. 自动心跳保持
    4. 消息发送与接收
    5. ACK 确认机制
    6. 自动重连
    7. 完整的错误处理
    """
    
    def __init__(self, config: WebSocketConfig = None, logger=None):
        self.config = config or WebSocketConfig()
        self.state = ConnectionState()
        self.logger = logger or rclpy.logging.get_logger('websocket_client')
        
        # WebSocket 连接
        self._ws = None
        self._token: Optional[str] = None
        self._aipet_id: Optional[int] = None
        
        # 线程和事件循环
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        
        # 任务管理
        self._heartbeat_task = None
        self._receive_task = None
        
        # 消息处理
        self._message_handlers: Dict[str, Callable] = {}
        self._pending_acks: Dict[str, asyncio.Future] = {}
        self._lock = threading.Lock()
        
        # 注册默认消息处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认消息处理器"""
        self.on(MessageType.ACK.value, self._handle_ack)
        self.on(MessageType.HEARTBEAT.value, self._handle_heartbeat_response)
        self.on(MessageType.SERVER_COMMAND.value, self._handle_server_command)
        self.on(MessageType.ERROR.value, self._handle_error_message)
    
    # ==================== 连接管理 ====================
    
    def start(self):
        """在后台线程启动 WebSocket 客户端"""
        if self._thread and self._thread.is_alive():
            self.logger.warning("WebSocket 客户端已在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info("WebSocket 客户端线程已启动")
    
    def stop(self):
        """停止 WebSocket 客户端"""
        self._running = False
        
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.disconnect(), self._loop)
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        self.logger.info("WebSocket 客户端已停止")
    
    def _run(self):
        """后台线程运行的主函数"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            self.logger.error(f"WebSocket 主循环异常: {e}")
        finally:
            self._loop.close()
    
    async def _main_loop(self):
        """主循环"""
        while self._running:
            try:
                connected = await self.connect()
                if connected:
                    # 连接成功，等待直到断开
                    while self._running and self.state.is_connected:
                        await asyncio.sleep(1)
                
                if not self._running:
                    break
                
                # 尝试重连
                if self.config.enable_auto_reconnect:
                    await self._reconnect()
                else:
                    break
                    
            except Exception as e:
                self.logger.error(f"主循环异常: {e}")
                await asyncio.sleep(self.config.reconnect_delay)
    
    async def connect(self) -> bool:
        """
        建立 WebSocket 连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 延迟导入 websockets，避免在导入时出错
            import websockets
            
            self.logger.info(f"正在连接服务器: {self.config.base_url}")
            
            # 1. 获取认证 Token
            if not await self._get_token():
                return False
            
            # 2. 建立 WebSocket 连接
            ws_url = self.config.base_url.replace(
                "http://", "ws://"
            ).replace("https://", "wss://")
            uri = f"{ws_url}/api/v1/aipet/ws/{self.config.serial_number}"
            
            self.logger.info(f"正在连接 WebSocket: {uri}")
            self._ws = await websockets.connect(
                uri, 
                ping_interval=None,  # 我们使用自己的心跳机制
                close_timeout=5
            )
            
            self.state.is_connected = True
            self.state.connection_time = datetime.now()
            self.logger.info("WebSocket 连接已建立")
            
            # 3. 启动接收循环
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # 4. 发送认证消息
            if not await self._authenticate():
                await self.disconnect()
                return False
            
            # 5. 启动心跳
            self._start_heartbeat()
            
            # 6. 重置重连计数
            self.state.reconnect_count = 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.state.errors_count += 1
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.logger.info("正在断开连接...")
        self.state.is_connected = False
        self.state.is_authenticated = False
        
        # 取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        # 取消接收任务
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        
        # 关闭 WebSocket 连接
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        
        # 清理待处理的 ACK
        for future in list(self._pending_acks.values()):
            if not future.done():
                future.cancel()
        self._pending_acks.clear()
        
        self.logger.info("连接已断开")
    
    async def _reconnect(self):
        """自动重连"""
        if not self.config.enable_auto_reconnect:
            self.logger.info("自动重连已禁用")
            return False
        
        if self.state.reconnect_count >= self.config.max_reconnect_attempts:
            self.logger.error(f"重连次数达到上限 ({self.config.max_reconnect_attempts})")
            return False
        
        self.state.reconnect_count += 1
        delay = self.config.reconnect_delay * min(self.state.reconnect_count, 5)
        
        self.logger.info(f"{delay}秒后进行第 {self.state.reconnect_count} 次重连...")
        await asyncio.sleep(delay)
        
        # 断开现有连接
        await self.disconnect()
        
        return True  # 返回True让主循环再次尝试连接
    
    # ==================== 认证 ====================
    
    async def _get_token(self) -> bool:
        """获取认证 Token"""
        try:
            import aiohttp
            
            url = f"{self.config.base_url}/api/v1/aipet/ws/auth/{self.config.serial_number}"
            
            timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self.logger.error(f"获取 Token 失败: HTTP {response.status}")
                        return False
                    
                    data = await response.json()
                    if data.get("code") != 200:
                        self.logger.error(f"获取 Token 失败: {data.get('msg')}")
                        return False
                    
                    self._token = data["data"]
                    self.logger.info(f"获取 Token 成功")
                    return True
                    
        except Exception as e:
            self.logger.error(f"获取 Token 异常: {e}")
            return False
    
    async def _authenticate(self) -> bool:
        """发送认证消息"""
        try:
            self.logger.info("正在发送认证消息...")
            
            auth_message = {
                "type": MessageType.AUTH.value,
                "access_token": self._token
            }
            
            # 发送认证消息并等待响应
            response = await self.send_and_wait_response(
                auth_message, 
                expected_type=MessageType.AUTH.value,
                timeout=10
            )
            
            if response and response.get("success"):
                self.state.is_authenticated = True
                self._aipet_id = response.get("data", {}).get("id")
                self.logger.info(f"认证成功! AI宠物ID: {self._aipet_id}")
                return True
            else:
                error_msg = response.get("message") if response else "无响应"
                self.logger.error(f"认证失败: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"认证异常: {e}")
            return False
    
    # ==================== 消息发送 ====================
    
    def send_sync(self, message: Dict[str, Any]) -> bool:
        """
        同步方式发送消息（线程安全）
        
        Args:
            message: 消息字典
            
        Returns:
            bool: 发送是否成功
        """
        if not self._loop:
            return False
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.send(message), 
                self._loop
            )
            return future.result(timeout=self.config.ack_timeout)
        except Exception as e:
            self.logger.error(f"同步发送消息失败: {e}")
            return False
    
    async def send(self, message: Dict[str, Any]) -> bool:
        """
        发送消息
        
        Args:
            message: 消息字典
            
        Returns:
            bool: 发送是否成功
        """
        if not self._ws or not self.state.is_connected:
            self.logger.warning("WebSocket 未连接，无法发送消息")
            return False
        
        try:
            message_json = json.dumps(message, ensure_ascii=False)
            await self._ws.send(message_json)
            self.state.messages_sent += 1
            
            msg_type = message.get("type", "unknown")
            self.logger.debug(f"发送消息 [{msg_type}]")
            return True
            
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            self.state.errors_count += 1
            return False
    
    async def send_with_ack(
        self, 
        message: Dict[str, Any], 
        timeout: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        发送消息并等待 ACK 确认
        
        Args:
            message: 消息字典
            timeout: 超时时间（秒）
            
        Returns:
            ACK 响应或 None
        """
        timeout = timeout or self.config.ack_timeout
        
        # 生成消息 ID
        if "message_id" not in message:
            message["message_id"] = self._generate_message_id()
        message["require_ack"] = True
        
        message_id = message["message_id"]
        future = asyncio.get_event_loop().create_future()
        
        with self._lock:
            self._pending_acks[message_id] = future
        
        try:
            if not await self.send(message):
                with self._lock:
                    self._pending_acks.pop(message_id, None)
                return None
            
            self.logger.debug(f"等待 ACK: {message_id}")
            ack_response = await asyncio.wait_for(future, timeout=timeout)
            self.logger.debug(f"收到 ACK: {message_id}")
            return ack_response
            
        except asyncio.TimeoutError:
            self.logger.warning(f"ACK 超时: {message_id}")
            with self._lock:
                self._pending_acks.pop(message_id, None)
            return None
        except Exception as e:
            self.logger.error(f"等待 ACK 异常: {e}")
            with self._lock:
                self._pending_acks.pop(message_id, None)
            return None
    
    async def send_and_wait_response(
        self,
        message: Dict[str, Any],
        expected_type: str = None,
        timeout: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        发送消息并等待响应
        
        Args:
            message: 消息字典
            expected_type: 期望的响应类型
            timeout: 超时时间（秒）
            
        Returns:
            响应消息或 None
        """
        msg_type = message.get("type", "unknown")
        response_future = asyncio.get_event_loop().create_future()
        
        # 创建临时处理器
        async def temp_handler(response):
            if not response_future.done():
                response_future.set_result(response)
        
        # 注册临时处理器
        expected = expected_type or msg_type
        self.on(expected, temp_handler)
        
        try:
            if not await self.send(message):
                return None
            
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.logger.warning(f"等待响应超时: {expected}")
            return None
        finally:
            # 移除临时处理器
            self.off(expected)
    
    # ==================== 特定消息类型发送 ====================
    
    def send_heartbeat_sync(self) -> bool:
        """同步方式发送心跳"""
        return self.send_sync({"type": MessageType.HEARTBEAT.value})
    
    async def send_heartbeat(self) -> bool:
        """发送心跳"""
        return await self.send({"type": MessageType.HEARTBEAT.value})
    
    def send_chat_sync(self, content: str, chat_type: str = "text", require_ack: bool = False) -> Optional[Dict]:
        """
        同步方式发送聊天消息
        
        Args:
            content: 消息内容
            chat_type: 消息类型
            require_ack: 是否需要确认
            
        Returns:
            如果 require_ack 为 True，返回 ACK 响应
        """
        message = {
            "type": MessageType.CHAT.value,
            "content": content,
            "chat_type": chat_type
        }
        
        if require_ack:
            if not self._loop:
                return None
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.send_with_ack(message),
                    self._loop
                )
                return future.result(timeout=self.config.ack_timeout)
            except Exception as e:
                self.logger.error(f"发送聊天消息失败: {e}")
                return None
        else:
            return {"success": self.send_sync(message)}
    
    def send_status_update_sync(
        self, 
        status: Dict[str, Any],
        require_ack: bool = False
    ) -> Optional[Dict]:
        """
        同步方式发送状态更新
        
        Args:
            status: 状态数据
            require_ack: 是否需要确认
            
        Returns:
            如果 require_ack 为 True，返回 ACK 响应
        """
        message = {
            "type": MessageType.STATUS_UPDATE.value,
            "status": status
        }
        
        if require_ack:
            if not self._loop:
                return None
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.send_with_ack(message),
                    self._loop
                )
                return future.result(timeout=self.config.ack_timeout)
            except Exception as e:
                self.logger.error(f"发送状态更新失败: {e}")
                return None
        else:
            return {"success": self.send_sync(message)}
    
    def send_command_response_sync(
        self,
        command_id: str,
        command: str,
        status: str = "success",
        result: Dict = None
    ) -> bool:
        """
        同步方式发送指令执行结果
        
        Args:
            command_id: 指令ID
            command: 指令名称
            status: 执行状态
            result: 执行结果
            
        Returns:
            发送是否成功
        """
        message = {
            "type": MessageType.COMMAND_RESPONSE.value,
            "command_id": command_id,
            "command": command,
            "status": status,
            "result": result or {}
        }
        return self.send_sync(message)
    
    def send_error_sync(
        self,
        error_code: str,
        error_message: str,
        error_details: Dict = None
    ) -> bool:
        """
        同步方式发送错误报告
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
            error_details: 错误详情
            
        Returns:
            发送是否成功
        """
        message = {
            "type": MessageType.ERROR.value,
            "error_code": error_code,
            "error_message": error_message,
            "error_details": error_details or {}
        }
        return self.send_sync(message)
    
    def send_app_request_sync(
        self,
        request_type: str,
        params: Dict[str, Any] = None,
        require_ack: bool = True
    ) -> Optional[Dict]:
        """
        同步方式发送APP业务请求
        
        Args:
            request_type: 请求类型
            params: 请求参数
            require_ack: 是否需要确认
            
        Returns:
            响应数据
        """
        message = {
            "type": MessageType.APP_REQUEST.value,
            "request_type": request_type
        }
        if params:
            message.update(params)
        
        if require_ack:
            if not self._loop:
                return None
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.send_and_wait_response(
                        message,
                        expected_type=request_type,
                        timeout=10
                    ),
                    self._loop
                )
                return future.result(timeout=15)
            except Exception as e:
                self.logger.error(f"发送APP请求失败: {e}")
                return None
        else:
            return {"success": self.send_sync(message)}
    
    # ==================== 消息接收与处理 ====================
    
    async def _receive_loop(self):
        """消息接收循环"""
        import websockets
        
        while self._running and self.state.is_connected:
            try:
                if not self._ws:
                    break
                
                message = await self._ws.recv()
                self.state.messages_received += 1
                
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    self.logger.warning(f"收到无效的 JSON: {message[:100]}")
                    
            except websockets.exceptions.ConnectionClosed:
                self.logger.info("WebSocket 连接已关闭")
                break
            except Exception as e:
                if self._running:
                    self.logger.error(f"接收消息异常: {e}")
                break
        
        # 连接断开
        self.state.is_connected = False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """处理收到的消息"""
        msg_type = message.get("type", "unknown")
        
        # 打印收到的消息结构（用于调试）
        self.logger.info(f"收到消息 [{msg_type}] 完整结构:")
        self.logger.info(json.dumps(message, indent=2, ensure_ascii=False))
        
        # 调用注册的处理器
        with self._lock:
            handler = self._message_handlers.get(msg_type)
        
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    # 同步处理器在线程池中运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, handler, message)
            except Exception as e:
                self.logger.error(f"消息处理器异常: {e}")
        else:
            self.logger.warning(f"未找到消息类型 [{msg_type}] 的处理器")
    
    # ==================== 默认消息处理器 ====================
    
    async def _handle_ack(self, message: Dict[str, Any]):
        """处理 ACK 消息"""
        message_id = message.get("data", {}).get("message_id")
        if message_id:
            with self._lock:
                future = self._pending_acks.pop(message_id, None)
            if future and not future.done():
                future.set_result(message)
    
    async def _handle_heartbeat_response(self, message: Dict[str, Any]):
        """处理心跳响应"""
        self.state.last_heartbeat = time.time()
        server_time = message.get("data", {}).get("server_time")
        self.logger.debug(f"心跳响应，服务器时间: {server_time}")
    
    async def _handle_server_command(self, message: Dict[str, Any]):
        """处理服务端指令"""
        command = message.get("command")
        command_id = message.get("command_id")
        params = message.get("command_params", {})
        
        self.logger.info(f"收到服务端指令: {command} (ID: {command_id})")
        
        # 发送 ACK（如果要求）
        if message.get("require_ack") and message.get("message_id"):
            await self.send({
                "type": MessageType.ACK.value,
                "message_id": message["message_id"]
            })
    
    async def _handle_error_message(self, message: Dict[str, Any]):
        """处理错误消息"""
        error_code = message.get("data", {}).get("error_code")
        error_message = message.get("data", {}).get("error_message")
        self.logger.warning(f"收到错误消息: [{error_code}] {error_message}")
    
    # ==================== 心跳管理 ====================
    
    def _start_heartbeat(self):
        """启动心跳任务"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.logger.info(f"心跳任务已启动，间隔: {self.config.heartbeat_interval}秒")
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running and self.state.is_connected:
            try:
                await self.send_heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"心跳异常: {e}")
                await asyncio.sleep(5)
    
    # ==================== 消息处理器注册 ====================
    
    def on(self, message_type: str, handler: Callable):
        """
        注册消息处理器
        
        Args:
            message_type: 消息类型
            handler: 处理函数（同步或异步）
        """
        with self._lock:
            self._message_handlers[message_type] = handler
    
    def off(self, message_type: str):
        """
        移除消息处理器
        
        Args:
            message_type: 消息类型
        """
        with self._lock:
            self._message_handlers.pop(message_type, None)
    
    # ==================== 工具方法 ====================
    
    def _generate_message_id(self) -> str:
        """生成唯一消息 ID"""
        return f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            "is_connected": self.state.is_connected,
            "is_authenticated": self.state.is_authenticated,
            "connection_time": self.state.connection_time.isoformat() if self.state.connection_time else None,
            "reconnect_count": self.state.reconnect_count,
            "messages_sent": self.state.messages_sent,
            "messages_received": self.state.messages_received,
            "errors_count": self.state.errors_count,
            "pending_acks": len(self._pending_acks)
        }
