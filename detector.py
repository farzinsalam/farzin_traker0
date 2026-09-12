"""
BottleVision Sentinel - YOLOv8 Detection Engine & Tactical HUD Overlay
"""

import time
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class BottleDetector:
    # COCO Dataset Class 39 is 'bottle'
    BOTTLE_CLASS_ID = 39

    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.40):
        self.conf_threshold = conf_threshold
        self.prev_time = time.time()
        self.fps = 0.0

        if YOLO is None:
            raise RuntimeError("Ultralytics package is not installed. Please run: pip install -r requirements.txt")

        print(f"[BottleDetector] Loading AI model: {model_name}...")
        self.model = YOLO(model_name)
        print("[BottleDetector] Model ready.")

    def update_confidence(self, conf: float):
        self.conf_threshold = max(0.05, min(0.95, conf))

    def detect(self, frame: np.ndarray, draw_overlay: bool = True, guardian_state: str = "OFF"):
        """
        Runs YOLOv8 detection specifically for bottles and annotates frame with tactical HUD.
        Returns: (annotated_frame, detections, count, fps)
        """
        curr_time = time.time()
        diff = curr_time - self.prev_time
        if diff > 0:
            self.fps = 0.85 * self.fps + 0.15 * (1.0 / diff)
        self.prev_time = curr_time

        # Run inference for COCO class 39 (bottle)
        raw_results = self.model.predict(
            source=frame,
            classes=[self.BOTTLE_CLASS_ID],
            conf=self.conf_threshold,
            verbose=False
        )

        results = list(raw_results) if raw_results is not None else []
        detections = []
        annotated_frame = frame.copy()

        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = map(int, xyxy)

                detections.append({
                    "box": [x1, y1, x2, y2],
                    "confidence": round(conf, 4)
                })

                if draw_overlay:
                    is_guarded = guardian_state in ("ARMED & SECURE", "ARMED", "ARMED_SECURE")
                    self._draw_tactical_box(annotated_frame, x1, y1, x2, y2, conf, is_guarded=is_guarded)

        count = len(detections)
        if draw_overlay:
            self._draw_tactical_hud(annotated_frame, count, self.fps, guardian_state)

        return annotated_frame, detections, count, self.fps

    def _draw_tactical_box(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int, conf: float, is_guarded: bool = False):
        """Draws high-tech cyberpunk reticle corner brackets and glowing badges."""
        if is_guarded:
            box_color = (255, 200, 0)       # High-tech Electric Cyan in BGR (0, 200, 255)
            corner_color = (255, 240, 50)
            badge_title = f"🛡️ FARZIN'S BOTTLE {int(conf * 100)}%"
        else:
            box_color = (100, 230, 50)       # Neon Emerald
            corner_color = (120, 255, 80)
            badge_title = f"BOTTLE {int(conf * 100)}%"

        # Subtle bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

        # High-tech corner brackets
        w, h = x2 - x1, y2 - y1
        c_len = max(10, min(28, int(min(w, h) * 0.22)))
        th = 3

        # Top-left
        cv2.line(img, (x1, y1), (x1 + c_len, y1), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + c_len), corner_color, th, cv2.LINE_AA)
        # Top-right
        cv2.line(img, (x2, y1), (x2 - c_len, y1), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + c_len), corner_color, th, cv2.LINE_AA)
        # Bottom-left
        cv2.line(img, (x1, y2), (x1 + c_len, y2), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - c_len), corner_color, th, cv2.LINE_AA)
        # Bottom-right
        cv2.line(img, (x2, y2), (x2 - c_len, y2), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - c_len), corner_color, th, cv2.LINE_AA)

        # Center reticle crosshair
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        r_len = 8
        cv2.line(img, (cx - r_len, cy), (cx + r_len, cy), corner_color, 1, cv2.LINE_AA)
        cv2.line(img, (cx, cy - r_len), (cx, cy + r_len), corner_color, 1, cv2.LINE_AA)

        # Holographic Badge Header
        (lw, lh), _ = cv2.getTextSize(badge_title, cv2.FONT_HERSHEY_DUPLEX, 0.50, 1)
        by1, by2 = max(0, y1 - lh - 10), y1
        bx1, bx2 = x1, x1 + lw + 16

        overlay = img.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (15, 18, 25), -1)
        cv2.addWeighted(overlay, 0.82, img, 0.18, 0, img)
        cv2.rectangle(img, (bx1, by1), (bx2, by2), box_color, 1, cv2.LINE_AA)
        cv2.putText(img, badge_title, (bx1 + 8, by2 - 6), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_tactical_hud(self, img: np.ndarray, count: int, fps: float, guardian_state: str):
        """Renders top telemetry bar, defense status indicators, and alarm banners."""
        h, w, _ = img.shape
        bar_height = 46

        # Semi-transparent sleek dark HUD bar
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_height), (10, 14, 22), -1)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
        cv2.line(img, (0, bar_height), (w, bar_height), (40, 55, 80), 1, cv2.LINE_AA)

        is_theft = "THEFT" in guardian_state or "ALERT" in guardian_state
        if is_theft:
            status_color = (40, 40, 255)       # Red
            status_text = "🚨 SENTINEL BREACH: WATER BOTTLE STOLEN! 🚨"
        elif "ARMED" in guardian_state:
            status_color = (255, 200, 0)      # Cyan
            status_text = f"🛡️ SENTINEL ARMED: {count} BOTTLE(S) SECURE"
        elif count > 0:
            status_color = (80, 240, 80)      # Emerald
            status_text = f"BOTTLES IN SIGHT: {count}"
        else:
            status_color = (240, 180, 0)      # Blue/Cyan
            status_text = "SCANNING SECTOR FOR BOTTLES..."

        # Indicator dot
        cv2.circle(img, (24, 23), 6, status_color, -1, cv2.LINE_AA)
        cv2.circle(img, (24, 23), 9, status_color, 1, cv2.LINE_AA)
        cv2.putText(img, status_text, (42, 29), cv2.FONT_HERSHEY_DUPLEX, 0.58, (245, 250, 255), 1, cv2.LINE_AA)

        # Right-side telemetry (FPS and Sensitivity)
        fps_text = f"FPS: {fps:0.1f} | SENSITIVITY: {int(self.conf_threshold * 100)}%"
        (fw, _), _ = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_DUPLEX, 0.48, 1)
        cv2.putText(img, fps_text, (max(10, w - fw - 20), 29), cv2.FONT_HERSHEY_DUPLEX, 0.48, (160, 185, 210), 1, cv2.LINE_AA)

        # Flashing Alarm Strobe Banner when theft is active!
        if is_theft:
            flash_phase = int(time.time() * 3.5) % 2
            if flash_phase == 0:
                banner_h = 96
                cy = h // 2
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - banner_h // 2), (w, cy + banner_h // 2), (15, 15, 180), -1)
                cv2.addWeighted(banner_overlay, 0.88, img, 0.12, 0, img)
                cv2.line(img, (0, cy - banner_h // 2), (w, cy - banner_h // 2), (60, 60, 255), 2, cv2.LINE_AA)
                cv2.line(img, (0, cy + banner_h // 2), (w, cy + banner_h // 2), (60, 60, 255), 2, cv2.LINE_AA)

                t1 = "🚨 THEFT DETECTED: KATHI THAZHE IDADA! 🚨"
                t2 = "WHO STOLE FARZIN'S WATER BOTTLE?! PUT IT BACK!"
                (tw1, _), _ = cv2.getTextSize(t1, cv2.FONT_HERSHEY_DUPLEX, 0.82, 2)
                (tw2, _), _ = cv2.getTextSize(t2, cv2.FONT_HERSHEY_DUPLEX, 0.65, 2)
                cv2.putText(img, t1, (max(10, (w - tw1) // 2), cy - 8), cv2.FONT_HERSHEY_DUPLEX, 0.82, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, t2, (max(10, (w - tw2) // 2), cy + 28), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 220, 70), 2, cv2.LINE_AA)
