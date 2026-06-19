# 叮叮提醒 (DingDing Reminder)

一个基于 Web 的提醒管理工具，支持**到点自动播放语音提醒**。专为 RK3576 板子部署设计，同时可在本地 Windows 环境运行。

## 功能特性

- **📝 提醒管理** — 新增、编辑、删除提醒
- **🔊 语音播放** — 提醒到点后自动播放语音（卡通人物风格声音）
- **🔄 重复提醒** — 支持每天、每周、每月重复
- **⏰ 自动调度** — 后台调度器每 5 秒检查一次，到点自动播放
- **🎨 精美 Web 界面** — 响应式设计，支持移动端
- **🤖 多后端 TTS** — 自动尝试多个语音合成引擎

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务

方式一：双击 `run.bat`

方式二：命令行启动
```bash
cd backend
python main.py
```

### 3. 打开浏览器

访问 http://localhost:8000

## TTS 语音合成

| 后端 | 要求 | 声音特点 |
|------|------|----------|
| edge-tts (Microsoft) | 需联网 | 🎭 卡通风格，推荐 |
| gTTS (Google) | 需联网 | 标准合成 |
| PowerShell (Windows) | Windows + .NET | 系统默认女声 |
| pyttsx3 (离线) | 离线可用 | SAPI5 语音 |

系统会自动尝试以上后端，按顺序使用第一个成功的。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reminders | 获取所有提醒 |
| POST | /api/reminders | 创建提醒 |
| PUT | /api/reminders/{id} | 更新提醒 |
| DELETE | /api/reminders/{id} | 删除提醒 |
| POST | /api/reminders/{id}/test-play | 试听提醒 |

### 创建提醒示例

```json
{
  "title": "喝水提醒",
  "description": "该喝水了",
  "reminder_time": "2026-06-20T10:00:00",
  "is_repeating": true,
  "repeat_type": "daily"
}
```

## 项目结构

```
reminder_codex/
├── backend/              # Python 后端 (FastAPI)
│   ├── main.py           # 入口文件
│   ├── config.py         # 配置
│   ├── database.py       # 数据库配置
│   ├── player.py         # 音频播放器 (pygame)
│   ├── models/
│   │   └── reminder.py   # 数据模型
│   ├── routes/
│   │   └── reminders.py  # API 路由
│   ├── services/
│   │   ├── tts.py        # TTS 语音合成
│   │   └── scheduler.py  # 定时调度器
│   └── requirements.txt  # Python 依赖
├── frontend/             # Web 前端
│   ├── index.html        # 主页面
│   ├── css/style.css     # 样式
│   └── js/app.js         # 前端逻辑
├── audio/                # 生成的语音文件
├── run.bat               # Windows 启动脚本
└── README.md
```

## 部署到 RK3576

RK3576 是 ARM Linux 板子，需要调整：

1. **Python 环境**: 使用 ARM 架构的 Python 3.8+
2. **TTS**: PowerShell 后端不可用，建议使用 `edge-tts` 或 `pyttsx3`
3. **音频播放**: pygame 支持 ALSA/PulseAudio，需要安装 `libsdl2-mixer-2.0-0`
4. **启动方式**: 使用 `nohup python main.py &` 或 systemd 服务

## 技术栈

- **后端**: Python 3.8+, FastAPI, SQLAlchemy (async), SQLite
- **前端**: HTML5, CSS3, JavaScript (原生)
- **语音**: edge-tts, gTTS, pyttsx3, PowerShell TTS
- **音频**: pygame (SDL_mixer)
- **调度**: asyncio 定时任务
