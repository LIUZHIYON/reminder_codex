# board_backup_20260629

板子 (192.168.1.191) 项目文件备份 - 2026-06-29

## 目录结构总览

```
board_backup_20260629\
│
├── home\cat\                                    ← 板子 ~/ 目录
│   ├── (启动脚本)                                🎯 启动语音三件套等
│   ├── ros2_ws\src\                             ← ROS2 工作空间源码
│   ├── reminder_system\                         ← 提醒系统
│   └── talk_with\ros_ws\install\                ← 中继节点（另一个项目）
│
├── opt\ros\humble\share\                        ← 预装 ROS 包（配置+启动文件）
│   ├── robot_voice_bridge\                      🎯 语音桥接
│   ├── robot_audio_node\                        🎵 音频播放
│   └── robot_doubao_tts_node\                   🔊 豆包 TTS
│
└── etc\systemd\system\                          ← 系统服务
```

## 文件清单

### 1️⃣ 启动脚本 (`home/cat/`)

| 文件 | 说明 |
|------|------|
| `start_voice.sh` | 🎯 启动语音三件套 (voice_bridge + tts + audio) |
| `setup_audio.sh` | 🔊 音频功放配置 (spk switch, 音量) |
| `launch_all.sh` | 🚀 一键启动所有节点 |
| `watchdog.sh` | 👀 看门狗 - 节点挂了自动重启 |
| `start_relay.sh` | 🔄 启动中继节点 |
| `restart_relay.sh` | 🔄 重启中继 |
| `voice_test.sh` | 🔊 语音播报测试 |
| `full_test.sh` | ✅ 全功能测试 |
| `test_speaker.sh` | 🔊 扬声器测试 |
| `tts_node_patched.py` | 🔧 补丁版 tts_node |
| `tts_launch_patched.py` | 🔧 补丁版 launch 文件 |

### 2️⃣ ROS2 工作空间源码 (`home/cat/ros2_ws/src/`)

| 目录/文件 | 说明 |
|-----------|------|
| `robot_reminder_bt/` | 🧠 **行为树提醒包** - bt_engine, reminder_nodes, reminder_tree |
| `robot_reminder_bt/launch/` | 启动文件 (reminder_bt.launch.py) |
| `robot_reminder_bt/config/` | 行为树配置 (reminder_bt_config.yaml) |
| `robot_reminder_bt/robot_reminder_bt/` | Python 节点源码 (reminder_bt_node.py, bt_engine.py) |
| `robot_aipet_relay/` | 🔄 **AI Pet 中继** - relay_node.py |
| `robot_aipet_relay/launch/` | 中继启动文件 |
| `robot_floor_seg/` | 🗺️ **地板分割** - seg_node.py, rknn_infer.py |
| `config/trees/` | 🌳 **行为树 XML** |
| `config/trees/reminder_bt_v3.xml` | 行为树定义 |
| `config/trees/nodes_metadata.xml` | Groot2 编辑器节点定义 |
| `config/reminder_bt_config.yaml` | 行为树配置 |
| `src/` | ⚙️ **C++ 行为树** (reminder_bt_main.cpp, reminder_nodes.cpp) |
| `launch/` | ROS2 启动文件 |
| `include/` | C++ 头文件 |
| `test/` | 测试脚本 |
| `docs/` | 文档 |
| `scripts/` | 运行脚本 |

### 3️⃣ 提醒系统 (`home/cat/reminder_system/`)

| 文件 | 说明 |
|------|------|
| `board_ws_client.py` | 🔗 **WebSocket 客户端** - 连接远端服务器(47.118.26.156) |
| `run.py` | 🏃 运行入口 |
| `requirements.txt` | Python 依赖 |
| `start_ws_client.sh` | ▶️ WS 客户端启动脚本 |
| `start_robot_ws.sh` | ▶️ ROS 工作空间启动脚本 |
| `app/` | 📱 **Web APP** |
| `app/web_app.py` | Web 应用 |
| `app/tts_service.py` | TTS 服务 |
| `app/scheduler.py` | 定时调度 |
| `app/config.py` | 配置 |
| `app/models.py` | 数据模型 |
| `app/json_reader.py` | JSON 读取器 |
| `app/templates/index.html` | 网页模板 |
| `app/static/style.css` | 样式 |
| `app/__init__.py` | 包初始化 |
| `data/` | 数据存储 |
| `scripts/` | 工具脚本 |

