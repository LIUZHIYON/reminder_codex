# 黑板变量不显示 Bug 修复记录

## 版本

v2.4 — 2026-06-29

## 症状

连接 BehaviorTreeMonitor Desktop App 或 Web 监控器 (8003) 后：

- 黑板面板显示 `0 keys / 1 keys`
- 变量名显示 `_raw:int 123`（MessagePack 解析失败的回退）
- 无法看到 `pending_count`、`tts_text`、`reminder_status` 等实际黑板变量

## 根因分析

黑板数据从 BT driver → ZMQ groot2_server → Monitor App 经过三层传递，其中有两个关键不兼容：

### 1. ZMQ 回复格式：单帧 → 多帧

**问题：** Groot2 Monitor 协议期望 `send_multipart([header, payload])` 两帧回复。原始实现用 `send(reply)` 发单帧。

**修复：** `groot2_server.py` 的 T/S/B 三个处理分支全部改为 `sock.send_multipart([reply_header, data])`

### 2. 黑板数据编码：JSON → MessagePack

**问题：** BehaviorTreeMonitor Desktop App 的 `_parse_blackboard_data()` 使用 `msgpack.Unpacker()` 解析黑板数据。但 `groot2_server.py` 发送的是 JSON 格式。

```python
# Desktop App 解析器 (bt_monitor/server.py line 332)
unpacker = msgpack.Unpacker()
unpacker.feed(raw)       # <- 期望 MessagePack
data = unpacker.unpack()
# JSON 数据在此处解析失败 -> fallback 显示 _raw
```

**修复：** `groot2_server.py` 改为 `msgpack.dumps(wrapper)`，并添加 `import msgpack` 回退逻辑

### 3. 节点颜色不变色

**问题：** `bt_engine.py` 和 `reminder_bt_nodes.py` 的所有 `execute()` 方法没有更新 `self.status`，节点始终 IDLE。

**修复：** Sequence、ReactiveSequence、Fallback、ActionNode、ConditionNode、AsyncActionNode 以及所有自定义节点的 `execute()` 返回前加上 `self.status = ...`

### 4. 树结构扁平化

**问题：** `_collect_node_statuses()` 只传类名列表，groot2_server 无法生成嵌套 XML。

**修复：** BT driver 新增 `tree_structure` 字段记录嵌套关系，groot2_server 用它生成嵌套 XML。

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `robot_reminder_bt/groot2_server.py` | ZMQ multipart、MessagePack 编码、动态 XML、黑板格式 |
| `robot_reminder_bt/bt_engine.py` | 所有 execute() 方法设置 self.status |
| `robot_reminder_bt/reminder_bt_nodes.py` | 所有自定义节点设置 self.status |
| `robot_reminder_bt/reminder_bt_driver.py` | tree_structure、每 tick 推送状态 |
| `tools/bt_monitor_server.py` | 适配 multipart、实时推送黑板数据 |
| `management/server.py` | SSH 直接推送提醒到话题 |

## 验证方法

### 在板子上

```bash
ss -tlnp | grep 1667        # 确认 groot2_server 运行
ps aux | grep reminder_bt_driver  # 确认 BT driver 运行
```

### 在 PC 上

```python
import zmq, struct, random, msgpack

ctx = zmq.Context()
s = ctx.socket(zmq.REQ)
s.connect("tcp://192.168.1.191:1667")

# 测试黑板数据
hdr = struct.pack("<BBL", 2, ord("B"), random.randint(0, 0xFFFFFFFF))
s.send_multipart([hdr, b""])
reply = s.recv_multipart()  # 应返回 2 帧
data = msgpack.loads(reply[1])
print("ReminderBT keys:", list(data.get("ReminderBT", {}).keys()))
# 应输出: ['pending_count', 'reminder_id', 'tts_text', 'reminder_status', ...]
