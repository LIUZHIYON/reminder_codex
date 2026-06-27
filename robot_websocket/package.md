# robot_websocket

## 包概述

**版本**: 0.1.0
**描述**: AI 宠物机器人 WebSocket 客户端模块，用于与后端服务器进行实时通信
**维护者**: AI Pet Bot Team
**许可证**: Proprietary
**硬件平台**: RK3576 ARM64 处理器，4GB 内存

### 核心功能
- WebSocket 连接管理与自动重连
- ROS 2 话题与 WebSocket 消息双向转发
- 服务端指令处理与执行
- 状态数据采集与上报
- 聊天消息处理
- 打印机指令支持

## 节点列表

### WebSocketNode

**文件**: `robot_websocket/robot_websocket/websocket_node.py`
**描述**: WebSocket ROS 2 节点，负责管理 WebSocket 连接并与 ROS 2 系统集成

**关键特性**:
- 自动 WebSocket 连接与认证
- 心跳机制保持连接
- 消息处理器注册系统
- 状态数据缓存与定时上报
- 完整的错误处理

## 话题接口

### 发布的话题

| 话题名称 | 消息类型 | QoS | 方向 | 描述 |
|---------|---------|-----|------|------|
| `command_topic` (参数配置) | `std_msgs/String` | reliability=RELIABLE, depth=10 | 发布 | 服务端指令转发到 ROS 系统 |
| `/websocket/connected` | `std_msgs/Bool` | reliability=RELIABLE, depth=10 | 发布 | WebSocket 连接状态 |
| `/websocket/chat_response` | `std_msgs/String` | reliability=RELIABLE, depth=10 | 发布 | 聊天消息响应 |
| `/websocket/config_response` | `std_msgs/String` | reliability=RELIABLE, depth=10 | 发布 | 配置响应消息 |
| `/printer/print` | `std_msgs/String` | reliability=RELIABLE, depth=10 | 发布 | 打印机指令 |

### 订阅的话题

| 话题名称 | 消息类型 | 回调函数 | 方向 | 描述 |
|---------|---------|---------|------|------|
| `/battery/state` | `sensor_msgs/BatteryState` | `_on_battery_state` | 订阅 | 电池状态信息 |
| `/robot/pose` | `geometry_msgs/Pose` | `_on_pose_message` | 订阅 | 机器人姿态信息 |
| `/robot/chat` | `std_msgs/String` | `_on_chat_message` | 订阅 | 聊天消息 |
| `/robot/status` | `std_msgs/String` | `_on_status_message` | 订阅 | 机器人状态信息 |
| `/printer/status` | `std_msgs/String` | `_on_printer_status` | 订阅 | 打印机状态信息 |

## 服务接口

本包暂未提供 ROS 服务接口。

## 动作接口

本包暂未提供 ROS 动作接口。

## 参数配置

| 参数名称 | 类型 | 默认值 | 描述 |
|---------|------|-------|------|
| `base_url` | string | `http://localhost:8000` | WebSocket 服务器基础 URL |
| `serial_number` | string | `6976f96f-bc80-56e3-9b27-13d12cdde9d9` | 机器人序列号 |
| `heartbeat_interval` | int | 30 | 心跳间隔（秒） |
| `reconnect_delay` | int | 3 | 重连延迟（秒） |
| `max_reconnect_attempts` | int | 10 | 最大重连次数 |
| `enable_auto_reconnect` | bool | true | 是否启用自动重连 |
| `config_file` | string | `""` | 配置文件路径 |
| `status_update_interval` | double | 5.0 | 状态更新间隔（秒） |
| `chat_topic` | string | `/robot/chat` | 聊天消息话题 |
| `command_topic` | string | `/robot/command` | 指令话题 |
| `status_topic` | string | `/robot/status` | 状态消息话题 |

## 依赖关系

### 构建依赖
- `rclpy`
- `robot_interface`
- `robot_utils`
- `std_msgs`
- `geometry_msgs`
- `sensor_msgs`

### 运行依赖
- `rclpy`
- `robot_interface`
- `robot_utils`
- `std_msgs`
- `geometry_msgs`
- `sensor_msgs`
- `websockets` (Python 包)
- `aiohttp` (Python 包)

### 测试依赖
- `ament_copyright`
- `ament_flake8`
- `ament_pep257`
- `python3-pytest`

## 启动文件

### `launch/websocket_service.launch.py`

**描述**: 启动 WebSocket 服务节点