### 4️⃣ 中继节点 (`home/cat/talk_with/ros_ws/install/`)

| 目录 | 说明 |
|------|------|
| `robot_aipet_relay/` | 🔄 **AI Pet 中继包** |
| `robot_aipet_relay/lib/.../robot_aipet_relay/` | Python 源码 |
| `robot_aipet_relay/lib/.../ws_daemon.py` | 🌐 WebSocket 守护进程 |
| `robot_aipet_relay/lib/.../relay_node.py` | 🤖 中继节点 |
| `robot_aipet_relay/lib/.../relay_voice_bridge.py` | 🔄 语音中继 |
| `robot_aipet_relay/lib/.../relay_mw.py` | 中间件中继 |
| `robot_aipet_relay/lib/.../file_mw.py` | 文件中间件 |
| `robot_aipet_relay/share/.../launch/relay.launch.py` | 启动文件 |
| `bt_relay/` | 🌳 **行为树中继** (C++) |
| `bt_relay/lib/bt_relay/bt_relay_node` | 编译的 C++ 节点 |
| `bt_relay/share/bt_relay/trees/relay_task.xml` | 中继任务行为树 |

### 5️⃣ 预装 ROS 包配置 (`opt/ros/humble/share/`)

#### robot_voice_bridge (语音桥接)

| 文件 | 说明 |
|------|------|
| `config/voice_bridge_config.yaml` | 🎯 配置: TTS话题、音频话题、队列设置 |
| `launch/voice_bridge.launch.py` | 启动文件 |
| `launch/all_nodes.launch.py` | 启动所有节点 |
| `action/Speak.action` | Speak Action 定义 |
| `package.xml` | 包描述 |

#### robot_audio_node (音频播放)

| 文件 | 说明 |
|------|------|
| `config/robot_audio_node.yaml` | 🎵 配置: ALSA设备、音量 |
| `launch/robot_audio_node.launch.py` | 启动文件 |
| `msg/AudioCmd.msg` | 音频命令消息定义 |
| `srv/SetVolume.srv` | 设置音量服务 |
| `srv/GetVolume.srv` | 获取音量服务 |

#### robot_doubao_tts_node (豆包 TTS)

| 文件 | 说明 |
|------|------|
| `config/tts_config.yaml` | 🔊 TTS 配置: API key, speaker, resource_id |
| `launch/tts.launch.py` | 启动文件 |
| `launch/tts_patched.launch.py` | 补丁版启动文件 |

### 6️⃣ 系统服务 (`etc/systemd/system/`)

| 服务文件 | 说明 | 状态 |
|----------|------|------|
| `board-ws-client.service` | 🔗 WebSocket 连接远端服务器 | 开机自启 ✅ |
| `audio-setup.service` | 🔊 开机音频配置 | 开机执行 ✅ |
| `heartbeat.service` | 💓 心跳上报 | 运行中 ✅ |
| `reminder.service` | ⏰ 提醒服务 | - |

## 板子信息

| 项目 | 值 |
|------|-----|
| IP | 192.168.1.191 |
| 用户 | cat |
| ROS 版本 | ROS 2 Humble |
| 系统 | Ubuntu (rockchip) |

## 运行中的 ROS 节点

| 节点 | 数量 | 来源 | 作用 |
|------|:----:|------|------|
| `/voice_bridge` | 1 | 预装包 | 语音桥接 Action 接口 |
| `/tts_node` | 1 | 预装包 | 豆包 TTS 合成 |
| `/robot_audio_node` | 1 | 预装包 | ALSA 音频输出 |
| `/aipet_relay_node` | 1 | talk_with 项目 | AI Pet 中继 |
| `/ws_daemon_bridge` | 1 | talk_with 项目 | WebSocket 连接管理 |
| `/relay_voice_bridge` | 1 | talk_with 项目 | 语音中继 |
| `/bt_relay_node` | 1 | talk_with 项目 | 行为树中继 |

## 备份说明

- 备份时间: 2026-06-29
- 文件总数: 177 个
- 总大小: 4.6 MB
- 目录结构保留板子原始路径
