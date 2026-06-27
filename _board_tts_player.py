#!/usr/bin/env python3
import sys, os, time, struct, threading, subprocess
sys.stdout = open(sys.stdout.fileno(), mode="w", buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode="w", buffering=1)
text = sys.argv[1] if len(sys.argv) > 1 else "你好"
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from robot_interface.msg import AudioData
except Exception as e:
    print("IMPORT FAIL:" + str(e))
    sys.exit(1)

class Collector(Node):
    def __init__(self, text):
        super().__init__("tts_collector")
        self.text = text
        self.chunks = []
        self.channels = 1
        self.rate = 24000
        self.last = time.time()
        self.ready = threading.Event()
        self.sub = self.create_subscription(AudioData, "/tts/audio", self.cb, 10)
        print("Subscribed to /tts/audio")
        time.sleep(0.3)
        msg = String(); msg.data = self.text
        self.create_publisher(String, "/tts/text", 10).publish(msg)
        print("Published to /tts/text:", text[:30])

    def cb(self, msg):
        self.last = time.time()
        self.channels = msg.channels
        self.rate = msg.rate
        for s in msg.data:
            self.chunks.append(struct.pack("<H", s))
        if not self.ready.is_set():
            self.ready.set()
        print(f"Chunk: {len(msg.data)} samples, total {len(self.chunks)} bytes")

rclpy.init()
col = Collector(text)
spin_thr = threading.Thread(target=lambda: rclpy.spin(col), daemon=True)
spin_thr.start()
# Wait for first chunk (timeout 10s) or timeout with no data
got_data = col.ready.wait(timeout=10.0)
if got_data:
    # Wait for silence (2s gap) or total max 8s after first data
    deadline = time.time() + 8.0
    while time.time() < deadline:
        if time.time() - col.last > 2.0:
            break
        time.sleep(0.1)
rclpy.shutdown()
if not col.chunks:
    print("FAIL: No audio received")
    sys.exit(1)
raw = b"".join(col.chunks)
import wave
with wave.open("/tmp/_tts_play.wav", "w") as wf:
    wf.setnchannels(col.channels)
    wf.setsampwidth(2)
    wf.setframerate(col.rate)
    wf.writeframes(raw)
print(f"WAV: {len(raw)} bytes")
subprocess.Popen(["paplay", "/tmp/_tts_play.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("PLAYING")
