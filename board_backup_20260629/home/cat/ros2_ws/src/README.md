# robot_reminder_bt — 提醒系统行为树

## 架构总览

```
┌────────────────────────────────────────────────────────┐
│                   行为树调度器                          │
│  (每 100ms tick 一次)                                   │
│                                                        │
│  ReactiveSequence("system_main_loop")                  │
│  ├─ Condition("有待触发提醒?")                          │
│  └─ Sequence("执行提醒")                               │
│      ├─ Action("取提醒内容")                            │
│      ├─ Retry("合成语音", ×2)                          │
│      │   └─ Action("GenerateTTS")                      │
│      ├─ Retry("播放语音", ×2)                          │
│      │   └─ Action("PlayAudio")                        │
│      ├─ Retry("WS通知", ×3)                            │
│      │   └─ Action("NotifyWebSocket")                  │
│      ├─ Action("标记已触发")                            │
│      └─ Action("记录日志")                             │
└────────────┬───────────────────────────────┬────────────┘
             │                               │
             ▼                               ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  提醒系统 (Flask) │          │  WebSocket 节点    │
    │  192.168.1.70:5000│          │  robot_websocket   │
    │                   │          │                    │
    │  /api/stats       │          │  /robot/command    │
    │  /api/reminders   │          │  /robot/status     │
    │  /api/test-tts    │          │  /robot/chat       │
    └──────────────────┘          └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │  doubao TTS 节点  │
    │  /tts/text        │
    │  /tts/audio       │
    └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │  audio_node       │
    │  FFmpeg → ALSA    │
    │  → 喇叭出声 🔊    │
    └──────────────────┘
```

## 包结构

```
robot_reminder_bt/
├── README.md                          ← 本文档
├── package.xml                        ← ROS2 包配置
├── setup.py / setup.cfg               ← Python 包安装
├── CMakeLists.txt                     ← C++ 编译配置
│
├── config/
│   ├── reminder_bt_config.yaml        ← ROS2 参数
│   └── trees/
│       └── reminder_bt_v3.xml         ← BT.CPP 行为树定义
│
├── launch/
│   └── reminder_bt.launch.py          ← ROS2 启动文件
│
├── robot_reminder_bt/                 ← Python 源码
│   ├── __init__.py
│   ├── bt_engine.py                   ← 轻量行为树引擎
│   ├── reminder_nodes.py              ← 自定义 BT 节点
│   ├── reminder_tree.py               ← 树构建
│   └── reminder_bt_node.py            ← ROS2 节点入口
│
├── include/robot_reminder_bt/         ← C++ 头文件
│   └── reminder_nodes.hpp
│
├── src/                               ← C++ 源码
│   ├── reminder_nodes.cpp             ← BT 节点实现
│   └── reminder_bt_main.cpp           ← ROS2 主入口
│
├── test/
│   ├── test_bt_local.py               ← Windows 本地测试
│   └── test_with_mock.py              ← Mock 测试
│
├── scripts/
│   ├── run_windows.bat                ← Windows 一键测试
│   └── run_board.sh                   ← 板子部署
│
└── docs/
    └── ARCHITECTURE.md                ← 本文
```

## 双版本设计

| 版本 | 语言 | 用途 | 运行环境 |
|------|------|------|---------|
| Python 版 | Python 3 | Windows 调试 | Windows / 板子 |
| C++ 版 | C++17 | 生产部署 | 板子 (RK3576) |

两个版本共享相同的**行为树结构**（BT.CPP XML 定义），逻辑等价。

## Windows 调试

```bash
cd robot_reminder_bt
python test\test_bt_local.py
```

或用批处理菜单：
```bash
scripts\run_windows.bat
```

## 板子部署

### Python 版
```bash
# 在板子上克隆/复制项目到 ROS2 workspace
cd ~/ros2_ws
cp -r robot_reminder_bt src/

# 编译安装
colcon build --packages-select robot_reminder_bt
source install/setup.bash

# 运行
ros2 launch robot_reminder_bt reminder_bt.launch.py
```

### C++ 版
```bash
colcon build --packages-select robot_reminder_bt
source install/setup.bash
ros2 run robot_reminder_bt reminder_bt_node \
  --ros-args \
  -p api_url:=http://192.168.1.70:5000 \
  -p bt_xml:=$(ros2 pkg prefix robot_reminder_bt)/share/robot_reminder_bt/config/trees/reminder_bt_v3.xml
```

## 行为树节点说明

| 节点名 | 类型 | 输入 | 输出 | 功能 |
|--------|------|------|------|------|
| CheckPendingReminder | Condition | api_url | reminder_list | HTTP GET /api/stats, 有 pending→SUCCESS |
| FetchReminder | Action | reminder_list | current_reminder | 取第一条提醒内容 |
| GenerateTTS | Action | current_reminder | — | 发布文本到 /tts/text |
| PlayAudio | Action | current_reminder | — | 等待 /audio/complete |
| NotifyWebSocket | Action | current_reminder | — | 发 command_response 到 /robot/command |
| MarkTriggered | Action | current_reminder | — | HTTP POST /api/reminders/{id}/trigger |
| LogReminder | Action | current_reminder | — | 日志记录 |

## 依赖

- ROS2 Humble
- Python 3.8+
- requests (可选，HTTP 调用用)
- BehaviorTree.CPP v3 (C++ 版)
- robot_reminder (原有提醒节点)
- robot_websocket (原有 WebSocket 节点)
