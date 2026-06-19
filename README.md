# 叮叮提醒 (DingDing Reminder)

一个基于 Web 的提醒管理工具，支持**到点自动播放语音提醒**。专为 RK3576 板子部署设计，同时可在本地 Windows 环境运行。

## 功能特性

- **📝 提醒管理** — 新增、编辑、删除提醒（完整 CRUD）
- **🔊 中文语音播放** — 系统自带的 Huihui 中文语音（TTS），约 1 秒合成
- **🔄 重复提醒** — 支持每天、每周、每月重复
- **⏰ 到点自动播放** — 后台调度器每 5 秒检查一次，到期自动播报
- **🎨 Web 管理界面** — 响应式设计，支持 PC / 手机
- **🤖 多后端 TTS 自动回退** — PowerShell → pyttsx3 → gTTS → edge-tts

## 快速开始

### 1. 安装依赖

打开终端（CMD / PowerShell），进入项目目录：

```bash
cd C:\Users\29503\Desktop\reminder_codex\backend
pip install -r requirements.txt
```

### 2. 启动服务

**方式一（推荐）：** 双击 `run.bat`

**方式二：** 命令行启动

```bash
cd C:\Users\29503\Desktop\reminder_codex\backend
python main.py
```

### 3. 打开浏览器

访问 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

> ⚠️ 如果你有代理软件（Clash/V2Ray 等），请使用 `127.0.0.1` 而不是 `localhost`，否则代理可能拦截请求返回 502。

## TTS 语音合成

系统按以下顺序尝试后端，直到成功为止：

| 优先级 | 后端 | 依赖 | 备注 |
|--------|------|------|------|
| 1️⃣ | **PowerShell TTS** | Windows + .NET | ✅ **推荐**，本地中文语音 Huihui，~~1秒合成 |
| 2️⃣ | pyttsx3 | Windows SAPI5 | 离线可用，备选 |
| 3️⃣ | gTTS | 需要外网 | Google 在线合成 |
| 4️⃣ | edge-tts | 需要外网 | Microsoft 在线，卡通音色 |

Windows 上默认使用 `Microsoft Huihui Desktop` 中文语音。（非中文系统先用 Huihui，若没有则回退到 `SelectVoiceByHints(Female)`。）

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reminders | 获取所有提醒 |
| POST | /api/reminders | 创建提醒 |
| PUT | /api/reminders/{id} | 更新提醒 |
| DELETE | /api/reminders/{id} | 删除提醒 |
| POST | /api/reminders/{id}/test-play | 试听提醒 |

### 创建 / 更新提醒

```json
{
  "title": "喝水提醒",
  "description": "该喝水了",
  "reminder_time": "2026-06-20T10:00:00",
  "is_repeating": true,
  "repeat_type": "daily"
}
```

> `repeat_type` 可选：`"daily"`(每天) / `"weekly"`(每周) / `"monthly"`(每月)

## 常见问题

### Q: 服务打开了，但浏览器访问不了 / 502 Bad Gateway

你的代理软件（Clash / V2Ray 等）拦截了 `localhost` 请求。

**解决：** 浏览器地址栏输入 `http://127.0.0.1:8000`（用 IP 地址代替 `localhost`）。

### Q: 没有声音 / "corrupt mp3 file"

PowerShell TTS 输出的是 WAV 格式，以前文件扩展名是 `.mp3` 导致播放器解析出错。已修复为 `.wav`。

### Q: 播放的还是旧提醒的语音

调度器以前用缓存数据合成语音，改了标题后可能还是旧的。已修复：调度器每次合成前都会重新从数据库获取最新标题。

## 项目结构

```
reminder_codex/
├── run.bat               # Windows 一键启动
├── README.md
├── .gitignore
├── audio/                # 生成的语音文件（.wav）
├── backend/              # Python 后端 (FastAPI)
│   ├── main.py           # FastAPI 入口 + 路由注册
│   ├── config.py         # 配置（端口 / TTS 参数）
│   ├── database.py       # SQLite + SQLAlchemy 异步引擎
│   ├── player.py         # 音频播放器（pygame，懒初始化）
│   ├── models/
│   │   └── reminder.py   # 提醒数据模型
│   ├── routes/
│   │   └── reminders.py  # CRUD + 试听 API
│   ├── services/
│   │   ├── tts.py        # 多后端 TTS 合成引擎
│   │   └── scheduler.py  # 到点自动播放调度器
│   └── requirements.txt
└── frontend/             # Web 前端
    ├── index.html
    ├── css/style.css
    └── js/app.js
```

## 部署到 RK3576

1. **Python**: 安装 ARM 架构 Python 3.8+
2. **依赖**: 复制 `backend/requirements.txt`，在 RK3576 上执行 `pip install -r requirements.txt`
3. **TTS**: PowerShell 后端不可用（Windows 专属），建议用 `edge-tts` 或 `pyttsx3`
4. **音频**: 安装 `libsdl2-mixer-2.0-0`（pygame 的 ALSA/PulseAudio 后端）
5. **启动**: 使用 `nohup python main.py &` 或配置 systemd 服务

## 技术栈

| 组件 | 选型 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) |
| 前端 | 原生 HTML5 / CSS3 / JavaScript |
| 语音合成 | PowerShell TTS (Huihui) / pyttsx3 / gTTS / edge-tts |
| 音频播放 | pygame (SDL_mixer) |
| 任务调度 | asyncio 定时任务（5 秒间隔） |
