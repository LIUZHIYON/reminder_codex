# -*- coding: utf-8 -*-
"""
WebSocket 客户端使用示例

展示了如何使用 WebSocketClient 与后端服务器通信
"""

import time
import json
import signal
import sys

# 导入 WebSocket 客户端
from robot_websocket.websocket_client import WebSocketClient, WebSocketConfig


class RobotWebSocketDemo:
    """机器人 WebSocket 演示"""
    
    def __init__(self):
        """初始化"""
        # 创建配置
        self.config = WebSocketConfig(
            base_url="http://localhost:8000",
            serial_number="6976f96f-bc80-56e3-9b27-13d12cdde9d9",
            heartbeat_interval=30,
            reconnect_delay=3,
            max_reconnect_attempts=10,
            enable_auto_reconnect=True
        )
        
        # 创建客户端
        self.client = WebSocketClient(self.config)
        
        # 注册自定义消息处理器
        self._register_handlers()
        
        # 运行标志
        self.running = False
    
    def _register_handlers(self):
        """注册消息处理器"""
        # 处理聊天响应
        self.client.on("chat", self._on_chat_response)
        
        # 处理服务端指令
        self.client.on("server_command", self._on_server_command)
        
        # 处理配置响应
        self.client.on("config_request", self._on_config_response)
    
    def _on_chat_response(self, message):
        """处理聊天响应"""
        content = message.get('data', {}).get('content', '')
        print(f"💬 收到聊天响应: {content}")
    
    def _on_server_command(self, message):
        """处理服务端指令"""
        command = message.get('command')
        command_id = message.get('command_id')
        params = message.get('command_params', {})
        
        print(f"\n📢 收到服务端指令:")
        print(f"   指令: {command}")
        print(f"   指令ID: {command_id}")
        print(f"   参数: {params}")
        
        # 根据指令执行操作
        if command == "wake_up":
            print("   执行: 唤醒机器人")
        elif command == "sleep":
            print("   执行: 机器人进入休眠")
        elif command == "play_sound":
            sound_id = params.get('sound_id')
            print(f"   执行: 播放声音 {sound_id}")
        elif command == "set_mood":
            mood = params.get('mood')
            print(f"   执行: 设置心情为 {mood}")
        else:
            print(f"   执行: 未知指令 {command}")
        
        # 发送指令响应
        self.client.send_command_response_sync(
            command_id=command_id,
            command=command,
            status="success",
            result={"executed_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        )
        print(f"   ✅ 指令响应已发送")
    
    def _on_config_response(self, message):
        """处理配置响应"""
        print(f"\n⚙️ 收到配置响应:")
        print(json.dumps(message.get('data', {}), indent=2, ensure_ascii=False))
    
    def run(self):
        """运行演示"""
        print("=" * 60)
        print("AI宠物机器人 WebSocket 客户端演示")
        print("=" * 60)
        print(f"服务器: {self.config.base_url}")
        print(f"设备序列号: {self.config.serial_number}")
        print("=" * 60)
        
        # 启动客户端
        print("\n🚀 启动 WebSocket 客户端...")
        self.client.start()
        self.running = True
        
        # 等待连接建立
        print("⏳ 等待连接建立...")
        time.sleep(3)
        
        if not self.client.state.is_connected:
            print("❌ 连接失败，请检查服务器是否运行")
            return
        
        print("✅ 连接成功！")
        
        # 演示各种功能
        self._demo_chat()
        self._demo_status_update()
        self._demo_app_request()
        
        # 保持运行，等待服务端指令
        print("\n⏳ 保持连接，等待服务端指令...")
        print("按 Ctrl+C 退出\n")
        
        try:
            while self.running:
                # 打印统计信息
                stats = self.client.get_stats()
                if stats['messages_received'] > 0:
                    print(f"\r📊 发送: {stats['messages_sent']} | "
                          f"接收: {stats['messages_received']} | "
                          f"重连: {stats['reconnect_count']}", 
                          end="", flush=True)
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⛔ 用户中断")
    
    def _demo_chat(self):
        """演示聊天功能"""
        print("\n💬 演示: 发送聊天消息")
        
        # 发送普通聊天消息
        result = self.client.send_chat_sync(
            content="你好，我是AI宠物机器人！",
            chat_type="text",
            require_ack=False
        )
        print(f"   发送结果: {result}")
        time.sleep(1)
        
        # 发送带 ACK 的消息
        print("   发送带确认的消息...")
        ack_result = self.client.send_chat_sync(
            content="这是一条重要消息",
            chat_type="text",
            require_ack=True
        )
        if ack_result:
            print(f"   ✅ 收到 ACK: {ack_result}")
        else:
            print("   ⚠️ ACK 超时")
    
    def _demo_status_update(self):
        """演示状态更新功能"""
        print("\n📊 演示: 发送状态更新")
        
        status = {
            "mood": "happy",
            "energy": 85,
            "health": 92,
            "battery_level": 78,
            "location": "living_room",
            "activity": "playing",
            "temperature": 23.5
        }
        
        result = self.client.send_status_update_sync(
            status=status,
            require_ack=False
        )
        print(f"   发送结果: {result}")
    
    def _demo_app_request(self):
        """演示 APP 业务请求"""
        print("\n📱 演示: 发送 APP 业务请求")
        
        # 请求宠物属性
        print("   请求: 获取宠物属性")
        result = self.client.send_app_request_sync(
            request_type="get_pet_attributes",
            require_ack=True
        )
        if result:
            print(f"   响应: {result.get('message')}")
        else:
            print("   请求超时")
        
        time.sleep(1)
        
        # 请求任务配置
        print("   请求: 获取任务配置")
        result = self.client.send_app_request_sync(
            request_type="get_task_configs",
            require_ack=True
        )
        if result:
            print(f"   响应: {result.get('message')}")
        else:
            print("   请求超时")
    
    def stop(self):
        """停止演示"""
        self.running = False
        print("\n🛑 停止 WebSocket 客户端...")
        self.client.stop()
        
        # 打印最终统计
        stats = self.client.get_stats()
        print("\n📈 最终统计:")
        print(f"   连接状态: {'已连接' if stats['is_connected'] else '未连接'}")
        print(f"   认证状态: {'已认证' if stats['is_authenticated'] else '未认证'}")
        print(f"   消息发送: {stats['messages_sent']}")
        print(f"   消息接收: {stats['messages_received']}")
        print(f"   重连次数: {stats['reconnect_count']}")
        print(f"   错误次数: {stats['errors_count']}")


def signal_handler(signum, frame):
    """信号处理器"""
    print("\n\n收到终止信号，正在退出...")
    if demo:
        demo.stop()
    sys.exit(0)


# 全局变量
demo = None


def main():
    """主函数"""
    global demo
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建并运行演示
    demo = RobotWebSocketDemo()
    demo.run()
    demo.stop()


if __name__ == '__main__':
    main()
