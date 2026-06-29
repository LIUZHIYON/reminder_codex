"""
test_bt_local.py — Windows 本地测试行为树（无需 ROS2）

在 Windows 上独立调试行为树逻辑。
通过模拟 HttpClient 来测试树结构、重试、中断等行为。
"""

import sys
import os

# 确保控制台输出 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from robot_reminder_bt.bt_engine import (
    NodeStatus, print_tree, Sequence, ReactiveSequence, Fallback,
    RetryNode, ActionNode, ConditionNode, BehaviorTree
)
from robot_reminder_bt.reminder_nodes import (
    HttpClient, CheckPendingReminder, FetchReminder, GenerateTTS,
    PlayAudio, NotifyWebSocket, MarkTriggered, LogReminder, WaitNode
)
from robot_reminder_bt.reminder_tree import build_reminder_tree


# ══════════════════════════════════════════════════
#  测试 1: 打印树结构
# ══════════════════════════════════════════════════

def test_print_tree():
    """查看行为树结构"""
    print("\n" + "=" * 50)
    print("测试 1: 打印行为树结构")
    print("=" * 50)

    tree = build_reminder_tree(http_client=None)
    print(print_tree(tree.root))


# ══════════════════════════════════════════════════
#  测试 2: 使用真实提醒 API 测试（如果提醒服务正在运行）
# ══════════════════════════════════════════════════

def test_with_real_api():
    """如果 192.168.1.70:5000 提醒系统在运行，做真实测试"""
    import socket

    print("\n" + "=" * 50)
    print("测试 2: 真实 API 测试")
    print("=" * 50)

    # 检查提醒服务是否可达
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("192.168.1.70", 5000))
    sock.close()

    if result != 0:
        print("[WARN] 192.168.1.70:5000 不可达，跳过真实测试")
        return

    client = HttpClient(base_url="http://192.168.1.70:5000")
    stats = client.get_stats()

    if stats:
        pending = stats.get("data", {}).get("pending", 0)
        total = stats.get("data", {}).get("total_reminders", 0)
        print(f"  提醒系统状态: 总计 {total} 条, 待触发 {pending} 条")

        if pending > 0:
            tree = build_reminder_tree(http_client=client)
            print("\n  > 开始 tick 行为树...")
            status = tree.tick_while_running(interval_ms=200, max_ticks=50)
            print(f"\n  > 行为树结果: {status.value}")
        else:
            print("  > 无待触发提醒，跳过")
    else:
        print("  提醒系统连接失败")


# ══════════════════════════════════════════════════
#  测试 3: 模拟提醒（纯本地调试）
# ══════════════════════════════════════════════════

class MockHttpClient:
    """模拟 HTTP 客户端"""
    def __init__(self, pending_count: int = 2):
        self._pending_count = pending_count
        self._triggered = []

    def get_stats(self):
        return {
            "success": True,
            "data": {
                "pending": self._pending_count,
                "triggered": 0,
                "total_reminders": 10,
            }
        }

    def get_pending_reminders(self):
        return [
            {"id": 1001, "content": "小明，该吃药了", "reminder_time": "2026-06-26 12:00:00"},
            {"id": 1002, "content": "小明，记得喝水", "reminder_time": "2026-06-26 13:00:00"},
        ][:self._pending_count]

    def mark_triggered(self, reminder_id):
        self._triggered.append(reminder_id)
        print(f"    [Mock] 标记 {reminder_id} 已触发 OK")
        return True

    def test_tts(self, text):
        print(f'    [Mock] TTS 合成: "{text}"')
        return True


def test_mock_reminder():
    """使用模拟客户端测试完整流程"""
    print("\n" + "=" * 50)
    print("测试 3: 模拟提醒流程")
    print("=" * 50)

    mock = MockHttpClient(pending_count=2)
    tree = build_reminder_tree(http_client=mock)
    tree.blackboard["pending_reminders"] = mock.get_pending_reminders()

    print("\n  > first tick (should process one reminder)...")
    status = tree.tick_while_running(interval_ms=100, max_ticks=30)
    print(f"  > result: {status.value}")

    # 模拟没有新提醒了
    mock._pending_count = 0
    tree.blackboard["pending_reminders"] = []
    print("\n  > second tick (no pending, should be FAILURE)...")
    status = tree.tick_while_running(interval_ms=100, max_ticks=5)
    print(f"  > result: {status.value}")

    assert mock._triggered == [1001], "reminder should be triggered once"
    print("\n  [OK] test passed!")


# ══════════════════════════════════════════════════
#  测试 4: 重试机制测试
# ══════════════════════════════════════════════════

class FlakyWsClient:
    """偶尔失败的 WebSocket 客户端"""
    def __init__(self, fail_count: int = 2):
        self._attempts = 0
        self._fail_count = fail_count

    def send_sync(self, msg):
        self._attempts += 1
        if self._attempts <= self._fail_count:
            print(f"    [模拟] WS 第 {self._attempts} 次失败 X")
            return False
        print(f"    [模拟] WS 第 {self._attempts} 次成功 OK")
        return True


def test_retry_mechanism():
    """测试 Retry 装饰器"""
    print("\n" + "=" * 50)
    print("测试 4: 重试机制测试")
    print("=" * 50)

    mock = MockHttpClient(pending_count=1)
    flaky_ws = FlakyWsClient(fail_count=2)

    tree = build_reminder_tree(http_client=mock, ws_client=flaky_ws)
    tree.blackboard["pending_reminders"] = mock.get_pending_reminders()

    print("\n  > WS 前 2 次失败，应重试 3 次直到成功...")
    status = tree.tick_while_running(interval_ms=100, max_ticks=40)
    print(f"  > result: {status.value}")
    print("  [OK] retry test passed!")


# ══════════════════════════════════════════════════
#  测试 5: 行为树中断/恢复
# ══════════════════════════════════════════════════

def test_halt_and_resume():
    """测试中断后重新开始"""
    print("\n" + "=" * 50)
    print("测试 5: 中断与恢复测试")
    print("=" * 50)

    mock = MockHttpClient(pending_count=10)
    tree = build_reminder_tree(http_client=mock)
    tree.blackboard["pending_reminders"] = mock.get_pending_reminders()

    # 跑 3 个 tick
    for i in range(3):
        tree.tick_once()

    print("\n  > 中断行为树...")
    tree.halt()
    print(f"  > 黑板状态: pending={len(tree.blackboard.get('pending_reminders', []))}")

    print("\n  > 恢复 tick（应从头开始检查）...")
    status = tree.tick_while_running(interval_ms=100, max_ticks=30)
    print(f"  > result: {status.value}")
    print("  [OK] halt/resume test passed!")


# ══════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("提醒行为树 - Windows 本地测试")
    print("=" * 50)

    test_print_tree()
    test_with_real_api()
    test_mock_reminder()
    test_retry_mechanism()
    test_halt_and_resume()

    print("\n" + "=" * 50)
    print("所有测试通过")
    print("=" * 50)
