# 叮叮提醒 (DingDing Reminder)
```
一个基于 Web 的提醒管理工具，支持**到点自动播放语音提醒 + 板子协同工作**。支持本地 Windows 运行，通过 AI Pet 远程服务器与 RK3576 板子通信。
```
## 功能特性
```
- **📝 提醒管理** — 新增、编辑、删除提醒（完整 CRUD）
- **🔊 中文语音播放** — PowerShell TTS / edge-tts 中文女声
- **🔄 重复提醒** — 支持每天、每周、每月重复
- **⏰ 到点自动播放** — 后台调度器每 5 秒检查一次，到期自动播报
- **🎨 Web 管理界面** — 双标签页：本地提醒 + 板子提醒
- **🤖 多后端 TTS 自动回退** — PowerShell → pyttsx3 → gTTS → edge-tts
- **🔗 板子协同** — 通过 AI Pet 服务器 (47.118.26.156:8000) 与 RK3576 板子通信
- **🖥️ 板子实时监控** — 查看板子在线状态、提醒列表、板子存放路径
- **🕐 实时时钟** — 页面顶部显示当前时间
- **👤 有人/没人检测** — 提醒到点时检测无人则延时，超 1 小时标记失败
- **🎯 六种状态标签** — ⏳待下发 / 📨已下发 / 🔄执行中 / ✅已完成 / ❌失败 / 🚫已取消
```
## 系统架构
```
┌──────────────────────────────────────────────────────────────────┐
│                        电脑端                                     │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐                    │
│  │ 8000 端口          │    │ 8001 端口          │                    │
│  │ 主界面 (FastAPI)   │    │ 管理服务器          │                    │
│  │ ┌─ 本地提醒标签 ✔  │    │ ┌─ 发送提醒到设备   │                    │
│  │ └─ 板子提醒标签 ✔  │    │ └─ 远程提醒列表     │                    │
│  │                    │    │  (HTTP Section 22)  │                    │
│  │ 调度器(5s间隔)     │◄──►│                    │                    │
│  │ TTS + 播放(pygame) │    │ WS 连接服务器       │                    │
│  └──────────────────┘    └─────────┬──────────┘                    │
│                                      │ HTTP /api/v1/aipet/app/     │
│                                      ▼                             │
│                        ┌──────────────────────────┐                │
│                        │  AI Pet 远程服务器          │                │
│                        │  47.118.26.156:8000       │                │
│                        │  ┌─ 提醒 CRUD (22.3-22.5) │                │
│                        │  └─ WS 下发到设备 (22.6)   │                │
│                        └──────────┬───────────────┘                │
│                                   │ WebSocket                      │
│                                   ▼                                │
│                        ┌──────────────────────────┐                │
│                        │  RK3576 板子               │                │
│                        │  192.168.1.226            │                │
│                        │                          │                │
│                        │  board_ws_client.py       │◄── SSH ────  │
│                        │  (systemd 守护)            │    状态同步     │
│                        │  SQLite: reminders.db     │                │
│                        │  audio/                   │                │
│                        └──────────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘
```
### 通信链路
```
**发送提醒：**
8001 Web → Section 22.3 POST /reminders/{pid} (创建) 
          → Section 22.6 POST /reminders/send/{pid}/{id} (下发)
          → 远程服务器 WS → 板子 board_ws_client → SQLite
          → 8001 同步到 8000 缓存 (/api/board-reminders/sync)
          缓存状态：板子在线 → sent / 板子离线 → pending
```
**状态流转：**
```
⏳待下发(pending) ───→ 📨已下发(sent) ───→ 🔄执行中(executing)
                                              ├──→ ✅已完成(completed)  有人出现 + 播放
                                              └──→ ❌失败(failed)      1小时超时无人
                                                   ↕
                                              🚫已取消(cancelled)    远程删除
```
**自动播报：**
```
调度器(5秒) → process_reminders()
              ├── 还没到时间 → skip
              ├── 时间到 + 有人 → TTS生成 → 播放 → ✅已完成
              ├── 时间到 + 没人 → 🔄执行中(10min后重试)
              └── 1小时超时仍无人 → ❌失败
              状态变更后 → SSH同步板子 SQLite + 通知远程服务器(PUT)
```
**板子回传状态：**
```
board_ws_client 轮询线程(每10秒) → SQLite 查 status ∈ {completed,failed}
                                 → WS command_response → 远程服务器更新
```
## 快速启动

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 终端1 - 8000 主界面 (本地提醒 + 板子提醒 + 自动播报)
cd backend
python main.py
```

# 终端2 - 8001 管理服务器 (发送提醒、远程提醒列表、删除)
cd management
python server.py
```

