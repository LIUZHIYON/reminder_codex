"""
reminder_nodes.py — 提醒系统行为树节点定义 (v2 — ROS2话题版)

替换 v1 的 HTTP 调用，改用 ROS2 话题与黑板节点通信：
  - CheckPendingReminder: 查询黑板是否有待处理提醒
  - FetchReminder:       从黑板取提醒 → 发布 TTS 请求
  - GenerateTTS:         发布到 /tts/text (doubao TTS)
  - PlayAudio:           等待 TTS 完成反馈
  - NotifyWebSocket:     发布 command_response 到 /robot/command
  - MarkTriggered:       通知黑板标记完成
  - LogReminder:         记录日志

话题:
  订阅: /reminder/blackboard/state (黑板状态), /reminder/tts/feedback (TTS反馈)
  发布: /reminder/blackboard/action (动作请求), /tts/text (TTS触发), /robot/command (WS通知)
"""

import json, time
from typing import Optional, Dict, Any, List, Callable
from bt_engine import TreeNode, NodeStatus, ActionNode, ConditionNode, AsyncActionNode


# ════════════════════════════════════════
#  ROS2 话题发布辅助 (注入方式)
# ════════════════════════════════════════
# 行为树节点通过黑板变量获取发布函数，不直接依赖 rclpy


class CheckPendingReminder(ConditionNode):
    """Condition: 检查黑板是否有待处理提醒
    
    黑板输入: blackboard_state (dict) — 来自 /reminder/blackboard/state
    黑板输出: pending_count (int)
    """
    def __init__(self, name: str = "有待触发提醒?"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        state = self.get_input("blackboard_state", {})
        pending = state.get("pending_count", 0)
        is_playing = state.get("is_playing", False)
        if pending > 0 and not is_playing:
            self.set_output("pending_count", pending)
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class FetchReminder(ActionNode):
    """Action: 通知黑板取出下一条提醒，等待黑板更新 current_reminder
    
    黑板输入: action_pub (callable) — 发布到 /reminder/blackboard/action
    黑板输出: current_reminder (dict)
    """
    def __init__(self, name: str = "取提醒内容"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        pub = self.get_input("action_pub")
        if pub:
            pub(json.dumps({"action": "fetch_next"}))
        # 等待黑板状态更新 (由 BT tick 循环驱动)
        state = self.get_input("blackboard_state", {})
        current = state.get("current_reminder")
        if current and current.get("title"):
            self.set_output("current_reminder", current)
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class GenerateTTS(ActionNode):
    """Action: 发布 TTS 文本到 /tts/text 话题 (触发 doubao TTS)
    
    黑板输入: current_reminder (dict), tts_pub (callable)
    """
    def __init__(self, name: str = "合成语音"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        text = reminder.get("content", "") or reminder.get("title", "提醒")
        tts_pub = self.get_input("tts_pub")
        if tts_pub:
            tts_pub(text)
        self.set_output("tts_text", text)
        self.set_output("tts_sent_time", time.time())
        return NodeStatus.SUCCESS


class PlayAudio(AsyncActionNode):
    """Action: 等待 TTS 播放完成 (监听 /reminder/tts/feedback)
    
    黑板输入: tts_feedback (dict), tts_sent_time (float)
    超时: 30秒
    """
    def __init__(self, name: str = "播放语音", timeout_s: float = 30.0):
        super().__init__(name)
        self._timeout = timeout_s
        self._start = 0

    def on_start(self) -> NodeStatus:
        self._start = time.time()
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        fb = self.get_input("tts_feedback", {})
        if fb and fb.get("status") == "done":
            return NodeStatus.SUCCESS
        if time.time() - self._start > self._timeout:
            return NodeStatus.FAILURE
        return NodeStatus.RUNNING

    def on_halt(self):
        pass


class NotifyWebSocket(ActionNode):
    """Action: 发布 command_response 到 /robot/command 通知 websocket_node
    
    黑板输入: current_reminder (dict), cmd_pub (callable)
    """
    def __init__(self, name: str = "WebSocket通知"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        pub = self.get_input("cmd_pub")
        notification = {
            "type": "command_response",
            "command_id": reminder.get("command_id", ""),
            "command": "reminder",
            "status": "completed",
            "result": {
                "played": True,
                "title": reminder.get("title", ""),
                "content": reminder.get("content", ""),
                "time": reminder.get("reminder_time", ""),
            },
        }
        if pub:
            pub(json.dumps(notification, ensure_ascii=False))
        return NodeStatus.SUCCESS


class MarkTriggered(ActionNode):
    """Action: 通知黑板标记提醒完成
    
    黑板输入: current_reminder (dict), action_pub (callable)
    """
    def __init__(self, name: str = "标记已完成"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        cid = reminder.get("command_id", "")
        if not cid:
            return NodeStatus.FAILURE
        pub = self.get_input("action_pub")
        if pub:
            pub(json.dumps({"action": "mark_complete", "command_id": cid}))
        return NodeStatus.SUCCESS


class LogReminder(ActionNode):
    """Action: 记录日志"""
    def __init__(self, name: str = "记录日志"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        r = self.get_input("current_reminder", {})
        print(f"[LOG] [{r.get('command_id','')}] {r.get('title','')} — {r.get('content','')}")
        return NodeStatus.SUCCESS


class WaitNode(AsyncActionNode):
    """等待指定毫秒"""
    def __init__(self, name: str = "等待", duration_ms: int = 5000):
        super().__init__(name)
        self._dur = duration_ms / 1000.0
        self._t0 = 0

    def on_start(self) -> NodeStatus:
        self._t0 = time.time()
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        return NodeStatus.SUCCESS if time.time() - self._t0 >= self._dur else NodeStatus.RUNNING

    def on_halt(self):
        pass
