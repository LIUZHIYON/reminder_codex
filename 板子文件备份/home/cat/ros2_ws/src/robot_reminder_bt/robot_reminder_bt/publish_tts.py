#!/usr/bin/env python3
import sys, os, time, json, uuid
def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "reminder"
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    try:
        rclpy.init(args=["publish_tts"])
    except:
        pass
    node = Node("publish_tts_tmp")
    pub = node.create_publisher(String, "/tts/text", 10)
    time.sleep(0.5)
    # Send JSON format (tts_node requires JSON, voice_bridge accepts both)
    msg = String()
    msg.data = json.dumps({"text": text, "id": "g_" + uuid.uuid4().hex[:12]},
                          ensure_ascii=False)
    pub.publish(msg)
    time.sleep(0.3)
    # Also send plain text as fallback (voice_bridge can use it)
    msg2 = String()
    msg2.data = text
    pub.publish(msg2)
    for _ in range(5):
        rclpy.spin_once(node, timeout_sec=0.3)
    node.destroy_node()
    print("PUB_OK", flush=True)
    return 0
if __name__ == "__main__":
    sys.exit(main())