### 3. 打开浏览器

- **主界面（操作本地/板子提醒）** → http://127.0.0.1:8000
- **管理端（发送到板子）** → http://127.0.0.1:8001

> ⚠️ 如有代理软件，请用 127.0.0.1 而非 localhost。
## 使用说明
```
### 本地提醒 (8000)
在「本地提醒」标签页中操作完整的增删改查。到点自动通过电脑喇叭播报。
```
### 板子提醒 (8000)
在「板子提醒」标签页中：
- 查看板子在线状态，实时显示板子上的提醒
- 👤 有人 / 🚫 没人开关：到点时检测此状态决定是否播报
- 试听：点击 🔊 按钮 → TTS 合成 → 本地播放
- 状态自动刷新（每 5 秒）
```
### 发送提醒到板子 (8001)
1. 输入标题、内容、时间
2. 选择重复类型：不重复 / 每天 / 每周 / 每月
3. 点击发送 → 通过远程服务器下发到板子
4. 远程提醒列表实时查看服务器上的所有提醒
```
### 删除功能 (8001)
远程提醒列表每行有「删除」按钮 → 同步删除远程服务器 + 板子标记 🚫已取消
```
## TTS 语音合成
```
| 优先级 | 后端 | 依赖 | 音色 |
|--------|------|------|------|
| 1️⃣ | **PowerShell TTS** | Windows + .NET | Microsoft Huihui Desktop |
| 2️⃣ | pyttsx3 | Windows SAPI5 | 系统语音 |
| 3️⃣ | edge-tts | 需要外网 | 卡通中文女声 Xiaoxiao |
```
## 状态标签说明
```
| 状态 | 含义 | 触发条件 |
|------|------|---------|
| ⏳ 待下发 | 板子离线，提醒只在远程服务器上 | 同步时板子 SSH 不可达 |
| 📨 已下发 | 板子已收到该提醒 | 同步时板子在线 / 板子 SQLite 查到 |
| 🔄 执行中 | 到时间了但没人 | 提醒时间到 + 没人开关为 🚫 |
| ✅ 已完成 | 播放完成 | 提醒时间到 + 有人 + 喇叭播报 |
| ❌ 失败 | 超时无人 | 1 小时超时仍 🚫 没人 |
| 🚫 已取消 | 远程删除 | 8001 页面点击删除 |
```
## 项目结构
```
reminder_codex/
├── README.md
├── .gitignore
├── board_reminders.json       # 板子提醒本地缓存（调度器核心数据）
├── board_presence.json        # 有人/没人状态
├── audio/                     # TTS 生成的语音文件
├── backend/                   # 8000 后端 (FastAPI)
│   ├── main.py                # 入口 + uvicorn 启动
│   ├── config.py              # 配置
│   ├── database.py            # SQLite 异步引擎
│   ├── player.py              # pygame 音频播放器
│   ├── models/
│   │   └── reminder.py        # 本地提醒 ORM 模型
│   ├── routes/
│   │   ├── reminders.py       # 本地提醒 CRUD API
│   │   ├── board.py           # 板子提醒 SSH 代理 + API
│   │   ├── board_scheduler.py # 调度器入口
│   │   └── presence.py        # 有人/没人逻辑 + 状态变更
│   ├── services/
│   │   ├── tts.py             # TTS 合成引擎(多后端回退)
│   │   └── scheduler.py       # asyncio 定时调度器
│   └── requirements.txt
├── frontend/                  # 8000 Web 前端
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── management/                # 8001 管理服务器
│   ├── server.py              # FastAPI + WS 客户端 + HTTP 代理
│   ├── index.html             # 管理界面（发送 + 远程列表 + 删除）
│   └── reminders.json
├── robot_reminder/            # 板子侧代码（PC 开发副本）
│   └── board_ws_client.py     # 板子 WS 客户端(含状态轮询线程)
├── robot_websocket/           # 通信节点 ROS2 包
│   └── ...
├── new_protocol/              # 通信协议文档
│   ├── AI-Pet-App-HTTP-API-协议文档(1).md
│   ├── AI-Pet-WebSocket-协议文档(1).md
│   └── old/
└── deploy/                    # 部署脚本
    └── deploy.sh
