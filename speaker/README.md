# robot_voice_bridge

语音桥接节点，在 TTS 合成节点和音频播放节点之间建立 Action 接口，支持文本合成播报、音频文件播报、任务队列和断点续播。

## 架构

```
外部 Client --Action /voice/speak--> voice_bridge --pub /tts/text--> doubao_tts_node
                                         |         sub /tts/audio <--
                                         |
                                         |    +- 文本路径: TTS->WAV->临时文件->audio_node
                                         |    +- 文件路径: 直接传 file_path 给 audio_node
                                         |
                                         +--pub /audio/audio_cmd--> robot_audio_node
                                                   |
                                                   +--sub /audio/status <--  播放进度
                                                   +--sub /audio/complete <-- 播放完成
                                                   |
                                                   v
                                                喇叭出声
```

两种播放路径最终都通过 `file_path` 方式传给 audio_node，由 audio_node 的 FFmpeg + ALSA 管线完成解码和播放。

## Action 接口

### /voice/speak (robot_voice_bridge/action/Speak)

**Goal**
| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 要合成的文本（非空走 TTS 路径） |
| `audio_path` | string | 要播放的音频文件绝对路径 |

> **注意**：`text` 和 `audio_path` 二选一，都非空时优先走文本/TTS 路径。

**Result**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `message` | string | 结果描述 |

**Feedback**
| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `ACCUMULATING` / `READY` / `PLAYING` / `PAUSED` / `QUEUED` |
| `queue_position` | int32 | 0=当前执行中 |
| `progress` | int32 | 0-100，PLAYING 时有效 |
| `message` | string | 附加信息 |

## 队列与打断

新任务到达时：
- **空闲** → 立即执行
- **忙** → 打断当前任务，当前任务塞回队首，新任务立即执行

当前任务完成后自动从队首取出续播，形成 LIFO（后进先出）栈式调度。

## 断点续播

支持四种打断+续播组合：

| 打断方 | 被断方 | 续播方式 |
|--------|--------|----------|
| 文本 | 文本 | 墙钟偏移 + WAV 裁剪 |
| 文本 | 音频路径 | 读入原始文件 + 墙钟偏移 + WAV 裁剪 |
| 音频路径 | 文本 | 墙钟偏移 + WAV 裁剪 |
| 音频路径 | 音频路径 | 读入原始文件 + 墙钟偏移 + WAV 裁剪 |

关键设计：

- **墙钟时间跟踪**：不依赖 audio_node 的解码进度（短文件解码快于播放会导致偏移不准），在打断时用实际流逝时间 × 音频字节率计算偏移
- **PCM 对齐**：偏移量对齐到 16-bit 采样边界（`pcm_offset &= ~1ULL`），避免字节错位导致杂音
- **WAV 头重建**：从原始 WAV 头读取采样率和声道数，按剩余 PCM 大小重建正确的 WAV 头
- **过期 Completion 处理**：打断时发送 `__stop__` 会触发 `SpeakerCtl` 内部 `stop()` 产生一次过期的 `/audio/complete` 消息，通过计数器 `_stale_completions_pending` 在回调中优先消费，避免错误结束新目标

### 续播流程

1. 打断时：记录墙钟偏移 → `bytes_sent`，目标标记为 `PAUSED`，推入队首
2. 续播时：从 `bytes_sent` 偏移切出剩余 PCM，重建 WAV 头，写入新临时文件
3. 发送新临时文件给 audio_node，续播完成后正常结束 goal

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `tts_text_topic` | `/tts/text` | 发往 TTS 的文本话题 |
| `tts_audio_topic` | `/tts/audio` | 接收 TTS 音频的话题 |
| `tts_status_topic` | `/tts/status` | 监听 TTS 状态的话题 |
| `audio_cmd_topic` | `/audio/audio_cmd` | 发往播放节点的音频指令 |
| `audio_complete_topic` | `/audio/complete` | 播放完成信号 |
| `max_queue_size` | `10` | 最大排队数 |
| `tts_silence_timeout_ms` | `2000` | TTS 静默超时 |
| `chunk_duration_ms` | `40` | 保留参数（当前使用 file_path 模式） |
| `resample_to_48k_stereo` | `false` | 24k 单声道 -> 48k 立体声重采样（由 audio_node 的 FFmpeg 处理） |

