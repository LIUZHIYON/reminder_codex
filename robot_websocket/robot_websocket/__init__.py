# -*- coding: utf-8 -*-
"""
AI宠物机器人 WebSocket 客户端模块

提供与后端服务器的实时通信功能
"""

from .websocket_client import WebSocketClient, WebSocketConfig, MessageType
from .websocket_node import WebSocketNode
from .message_handlers import (
    BaseMessageHandler,
    ServerCommandHandler,
    ChatResponseHandler,
    ConfigResponseHandler,
    NotificationHandler,
    AppResponseHandler,
    ErrorHandler,
    MessageHandlerRegistry,
    create_standard_handlers,
)

__all__ = [
    # 客户端类
    'WebSocketClient',
    'WebSocketConfig', 
    'MessageType',
    'WebSocketNode',
    # 处理器类
    'BaseMessageHandler',
    'ServerCommandHandler',
    'ChatResponseHandler',
    'ConfigResponseHandler',
    'NotificationHandler',
    'AppResponseHandler',
    'ErrorHandler',
    'MessageHandlerRegistry',
    'create_standard_handlers',
]

__version__ = '0.1.0'
