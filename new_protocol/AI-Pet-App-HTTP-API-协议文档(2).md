# AI Pet App HTTP API 接口协议文档

## 基础信息

| 项目 | 值 |
|------|-----|
| 服务地址 | `http://47.118.26.156:8000` |
| 全局前缀 | `/api/v1` |
| 认证方式 | Bearer Token（Header: `Authorization: Bearer {token}`） |
| 数据格式 | JSON，字段名 camelCase |
| 响应格式 | `{ code: 200, msg: "...", success: true, time: "...", data: {...} }` |

---

## 目录

1. [微信登录](#1-微信登录)
2. [AI 宠物核心](#2-ai-宠物核心)
3. [聊天](#3-聊天)
4. [指令下发](#4-指令下发)
5. [配置管理](#5-配置管理)
6. [家庭成员](#6-家庭成员)
7. [好友系统](#7-好友系统)
8. [任务系统](#8-任务系统)
9. [道具系统](#9-道具系统)
10. [虚拟货币](#10-虚拟货币)
11. [等级特权](#11-等级特权)
12. [商店](#12-商店)
13. [收货地址](#13-收货地址)
14. [发货物流](#14-发货物流)
15. [宝箱系统](#15-宝箱系统)
16. [自定义奖励](#16-自定义奖励)
17. [朋友圈动态](#17-朋友圈动态)
18. [农场系统](#18-农场系统)
19. [行为日志](#19-行为日志)
20. [文件上传](#20-文件上传)
21. [WebSocket HTTP 接口](#21-websocket-http-接口)
22. [待办事提醒 App HTTP](#22-待办事提醒-app-http)
23. [传话消息 App HTTP](#23-传话消息-app-http)

---

## 1. 微信登录

**Router 前缀:** `/api/v1/wechat`

### 1.1 微信注册/登录

```
POST /api/v1/wechat/auth/register
```

**Request Body:** `WxMiniPhoneNumberCode`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| loginCode | string | 否 | 微信小程序登录 code |
| phoneNumCode | string | 否 | 微信小程序手机号 code |

**Response data:**
```json
{
  "token": "...",
  "expiresIn": "...",
  "user": { ... },
  "wxUser": { ... }
}
```

### 1.2 微信登录

```
POST /api/v1/wechat/auth/login
```

**Request Body:** `WxMiniLoginCode`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| loginCode | string | 否 | 微信小程序登录 code |

**Response data:** 同上 `AppLoginModelResp`

### 1.3 获取微信用户信息

```
GET /api/v1/wechat/user/info
```

**认证:** 需要 Bearer Token

**Response data:** `UserWechatModel`（nickName, avatar, phoneNumber 等）

---

## 2. AI 宠物核心

**Router 前缀:** `/api/v1/aipet/app`
**认证:** 所有接口需要 Bearer Token（除 `/auth` 外）

### 2.1 手机号短信登录

```
GET /api/v1/aipet/app/auth/{phone_number}/{sms_code}
```

**认证:** 不需要  
**说明:** sms_code 硬编码校验为 `888888`

**Response data:** token 字符串

### 2.2 绑定宠物

```
GET /api/v1/aipet/app/bind/{serial_number}
```

**Response data:** AI Pet 信息对象

### 2.3 解绑宠物

```
GET /api/v1/aipet/app/unbind/{serial_number}
```

**Response data:** AI Pet 信息对象

### 2.4 我的宠物列表

```
GET /api/v1/aipet/app/myaipets
```

**Response data:** AI Pet 信息对象列表

### 2.5 我的用户信息

```
GET /api/v1/aipet/app/myinfo
```

**Response data:** `AiPetUserInfoModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 用户 ID |
| phoneNumber | string? | 手机号 |
| registerDate | datetime? | 注册日期 |

### 2.6 获取宠物状态

```
GET /api/v1/aipet/app/status/{aipet_id}
```

**说明:** 获取 AI 宠物的在线状态和当前设备状态数据（电池、心情等）

### 2.7 获取宠物属性

```
GET /api/v1/aipet/app/attributes/{aipet_id}
```

**说明:** 获取宠物等级、经验、健康、饥饿、心情等属性

---

## 3. 聊天

### 3.1 与 AI 宠物聊天 (核心接口)

```
POST /api/v1/aipet/app/chatWith/{aipet_id}
```

**Request Body:** `AiPetChatModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| sessionId | string? | 会话 ID |
| messageType | string? | 消息类型: text / voice / image / command / emotion / file |
| content | string? | 消息内容 |
| senderType | int? | 发送者类型（1=用户, 2=AI宠物） |
| mediaUrl | string? | 媒体文件 URL |
| mediaDuration | int? | 媒体时长（秒） |
| mediaSize | int? | 媒体文件大小（字节） |
| commandType | string? | 指令类型（messageType=command 时必填） |
| commandParams | dict? | 指令参数 JSON（messageType=command 时必填） |
| emotionType | string? | 表情类型: happy / sad / angry 等 |
| replyToMessageId | int? | 回复的目标消息 ID |
| extraData | dict? | 扩展数据 JSON |

**message_type 枚举：**
| 值 | 说明 |
|---|------|
| text | 文字消息 |
| voice | 语音消息 |
| image | 图片消息 |
| command | 指令消息 |
| emotion | 表情消息 |
| file | 文件消息 |

**command_type 枚举（message_type=command 时）：**
| 值 | 说明 | command_params |
|---|------|------|
| print | 打印 | content 需为 http(s) URL |

> **注意：** `reminder`（待办事提醒）和 `relay`（传话）已脱离 command 体系，改为独立的业务通道。提醒请使用 [§22 待办事提醒](#22-待办事提醒-app-http)，传话请使用 [§23 传话消息](#23-传话消息-app-http)。在 ChatWith 中传入 `command_type=reminder` 或 `command_type=relay` 将返回"指令类型不正确"。

**Response data:** 发送结果（id, content, send_time 等）

### 3.2 查询聊天记录

```
GET /api/v1/aipet/app/chatlogs/{aipet_id}/{page_num}/{page_size}
```

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| command_type | string? | 否 | 按指令类型筛选 |
| message_type | string? | 否 | 按消息类型筛选 |

**Response data:** 分页数据 `{ rows: [...], total, pageNum, pageSize, hasNext }`

---

## 4. 指令下发

**Router 前缀:** `/api/v1/aipet/app/command`
**认证:** 需要 Bearer Token

**通用请求体 `CommandParamsModel`：**
| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| commandParams | dict | {} | 指令参数 |
| priority | string | "normal" | low / normal / high / urgent |
| requireAck | bool | false | 是否需要设备 ACK |
| timeout | int | 30 | 超时秒数 |

**支持的 command_type 枚举：**

| 值 | 说明 |
|---|------|
| print | 打印 |
| upload_status | 获取宠物状态 |
| update_config | 获取配置信息 |
| wake_up | 唤醒 |
| sleep | 休眠 |
| play_sound | 播放声音 |
| set_mood | 设置心情 |
| restart | 重启设备 |
| set_volume | 设置音量 |
| set_brightness | 设置亮度 |
| take_photo | 拍照 |
| start_recording | 开始录音 |
| stop_recording | 停止录音 |
| update_firmware | 固件更新 |
| factory_reset | 恢复出厂设置 |
| enter_maintenance | 进入维护模式 |
| exit_maintenance | 退出维护模式 |

> **注意：** `reminder`（待办事提醒）和 `relay`（传话）已从 command 体系中移除，不再通过 `POST /app/command/{aipet_id}/{command_type}` 下发。提醒使用 `POST /app/reminders/{aipet_id}`，传话使用 `POST /app/relayMessages/{aipet_id}`，二者均为创建即自动下发，详见 [§22](#22-待办事提醒-app-http) 和 [§23](#23-传话消息-app-http)。

### 4.1 通用指令下发

```
POST /api/v1/aipet/app/command/{aipet_id}/{command_type}
```

**说明:** 发送任意类型指令到设备。检查所有权和在线状态，通过 WebSocket/Redis 下发。

### 4.2 批量指令下发

```
POST /api/v1/aipet/app/command/batch
```

**Request Body:**
| 字段 | 类型 | 说明 |
|------|------|------|
| aipetIds | list[string] | 设备 ID 列表 |
| commandType | string | 指令类型 |
| params | CommandParamsModel | 指令参数 |

**Response data:**
```json
{
  "totalCount": 3,
  "successCount": 2,
  "commandType": "wake_up",
  "results": [
    { "aipetId": "1", "success": true, "message": "成功", "commandId": "cmd_..." },
    { "aipetId": "2", "success": false, "message": "设备不在线" }
  ]
}
```

### 4.3 待处理指令

```
GET /api/v1/aipet/app/command/pending/{aipet_id}
```

**Response data:** `{ aipetId: "...", pendingCommands: [...] }`

### 4.4 指令历史

```
GET /api/v1/aipet/app/command/history/{aipet_id}?limit=50
```

**Response data:** `{ aipetId: "...", history: [...] }`

---

## 5. 配置管理

### 5.1 获取设备配置

```
GET /api/v1/aipet/app/config/{aipet_id}
```

**Response data:** `AiPetConfigModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| petId | string? | 宠物 ID |
| petNickname | string? | 宠物昵称 |
| personality | string? | 性格 |
| hobby | string? | 爱好 |
| language | string? | 语言：zh-CN / zh-TW / en-US / ja-JP / ko-KR |
| interactionMode | string? | 交互模式 |
| eyeStyle | string? | 眼睛样式 |
| voiceStyle | string? | 声音风格 |
| themeColor | string? | 主题颜色 |
| timeZone | string? | 时区 |
| avatarUrl | string? | 头像 URL |
| backgroundUrl | string? | 背景图片 URL |
| configJson | string? | 扩展配置 JSON |
| isActive | int? | 启用状态（0=禁用, 1=启用） |

### 5.2 编辑设备配置

```
GET /api/v1/aipet/app/config/edit/{aipet_id}
```

**Request Body:** `AiPetConfigModel`（同上）

### 5.3 获取我的配置

```
GET /api/v1/aipet/app/myconfig
```

**Response data:** `AiPetUserConfigModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| userId | int? | 用户 ID |
| nickname | string? | 昵称 |
| avatarUrl | string? | 头像 URL |
| backgroundUrl | string? | 背景 URL |
| gender | int? | 性别（0=未知, 1=男, 2=女） |
| age | int? | 年龄 |
| birthday | date? | 生日 |
| constellation | string? | 星座 |
| zodiac | string? | 生肖 |
| familyRole | string? | 家庭角色 |
| personalities | string? | 性格 |
| interests | string? | 兴趣 |
| language | string? | 语言 |
| interactionMode | string? | 交互模式 |
| voicePreference | string? | 声音偏好 |
| themeColor | string? | 主题颜色 |
| timeZone | string? | 时区 |
| configJson | string? | 扩展配置 JSON |

### 5.4 编辑我的配置

```
GET /api/v1/aipet/app/myconfig/edit
```

**Request Body:** `AiPetUserConfigModel`（同上）

---

## 6. 家庭成员

### 6.1 成员列表

```
GET /api/v1/aipet/app/familymembers/list
```

**Response data:** `AiPetFamilyMembersModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| userId | int? | 用户 ID |
| petId | int? | 宠物 ID |
| memberName | string? | 成员名称 |
| relationship | string? | 关系（owner / father / mother 等） |
| gender | int? | 性别（0=未知, 1=男, 2=女） |
| age | int? | 年龄 |
| avatarUrl | string? | 头像 URL |
| description | string? | 描述 |
| isActive | int? | 启用（1=是, 0=否） |

### 6.2 新增成员

```
POST /api/v1/aipet/app/familymembers/new
```

**Request Body:** `AiPetFamilyMembersModel`（同上，必填字段：petId, memberName, relationship）

### 6.3 编辑成员

```
POST /api/v1/aipet/app/familymembers/edit
```

**Request Body:** `AiPetFamilyMembersModel`（必须包含 id）

---

## 7. 好友系统

### 7.1 好友列表

```
GET /api/v1/aipet/app/friends/list/{aipet_id}
```

### 7.2 添加好友

```
POST /api/v1/aipet/app/friends/new
```

**Request Body:** `AiPetFriendsModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| petId | int? | 宠物 ID |
| friendPetId | int? | 好友宠物 ID |
| status | int? | 状态（1=正常, 2=已删除, 3=已屏蔽） |

### 7.3 删除好友

```
POST /api/v1/aipet/app/friends/delete
```

**Request Body:** `AiPetFriendsModel`（标识要删除的好友）

### 7.4 好友对话列表

```
GET /api/v1/aipet/app/friends/dialogs/{aipet_id}/{page_num}/{page_size}
```

**说明:** 获取每个好友宠物最新一条消息的摘要列表

### 7.5 好友聊天记录

```
GET /api/v1/aipet/app/friends/messages/{aipet_id}/{friend_pet_id}/{page_num}/{page_size}
```

### 7.6 发送好友消息

```
POST /api/v1/aipet/app/friends/messages/send
```

**Request Body:** `AiPetFriendMessagesModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| petId | int? | 发送方宠物 ID |
| friendPetId | int? | 接收方宠物 ID |
| senderUserId | int? | 发送方用户 ID |
| receiverUserId | int? | 接收方用户 ID |
| messageType | int? | 消息类型（1=text, 2=image, 3=video, 4=voice） |
| content | string? | 消息内容 |
| mediaUrl | string? | 媒体 URL |
| mediaThumbnail | string? | 媒体缩略图 URL |
| isRead | int? | 已读（0=未读, 1=已读） |

---

## 8. 任务系统

### 8.1 所有任务配置

```
GET /api/v1/aipet/app/tasks/all
```

**Response data:** `AiPetTaskConfigsModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| taskCode | string? | 任务编码（唯一） |
| taskName | string? | 任务名称 |
| taskDescription | string? | 描述 |
| taskType | string? | 类型：daily / weekly / achievement / event |
| targetCount | int? | 目标完成次数 |
| rewardType | string? | 奖励类型：gold / diamond / exp / item |
| rewardAmount | int? | 奖励数量 |
| rewardItemId | int? | 奖励道具 ID |
| sortOrder | int? | 排序 |
| isActive | int? | 启用 |
| startTime | datetime? | 开始时间 |
| endTime | datetime? | 结束时间 |

### 8.2 我的任务记录

```
GET /api/v1/aipet/app/tasks/myrecords
```

**Response data:** `AiPetTaskCompletionRecordsModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| userId | int? | 用户 ID |
| taskId | int? | 任务 ID |
| taskCode | string? | 任务编码 |
| currentCount | int? | 当前完成次数 |
| targetCount | int? | 目标次数 |
| isCompleted | int? | 已完成（0=否, 1=是） |
| completedTime | datetime? | 完成时间 |
| isRewarded | int? | 已领取奖励（0=否, 1=是） |
| rewardedTime | datetime? | 领取时间 |
| cycleDate | date? | 周期日期（每日/每周任务） |

### 8.3 完成任务

```
GET /api/v1/aipet/app/tasks/complete/{aipet_id}/{task_id}
```

### 8.4 领取任务奖励

```
GET /api/v1/aipet/app/tasks/reward/{aipet_id}/{task_id}
```

---

## 9. 道具系统

### 9.1 获取道具详情

```
GET /api/v1/aipet/app/items/{item_ids}
```

**说明:** item_ids 为逗号分隔的道具 ID 列表

### 9.2 使用道具

```
GET /api/v1/aipet/app/items/use/{user_item_id}/{aipet_id}
```

### 9.3 我的道具列表

```
GET /api/v1/aipet/app/myitems
```

---

## 10. 虚拟货币

### 10.1 我的货币

```
GET /api/v1/aipet/app/mycurrency
```

**Response data:** `AiPetUserVirtualCurrencyModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| userId | int? | 用户 ID |
| currencyType | string? | 货币类型：gold / diamond / coin |
| balance | int? | 当前余额 |
| totalEarned | int? | 累计获得 |
| totalConsumed | int? | 累计消费 |
| lastEarnTime | datetime? | 最后获得时间 |
| lastConsumeTime | datetime? | 最后消费时间 |

---

## 11. 等级特权

### 11.1 所有等级特权

```
GET /api/v1/aipet/app/levelprivileges/all
```

**Response data:** `AiPetLevelPrivilegesModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| level | int? | 等级 |
| privilegeCode | string? | 特权编码（唯一） |
| privilegeName | string? | 特权名称 |
| privilegeDescription | string? | 描述 |
| privilegeType | string? | 类型：function / limit / bonus |
| privilegeValue | string? | 值 |
| sortOrder | int? | 排序 |
| isActive | int? | 启用 |

### 11.2 我的特权

```
GET /api/v1/aipet/app/myprivileges/{aipet_id}
```

**说明:** 根据宠物等级获取对应的特权编码列表

---

## 12. 商店

### 12.1 商品列表

```
GET /api/v1/aipet/app/shop/goods/list/{page_num}/{page_size}
```

**Response data:** `AiPetGoodsShopModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| goodsId | int? | 商品 ID |
| goodsType | string? | 类型：physical / virtual_item / redeem_code |
| description | string? | 描述 |
| shopPrice | int? | 售价 |
| originalPrice | int? | 原价 |
| virtualCurrencyPrice | int? | 虚拟货币价格 |
| virtualCurrencyType | string? | 货币类型：gold / diamond / coin |
| onlinePaymentPrice | float? | 在线支付价格 |
| paymentMethods | string? | 支付方式（逗号分隔） |
| stockQuantity | int? | 库存（-1=无限） |
| maxPurchasePerUser | int? | 每用户限购（0=不限） |
| sortOrder | int? | 排序 |
| isActive | int? | 启用 |
| saleStartTime | datetime? | 销售开始时间 |
| saleEndTime | datetime? | 销售结束时间 |
| extraInfo | dict? | 扩展信息 |

### 12.2 购买商品

```
GET /api/v1/aipet/app/shop/buy/{goodsId}
```

### 12.3 购买记录

```
GET /api/v1/aipet/app/shop/buy/record/{page_num}/{page_size}
```

---

## 13. 收货地址

### 13.1 地址列表

```
GET /api/v1/aipet/app/address/list
```

### 13.2 获取默认地址

```
GET /api/v1/aipet/app/address/default
```

### 13.3 新增地址

```
POST /api/v1/aipet/app/address/add
```

**Request Body:** `AiPetUserAddressModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| consigneeName | string? | 收货人姓名 |
| consigneePhone | string? | 收货人电话 |
| province | string? | 省 |
| city | string? | 市 |
| district | string? | 区 |
| detailAddress | string? | 详细地址 |
| postalCode | string? | 邮编 |
| isDefault | int? | 是否默认（0=否, 1=是） |
| remark | string? | 备注 |

### 13.4 修改地址

```
PUT /api/v1/aipet/app/address/update/{address_id}
```

### 13.5 删除地址

```
DELETE /api/v1/aipet/app/address/delete/{address_id}
```

### 13.6 设为默认地址

```
POST /api/v1/aipet/app/address/setDefault/{address_id}
```

---

## 14. 发货物流

### 14.1 物流详情

```
GET /api/v1/aipet/app/shipping/detail/{shipping_id}
```

**Response data:** `AiPetGoodsShopShippingModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| purchaseId | int? | 购买记录 ID |
| paymentOrderId | int? | 支付订单 ID |
| shippingStatus | int? | 状态（0=待发货, 1=已发货, 2=已收货, 3=已取消） |
| logisticsCompany | string? | 物流公司 |
| logisticsNo | string? | 物流单号 |
| shippingTime | datetime? | 发货时间 |

### 14.2 确认收货

```
POST /api/v1/aipet/app/shipping/confirm/{shipping_id}
```

---

## 15. 宝箱系统

### 15.1 宝箱配置列表

```
GET /api/v1/aipet/app/treasurechest/list
```

### 15.2 我的宝箱

```
GET /api/v1/aipet/app/treasurechest/my
```

### 15.3 宝箱奖励内容

```
GET /api/v1/aipet/app/treasurechest/rewards/{chest_id}
```

### 15.4 添加宝箱到库存

```
POST /api/v1/aipet/app/treasurechest/add/{chest_id}?quantity=1
```

### 15.5 合成宝箱

```
POST /api/v1/aipet/app/treasurechest/compose/{chest_id}
```

### 15.6 按道具合成宝箱

```
POST /api/v1/aipet/app/treasurechest/composeByItems
```

### 15.7 开启宝箱

```
POST /api/v1/aipet/app/treasurechest/open/{aipet_id}/{chest_id}
```

---

## 16. 自定义奖励

### 16.1 奖励列表

```
GET /api/v1/aipet/app/rewardsCustom/list/{page_num}/{page_size}
```

**Response data:** `AiPetRewardsCustomModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| petId | int? | 宠物 ID |
| userId | int? | 用户 ID |
| rewardsType | string? | 类型：park / snacks / trip / toys / film / digital |
| description | string? | 描述 |
| virtualCurrencyPrice | int? | 虚拟货币价格 |
| virtualCurrencyType | string? | 货币类型：gold / diamond / coin |
| stockQuantity | int? | 库存（-1=无限） |
| sortOrder | int? | 排序 |
| isActive | int? | 启用 |
| extraInfo | dict? | 扩展信息 |

### 16.2 新增奖励

```
POST /api/v1/aipet/app/rewardsCustom/add
```

**Request Body:** `AiPetRewardsCustomModel`（rewardsType 必填，枚举：park, snacks, trip, toys, film, digital）

### 16.3 修改奖励

```
POST /api/v1/aipet/app/rewardsCustom/update
```

### 16.4 删除奖励

```
DELETE /api/v1/aipet/app/rewardsCustom/delete/{rewardsCustomIds}
```

**说明:** rewardsCustomIds 为逗号分隔的 ID 列表

### 16.5 兑换奖励

```
GET /api/v1/aipet/app/rewardsCustom/exchange/{rewardsCustomId}
```

**说明:** 兑换自定义奖励，扣除虚拟货币

---

## 17. 朋友圈动态

### 17.1 我的动态（简要）

```
GET /api/v1/aipet/app/moments/{aipet_id}
```

### 17.2 动态列表（分页）

```
GET /api/v1/aipet/app/moments/{aipet_id}/{page_num}/{page_size}
```

**Response data:** `AiPetMomentsModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| petId | int? | 发布者宠物 ID |
| userId | int? | 发布者用户 ID |
| content | string? | 文字内容 |
| mediaType | int? | 媒体类型（1=text, 2=image, 3=video） |
| mediaUrls | string? | 媒体 URL（JSON 列表） |
| location | string? | 位置 |
| privacySetting | int? | 隐私（1=公开, 2=好友可见, 3=仅自己） |
| likeCount | int? | 点赞数 |
| commentCount | int? | 评论数 |
| viewCount | int? | 浏览数 |
| isLiked | bool? | 当前用户是否已点赞 |

### 17.3 动态详情

```
GET /api/v1/aipet/app/moments/{aipet_id}/{moment_id}
```

### 17.4 发布动态

```
POST /api/v1/aipet/app/moments/{aipet_id}
```

**Request Body:** `AiPetMomentsModel`

### 17.5 编辑动态

```
PUT /api/v1/aipet/app/moments/{aipet_id}/{moment_id}
```

### 17.6 删除动态

```
DELETE /api/v1/aipet/app/moments/{aipet_id}/{moment_id}
```

### 17.7 点赞

```
GET /api/v1/aipet/app/momentslike/do/{moment_id}
```

### 17.8 取消点赞

```
GET /api/v1/aipet/app/momentslike/undo/{moment_id}
```

### 17.9 评论列表

```
GET /api/v1/aipet/app/comments/{moment_id}/{page_num}/{page_size}
```

**Response data:** `AiPetMomentCommentsModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 评论 ID |
| momentId | int? | 动态 ID |
| content | string? | 评论内容 |
| petId | int? | 评论者宠物 ID |
| userId | int? | 评论者用户 ID |
| parentId | int? | 父评论 ID（回复时使用） |
| replyPetId | int? | 被回复的宠物 ID |
| replyUserId | int? | 被回复的用户 ID |

### 17.10 发表评论

```
POST /api/v1/aipet/app/comments/{moment_id}
```

**Request Body:** `AiPetMomentCommentsModel`

### 17.11 删除评论

```
DELETE /api/v1/aipet/app/comments/{moment_id}/{comment_id}
```

---

## 18. 农场系统

### 18.1 我的农场

```
GET /api/v1/aipet/app/myfarm
```

### 18.2 好友农场

```
GET /api/v1/aipet/app/friendsfarm/{friend_aipet_id}
```

### 18.3 喂食

```
POST /api/v1/aipet/app/myfarm/feed
```

**Request Body:** `AiPetFarmFeedModel`
| 字段 | 类型 | 说明 |
|------|------|------|
| farmId | int? | 农场 ID |
| itemId | int? | 食物道具 ID |
| itemName | string? | 食物名称 |
| totalEffectValue | int? | 总效果值 |
| remainingEffectValue | int? | 剩余效果值 |
| consumeSpeed | int? | 每分钟消耗速度 |
| status | string? | 状态：FULL / CONSUMING / EMPTY |
| startTime | datetime? | 开始时间 |
| endTime | datetime? | 预计结束时间 |

### 18.4 互动记录

```
GET /api/v1/aipet/app/myfarm/interaction/{page_num}/{page_size}
```

**Response data:** `AiPetFarmInteractionModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| interactionType | string? | 类型：EMPLOYMENT / THEFT |
| petId | int? | 参与宠物 ID |
| targetFarmId | int? | 目标农场 ID |
| status | string? | 状态：ACTIVE / ENDED / LEAVING |
| foodConsumed | int? | 消耗的食物 |
| productionContribution | int? | 产出贡献 |

### 18.5 产出列表

```
GET /api/v1/aipet/app/myfarm/production/{page_num}/{page_size}
```

**Response data:** `AiPetFarmProductionModel[]`
| 字段 | 类型 | 说明 |
|------|------|------|
| productionType | string? | 类型：treasure_box |
| productionStatus | string? | 状态：PRODUCED / CLAIMED / OPENED |
| rewardDetails | dict? | 奖励详情 |
| produceTime | datetime? | 产出时间 |
| claimTime | datetime? | 领取时间 |
| openTime | datetime? | 开启时间 |

### 18.6 领取产出

```
GET /api/v1/aipet/app/myfarm/production/{production_id}/reward
```

### 18.7 雇佣好友宠物

```
POST /api/v1/aipet/app/myfarm/employ/{friend_aipet_id}
```

### 18.8 解雇好友宠物

```
POST /api/v1/aipet/app/myfarm/dismiss/{friend_aipet_id}
```

### 18.9 召回宠物

```
POST /api/v1/aipet/app/myfarm/recall/{aipet_id}
```

---

## 19. 行为日志

```
GET /api/v1/aipet/app/behaviorlogs/{aipet_id}/{page_num}/{page_size}
```

**说明:** 按时间倒序排列

---

## 20. 文件上传

```
POST /api/v1/aipet/app/upload
```

**Content-Type:** multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 上传的文件 |

**Response data:**
```json
{
  "url": "https://oss.example.com/uploads/xxx.png"
}
```

---

## 21. WebSocket HTTP 接口

**Router 前缀:** `/api/v1/aipet/ws`

### 21.1 获取设备连接令牌

```
GET /api/v1/aipet/ws/auth/{serial_number}
```

**认证:** 不需要用户 Token

**Response data:** 设备 WebSocket 连接令牌

### 21.2 设备上传文件

```
POST /api/v1/aipet/ws/upload
```

**认证:** Header `Authorization: Bearer {device_token}`

**Content-Type:** multipart/form-data（字段: file）

### 21.3 WebSocket 健康检查

```
GET /api/v1/aipet/ws/health/status    # 健康状态总览
GET /api/v1/aipet/ws/health/metrics   # Prometheus 指标
GET /api/v1/aipet/ws/health/connections  # 连接详情
GET /api/v1/aipet/ws/health/rate-limits/{aipet_id}  # 查看限流状态
POST /api/v1/aipet/ws/health/rate-limits/{aipet_id}/reset  # 重置限流
GET /api/v1/aipet/ws/health/reliability/stats  # 消息可靠性统计
GET /api/v1/aipet/ws/health/ready     # K8s Readiness Probe
GET /api/v1/aipet/ws/health/live      # K8s Liveness Probe
```

---

## 22. 待办事提醒 App HTTP

**Router 前缀:** `/api/v1/aipet/app/reminders`
**认证:** 所有接口需要 Bearer Token

### 22.1 提醒列表

```
GET /api/v1/aipet/app/reminders/list/{aipet_id}/{page_num}/{page_size}
```

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string? | 否 | 按状态筛选：pending / sent / executing / completed / failed / cancelled |

**Response data:** 分页数据 `{ rows: [...], total, pageNum, pageSize, hasNext }`

**rows 字段说明（AiPetRemindersModel）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| petId | int? | 设备 ID |
| userId | int? | 创建者用户 ID |
| title | string? | 提醒标题 |
| content | string? | 提醒内容 |
| reminderTime | datetime? | 提醒触发时间 |
| repeatType | string? | 重复类型：none / daily / weekly / monthly |
| status | string? | 状态：pending / sent / executing / completed / failed / cancelled |
| deliveryId | string? | 下发追踪 ID（格式 `rmd_{aipet_id}_{timestamp}_{hash}`） |
| deliveryParams | dict? | 下发给设备的完整参数 |
| result | dict? | 设备返回的执行结果 |
| errorMessage | string? | 错误信息 |
| sentTime | datetime? | 下发时间 |
| executedTime | datetime? | 设备执行完成时间 |

### 22.2 提醒详情

```
GET /api/v1/aipet/app/reminders/{reminder_id}
```

**Response data:** `AiPetRemindersModel`（同上）

### 22.3 新增提醒（创建即下发）

```
POST /api/v1/aipet/app/reminders/{aipet_id}
```

**Request Body:** `AiPetRemindersModel`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 提醒标题 |
| content | string | 否 | 提醒内容 |
| reminderTime | datetime | 是 | 提醒触发时间 |
| repeatType | string | 否 | 重复类型：none / daily / weekly / monthly，默认 none |

**说明:** `petId`、`userId`、`createBy` 由服务端自动填充。**创建后自动下发到设备**，无需再调用独立发送端点。

**自动下发流程：**
1. 校验参数 → INSERT `ai_pet_reminders`（status=`pending`）
2. 构建 `delivery_params`（含 `reminder_data` 和 `reminder_source: "app_chat"`）
3. 通过 `send_reminder_to_aipet()` 下发 WS `reminder_delivery` 消息到设备
4. UPDATE `ai_pet_reminders` SET `delivery_id`、`delivery_params`、`status=sent`、`sent_time=now()`

> **注意：** 提醒走独立下发通道（`reminder_delivery`），**不经过** `send_command_to_aipet()`，**不写入** `ai_pet_command_logs`。

**Response data (成功):**
```json
{
  "code": 200,
  "msg": "提醒已创建并下发",
  "data": {
    "id": 1,
    "deliveryId": "rmd_1_1718800000_abc123",
    "status": "sent"
  }
}
```

### 22.4 编辑提醒

```
PUT /api/v1/aipet/app/reminders/{reminder_id}
```

**Request Body:** `AiPetRemindersModel`（只需传要修改的字段）

**说明:** 校验记录存在且当前用户有权限（宠物归属校验）。

### 22.5 删除提醒

```
DELETE /api/v1/aipet/app/reminders/{reminder_ids}
```

**说明:** reminder_ids 为逗号分隔的 ID 列表，支持批量软删除。逐个校验宠物归属权限。

### 22.6 下发提醒到设备（已废弃）

> **此端点已移除。** 提醒在创建时自动下发（见 [§22.3](#223-新增提醒创建即下发)），不再需要独立发送端点。

---

## 23. 传话消息 App HTTP

**Router 前缀:** `/api/v1/aipet/app/relayMessages`
**认证:** 所有接口需要 Bearer Token

### 23.1 传话消息列表

```
GET /api/v1/aipet/app/relayMessages/list/{aipet_id}/{page_num}/{page_size}
```

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content_type | string? | 否 | 按内容类型筛选：text / voice |
| status | string? | 否 | 按状态筛选：pending / sent / executing / completed / failed |

**Response data:** 分页数据 `{ rows: [...], total, pageNum, pageSize, hasNext }`

**rows 字段说明（AiPetRelayMessagesModel）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int? | 记录 ID |
| petId | int? | 设备 ID |
| userId | int? | 发送者用户 ID |
| relayFrom | string? | 传话发起者（如 "妈妈"） |
| relayFromMemberId | int? | 关联家庭成员 ID |
| relayTo | string? | 传话目标（如 "孩子"） |
| relayToMemberId | int? | 关联家庭成员 ID |
| contentType | string? | 内容类型：text / voice |
| content | string? | 文本内容（text 类型，≤200 字符） |
| mediaUrl | string? | 音频 URL（voice 类型） |
| mediaDuration | int? | 音频时长（秒） |
| mediaSize | int? | 音频大小（字节） |
| voiceStyle | string? | 语音风格：sweet / normal |
| speed | float? | 语速（如 1.0） |
| status | string? | 状态：pending / sent / executing / completed / failed |
| deliveryId | string? | 下发追踪 ID（格式 `rly_{aipet_id}_{timestamp}_{hash}`） |
| deliveryParams | dict? | 下发给设备的完整参数 |
| result | dict? | 设备返回的执行结果 |
| errorMessage | string? | 错误信息 |
| sentTime | datetime? | 下发时间 |
| executedTime | datetime? | 设备执行完成时间 |

### 23.2 传话消息详情

```
GET /api/v1/aipet/app/relayMessages/{relay_id}
```

**Response data:** `AiPetRelayMessagesModel`（同上）

### 23.3 新增传话消息（创建即下发）

```
POST /api/v1/aipet/app/relayMessages/{aipet_id}
```

**Request Body:** `AiPetRelayMessagesModel`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| contentType | string | 是 | text / voice |
| content | string | 条件必填 | 文本内容（text 模式必填，≤200 字符） |
| mediaUrl | string | 条件必填 | 音频 URL（voice 模式必填） |
| mediaDuration | int | 否 | 音频时长（秒） |
| mediaSize | int | 否 | 音频大小（字节） |
| relayFrom | string | 是 | 传话发起者 |
| relayTo | string | 是 | 传话目标 |
| voiceStyle | string | 否 | 语音风格：sweet / normal |
| speed | float | 否 | 语速（默认 1.0） |

**说明:** `petId`、`userId`、`createBy` 由服务端自动填充。**创建后自动下发到设备**，无需再调用独立发送端点。

**自动下发流程：**
1. 校验内容格式（text 模式 ≤200 字符；voice 模式需 mediaUrl）
2. INSERT `ai_pet_relay_messages`（status=`pending`）
3. 根据 content_type 构建 `delivery_params`（text: content/voice_style/speed；voice: media_url/media_duration/media_size）
4. 通过 `send_relay_message_to_aipet()` 下发 WS `relay_message_delivery` 消息到设备
5. UPDATE `ai_pet_relay_messages` SET `delivery_id`、`delivery_params`、`status=sent`、`sent_time=now()`

> **注意：** 传话走独立下发通道（`relay_message_delivery`），**不经过** `send_command_to_aipet()`，**不写入** `ai_pet_command_logs`。

**Response data (成功):**
```json
{
  "code": 200,
  "msg": "传话已创建并下发",
  "data": {
    "id": 1,
    "deliveryId": "rly_1_1718800000_def456",
    "status": "sent"
  }
}
```

### 23.4 删除传话消息

```
DELETE /api/v1/aipet/app/relayMessages/{relay_ids}
```

**说明:** relay_ids 为逗号分隔的 ID 列表，支持批量软删除。逐个校验宠物归属权限。

### 23.5 下发传话消息到设备（已废弃）

> **此端点已移除。** 传话消息在创建时自动下发（见 [§23.3](#233-新增传话消息创建即下发)），不再需要独立发送端点。

---

## 附录：通用响应格式

### 成功
```json
{
  "code": 200,
  "msg": "success message",
  "success": true,
  "time": "2026-06-19T12:30:00",
  "data": { ... }
}
```

### 错误
```json
{
  "code": 500,
  "msg": "error message",
  "success": false,
  "time": "2026-06-19T12:30:00",
  "data": null
}
```

### 业务失败
```json
{
  "code": 601,
  "msg": "failure message",
  "success": false,
  "time": "2026-06-19T12:30:00",
  "data": null
}
```
