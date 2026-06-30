# 叮叮提醒 v2.6 — BehaviorTree 稳定版

基于 **Web + 远程服务器 + WebSocket + ROS2 + BehaviorTree** 的智能提醒管理工具。

## 项目简介

这是一个完整的提醒系统，支持通过 Web 页面远程发送提醒消息，经过远程服务器推送到 RK3576 板子，由行为树调度在设定时间自动调用 TTS 语音播放提醒内容。

```
┌──────────┐    HTTP     ┌──────────────┐   WebSocket   ┌─────────────────┐
│  Web UI  │ ──────────→ │ 远程服务器    │ ────────────→ │ RK3576 板子     │
│ :8000    │ ←────────── │ 47.118.26.156│ ←──────────── │ (ROS2 Humble)   │
│ :8001    │    API      │              │   结果回传     │                 │
└──────────┘             └──────────────┘              └────────┬────────┘
                                                               │
                                          ┌────────────────────┘
                                          ▼
                              ┌─────────────────────┐
                              │ reminder_ws_daemon  │ ← WebSocket 守护
                              │ aipet_reminder_node │ ← 消息中继
                              │ reminder_bt_driver  │ ← 行为树调度
                              │ voice_bridge        │ ← TTS + 喇叭播放
                              └─────────────────────┘
```

## 项目结构 (PC 端)

```
reminder_codex-1.1/
├── robot_reminder_bt/          ★ 核心：行为树提醒包 (部署到板子)
│   ├── bt_engine.py            # 轻量 Python 行为树引擎
│   ├── reminder_bt_nodes.py    # BT 专用节点 (CheckNewReminder/GenerateTTS等)
│   ├── reminder_bt_driver.py   # ROS2 驱动节点 + ZMQ 监控(:1667)
│   ├── groot2_server.py        # Groot2 ZMQ 可视化服务器
│   └── robot_reminder_bt/      # 板子专属节点
│       ├── aipet_reminder_node.py   # 消息中继 (WS↔BT)
│       └── reminder_ws_daemon.py    # WebSocket 守护 (连接远程服务器)
│
├── management/server.py        # Web 管理端 :8001 (远程发送)
├── management/index.html       # 8001 前端页面
│
├── backend/                    # PC 本地后端 :8000 (已弃用)
├── frontend/                   # PC 前端 (已弃用)
│
├── robot_aipet_relay/          # 同事的 WebSocket 中继包 (参考)
├── robot_websocket/            # ROS2 WebSocket 客户端包 (参考)
├── robot_reminder/             # 旧版提醒节点 (参考)
│
├── tools/
│   └── bt_monitor_server.py    # PC端 BT 监控 WebSocket 服务器 :8003
│
├── deploy/deploy.sh            # 部署脚本 (SSH 到板子)
├── simulation/                 # 本地模拟测试
│   ├── device_simulator.py
│   └── app_simulator.py
│
├── new_protocol/               # 协议文档
│   ├── AI-Pet-App-HTTP-API-协议文档(2).md
│   └── AI-Pet-WebSocket-协议文档(2).md
│
├── test/test_reminder_flow.py  # 集成测试
└── audio/                      # TTS 音频缓存
```

## 板子端文件 (RK3576, IP: 192.168.1.209)

板子上有 3 个关键位置：

### 1. ROS2 行为树包
**路径**: `/home/cat/ros2_ws/src/robot_reminder_bt/`

| 文件 | 作用 |
|:---|:---|
| `reminder_bt_driver.py` | ★ BT 驱动节点，含 ZMQ 监控端口 :1667 |
| `reminder_bt_nodes.py` | ★ BT 节点实现 (9个节点) |
| `bt_engine.py` | 轻量行为树引擎 |
| `robot_reminder_bt/aipet_reminder_node.py` | ★ 消息中继节点 |
| `robot_reminder_bt/reminder_ws_daemon.py` | ★ WebSocket 守护节点 |
| `reminders.json` | 持久化提醒数据 |

### 2. 远程发送服务
**路径**: `/home/cat/reminder_remote/`

| 文件 | 作用 |
|:---|:---|
| `server.py` | Flask 服务 :8001 (远程发送) |
| `index.html` | 8001 前端页面 |

### 3. 本地提醒服务 (系统自带)
**路径**: `/home/cat/reminder_system/`

| 文件 | 作用 |
|:---|:---|
| `run.py` | Flask 服务 :8000 (本地提醒管理) |
| `app/web_app.py` | 路由和 API |
| `app/templates/index.html` | 8000 前端页面 |

## 快速启动

### 板子端 (必要)
```bash
# SSH 到板子
ssh cat@192.168.1.209   # 密码: temppwd

# 1. 语音管线 (必须先启动)
source /opt/ros/humble/setup.bash
ros2 launch robot_voice_bridge voice_bridge.launch.py &

# 2. WebSocket 守护
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export PYTHONPATH=~/ros2_ws/src/robot_reminder_bt:$PYTHONPATH
nohup python3 -m robot_reminder_bt.reminder_ws_daemon > /tmp/ws.log 2>&1 &

# 3. 消息中继
nohup python3 -m robot_reminder_bt.aipet_reminder_node > /tmp/rn.log 2>&1 &

# 4. 行为树驱动 (含 ZMQ :1667)
echo '[]' > /data/reminders/pending_reminders.json
nohup python3 -m robot_reminder_bt.reminder_bt_driver   --ros-args -p tick_interval_ms:=200 -p command_topic:=/robot/command   > /tmp/bt.log 2>&1 &

# 5. 远程发送服务 (8001) — systemd 自动管理
sudo systemctl restart reminder
```

