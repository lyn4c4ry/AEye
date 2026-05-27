"""
BlindAssist — Ultimate Real-Time Tracking & Memory Optimization Module
Fixed: Anti-Lag Interrupter, Small Object Close Proximity, and Absolute Human Priority
"""

import sys
import time
import cv2
import numpy as np

from config import (
    FRAME_SKIP, WINDOW_TITLE, SHOW_FPS, ALERT_COOLDOWN,
    ENABLE_HAZARD_DETECTION, MOTION_ANALYSIS_ENABLED,
    VOICE_FEEDBACK_GLOBAL_COOLDOWN
)
from core.camera import Camera
from detection.detector import Detector
from utils.fps_counter import FPSCounter
from depth_estimator import DepthEstimator
from motion_tracker import MotionTracker
from voice_assistant import VoiceAssistant
from hazard_analyzer import HazardAnalyzer, HazardLevel
from motion_analyzer import MotionAnalyzer
from voice_feedback_manager import VoiceFeedbackManager, FeedbackPriority

depth_estimator = DepthEstimator()

COLOR_PERSON   = (0, 255, 120)
COLOR_OBSTACLE = (0, 140, 255)
COLOR_DIM      = (70, 70, 70)


def draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2):
    lx = max(12, (x2 - x1) // 5); ly = max(12, (y2 - y1) // 5)
    cv2.line(frame, (x1, y1), (x1 + lx, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + ly), color, thickness)
    cv2.line(frame, (x2, y1), (x2 - lx, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + ly), color, thickness)
    cv2.line(frame, (x1, y2), (x1 + lx, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - ly), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - lx, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - ly, y2), color, thickness)

