# -*- coding: utf-8 -*-
"""
reminder_bt_nodes — 提醒系统行为树节点
所有节点通过共享黑板通信。

黑板键:
  reminder_id, reminder_title, reminder_content, reminder_time
  reminder_status, is_repeating, repeat_type, tts_text
  pending_reminders, current_reminder
"""

import json, os, time, threading, subprocess, tempfile
from datetime import datetime, timedelta
from bt_engine import TreeNode, NodeStatus, ActionNode, ConditionNode, AsyncActionNode


class CheckNewReminder(ConditionNode):
    """检查是否有pending/received状态的新提醒"""
    def __init__(self, name="CheckNewReminder"): super().__init__(name)
    def execute(self) -> NodeStatus:
        rems = self.get_input("pending_reminders", [])
        for r in rems:
            if r.get("status") in ("pending", "received", "executing"):
                self.set_output("current_reminder", r)
                for k in ("command_id", "title", "content", "reminder_time",
                          "is_repeating", "repeat_type"):
                    if k == "command_id":
                        key = "reminder_id"
                    elif k.startswith("reminder_"):
                        key = k
                    else:
                        key = f"reminder_{k}"
                    self.set_output(key, r.get(k, ""))
                self.status = NodeStatus.SUCCESS
                return self.status
        self.status = NodeStatus.FAILURE
        return self.status


class CheckTimeCondition(ConditionNode):
    """检查提醒是否到时间"""
    def __init__(self, name="CheckTime"): super().__init__(name)
    def execute(self) -> NodeStatus:
        ts = self.get_input("reminder_time", "")
        if not ts: return NodeStatus.FAILURE
        try:
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
            self.status = NodeStatus.SUCCESS if datetime.now() >= dt else NodeStatus.FAILURE
            return self.status
        except: return NodeStatus.FAILURE


class CheckRepeating(ConditionNode):
    def __init__(self, name="CheckRepeating"): super().__init__(name)
    def execute(self) -> NodeStatus:
        self.status = NodeStatus.SUCCESS if self.get_input("is_repeating", False) else NodeStatus.FAILURE
        return self.status


class MarkExecuting(ActionNode):
    def __init__(self, name="MarkExecuting"): super().__init__(name)
    def execute(self) -> NodeStatus:
        rid = self.get_input("reminder_id","")
        for r in self.get_input("pending_reminders",[]):
            if r.get("command_id")==rid: r["status"]="executing"; r["executing_at"]=datetime.now().isoformat(); break
        self.set_output("reminder_status","executing")
        self.status = NodeStatus.SUCCESS
        return self.status


class BuildTtsText(ActionNode):
    def __init__(self, name="BuildTtsText"): super().__init__(name)
    def execute(self) -> NodeStatus:
        t = self.get_input("reminder_title","reminder")
        c = self.get_input("reminder_content","")
        txt = f"叮咚,提醒时间到啦,{t}"
        if c: txt += f",{c}"
        txt += ",别忘了哦!"
        self.set_output("tts_text", txt)
        self.status = NodeStatus.SUCCESS
        return self.status


