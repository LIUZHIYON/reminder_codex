# 板子提醒项目启动说明

## 目录结构

```
板子文件备份/
└── home/
    └── cat/
        ├── reminder_remote/          ← 8001 前端服务
        └── ros2_ws/src/robot_reminder_bt/   ← 3 个提醒节点
```

---

## 前置准备（每次登录板子必须先执行）

```bash
ssh cat@192.168.1.190

# 设置 ROS2 环境
source /opt/ros/humble/setup.bash
export PYTHONPATH=/home/cat/ros2_ws/src:$PYTHONPATH
```

---

## 一、3 个提醒节点的启动

### 节点 1：reminder_ws_daemon（WebSocket 客户端）

连接云端服务器，接收推送提醒。

```bash
python3 /home/cat/ros2_ws/src/robot_reminder_bt/robot_reminder_bt/reminder_ws_daemon.py \
  --ros-args \
  -p server_host:=47.118.26.156 \
  -p server_port:=8000 \
  -p serial_number:=6976f96f-bc80-56e3-9b27-13d12cdde9d3
```

日志文件：`/tmp/reminder_ws_daemon.log`

---

### 节点 2：aipet_reminder_node（提醒转发节点）

接收 ws_daemon 的消息，转发给行为树驱动。

```bash
python3 -m robot_reminder_bt.aipet_reminder_node
```

---

### 节点 3：reminder_bt_driver（行为树驱动）

处理提醒、判断时间、触发语音播放。

```bash
python3 -m robot_reminder_bt.reminder_bt_driver \
  --ros-args \
  -p tick_interval_ms:=200 \
  -p command_topic:=/robot/command
```

日志文件：`/tmp/bt_driver.log`

---

### 一键启动 3 个节点

```bash
source /opt/ros/humble/setup.bash
export PYTHONPATH=/home/cat/ros2_ws/src:$PYTHONPATH
cd /home/cat/ros2_ws

# 启动 ws_daemon
nohup python3 /home/cat/ros2_ws/src/robot_reminder_bt/robot_reminder_bt/reminder_ws_daemon.py \
  --ros-args -p server_host:=47.118.26.156 -p server_port:=8000 \
  -p serial_number:=6976f96f-bc80-56e3-9b27-13d12cdde9d3 \
  > /tmp/reminder_ws_daemon.log 2>&1 &

# 启动 aipet_reminder_node
nohup python3 -m robot_reminder_bt.aipet_reminder_node \
  > /tmp/aipet_reminder_node.log 2>&1 &

# 启动行为树驱动
nohup python3 -m robot_reminder_bt.reminder_bt_driver \
  --ros-args -p tick_interval_ms:=200 -p command_topic:=/robot/command \
  > /tmp/bt_driver.log 2>&1 &
```

---

## 二、语音服务启动（3 个节点，必须）

行为树的语音播放功能依赖以下 ROS2 节点：

```bash
# 1. 音频播放节点
ros2 launch robot_audio_node robot_audio_node.launch.py &

# 2. TTS 语音合成节点（已打补丁版本）
ros2 launch robot_doubao_tts_node tts_patched.launch.py &

# 3. 语音中转节点
ros2 launch robot_voice_bridge voice_bridge.launch.py &
```

---

## 三、8001 前端的启动

8001 端口是独立 Flask 服务，**不需要 ROS2 环境**，负责发送提醒到云端。

```bash
# 直接运行
python3 /home/cat/reminder_remote/server.py

# 或者后台运行
nohup python3 /home/cat/reminder_remote/server.py > /tmp/server_8001.log 2>&1 &
```

访问地址：`http://192.168.1.190:8001/`

---

## 四、验证是否启动成功

```bash
# 检查 ROS2 节点是否在线
source /opt/ros/humble/setup.bash
ros2 node list

# 应该看到以下节点（你的3个）：
#   /reminder_ws_daemon
#   /aipet_reminder_node
#   /reminder_bt_driver

# 检查语音节点：
#   /voice_bridge
#   /tts_node
#   /robot_audio_node

# 检查 8001 端口
ss -tlnp | grep 8001
```

---

## 五、注意事项

- `spk switch` 默认是 off，听不到声音。需要手动开启：`amixer sset 'spk switch' on`
- 同事的节点（`aipet_relay_node`、`bt_relay_node` 等）与本项目无关，不影响提醒流程
- 3 个提醒节点都需要先 `source /opt/ros/humble/setup.bash` 设置 ROS2 环境
