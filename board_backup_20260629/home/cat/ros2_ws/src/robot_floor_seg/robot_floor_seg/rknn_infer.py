import os
import cv2
import numpy as np
from rknnlite.api import RKNNLite

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "floor_wall_seg_v2-rk3576.rknn")
INPUT_SIZE = 640
CONF_THRESH = 0.25
MASK_THRESH = 0.5
MAX_DET = 30

CLASS_NAMES = ["BG", "Floor", "Wall"]
COLORS = [(50, 50, 50), (0, 255, 0), (255, 130, 0)]
CLASS_FILTER = {0}


class RKNNDetector:
    def __init__(self):
        self.rknn = None
        self._load_model()

    def _load_model(self):
        path = MODEL_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}")
        self.rknn = RKNNLite()
        if self.rknn.load_rknn(path) != 0:
            raise RuntimeError("load_rknn failed")
        if self.rknn.init_runtime() != 0:
            raise RuntimeError("init_runtime failed")

    def release(self):
        if self.rknn:
            self.rknn.release()
            self.rknn = None

    @staticmethod
    def letterbox(img, new_shape=(INPUT_SIZE, INPUT_SIZE), color=(114, 114, 114)):
        shape = img.shape[:2]
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw = new_shape[1] - new_unpad[0]
        dh = new_shape[0] - new_unpad[1]
        dw /= 2
        dh /= 2
        if shape[::-1] != new_unpad:
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top = int(round(dh - 0.1))
        bottom = int(round(dh + 0.1))
        left = int(round(dw - 0.1))
        right = int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img, r, (dw, dh)

    def infer(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        img_pad, r, pad = self.letterbox(frame_bgr)
        img_rgb = cv2.cvtColor(img_pad, cv2.COLOR_BGR2RGB)
        inp = np.expand_dims(img_rgb, axis=0).astype(np.float32)
        outs = self.rknn.inference(inputs=[inp])

        dets = outs[0][0]
        mask_protos = outs[1]
        proto_hw = (mask_protos.shape[2], mask_protos.shape[3])

        results = []
        for d in dets:
            conf = float(d[4])
            if conf < CONF_THRESH:
                continue
            cls_id = int(float(d[5]))
            if cls_id in CLASS_FILTER or cls_id < 0 or cls_id >= len(CLASS_NAMES):
                continue
            bbox = np.float32(d[:4])
            pw_px = int(round(pad[0]))
            ph_px = int(round(pad[1]))
            s = r
            ox1 = max(0.0, min(float(w), (bbox[0] - pw_px) / s))
            oy1 = max(0.0, min(float(h), (bbox[1] - ph_px) / s))
            ox2 = max(0.0, min(float(w), (bbox[2] - pw_px) / s))
            oy2 = max(0.0, min(float(h), (bbox[3] - ph_px) / s))
            results.append({
                "cls_id": cls_id, "conf": conf,
                "bbox": (ox1, oy1, ox2, oy2),
                "mask_coeffs": np.float32(d[6:38]),
            })
        results.sort(key=lambda x: x["conf"], reverse=True)
        results = results[:MAX_DET]

        frame_out = self._draw(frame_bgr, results, mask_protos, r, pad, proto_hw)
        return frame_out, len(results)

    def _draw(self, frame, results, mask_protos, r, pad, proto_hw):
        dw, dh = pad
        h, w = frame.shape[:2]
        ph = int(round(dh))
        pw = int(round(dw))

        if mask_protos is not None and results:
            protos = mask_protos[0].astype(np.float32)
            nc = protos.shape[0]
            coeffs_list = [x["mask_coeffs"] for x in results]
            if coeffs_list:
                coeffs_arr = np.stack(coeffs_list, axis=0)
                masks_raw = coeffs_arr @ protos.reshape(nc, -1)
                masks_sig = 1.0 / (1.0 + np.exp(-masks_raw))
                phw, pww = proto_hw
                masks_map = masks_sig.reshape(-1, phw, pww)

                mask_overlay = np.zeros((h, w, 3), dtype=np.uint8)
                for i, r_ in enumerate(results):
                    m = masks_map[i]
                    m = cv2.resize(m, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
                    m = m[ph:ph + h, pw:pw + w]
                    if m.shape[0] != h or m.shape[1] != w:
                        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
                    x1, y1, x2, y2 = r_["bbox"]
                    x1c = max(0, int(x1))
                    y1c = max(0, int(y1))
                    x2c = min(w, int(x2))
                    y2c = min(h, int(y2))
                    if x2c > x1c and y2c > y1c:
                        color = COLORS[r_["cls_id"] % len(COLORS)]
                        crop = m[y1c:y2c, x1c:x2c]
                        if crop.size > 10:
                            crop = cv2.resize(crop, (x2c - x1c, y2c - y1c), interpolation=cv2.INTER_LINEAR)
                            mask_bin = (crop > MASK_THRESH).astype(np.uint8)
                            for c in range(3):
                                mask_overlay[y1c:y2c, x1c:x2c, c] = np.where(
                                    mask_bin > 0,
                                    np.maximum(mask_overlay[y1c:y2c, x1c:x2c, c], color[c] * mask_bin),
                                    mask_overlay[y1c:y2c, x1c:x2c, c])
                if np.any(mask_overlay):
                    alpha = 0.5
                    blended = frame.copy().astype(np.float32)
                    blended[mask_overlay.max(2) > 0] = blended[mask_overlay.max(2) > 0] * (1 - alpha) + mask_overlay[mask_overlay.max(2) > 0].astype(np.float32) * alpha
                    frame = blended.astype(np.uint8)

        for r_ in results:
            cls_id = r_["cls_id"]
            conf = r_["conf"]
            x1, y1, x2, y2 = r_["bbox"]
            color = COLORS[cls_id % len(COLORS)]
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            name = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"cls_{cls_id}"
            label = f"{name} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (int(x1), int(y1) - th - 4), (int(x1) + tw + 4, int(y1)), color, -1)
            cv2.putText(frame, label, (int(x1) + 2, int(y1) - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return frame
