"""
robot_aipet_relay — AI Pet 板端 WebSocket 传话节点

设计原则：
  - 使用 WebSocket 长连接与服务器通信（非 HTTP 短连接轮询）
  - 非"客户端模式"：不在循环中轮询 HTTP API，仅通过 WebSocket 接收/发送消息
  - 仅实现传话（relay）相关功能
  - 心跳间隔 30s，避免不必要的通信
  - 单例连接，无会话风暴

流程：
  1. 启动时通过 HTTP 获取 WebSocket 认证令牌（一次性）
  2. 建立 WebSocket 长连接
  3. 发送 auth 消息认证
  4. 认证成功后开启心跳定时器（每 30s）
  5. 监听服务端下发的 relay_message_delivery / server_command / chat 并处理
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import threading
import time
import ssl
from datetime import datetime

try:
    import websocket
except ImportError:
    websocket = None

try:
    import urllib.request
except ImportError:
    urllib = None


class AIPetRelayWSClient:
    """WebSocket 客户端，管理与服务器的长连接"""

    def __init__(self, ws_url, token, relay_node, on_message=None, on_command=None):
        self.ws_url = ws_url
        self.token = token
        self.relay_node = relay_node  # ROS2 node reference for logging
        self.on_message_cb = on_message
        self.on_command_cb = on_command
        self.ws = None
        self.connected = False
        self._stop = threading.Event()

    def connect(self):
        def _run():
            backoff = 1  # 初始 1 秒
            max_backoff = 60  # 最长 60 秒
            while not self._stop.is_set():
                try:
                    self.ws = websocket.WebSocketApp(
                        self.ws_url,
                        on_open=self._on_open,
                        on_message=self._on_message,
                        on_error=self._on_error,
                        on_close=self._on_close,
                    )
                    # 设置心跳包 ping 间隔 (25s < 30s 心跳间隔)
                    self.ws.run_forever(
                        ping_interval=25,
                        ping_timeout=10,
                        skip_utf8_validation=False,
                    )
                except Exception as e:
                    self.relay_node.get_logger().error(f'WS 连接异常: {e}')
                if not self._stop.is_set():
                    self.relay_node.get_logger().info(f'WS 将在 {backoff} 秒后重连...')
                    self._backoff_sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _backoff_sleep(self, seconds):
        """可中断的退避等待"""
        for _ in range(int(seconds * 10)):
            if self._stop.is_set():
                return
            time.sleep(0.1)

    def _on_open(self, ws):
        self.relay_node.get_logger().info('WebSocket 已连接，发送认证...')
        # 发送认证消息
        auth_msg = json.dumps({
            'type': 'auth',
            'access_token': self.token
        })
        ws.send(auth_msg)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')
            self.relay_node.get_logger().debug(f'收到 WS 消息: type={msg_type}')

            if msg_type == 'auth':
                self._handle_auth(data, ws)
            elif msg_type == 'heartbeat':
                self._handle_heartbeat(data)
            elif msg_type == 'config_request':
                self._handle_config_response(data)
            elif msg_type == 'relay_message_delivery':
                self._handle_relay_delivery(data, ws)
            elif msg_type == 'server_command':
                self._handle_server_command(data, ws)
            elif msg_type == 'chat':
                self._handle_chat(data)
            elif msg_type == 'ack':
                self._handle_ack(data)
            else:
                self.relay_node.get_logger().debug(f'未处理的消息类型: {msg_type}')

            # 回调通知 ROS 层
            if self.on_message_cb:
                self.on_message_cb(data)

        except json.JSONDecodeError:
            self.relay_node.get_logger().error(f'JSON 解析失败: {message}')
        except Exception as e:
            self.relay_node.get_logger().error(f'消息处理异常: {e}')

    def _on_error(self, ws, error):
        self.connected = False
        self.relay_node.get_logger().error(f'WS 错误: {error}')

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self.relay_node.get_logger().info(f'WS 关闭: code={close_status_code}, msg={close_msg}')

    def _handle_auth(self, data, ws):
        if data.get('success'):
            self.connected = True
            self.relay_node.get_logger().info('✅ 认证成功！设备已上线')
            # 认证成功后立即发送配置请求
            config_req = json.dumps({'type': 'config_request'})
            ws.send(config_req)
        else:
            self.connected = False
            self.relay_node.get_logger().error(f'❌ 认证失败: {data.get("message", "未知错误")}')

    def _handle_heartbeat(self, data):
        self.relay_node.get_logger().debug('心跳响应正常')

    def _handle_config_response(self, data):
        """处理配置请求响应"""
        if data.get('success') and data.get('data'):
            config = data['data']
            self.relay_node.get_logger().info(f'📋 获取到配置: 昵称={config.get("pet_nickname", "未知")}')
            # 发布配置到 ROS topic
            if self.relay_node:
                msg = String()
                msg.data = json.dumps(config, ensure_ascii=False)
                self.relay_node._config_pub.publish(msg)
        else:
            self.relay_node.get_logger().info('📋 暂无配置信息')

    def _handle_relay_delivery(self, data, ws):
        """处理服务器下发的传话消息"""
        relay_id = data.get('relay_id') or data.get('relayId') or data.get('data', {}).get('relay_id', '')
        relay_from = data.get('relay_from') or data.get('relayFrom', '')
        relay_to = data.get('relay_to') or data.get('relayTo', '')
        content = data.get('content', '')
        content_type = data.get('content_type') or data.get('contentType', 'text')

        self.relay_node.get_logger().info(
            f'📨 收到传话: {relay_from} → {relay_to} | {content_type}: {content[:50] if content else "(语音)"}'
        )

        # 发布到 ROS topic 供其他节点使用
        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._relay_delivery_pub.publish(msg)

        # 响应传话执行结果
        response = json.dumps({
            'type': 'relay_message_response',
            'relay_id': relay_id or data.get('message_id', ''),
            'status': 'completed',
            'result': {
                'played': True,
                'displayed': True,
                'executed_at': datetime.now().isoformat()
            }
        })
        ws.send(response)
        self.relay_node.get_logger().info(f'✅ 传话已响应: relay_id={relay_id}')

    def _handle_server_command(self, data, ws):
        """处理服务器下发的通用指令"""
        cmd_id = data.get('command_id', '')
        cmd_type = data.get('command', '') or data.get('command_type', '')
        self.relay_node.get_logger().info(f'⚙️ 收到指令: {cmd_type} (id={cmd_id})')

        # 发布到 ROS topic
        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._command_delivery_pub.publish(msg)

        # 响应指令执行结果
        response = json.dumps({
            'type': 'command_response',
            'command_id': cmd_id,
            'command': cmd_type,
            'status': 'success',
            'result': {'received': True, 'executed_at': datetime.now().isoformat()}
        })
        ws.send(response)
        self.relay_node.get_logger().info(f'✅ 指令已响应: {cmd_type}')

    def _handle_chat(self, data):
        """处理服务器转发的聊天消息"""
        content = data.get('content', '')
        self.relay_node.get_logger().info(f'💬 收到聊天: {content[:60]}')

        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._chat_delivery_pub.publish(msg)

    def _handle_ack(self, data):
        self.relay_node.get_logger().debug(f'ACK: {data.get("data", {})}')

    def send_status_update(self, status_dict):
        """发送状态更新到服务器"""
        if not self.connected or not self.ws:
            return False
        try:
            msg = json.dumps({
                'type': 'status_update',
                'status': status_dict
            })
            self.ws.send(msg)
            return True
        except Exception as e:
            self.relay_node.get_logger().error(f'状态上报失败: {e}')
            return False

    def send_chat(self, content, chat_type='text'):
        """发送聊天消息到服务器"""
        if not self.connected or not self.ws:
            return False
        try:
            msg = json.dumps({
                'type': 'chat',
                'content': content,
                'chat_type': chat_type
            })
            self.ws.send(msg)
            return True
        except Exception as e:
            self.relay_node.get_logger().error(f'聊天发送失败: {e}')
            return False

    def stop(self):
        self._stop.set()
        if self.ws:
            self.ws.close()


class AIPetRelayNode(Node):
    """AI Pet 传话 ROS2 节点"""

    def __init__(self):
        super().__init__('aipet_relay_node')

        # 声明参数
        self.declare_parameter('server_host', '47.118.26.156')
        self.declare_parameter('server_port', 8000)
        self.declare_parameter('serial_number', 'AIPET-001')
        self.declare_parameter('heartbeat_interval', 30.0)
        self.declare_parameter('auto_reconnect', True)

        self.server_host = self.get_parameter('server_host').value
        self.server_port = self.get_parameter('server_port').value
        self.serial_number = self.get_parameter('serial_number').value
        self.heartbeat_interval = self.get_parameter('heartbeat_interval').value

        self.get_logger().info(f'🚀 AI Pet 传话节点启动')
        self.get_logger().info(f'   服务器: {self.server_host}:{self.server_port}')
        self.get_logger().info(f'   序列号: {self.serial_number}')

        # 发布器：将服务器下发的消息发布到 ROS topic
        self._relay_delivery_pub = self.create_publisher(String, 'aipet/relay_delivery', 10)
        self._command_delivery_pub = self.create_publisher(String, 'aipet/command_delivery', 10)
        self._chat_delivery_pub = self.create_publisher(String, 'aipet/chat_delivery', 10)
        self._config_pub = self.create_publisher(String, 'aipet/config', 10)

        # 订阅器：允许其他节点通过 ROS 发送消息到服务器
        self._status_sub = self.create_subscription(String, 'aipet/status_update', self._on_status_update, 10)
        self._chat_sub = self.create_subscription(String, 'aipet/send_chat', self._on_send_chat, 10)

        # 获取 WS 令牌
        self._token_retry_count = 0
        self._token_retry_timer = None
        token = self._fetch_ws_token()
        if not token:
            self.get_logger().error('无法获取 WebSocket 令牌，将按指数退避重试')
            self._schedule_token_retry()
            return

        # 建立 WebSocket 连接
        ws_url = f'ws://{self.server_host}:{self.server_port}/api/v1/aipet/ws/{self.serial_number}'
        self.ws_client = AIPetRelayWSClient(ws_url, token, self)
        self.ws_client.connect()

        # 心跳定时器（每 30 秒发送一次）
        self._heartbeat_timer = self.create_timer(self.heartbeat_interval, self._send_heartbeat)
        self.get_logger().info(f'❤️ 心跳定时器已启动，间隔 {self.heartbeat_interval}s')

        # 状态定时器（每 60 秒上报一次状态）
        self._status_timer = self.create_timer(60.0, self._periodic_status)
        self.get_logger().info('📊 状态上报定时器已启动（60s）')

    def _fetch_ws_token(self):
        """一次性 HTTP 调用获取 WebSocket 认证令牌"""
        url = f'http://{self.server_host}:{self.server_port}/api/v1/aipet/ws/auth/{self.serial_number}'
        self.get_logger().info(f'获取 WS 令牌: {url}')
        try:
            req = urllib.request.urlopen(url, timeout=10)
            resp = json.loads(req.read())
            token = resp.get('data')
            if token:
                self.get_logger().info('✅ WS 令牌获取成功')
                return token
            else:
                self.get_logger().error(f'令牌获取失败: {resp}')
                return None
        except Exception as e:
            self.get_logger().error(f'令牌获取异常: {e}')
            return None

    def _schedule_token_retry(self):
        """按指数退避调度令牌重试"""
        delays = [10, 30, 60, 120, 300]  # 10s → 30s → 1min → 2min → 5min
        idx = min(self._token_retry_count, len(delays) - 1)
        delay = delays[idx]
        self._token_retry_count += 1
        self.get_logger().info(f'将在 {delay} 秒后重试获取令牌 (第 {self._token_retry_count} 次)')
        self._token_retry_timer = self.create_timer(delay, self._retry_init)

    def _retry_init(self):
        """重试初始化"""
        # 先销毁当前定时器，防止堆积
        if self._token_retry_timer:
            self.destroy_timer(self._token_retry_timer)
            self._token_retry_timer = None

        self.get_logger().info('重试获取 WS 令牌...')
        token = self._fetch_ws_token()
        if token:
            ws_url = f'ws://{self.server_host}:{self.server_port}/api/v1/aipet/ws/{self.serial_number}'
            self.ws_client = AIPetRelayWSClient(ws_url, token, self)
            self.ws_client.connect()
            self._heartbeat_timer = self.create_timer(self.heartbeat_interval, self._send_heartbeat)
            self._status_timer = self.create_timer(60.0, self._periodic_status)
            self.get_logger().info('✅ 重试成功，WS 已连接')
        else:
            self._schedule_token_retry()

    def _send_heartbeat(self):
        """发送心跳"""
        if hasattr(self, 'ws_client') and self.ws_client and self.ws_client.connected:
            try:
                msg = json.dumps({'type': 'heartbeat'})
                self.ws_client.ws.send(msg)
                self.get_logger().debug('❤️ 心跳已发送')
            except Exception as e:
                self.get_logger().warn(f'心跳发送失败: {e}')

    def _periodic_status(self):
        """定时上报设备状态"""
        if hasattr(self, 'ws_client') and self.ws_client:
            status = {
                'battery': 85,
                'temperature': 36.5,
                'mood': 'happy',
                'health': 100,
                'hunger': 60,
                'cleanliness': 80,
                'stamina': 75,
                'energy': 45
            }
            self.ws_client.send_status_update(status)

    def _on_status_update(self, msg):
        """收到 ROS topic 的状态更新请求，转发到服务器"""
        if hasattr(self, 'ws_client') and self.ws_client:
            try:
                data = json.loads(msg.data)
                self.ws_client.send_status_update(data)
            except Exception as e:
                self.get_logger().error(f'状态更新转发失败: {e}')

    def _on_send_chat(self, msg):
        """收到 ROS topic 的聊天请求，转发到服务器"""
        if hasattr(self, 'ws_client') and self.ws_client:
            try:
                data = json.loads(msg.data)
                content = data.get('content', msg.data)
                chat_type = data.get('chat_type', 'text')
                self.ws_client.send_chat(content, chat_type)
            except Exception:
                self.ws_client.send_chat(msg.data)

    def destroy_node(self):
        if hasattr(self, 'ws_client') and self.ws_client:
            self.ws_client.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AIPetRelayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
