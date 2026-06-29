import os
import sys
import time
import threading
import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int32
from sensor_msgs.msg import Image

from robot_floor_seg.rknn_infer import RKNNDetector
from robot_floor_seg.web_server import WebServer


class WallFloorSegNode(Node):
    def __init__(self):
        super().__init__("wall_floor_seg_node")

        self.declare_parameter("web_port", 8080)
        self.declare_parameter("camera_id", "/dev/video11")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("skip_frames", 2)

        self.web_port = self.get_parameter("web_port").value
        self.camera_id = self.get_parameter("camera_id").value
        self.width = self.get_parameter("width").value
        self.height = self.get_parameter("height").value
        self.skip_frames = self.get_parameter("skip_frames").value

        self._enabled = True
        self._latest_jpeg = None
        self._stats = {"fps": 0.0, "n": 0, "latency": 0}
        self._lock = threading.Lock()

        self.pub_enabled = self.create_publisher(Bool, "seg_enabled", 10)
        self.pub_det_count = self.create_publisher(Int32, "seg_det_count", 10)

        self.get_logger().info("Loading RKNN model...")
        self.detector = RKNNDetector()
        self.get_logger().info("RKNN model ready")

        self.web = WebServer(self._web_handler, port=self.web_port)
        self._web_thread = threading.Thread(target=self.web.start, daemon=True)
        self._web_thread.start()
        self.get_logger().info(f"Web server: http://0.0.0.0:{self.web_port}")

        self._infer_thread = threading.Thread(target=self._inference_loop, daemon=True)
        self._infer_thread.start()

    def _web_handler(self, toggle=False, stats=False):
        if toggle:
            with self._lock:
                self._enabled = not self._enabled
                msg = Bool()
                msg.data = self._enabled
                self.pub_enabled.publish(msg)
                self.get_logger().info(f"Segmentation {'enabled' if self._enabled else 'disabled'}")
            return self._enabled
        if stats:
            with self._lock:
                return dict(self._stats)
        with self._lock:
            return self._latest_jpeg

    def _inference_loop(self):
        self.get_logger().info("Opening camera...")
        cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(11, cv2.CAP_V4L2)
        if not cap.isOpened():
            self.get_logger().error("Camera not found, waiting for camera...")
            cap = None

        if cap:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        fc = 0
        skip = 0
        ft = time.time()
        cached_jpeg = None
        self.get_logger().info("Inference loop started")

        while rclpy.ok():
            if cap:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
            else:
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                time.sleep(0.033)

            skip += 1
            with self._lock:
                enabled = self._enabled

            if skip % (self.skip_frames + 1) != 0 or not enabled:
                fc += 1
                with self._lock:
                    self._latest_jpeg = cached_jpeg
                if time.time() - ft >= 1.0:
                    with self._lock:
                        self._stats["fps"] = fc / (time.time() - ft)
                    fc = 0
                    ft = time.time()
                continue

            t0 = time.time()
            frame_out, det_count = self.detector.infer(frame)
            latency = (time.time() - t0) * 1000
            fc += 1

            ret_jpg, jpg = cv2.imencode(".jpg", frame_out, [cv2.IMWRITE_JPEG_QUALITY, 65])
            if ret_jpg:
                jpeg_bytes = jpg.tobytes()
                with self._lock:
                    self._latest_jpeg = jpeg_bytes
                    self._stats["n"] = det_count
                    self._stats["latency"] = latency
                cached_jpeg = jpeg_bytes

            now = time.time()
            if now - ft >= 1.0:
                fps = fc / (now - ft)
                with self._lock:
                    self._stats["fps"] = fps
                self.get_logger().info(f"FPS: {fps:.1f} | det: {det_count} | lat: {latency:.0f}ms")
                fc = 0
                ft = now
                msg = Int32()
                msg.data = det_count
                self.pub_det_count.publish(msg)

        if cap:
            cap.release()
        self.detector.release()

    def shutdown(self):
        self.detector.release()
        super().shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = WallFloorSegNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
