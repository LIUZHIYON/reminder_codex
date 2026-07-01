"""
reminder_tree.py — 构建提醒行为树

通过组合 bt_engine 中的控制节点和 reminder_nodes 中的叶子节点，
构建完整的提醒系统行为树。

行为树结构 (BT.CPP v3 XML 等价定义见 config/trees/):

           ReactiveSequence("提醒主循环")
           ├── Condition("有待触发提醒?")
           └── Sequence("执行提醒")
               ├── Action("取提醒内容")
               ├── RetryUntilSuccessful("TTS合成重试", max=2)
               │   └── Action("合成语音")
               ├── RetryUntilSuccessful("播放重试", max=2)
               │   └── Action("播放语音")
               ├── RetryUntilSuccessful("WS通知重试", max=3)
               │   └── Action("WebSocket通知")
               ├── Action("标记已触发")
               └── Action("记录日志")
"""

from typing import Optional, Dict, Any

from .bt_engine import (
    BehaviorTree, Sequence, ReactiveSequence, Fallback,
    RetryNode, ConditionNode, ActionNode, AsyncActionNode,
    NodeStatus
)
from .reminder_nodes import (
    CheckPendingReminder, FetchReminder, GenerateTTS,
    PlayAudio, NotifyWebSocket, MarkTriggered, LogReminder, WaitNode
)


def build_reminder_tree(
    http_client=None,
    ws_client=None,
    tts_topic_pub=None,
    check_interval_ms: int = 2000,
) -> BehaviorTree:
    """
    构建完整提醒行为树

    参数:
      http_client:    HttpClient 实例（或 None 使用模拟模式）
      ws_client:      WebSocket 客户端实例（或 None）
      tts_topic_pub:  ROS2 Publisher 实例（或 None）
      check_interval_ms: 检查间隔（毫秒）

    返回:
      BehaviorTree 实例
    """

    # ── 黑板（全局数据共享） ──
    blackboard = {
        "http_client": http_client,
        "ws_client": ws_client,
        "tts_topic_pub": tts_topic_pub,
        "pending_reminders": [],
        "current_reminder": {},
    }

    # ── 构建树 ──
    tree = BehaviorTree(
        root=ReactiveSequence("提醒主循环", [
            CheckPendingReminder("有待触发提醒?"),
            Sequence("执行提醒", [
                FetchReminder("取提醒内容"),
                RetryNode("TTS重试", GenerateTTS("合成语音"), max_attempts=2),
                RetryNode("播放重试", PlayAudio("播放语音"), max_attempts=2),
                RetryNode("WS通知重试", NotifyWebSocket("WebSocket通知"), max_attempts=3),
                MarkTriggered("标记已触发"),
                LogReminder("记录日志"),
            ]),
        ]),
        blackboard=blackboard,
        name="reminder_bt",
    )

    return tree


def build_maintenance_tree():
    """
    构建维护模式的行为树（例如：无提醒时做自检）
    可用于 Fallback 的第二个分支
    """
    return Fallback("维护模式", [
        Sequence("健康检查", [
            ActionNode("检查WS连接", lambda: NodeStatus.SUCCESS),
            ActionNode("检查TTS状态", lambda: NodeStatus.SUCCESS),
        ]),
        WaitNode("空闲等待", duration_ms=10000),
    ])


def build_full_tree(http_client=None, ws_client=None, tts_topic_pub=None):
    """
    完整行为树：提醒 + 维护模式

    ReactiveSequence("主循环")
    ├── Sequence 或 Fallback
    │   ├── (提醒子树)
    │   └── (维护子树)
    """
    reminder_subtree = build_reminder_tree(http_client, ws_client, tts_topic_pub)

    full_bb = dict(reminder_subtree.blackboard)

    root = ReactiveSequence("系统主循环", [
        reminder_subtree.root,
        build_maintenance_tree(),
    ])

    return BehaviorTree(root, blackboard=full_bb, name="system_bt")
