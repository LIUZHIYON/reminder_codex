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
            if r.get("status") in ("pending", "received"):
                self.set_output("current_reminder", r)
                for k in ("command_id", "title", "content", "reminder_time",
                          "is_repeating", "repeat_type"):
                    self.set_output(f"reminder_id" if k=="command_id" else k, r.get(k, ""))
                return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class CheckTimeCondition(ConditionNode):
    """检查提醒是否到时间"""
    def __init__(self, name="CheckTime"): super().__init__(name)
    def execute(self) -> NodeStatus:
        ts = self.get_input("reminder_time", "")
        if not ts: return NodeStatus.FAILURE
        try:
            dt = datetime.fromisoformat(ts.replace("Z","+00:00").replace("T"," "))
            return NodeStatus.SUCCESS if datetime.now() >= dt else NodeStatus.FAILURE
        except: return NodeStatus.FAILURE


class CheckRepeating(ConditionNode):
    def __init__(self, name="CheckRepeating"): super().__init__(name)
    def execute(self) -> NodeStatus:
        return NodeStatus.SUCCESS if self.get_input("is_repeating", False) else NodeStatus.FAILURE


class MarkExecuting(ActionNode):
    def __init__(self, name="MarkExecuting"): super().__init__(name)
    def execute(self) -> NodeStatus:
        rid = self.get_input("reminder_id","")
        for r in self.get_input("pending_reminders",[]):
            if r.get("command_id")==rid: r["status"]="executing"; r["executing_at"]=datetime.now().isoformat(); break
        self.set_output("reminder_status","executing")
        return NodeStatus.SUCCESS


class BuildTtsText(ActionNode):
    def __init__(self, name="BuildTtsText"): super().__init__(name)
    def execute(self) -> NodeStatus:
        t = self.get_input("reminder_title","reminder")
        c = self.get_input("reminder_content","")
        txt = f"叮咚,提醒时间到啦,{t}"
        if c: txt += f",{c}"
        txt += ",别忘了哦!"
        self.set_output("tts_text", txt)
        return NodeStatus.SUCCESS


class GenerateTTS(AsyncActionNode):
    """调用 voice_bridge Action 合成语音"""
    def __init__(self, name="GenerateTTS"):
        super().__init__(name); self._t=None; self._ok=False
    def on_start(self) -> NodeStatus:
        text=self.get_input("tts_text","reminder"); self._ok=False
        self._t=threading.Thread(target=self._run, args=(text,), daemon=True); self._t.start()
        return NodeStatus.RUNNING
    def _run(self, text):
        try:
            safe=text.replace('"',"'")
            scr=f"#!/bin/bash\nsource /opt/ros/humble/setup.bash\nsource ~/ros2_ws/install/setup.bash 2>/dev/null\ntimeout 30 ros2 action send_goal /voice/speak robot_voice_bridge/action/Speak '{{text: \"{safe}\"}}' 2>/dev/null\n"
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write(scr); sp=f.name
            os.chmod(sp,0o755)
            r=subprocess.run(["timeout","35",sp],timeout=40,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            os.unlink(sp); self._ok=(r.returncode==0)
        except Exception as e: print(f"[BT-TTS] {e}"); self._ok=False
    def on_tick(self) -> NodeStatus:
        return NodeStatus.RUNNING if (self._t and self._t.is_alive()) else (NodeStatus.SUCCESS if self._ok else NodeStatus.FAILURE)
    def on_halt(self): self._ok=False




class RescheduleRepeating(ActionNode):
    def __init__(self, name="RescheduleRepeating"): super().__init__(name)
    def execute(self) -> NodeStatus:
        rid=self.get_input("reminder_id",""); rt=self.get_input("repeat_type","")
        dm={"daily":1,"weekly":7,"monthly":30}
        if rt not in dm: return NodeStatus.SUCCESS
        try:
            dt=datetime.fromisoformat(self.get_input("reminder_time","").replace("Z","+00:00").replace("T"," "))
            nt=(dt+timedelta(days=dm[rt])).isoformat()
            for r in self.get_input("pending_reminders",[]):
                if r.get("command_id")==rid: r["reminder_time"]=nt; r["status"]="pending"; break
        except: return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class PublishStatus(ActionNode):
    """发布提醒结果到 /robot/command_response"""
    def __init__(self, name="PublishStatus"): super().__init__(name); self._pub=None
    def set_publisher(self, pub): self._pub=pub
    def execute(self) -> NodeStatus:
        if not self._pub: return NodeStatus.SUCCESS
        from std_msgs.msg import String
        msg=String()
        msg.data=json.dumps({"type":"command_response","command_id":self.get_input("reminder_id",""),
                             "command":"reminder","status":"success" if self.get_input("reminder_status","")=="completed" else "failed",
                             "result":{"played":True}},ensure_ascii=False)
        self._pub.publish(msg)
        return NodeStatus.SUCCESS