```
## API 接口
```
### 本地提醒 (8000)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reminders | 获取所有提醒 |
| POST | /api/reminders | 创建提醒 |
| PUT | /api/reminders/{id} | 更新提醒 |
| DELETE | /api/reminders/{id} | 删除提醒 |
| POST | /api/reminders/{id}/test-play | 试听 |
```
### 板子提醒 (8000)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/board-reminders | 获取板子提醒列表(SSH + 缓存合并) |
| GET | /api/board-reminders/status | 板子在线状态 + 提醒数 |
| GET | /api/board-reminders/presence | 获取有人/没人状态 |
| POST | /api/board-reminders/presence | 设置有人/没人 |
| POST | /api/board-reminders/sync | 8001 同步提醒到缓存 |
| POST | /api/board-reminders/status-update | 更新状态 + SSH 同步板子 |
| DELETE | /api/board-reminders/{id} | 删除板子提醒 |
| POST | /api/board-reminders/{id}/play | 播放(TTS或板子音频) |
```
### 管理服务器 (8001)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/status | 登录状态 + 收到的提醒数 |
| GET | /api/reminders | 8001 本地收到的提醒 |
| POST | /api/send-reminder | 发送提醒(Section 22.3+22.6) |
| GET | /api/remote-reminders | 远程服务器提醒列表(Section 22.1) |
| POST | /api/update-remote-status | 更新远程状态(Section 22.4 PUT) |
| POST | /api/delete-remote-reminder | 删除远程提醒(Section 22.5) |
```
## 板子部署 (RK3576)
```
板子信息：192.168.1.226，用户 cat，密码 	emppwd
```
### 已部署的服务
```
| 服务 | 文件 | 守护方式 | 功能 |
|------|------|---------|------|
| WS 客户端 | ~/reminder_system/board_ws_client.py | systemd oard-ws-client | 接收 + 状态上报 |
| 提醒数据库 | ~/reminder_system/data/reminders.db | SQLite | 存储提醒 |
| 音频文件 | ~/reminder_system/audio/ | 磁盘 | TTS 音频 |
```
### 部署更新
```
`ash
# 更新 board_ws_client.py
python deploy/deploy.py
```
# 重启服务
ssh cat@192.168.1.226 "sudo systemctl restart board-ws-client"
```
## 常见问题
```
### 浏览器 502 / 无法访问
代理软件拦截 localhost 请求。用 http://127.0.0.1:8000。
```
### 没有声音
检查 pygame 是否正常初始化，音频文件是否生成在 udio/ 目录下。
```
### 提醒到时间了没有自动播放
1. 检查后台是否有人/没人开关设为 🚫 没人（会进入延时）
2. 8000 后端是否运行中（调度器每 5 秒检查一次）
3. TTS 是否生成成功（查看 udio/ 目录下是否有 .mp3 文件）
```
### 板子状态没更新
板子离线时 8001 同步会显示 pending（⏳待下发）。板子上线后再次同步即可变为 sent（📨已下发）。
```
### 8001 Remote Reminders 为空
检查远程服务器连接是否正常，Token 是否有效（8001 会自动刷新）。
```
## 技术栈
```
| 组件 | 选型 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy (async) |
| 前端 | 原生 HTML5 / CSS3 / JavaScript |
| 语音合成 | PowerShell TTS / pyttsx3 / edge-tts |
| 音频播放 | pygame (SDL_mixer) |
| 任务调度 | asyncio 定时任务（5 秒间隔） |
| SSH 通信 | paramiko |
| WS 通信 | websocket-client |
| 远程 API | AI Pet 服务器 Section 22 (HTTP) |


## 更新日志

### 2026-06-24
`
- fix: 取消/恢复操作同步到8000时使用new_status而非硬编码cancelled
- fix: 8000后端board.py异步化，list_board_reminders改用run_in_executor后台SSH
- fix: status-update和merge按reminder_time兜底匹配，修复不同command_id/content时的状态同步
- fix: Remote Reminders Refresh改用事件委托机制，修复按钮onclick参数引用错误
- fix: 增加resp.ok检查和Array.isArray确保API响应健壮性
- fix: 使用encodeURIComponent/decodeURIComponent安全传递参数
`
