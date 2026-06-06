"""
BlindAssist — Camera
"""

import cv2
import numpy as np
from config import CAMERA_SOURCE


class Camera:
    def __init__(self, source=None):
        # Use the provided source; fall back to config value (webcam, DroidCam IP, etc.)
        self.source = source or CAMERA_SOURCE
        self.cap = None  # VideoCapture object, initialized on open()

    def open(self) -> bool:
        """Open the camera and set capture resolution to 1280x720.
        Returns True on success, False if the source cannot be opened."""
        print(f"[Camera] Connecting to: {self.source}")
        self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            print(f"[Camera] ERROR: Could not open camera -> {self.source}")
            return False

        # Force 720p — DroidCam and webcams may default to a lower resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        print("[Camera] Connected — 1280x720")
        return True

    def read(self):
        """Read a single frame from the capture device.
        Returns (ret, frame) — same contract as cv2.VideoCapture.read()."""
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        """Release the capture device and free resources."""
        if self.cap:
            self.cap.release()
            print("[Camera] Released.")