"""
robot_aipet_relay — AI Pet 板端 WebSocket 传话节点

架构:
  服务器(WebSocket) → relay_node → /robot/command (reminder指令)
                                 → aipet/command_delivery (通用指令)
                                 → aipet/relay_delivery (传话)
                                 → aipet/chat_delivery (聊天)

特点:
  - WebSocket 长连接，无 HTTP 轮询
  - reminder 类型指令同时发布到 /robot/command 供 BT driver 使用
  - 心跳 30s，指数退避重连
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import threading
import time
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

    def __init__(self, ws_url, token, relay_node):
        self.ws_url = ws_url
        self.token = token
        self.relay_node = relay_node
        self.ws = None
        self.connected = False
        self._stop = threading.Event()

    def connect(self):
        def _run():
            backoff = 1
            max_backoff = 60
            while not self._stop.is_set():
                try:
                    self.ws = websocket.WebSocketApp(
                        self.ws_url,
                        on_open=self._on_open,
                        on_message=self._on_message,
                        on_error=self._on_error,
                        on_close=self._on_close,
                    )
                    self.ws.run_forever(ping_interval=25, ping_timeout=10,
                                        skip_utf8_validation=False)
                except Exception as e:
                    self.relay_node.get_logger().error(f'WS 连接异常: {e}')
                if not self._stop.is_set():
                    self.relay_node.get_logger().info(f'WS 将在 {backoff} 秒后重连...')
                    self._backoff_sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _backoff_sleep(self, seconds):
        for _ in range(int(seconds * 10)):
            if self._stop.is_set():
                return
            time.sleep(0.1)

    def _on_open(self, ws):
        self.relay_node.get_logger().info('WebSocket 已连接，发送认证...')
        auth_msg = json.dumps({'type': 'auth', 'access_token': self.token})
        ws.send(auth_msg)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')
            self.relay_node.get_logger().debug(f'收到 WS 消息: type={msg_type}')

            if msg_type == 'auth':
                self._handle_auth(data, ws)
            elif msg_type == 'heartbeat':
                pass
            elif msg_type == 'config_request':
                self._handle_config_response(data)
            elif msg_type == 'relay_message_delivery':
                self._handle_relay_delivery(data, ws)
            elif msg_type == 'server_command':
                self._handle_server_command(data, ws)
            elif msg_type == 'reminder_delivery':
                self._handle_reminder_delivery(data, ws)
            elif msg_type == 'chat':
                self._handle_chat(data)
            elif msg_type == 'ack':
                pass
            else:
                self.relay_node.get_logger().debug(f'未处理: {msg_type}')

            # 回调通知 ROS 层
            if self.relay_node and hasattr(self.relay_node, '_on_ws_message'):
                self.relay_node._on_ws_message(data)

        except json.JSONDecodeError:
            self.relay_node.get_logger().error(f'JSON 解析失败')
        except Exception as e:
            self.relay_node.get_logger().error(f'消息处理异常: {e}')

    def _on_error(self, ws, error):
        self.connected = False
        self.relay_node.get_logger().error(f'WS 错误: {error}')

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self.relay_node.get_logger().info(f'WS 关闭: code={close_status_code}')

    def _handle_auth(self, data, ws):
        if data.get('success'):
            self.connected = True
            self.relay_node.get_logger().info('✅ 认证成功！设备已上线')
            config_req = json.dumps({'type': 'config_request'})
            ws.send(config_req)
        else:
            self.connected = False
            self.relay_node.get_logger().error(f'❌ 认证失败: {data.get("message", "")}')

    def _handle_config_response(self, data):
        if data.get('success') and data.get('data'):
            config = data['data']
            self.relay_node.get_logger().info(
                f'📋 配置: 昵称={config.get("pet_nickname", "未知")}')
            if self.relay_node:
                msg = String()
                msg.data = json.dumps(config, ensure_ascii=False)
                self.relay_node._config_pub.publish(msg)
        else:
            self.relay_node.get_logger().info('📋 暂无配置')

    def _handle_relay_delivery(self, data, ws):
        """处理传话消息 → 发布到 aipet/relay_delivery"""
        relay_id = data.get('relay_id') or data.get('relayId') or ''
        relay_from = data.get('relay_from') or data.get('relayFrom', '')
        relay_to = data.get('relay_to') or data.get('relayTo', '')
        content = data.get('content', '')
        self.relay_node.get_logger().info(
            f'📨 传话: {relay_from} → {relay_to}: {str(content)[:50]}')

        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._relay_delivery_pub.publish(msg)

        response = json.dumps({
            'type': 'relay_message_response',
            'relay_id': relay_id or data.get('message_id', ''),
            'status': 'completed',
            'result': {'played': True, 'displayed': True,
                       'executed_at': datetime.now().isoformat()}
        })
        ws.send(response)

    def _handle_server_command(self, data, ws):
        """处理服务器指令 → 发布到 话题 + 如果 reminder 类型也发到 /robot/command"""
        cmd_id = data.get('command_id', '')
        cmd_type = data.get('command', '') or data.get('command_type', '')
        self.relay_node.get_logger().info(f'⚙️ 指令: {cmd_type} (id={cmd_id})')

        # 1) 发布到 aipet/command_delivery（通用）
        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._command_delivery_pub.publish(msg)

        # 2) 如果是 reminder 指令，同时发布到 /robot/command（BT driver 监听）
        if cmd_type == 'reminder' and self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._robot_command_pub.publish(msg)
            self.relay_node.get_logger().info(
                f'  → 已转发到 /robot/command: {cmd_type}')

        # 响应
        response = json.dumps({
            'type': 'command_response',
            'command_id': cmd_id,
            'command': cmd_type,
            'status': 'success',
            'result': {'received': True, 'executed_at': datetime.now().isoformat()}
        })
        ws.send(response)


    def _handle_reminder_delivery(self, data, ws):
        # Handle reminder_delivery from server -> publish to topics for BT driver
        rid = data.get("reminder_id", "")
        rd = data.get("reminder_data", {})
        title = rd.get("title", "") or rd.get("content", "")
        content = rd.get("content", "") or title
        rtime = rd.get("reminder_time", "") or rd.get("reminderTime", "")
        self.relay_node.get_logger().info(f"Reminder delivery: {title} @ {rtime}")
        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._command_delivery_pub.publish(msg)
            msg2 = String()
            msg2.data = json.dumps({"command":"reminder","command_id":rid,"params":{"reminder_data":rd}}, ensure_ascii=False)
            self.relay_node._robot_command_pub.publish(msg2)
        response = json.dumps({"type":"reminder_response","reminder_id":rid,"status":"received","result":{"received":True}})
        ws.send(response)

    def _handle_chat(self, data):
        if self.relay_node:
            msg = String()
            msg.data = json.dumps(data, ensure_ascii=False)
            self.relay_node._chat_delivery_pub.publish(msg)

    def send_status_update(self, status_dict):
        if not self.connected or not self.ws:
            return False
        try:
            msg = json.dumps({'type': 'status_update', 'status': status_dict})
            self.ws.send(msg)
            return True
        except Exception as e:
            self.relay_node.get_logger().error(f'状态上报失败: {e}')
            return False

    def send_chat(self, content, chat_type='text'):
        if not self.connected or not self.ws:
            return False
        try:
            msg = json.dumps({'type': 'chat', 'content': content, 'chat_type': chat_type})
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

        self.declare_parameter('server_host', '47.118.26.156')
        self.declare_parameter('server_port', 8000)
        self.declare_parameter('serial_number', 'AIPET-001')
        self.declare_parameter('heartbeat_interval', 30.0)

        self.server_host = self.get_parameter('server_host').value
        self.server_port = self.get_parameter('server_port').value
        self.serial_number = self.get_parameter('serial_number').value
        self.heartbeat_interval = self.get_parameter('heartbeat_interval').value

        self.get_logger().info(f'🚀 AI Pet 传话节点启动')
        self.get_logger().info(f'   服务器: {self.server_host}:{self.server_port}')
        self.get_logger().info(f'   序列号: {self.serial_number}')

        # 发布器
        self._relay_delivery_pub = self.create_publisher(String, 'aipet/relay_delivery', 10)
        self._command_delivery_pub = self.create_publisher(String, 'aipet/command_delivery', 10)
        self._chat_delivery_pub = self.create_publisher(String, 'aipet/chat_delivery', 10)
        self._config_pub = self.create_publisher(String, 'aipet/config', 10)
        # ★ 新增：提醒指令同时发布到 /robot/command（BT driver 监听）
        self._robot_command_pub = self.create_publisher(String, '/robot/command', 10)

        # 订阅器
        self._status_sub = self.create_subscription(
            String, 'aipet/status_update', self._on_status_update, 10)
        self._chat_sub = self.create_subscription(
            String, 'aipet/send_chat', self._on_send_chat, 10)

        # 获取 WS 令牌并连接
        self._token_retry_count = 0
        self._token_retry_timer = None
        token = self._fetch_ws_token()
        if not token:
            self.get_logger().error('无法获取 WebSocket 令牌，将重试')
            self._schedule_token_retry()
            return

        ws_url = (f'ws://{self.server_host}:{self.server_port}'
                  f'/api/v1/aipet/ws/{self.serial_number}')
        self.ws_client = AIPetRelayWSClient(ws_url, token, self)
        self.ws_client.connect()

        self._heartbeat_timer = self.create_timer(
            self.heartbeat_interval, self._send_heartbeat)
        self._status_timer = self.create_timer(60.0, self._periodic_status)

    def _on_ws_message(self, data):
        """WS 消息统一回调，可扩展"""
        pass

    def _fetch_ws_token(self):
        url = (f'http://{self.server_host}:{self.server_port}'
               f'/api/v1/aipet/ws/auth/{self.serial_number}')
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
        delays = [10, 30, 60, 120, 300]
        idx = min(self._token_retry_count, len(delays) - 1)
        delay = delays[idx]
        self._token_retry_count += 1
        self.get_logger().info(f'将在 {delay} 秒后重试 (第 {self._token_retry_count} 次)')
        self._token_retry_timer = self.create_timer(delay, self._retry_init)

    def _retry_init(self):
        if self._token_retry_timer:
            self.destroy_timer(self._token_retry_timer)
            self._token_retry_timer = None
        self.get_logger().info('重试获取 WS 令牌...')
        token = self._fetch_ws_token()
        if token:
            ws_url = (f'ws://{self.server_host}:{self.server_port}'
                      f'/api/v1/aipet/ws/{self.serial_number}')
            self.ws_client = AIPetRelayWSClient(ws_url, token, self)
            self.ws_client.connect()
            self._heartbeat_timer = self.create_timer(
                self.heartbeat_interval, self._send_heartbeat)
            self._status_timer = self.create_timer(60.0, self._periodic_status)
            self.get_logger().info('✅ 重试成功')
        else:
            self._schedule_token_retry()

    def _send_heartbeat(self):
        if hasattr(self, 'ws_client') and self.ws_client and self.ws_client.connected:
            try:
                msg = json.dumps({'type': 'heartbeat'})
                self.ws_client.ws.send(msg)
            except Exception:
                pass

    def _periodic_status(self):
        if hasattr(self, 'ws_client') and self.ws_client:
            status = {'battery': 85, 'temperature': 36.5, 'mood': 'happy',
                      'health': 100, 'hunger': 60, 'cleanliness': 80,
                      'stamina': 75, 'energy': 45}
            self.ws_client.send_status_update(status)

    def _on_status_update(self, msg):
        if hasattr(self, 'ws_client') and self.ws_client:
            try:
                data = json.loads(msg.data)
                self.ws_client.send_status_update(data)
            except Exception:
                pass

    def _on_send_chat(self, msg):
        if hasattr(self, 'ws_client') and self.ws_client:
            try:
                data = json.loads(msg.data)
                self.ws_client.send_chat(data.get('content', msg.data),
                                          data.get('chat_type', 'text'))
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