## 依赖

- `rclcpp`、`rclcpp_action`、`std_msgs`
- `robot_audio_node`（AudioCmd 消息）
- `robot_interface`（AudioData 消息）
- ROS2 Humble

## 构建

```bash
cd ~/VOICE
colcon build --packages-select robot_voice_bridge
source install/setup.bash
```

## 启动

```bash
ros2 launch robot_voice_bridge voice_bridge.launch.py
```

需要同时运行 `robot_audio_node` 和 `robot_doubao_tts_node` 才能完整工作。

## 使用示例

```bash
# 文本播报
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {text: '你好世界'}"

# 带进度反馈
ros2 action send_goal --feedback /voice/speak robot_voice_bridge/action/Speak "
  {text: '你好世界'}"

# 文本打断文本 + 续播
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {text: '第一段长文本'}" &
sleep 2
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {text: '打断插播'}"

# 文本打断音频文件 + 续播
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {audio_path: '/home/cat/audio/bgm.wav'}" &
sleep 2
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {text: '插播通知'}"

# 音频文件打断文本 + 续播
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {text: '长文本播报'}" &
sleep 3
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {audio_path: '/home/cat/audio/alert.wav'}"

# 音频文件打断音频文件 + 续播
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {audio_path: '/home/cat/audio/bgm.wav'}" &
sleep 2
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {audio_path: '/home/cat/audio/alert.wav'}"

# 直接播放音频文件（不打断）
ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak "
  {audio_path: '/home/cat/audio/sound.wav'}"
```

## Python 客户端示例

```python
from robot_voice_bridge.action import Speak
from rclpy.action import ActionClient

client = ActionClient(node, Speak, '/voice/speak')

def feedback_cb(fb):
    msg = fb.feedback
    print(f'{msg.status}  queue={msg.queue_position}  {msg.progress}%')

# 文本播报
goal = Speak.Goal()
goal.text = '你好世界'

send_future = client.send_goal_async(goal, feedback_cb)
handle = send_future.result()          # goal 被接受
result = handle.get_result_async().result()
print(f'完成: {result.result.success}')

# 音频文件播报
goal2 = Speak.Goal()
goal2.audio_path = '/home/cat/audio/sound.wav'
send_future2 = client.send_goal_async(goal2)

# 取消（队列中或执行中都行）
handle.cancel_goal_async()
```

## 播放管线

### 文本路径 (text -> TTS -> file_path)

1. Goal 接受 -> 发布文本到 `/tts/text`
2. TTS 节点返回音频数据（24kHz/单声道/16bit PCM）
3. 静默超时或 TTS 状态 done -> 将所有 PCM 拼合，调用 `PCMConverter::create_wav()` 生成完整 WAV
4. 写入临时文件 `/tmp/tts_<id>.wav`
5. 发送 `AudioCmd(file_path=临时文件)` 给 audio_node
6. 等待 `/audio/complete` 回调结束 goal

### 文件路径 (audio_path -> file_path)

1. Goal 接受 -> 直接发送 `AudioCmd(file_path=原始文件)` 给 audio_node
2. 等待 `/audio/complete` 回调结束 goal

## PCM 格式处理

TTS 输出裸 PCM（24kHz/单声道/16bit），`PCMConverter::create_wav()` 添加 44 字节 WAV Header 生成标准 WAV 文件。重采样默认关闭（`resample_to_48k_stereo: false`），由 audio_node 的 FFmpeg swresample 自动处理格式转换。
