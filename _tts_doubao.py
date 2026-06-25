import rclpy, time, struct, sys
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from robot_interface.msg import AudioData

rclpy.init()
n = Node('collect')
chunks = []
last_t = [time.time()]
chan = [1]
srate = [24000]

def cb(msg):
    last_t[0] = time.time()
    chan[0] = msg.channels
    srate[0] = msg.rate
    for s in msg.data:
        chunks.append(struct.pack('<H', s))

n.create_subscription(AudioData, '/tts/audio', cb, 10)
executor = SingleThreadedExecutor()
executor.add_node(n)
import threading
t = threading.Thread(target=lambda: executor.spin(), daemon=True)
t.start()

# Publish text to trigger TTS
time.sleep(0.3)
msg = String()
msg.data = sys.argv[1] if len(sys.argv) > 1 else '测试'
n.create_publisher(String, '/tts/text', 10).publish(msg)
sys.stdout.write('PUB\n'); sys.stdout.flush()

# Wait for audio with timeout
deadline = time.time() + 10
while time.time() < deadline:
    if len(chunks) > 0 and time.time() - last_t[0] > 2:
        break
    time.sleep(0.05)

rclpy.shutdown()
executor.shutdown()

if not chunks:
    sys.stdout.write('NO_AUDIO\n')
    sys.exit(1)

raw = b''.join(chunks)
import wave
with wave.open('/tmp/_tts_doubao.wav', 'w') as wf:
    wf.setnchannels(chan[0])
    wf.setsampwidth(2)
    wf.setframerate(srate[0])
    wf.writeframes(raw)
sys.stdout.write('OK:' + str(len(raw)) + '\n')