**启动参数**:
| 参数名称 | 类型 | 默认值 | 描述 |
|---------|------|-------|------|
| `base_url` | string | `http://localhost:8000` | WebSocket 服务器 URL |
| `serial_number` | string | `6976f96f-bc80-56e3-9b27-13d12cdde9d9` | 机器人序列号 |
| `config_file` | string | `""` | 配置文件路径 |
| `use_config_file` | bool | false | 是否使用配置文件 |

**启动命令**:
```bash
ros2 launch robot_websocket websocket_service.launch.py base_url:="http://your-server:8000" serial_number:="your-serial-number"
```

## 配置文件

### `config/websocket_config.yaml`

**描述**: WebSocket 客户端配置文件

**配置示例**:
```yaml
base_url: "http://localhost:8000"
serial_number: "6976f96f-bc80-56e3-9b27-13d12cdde9d9"
heartbeat_interval: 30
reconnect_delay: 3
max_reconnect_attempts: 10
enable_auto_reconnect: true
```

## 使用示例

### 1. 启动 WebSocket 服务

```bash
# 使用默认参数
ros2 launch robot_websocket websocket_service.launch.py

# 使用自定义参数
ros2 launch robot_websocket websocket_service.launch.py base_url:="http://api.example.com" serial_number:="robot-001"
```

### 2. 监听 WebSocket 连接状态

```bash
ros2 topic echo /websocket/connected
```

### 3. 发送聊天消息

```bash
ros2 topic pub /robot/chat std_msgs/String "{data: '{\"content\": \"Hello from ROS\", \"type\": \"text\"}'}"
```

### 4. 查看聊天响应

```bash
ros2 topic echo /websocket/chat_response
```

## 调试建议

### 1. 检查 WebSocket 连接状态

```bash
# 查看连接状态
ros2 topic echo /websocket/connected

# 查看节点日志
ros2 node info /websocket_node
ros2 topic info /websocket/connected
```

### 2. 查看节点统计信息

```bash
# 查看节点详细信息
ros2 node info /websocket_node

# 查看发布的话题
ros2 topic list | grep websocket
```

### 3. 测试 WebSocket 客户端

```bash
# 运行测试客户端
python3 test/example_websocket_client.py

# 运行单元测试
cd src/robot_websocket && python3 -m pytest test/test_websocket_client.py -v
```

### 4. 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|----------|
| 连接失败 | 服务器 URL 错误 | 检查 base_url 参数 |
| 认证失败 | 序列号无效 | 检查 serial_number 参数 |
| 消息发送失败 | WebSocket 未连接 | 检查网络连接和服务器状态 |
| 重连失败 | 网络问题或服务器不可用 | 检查网络连接和服务器状态 |

## 性能优化

- **内存使用**: WebSocket 客户端使用异步编程，内存占用较低
- **CPU 使用率**: 心跳间隔默认为 30 秒，可根据实际需求调整
- **网络带宽**: 状态更新间隔默认为 5 秒，可根据网络条件调整
- **重连策略**: 实现了指数退避重连，避免频繁重连占用资源

## 源码文件

| 文件路径 | 描述 |
|---------|------|
| `robot_websocket/websocket_node.py` | WebSocket ROS 2 节点实现 |
| `robot_websocket/websocket_client.py` | WebSocket 客户端实现 |
| `robot_websocket/message_handlers.py` | 消息处理器模块 |
| `robot_websocket/__init__.py` | 包初始化文件 |
| `launch/websocket_service.launch.py` | 启动文件 |
| `config/websocket_config.yaml` | 配置文件 |

## 开发注意事项

1. **安全考虑**:
   - 确保 WebSocket 服务器 URL 安全可靠
   - 避免在日志中记录敏感信息

2. **性能考虑**:
   - 状态更新频率不宜过高，避免占用过多网络带宽
   - 消息处理器应保持轻量，避免阻塞主线程

3. **可靠性考虑**:
   - 实现了完善的重连机制，确保连接稳定性
   - 消息发送支持 ACK 确认，确保消息可靠送达

4. **扩展性**:
   - 消息处理器采用注册机制，便于添加新的消息类型处理
   - 配置参数化，便于根据不同环境调整

## 已知问题

- 暂无已知问题

## TODO 事项

- 添加更多单元测试
- 实现消息队列机制，提高消息处理可靠性
- 增加连接状态监控和告警机制
- 优化重连策略，适应不同网络环境