### PC 端 (可选, 8001 已在板子上)
```bash
# BT 监控 (Groot2 可视化)
cd tools && py bt_monitor_server.py   # http://127.0.0.1:8003
```

## 使用的 Web 页面

| 地址 | 端口 | 位置 | 功能 |
|:---|:---|:---|:---|
| `http://192.168.1.209:8000` | 8000 | 板子 | 本地提醒管理 (SQLite) |
| `http://192.168.1.209:8001` | 8001 | 板子 | ★ 远程发送提醒 (走服务器) |
| 行为树监视器 | :1667 | 板子 | ZMQ 端口, Groot2/BT Monitor 连接 |

## 行为树结构

```
ProcessReminders (ReactiveSequence)
├── CheckNewReminder       ← 检查 pending/received/executing 状态的提醒
└── ReminderProcess (ReactiveSequence)
    ├── CheckTimeCondition ← 时间到了?
    └── RepeatBranch (Fallback)
        ├── RepeatPath (Sequence)      ← 重复提醒
        │   ├── MarkExecuting
        │   ├── BuildTtsText
        │   ├── GenerateTTS            ← 调 /voice/speak Action
        │   ├── RescheduleRepeating
        │   └── PublishStatus
        └── NoRepeatPath (Sequence)    ← 非重复提醒
            ├── MarkExecuting
            ├── BuildTtsText
            ├── GenerateTTS
            └── PublishStatus
```

## 行为树节点

| 节点 | 类型 | 说明 |
|:---|:---|:---|
| CheckNewReminder | Condition | 检查 pending/received/executing 状态的未处理提醒 |
| CheckTimeCondition | Condition | 检查是否到设定时间 (Python datetime 比较) |
| MarkExecuting | Action | 标记提醒状态为 executing |
| BuildTtsText | Action | 构建 TTS 文本: `叮咚,提醒时间到啦,{标题},别忘了哦!` |
| GenerateTTS | AsyncAction | shell subprocess 调用 `/voice/speak` Action → 喇叭播放 |
| RescheduleRepeating | Action | 重复提醒重新计算下次时间 |
| PublishStatus | Action | 标记 completed/failed + 回传结果到远程服务器 |

## 黑板变量 (Blackboard)

| 键 | 类型 | 说明 |
|:---|:---|:---|
| pending_reminders | list | 待处理提醒列表 |
| current_reminder | dict | 当前处理的提醒 |
| reminder_id | str | 提醒 ID |
| reminder_title | str | 提醒标题 |
| reminder_time | str | 提醒时间 (ISO 格式) |
| reminder_status | str | executing / completed / failed |
| tts_text | str | 待合成的 TTS 文本 |
| completed_count | int | 成功计数 |
| failed_count | int | 失败计数 |

## v2.6 关键修复

| 修复 | 说明 |
|:---|:---|
| 键名匹配 | CheckNewReminder 统一用 `reminder_` 前缀, 标题正确传入 TTS |
| GoalAccepted | RC=124 超时不误报 FAIL, 检查 stdout `Goal accepted` |
| PublishStatus | 处理完标记 completed/failed, 不再永远 executing |
| 去重 | 同标题+同时间的重复消息跳过 |
| WS 断连 | on_close/on_error 加日志, ping_interval 优化 |
| SSH 直推删除 | 提醒必须走远程服务器, 不直推话题 |
| 语音调用 | shell subprocess 方式调 voice_bridge Action |

## 板子信息

| 项 | 值 |
|:---|:---|
| IP | 192.168.1.209 |
| 用户/密码 | cat / temppwd |
| 序列号 | 6976f96f-bc80-56e3-9b27-13d12cdde9d3 |
| ROS2 | Humble |
| 板子 Git 仓库 | `/home/cat/ros2_ws/src/robot_reminder_bt` (仅本地, 不上传远程) |

## 提醒消息全链路

```
1. 用户打开 http://192.168.1.209:8001
2. 登录 (手机号) → 发送提醒 (标题+时间+重复类型)
3. 8001 Flask → POST 远程服务器 API → 创建提醒
4. 服务器 → WebSocket push → reminder_ws_daemon
5. WS daemon → /reminder/ws/delivery 话题
6. aipet_reminder_node → /robot/command 话题
7. reminder_bt_driver → CheckNewReminder → CheckTimeCondition
8. 到时间 → MarkExecuting → BuildTtsText → GenerateTTS
9. GenerateTTS → shell subprocess → /voice/speak Action
10. voice_bridge → TTS合成 → robot_audio_node → 喇叭播放 🔊
11. PublishStatus → /robot/command_response → RN → /reminder/ws/result
12. WS daemon → WebSocket → 服务器 → 状态更新
```

## 版本历史

| 版本 | 日期 | 说明 |
|:---|:---|:---|
| **v2.6** | 2026-06-30 | 标题修复 + GoalAccepted + 全链路稳定 ✅ |
| v2.5 | 2026-06-30 | PublishStatus 修复 + 去重 |
| v2.1 | 2026-06-27 | BehaviorTree 行为树集成 |
| v2.0 | - | 话题通信 + 登录绑定 |
| v1.0 | - | SQLite 数据库通信 |
