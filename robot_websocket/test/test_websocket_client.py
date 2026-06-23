# -*- coding: utf-8 -*-
"""
WebSocket 客户端测试
"""

import unittest
import time
import json
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# 导入被测模块
from robot_websocket.websocket_client import WebSocketClient, WebSocketConfig, MessageType


class TestWebSocketConfig(unittest.TestCase):
    """测试 WebSocketConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = WebSocketConfig()
        self.assertEqual(config.base_url, "http://localhost:8000")
        self.assertEqual(config.serial_number, "6976f96f-bc80-56e3-9b27-13d12cdde9d9")
        self.assertEqual(config.heartbeat_interval, 30)
        self.assertEqual(config.reconnect_delay, 3)
        self.assertEqual(config.max_reconnect_attempts, 10)
        self.assertTrue(config.enable_auto_reconnect)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = WebSocketConfig(
            base_url="http://192.168.1.100:8000",
            serial_number="TEST123",
            heartbeat_interval=60
        )
        self.assertEqual(config.base_url, "http://192.168.1.100:8000")
        self.assertEqual(config.serial_number, "TEST123")
        self.assertEqual(config.heartbeat_interval, 60)


class TestMessageType(unittest.TestCase):
    """测试 MessageType 枚举"""
    
    def test_message_types(self):
        """测试消息类型"""
        self.assertEqual(MessageType.AUTH.value, "auth")
        self.assertEqual(MessageType.HEARTBEAT.value, "heartbeat")
        self.assertEqual(MessageType.CHAT.value, "chat")
        self.assertEqual(MessageType.STATUS_UPDATE.value, "status_update")
        self.assertEqual(MessageType.COMMAND_RESPONSE.value, "command_response")
        self.assertEqual(MessageType.SERVER_COMMAND.value, "server_command")


class TestWebSocketClient(unittest.TestCase):
    """测试 WebSocketClient"""
    
    def setUp(self):
        """测试前准备"""
        self.config = WebSocketConfig(
            base_url="http://localhost:8000",
            serial_number="TEST123"
        )
        self.client = WebSocketClient(self.config)
    
    def tearDown(self):
        """测试后清理"""
        if self.client._running:
            self.client.stop()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertFalse(self.client.state.is_connected)
        self.assertFalse(self.client.state.is_authenticated)
        self.assertEqual(self.client.state.reconnect_count, 0)
        self.assertEqual(self.client.config.serial_number, "TEST123")
    
    def test_message_handler_registration(self):
        """测试消息处理器注册"""
        handler_called = [False]
        
        def test_handler(message):
            handler_called[0] = True
        
        self.client.on("test_type", test_handler)
        
        # 验证处理器已注册
        self.assertIn("test_type", self.client._message_handlers)
        
        # 测试移除处理器
        self.client.off("test_type")
        self.assertNotIn("test_type", self.client._message_handlers)
    
    def test_generate_message_id(self):
        """测试消息ID生成"""
        msg_id1 = self.client._generate_message_id()
        msg_id2 = self.client._generate_message_id()
        
        # 验证ID不为空
        self.assertTrue(msg_id1)
        self.assertTrue(msg_id2)
        
        # 验证ID唯一性
        self.assertNotEqual(msg_id1, msg_id2)
        
        # 验证格式
        self.assertTrue(msg_id1.startswith("msg_"))
    
    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.client.get_stats()
        
        self.assertIn("is_connected", stats)
        self.assertIn("is_authenticated", stats)
        self.assertIn("reconnect_count", stats)
        self.assertIn("messages_sent", stats)
        self.assertIn("messages_received", stats)
        
        self.assertFalse(stats["is_connected"])
        self.assertEqual(stats["messages_sent"], 0)


class TestWebSocketClientAsync(unittest.IsolatedAsyncioTestCase):
    """异步测试 WebSocketClient"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.config = WebSocketConfig(
            base_url="http://localhost:8000",
            serial_number="TEST123"
        )
        self.client = WebSocketClient(self.config)
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        await self.client.disconnect()
    
    async def test_handle_ack(self):
        """测试 ACK 处理"""
        import asyncio
        
        # 创建 pending ACK
        message_id = "test_msg_123"
        future = asyncio.get_event_loop().create_future()
        self.client._pending_acks[message_id] = future
        
        # 发送 ACK 消息
        ack_message = {
            "type": "ack",
            "data": {"message_id": message_id}
        }
        await self.client._handle_ack(ack_message)
        
        # 验证 future 已完成
        self.assertTrue(future.done())
        self.assertNotIn(message_id, self.client._pending_acks)
    
    async def test_handle_server_command(self):
        """测试服务端指令处理"""
        command_msg = {
            "type": "server_command",
            "command": "wake_up",
            "command_id": "cmd_123",
            "command_params": {"force": True}
        }
        
        # 处理指令（不应抛出异常）
        await self.client._handle_server_command(command_msg)
    
    async def test_handle_error_message(self):
        """测试错误消息处理"""
        error_msg = {
            "type": "error",
            "data": {
                "error_code": "TEST_ERROR",
                "error_message": "Test error message"
            }
        }
        
        # 处理错误消息（不应抛出异常）
        await self.client._handle_error_message(error_msg)


class TestIntegration(unittest.TestCase):
    """集成测试（需要实际服务器）"""
    
    @unittest.skip("需要实际服务器")
    def test_connect_and_disconnect(self):
        """测试连接和断开"""
        config = WebSocketConfig(
            base_url="http://localhost:8000",
            serial_number="6976f96f-bc80-56e3-9b27-13d12cdde9d9"
        )
        client = WebSocketClient(config)
        
        # 启动客户端
        client.start()
        time.sleep(2)  # 等待连接
        
        # 验证连接状态
        # 注意：这取决于服务器是否可用
        stats = client.get_stats()
        print(f"Connection stats: {stats}")
        
        # 停止客户端
        client.stop()


if __name__ == '__main__':
    unittest.main()
