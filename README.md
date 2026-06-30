# 叮叮提醒 v2.6 — BehaviorTree 稳定版

基于 Web + ROS2 + BehaviorTree 的提醒管理工具，支持通过远程服务器向板子发送提醒。

## 快速启动

```bash
# 板子端 (自动启动 by systemd)
http://192.168.1.209:8000   # 本地提醒管理
http://192.168.1.209:8001   # 远程发送（走服务器 → WS → BT → 语音）

# 核心节点 (板子上 ROS2):
ros2 launch robot_voice_bridge voice_bridge.launch.py  # 语音管线
ros2 run robot_reminder_bt reminder_bt_driver           # 行为树驱动 + ZMQ:1667
ros2 run robot_reminder_bt aipet_reminder_node         # 消息中继
ros2 run robot_reminder_bt reminder_ws_daemon          # WebSocket 守护
```

## 架构

```
Web(8000/8001) → 远程服务器(47.118.26.156) → WebSocket → reminder_ws_daemon
  → /reminder/ws/delivery → aipet_reminder_node → /robot/command → reminder_bt_driver
      ├─ CheckNewReminder  → 检查 pending/received/executing
      ├─ CheckTimeCondition → 时间到了?
      ├─ MarkExecuting     → 标记 executing
      ├─ BuildTtsText      → 构建 TTS 文本 (标题正确传入)
      ├─ GenerateTTS       → shell subprocess 调 voice_bridge
      ├─ RescheduleRepeating → 重复提醒重新排期
      └─ PublishStatus     → 标记 completed/failed → 回传服务器
```

## v2.6 关键修复

| 修复 | 说明 |
|:---|:---|
| 键名匹配 | CheckNewReminder `reminder_title` 键名统一，标题正确传入TTS |
| GoalAccepted | RC=124 超时不误报 FAIL，检查 stdout `Goal accepted` |
| PublishStatus | 处理完标记 completed/failed，不再永远 executing |
| 去重 | 同标题+同时间重复消息跳过 |
| WS断连 | on_close/on_error 日志 + ping_interval 优化 |
| SSH直推删除 | 提醒必须走远程服务器，不直推话题 |

## 行为树节点

| 节点 | 类型 | 说明 |
|:---|:---|:---|
| CheckNewReminder | Condition | 检查 pending/received/executing 状态的未处理提醒 |
| CheckTimeCondition | Condition | 检查是否到设定的提醒时间 |
| MarkExecuting | Action | 标记提醒状态为 executing |
| BuildTtsText | Action | 构建TTS语音文本 (reminder_title → tts_text) |
| GenerateTTS | AsyncAction | shell subprocess 调用 /voice/speak Action |
| RescheduleRepeating | Action | 重新计算重复提醒的下次时间 |
| PublishStatus | Action | 标记 completed/failed + 回传结果到服务器 |

## 黑板键 (Blackboard)

| 键 | 类型 | 说明 |
|:---|:---|:---|
| pending_reminders | list | 所有待处理提醒 |
| current_reminder | dict | 当前处理的提醒 |
| reminder_id | str | 提醒唯一ID |
| reminder_title | str | 提醒标题 |
| reminder_time | str | 提醒时间(ISO) |
| reminder_status | str | 状态(executing/completed/failed) |
| tts_text | str | TTS文本 |
| completed_count | int | 成功计数 |
| failed_count | int | 失败计数 |

## 板子信息

| 项 | 值 |
|:---|:---|
| IP | 192.168.1.209 |
| 用户 | cat |
| 序列号 | 6976f96f-bc80-56e3-9b27-13d12cdde9d3 |
| ROS2 | Humble |
| 板子 Git | 仅本地，不上传远程 |

## 版本

- **v2.6** (2026-06-30) — 标题修复 + GoalAccepted + 全链路稳定 ✅
- **v2.5** — PublishStatus 修复 + 去重
- **v2.1** — BehaviorTree 行为树集成
- **v2.0** — 话题通信 + 登录绑定
- **v1.0** — 数据库通信 + SQLite
