"""
BlindAssist — Camera
"""

import cv2
import numpy as np
from config import CAMERA_SOURCE


class Camera:
    def __init__(self, source=None):
        self.source = source or CAMERA_SOURCE
        self.cap = None

    def open(self) -> bool:
        print(f"[Camera] Connecting to: {self.source}")
        self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            print(f"[Camera] ERROR: Could not open camera -> {self.source}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        print("[Camera] Connected — 1280x720")
        return True

    def read(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            self.cap.release()
            print("[Camera] Released.")