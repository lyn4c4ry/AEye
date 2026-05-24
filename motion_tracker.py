import numpy as np
import time


class MotionTracker:
    def __init__(self, frame_width):
        self.frame_width = frame_width

        # objeleri tutma (label bazlı basit tracking)
        self.objects = {}

        # zone boundaries (1/3 - 1/3 - 1/3)
        self.left_bound = frame_width / 3
        self.right_bound = 2 * frame_width / 3

    # ─────────────────────────────────────────────
    # detection update
    # ─────────────────────────────────────────────
    def update(self, detections):
        """
        detections: Detector çıktısı (Detection list)
        """
        for det in detections:
            cx, cy = det.center
            label = det.label

            # basit ID (ileride geliştirilebilir)
            obj_id = f"{label}"

            if obj_id not in self.objects:
                self.objects[obj_id] = {
                    "history": [],
                    "last_seen": time.time(),
                    "last_area": det.area_ratio
                }

            obj = self.objects[obj_id]

            # geçmişe ekle
            obj["history"].append((cx, cy, det.area_ratio))
            obj["last_seen"] = time.time()

            # son 5 frame tut
            if len(obj["history"]) > 5:
                obj["history"].pop(0)

    # ─────────────────────────────────────────────
    # horizontal zone detection
    # ─────────────────────────────────────────────
    def get_zone(self, cx):
        if cx < self.left_bound:
            return "left"
        elif cx < self.right_bound:
            return "center"
        else:
            return "right"

    # ─────────────────────────────────────────────
    # movement direction
    # ─────────────────────────────────────────────
    def get_motion(self, obj_id):
        obj = self.objects.get(obj_id)
        if not obj or len(obj["history"]) < 2:
            return "unknown"

        x1 = obj["history"][-2][0]
        x2 = obj["history"][-1][0]

        dx = x2 - x1

        if dx > 10:
            return "moving right"
        elif dx < -10:
            return "moving left"
        else:
            return "static"

    # ─────────────────────────────────────────────
    # approaching detection (size change)
    # ─────────────────────────────────────────────
    def get_approach(self, obj_id):
        obj = self.objects.get(obj_id)
        if not obj or len(obj["history"]) < 2:
            return "unknown"

        prev_area = obj["history"][-2][2]
        curr_area = obj["history"][-1][2]

        if curr_area > prev_area * 1.15:
            return "approaching"
        elif curr_area < prev_area * 0.85:
            return "moving away"
        else:
            return "stable"

    # ─────────────────────────────────────────────
    # full analysis (SENİN ANA FONKSİYONUN)
    # ─────────────────────────────────────────────
    def analyze(self, detections):
        results = []

        for det in detections:
            cx, cy = det.center
            label = det.label

            obj_id = f"{label}"

            zone = self.get_zone(cx)
            motion = self.get_motion(obj_id)
            approach = self.get_approach(obj_id)

            results.append({
                "label": label,
                "zone": zone,
                "motion": motion,
                "approach": approach
            })

        return results