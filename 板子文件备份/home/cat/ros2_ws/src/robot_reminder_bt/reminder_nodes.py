"""
reminder_nodes.py — 提醒系统行为树节点定义

定义所有自定义 BT 节点（Action / Condition）：
  - CheckPendingReminder: 检查是否有待触发提醒
  - FetchReminder:       获取提醒内容
  - GenerateTTS:         合成语音
  - PlayAudio:           播放音频
  - NotifyWebSocket:     WebSocket 通知服务器
  - MarkTriggered:       标记已执行
  - LogReminder:         记录日志
"""

import json
import time
from typing import Optional, Dict, Any

from .bt_engine import (
    TreeNode, NodeStatus, ActionNode, ConditionNode, AsyncActionNode
)


# ══════════════════════════════════════════════════
#  HTTP 客户端（调用提醒后端 API）
# ══════════════════════════════════════════════════

class HttpClient:
    """封装对提醒系统后端的 HTTP 调用"""

    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_stats(self) -> Optional[Dict]:
        """获取系统统计（pending 数量）"""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/stats", timeout=self.timeout)
            data = resp.json()
            return data if data.get("success") else None
        except Exception as e:
            print(f"[HttpClient] get_stats 失败: {e}")
            return None

    def get_pending_reminders(self) -> list:
        """获取所有待触发提醒"""
        try:
            import requests
            resp = requests.get(
                f"{self.base_url}/api/reminders?status=pending",
                timeout=self.timeout
            )
            data = resp.json()
            return data.get("data", []) if data.get("success") else []
        except Exception as e:
            print(f"[HttpClient] get_pending_reminders 失败: {e}")
            return []

    def mark_triggered(self, reminder_id: int) -> bool:
        """标记提醒已触发"""
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/api/reminders/{reminder_id}/trigger",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return True
            data = resp.json()
            return data.get("success", False)
        except Exception as e:
            print(f"[HttpClient] mark_triggered({reminder_id}) 失败: {e}")
            return False

    def test_tts(self, text: str) -> bool:
        """调用板子 TTS 测试接口"""
        import urllib.parse
        try:
            import requests
            url = f"{self.base_url}/api/test-tts?text={urllib.parse.quote(text)}"
            resp = requests.get(url, timeout=10)
            return resp.json().get("success", False)
        except Exception as e:
            print(f"[HttpClient] test_tts 失败: {e}")
            return False

    def play_audio(self, audio_file: str) -> bool:
        """播放指定音频文件"""
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/api/audio/play",
                json={"file": audio_file},
                timeout=10
            )
            return resp.json().get("success", False)
        except Exception as e:
            print(f"[HttpClient] play_audio 失败: {e}")
            return False


# ══════════════════════════════════════════════════
#  行为树节点（可在 Windows 上独立调试）
# ══════════════════════════════════════════════════