def draw_detections(frame, detections):
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        color = COLOR_PERSON if det.is_person else COLOR_OBSTACLE if det.is_close else COLOR_DIM
        draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2)
        label_text = f"{det.label} {det.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        lx = x1 + 2; ly = y1 - 6 if y1 - th - 8 >= 0 else y2 + th + 6
        cv2.rectangle(frame, (lx - 2, ly - th - 3), (lx + tw + 3, ly + 2), (12, 12, 12), -1)
        cv2.putText(frame, label_text, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return frame


def main():
    print("=" * 50)
    print("  BlindAssist — Hazard Detection Mode")
    print("=" * 50)

    camera = Camera()
    detector = Detector()
    fps_ctr = FPSCounter()
    assistant = VoiceAssistant(global_cooldown=ALERT_COOLDOWN)

    # Initialize new hazard detection components
    if ENABLE_HAZARD_DETECTION:
        hazard_analyzer = HazardAnalyzer()
        feedback_manager = VoiceFeedbackManager(
            global_cooldown=VOICE_FEEDBACK_GLOBAL_COOLDOWN
        )
        print("[Hazard Detection] Enabled")
    else:
        hazard_analyzer = None
        feedback_manager = None

    # Initialize motion analysis
    if MOTION_ANALYSIS_ENABLED:
        motion_analyzer = None  # Will be initialized after first frame
        print("[Motion Analysis] Enabled")
    else:
        motion_analyzer = None

    if not camera.open():
        sys.exit(1)

    tracker = None
    frame_count = 0
    detections = []
    depth_result = None

    # ── ARCHITECTURAL MEMORY AND STABILITY AREAS ─────────────────────────────
    start_time = time.time()
    initial_scan_done = False

    tracked_environment_memory = {}
    buffered_scan_objects = {}

    # Human Navigation Tracking Memory
    is_person_in_room = False
    person_missing_frames = 0
    person_distance_state = "unknown"
    person_last_direction = "unknown"

    print("\n[Main Loop] Running — press 'q' to quit\n")

    while True:
        try:
            ret, frame = camera.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue
        except Exception:
            time.sleep(0.02)
            continue

        frame_count += 1
        fps_ctr.tick()

        if tracker is None:
            tracker = MotionTracker(frame.shape[1])

        # Initialize motion analyzer on first frame
        if MOTION_ANALYSIS_ENABLED and motion_analyzer is None:
            motion_analyzer = MotionAnalyzer(frame.shape[1], frame.shape[0])

        depth_result = depth_estimator.estimate(frame)

        # ── HAZARD DETECTION ANALYSIS ────────────────────────────────────────
        motion_data = None
        hazard_events = []

        # Perform motion analysis (detects abnormal motion patterns)
        if MOTION_ANALYSIS_ENABLED and motion_analyzer is not None:
            motion_result = motion_analyzer.analyze(frame)
            motion_data = motion_analyzer.get_motion_data_for_detection(detections)

            # Alert on abnormal motion with detailed description
            if motion_result["is_abnormal"] and motion_result.get("description"):
                description = motion_result["description"]
                # Determine priority based on severity
                if "Danger" in description or "fast" in description.lower():
                    priority = FeedbackPriority.HIGH
                    unique_key = "motion_danger"
                    cooldown = 2.0
                    force = True
                else:
                    priority = FeedbackPriority.NORMAL
                    unique_key = "motion_warning"
                    cooldown = 3.0
                    force = False
                
                feedback_manager.add_feedback(
                    description, unique_key, priority, cooldown=cooldown, force=force
                )

        # ── YOLO GEOMETRIC RISK ANALYSIS ──────────────────────────────────────
        if frame_count % FRAME_SKIP == 0:
            detections = detector.detect(frame)
            tracker.update(detections)
            analysis = tracker.analyze(detections)

            # Perform hazard analysis (combines multiple detections)
            if ENABLE_HAZARD_DETECTION and hazard_analyzer is not None:
                hazard_events = hazard_analyzer.analyze(detections, depth_result, motion_data)

                # Process hazard events and convert to voice feedback
                for hazard in hazard_events:
                    message, unique_key, priority = feedback_manager.hazard_to_feedback(
                        hazard.hazard_type,
                        hazard.level.value,
                        hazard.location,
                        hazard.message,
                    )

                    # Determine cooldown based on hazard level
                    if hazard.level == HazardLevel.EMERGENCY:
                        cooldown = 1.0
                        is_force = True
                    elif hazard.level == HazardLevel.DANGER:
                        cooldown = 2.0
                        is_force = True
                    elif hazard.level == HazardLevel.WARNING:
                        cooldown = 3.0
                        is_force = False
                    else:
                        cooldown = 5.0
                        is_force = False

                    feedback_manager.add_feedback(
                        message, unique_key, priority, cooldown=cooldown, force=is_force
                    )

            active_this_frame = {}
            current_person_det = None
            current_person_direction = "ahead"

            for obj in analysis:
                label = obj["label"]
                zone = obj["zone"]
                direction = (
                    "on the left"
                    if "left" in zone
                    else "on the right"
                    if "right" in zone
                    else "ahead"
                )

                matched_det = None
                for d in detections:
                    if d.label == label:
                        matched_det = d
                        break

                if matched_det:
                    area = matched_det.area_ratio

                    # Cell phone gets special attention even when small
                    if label == "cell phone" and area >= 0.015:
                        dist_str = "very close"
                    else:
                        dist_str = (
                            "very close"
                            if area >= 0.075
                            else "at medium distance"
                            if area >= 0.022
                            else "far away"
                        )

                    if label == "person":
                        current_person_det = matched_det
                        current_person_direction = direction
                    else:
                        active_this_frame[(label, direction)] = dist_str

            # --- PHASE 1: INITIAL ENVIRONMENT SETUP (3 SECONDS) ---
            if not initial_scan_done:
                if current_person_det:
                    is_person_in_room = True
                    area = current_person_det.area_ratio
                    person_distance_state = (
                        "very close"
                        if area >= 0.075
                        else "at medium distance"
                        if area >= 0.022
                        else "far away"
                    )
                    person_last_direction = current_person_direction

                for (label, direction), dist_str in active_this_frame.items():
                    buffered_scan_objects[(label, direction)] = dist_str

                if time.time() - start_time > 3.0:
                    assistant.speak(
                        "Environment scan ready.", unique_key="scan_init", priority=1, force=True
                    )
                    if is_person_in_room:
                        assistant.speak(
                            f"A person is {person_last_direction} and {person_distance_state}.",
                            unique_key="init_person",
                            priority=1,
                        )
                    for (label, direction), dist_str in buffered_scan_objects.items():
                        assistant.speak(
                            f"Detected a {label} {direction}, {dist_str}.",
                            unique_key=f"init:{label}",
                            priority=2,
                        )
                        tracked_environment_memory[(label, direction)] = {
                            "score": 35,
                            "distance": dist_str,
                        }
                    initial_scan_done = True

            # --- PHASE 2: REAL-TIME NAVIGATION WITH INTERRUPTS ---
            else:
                # A) ABSOLUTE PRIORITY: PERSON AND CELL PHONE TRACKING
                if current_person_det:
                    person_missing_frames = 0
                    area = current_person_det.area_ratio
                    new_dist_state = (
                        "very close"
                        if area >= 0.075
                        else "at medium distance"
                        if area >= 0.022
                        else "far away"
                    )

                    if not is_person_in_room:
                        assistant.speak(
                            f"A person entered {current_person_direction}.",
                            unique_key="person_entry",
                            priority=1,
                            force=True,
                        )
                        is_person_in_room = True
                        person_distance_state = new_dist_state
                        person_last_direction = current_person_direction
                    else:
                        # Direction change: immediately interrupt and announce
                        if current_person_direction != person_last_direction:
                            assistant.speak(
                                f"Person moved {current_person_direction}.",
                                unique_key="p_direction_change",
                                priority=1,
                                force=True,
                            )
                            person_last_direction = current_person_direction

                        # Distance change: critical and immediate interrupt
                        if new_dist_state != person_distance_state:
                            if new_dist_state == "very close":
                                assistant.speak(
                                    "Warning! A person is getting very close to you.",
                                    unique_key="p_close",
                                    priority=1,
                                    force=True,
                                )
                            elif (
                                new_dist_state == "at medium distance"
                                and person_distance_state == "very close"
                            ):
                                assistant.speak(
                                    "Person is moving away.",
                                    unique_key="p_away",
                                    priority=1,
                                    force=True,
                                )
                            elif (
                                new_dist_state == "at medium distance"
                                and person_distance_state == "far away"
                            ):
                                assistant.speak(
                                    "A person is walking towards you.",
                                    unique_key="p_toward",
                                    priority=1,
                                    force=True,
                                )

                            person_distance_state = new_dist_state
                else:
                    if is_person_in_room:
                        person_missing_frames += 1
                        if person_missing_frames >= 15:
                            assistant.speak(
                                "Person left the area.",
                                unique_key="person_exit",
                                priority=1,
                                force=True,
                            )
                            is_person_in_room = False
                            person_distance_state = "unknown"
                            person_last_direction = "unknown"

                # B) OTHER OBJECTS AND CELL PHONE SPECIAL FILTER
                for (label, direction), dist_str in active_this_frame.items():
                    # Cell phone gets special priority
                    if label == "cell phone" and dist_str == "very close":
                        assistant.speak(
                            "Warning! A cell phone is very close in front of you.",
                            unique_key="cell_close",
                            priority=1,
                            force=True,
                        )
                        continue

                    if (label, direction) not in tracked_environment_memory:
                        tracked_environment_memory[(label, direction)] = {
                            "score": 1,
                            "distance": dist_str,
                        }
                    else:
                        # Increase score with tolerance for background object flickering
                        tracked_environment_memory[(label, direction)]["score"] = min(
                            35,
                            tracked_environment_memory[(label, direction)]["score"] + 1,
                        )
                        if (
                            tracked_environment_memory[(label, direction)]["distance"]
                            != dist_str
                        ):
                            assistant.speak(
                                f"{label} {direction} is now {dist_str}.",
                                unique_key=f"move:{label}",
                                priority=2,
                            )
                            tracked_environment_memory[(label, direction)][
                                "distance"
                            ] = dist_str

                    if tracked_environment_memory[(label, direction)]["score"] == 4:
                        assistant.speak(
                            f"New object: {label} {direction}, {dist_str}.",
                            unique_key=f"new:{label}",
                            priority=2,
                        )

                # Remove objects that disappeared from environment
                keys_to_delete = []
                for (label, direction), data in tracked_environment_memory.items():
                    if (label, direction) not in active_this_frame:
                        data["score"] = max(0, data["score"] - 1)
                        if data["score"] == 0:
                            assistant.speak(
                                f"{label} removed from {direction}.",
                                unique_key=f"rem:{label}",
                                priority=2,
                            )
                            keys_to_delete.append((label, direction))
                for k in keys_to_delete:
                    del tracked_environment_memory[k]

        # ── HUD AND SCREEN DRAWING ────────────────────────────────────────────
        if depth_result is not None:
            try:
                frame = depth_estimator.draw_overlay(frame, depth_result)
            except Exception:
                pass

        frame = draw_detections(frame, detections)

        # Draw hazard information overlay (optional visualization)
        if ENABLE_HAZARD_DETECTION and hazard_analyzer is not None:
            danger_zones = hazard_analyzer.get_danger_zones()
            frame = _draw_hazard_overlay(frame, danger_zones, hazard_analyzer.active_hazards)

        cv2.imshow(WINDOW_TITLE, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
    assistant.stop()


def _draw_hazard_overlay(frame, danger_zones, active_hazards):
    """
    Draw hazard zone visualization on frame.
    Shows safe vs danger zones in different colors.
    """
    h, w = frame.shape[:2]
    third_w = w // 3

    # Color coding: green=safe, yellow=warning, red=danger
    colors = {"safe": (0, 255, 0), "warning": (0, 255, 255), "danger": (0, 0, 255)}

    # Draw vertical zones
    for i, (zone_name, zone_status) in enumerate(danger_zones.items()):
        x1 = i * third_w
        x2 = (i + 1) * third_w if i < 2 else w
        color = colors[zone_status]

        # Draw semi-transparent zone indicator
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, 0), (x2, 30), color, -1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

        # Draw zone label
        label = f"{zone_name}: {zone_status.upper()}"
        cv2.putText(
            frame,
            label,
            (x1 + 10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
        )

    # Draw active hazards count
    if active_hazards:
        hazard_count = len(active_hazards)
        cv2.putText(
            frame,
            f"Active Hazards: {hazard_count}",
            (10, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
        )

    return frame


if __name__ == "__main__":
    main()