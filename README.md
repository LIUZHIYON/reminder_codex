# 叮叮提醒 v2.8 — BehaviorTree 稳定版

基于 **Web + 远程服务器 + WebSocket + ROS2 + BehaviorTree** 的智能提醒管理工具。

## 项目简介

这是一个完整的提醒系统，支持通过 Web 页面远程发送提醒消息，经过远程服务器推送到 RK3576 板子，由行为树调度在设定时间自动调用 TTS 语音播放提醒内容。

```
┌──────────┐    HTTP     ┌──────────────┐   WebSocket   ┌─────────────────┐
│  Web UI  │ ──────────→ │ 远程服务器    │ ────────────→ │ RK3576 板子     │
│ :8001    │ ←────────── │ 47.118.26.156│ ←──────────── │ (ROS2 Humble)   │
└──────────┘             └──────────────┘              └────────┬────────┘
                                                               │
                                          ┌────────────────────┘
                                          ▼
                              ┌─────────────────────────────────┐
                              │ reminder_ws_daemon  (你的)       │
                              │ aipet_reminder_node (你的)       │
                              │ reminder_bt_driver  (你的)       │
                              │ voice_bridge                     │
                              │ tts_node_patched                 │
                              │ robot_audio_node                 │
                              └─────────────────────────────────┘
```

## 项目结构

```
reminder_codex-1.1/
├── robot_reminder_bt/          ★ 核心：行为树提醒包
│   ├── bt_engine.py            # 轻量 Python 行为树引擎
│   ├── reminder_bt_nodes.py    # BT 节点 (GenerateTTS 等)
│   ├── reminder_bt_driver.py   # ROS2 驱动节点
│   ├── groot2_server.py        # Groot2 ZMQ 可视化
│   ├── config/                 # 配置文件
│   ├── launch/                 # ROS2 launch 文件
│   └── robot_reminder_bt/      # 包内节点
│       ├── aipet_reminder_node.py
│       └── reminder_ws_daemon.py
│
├── reminder_remote/            # 8001 前端服务
│   ├── server.py               # Flask 服务
│   └── index.html              # 前端页面
│
├── 板子文件备份/               # 板子文件本地备份
│   └── home/cat/...
│
├── backend/                    # PC 本地后端 (已弃用)
├── frontend/                   # PC 前端 (已弃用)
├── tools/                      # 工具脚本
├── deploy/                     # 部署脚本
├── simulation/                 # 本地模拟测试
├── new_protocol/               # 协议文档
└── test/                       # 集成测试
```

## 你的 3 个节点

| 节点 | 文件路径（板子） | 功能 |
|:---|:---|:---|
| **reminder_ws_daemon** | `robot_reminder_bt/reminder_ws_daemon.py` | WebSocket 连接云端 |
| **aipet_reminder_node** | `robot_reminder_bt/aipet_reminder_node.py` | 消息中继转发 |
| **reminder_bt_driver** | `reminder_bt_driver.py` | 行为树调度核心 |

## 快速启动（板子端）

```bash
ssh cat@192.168.1.190
source /opt/ros/humble/setup.bash
export PYTHONPATH=/home/cat/ros2_ws/src:\$PYTHONPATH

# 语音服务
ros2 launch robot_audio_node robot_audio_node.launch.py &
ros2 launch robot_doubao_tts_node tts_patched.launch.py &
ros2 launch robot_voice_bridge voice_bridge.launch.py &

# 3 个提醒节点
python3 /home/cat/ros2_ws/src/robot_reminder_bt/robot_reminder_bt/reminder_ws_daemon.py \
  --ros-args -p server_host:=47.118.26.156 -p server_port:=8000 \
  -p serial_number:=6976f96f-bc80-56e3-9b27-13d12cdde9d3 &

python3 -m robot_reminder_bt.aipet_reminder_node &

python3 -m robot_reminder_bt.reminder_bt_driver \
  --ros-args -p tick_interval_ms:=200 -p command_topic:=/robot/command &

# 8001 前端
python3 /home/cat/reminder_remote/server.py &
```

## 行为树结构

```
ProcessReminders (ReactiveSequence)
├── CheckNewReminder
└── ReminderProcess (ReactiveSequence)
    ├── CheckTimeCondition
    └── RepeatBranch (Fallback)
        ├── RepeatPath (Sequence)
        │   ├── MarkExecuting
        │   ├── BuildTtsText
        │   ├── GenerateTTS  ← 调 /voice/speak Action
        │   ├── RescheduleRepeating
        │   └── PublishStatus
        └── NoRepeatPath (Sequence)
            ├── MarkExecuting
            ├── BuildTtsText
            ├── GenerateTTS
            └── PublishStatus
```

## GenerateTTS 核心逻辑

```
on_start() → 启动线程, 返回 RUNNING
_run()     → subprocess ros2 action send_goal /voice/speak
on_tick()  → 线程活着? RUNNING / 结束? SUCCESS/FAILURE
on_halt()  → 重置状态
```

## 版本历史

| 版本 | 说明 |
|:---|:---|
| **v2.8** | 板子文件备份 + 启动说明 |
| **v2.7** | GenerateTTS 修复: on_tick/on_halt 恢复 |
| **v2.6** | 标题修复 + GoalAccepted + 全链路稳定 |
| v2.5 | PublishStatus 修复 + 去重 |
| v2.1 | BehaviorTree 行为树集成 |
| v1.0 | SQLite 数据库通信 |