class CheckPendingReminder(ConditionNode):
    """
    Condition: 检查是否有待触发提醒

    输入黑板变量:
      - http_client: HttpClient 实例
      - pending_reminders: list (输出)
    """
    def __init__(self, name: str = "有待触发提醒?"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        client: HttpClient = self.get_input("http_client")
        if not client:
            print(f"[{self.name}] http_client 未配置")
            return NodeStatus.FAILURE

        stats = client.get_stats()
        if stats and stats.get("data", {}).get("pending", 0) > 0:
            reminders = client.get_pending_reminders()
            self.set_output("pending_reminders", reminders)
            print(f"[{self.name}] ✅ 发现 {len(reminders)} 条待处理提醒")
            return NodeStatus.SUCCESS

        # print(f"[{self.name}] ❌ 无待处理提醒")
        return NodeStatus.FAILURE


class FetchReminder(ActionNode):
    """
    Action: 从队列取第一条提醒

    输入黑板变量:  pending_reminders: list
    输出黑板变量:  current_reminder: dict
    """
    def __init__(self, name: str = "取提醒内容"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminders = self.get_input("pending_reminders", [])
        if not reminders:
            print(f"[{self.name}] ❌ 提醒队列为空")
            return NodeStatus.FAILURE

        reminder = reminders.pop(0)
        self.set_output("current_reminder", reminder)
        self.set_output("pending_reminders", reminders)
        print(f"[{self.name}] ✅ 提醒: [{reminder.get('id')}] {reminder.get('content', '')}")
        return NodeStatus.SUCCESS


class GenerateTTS(AsyncActionNode):
    """
    Action: 生成 TTS 语音

    输入黑板变量:
      - current_reminder: dict
      - http_client: HttpClient (可选)
      - tts_topic_pub: ROS2 Publisher (可选)
    """
    def __init__(self, name: str = "合成语音"):
        super().__init__(name)
        self._text = ""
        self._start_time = 0

    def on_start(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        self._text = reminder.get("content", "您有一条新提醒")
        print(f"[{self.name}] ▶ 开始合成: 「{self._text}」")

        # 方式 A: 通过 ROS2 话题发送（如果节点已注入）
        pub = self.get_input("tts_topic_pub")
        if pub:
            pub.publish(self._text)
            self._start_time = time.time()
            return NodeStatus.SUCCESS

        # 方式 B: 通过 HTTP 调用测试接口
        client: HttpClient = self.get_input("http_client")
        if client:
            ok = client.test_tts(self._text)
            self._start_time = time.time()
            if ok:
                return NodeStatus.SUCCESS
            print(f"[{self.name}] HTTP TTS 失败，改用模拟模式")

        # 方式 C: 模拟合成（Windows 调试）
        print(f"[{self.name}] [模拟] 合成语音: 「{self._text}」 (~{len(self._text)*50}ms)")
        self._start_time = time.time()
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        elapsed = (time.time() - self._start_time) * 1000
        # 模拟合成耗时约 50ms/字
        expected_ms = max(200, len(self._text) * 50)
        if elapsed >= expected_ms:
            print(f"[{self.name}] ✅ 合成完成 ({expected_ms:.0f}ms)")
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def on_halt(self):
        print(f"[{self.name}] ⛔ 合成被中断")


class PlayAudio(AsyncActionNode):
    """
    Action: 播放语音

    输入黑板变量:
      - current_reminder: dict
      - http_client: HttpClient (可选)
    """
    def __init__(self, name: str = "播放语音"):
        super().__init__(name)
        self._play_start = 0
        self._duration_ms = 1000  # 模拟播放时长(ms)

    def on_start(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        text = reminder.get("content", "")
        self._duration_ms = max(800, len(text) * 80)  # ~80ms/字

        print(f"[{self.name}] ▶ 开始播放: 「{text}」")
        self._play_start = time.time()
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        elapsed = (time.time() - self._play_start) * 1000
        if elapsed >= self._duration_ms:
            print(f"[{self.name}] ✅ 播放完成 ({self._duration_ms:.0f}ms)")
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def on_halt(self):
        print(f"[{self.name}] ⛔ 播放被中断")


class NotifyWebSocket(ActionNode):
    """
    Action: 通过 WebSocket 通知服务器

    输入黑板变量:
      - current_reminder: dict
      - ws_client: WebSocket 客户端实例 (可选)
    """
    def __init__(self, name: str = "WebSocket通知"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        ws = self.get_input("ws_client")

        notification = {
            "type": "command_response",
            "command": "reminder",
            "status": "success",
            "result": {
                "played": True,
                "title": reminder.get("content", ""),
                "id": reminder.get("id", 0),
                "time": reminder.get("reminder_time", ""),
            },
        }
        print(f"[{self.name}] 📤 发送通知: {json.dumps(notification, ensure_ascii=False)}")

        if ws:
            ok = ws.send_sync(notification)
            if ok:
                return NodeStatus.SUCCESS
            print(f"[{self.name}] ⚠ WebSocket 发送失败")
            return NodeStatus.FAILURE

        # 模拟（Windows 调试）
        print(f"[{self.name}] [模拟] WebSocket 通知已发送")
        return NodeStatus.SUCCESS


class MarkTriggered(ActionNode):
    """
    Action: 标记提醒已触发

    输入黑板变量:
      - current_reminder: dict
      - http_client: HttpClient
    """
    def __init__(self, name: str = "标记已触发"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        reminder_id = reminder.get("id")
        if not reminder_id:
            print(f"[{self.name}] ❌ 无提醒 ID")
            return NodeStatus.FAILURE

        client: HttpClient = self.get_input("http_client")
        if client:
            ok = client.mark_triggered(reminder_id)
            if ok:
                print(f"[{self.name}] ✅ 已标记 [{reminder_id}] 为触发")
                return NodeStatus.SUCCESS
            print(f"[{self.name}] ❌ 标记失败")
            return NodeStatus.FAILURE

        # 模拟
        print(f"[{self.name}] [模拟] 已标记 [{reminder_id}] 为已触发")
        return NodeStatus.SUCCESS


class LogReminder(ActionNode):
    """Action: 记录播报日志"""
    def __init__(self, name: str = "记录日志"):
        super().__init__(name)

    def execute(self) -> NodeStatus:
        reminder = self.get_input("current_reminder", {})
        print(f"[{self.name}] 📝 日志: [{reminder.get('id')}] {reminder.get('content', '')}")
        return NodeStatus.SUCCESS


class WaitNode(AsyncActionNode):
    """Action: 等待指定时间（毫秒）"""
    def __init__(self, name: str = "等待", duration_ms: int = 5000):
        super().__init__(name)
        self._duration_ms = duration_ms
        self._start = 0

    def on_start(self) -> NodeStatus:
        self._start = time.time()
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        elapsed = (time.time() - self._start) * 1000
        if elapsed >= self._duration_ms:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def on_halt(self):
        pass
