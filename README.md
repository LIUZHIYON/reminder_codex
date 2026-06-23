# 叮叮提醒 (DingDing Reminder)

一个基于 Web 的提醒管理工具，支持**到点自动播放语音提醒**。支持本地 Windows 运行，也支持通过 AI Pet 服务器与 RK3576 板子协同工作。

## 功能特性

- **📝 提醒管理** — 新增、编辑、删除提醒（完整 CRUD）
- **🔊 中文语音播放** — PowerShell TTS / edge-tts 中文女声，~1 秒合成
- **🔄 重复提醒** — 支持每天、每周、每月重复
- **⏰ 到点自动播放** — 后台调度器每 5 秒检查一次，到期自动播报
- **🎨 Web 管理界面** — 双标签页：本地提醒 + 板子提醒
- **🤖 多后端 TTS 自动回退** — PowerShell → pyttsx3 → gTTS → edge-tts
- **🔗 板子协同** — 通过 AI Pet 服务器与 RK3576 板子通信
- **🖥️ 板子实时监控** — 查看板子在线状态、提醒列表、文件路径
- **🕐 实时时钟** — 页面顶部显示当前时间

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      电脑端                              │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │ 8000 端口 │    │ 8001 端口 │    │ TTS + 播放器     │  │
│  │ 主界面     │    │ 管理服务器 │    │ (pygame)         │  │
│  │ 本地提醒   │◄──►│ WS+HTTP   │───►│                  │  │
│  │ 板子提醒   │    │ 发送提醒   │    │ 到点自动播报     │  │
│  └──────────┘    └────┬─────┘    └──────────────────┘  │
│                        │                                │
│                   HTTP │ chatWith                       │
│                        ▼                                │
│              ┌─────────────────┐                        │
│              │  AI Pet 服务器   │ 47.118.26.156:8000     │
│              │  (远程服务器)    │                        │
│              └────────┬────────┘                        │
│                       │ WebSocket                       │
│                       ▼                                │
│              ┌─────────────────┐                        │
│              │  RK3576 板子     │ 192.168.1.64          │
│              │                 │                        │
│              │  Flask 5000端口   │◄── SSH 读取───────── │
│              │  board_ws_client │                        │
│              │  SQLite 数据库   │                        │
│              └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

### 通信链路

**发送提醒：**
```
Web界面 → 8001 HTTP → AI Pet 服务器 → WS → 8001 on_msg
           ↓ (直连)
           http.client → 板子 Flask:5000 → SQLite
           ↓ (同步到本地缓存)
           8000 /api/board-reminders/sync → cache + TTS
```

**查看板子提醒：**
```
Web界面 → 8000 → SSH → 板子 SQLite 数据库
```

**自动播报：**
```
调度器(5秒间隔) → check_board_reminders()
                    ↓
                   缓存 → 到期≤5min → TTS生成 → 播放
                   缓存 → 到期>5min → 标记missed
```

## 快速启动

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务

**方式一（推荐）：** 双击 `run.bat`

**方式二：** 分别启动两个服务

```bash
# 终端1 - 8000 主界面
cd backend
python main.py

# 终端2 - 8001 管理服务器
cd management
python server.py
```

### 3. 打开浏览器

