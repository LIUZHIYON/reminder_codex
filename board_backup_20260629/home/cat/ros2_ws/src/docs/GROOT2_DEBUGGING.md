# Groot2 可视化调试指南

## 目录
1. [Groot2 是什么](#1-groot2-是什么)
2. [调试架构](#2-调试架构)
3. [方式一：在线调试（连接板子）](#3-方式一在线调试连接板子)
4. [方式二：离线编辑 XML](#4-方式二离线编辑-xml)
5. [方式三：回放日志](#5-方式三回放日志)
6. [BT.CPP 树与 Groot2 对接](#6-btcpp-树与-groot2-对接)
7. [常见问题](#7-常见问题)

---

## 1. Groot2 是什么

Groot2 是 BehaviorTree.CPP 官方的可视化工具，功能：

| 功能 | 说明 |
|------|------|
| **离线编辑** | 在 GUI 中拖拽创建/编辑行为树 XML |
| **在线监控** | 连接运行中的 BT，实时查看节点状态 |
| **断点调试** | 设置断点，单步执行 |
| **日志回放** | 加载 SQLite 日志文件回放历史状态 |
| **节点库管理** | 注册自定义节点类型、输入输出端口 |

## 2. 调试架构

```
┌─────────────────── Windows ──────────────────┐
│                                                │
│   Groot2 (E:\Groot2\bin\groot2.exe)           │
│     │                                          │
│     │ TCP/ZMQ (port 1666)                      │
│     │ WebSocket (port 1667)                    │
│     ▼                                          │
│   [实时监控] [断点调试] [XML编辑] [日志回放]      │
│                                                │
└────────────────────┬───────────────────────────┘
                     │
            网络 (192.168.1.x)
                     │
┌────────────────────▼─────────── 板子 ──────────┐
│                                                │
│   reminder_bt_node (C++ 版)                    │
│     │                                          │
│     ├── BehaviorTree.CPP v3 (3.8.7)            │
│     ├── PublisherZMQ (port 1666) ────→ Groot2  │
│     ├── custom BT nodes                        │
│     └── ROS2 Humble                            │
│                                                │
└────────────────────────────────────────────────┘
```

## 3. 方式一：在线调试（连接板子）

这是最常用的调试方式——板子上跑 BT，Windows 上 Groot2 连上去实时看。

### 步骤

#### 3.1 板子上启动 BT 节点（带 ZMQ Publisher）

```bash
# SSH 到板子
ssh cat@192.168.1.70

# 编译（首次或改代码后）
cd ~/ros2_ws
colcon build --packages-select robot_reminder_bt
source install/setup.bash

# 启动 BT 节点，自动启动 Groot2 ZMQ Publisher（端口 1666）
ros2 run robot_reminder_bt reminder_bt_node \
  --ros-args \
  -p api_url:=http://192.168.1.70:5000 \
  -p groot2_enabled:=true \
  -p groot2_port:=1666
```

你应该看到日志：
```
[INFO] Groot2 ZMQ Publisher 已启动, 端口=1666
```

#### 3.2 Groot2 连接板子

1. 双击 `E:\Groot2\groot2.bat` 启动 Groot2
2. 菜单栏 → **Monitor** → **Connect**（或工具栏插头图标 🔌）
3. 在弹出的对话框：
   - **Host**: `192.168.1.70`
   - **Port**: `1666`
   - **Mode**: `ZMQ`（BT.CPP v3 用 ZMQ；v4 用 WebSocket）
4. 点击 **Connect**

#### 3.3 实时监控

连接成功后你会看到：

- **左面板**：行为树结构，节点**实时着色**
  - 🟢 绿色 = SUCCESS
  - 🔴 红色 = FAILURE
  - 🟡 黄色 = RUNNING
  - ⚪ 灰色 = IDLE（未执行）
- **右面板**：黑板（Blackboard）变量值
- **底部**：日志输出

#### 3.4 断点调试

在 Groot2 中右键点击任意节点 → **Add Breakpoint**：

- **Before tick**：执行前暂停
- **After tick**：执行后暂停

暂停时你可以：
- 查看/修改黑板变量
- 单步执行（Step Over / Step Into）
- 继续执行（Resume）

## 4. 方式二：离线编辑 XML

不用连接板子也能用 Groot2 编辑行为树 XML。

### 步骤

1. 启动 Groot2
2. 点击 **File** → **Open** → 选择项目 XML
   或者新建：**File** → **New BehaviorTree**

3. 在左侧 **Tree Editor** 面板：
   - 拖拽节点类型到画布
   - 双击节点配置参数/端口
   - 用连线连接父子节点
   - 保存为 XML 文件

### 注册自定义节点类型

Groot2 需要知道你的自定义节点有哪些输入/输出端口。
在 Groot2 的 **Node Editor** 中手动注册，或提供一个 **nodes_metadata.xml**：

```xml
<?xml version="1.0"?>
<root BTCPP_format="4">
    <NodeGroups>
        <Group name="reminder">
            <CustomNode name="CheckPendingReminder" category="condition">
                <input_port name="api_url" type="std::string" default="http://localhost:5000"/>
                <output_port name="reminder_list" type="std::string"/>
            </CustomNode>
            <CustomNode name="FetchReminder" category="action">
                <input_port name="reminder_list" type="std::string"/>
                <output_port name="current_reminder" type="std::string"/>
            </CustomNode>
            <CustomNode name="GenerateTTS" category="action">
                <input_port name="reminder" type="std::string"/>
                <input_port name="test_text" type="std::string"/>
            </CustomNode>
            <CustomNode name="PlayAudio" category="action">
                <input_port name="reminder" type="std::string"/>
            </CustomNode>
            <CustomNode name="NotifyWebSocket" category="action">
                <input_port name="reminder" type="std::string"/>
            </CustomNode>
            <CustomNode name="MarkTriggered" category="action">
                <input_port name="reminder" type="std::string"/>
            </CustomNode>
            <CustomNode name="LogReminder" category="action">
                <input_port name="reminder" type="std::string"/>
            </CustomNode>
        </Group>
    </NodeGroups>
</root>
```

在 Groot2 中：**File → Import Node Definitions** → 选择此文件。

之后你的自定义节点就会出现在左侧节点面板中。

### 编辑我们的提醒树

打开 `config/trees/reminder_bt_v3.xml`，你会看到完整的树：

```
ReactiveSequence("reminder_main_loop")
├── CheckPendingReminder("has_pending_reminder")
└── Sequence("execute_reminder")
    ├── FetchReminder("fetch_reminder")
    ├── RetryUntilSuccessful("tts_retry", ×2)
    │   └── GenerateTTS
    ├── RetryUntilSuccessful("play_retry", ×2)
    │   └── PlayAudio
    ├── RetryUntilSuccessful("ws_retry", ×3)
    │   └── NotifyWebSocket
    ├── MarkTriggered
    └── LogReminder
```

你可以用 Groot2 修改它：加新分支、改重试次数、加装饰器等。

## 5. 方式三：回放日志

BT.CPP 支持将运行日志保存为 SQLite 文件，Groot2 可以回放。

### 录制日志

在板子的 C++ 代码中添加文件日志：

```cpp
#include <behaviortree_cpp/loggers/bt_file_logger.h>

// 在创建树后
BT::FileLogger logger(*tree_, "/tmp/bt_reminder_log.btlog");
```

### 在 Groot2 中回放

1. 用 SCP 把日志文件拷贝到 Windows：
   ```bash
   scp cat@192.168.1.70:/tmp/bt_reminder_log.btlog .
   ```

2. Groot2 → **File** → **Open** → 选择 `.btlog` 文件
3. 使用回放控制栏：▶️ ⏸ ⏮ ⏭

## 6. BT.CPP 树与 Groot2 对接

### C++ 代码中的关键改动

```cpp
// reminder_bt_main.cpp 中

#include <behaviortree_cpp_v3/loggers/bt_zmq_publisher.h>

// 创建树后：
tree_ = std::make_unique<BT::Tree>(factory.createTree("ReminderTree"));

// 启动 ZMQ Publisher（端口 1666）
BT::PublisherZMQ publisher(*tree_, 1666);

// 或者用更简洁的方式：
// tree_->enableAutoPublish();  // 默认端口 1666
```

### CMakeLists.txt 需要链接 ZMQ

```cmake
# 已包含在 CMakeLists.txt 中
find_package(cppzmq REQUIRED)
target_link_libraries(reminder_bt_node
  reminder_bt_nodes
  ${behaviortree_cpp_v3_LIBRARIES}
  cppzmq::cppzmq
)
```

### 板子环境确认

| 依赖 | 状态 | 确认方式 |
|------|------|---------|
| BT.CPP v3 | ✅ 3.8.7 | `dpkg -l \| grep behavio` |
| libzmq5 | ✅ 4.3.4 | `dpkg -l \| grep zmq` |
| libzmq3-dev | ✅ 4.3.4 | `dpkg -l \| grep zmq` |
| Groot2 | ✅ 1.9.0 | `E:\Groot2\bin\groot2.exe` |

## 7. 常见问题

### Q: Groot2 连不上板子

**排查：**
```bash
# 板子上检查端口是否在监听
ss -tlnp | grep 1666

# 检查防火墙
sudo ufw status

# 测试从 Windows 到板子的网络
Test-NetConnection -ComputerName 192.168.1.70 -Port 1666
```

### Q: Groot2 连接后看不到节点状态

- 确认 BT 节点已在运行（`ros2 node list` 能看到）
- 确认 ZMQ Publisher 已创建（看启动日志）
- 在 Groot2 中尝试 **Monitor → Reconnect**

### Q: Groot2 显示节点类型未注册

导入节点定义文件（见第 4 节），或在 Groot2 中手动注册。

### Q: 端口冲突

修改端口：
```bash
# 板子端
ros2 run robot_reminder_bt reminder_bt_node \
  --ros-args -p groot2_port:=1667

# Groot2 连接时 Port 填 1667
```

### Q: 板子编译时找不到 cppzmq

```bash
sudo apt install libzmq3-dev
# 并在 CMakeLists.txt 中添加：
find_package(cppzmq REQUIRED)
```

---

## 快速参考卡

| 操作 | 命令/步骤 |
|------|----------|
| 🚀 启动 Groot2 | 双击 `E:\Groot2\groot2.bat` |
| 🔌 连接板子 | Monitor → Connect → `192.168.1.70:1666` (ZMQ) |
| 📝 编辑 XML | File → Open → `reminder_bt_v3.xml` |
| 📦 导入自定义节点 | File → Import Node Definitions → `nodes_metadata.xml` |
| 🐛 设断点 | 右键节点 → Add Breakpoint |
| 📋 打开黑板 | Monitor → Show Blackboard |
| 🎬 日志回放 | File → Open → `.btlog` 文件 |
| 🖥 板子启动 | `ros2 run robot_reminder_bt reminder_bt_node` |
