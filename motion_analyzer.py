"""
motion_analyzer.py — Advanced Motion Analysis for Hazard Detection
Uses optical flow and frame differencing to detect abnormal motion.

Features:
- Optical flow based velocity detection
- Abnormal motion (sudden, fast) detection
- Crowd motion analysis
- Frame-to-frame change analysis
"""

import cv2
import numpy as np
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MotionEvent:
    """Represents a motion event."""
    event_type: str         # "fast_motion", "sudden_motion", "crowd_motion"
    severity: float         # 0.0 to 1.0
    zone: str               # "left", "center", "right"
    motion_vector: Tuple    # (dx, dy) average motion
    timestamp: float
    message: str


class MotionAnalyzer:
    """
    Analyzes motion patterns in video frames using optical flow
    and frame differencing to detect abnormal or dangerous motion.
    """

    def __init__(self, frame_width: int, frame_height: int):
        """
        Initialize the motion analyzer.
        
        Args:
            frame_width: Width of video frames
            frame_height: Height of video frames
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.prev_frame_gray: Optional[np.ndarray] = None
        self.prev_frame_heatmap: Optional[np.ndarray] = None
        self.frame_diff_history: List[float] = []
        self.motion_history: List[MotionEvent] = []
        self.last_motion_time = time.time()

        # Optical flow parameters
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        # Corner detection for optical flow
        self.detector = cv2.goodFeaturesToTrack(
            np.zeros((frame_height, frame_width), dtype=np.uint8),
            maxCorners=200,
            qualityLevel=0.01,
            minDistance=30,
        )

        # Frame difference threshold
        self.frame_diff_threshold = 5.0  # Percentage of changed pixels
        self.motion_alert_threshold = 15.0

    def analyze(self, frame: np.ndarray) -> Dict:
        """
        Analyze motion in the current frame.
        
        Args:
            frame: Input frame (BGR)
        
        Returns:
            Dictionary with motion analysis results:
            {
                "events": List[MotionEvent],
                "avg_motion": float (0-1, normalized),
                "zones": {"left": float, "center": float, "right": float},
                "is_abnormal": bool,
                "description": str (descriptive message about motion),
            }
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.GaussianBlur(frame_gray, (5, 5), 0)

        motion_events = []
        zone_motion = {"left": 0.0, "center": 0.0, "right": 0.0}
        avg_motion = 0.0
        description = ""

        # 1. Optical flow analysis
        if self.prev_frame_gray is not None:
            flow, mag, angle = self._compute_optical_flow(frame_gray)
            avg_motion = np.mean(mag) / 10.0  # Normalize
            zone_motion = self._analyze_flow_by_zone(mag)

            # Detect fast/abnormal motion
            if avg_motion > 0.3:  # High motion threshold
                if avg_motion > 0.6:
                    description = "Warning: Very fast abnormal movement detected around you."
                else:
                    description = "Warning: Abnormal movement detected in your vicinity."
                    
                motion_events.append(
                    MotionEvent(
                        event_type="fast_motion",
                        severity=min(avg_motion, 1.0),
                        zone="center",
                        motion_vector=(np.mean(flow[..., 0]), np.mean(flow[..., 1])),
                        timestamp=time.time(),
                        message=description,
                    )
                )

        # 2. Frame differencing (sudden changes)
        frame_diff = self._compute_frame_difference(frame_gray)
        self.frame_diff_history.append(frame_diff)
        if len(self.frame_diff_history) > 10:
            self.frame_diff_history.pop(0)

        # Detect sudden motion spikes
        if len(self.frame_diff_history) > 3:
            recent_avg = np.mean(self.frame_diff_history[-3:])
            if frame_diff > recent_avg * 1.5:  # Sudden spike
                if frame_diff > 30:
                    description = "Danger: Sudden fast movement detected. Be alert!"
                else:
                    description = "Warning: Sudden movement detected in your environment."
                    
                motion_events.append(
                    MotionEvent(
                        event_type="sudden_motion",
                        severity=min(frame_diff / 50.0, 1.0),
                        zone="center",
                        motion_vector=(0, 0),
                        timestamp=time.time(),
                        message=description,
                    )
                )

        self.prev_frame_gray = frame_gray
        self.motion_history.extend(motion_events)

        # Keep only recent history
        current_time = time.time()
        self.motion_history = [
            m for m in self.motion_history if current_time - m.timestamp < 5.0
        ]

        return {
            "events": motion_events,
            "avg_motion": avg_motion,
            "zones": zone_motion,
            "is_abnormal": len(motion_events) > 0,
            "frame_diff": frame_diff,
            "description": description,
        }

    def _compute_optical_flow(self, frame_gray: np.ndarray) -> Tuple:
        """
        Compute dense optical flow using Farneback method.
        
        Returns:
            (flow, magnitude, angle)
            flow: (H, W, 2) - flow vectors
            magnitude: (H, W) - motion magnitude at each pixel
            angle: (H, W) - motion direction at each pixel
        """
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_frame_gray,
            frame_gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )

        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return flow, magnitude, angle

    def _analyze_flow_by_zone(self, magnitude: np.ndarray) -> Dict[str, float]:
        """
        Analyze optical flow magnitude by frame zones (left/center/right).
        """
        h, w = magnitude.shape
        third_w = w // 3

        zones = {
            "left": np.mean(magnitude[:, :third_w]),
            "center": np.mean(magnitude[:, third_w : 2 * third_w]),
            "right": np.mean(magnitude[:, 2 * third_w :]),
        }

        # Normalize to 0-1 range
        max_val = max(zones.values()) or 1.0
        return {k: v / (max_val * 10.0) for k, v in zones.items()}

    def _compute_frame_difference(self, frame_gray: np.ndarray) -> float:
        """
        Compute percentage of pixels that changed significantly between frames.
        """
        if self.prev_frame_gray is None:
            return 0.0

        diff = cv2.absdiff(self.prev_frame_gray, frame_gray)
        diff_percent = (np.count_nonzero(diff > 30) / diff.size) * 100
        return diff_percent

    def get_motion_data_for_detection(self, detections: List) -> Dict:
        """
        Generate motion data for each detected object.
        This integrates with the detector output.
        """
        motion_data = {}
        current_time = time.time()

        for det in detections:
            # Calculate velocity (area change rate)
            if len(self.motion_history) > 0:
                # Use average motion severity as velocity proxy
                velocities = [
                    m.severity for m in self.motion_history
                    if current_time - m.timestamp < 1.0
                ]
                velocity = np.mean(velocities) if velocities else 1.0
            else:
                velocity = 1.0

            motion_data[det.label] = {
                "velocity": velocity,
                "is_moving": velocity > 0.2,
            }

        return motion_data

    def is_crowded_motion(self) -> bool:
        """
        Detect if there's abnormal crowded motion.
        (Multiple fast motion events in a short time)
        """
        if len(self.motion_history) < 3:
            return False

        recent_events = [
            m for m in self.motion_history
            if time.time() - m.timestamp < 2.0
        ]

        return len(recent_events) > 2 and np.mean([e.severity for e in recent_events]) > 0.5

    def visualize(self, frame: np.ndarray, flow: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Draw motion visualization on frame (optical flow vectors).
        """
        if flow is None or self.prev_frame_gray is None:
            return frame

        flow = cv2.calcOpticalFlowFarneback(
            self.prev_frame_gray,
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
            None,
            0.5, 3, 15, 3, 5, 1.2, 0
        )

        # Draw flow vectors
        step = 16
        for y in range(0, flow.shape[0], step):
            for x in range(0, flow.shape[1], step):
                fx, fy = flow[y, x]
                end_x = int(x + fx)
                end_y = int(y + fy)

                # Draw arrow
                cv2.arrowedLine(
                    frame,
                    (x, y),
                    (end_x, end_y),
                    (0, 255, 0),
                    1,
                    tipLength=0.3,
                )

        return frame


# Standalone helper function for backward compatibility
def get_motion_velocity(det, motion_tracker) -> float:
    """
    Get velocity of a detected object from motion tracker.
    Backward compatible with existing motion_tracker module.
    """
    if hasattr(motion_tracker, 'get_approach'):
        approach = motion_tracker.get_approach(f"{det.label}")
        if approach == "approaching":
            return 0.8
        elif approach == "moving away":
            return 0.2
    return 0.5
