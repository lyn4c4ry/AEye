"""
hazard_analyzer.py — Dynamic Hazard Detection System
Combines multiple detections to infer dangerous situations.
Provides context-based hazard analysis for visually impaired users.

Features:
- Context-based hazard detection (cones+barriers+workers→"Road work")
- Environmental hazard detection (smoke, fire, etc.)
- Crowded/fast movement detection
- Hazard prioritization (INFO, WARNING, DANGER, EMERGENCY)
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Tuple
import numpy as np


class HazardLevel(Enum):
    """Hazard priority levels."""
    INFO = 0
    WARNING = 1
    DANGER = 2
    EMERGENCY = 3


@dataclass
class HazardEvent:
    """Represents a detected hazard."""
    hazard_type: str          # e.g., "road_work", "approaching_vehicle"
    level: HazardLevel        # Priority level
    message: str              # Voice message to announce
    duration: float           # How long to track this hazard (seconds)
    location: str             # Where it is: "left", "center", "right", "ahead"
    confidence: float         # 0.0 to 1.0
    unique_key: str           # For deduplication
    timestamp: float          # When detected
    is_recurring: bool        # Whether to re-alert if it persists


class HazardAnalyzer:
    """
    Analyzes detected objects and environmental data to infer hazardous situations.
    Combines multiple detections for context-aware hazard detection.
    """

    # Hazard type definitions with their characteristics
    HAZARD_DEFINITIONS = {
        "road_work": {
            "triggers": ["traffic cone", "stop sign", "sports person"],
            "level": HazardLevel.WARNING,
            "message": "Road work ahead.",
            "duration": 5.0,
        },
        "approaching_vehicle": {
            "triggers": ["car", "truck", "bus", "motorcycle"],
            "level": HazardLevel.DANGER,
            "message": "Vehicle approaching quickly.",
            "duration": 3.0,
        },
        "fire_hazard": {
            "triggers": ["fire", "smoke"],
            "level": HazardLevel.DANGER,
            "message": "Danger, fire detected.",
            "duration": 10.0,
        },
        "collision_risk": {
            "triggers": ["person"],
            "level": HazardLevel.WARNING,
            "message": "Person moving towards you.",
            "duration": 3.0,
        },
    }

    def __init__(self):
        self.active_hazards: Dict[str, HazardEvent] = {}
        self.hazard_history: List[HazardEvent] = []
        self.last_hazard_alert: Dict[str, float] = {}
        self.frame_count = 0

    def analyze(
        self,
        detections: List,
        depth_result: Optional[object] = None,
        motion_data: Optional[Dict] = None,
    ) -> List[HazardEvent]:
        """
        Main analysis method.
        
        Args:
            detections: List of Detection objects from YOLO
            depth_result: Depth estimation result (optional)
            motion_data: Motion tracking data (optional)
        
        Returns:
            List of new or critical HazardEvent objects to announce
        """
        self.frame_count += 1
        current_time = time.time()
        new_hazards = []

        # Clean expired hazards
        expired_keys = [
            k for k, h in self.active_hazards.items()
            if current_time - h.timestamp > h.duration
        ]
        for key in expired_keys:
            del self.active_hazards[key]

        # Perform various analyses
        new_hazards.extend(self._detect_approaching_objects(detections, motion_data))
        new_hazards.extend(self._detect_environmental_hazards(detections))
        new_hazards.extend(self._detect_collision_risk(detections, motion_data))
        new_hazards.extend(self._detect_context_hazards(detections))

        # Add new hazards to active set
        for hazard in new_hazards:
            self.active_hazards[hazard.unique_key] = hazard
            self.hazard_history.append(hazard)

        # Return only critical/new hazards to announce
        return self._filter_for_announcement(new_hazards, current_time)

    def _detect_approaching_objects(
        self, detections: List, motion_data: Optional[Dict]
    ) -> List[HazardEvent]:
        """
        Detect objects approaching quickly.
        Risk = (velocity × object_priority) / distance
        """
        hazards = []

        # High-priority approaching objects
        high_priority_classes = {
            "car": 10,
            "truck": 12,
            "bus": 11,
            "motorcycle": 8,
            "person": 5,
        }

        for det in detections:
            if det.label not in high_priority_classes:
                continue

            # Skip if far away
            if det.area_ratio < 0.015:
                continue

            priority_weight = high_priority_classes[det.label]

            # Estimate velocity from motion data
            velocity = 1.0  # Default velocity multiplier
            if motion_data and det.label in motion_data:
                velocity = motion_data[det.label].get("velocity", 1.0)

            # Calculate risk score
            risk_score = (velocity * priority_weight) / max(det.area_ratio, 0.01)

            # If high risk, generate hazard
            if risk_score > 5.0:
                direction = self._get_direction(det.center, det.bbox)
                
                # Create detailed message based on object type and distance
                if det.area_ratio > 0.08:
                    message = f"Warning: {det.label.capitalize()} is very close to you on the {direction}. Move away immediately."
                elif det.area_ratio > 0.04:
                    message = f"Warning: {det.label.capitalize()} is approaching quickly from the {direction}."
                else:
                    message = f"Warning: {det.label.capitalize()} is moving toward you from the {direction}."
                
                hazard = HazardEvent(
                    hazard_type="approaching_object",
                    level=HazardLevel.DANGER if risk_score > 10.0 else HazardLevel.WARNING,
                    message=message,
                    duration=3.0,
                    location=direction,
                    confidence=min(risk_score / 15.0, 1.0),
                    unique_key=f"approach_{det.label}",
                    timestamp=time.time(),
                    is_recurring=False,
                )
                hazards.append(hazard)

        return hazards

    def _detect_environmental_hazards(self, detections: List) -> List[HazardEvent]:
        """Detect environmental hazards like smoke, fire."""
        hazards = []
        hazard_classes = {
            "fire": HazardLevel.EMERGENCY,
            "smoke": HazardLevel.DANGER,
        }

        for det in detections:
            if det.label in hazard_classes:
                location = self._get_direction(det.center, det.bbox)
                message = f"Emergency: {det.label.upper()} detected {location}. Evacuate immediately."
                
                hazard = HazardEvent(
                    hazard_type=f"{det.label}_detected",
                    level=hazard_classes[det.label],
                    message=message,
                    duration=5.0,
                    location=location,
                    confidence=det.confidence,
                    unique_key=f"env_{det.label}",
                    timestamp=time.time(),
                    is_recurring=True,
                )
                hazards.append(hazard)

        return hazards

    def _detect_collision_risk(
        self, detections: List, motion_data: Optional[Dict]
    ) -> List[HazardEvent]:
        """Detect collision risk with people."""
        hazards = []

        for det in detections:
            if det.label != "person":
                continue

            # High collision risk if person is close and moving toward camera
            if det.area_ratio > 0.05:  # Very close
                # Check if person is in central zone (most dangerous)
                is_center = 0.35 < det.center[0] / 640 < 0.65  # Assuming 640 width

                if is_center:
                    message = "Danger: Person is directly ahead and very close. Collision risk! Move immediately left or right."
                    
                    hazard = HazardEvent(
                        hazard_type="collision_risk",
                        level=HazardLevel.DANGER,
                        message=message,
                        duration=2.0,
                        location="ahead",
                        confidence=0.9,
                        unique_key="collision_risk",
                        timestamp=time.time(),
                        is_recurring=False,
                    )
                    hazards.append(hazard)

        return hazards

    def _detect_context_hazards(self, detections: List) -> List[HazardEvent]:
        """Detect hazards based on context (combining multiple objects)."""
        hazards = []

        # Extract labels from current detections
        labels = {det.label for det in detections}

        # Road work detection: cones + barriers + workers
        work_indicators = {"traffic cone", "stop sign", "person"}
        if len(labels & work_indicators) >= 2:
            message = "Warning: Road work area detected ahead. Traffic cones, equipment, or construction workers present. Proceed with extreme caution."
            
            hazard = HazardEvent(
                hazard_type="road_work",
                level=HazardLevel.WARNING,
                message=message,
                duration=5.0,
                location="ahead",
                confidence=0.85,
                unique_key="road_work",
                timestamp=time.time(),
                is_recurring=True,
            )
            hazards.append(hazard)

        return hazards

    def _get_direction(self, center: Tuple[int, int], bbox: Tuple) -> str:
        """Determine direction based on position in frame."""
        cx = center[0]
        frame_width = 640  # Standard assumption; can be passed in

        if cx < frame_width / 3:
            return "left"
        elif cx > 2 * frame_width / 3:
            return "right"
        else:
            return "ahead"

    def _filter_for_announcement(
        self, hazards: List[HazardEvent], current_time: float
    ) -> List[HazardEvent]:
        """
        Filter hazards to only announce the most critical ones.
        Avoid overwhelming the user.
        """
        # Always announce EMERGENCY level
        critical_hazards = [h for h in hazards if h.level in [HazardLevel.EMERGENCY]]

        # Announce DANGER level if not recently announced
        for hazard in hazards:
            if hazard.level == HazardLevel.DANGER:
                last_time = self.last_hazard_alert.get(hazard.unique_key, 0)
                if current_time - last_time > 2.0:  # 2 second cooldown
                    critical_hazards.append(hazard)
                    self.last_hazard_alert[hazard.unique_key] = current_time

        return critical_hazards

    def get_active_hazards(self) -> List[HazardEvent]:
        """Get all currently active hazards."""
        return list(self.active_hazards.values())

    def get_danger_zones(self) -> Dict[str, str]:
        """
        Analyze current detections to determine safe vs. dangerous zones.
        Returns: {"left": "danger", "center": "safe", "right": "warning"}
        """
        zones = {"left": "safe", "center": "safe", "right": "safe", "ahead": "safe"}

        for hazard in self.active_hazards.values():
            # Map "ahead" to "center" for danger assessment
            zone_key = "center" if hazard.location == "ahead" else hazard.location
            
            if hazard.level in [HazardLevel.EMERGENCY, HazardLevel.DANGER]:
                zones[zone_key] = "danger"
            elif hazard.level == HazardLevel.WARNING:
                if zones.get(zone_key, "safe") != "danger":
                    zones[zone_key] = "warning"

        return zones
