"""
BlindAssist — YOLO Detector
Core detection module for humans and obstacles.
Other team members import this class and build on top of it.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass

from config import (
    YOLO_MODEL, CONFIDENCE_THRESHOLD, TARGET_CLASSES,
    OBSTACLE_AREA_RATIO, BOX_COLOR_PERSON,
    BOX_COLOR_OBSTACLE, BOX_COLOR_DEFAULT, SHOW_LABELS
)


@dataclass
class Detection:
    """Represents a single detected object."""
    class_id: int
    label: str           # class name from YOLO
    confidence: float
    bbox: tuple          # (x1, y1, x2, y2) in pixels
    center: tuple        # (cx, cy) in pixels
    area_ratio: float    # bbox area / frame area
    is_person: bool
    is_close: bool       # True if area_ratio >= OBSTACLE_AREA_RATIO


class Detector:
    def __init__(self):
        print(f"[Detector] Loading model: {YOLO_MODEL}")
        self.model = YOLO(YOLO_MODEL)
        print("[Detector] Model ready.")

    # ──────────────────────────────────────────
    #  Main detection method
    # ──────────────────────────────────────────
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Analyzes a frame and returns a list of Detection objects.
        Only returns classes defined in TARGET_CLASSES.
        """
        h, w = frame.shape[:2]
        frame_area = h * w

        results = self.model(frame, verbose=False)[0]
        detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in TARGET_CLASSES:
                continue

            conf = float(box.conf[0])
            if conf < CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            bbox_area = (x2 - x1) * (y2 - y1)
            area_ratio = bbox_area / frame_area
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            det = Detection(
                class_id=cls_id,
                label=TARGET_CLASSES[cls_id],
                confidence=conf,
                bbox=(x1, y1, x2, y2),
                center=(cx, cy),
                area_ratio=area_ratio,
                is_person=(cls_id == 0),
                is_close=(area_ratio >= OBSTACLE_AREA_RATIO),
            )
            detections.append(det)

        return detections

    # ──────────────────────────────────────────
    #  Drawing
    # ──────────────────────────────────────────
    def draw(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        """Draws bounding boxes and labels onto the frame."""
        for det in detections:
            x1, y1, x2, y2 = det.bbox

            # Pick color based on detection type
            if det.is_person:
                color = BOX_COLOR_PERSON
            elif det.is_close:
                color = BOX_COLOR_OBSTACLE
            else:
                color = BOX_COLOR_DEFAULT

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            if SHOW_LABELS:
                label_text = f"{det.label} {det.confidence:.0%}"
                if det.is_close:
                    label_text += " !"

                # Label background
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
                cv2.putText(
                    frame, label_text,
                    (x1 + 3, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 0), 2
                )

        return frame

    # ──────────────────────────────────────────
    #  Helper filters (used by other team members)
    # ──────────────────────────────────────────
    def get_persons(self, detections: list[Detection]) -> list[Detection]:
        return [d for d in detections if d.is_person]

    def get_obstacles(self, detections: list[Detection]) -> list[Detection]:
        return [d for d in detections if d.is_close and not d.is_person]

    def get_by_class(self, detections: list[Detection], class_id: int) -> list[Detection]:
        return [d for d in detections if d.class_id == class_id]
