# AI宠物机器人 WebSocket 客户端模块

ROS 2 的 WebSocket 客户端模块，用于与后端服务器进行实时通信。

## 📁 目录结构

```
robot_websocket/
├── robot_websocket/
│   ├── __init__.py              # 模块初始化
│   ├── websocket_client.py      # WebSocket 客户端核心类
│   └── websocket_node.py        # ROS 2 节点
├── config/
│   └── websocket_config.yaml    # 配置文件
├── launch/
│   └── websocket_service.launch.py  # 启动文件
├── test/
│   ├── test_websocket_client.py     # 单元测试
│   └── example_websocket_client.py  # 使用示例
├── package.xml
├── setup.py
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install websockets aiohttp
```

### 2. 编译模块

```bash
# 在工作空间根目录执行
colcon build --packages-select robot_websocket

# 加载环境变量
source install/setup.bash
```

### 3. 启动节点

```bash
# 使用默认参数启动
ros2 launch robot_websocket websocket_service.launch.py

# 指定服务器地址
ros2 launch robot_websocket websocket_service.launch.py base_url:=http://192.168.1.100:8000

# 指定设备序列号
ros2 launch robot_websocket websocket_service.launch.py serial_number:=YOUR_SERIAL_NUMBER
```

## 📡 消息类型

| 消息类型 | 说明 | 方向 |
|---------|------|------|
| `auth` | 认证消息 | 客户端→服务端 |
| `heartbeat` | 心跳消息 | 客户端→服务端 |
| `chat` | 聊天消息 | 双向 |
| `status_update` | 状态更新 | 客户端→服务端 |
| `command_response` | 指令响应 | 客户端→服务端 |
| `server_command` | 服务端指令 | 服务端→客户端 |
| `app_request` | APP业务请求 | 客户端→服务端 |

## 📋 配置参数

### 启动参数

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `base_url` | `http://localhost:8000` | 服务器基础 URL |
| `serial_number` | `host_tag()`（自动） | 设备序列号，默认通过 `robot_utils.get_device_info.host_tag()` 从 CPU 序列号自动生成 |
| `heartbeat_interval` | `30` | 心跳间隔（秒） |
| `reconnect_delay` | `3` | 重连延迟（秒） |
| `max_reconnect_attempts` | `10` | 最大重连次数 |
| `enable_auto_reconnect` | `true` | 是否启用自动重连 |
| `status_update_interval` | `5.0` | 状态上报间隔（秒） |

### 配置文件示例

```yaml
# websocket_config.yaml
base_url: "http://localhost:8000"
serial_number: ""   # 空字符串 = 自动使用 host_tag() 从 CPU 序列号生成
heartbeat_interval: 30
reconnect_delay: 3
max_reconnect_attempts: 10
enable_auto_reconnect: true
status_update_interval: 5.0
```

## 📤 ROS 2 话题

### 发布的话题

| 话题名 | 消息类型 | 说明 |
|--------|----------|------|
| `/websocket/connected` | `std_msgs/Bool` | 连接状态 |
| `/websocket/chat_response` | `std_msgs/String` | 聊天响应（JSON格式） |
| `/websocket/config_response` | `std_msgs/String` | 配置响应（JSON格式） |
| `/robot/command` | `std_msgs/String` | 服务端指令（JSON格式） |

### 订阅的话题

| 话题名 | 消息类型 | 说明 |
|--------|----------|------|
| `/robot/chat` | `std_msgs/String` | 聊天消息 |
| `/robot/status` | `std_msgs/String` | 状态更新（JSON格式） |
| `/battery/state` | `sensor_msgs/BatteryState` | 电池状态 |
| `/robot/pose` | `geometry_msgs/Pose` | 机器人姿态 |

## 💬 使用示例

### 发送聊天消息

```python
import rclpy
from std_msgs.msg import String

rclpy.init()
node = rclpy.create_node('chat_example')
pub = node.create_publisher(String, '/robot/chat', 10)

msg = String()
msg.data = '{"content": "你好，AI宠物！", "type": "text"}'
pub.publish(msg)
```

### 监听服务端指令

```python
import rclpy
from std_msgs.msg import String
import json

def on_command(msg):
    data = json.loads(msg.data)
    print(f"收到指令: {data['command']}")
    print(f"参数: {data['params']}")

rclpy.init()
node = rclpy.create_node('command_listener')
sub = node.create_subscription(String, '/robot/command', on_command, 10)
rclpy.spin(node)
```

### 更新机器人状态

```python
import rclpy
from std_msgs.msg import String
import json

rclpy.init()
node = rclpy.create_node('status_example')
pub = node.create_publisher(String, '/robot/status', 10)

status = {
    "mood": "happy",
    "energy": 85,
    "health": 92,
    "activity": "playing"
}

msg = String()
msg.data = json.dumps(status)
pub.publish(msg)
```

## 🔧 支持的 APP 业务请求

| 请求类型 | 说明 |
|----------|------|
| `get_user_treasure_chest` | 获取用户宝箱列表 |
| `combine_treasure_chest` | 合成宝箱 |
| `open_treasure_chest` | 开启宝箱 |
| `get_pet_attributes` | 获取宠物属性 |
| `get_task_configs` | 获取任务配置 |
| `complete_task` | 完成任务 |
| `claim_task_reward` | 领取任务奖励 |
| `get_user_virtual_currency` | 获取虚拟货币 |
| `post_moment` | 发布朋友圈 |

## 🧪 测试

```bash
# 运行单元测试
ros2 run robot_websocket test_websocket_client.py

# 运行示例程序
ros2 run robot_websocket example_websocket_client.py
```

## 📊 调试信息

查看 WebSocket 连接状态：

```bash
# 查看连接状态
ros2 topic echo /websocket/connected

# 查看服务端指令
ros2 topic echo /robot/command

# 查看节点日志
ros2 run robot_websocket websocket_node --ros-args --log-level debug
```

## 🛠️ 故障排除

### 连接失败

1. 检查服务器地址是否正确
2. 检查设备序列号是否正确
3. 检查网络连接
4. 查看节点日志获取详细信息

```bash
# 使用调试日志级别启动
ros2 run robot_websocket websocket_node --ros-args --log-level debug
```

### 认证失败

1. 确认设备已在服务器注册
2. 检查设备序列号是否与注册时一致
3. 检查服务器时间是否同步

## 📝 依赖

- ROS 2 Humble 或更高版本
- Python 3.8+
- websockets >= 10.0
- aiohttp >= 3.8.0

## 📄 License

MIT License

# CI trigger 9/16
