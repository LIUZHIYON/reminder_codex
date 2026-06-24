# AI Pet 设备 WebSocket 协议文档

## 基础信息

| 项目 | 值 |
|------|-----|
| 连接地址 | `ws://47.118.26.156:8000/api/v1/aipet/ws/{serial_number}` |
| 认证端点 | `GET http://47.118.26.156:8000/api/v1/aipet/ws/auth/{serial_number}`（HTTP，获取连接令牌） |
| 消息格式 | JSON |
| 编码 | UTF-8 |
| 心跳间隔 | 建议 30 秒（Redis TTL 为 3 分钟） |

---

## 目录

1. [连接生命周期](#1-连接生命周期)
2. [通用响应信封](#2-通用响应信封)
3. [上行消息（设备→服务器）](#3-上行消息设备服务器)
   - [3.1 auth — 设备认证](#31-auth--设备认证)
   - [3.2 heartbeat — 心跳](#32-heartbeat--心跳)
   - [3.3 config_request — 配置请求](#33-config_request--配置请求)
   - [3.4 status_update — 状态上报](#34-status_update--状态上报)
   - [3.5 chat — 设备发起的聊天](#35-chat--设备发起的聊天)
   - [3.6 command_response — 指令执行结果](#36-command_response--指令执行结果)
   - [3.7 reminder_response — 提醒执行结果](#37-reminder_response--提醒执行结果)
   - [3.8 relay_message_response — 传话执行结果](#38-relay_message_response--传话执行结果)
   - [3.9 notification — 设备通知](#39-notification--设备通知)
   - [3.10 error — 错误上报](#310-error--错误上报)
   - [3.11 ack — 消息确认](#311-ack--消息确认)
   - [3.12 app_request — 业务请求](#312-app_request--业务请求)
4. [下行消息（服务器→设备）](#4-下行消息服务器设备)
   - [4.1 server_command — 服务器下发指令](#41-server_command--服务器下发指令)
   - [4.2 reminder_delivery — 待办事提醒下发](#42-reminder_delivery--待办事提醒下发)
   - [4.3 relay_message_delivery — 传话消息下发](#43-relay_message_delivery--传话消息下发)
   - [4.4 chat — 服务器转发聊天](#44-chat--服务器转发聊天)
   - [4.5 自动 ACK 回执](#45-自动-ack-回执)
5. [完整消息类型汇总](#5-完整消息类型汇总)
6. [指令生命周期](#6-指令生命周期)

---

## 1. 连接生命周期

```
Device                                    Server
  |                                          |
  |-- WebSocket Connect ------------------->|  ws://host/api/v1/aipet/ws/{serial_number}
  |                                          |  接受连接，等待认证
  |                                          |
  |-- { type: "auth", access_token: "..." }->|  验证 JWT 令牌
  |                                          |  注册全局连接管理器
  |<-- { type: "auth", success: true } ------|  推送离线缓冲消息
  |                                          |  开始速率限制
  |                                          |
  |-- { type: "heartbeat" } ---------------->| 刷新连接 TTL（每 30s）
  |<-- { type: "heartbeat", ... } -----------|
  |                                          |
  |-- ...业务消息... ------------------------>|
  |<-- ...业务响应 / server_command... ------|
  |                                          |
  |-- WebSocket Disconnect ----------------->|  注销连接，设置离线状态
```

**连接限制：** 全局连接数超过 `WS_CONNECTION_POOL_SIZE` 时，新连接被拒绝（close code 1013）。

---

## 2. 通用响应信封

所有服务器响应共享此结构（由 `BaseMessageHandler.create_response()` 生成）：

```json
{
  "success": true,
  "type": "message_type",
  "message": "人类可读的消息",
  "timestamp": 1718800000,
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 操作是否成功 |
| type | string | 消息类型（与请求 type 对应） |
| message | string | 人类可读的描述 |
| timestamp | int | Unix 时间戳（秒） |
| data | any | 业务数据（可选） |

---

## 3. 上行消息（设备→服务器）

### 3.1 auth — 设备认证

**方向:** 设备 → 服务器  
**认证:** 不需要（必须是首条消息）  
**Handler:** `AuthMessageHandler`

设备连接后必须立即发送此消息进行身份验证。

#### 请求

```json
{
  "type": "auth",
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 固定值 `"auth"` |
| access_token | string | 是 | 从 HTTP 端点 `/api/v1/aipet/ws/auth/{serial_number}` 获取的 JWT 令牌，可带 `"Bearer "` 前缀 |

#### 成功响应

```json
{
  "success": true,
  "type": "auth",
  "message": "认证成功",
  "timestamp": 1718800000,
  "data": {
    "id": 1,
    "serial_number": "AIPET-001",
    "register_by": "42",
    "first_register_date": "2025-01-01 00:00:00",
    "birth_day": "2025-01-01 00:00:00"
  }
}
```

#### 失败响应

```json
{
  "success": false,
  "type": "auth",
  "message": "认证失败",
  "timestamp": 1718800000
}
```

**可能的错误消息：** `"缺少access_token"` / `"AIPet token不合法"` / `"AIPet token已失效，请重新登录"`

#### 服务端行为

1. 验证 JWT 签名和有效期
2. 确认 Redis 中存储的 token 与提交的 token 一致（单设备强制）
3. 成功后注册全局连接，写入 `OnlineStatusModel` 到 Redis（TTL 3 分钟）

---

### 3.2 heartbeat — 心跳

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `HeartbeatMessageHandler`

设备定期发送心跳以维持在线状态。

#### 请求

```json
{
  "type": "heartbeat"
}
```

无额外必填字段。

#### 成功响应

```json
{
  "success": true,
  "type": "heartbeat",
  "message": "心跳正常",
  "timestamp": 1718800000,
  "data": {
    "server_time": "2025-01-15 12:30:00"
  }
}
```

#### 服务端行为

1. 从 Redis 读取现有 `OnlineStatusModel`
2. 更新 `last_heartbeat`、`last_ping` 为当前时间
3. 设置 `online: true`、`websocket_connected: true`
4. 清除 `disconnection_time` 和 `offline_reason`
5. 写回 Redis（TTL 3 分钟）
6. 调用 `connection_manager.update_connection_ttl()` 延长连接租约

---

### 3.3 config_request — 配置请求

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `ConfigRequestMessageHandler`

#### 请求

```json
{
  "type": "config_request",
  "aipet_id": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| aipet_id | int | 否 | 若省略则使用当前认证的宠物 ID |

#### 成功响应

```json
{
  "success": true,
  "type": "config_request",
  "message": "配置获取成功",
  "timestamp": 1718800000,
  "data": {
    "id": 1,
    "pet_id": 1,
    "pet_nickname": "Fluffy",
    "eye_style": "cute",
    "voice_style": "sweet",
    "personality": "lively",
    "hobby": "playing",
    "avatar_url": "https://...",
    "background_url": "https://...",
    "theme_color": "#FF69B4",
    "language": "zh-CN",
    "time_zone": "Asia/Shanghai",
    "interaction_mode": "normal",
    "config_json": { ... },
    "is_active": 1
  }
}
```

#### 无配置时响应

```json
{
  "success": true,
  "type": "config_request",
  "message": "该AI宠物暂无配置信息",
  "timestamp": 1718800000,
  "data": null
}
```

---

### 3.4 status_update — 状态上报

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `StatusUpdateMessageHandler`

设备定期或在状态变化时上报自身状态。

#### 请求

```json
{
  "type": "status_update",
  "status": {
    "battery": 85,
    "temperature": 36.5,
    "mood": "happy",
    "health": 100,
    "hunger": 60,
    "cleanliness": 80,
    "stamina": 75,
    "loyalty": 90,
    "experience": 2500,
    "energy": 45,
    "grade": 3,
    "max_exp": 5000
  }
}
```

`status` 对象中的所有字段均为可选。

#### 成功响应

```json
{
  "success": true,
  "type": "status_update",
  "message": "状态更新成功",
  "timestamp": 1718800000,
  "data": {
    "saved_status": { "battery": 85, "mood": "happy", ... },
    "save_time": "2025-01-15T12:30:00.123456"
  }
}
```

#### 服务端行为

- 使用 `AiPetStateModel` 验证 status 对象
- 包裹元数据（`aipet_id`、`serial_number`、`update_time`、`timestamp`）
- 保存到 Redis key `aipet_state:{aipet_id}`，**无过期时间**（长期存储）

---

### 3.5 chat — 设备发起的聊天

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `ChatMessageHandler`

设备向服务器发送聊天消息（当前实现为简单回显，预留 AI 对话逻辑扩展点）。

#### 请求

```json
{
  "type": "chat",
  "content": "用户说了什么",
  "chat_type": "text"
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| content | string | — | 消息内容（必填） |
| chat_type | string | "text" | 消息类型 |

#### 成功响应

```json
{
  "success": true,
  "type": "chat",
  "message": "消息发送成功",
  "timestamp": 1718800000,
  "data": {
    "content": "收到您的消息: 用户说了什么",
    "type": "text",
    "timestamp": "2025-01-15 12:30:00"
  }
}
```

---

### 3.6 command_response — 指令执行结果

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `CommandResponseMessageHandler`

设备执行完服务器下发的 `server_command` 后，通过此消息反馈执行结果。

> **注意：** 此消息仅用于 `AiPetCommandMessageType` 通用指令（print、wake_up、set_volume 等）。**提醒和传话的执行结果请使用 [reminder_response](#37-reminder_response--提醒执行结果) 和 [relay_message_response](#38-relay_message_response--传话执行结果)**。

#### 请求

```json
{
  "type": "command_response",
  "command_id": "cmd_1_1718800000_12345",
  "command": "set_volume",
  "status": "success",
  "result": { "volume": 75 },
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| command_id | string | 是 | 对应 server_command 的 command_id |
| command | string | 是 | 执行的指令类型（必须是 `AiPetCommandMessageType` 枚举值，**不含 reminder/relay**） |
| status | string | 否 | 执行状态：`"success"` / `"failed"` / `"executing"` / `"unknown"` |
| result | object | 否 | 执行结果数据（默认为 `{}`） |
| error | string | 否 | 错误信息（status=failed 时） |

#### 成功响应

```json
{
  "success": true,
  "type": "command_response",
  "message": "指令执行结果已记录",
  "timestamp": 1718800000,
  "data": {
    "command_id": "cmd_1_1718800000_12345",
    "recorded_at": "2025-01-15T12:30:00.123456"
  }
}
```

#### 服务端行为

1. 验证 `command` 是否为有效的 `AiPetCommandMessageType` 枚举值（**reminder 和 relay 已从该枚举移除，不会被此 handler 处理**）
2. 将执行记录推入 Redis list `aipet_command_history:{aipet_id}`（保留最近 50 条）
3. 如果提供了 `command_id`，更新 MySQL `ai_pet_command_logs` 表（`status`、`result`、`error_message`、`executed_time`）
4. **不再**更新 `ai_pet_reminders` 或 `ai_pet_relay_messages` 表（提醒/传话结果由专用 handler 处理）

> **注意：** 指令下发时（`server_command`），`send_command_to_aipet()` 已统一调用 `_write_command_log()` 写入 `ai_pet_command_logs` 的初始记录（含完整 `command_params`）。`command_response` 是在此基础上追加执行状态和结果。

---

### 3.7 reminder_response — 提醒执行结果

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `ReminderResponseMessageHandler`

设备执行完服务器下发的 `reminder_delivery` 后，通过此消息反馈提醒执行结果。**此消息独立于 command 体系，只更新 `ai_pet_reminders` 表。**

#### 请求

```json
{
  "type": "reminder_response",
  "reminder_id": "rmd_1_1718800000_abc123",
  "status": "completed",
  "result": { "played": true, "user_acknowledged": true },
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reminder_id | string | 是 | 对应 `reminder_delivery` 的 reminder_id |
| status | string | 否 | 执行状态：`"completed"` / `"failed"` / `"executing"` |
| result | object | 否 | 执行结果数据（默认为 `{}`） |
| error | string | 否 | 错误信息（status=failed 时） |

#### 成功响应

```json
{
  "success": true,
  "type": "reminder_response",
  "message": "提醒执行结果已记录",
  "timestamp": 1718800000,
  "data": {
    "reminder_id": "rmd_1_1718800000_abc123"
  }
}
```

#### 服务端行为

1. 校验 `reminder_id` 必填
2. 调用 `AiPetRemindersDao.update_by_delivery_id()` 更新 `ai_pet_reminders` 表：
   - `status`、`result`、`error_message`、`executed_time`
3. **不写入** `ai_pet_command_logs`

---

### 3.8 relay_message_response — 传话执行结果

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `RelayMessageResponseMessageHandler`

设备执行完服务器下发的 `relay_message_delivery` 后，通过此消息反馈传话执行结果。**此消息独立于 command 体系，只更新 `ai_pet_relay_messages` 表。**

#### 请求

```json
{
  "type": "relay_message_response",
  "relay_id": "rly_1_1718800000_def456",
  "status": "completed",
  "result": { "played": true, "duration_ms": 3200 },
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| relay_id | string | 是 | 对应 `relay_message_delivery` 的 relay_id |
| status | string | 否 | 执行状态：`"completed"` / `"failed"` / `"executing"` |
| result | object | 否 | 执行结果数据（默认为 `{}`） |
| error | string | 否 | 错误信息（status=failed 时） |

#### 成功响应

```json
{
  "success": true,
  "type": "relay_message_response",
  "message": "传话执行结果已记录",
  "timestamp": 1718800000,
  "data": {
    "relay_id": "rly_1_1718800000_def456"
  }
}
```

#### 服务端行为

1. 校验 `relay_id` 必填
2. 调用 `AiPetRelayMessagesDao.update_by_delivery_id()` 更新 `ai_pet_relay_messages` 表：
   - `status`、`result`、`error_message`、`executed_time`
3. **不写入** `ai_pet_command_logs`

---

### 3.9 notification — 设备通知

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `NotificationMessageHandler`

设备向服务器报告事件通知。

#### 请求

```json
{
  "type": "notification",
  "notification_type": "system_update",
  "title": "低电量",
  "content": "AI宠物电量仅剩 20%",
  "priority": "high"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| notification_type | string | 是 | 通知类型枚举（见下方） |
| title | string | 否 | 通知标题 |
| content | string | 否 | 通知内容 |
| priority | string | 否 | 优先级（默认 `"normal"`）：low / normal / high / urgent |

**notification_type 枚举：**
| 值 | 说明 |
|---|------|
| system_update | 系统更新通知 |
| config_changed | 配置变更通知 |
| reminder | 提醒通知 |
| alert | 告警通知 |
| maintenance | 维护通知 |

#### 成功响应

```json
{
  "success": true,
  "type": "notification",
  "message": "通知发送成功",
  "timestamp": 1718800000,
  "data": {
    "notification_id": "sys_1_1737000000",
    "type": "system_update",
    "title": "低电量",
    "content": "AI宠物电量仅剩 20%",
    "priority": "high",
    "timestamp": "2025-01-15 12:30:00",
    "action_required": true
  }
}
```

---

### 3.10 error — 错误上报

**方向:** 设备 → 服务器  
**认证:** 不需要  
**Handler:** `ErrorMessageHandler`

设备向服务器报告运行时错误。

#### 请求

```json
{
  "type": "error",
  "error_code": "CONNECTION_LOST",
  "error_message": "WiFi 意外断开",
  "error_details": { "rssi": -80 }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| error_code | string | 错误编码 |
| error_message | string | 错误描述 |
| error_details | object | 错误详情（可选） |

**已知错误码与建议：**
| error_code | 服务器建议 |
|---|---|
| AUTH_FAILED | 检查凭证并重新连接 |
| CONNECTION_LOST | 检查网络环境 |
| INVALID_MESSAGE | 检查消息结构 |
| PERMISSION_DENIED | 联系管理员 |
| SERVICE_UNAVAILABLE | 稍后重试 |
| CONFIG_ERROR | 检查配置参数 |
| TIMEOUT | 重试操作 |
| UNKNOWN_COMMAND | 检查支持的指令列表 |

#### 成功响应

```json
{
  "success": true,
  "type": "error",
  "message": "错误信息已记录",
  "timestamp": 1718800000,
  "data": {
    "error_id": "err_1737000000",
    "error_code": "CONNECTION_LOST",
    "error_message": "WiFi 意外断开",
    "error_details": { "rssi": -80 },
    "suggestion": "网络连接不稳定，建议检查网络环境",
    "timestamp": "2025-01-15 12:30:00",
    "aipet_id": 1,
    "resolved": false,
    "support_contact": "请联系技术支持获取帮助"
  }
}
```

---

### 3.11 ack — 消息确认

**方向:** 设备 → 服务器  
**认证:** 不需要  
**Handler:** `AckMessageHandler`

设备确认收到服务器的某条消息。

#### 请求

```json
{
  "type": "ack",
  "message_id": "msg_1_1737000000_12345"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message_id | string | 是 | 确认的消息 ID |

#### 成功响应

```json
{
  "success": true,
  "type": "ack",
  "message": "ACK 已处理",
  "timestamp": 1718800000,
  "data": { "message_id": "msg_1_1737000000_12345" }
}
```

#### message_id 未知时

```json
{
  "success": false,
  "type": "ack",
  "message": "未知的消息 ID",
  "timestamp": 1718800000,
  "data": { "message_id": "msg_1_1737000000_12345" }
}
```

---

### 3.12 app_request — 业务请求

**方向:** 设备 → 服务器  
**认证:** 需要  
**Handler:** `AppRequestMessageHandler`

设备通过此消息查询服务端业务数据。支持 21 种 `request_type`。

#### 通用请求格式

```json
{
  "type": "app_request",
  "request_type": "get_reminders",
  "page_num": 1,
  "page_size": 10,
  "status": "sent"
}
```

#### 支持的 request_type 一览

| request_type | 说明 | 额外参数 |
|---|---|---|
| `get_chat_logs` | 查询聊天记录 | page_num, page_size, command_type, message_type |
| `get_command_logs` | 查询指令日志 | page_num, page_size, command_type, status |
| `get_reminders` | 查询待办事提醒 | page_num, page_size, status |
| `get_family_members` | 查询家庭成员 | — |
| `get_pet_items` | 查询宠物道具 | — |
| `get_pet_attributes` | 查询宠物属性 | — |
| `get_user_items` | 查询用户道具 | — |
| `get_level_privileges` | 查询等级特权 | level（可选） |
| `get_task_configs` | 查询任务配置 | — |
| `get_task_completion_records` | 查询任务完成记录 | — |
| `get_user_virtual_currency` | 查询虚拟货币 | — |
| `get_user_treasure_chest` | 查询用户宝箱 | — |
| `get_treasure_chest_list` | 查询宝箱配置列表 | — |
| `get_treasure_chest_rewards` | 查询宝箱奖励 | chest_id |
| `combine_treasure_chest` | 合成宝箱 | chest_id |
| `combine_fragment_to_chest` | 按道具碎片合成宝箱 | fragment_item_id, required_quantity, target_chest_id |
| `open_treasure_chest` | 开启宝箱 | chest_id |
| `complete_task` | 完成任务 | task_id |
| `claim_task_reward` | 领取任务奖励 | task_id |
| `post_moment` | 发布动态 | content, media_type, media_urls, privacy_setting, location |

#### 通用响应格式

```json
{
  "success": true,
  "type": "get_reminders",
  "message": "获取提醒列表成功",
  "timestamp": 1718800000,
  "data": {
    "rows": [
      {
        "id": 1,
        "title": "起床提醒",
        "content": "该起床了",
        "reminder_time": "2026-06-20T07:00:00",
        "status": "sent"
      }
    ],
    "total": 1,
    "pageNum": 1,
    "pageSize": 10,
    "hasNext": false
  }
}
```

> **注意：** 响应的 `type` 字段为具体的 `request_type` 值（如 `"get_reminders"`），而非 `"app_request"`。

#### 示例：开启宝箱

**请求：**
```json
{
  "type": "app_request",
  "request_type": "open_treasure_chest",
  "chest_id": 1
}
```

**响应：**
```json
{
  "success": true,
  "type": "open_treasure_chest",
  "message": "宝箱开启成功",
  "timestamp": 1718800000,
  "data": {
    "rewards": [
      { "reward_type": "gold", "reward_amount": 100 },
      { "reward_type": "item", "reward_amount": 1, "item_id": 5 }
    ]
  }
}
```

#### 示例：发布动态

**请求：**
```json
{
  "type": "app_request",
  "request_type": "post_moment",
  "content": "今天在公园玩得很开心！",
  "media_type": 1,
  "media_urls": "",
  "privacy_setting": 1,
  "location": "中央公园",
  "extra_data": {}
}
```

---

## 4. 下行消息（服务器→设备）

### 4.1 server_command — 服务器下发指令

**方向:** 服务器 → 设备  
**触发方式:** 服务器调用 `AIPetWebsocketService.send_command_to_aipet()`

服务器通过此消息向设备下发各种操作指令。设备应在执行完成后通过 `command_response` 反馈结果。

#### 消息格式（通用）

```json
{
  "type": "server_command",
  "command_id": "cmd_1_1718800000_12345",
  "command": "reminder",
  "command_params": { ... },
  "priority": "normal",
  "timestamp": "2025-01-15T12:30:00.123456",
  "timeout": 30
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 `"server_command"` |
| command_id | string | 指令唯一 ID，格式：`cmd_{aipet_id}_{timestamp}_{hash}` |
| command | string | 指令类型（见下方枚举） |
| command_params | object | 指令参数（因 command 类型而异） |
| priority | string | 优先级：low / normal / high / urgent |
| timestamp | string | ISO 8601 时间戳 |
| timeout | int | 超时秒数（默认 30） |

**指令优先级说明：**
| priority | 说明 | 设备处理建议 |
|---|---|---|
| low | 低优先级 | 空闲时处理 |
| normal | 普通 | 正常队列 |
| high | 高优先级 | 优先处理 |
| urgent | 紧急 | 立即处理（如重启、恢复出厂） |

---

#### 4.1.1 print — 打印

```json
{
  "type": "server_command",
  "command": "print",
  "command_params": {
    "file_url": "https://cdn.example.com/print/doc.pdf",
    "file_type": "pdf",
    "print_source": "app_chat"
  }
}
```

---

#### 4.1.2 其他指令

```json
// 唤醒
{ "command": "wake_up", "command_params": {} }

// 休眠
{ "command": "sleep", "command_params": {} }

// 播放声音
{ "command": "play_sound", "command_params": { "sound_id": "alert_01", "volume": 80, "repeat": 3 } }

// 设置心情
{ "command": "set_mood", "command_params": { "mood": "happy", "intensity": 0.8 } }

// 设置音量
{ "command": "set_volume", "command_params": { "volume": 75 } }

// 设置亮度
{ "command": "set_brightness", "command_params": { "brightness": 90 } }

// 拍照
{ "command": "take_photo", "command_params": { "quality": "high", "flash": false } }

// 开始录音
{ "command": "start_recording", "command_params": { "duration": 30, "format": "mp3" } }

// 停止录音
{ "command": "stop_recording", "command_params": {} }

// 重启设备
{ "command": "restart", "command_params": {} }

// 固件更新
{ "command": "update_firmware", "command_params": { "firmware_url": "https://.../v2.0.bin", "version": "2.0.0" } }

// 恢复出厂设置
{ "command": "factory_reset", "command_params": {} }

// 进入维护模式
{ "command": "enter_maintenance", "command_params": {} }

// 退出维护模式
{ "command": "exit_maintenance", "command_params": {} }

// 获取状态
{ "command": "upload_status", "command_params": {} }

// 获取配置
{ "command": "update_config", "command_params": { "config_key": "all" } }
```

---

### 4.2 reminder_delivery — 待办事提醒下发

**方向:** 服务器 → 设备  
**触发方式:** 服务器调用 `AIPetWebsocketService.send_reminder_to_aipet()`

> **注意：** 提醒已脱离 `server_command` 体系，走独立的 `reminder_delivery` 通道。此通道**不写入** `ai_pet_command_logs`。

#### 消息格式

```json
{
  "type": "reminder_delivery",
  "reminder_id": "rmd_1_1718800000_abc123",
  "reminder_data": {
    "title": "起床提醒",
    "content": "该起床了，今天有重要会议",
    "reminder_time": "2026-06-20T07:00:00",
    "repeat_type": "daily"
  },
  "reminder_source": "app_chat",
  "priority": "high",
  "timestamp": "2025-01-15T12:30:00.123456",
  "timeout": 30
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 `"reminder_delivery"` |
| reminder_id | string | 提醒唯一 ID，格式：`rmd_{aipet_id}_{timestamp}_{hash}` |
| reminder_data | object | 提醒数据 |
| reminder_data.title | string | 提醒标题 |
| reminder_data.content | string | 提醒内容 |
| reminder_data.reminder_time | string | 提醒触发时间（ISO 8601） |
| reminder_data.repeat_type | string | 重复类型：none / daily / weekly / monthly |
| reminder_source | string | 来源：app_chat / admin_panel |
| priority | string | 优先级（默认 high） |
| timestamp | string | ISO 8601 时间戳 |
| timeout | int | 超时秒数（默认 30） |

#### 设备执行完成后应回复

设备应通过 `reminder_response` 消息回报执行结果（见 [§3.7](#37-reminder_response--提醒执行结果)）。

---

### 4.3 relay_message_delivery — 传话消息下发

**方向:** 服务器 → 设备  
**触发方式:** 服务器调用 `AIPetWebsocketService.send_relay_message_to_aipet()`

> **注意：** 传话已脱离 `server_command` 体系，走独立的 `relay_message_delivery` 通道。此通道**不写入** `ai_pet_command_logs`。

#### 文本模式

```json
{
  "type": "relay_message_delivery",
  "relay_id": "rly_1_1718800000_def456",
  "content_type": "text",
  "content": "回家吃饭了",
  "relay_from": "妈妈",
  "relay_to": "孩子",
  "voice_style": "sweet",
  "speed": 1.0,
  "relay_source": "app_chat",
  "priority": "high",
  "timestamp": "2025-01-15T12:30:00.123456",
  "timeout": 30
}
```

#### 语音模式

```json
{
  "type": "relay_message_delivery",
  "relay_id": "rly_1_1718800000_def456",
  "content_type": "voice",
  "media_url": "https://cdn.example.com/audio/msg123.mp3",
  "media_duration": 15,
  "media_size": 120000,
  "relay_from": "爸爸",
  "relay_to": "孩子",
  "relay_source": "admin_panel",
  "priority": "high",
  "timestamp": "2025-01-15T12:30:00.123456",
  "timeout": 30
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 `"relay_message_delivery"` |
| relay_id | string | 传话唯一 ID，格式：`rly_{aipet_id}_{timestamp}_{hash}` |
| content_type | string | text / voice |
| content | string | 文本内容（text 模式，≤200 字符） |
| media_url | string | 音频 URL（voice 模式） |
| media_duration | int | 音频时长，秒（voice 模式） |
| media_size | int | 音频大小，字节（voice 模式） |
| relay_from | string | 传话发起者 |
| relay_to | string | 传话目标 |
| voice_style | string | 语音风格：sweet / normal |
| speed | float | 语速（如 1.0） |
| relay_source | string | 来源：app_chat / admin_panel |
| priority | string | 优先级（默认 high） |
| timestamp | string | ISO 8601 时间戳 |
| timeout | int | 超时秒数（默认 30） |

#### 设备执行完成后应回复

设备应通过 `relay_message_response` 消息回报执行结果（见 [§3.8](#38-relay_message_response--传话执行结果)）。

---

### 4.4 chat — 服务器转发聊天

**方向:** 服务器 → 设备  
**触发方式:** 服务器调用 `AIPetWebsocketService.send_chat_to_aipet()`

服务器将用户在 App 发送的聊天消息转发给设备。

```json
{
  "type": "chat",
  "message_id": "msg_1_1718800000_12345",
  "content": "你好 Fluffy，今天过得怎么样？",
  "message_type": "text",
  "priority": "normal",
  "timestamp": "2025-01-15T12:30:00.123456"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 `"chat"` |
| message_id | string | 消息 ID，格式：`msg_{aipet_id}_{timestamp}_{hash}` |
| content | string | 消息内容 |
| message_type | string | 消息类型：text / voice / image / command / emotion / file |
| priority | string | low / normal / high / urgent |
| timestamp | string | ISO 8601 |

---

### 4.5 自动 ACK 回执

当设备发送的消息中包含 `"require_ack": true` 和 `"message_id"` 时，服务器在成功处理后自动回复：

```json
{
  "type": "ack",
  "success": true,
  "message": "消息已收到",
  "data": { "message_id": "msg_1_1718800000_12345" },
  "timestamp": 1718800000
}
```

---

## 5. 完整消息类型汇总

| type | 方向 | 认证 | 说明 |
|------|------|------|------|
| `auth` | 设备→服务器 | 否 | 设备认证（必须首条） |
| `heartbeat` | 设备→服务器 | 是 | 心跳保活 |
| `config_request` | 设备→服务器 | 是 | 请求配置 |
| `status_update` | 设备→服务器 | 是 | 状态上报 |
| `chat` | 设备→服务器 | 是 | 设备发起聊天 |
| `chat` | 服务器→设备 | — | 服务器转发聊天 |
| `command_response` | 设备→服务器 | 是 | 指令执行结果（general commands only） |
| `server_command` | 服务器→设备 | — | 服务器下发通用指令（不含 reminder/relay） |
| `reminder_delivery` | 服务器→设备 | — | 待办事提醒下发 |
| `reminder_response` | 设备→服务器 | 是 | 提醒执行结果 |
| `relay_message_delivery` | 服务器→设备 | — | 传话消息下发 |
| `relay_message_response` | 设备→服务器 | 是 | 传话执行结果 |
| `notification` | 设备→服务器 | 是 | 设备通知 |
| `error` | 设备→服务器 | 否 | 错误上报 |
| `ack` | 设备→服务器 | 否 | 消息确认 |
| `ack` | 服务器→设备 | — | 自动 ACK 回执（require_ack=true 时） |
| `app_request` | 设备→服务器 | 是 | 业务请求（21 种子类型） |

---

## 6. 指令生命周期

### 通用指令下发（send_command_to_aipet）

```
入口层（Controller）                        服务层（WebSocket Service）               MySQL
  |                                          |                                      |
  |-- send_command_to_aipet() -------------->|                                      |
  |   (query_db, user_id, dept_id)           |                                      |
  |                                          |-- _write_command_log() ------------->| INSERT
  |                                          |   (command_params 完整写入)            | status=sent
  |                                          |   ✅ 无论设备在线/离线，都会写入        | 或 status=failed
  |                                          |                                      |
  |                                          |-- 检查设备在线状态                      |
  |                                          |   ├─ 离线 → 返回失败                   |
  |                                          |   └─ 在线 → 继续下发                   |
  |                                          |                                      |
  |                                          |-- Redis Publish / WebSocket send ---->| 推送到设备
```

> **注意：** `send_command_to_aipet()` 不再处理 `reminder` 和 `relay` 类型（已从 `AiPetCommandMessageType` 枚举中移除）。

### 提醒下发（send_reminder_to_aipet）

```
Controller.add_reminder()               WebSocket Service                   MySQL
  |                                          |                                |
  |-- INSERT ai_pet_reminders ------------->|                                | status=pending
  |                                          |                                |
  |-- send_reminder_to_aipet() ------------>|                                |
  |   (reminder_params)                      |                                |
  |                                          |-- 检查设备在线状态                |
  |                                          |-- Redis Publish / WS send ----->| 推送到设备
  |                                          |   type="reminder_delivery"     |
  |                                          |   ❌ 不写 ai_pet_command_logs   |
  |                                          |                                |
  |-- UPDATE ai_pet_reminders ------------->|                                | delivery_id + delivery_params
  |                                          |                                | status=sent + sent_time
```

### 传话下发（send_relay_message_to_aipet）

```
Controller.add_relay_message()          WebSocket Service                   MySQL
  |                                          |                                |
  |-- INSERT ai_pet_relay_messages ------->|                                | status=pending
  |                                          |                                |
  |-- send_relay_message_to_aipet() ------->|                                |
  |   (relay_params)                         |                                |
  |                                          |-- 检查设备在线状态                |
  |                                          |-- Redis Publish / WS send ----->| 推送到设备
  |                                          |   type="relay_message_delivery"|
  |                                          |   ❌ 不写 ai_pet_command_logs   |
  |                                          |                                |
  |-- UPDATE ai_pet_relay_messages -------->|                                | delivery_id + delivery_params
  |                                          |                                | status=sent + sent_time
```

### 设备执行 + 结果回报

```
Device                                    Server                                   MySQL
  |                                          |                                      |
  |  设备收到消息                              |                                      |
  |  ┌─ server_command → command_response   |                                      |
  |  ├─ reminder_delivery → reminder_response|                                     |
  |  └─ relay_message_delivery → relay_message_response|                           |
  |                                          |                                      |
  |--- reminder_response ------------------>|                                      |
  |     {reminder_id, status:"completed"}    |                                      |
  |                                          |-- AiPetRemindersDao                 |
  |                                          |   .update_by_delivery_id() -------->| UPDATE ai_pet_reminders
  |                                          |                                      | status + result + executed_time
  |                                          |   ❌ 不写 ai_pet_command_logs        |
  |                                          |                                      |
  |--- relay_message_response ------------->|                                      |
  |     {relay_id, status:"completed"}      |                                      |
  |                                          |-- AiPetRelayMessagesDao              |
  |                                          |   .update_by_delivery_id() -------->| UPDATE ai_pet_relay_messages
  |                                          |                                      | status + result + executed_time
  |                                          |   ❌ 不写 ai_pet_command_logs        |
  |                                          |                                      |
  |--- command_response ------------------->|                                      |
  |     {command_id, command, status, ...}   |                                      |
  |                                          |-- _record_command_result()           |
  |                                          |   ├─ Redis LPUSH history             |
  |                                          |   └─ UPDATE ai_pet_command_logs      |
```

### 写入时机总结

| 阶段 | 谁触发 | 写入表 | 写入内容 |
|------|--------|--------|---------|
| 通用指令下发 | `send_command_to_aipet()` | `ai_pet_command_logs` | **INSERT** — command_type, command_params (完整 JSON), status=sent/failed |
| 通用指令执行回报 | `command_response` handler | `ai_pet_command_logs` | **UPDATE** — status, result, error_message, executed_time |
| 提醒下发 | `send_reminder_to_aipet()` | `ai_pet_reminders` | **UPDATE** — delivery_id, delivery_params, status=sent, sent_time（Controller 层执行） |
| 提醒执行回报 | `reminder_response` handler | `ai_pet_reminders` | **UPDATE** — status, result, error_message, executed_time |
| 传话下发 | `send_relay_message_to_aipet()` | `ai_pet_relay_messages` | **UPDATE** — delivery_id, delivery_params, status=sent, sent_time（Controller 层执行） |
| 传话执行回报 | `relay_message_response` handler | `ai_pet_relay_messages` | **UPDATE** — status, result, error_message, executed_time |

> **关键差异：** 提醒和传话走独立下发通道（`reminder_delivery` / `relay_message_delivery`），全程**不写入** `ai_pet_command_logs`。只有通用指令（print、wake_up、set_volume 等）才经过 `send_command_to_aipet()` → `ai_pet_command_logs` → `command_response` 路径。

### 超时说明

命令下发后，如果设备在 `timeout` 秒内未返回结果：
- Redis `aipet_command_pending:{cmd_id}` 在 10 分钟后自动过期
- 失败命令记录到 `aipet_command_failed:{cmd_id}`，TTL 48 小时
- MySQL `ai_pet_command_logs` 中的 `status` 保持为 `sent`（后续可通过定时任务标记为 timeout）

---

## 附录 A：完整 command 类型枚举（AiPetCommandMessageType）

| 值 | 枚举名 | 说明 |
|---|------|------|
| print | PRINT | 打印 |
| upload_status | UPLOAD_STATUS | 获取宠物状态 |
| update_config | UPDATE_CONFIG | 获取配置信息 |
| wake_up | WAKE_UP | 唤醒 |
| sleep | SLEEP | 休眠 |
| play_sound | PLAY_SOUND | 播放声音 |
| set_mood | SET_MOOD | 设置心情 |
| restart | RESTART | 重启设备 |
| set_volume | SET_VOLUME | 设置音量 |
| set_brightness | SET_BRIGHTNESS | 设置亮度 |
| take_photo | TAKE_PHOTO | 拍照 |
| start_recording | START_RECORDING | 开始录音 |
| stop_recording | STOP_RECORDING | 停止录音 |
| update_firmware | UPDATE_FIRMWARE | 固件更新 |
| factory_reset | FACTORY_RESET | 恢复出厂设置 |
| enter_maintenance | ENTER_MAINTENANCE | 进入维护模式 |
| exit_maintenance | EXIT_MAINTENANCE | 退出维护模式 |

> **已移除：** `reminder`（待办事提醒）和 `relay`（传话）已从 `AiPetCommandMessageType` 枚举中移除。提醒和传话现走独立的 `reminder_delivery` / `relay_message_delivery` 下发通道，设备端应使用 `reminder_response` / `relay_message_response` 回报执行结果。

---

## 附录 B：核心文件索引

| 文件 | 说明 |
|------|------|
| `module_aipet/websocket/aipet_websocket.py` | WebSocket 端点实现 |
| `module_aipet/websocket/message_manager.py` | 消息管理器（Handler 注册，含 reminder/relay 新 handler） |
| `module_aipet/websocket/message_handler.py` | Handler 工厂/调度 |
| `module_aipet/websocket/handlers/base_handler.py` | 处理器基类 |
| `module_aipet/websocket/handlers/auth_handler.py` | 认证处理 |
| `module_aipet/websocket/handlers/heartbeat_handler.py` | 心跳处理 |
| `module_aipet/websocket/handlers/config_handler.py` | 配置请求处理 |
| `module_aipet/websocket/handlers/status_handler.py` | 状态上报处理 |
| `module_aipet/websocket/handlers/chat_handler.py` | 聊天处理 |
| `module_aipet/websocket/handlers/command_handler.py` | 指令响应处理（仅 general commands，不再写 reminders/relay） |
| `module_aipet/websocket/handlers/reminder_response_handler.py` | **新增** — 提醒执行结果处理（只写 ai_pet_reminders，不写 command_logs） |
| `module_aipet/websocket/handlers/relay_message_response_handler.py` | **新增** — 传话执行结果处理（只写 ai_pet_relay_messages，不写 command_logs） |
| `module_aipet/websocket/handlers/notification_handler.py` | 通知处理 |
| `module_aipet/websocket/handlers/error_handler.py` | 错误处理 |
| `module_aipet/websocket/handlers/ack_handler.py` | ACK 处理 |
| `module_aipet/websocket/handlers/app_request_handler.py` | 业务请求处理（21 子类型，含 get_reminders / get_relay_messages） |
| `module_aipet/service/ai_pet_websocket_service.py` | 服务器→设备消息发送（含 `send_command_to_aipet`、`send_reminder_to_aipet`、`send_relay_message_to_aipet`） |
| `module_aipet/dao/ai_pet_command_logs_dao.py` | 指令日志 DAO |
| `module_aipet/dao/ai_pet_reminders_dao.py` | 提醒 DAO（含 `update_by_delivery_id`，原 `update_by_command_id`） |
| `module_aipet/dao/ai_pet_relay_messages_dao.py` | 传话 DAO（含 `update_by_delivery_id`，原 `update_by_command_id`） |
| `module_aipet/config/enums.py` | 所有枚举定义（AiPetCommandMessageType 已移除 REMINDER/RELAY；AiPetWebSocketMessageType 新增 4 个类型） |
