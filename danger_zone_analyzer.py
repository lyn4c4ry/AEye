"""
danger_zone_analyzer.py — Dynamic Danger Zone Analysis
Analyzes frame regions to identify safe paths and risky areas.

Features:
- Danger zone segmentation (safe vs warning vs danger)
- Safe path detection
- Directional guidance based on danger zones
- Heatmap generation for visualization
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DangerZone:
    """Represents a region with detected hazards."""
    x1: int
    y1: int
    x2: int
    y2: int
    danger_level: str  # "safe", "warning", "danger", "emergency"
    hazards: List[str]  # Types of hazards in this zone
    score: float  # 0.0 (safe) to 1.0 (most dangerous)


class DangerZoneAnalyzer:
    """
    Analyzes the camera frame to identify safe vs dangerous regions.
    Provides spatial analysis of hazards for better user guidance.
    """

    def __init__(self, frame_width: int, frame_height: int, grid_size: int = 6):
        """
        Initialize danger zone analyzer.
        
        Args:
            frame_width: Width of video frames
            frame_height: Height of video frames
            grid_size: Number of grid divisions per axis (default 6x6)
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.grid_size = grid_size
        self.grid_width = frame_width // grid_size
        self.grid_height = frame_height // grid_size

        # Initialize danger grid
        self.danger_grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.hazard_grid = [[[] for _ in range(grid_size)] for _ in range(grid_size)]

    def analyze(self, detections: List, depth_map: Optional[np.ndarray] = None) -> Dict:
        """
        Analyze detections to build danger map.
        
        Args:
            detections: List of Detection objects from YOLO
            depth_map: Optional depth map for distance-based scoring
        
        Returns:
            Dictionary with:
            - danger_grid: 2D array of danger scores (0-1)
            - danger_zones: List of DangerZone objects
            - safe_zones: List of safe regions
            - safe_path: Recommended direction for safe movement
            - overall_safety: Overall environmental safety score (0-1)
        """
        # Reset grids
        self.danger_grid = np.zeros((self.grid_size, self.grid_size), dtype=np.float32)
        self.hazard_grid = [[[] for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        # Process each detection
        for det in detections:
            self._update_danger_grid_for_detection(det)

        # Apply depth-based weighting if available
        if depth_map is not None:
            self._apply_depth_weighting(depth_map)

        # Smooth the danger grid
        self.danger_grid = cv2.GaussianBlur(self.danger_grid, (3, 3), 0.5)
        self.danger_grid = np.clip(self.danger_grid, 0, 1)

        # Extract danger zones and safe zones
        danger_zones = self._extract_danger_zones()
        safe_zones = self._extract_safe_zones()

        # Find safe path
        safe_path = self._find_safe_path()

        # Calculate overall safety
        overall_safety = 1.0 - np.mean(self.danger_grid)

        return {
            "danger_grid": self.danger_grid,
            "danger_zones": danger_zones,
            "safe_zones": safe_zones,
            "safe_path": safe_path,
            "overall_safety": overall_safety,
            "threat_level": self._get_threat_level(overall_safety),
        }

    def _update_danger_grid_for_detection(self, det) -> None:
        """Update danger grid based on a single detection."""
        x1, y1, x2, y2 = det.bbox
        cx, cy = det.center

        # Calculate danger score based on object properties
        danger_score = self._calculate_danger_score(det)

        # Get grid coordinates
        grid_x = min(self.grid_size - 1, cx // self.grid_width)
        grid_y = min(self.grid_size - 1, cy // self.grid_height)

        # Spread danger across nearby grid cells (3x3 neighborhood)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                nx = grid_x + dx
                ny = grid_y + dy

                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    # Distance-based weight (center is highest)
                    weight = 1.0 - (abs(dx) + abs(dy)) * 0.2
                    self.danger_grid[ny, nx] = max(
                        self.danger_grid[ny, nx], danger_score * weight
                    )
                    self.hazard_grid[ny][nx].append(det.label)

    def _calculate_danger_score(self, det) -> float:
        """Calculate danger score for a detection (0-1)."""
        # High-priority objects
        high_priority = {
            "car": 0.8,
            "truck": 0.9,
            "bus": 0.85,
            "motorcycle": 0.7,
            "person": 0.4,
        }

        # Environmental hazards
        environmental_hazards = {
            "fire": 1.0,
            "smoke": 0.9,
        }

        base_score = high_priority.get(det.label, 0.3)

        # Environmental hazards get highest priority
        if det.label in environmental_hazards:
            return environmental_hazards[det.label]

        # Closer objects are more dangerous
        closeness_factor = min(det.area_ratio / 0.1, 1.0)
        confidence_factor = det.confidence

        return base_score * closeness_factor * confidence_factor

    def _apply_depth_weighting(self, depth_map: np.ndarray) -> None:
        """Apply depth information to danger scoring."""
        # Resize depth map to grid size
        depth_grid = cv2.resize(
            depth_map, (self.grid_size, self.grid_size), interpolation=cv2.INTER_NEAREST
        )

        # Close objects (higher depth values) are more dangerous
        # Invert: closer = higher value = more dangerous
        depth_weight = 1.0 - depth_grid  # Invert so close = high

        # Apply weighting
        self.danger_grid *= (1.0 + depth_weight) / 2.0

    def _extract_danger_zones(self) -> List[DangerZone]:
        """Extract connected danger regions from grid."""
        danger_zones = []

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.danger_grid[y, x] > 0.3:  # Threshold for danger
                    x1 = x * self.grid_width
                    y1 = y * self.grid_height
                    x2 = min((x + 1) * self.grid_width, self.frame_width)
                    y2 = min((y + 1) * self.grid_height, self.frame_height)

                    score = float(self.danger_grid[y, x])
                    level = self._score_to_level(score)
                    hazards = list(set(self.hazard_grid[y][x]))

                    zone = DangerZone(
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        danger_level=level,
                        hazards=hazards,
                        score=score,
                    )
                    danger_zones.append(zone)

        return danger_zones

    def _extract_safe_zones(self) -> List[DangerZone]:
        """Extract safe regions from grid."""
        safe_zones = []

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.danger_grid[y, x] < 0.2:  # Threshold for safety
                    x1 = x * self.grid_width
                    y1 = y * self.grid_height
                    x2 = min((x + 1) * self.grid_width, self.frame_width)
                    y2 = min((y + 1) * self.grid_height, self.frame_height)

                    zone = DangerZone(
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        danger_level="safe",
                        hazards=[],
                        score=0.0,
                    )
                    safe_zones.append(zone)

        return safe_zones

    def _find_safe_path(self) -> Optional[str]:
        """
        Find the safest direction for the user to move.
        Returns: "left", "center", "right", "ahead", or None if no safe path
        """
        # Divide frame into zones
        third_w = self.frame_width // 3

        # Calculate danger in each zone
        left_danger = np.mean(self.danger_grid[:, :2])
        center_danger = np.mean(self.danger_grid[:, 1:-1])
        right_danger = np.mean(self.danger_grid[:, -2:])

        # Find safest direction
        dangers = {
            "left": left_danger,
            "center": center_danger,
            "right": right_danger,
        }

        safest = min(dangers, key=dangers.get)

        # If all zones are too dangerous, return None
        if dangers[safest] > 0.7:
            return None

        return safest

    def _score_to_level(self, score: float) -> str:
        """Convert danger score to level name."""
        if score > 0.8:
            return "emergency"
        elif score > 0.6:
            return "danger"
        elif score > 0.3:
            return "warning"
        else:
            return "safe"

    def _get_threat_level(self, overall_safety: float) -> str:
        """Get overall threat level."""
        threat = 1.0 - overall_safety
        if threat > 0.8:
            return "CRITICAL"
        elif threat > 0.6:
            return "HIGH"
        elif threat > 0.3:
            return "MODERATE"
        else:
            return "LOW"

    def visualize(self, frame: np.ndarray, analysis_result: Dict) -> np.ndarray:
        """
        Draw danger zone visualization on frame.
        """
        danger_zones = analysis_result.get("danger_zones", [])
        safe_zones = analysis_result.get("safe_zones", [])
        safe_path = analysis_result.get("safe_path")
        overall_safety = analysis_result.get("overall_safety", 0.5)

        # Draw danger zones
        for zone in danger_zones:
            if zone.danger_level == "emergency":
                color = (0, 0, 255)  # Red
                thickness = 3
            elif zone.danger_level == "danger":
                color = (0, 100, 255)  # Orange-red
                thickness = 2
            elif zone.danger_level == "warning":
                color = (0, 255, 255)  # Yellow
                thickness = 1
            else:
                continue

            cv2.rectangle(frame, (zone.x1, zone.y1), (zone.x2, zone.y2), color, thickness)

        # Draw safe zones (subtle)
        for zone in safe_zones[:3]:  # Limit to avoid clutter
            cv2.rectangle(frame, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 255, 0), 1)

        # Draw safe path arrow
        if safe_path:
            h, w = frame.shape[:2]
            if safe_path == "left":
                pt1 = (w // 2, h // 2)
                pt2 = (w // 4, h // 2)
            elif safe_path == "right":
                pt1 = (w // 2, h // 2)
                pt2 = (3 * w // 4, h // 2)
            else:  # center
                pt1 = (w // 2, h // 2)
                pt2 = (w // 2, h // 4)

            cv2.arrowedLine(frame, pt1, pt2, (0, 255, 0), 2, tipLength=0.2)

        # Draw safety info
        threat_color = (0, 255, 0) if overall_safety > 0.7 else (0, 255, 255) if overall_safety > 0.3 else (0, 0, 255)
        cv2.putText(
            frame,
            f"Safety: {overall_safety * 100:.0f}%",
            (10, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            threat_color,
            2,
        )

        return frame

    def get_directional_guidance(self, analysis_result: Dict) -> Optional[str]:
        """
        Get actionable directional guidance based on analysis.
        """
        safe_path = analysis_result.get("safe_path")
        overall_safety = analysis_result.get("overall_safety", 0.5)

        if overall_safety < 0.2:
            return "STOP. Multiple hazards detected."
        elif safe_path == "left":
            return "Move left for safety."
        elif safe_path == "right":
            return "Move right for safety."
        elif safe_path == "center":
            return "Move straight ahead carefully."
        else:
            return "Multiple hazards. Proceed with extreme caution."
