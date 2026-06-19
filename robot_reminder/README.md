# 待办事提醒系统 — robot_reminder

## 项目结构

```
robot_reminder_system/
├── robot_reminder/          # ROS2 提醒节点 (部署到 RK3576)
│   ├── package.xml
│   ├── setup.py / setup.cfg
│   ├── robot_reminder/
│   │   ├── reminder_node.py   # 主节点: WS连接 + 命令处理 + TTS + 播放
│   │   └── __init__.py
│   ├── launch/reminder.launch.py
│   ├── config/reminder_params.yaml
│   └── requirements.txt
├── simulation/              # 本地模拟器
│   ├── app_simulator.py       # 模拟 APP (HTTP API 客户端)
│   └── device_simulator.py    # 模拟设备 (WebSocket 客户端)
├── test/
│   └── test_reminder_flow.py  # 集成测试
└── deploy/
    └── deploy.sh              # 部署到 RK3576
```

## 架构

```
┌─────────────────┐     HTTP API      ┌──────────────┐
│  APP (手机端)    │ ────────────────→ │  AI Pet 服务器 │
│  app_simulator.py│   POST /command   │ 42.121.217.40 │
└─────────────────┘                   │ :9099 / :3000 │
                                      └──────┬───────┘
                                             │ WebSocket
                                             │ server_command
                                             ↓
┌──────────────────────────────────────────────┐
│  设备节点 (robot_reminder / device_simulator)  │
│                                              │
│  1. WS 连接 → Auth → Heartbeat               │
│  2. 接收 server_command → 解析 reminder       │
│  3. TTS 合成语音 (PowerShell/edge-tts/espeak) │
│  4. 播放语音                                   │
│  5. 上报 command_response                     │
└──────────────────────────────────────────────┘
```

## 快速开始

### 1. 本地模拟测试

```bash
# 终端 1：启动设备模拟器
cd simulation
python device_simulator.py --serial AIPET-DEMO-001

# 终端 2：发送提醒命令（通过 HTTP API）
cd simulation
python app_simulator.py --login 13800138000
python app_simulator.py --reminder "喝水提醒" --time "2026-06-20T10:00:00"
```

### 2. 运行集成测试

```bash
cd test
python test_reminder_flow.py
```

### 3. 部署到 RK3576

```bash
cd deploy
bash deploy.sh
```

### 4. 在 RK3576 上运行 (有 ROS2)

```bash
ssh cat@192.168.1.40
ros2 run robot_reminder reminder_node
```

### 5. 在 RK3576 上运行 (无 ROS2)

```bash
ssh cat@192.168.1.40
cd /home/cat/robot_reminder
python3 -c "from robot_reminder.reminder_node import main; main()"
```

## 实现内容

| 模块 | 文件 | 功能 |
|------|------|------|
| ROS2 节点 | `reminder_node.py` | WS连接、心跳、命令处理、TTS、播放、上报 |
| APP 模拟 | `app_simulator.py` | HTTP登录、绑定宠物、下发提醒命令 |
| 设备模拟 | `device_simulator.py` | WS连接、Auth、Heartbeat、命令处理 |
| 集成测试 | `test_reminder_flow.py` | HTTP API + WS 全流程验证 |
| 部署脚本 | `deploy.sh` | 自动部署到 RK3576 |

## 支持的 TTS 后端

| 后端 | 平台 | 优先级 |
|------|------|--------|
| PowerShell TTS (Huihui) | Windows | 1️⃣ 最快 |
| edge-tts (Xiaoyi) | 跨平台 | 2️⃣ 需联网 |
| espeak | Linux | 3️⃣ 备选 |

## 协议实现

- **HTTP API**: 登录 `/aipet/app/auth/{phone}/{code}` → 绑定宠物 → 发送命令 `/aipet/app/command/{pet_id}/reminder`
- **WebSocket**: 连接 `/openclaw-wwh/robot_websocket` → Auth → Heartbeat(30s) → `server_command` → `command_response`
- **提醒命令 (`reminder`)**: 服务器下发 `reminder_data`(title/content/time) → 设备 TTS 合成 → 播放 → 上报结果