class GenerateTTS(AsyncActionNode):
    """调用 voice_bridge Action /voice/speak 合成语音（ROS2 Action直调）"""
    def __init__(self, name="GenerateTTS"):
        super().__init__(name); self._t=None; self._ok=False

    def on_start(self) -> NodeStatus:
        text = self.get_input("tts_text", "reminder")
        self._ok = False
        with open("/tmp/tts_debug.log", "a") as f:
            f.write("[on_start] tts_text={}\n".format(text))
        self._t = threading.Thread(target=self._run_tts, args=(text,), daemon=True)
        self._t.start()
        return NodeStatus.RUNNING

    def _run_tts(self, text):
        import subprocess, tempfile, os, datetime, traceback
        log = open("/tmp/tts_debug.log", "a")
        log.write("\n[{}] _run_tts START: {}\n".format(datetime.datetime.now(), text))
        log.flush()
        fp = None
        try:
            safe_text = text.replace(chr(34), chr(39))
            lines = ["#!/bin/bash", "source /opt/ros/humble/setup.bash"]
            cmd = 'ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak'
            yaml_val = "'{text: \"%s\"}'" % safe_text
            lines.append("{} {}".format(cmd, yaml_val))
            scr = "\n".join(lines)
            fp = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8")
            fp.write(scr)
            fp.close()
            os.chmod(fp.name, 0o755)
            log.write("[{}] Script: {}\n".format(datetime.datetime.now(), fp.name))
            log.write("[{}] Content: {}\n".format(datetime.datetime.now(), scr))
            log.flush()
            r = subprocess.run(["timeout", "35", fp.name], capture_output=True, text=True, timeout=40)
            self._ok = (r.returncode == 0 or "Goal accepted" in r.stdout)
            log.write("[{}] RC={} stdout={}\n".format(datetime.datetime.now(), r.returncode, r.stdout[:150]))
            log.flush()
        except Exception as e:
            traceback.print_exc(file=log)
            log.write("[{}] EXCEPTION: {}\n".format(datetime.datetime.now(), e))
            log.flush()
            self._ok = False
        finally:
            if fp is not None:
                try: os.unlink(fp.name)
                except: pass
            log.write("[{}] _run_tts END\n".format(datetime.datetime.now()))
            log.flush()
            log.close()

    def on_tick(self) -> NodeStatus:
        if self._t is None:
            self.status = NodeStatus.FAILURE; return self.status
        if self._t.is_alive():
            self.status = NodeStatus.RUNNING; return self.status
        self.status = NodeStatus.SUCCESS if self._ok else NodeStatus.FAILURE
        return self.status

class RescheduleRepeating(ActionNode):
    def __init__(self, name="RescheduleRepeating"): super().__init__(name)
    def execute(self) -> NodeStatus:
        rid=self.get_input("reminder_id",""); rt=self.get_input("repeat_type","")
        dm={"daily":1,"weekly":7,"monthly":30}
        if rt not in dm: return NodeStatus.SUCCESS
        try:
            dt=datetime.fromisoformat(self.get_input("reminder_time","").replace("Z","+00:00"))
            nt=(dt+timedelta(days=dm[rt])).isoformat()
            for r in self.get_input("pending_reminders",[]):
                if r.get("command_id")==rid: r["reminder_time"]=nt; r["status"]="pending"; break
        except:
            self.status = NodeStatus.FAILURE
            return self.status
        self.status = NodeStatus.SUCCESS
        return self.status


class PublishStatus(ActionNode):
    """发布提醒结果到 /robot/command_response 并清理"""
    def __init__(self, name="PublishStatus"): super().__init__(name); self._pub=None; self._ok=True
    def set_publisher(self, pub): self._pub=pub
    def execute(self) -> NodeStatus:
        if not self._pub: return NodeStatus.SUCCESS
        rid = self.get_input("reminder_id", self.get_input("command_id", ""))
        if not rid:
            r = self.get_input("current_reminder", {})
            rid = r.get("command_id", "")
        # Mark as completed/failed in pending_reminders
        rems = self.get_input("pending_reminders", [])
        for rm in rems:
            if rm.get("command_id") == rid:
                rm["status"] = "completed" if self._ok else "failed"
                rm["completed_at"] = datetime.now().isoformat()
                break
        self.set_output("reminder_status", "completed" if self._ok else "failed")
        if self._ok:
            c = self.get_input("completed_count", 0) + 1
            self.set_output("completed_count", c)
        else:
            f = self.get_input("failed_count", 0) + 1
            self.set_output("failed_count", f)
        from std_msgs.msg import String
        msg=String()
        msg.data=json.dumps({"type":"command_response","command_id":rid,
                             "command":"reminder","status":"success" if self._ok else "failed",
                             "result":{"played":self._ok}},ensure_ascii=False)
        self._pub.publish(msg)
        self.status = NodeStatus.SUCCESS
        return self.status
