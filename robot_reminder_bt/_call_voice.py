#!/usr/bin/env python3
"""Standalone voice/speak caller - clean rclpy lifecycle"""
import sys

def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "reminder"
    
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from robot_voice_bridge.action import Speak
    
    # Force fresh context
    import os
    if "RCLPY_OK" in os.environ:
        del os.environ["RCLPY_OK"]
    
    try:
        rclpy.init(args=["_call_voice_sub"])
    except:
        pass  # already initialized
    
    node = Node("_call_voice")
    client = ActionClient(node, Speak, "/voice/speak")
    
    if not client.wait_for_server(timeout_sec=5.0):
        print("NO_SERVER", flush=True)
        node.destroy_node()
        return 1
    
    goal = Speak.Goal()
    goal.text = text
    goal.audio_path = ""
    
    future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    gh = future.result()
    
    if gh is None:
        print("REJECTED", flush=True)
        node.destroy_node()
        return 1
    
    result_future = gh.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=60.0)
    result = result_future.result()
    
    if result and result.result.success:
        print("SUCCESS", flush=True)
        node.destroy_node()
        return 0
    else:
        print("FAILED", flush=True)
        node.destroy_node()
        return 1

if __name__ == "__main__":
    sys.exit(main())
