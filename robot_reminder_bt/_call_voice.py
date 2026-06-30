#!/usr/bin/env python3
"""Standalone voice/speak caller - 独立进程，不污染ROS2上下文"""
import sys, os

def speak(text: str) -> bool:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from robot_voice_bridge.action import Speak
    
    # 完全独立的 rclpy 上下文
    rclpy.init(args=["_call_voice"])
    node = Node("_call_voice_node")
    
    client = ActionClient(node, Speak, "/voice/speak")
    if not client.wait_for_server(timeout_sec=3.0):
        print("NO_SERVER", flush=True)
        node.destroy_node()
        rclpy.shutdown()
        return False
    
    goal = Speak.Goal()
    goal.text = text
    goal.audio_path = ""
    
    send_future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future, timeout_sec=5.0)
    goal_handle = send_future.result()
    
    if goal_handle is None:
        print("REJECTED", flush=True)
        node.destroy_node()
        rclpy.shutdown()
        return False
    
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=60.0)
    result = result_future.result()
    
    ok = result is not None and result.result.success
    print("SUCCESS" if ok else "FAILED", flush=True)
    
    node.destroy_node()
    # 关键：完整 shutdown，不留给下次调用
    rclpy.shutdown()
    # 重置上下文，允许下次 rclpy.init()
    import gc
    gc.collect()
    return ok

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "reminder"
    speak(text)
