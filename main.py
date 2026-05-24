"""
BlindAssist — Person 1 Module
Human & Obstacle Detection + Depth
"""

import sys
import time
import cv2
import numpy as np

from config import FRAME_SKIP, WINDOW_TITLE, SHOW_FPS, ALERT_COOLDOWN
from core.camera import Camera
from detection.detector import Detector
from utils.fps_counter import FPSCounter
from depth_estimator import DepthEstimator
from motion_tracker import MotionTracker

depth_estimator = DepthEstimator()

COLOR_PERSON   = (0, 255, 120)
COLOR_OBSTACLE = (0, 140, 255)
COLOR_DIM      = (70, 70, 70)


class AlertManager:
    def __init__(self, cooldown: float = ALERT_COOLDOWN):
        self.cooldown = cooldown
        self._last: dict = {}

    def should_alert(self, label: str) -> bool:
        now = time.time()
        if now - self._last.get(label, 0) >= self.cooldown:
            self._last[label] = now
            return True
        return False


def draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2):
    """CS:GO tarzı köşe kutusu — tam çizilir."""
    lx = max(12, (x2 - x1) // 5)
    ly = max(12, (y2 - y1) // 5)
    # Üst-sol
    cv2.line(frame, (x1, y1), (x1 + lx, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + ly), color, thickness)
    # Üst-sağ
    cv2.line(frame, (x2, y1), (x2 - lx, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + ly), color, thickness)
    # Alt-sol
    cv2.line(frame, (x1, y2), (x1 + lx, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - ly), color, thickness)
    # Alt-sağ
    cv2.line(frame, (x2, y2), (x2 - lx, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - ly), color, thickness)


def draw_detections(frame, detections):
    for det in detections:
        x1, y1, x2, y2 = det.bbox

        if det.is_person:
            color = COLOR_PERSON
            label = f"person  {det.confidence:.0%}"
        elif det.is_close:
            color = COLOR_OBSTACLE
            label = f"{det.label}  {det.confidence:.0%}  !"
        else:
            color = COLOR_DIM
            label = f"{det.label}  {det.confidence:.0%}"

        draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2)

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        lx = x1 + 2
        ly = y1 - 6 if y1 - th - 8 >= 0 else y2 + th + 6
        cv2.rectangle(frame, (lx - 2, ly - th - 3), (lx + tw + 3, ly + 2), (12, 12, 12), -1)
        cv2.putText(frame, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

    return frame


def draw_hud(frame, fps, n_persons, n_obstacles, n_structural):
    h, w = frame.shape[:2]
    bar_h = 44

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), (8, 8, 8), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
    cv2.line(frame, (0, h - bar_h), (w, h - bar_h), (40, 40, 40), 1)

    # FPS — sol
    fps_color = (0, 200, 80) if fps >= 30 else (0, 140, 255) if fps >= 15 else (0, 60, 220)
    cv2.putText(frame, f"{fps:.0f} fps", (14, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, fps_color, 1)

    # 3 stat — ortalanmış
    stats = [
        (f"PERSON  {n_persons}", COLOR_PERSON   if n_persons    > 0 else COLOR_DIM),
        (f"OBSTACLE  {n_obstacles}", COLOR_OBSTACLE if n_obstacles > 0 else COLOR_DIM),
        (f"STRUCTURAL  {n_structural}", (0, 60, 220)  if n_structural > 0 else COLOR_DIM),
    ]
    seg = w // 3
    for i, (text, color) in enumerate(stats):
        tw, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0]
        x = seg * i + (seg - tw) // 2
        cv2.putText(frame, text, (x, h - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

    return frame


def main():
    print("=" * 50)
    print("  BlindAssist — Starting")
    print("=" * 50)

    camera   = Camera()
    detector = Detector()
    fps_ctr  = FPSCounter()
    alerts   = AlertManager()

    if not camera.open():
        sys.exit(1)

    tracker = None
    
    frame_count  = 0
    detections   = []
    depth_result = None

    print("\n[Main Loop] Running — press 'q' to quit\n")

    while True:
        ret, frame = camera.read()
        if not ret or frame is None:
            print("[Main Loop] End of stream.")
            break

        if tracker is None:
            tracker = MotionTracker(frame.shape[1])

        frame_count += 1
        fps_ctr.tick()

        # ── YOLO ─────────────────────────────────────────────────────────────
        if frame_count % FRAME_SKIP == 0:
            detections = detector.detect(frame)

            tracker.update(detections)
            analysis = tracker.analyze(detections)

            for obj in analysis:
                print(f"[MOTION] {obj['label']} | {obj['zone']} | {obj['motion']} | {obj['approach']}")

            persons    = detector.get_persons(detections)
            obstacles  = detector.get_obstacles(detections)

            if persons and alerts.should_alert("person"):
                n = len(persons)
                print(f"[ALERT] {'Person ahead.' if n == 1 else f'{n} people ahead.'}")
            for obs in obstacles:
                if alerts.should_alert(obs.label):
                    print(f"[ALERT] {obs.label} ahead.")

        # ── Depth (thread'de, bloklamaz) ──────────────────────────────────────
        depth_result = depth_estimator.estimate(frame)
        if depth_result:
            for msg in depth_result.prop_alerts:
                print(f"[PROP]  {msg}")

        # ── Çizim ─────────────────────────────────────────────────────────────
        if depth_result:
            frame = depth_estimator.draw_overlay(frame, depth_result)

        frame = draw_detections(frame, detections)

        n_struct = len(depth_result.close_zones) if depth_result else 0
        frame = draw_hud(frame, fps_ctr.fps,
                         len(detector.get_persons(detections)),
                         len(detector.get_obstacles(detections)),
                         n_struct)

        cv2.imshow(WINDOW_TITLE, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("\n[Main Loop] Quitting...")
            break

    camera.release()
    cv2.destroyAllWindows()
    print("[Main Loop] Done.")


if __name__ == "__main__":
    main()