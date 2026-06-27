# robot_reminder_bt — 提醒系统行为树

## 架构
```
远程服务器
  ↓ WebSocket
websocket_node (robot_websocket)
  ↓ 发布 /robot/command
reminder_bt_driver (robot_reminder_bt)  ← 行为树驱动
  ├─ CheckNewReminder   ← 条件: 有新提醒?
  ├─ CheckTime          ← 条件: 到时间了?
  ├─ MarkExecuting      ← 动作: 标记执行中
  ├─ BuildTtsText       ← 动作: 构建TTS文本
  ├─ GenerateTTS        ← 动作: 调用voice_bridge播放
  ├─ SavePersistence    ← 动作: 保存到本地JSON
  ├─ RescheduleRepeating← 动作: 重复提醒重新调度
  └─ PublishStatus      ← 动作: 发布结果到 /robot/command_response
```

## 行为树结构
```
ProcessReminders (ReactiveSequence)
├── CheckNewReminder
└── ReminderProcess (ReactiveSequence)
    ├── CheckTimeCondition
    └── Fallback
        ├── RepeatPath (Sequence)
        │   ├── MarkExecuting
        │   ├── BuildTtsText
        │   ├── GenerateTTS
        │   ├── SavePersistence
        │   ├── RescheduleRepeating
        │   └── PublishStatus
        └── NoRepeatPath (Sequence)
            ├── MarkExecuting
            ├── BuildTtsText
            ├── GenerateTTS
            ├── SavePersistence
            └── PublishStatus
```

## 黑板键
| 键 | 类型 | 说明 |
|:---|:---|:---|
| pending_reminders | list | 待处理提醒列表 |
| reminder_id | str | 提醒ID |
| reminder_title | str | 提醒标题 |
| reminder_time | str | 提醒时间 ISO |
| tts_text | str | TTS文本 |
| data_dir | str | 存储目录 |

## 启动
```bash
ros2 launch robot_reminder_bt reminder_bt.launch.py
```