- **主界面** → [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **管理端** → [http://127.0.0.1:8001](http://127.0.0.1:8001)

> ⚠️ 如有代理软件（Clash/V2Ray），请用 `127.0.0.1` 而非 `localhost`。

## 使用说明

### 本地提醒
在 8000 端口的「本地提醒」标签页中：
- 点击「新增提醒」创建提醒
- 编辑 / 删除已有提醒
- 点击 🔊 试听语音
- 到点自动通过电脑喇叭播放

### 板子提醒
在 8000 端口的「板子提醒」标签页中：
- 查看板子在线状态
- 查看板子上的提醒列表（实时通过 SSH 读取，每 5 秒自动刷新）
- 点击 🔊 播放按钮 → TTS 生成语音本地播放
- 点击 🗑️ 删除板子上的提醒

### 发送提醒到板子
在 8001 端口的网页中：
- 输入提醒标题、内容、时间
- 点击「发送提醒」
- 提醒通过 AI Pet 服务器发给板子，同时直连板子 Flask API 并同步到本地缓存

## TTS 语音合成

| 优先级 | 后端 | 依赖 | 备注 |
|--------|------|------|------|
| 1️⃣ | **PowerShell TTS** | Windows + .NET | 本地中文语音 Huihui |
| 2️⃣ | pyttsx3 | Windows SAPI5 | 离线可用 |
| 3️⃣ | gTTS | 需要外网 | Google 在线合成 |
| 4️⃣ | edge-tts | 需要外网 | 卡通中文女声 |

Windows 上默认使用 `Microsoft Huihui Desktop` 中文语音。

## API 接口

### 本地提醒 (8000)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reminders | 获取所有提醒 |
| POST | /api/reminders | 创建提醒 |
| PUT | /api/reminders/{id} | 更新提醒 |
| DELETE | /api/reminders/{id} | 删除提醒 |
| POST | /api/reminders/{id}/test-play | 试听提醒 |

### 板子提醒 (8000)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/board-reminders | 获取板子提醒列表 |
| GET | /api/board-reminders/status | 板子状态 |
| POST | /api/board-reminders/sync | 同步提醒到本地缓存 |
| DELETE | /api/board-reminders/{id} | 删除板子提醒 |
| POST | /api/board-reminders/{id}/play | 播放提醒语音（板子无音频则TTS） |
| POST | /api/board-reminders/{id}/generate-tts | 手动生成 TTS 语音 |

### 管理服务器 (8001)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/status | 服务器 + 板子状态 |
| POST | /api/send-reminder | 发送提醒到板子 |

## 项目结构

```
reminder_codex/
├── run.bat                    # Windows 一键启动
├── README.md
├── .gitignore
├── board_reminders.json       # 板子提醒本地缓存
├── audio/                     # 生成的语音文件
├── backend/                   # 8000 后端 (FastAPI)
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 配置
│   ├── database.py            # SQLite 异步引擎
│   ├── player.py              # 音频播放器 (pygame)
│   ├── models/
│   │   └── reminder.py        # 数据模型
│   ├── routes/
│   │   ├── reminders.py       # 本地提醒 CRUD API
│   │   ├── board.py           # 板子提醒 SSH + API
│   │   └── board_scheduler.py # 板子提醒自动播报
│   ├── services/
│   │   ├── tts.py             # TTS 合成引擎
│   │   └── scheduler.py       # 到点播放调度器
│   └── requirements.txt
├── frontend/                  # Web 前端
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── management/                # 8001 管理服务器
│   ├── server.py              # FastAPI + WS 客户端
│   ├── index.html             # 管理界面
│   └── reminders.json
├── robot_reminder/            # 板子 ROS2 节点
│   ├── board_ws_client.py     # 板子 WS 客户端
│   └── ...
├── robot_websocket/           # 通信节点 ROS2 包
│   ├── robot_websocket/       # WS 客户端 + 消息处理
│   ├── config/                # 通信配置
│   └── launch/                # 启动文件
└── deploy/                    # 部署脚本
    └── deploy.sh              # 板子部署脚本
```

## 板子部署 (RK3576)

板子信息：`192.168.1.64`，用户 `cat`，密码 `temppwd`

### 已部署的服务

| 服务 | 文件 | 守护方式 |
|------|------|---------|
| Flask API | `~/reminder_system/run.py` | nohup |
| WS 客户端 | `~/reminder_system/board_ws_client.py` | systemd `board-ws-client` |
| 提醒数据库 | `~/reminder_system/data/reminders.db` | SQLite |
| 音频文件 | `~/reminder_system/audio/` | 磁盘 |

### 手动部署

```bash
ssh cat@192.168.1.64
cd ~/reminder_system
nohup python3 run.py > logs/run.log 2>&1 &
nohup python3 board_ws_client.py > logs/ws_client.log 2>&1 &
```

## 常见问题

### 浏览器 502 / 无法访问
代理软件拦截了 `localhost` 请求。用 `http://127.0.0.1:8000`。

### 没有声音
检查 pygame 是否正常初始化，以及音频文件是否生成在 `audio/` 目录下。

### 中文变成 ???? 
8001 直连板子时走了 Windows 代理导致编码损坏，已改用 `http.client` 绕过代理。

### 板子提醒列表为空
检查板子是否在线（状态灯），以及 SSH 连接是否正常。

### 提醒到时间了没有自动播放
可能原因和修复：
1. **8001 发送没同步到本地缓存** — 已修复：send() 内 POST 到 `/api/board-reminders/sync`
2. **`timedelta` 未导入导致调度器崩溃** — 已修复：`board_scheduler.py` 添加 `from datetime import timedelta`
3. **`title` 在定义前使用导致 NameError** — 已修复：`title = r.get(...)` 移到 `if rtd <= now:` 之前
4. **同步端点 `except: pass` 吞掉 TTS 错误** — 已修复：改为打印错误日志
5. **TTS 生成了但不播放** — 已修复：同步端点检查时间已到则直接播放

## 技术栈

| 组件 | 选型 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) |
| 前端 | 原生 HTML5 / CSS3 / JavaScript |
| 语音合成 | PowerShell TTS / pyttsx3 / gTTS / edge-tts |
| 音频播放 | pygame (SDL_mixer) |
| 任务调度 | asyncio 定时任务（5 秒间隔） |
| SSH 通信 | paramiko |
| WS 通信 | websocket-client |
| 板子通信 | AI Pet 服务器 API + WebSocket |
