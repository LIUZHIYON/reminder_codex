"""
reminder_tree_v2.py — v2 行为树构建 (话题通信版)

行为树结构:
    ReactiveSequence("提醒主循环")
    ├── CheckPendingReminder    ← 查 blackboard["blackboard_state"]["pending_count"]
    └── Sequence("执行提醒")
        ├── FetchReminder        ← 发 action_pub({"action":"fetch_next"})
        ├── GenerateTTS          ← 调 tts_pub(text)
        ├── PlayAudio            ← 查 blackboard["tts_feedback"]["status"]=="done"
        ├── NotifyWebSocket      ← 调 cmd_pub(command_response_json)
        ├── MarkTriggered        ← 发 action_pub({"action":"mark_complete",...})
        └── LogReminder          ← 日志
"""

from bt_engine import BehaviorTree, Sequence, ReactiveSequence
from reminder_nodes_v2 import (
    CheckPendingReminder, FetchReminder, GenerateTTS,
    PlayAudio, NotifyWebSocket, MarkTriggered, LogReminder
)


def build_reminder_tree_v2(blackboard: dict = None) -> BehaviorTree:
    """构建 v2 行为树"""

    if blackboard is None:
        blackboard = {}

    # 确保必要键存在
    blackboard.setdefault("blackboard_state", {})
    blackboard.setdefault("tts_feedback", {})
    blackboard.setdefault("current_reminder", {})
    blackboard.setdefault("tts_pub", None)
    blackboard.setdefault("cmd_pub", None)
    blackboard.setdefault("action_pub", None)
    blackboard.setdefault("pending_count", 0)
    blackboard.setdefault("tts_text", "")
    blackboard.setdefault("tts_sent_time", 0)

    tree = BehaviorTree(
        root=ReactiveSequence("提醒主循环", [
            CheckPendingReminder("有待触发提醒?"),
            Sequence("执行提醒", [
                FetchReminder("取提醒内容"),
                GenerateTTS("合成语音"),
                PlayAudio("播放语音", timeout_s=30.0),
                NotifyWebSocket("WebSocket通知"),
                MarkTriggered("标记已完成"),
                LogReminder("记录日志"),
            ]),
        ]),
        blackboard=blackboard,
        name="reminder_bt_v2",
    )
    return tree
