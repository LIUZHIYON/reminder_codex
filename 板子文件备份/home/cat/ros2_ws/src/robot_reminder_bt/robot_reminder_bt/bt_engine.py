"""
robot_reminder_bt — 提醒系统行为树引擎

轻量 Python 行为树引擎，零外部依赖。
接口兼容 BT.CPP v3/v4 风格，可在 Windows 上直接调试。
"""

from enum import Enum
from typing import List, Optional, Callable, Any, Dict
import time


class NodeStatus(Enum):
    """行为树节点状态（兼容 BT.CPP）"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    SKIPPED = "SKIPPED"


# ────────────── 节点基类 ──────────────

class TreeNode:
    """行为树节点基类（兼容 BT.CPP TreeNode）"""
    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self._children: List[TreeNode] = []
        self._blackboard: Optional[Dict] = None
        self.status = NodeStatus.IDLE

    def set_blackboard(self, bb: Dict):
        self._blackboard = bb

    def get_input(self, key: str, default=None):
        """从黑板或配置读取输入端口"""
        if self._blackboard and key in self._blackboard:
            return self._blackboard[key]
        return self.config.get(key, default)

    def set_output(self, key: str, value: Any):
        """写入黑板"""
        if self._blackboard is not None:
            self._blackboard[key] = value

    def halt(self):
        """中断当前节点（BT.CPP 兼容）"""
        self.status = NodeStatus.IDLE

    def execute(self) -> NodeStatus:
        raise NotImplementedError


class LeafNode(TreeNode):
    """叶子节点基类"""
    def add_child(self, child: TreeNode) -> 'LeafNode':
        raise RuntimeError(f"LeafNode '{self.name}' cannot have children")


# ────────────── 控制节点 ──────────────

class Sequence(TreeNode):
    """Sequence: 从左到右依次执行，全成功才成功
    等价于 BT.CPP 的 Sequence (memory=true)
    """
    def __init__(self, name: str, children: Optional[List[TreeNode]] = None):
        super().__init__(name)
        if children:
            self._children = children
        self._running_child = 0

    def add_child(self, child: TreeNode) -> 'Sequence':
        self._children.append(child)
        return self

    def execute(self) -> NodeStatus:
        while self._running_child < len(self._children):
            child = self._children[self._running_child]
            status = child.execute()
            if status == NodeStatus.FAILURE:
                self._running_child = 0
                self.status = NodeStatus.FAILURE
                return self.status
            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
                return self.status
            self._running_child += 1
        self._running_child = 0
        self.status = NodeStatus.SUCCESS
        return self.status

    def halt(self):
        self._running_child = 0
        for child in self._children:
            child.halt()
        super().halt()


class ReactiveSequence(TreeNode):
    """ReactiveSequence: 每次 tick 都重新执行所有前置条件
    等价于 BT.CPP 的 ReactiveSequence
    """
    def __init__(self, name: str, children: Optional[List[TreeNode]] = None):
        super().__init__(name)
        if children:
            self._children = children
        self._running_child = 0

    def add_child(self, child: TreeNode) -> 'ReactiveSequence':
        self._children.append(child)
        return self

    def execute(self) -> NodeStatus:
        # 每次 tick 都从第一个节点开始重新检查
        for i, child in enumerate(self._children):
            if i < self._running_child:
                # 如果之前的条件现在失败了，重新开始
                status = child.execute()
                if status == NodeStatus.FAILURE:
                    self._running_child = 0
                    self.status = NodeStatus.FAILURE
                    return self.status
                if status == NodeStatus.RUNNING:
                    self.status = NodeStatus.RUNNING
                    return self.status
                continue

            status = child.execute()
            if status == NodeStatus.FAILURE:
                self._running_child = 0
                self.status = NodeStatus.FAILURE
                return self.status
            if status == NodeStatus.RUNNING:
                self._running_child = i
                self.status = NodeStatus.RUNNING
                return self.status
        self._running_child = 0
        self.status = NodeStatus.SUCCESS
        return self.status

    def halt(self):
        self._running_child = 0
        for child in self._children:
            child.halt()
        super().halt()


class Fallback(TreeNode):
    """Fallback/Selector: 从左到右尝试，成功则停
    等价于 BT.CPP 的 Fallback (memory=true)
    """
    def __init__(self, name: str, children: Optional[List[TreeNode]] = None):
        super().__init__(name)
        if children:
            self._children = children
        self._running_child = 0

    def add_child(self, child: TreeNode) -> 'Fallback':
        self._children.append(child)
        return self

    def execute(self) -> NodeStatus:
        while self._running_child < len(self._children):
            child = self._children[self._running_child]
            status = child.execute()
            if status == NodeStatus.SUCCESS:
                self._running_child = 0
                self.status = NodeStatus.SUCCESS
                return self.status
            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
                return self.status
            self._running_child += 1
        self._running_child = 0
        self.status = NodeStatus.FAILURE
        return self.status

    def halt(self):
        self._running_child = 0
        for child in self._children:
            child.halt()
        super().halt()


# ────────────── 装饰器节点 ──────────────

class RetryNode(TreeNode):
    """RetryUntilSuccessful: 失败重试指定次数
    等价于 BT.CPP 的 RetryUntilSuccessful
    """
    def __init__(self, name: str, child: TreeNode, max_attempts: int = 3):
        super().__init__(name)
        self._child = child
        self._max_attempts = max_attempts
        self._attempts = 0

    def add_child(self, child: TreeNode) -> 'RetryNode':
        self._child = child
        return self

    def execute(self) -> NodeStatus:
        while self._attempts < self._max_attempts:
            status = self._child.execute()
            if status == NodeStatus.SUCCESS:
                self._attempts = 0
                return NodeStatus.SUCCESS
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            self._attempts += 1
            print(f"[Retry] '{self.name}' 第 {self._attempts}/{self._max_attempts} 次重试")
        self._attempts = 0
        return NodeStatus.FAILURE

    def halt(self):
        self._attempts = 0
        self._child.halt()
        super().halt()


class InverterNode(TreeNode):
    """Inverter: 取反子节点状态
    等价于 BT.CPP 的 Inverter
    """
    def __init__(self, name: str, child: TreeNode):
        super().__init__(name)
        self._child = child

    def add_child(self, child: TreeNode) -> 'InverterNode':
        self._child = child
        return self

    def execute(self) -> NodeStatus:
        status = self._child.execute()
        if status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        if status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


class DelayNode(TreeNode):
    """Delay: 执行前等待指定时间
    等价于 BT.CPP 的 Delay
    """
    def __init__(self, name: str, child: TreeNode, delay_ms: int = 100):
        super().__init__(name)
        self._child = child
        self._delay_ms = delay_ms
        self._wait_start = None

    def add_child(self, child: TreeNode) -> 'DelayNode':
        self._child = child
        return self

    def execute(self) -> NodeStatus:
        if self._wait_start is None:
            self._wait_start = time.time()
            return NodeStatus.RUNNING
        if (time.time() - self._wait_start) * 1000 < self._delay_ms:
            return NodeStatus.RUNNING
        self._wait_start = None
        return self._child.execute()

    def halt(self):
        self._wait_start = None
        self._child.halt()
        super().halt()


# ────────────── 叶子节点（用户可继承） ──────────────

class ActionNode(LeafNode):
    """动作节点：执行操作并返回状态
    等价于 BT.CPP 的 SyncActionNode
    """
    def __init__(self, name: str, fn: Optional[Callable[[], NodeStatus]] = None):
        super().__init__(name)
        self._fn = fn

    def execute(self) -> NodeStatus:
        if self._fn:
            self.status = self._fn()
            return self.status
        self.status = NodeStatus.SUCCESS
        return self.status


class ConditionNode(LeafNode):
    """条件节点：检查条件
    等价于 BT.CPP 的 ConditionNode
    """
    def __init__(self, name: str, fn: Optional[Callable[[], bool]] = None):
        super().__init__(name)
        self._fn = fn

    def execute(self) -> NodeStatus:
        if self._fn:
            self.status = NodeStatus.SUCCESS if self._fn() else NodeStatus.FAILURE
            return self.status
        self.status = NodeStatus.FAILURE
        return self.status


class AsyncActionNode(LeafNode):
    """异步动作节点：需要多次 tick 才能完成
    等价于 BT.CPP 的 AsyncActionNode / StatefulActionNode

    子类需实现:
      - on_start() -> NodeStatus: 开始动作
      - on_tick() -> NodeStatus:  每次 tick 更新进度
      - on_halt():                中断时清理
    """
    def __init__(self, name: str):
        super().__init__(name)
        self._started = False

    def on_start(self) -> NodeStatus:
        return NodeStatus.SUCCESS

    def on_tick(self) -> NodeStatus:
        return NodeStatus.SUCCESS

    def on_halt(self):
        pass

    def execute(self) -> NodeStatus:
        if not self._started:
            self._started = True
            self.status = self.on_start()
            if self.status != NodeStatus.SUCCESS:
                return self.status
        self.status = self.on_tick()
        return self.status

    def halt(self):
        self._started = False
        self.on_halt()
        super().halt()


# ────────────── 行为树 ──────────────

class BehaviorTree:
    """行为树主类"""
    def __init__(self, root: TreeNode, blackboard: Optional[Dict] = None, name: str = "root"):
        self.root = root
        self.name = name
        self.blackboard = blackboard or {}
        self._set_blackboard(root)

    def _set_blackboard(self, node: TreeNode):
        node.set_blackboard(self.blackboard)
        for child in getattr(node, '_children', []):
            self._set_blackboard(child)

    def tick_once(self) -> NodeStatus:
        """单次 tick，返回根节点执行状态"""
        return self.root.execute()

    def tick_while_running(self, interval_ms: int = 100, max_ticks: int = 0) -> NodeStatus:
        """持续 tick 直到返回 SUCCESS 或 FAILURE"""
        status = NodeStatus.IDLE
        ticks = 0
        while status not in (NodeStatus.SUCCESS, NodeStatus.FAILURE):
            status = self.root.execute()
            ticks += 1
            if max_ticks and ticks >= max_ticks:
                break
            if status == NodeStatus.RUNNING:
                time.sleep(interval_ms / 1000.0)
        return status

    def halt(self):
        """中断整棵树"""
        self.root.halt()


# ────────────── 可视化 ──────────────

def print_tree(node: TreeNode, indent: str = "", is_last: bool = True) -> str:
    """打印行为树结构"""
    prefix = indent + ("└── " if is_last else "├── ")
    status_icon = {
        NodeStatus.SUCCESS: "✅",
        NodeStatus.FAILURE: "❌",
        NodeStatus.RUNNING: "⏳",
        NodeStatus.IDLE: "○",
    }.get(node.status, "○")

    cls_name = type(node).__name__
    out = f"{prefix}{status_icon} {cls_name}({node.name})\n"

    indent += "    " if is_last else "│   "
    children = getattr(node, '_children', [])
    for i, child in enumerate(children):
        out += print_tree(child, indent, i == len(children) - 1)

    return out
