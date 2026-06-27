# 叮叮提醒 v2.1 — BehaviorTree 版

基于 Web + ROS2 + BehaviorTree 的提醒管理工具，支持本地 PC 和 RK3576 板子协同工作。

## 快速启动

```bash
# PC 端
cd backend && py main.py        # http://127.0.0.1:8000 前端+API
cd management && py server.py   # http://127.0.0.1:8001 管理端(发送提醒)

# 板子端 (SSH)
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash
ros2 launch robot_voice_bridge voice_bridge.launch.py      # 语音管线
ros2 run robot_reminder_bt reminder_bt_driver               # 行为树提醒
```

## 架构

```
Web (8000/8001) → 远程服务器(airobot.lenudo.com) → WebSocket → 板子 ws_daemon_bridge
  → /robot/command → reminder_bt_driver (BehaviorTree)
      ├─ CheckNewReminder  → 有新提醒?
      ├─ CheckTime         → 到时间?
      ├─ BuildTtsText      → 构建TTS文本
      ├─ GenerateTTS       → voice_bridge Action 播放
      ├─ SavePersistence   → 本地JSON存储
      └─ PublishStatus     → /robot/command_response
```

## 项目结构

```
reminder_codex-1.1/
├── backend/              # FastAPI 后端 (8000)
│   ├── routes/board.py   # 板子提醒API + SSH
│   ├── routes/presence.py # 调度器提醒处理
│   └── services/         # TTS + scheduler
├── frontend/             # Web 前端 (8000)
├── management/           # 管理服务器 (8001)
│   └── server.py         # 登录/绑定/发送提醒
├── robot_reminder_bt/    # ★ BehaviorTree 提醒包
│   ├── bt_engine.py      # 轻量Python BT引擎
│   ├── reminder_bt_nodes.py  # 专用BT节点
│   ├── reminder_bt_driver.py # ROS2驱动节点
│   └── launch/
├── robot_reminder/       # ROS2 提醒节点(旧)
├── robot_websocket/      # ROS2 WebSocket节点
└── robot_voice_bridge/   # 语音桥接(speaker/)
```

## 行为树节点

| 节点 | 类型 | 说明 |
|:---|:---|:---|
| CheckNewReminder | Condition | 检查是否有pending/received的提醒 |
| CheckTimeCondition | Condition | 检查是否到设定的提醒时间 |
| CheckRepeating | Condition | 检查是否为重复提醒 |
| MarkExecuting | Action | 标记提醒状态为executing |
| BuildTtsText | Action | 构建TTS语音文本 |
| GenerateTTS | AsyncAction | 调用voice_bridge播放语音 |
| SavePersistence | Action | 保存到本地JSON文件 |
| RescheduleRepeating | Action | 重新计算重复提醒的下次时间 |
| PublishStatus | Action | 发布结果到/robot/command_response |

## 黑板键 (Blackboard)

| 键 | 类型 | 说明 |
|:---|:---|:---|
| pending_reminders | list | 所有待处理提醒列表 |
| current_reminder | dict | 当前正在处理的提醒 |
| reminder_id | str | 提醒唯一ID |
| reminder_title | str | 提醒标题 |
| reminder_time | str | 提醒时间(ISO格式) |
| tts_text | str | 待合成的TTS文本 |
| data_dir | str | 持久化存储目录 |

## TTS 播放优先级

| 位置 | 方式 |
|:---|:---|
| PC 后端 | 1. 本地 PowerShell TTS + pygame |
| | 2. edge-tts |
| 板子 BT | voice_bridge Action → doubao TTS → robot_audio_node → ALSA |

## 版本

- **v2.1** (2026-06-27) — BehaviorTree 行为树集成
- **v2.0** — 话题通信 + 登录绑定 + 本地试听
- **v1.0** — 数据库通信 + SQLite
