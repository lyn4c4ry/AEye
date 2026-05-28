"""
BlindAssist — Ultimate Real-Time Tracking & Memory Optimization Module
Entegrasyon: DangerZoneAnalyzer, HazardAnalyzer, MotionAnalyzer, VoiceFeedbackManager
"""

import sys
import time
import cv2
import numpy as np

from config import (
    FRAME_SKIP, WINDOW_TITLE, SHOW_FPS, ALERT_COOLDOWN,
    ENABLE_HAZARD_DETECTION,
    MOTION_ANALYSIS_ENABLED,
    VOICE_FEEDBACK_GLOBAL_COOLDOWN,
)
from core.camera import Camera
from detection.detector import Detector
from utils.fps_counter import FPSCounter
from depth_estimator import DepthEstimator
from motion_tracker import MotionTracker
from voice_assistant import VoiceAssistant

# ── Kişi 4 modülleri ─────────────────────────────────────────────────────────
from danger_zone_analyzer import DangerZoneAnalyzer
from hazard_analyzer import HazardAnalyzer, HazardLevel
from motion_analyzer import MotionAnalyzer
from voice_feedback_manager import VoiceFeedbackManager, FeedbackPriority

depth_estimator = DepthEstimator()

COLOR_PERSON   = (0, 255, 120)
COLOR_OBSTACLE = (0, 140, 255)
COLOR_DIM      = (70, 70, 70)


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı çizim fonksiyonları
# ─────────────────────────────────────────────────────────────────────────────

def draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2):
    lx = max(12, (x2 - x1) // 5)
    ly = max(12, (y2 - y1) // 5)
    cv2.line(frame, (x1, y1), (x1 + lx, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + ly), color, thickness)
    cv2.line(frame, (x2, y1), (x2 - lx, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + ly), color, thickness)
    cv2.line(frame, (x1, y2), (x1 + lx, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - ly), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - lx, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - ly), color, thickness)


def draw_detections(frame, detections):
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        color = COLOR_PERSON if det.is_person else COLOR_OBSTACLE if det.is_close else COLOR_DIM
        draw_corner_box(frame, x1, y1, x2, y2, color, thickness=2)
        label_text = f"{det.label} {det.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        lx = x1 + 2
        ly = y1 - 6 if y1 - th - 8 >= 0 else y2 + th + 6
        cv2.rectangle(frame, (lx - 2, ly - th - 3), (lx + tw + 3, ly + 2), (12, 12, 12), -1)
        cv2.putText(frame, label_text, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return frame


# ─────────────────────────────────────────────────────────────────────────────
# Ana döngü
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  BlindAssist — Fully Stabilized Assistant Mode")
    print("=" * 50)

    camera   = Camera()
    detector = Detector()
    fps_ctr  = FPSCounter()
    assistant = VoiceAssistant(global_cooldown=ALERT_COOLDOWN)

    if not camera.open():
        sys.exit(1)

    # Çözünürlük bilgisini al (ilk frame gelmeden boyutları bilmiyoruz,
    # geçici 1280x720 ile başlatıp ilk frame'de yeniden oluşturuyoruz)
    FRAME_W, FRAME_H = 1280, 720

    # ── Kişi 4 — modül başlatma ───────────────────────────────────────────────
    danger_analyzer  = DangerZoneAnalyzer(FRAME_W, FRAME_H, grid_size=6)
    hazard_analyzer  = HazardAnalyzer()
    motion_analyzer  = MotionAnalyzer(FRAME_W, FRAME_H)
    feedback_manager = VoiceFeedbackManager(global_cooldown=VOICE_FEEDBACK_GLOBAL_COOLDOWN)

    # Kişi 4 modülleri frame boyutuna göre yeniden oluşturuldu mu?
    p4_initialized = False

    tracker     = None
    frame_count = 0
    detections  = []
    depth_result = None

    # ── Ortam hafızası ────────────────────────────────────────────────────────
    start_time           = time.time()
    initial_scan_done    = False
    tracked_environment_memory = {}
    buffered_scan_objects      = {}

    # İnsan takip hafızası
    is_person_in_room     = False
    person_missing_frames = 0
    person_distance_state = "unknown"
    person_last_direction = "unknown"

    print("\n[Main Loop] Running — press 'q' to quit\n")

    while True:
        # ── Frame oku ─────────────────────────────────────────────────────────
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

        # ── İlk frame'de gerçek boyutu al, Kişi 4 modüllerini yeniden init et
        if not p4_initialized:
            FRAME_H, FRAME_W = frame.shape[:2]
            danger_analyzer  = DangerZoneAnalyzer(FRAME_W, FRAME_H, grid_size=6)
            motion_analyzer  = MotionAnalyzer(FRAME_W, FRAME_H)
            p4_initialized   = True

        if tracker is None:
            tracker = MotionTracker(frame.shape[1])

        # ── Derinlik tahmini (thread'de, bloklamaz) ───────────────────────────
        depth_result = depth_estimator.estimate(frame)

        # ── Motion analizi (Kişi 4 — her frame'de çalışır) ───────────────────
        motion_result = None
        if MOTION_ANALYSIS_ENABLED:
            motion_result = motion_analyzer.analyze(frame)

            # Anormal hareket uyarısı → VoiceFeedbackManager'a ilet
            if motion_result.get("is_abnormal"):
                desc = motion_result.get("description", "")
                if desc:
                    msg, key, pri = feedback_manager.hazard_to_feedback(
                        "abnormal_motion", level=1, custom_message=desc
                    )
                    feedback_manager.add_feedback(msg, key, pri, cooldown=3.0)

        # ── YOLO + tracker her FRAME_SKIP'te ──────────────────────────────────
        if frame_count % FRAME_SKIP == 0:
            detections = detector.detect(frame)
            tracker.update(detections)
            analysis = tracker.analyze(detections)

            # ── Kişi 4 — Tehlike bölgesi analizi ─────────────────────────────
            p4_danger_result = None
            if ENABLE_HAZARD_DETECTION and detections:
                depth_map_for_p4 = depth_result.depth_map if depth_result is not None else None
                p4_danger_result = danger_analyzer.analyze(detections, depth_map=depth_map_for_p4)

                # Güvenli yön sesli rehberlik
                guidance = danger_analyzer.get_directional_guidance(p4_danger_result)
                if guidance:
                    overall_safety = p4_danger_result.get("overall_safety", 1.0)
                    level = 2 if overall_safety < 0.3 else 1 if overall_safety < 0.6 else 0
                    msg, key, pri = feedback_manager.hazard_to_feedback(
                        "safe_path", level=level, custom_message=guidance
                    )
                    feedback_manager.add_feedback(msg, key, pri, cooldown=4.0)

            # ── Kişi 4 — HazardAnalyzer ──────────────────────────────────────
            if ENABLE_HAZARD_DETECTION and detections:
                motion_data = None
                if motion_result:
                    motion_data = motion_analyzer.get_motion_data_for_detection(detections)

                hazard_events = hazard_analyzer.analyze(
                    detections,
                    depth_result=depth_result,
                    motion_data=motion_data,
                )

                for event in hazard_events:
                    # HazardLevel → int dönüşümü
                    level_int = event.level.value  # INFO=0, WARNING=1, DANGER=2, EMERGENCY=3
                    msg, key, pri = feedback_manager.hazard_to_feedback(
                        event.hazard_type,
                        level=level_int,
                        location=event.location,
                        custom_message=event.message,
                    )
                    force = event.level in (HazardLevel.EMERGENCY, HazardLevel.DANGER)
                    feedback_manager.add_feedback(msg, key, pri, cooldown=2.0, force=force)

            # ── Kişi 4 — VoiceFeedbackManager → VoiceAssistant'a aktar ───────
            while True:
                msg, key = feedback_manager.get_next_feedback()
                if msg is None:
                    break
                # FeedbackPriority → assistant priority (0=en yüksek)
                # VoiceAssistant'ın priority parametresi: 1=acil, 2=normal
                priority = 1 if "emergency" in key or "danger" in key else 2
                force    = priority == 1
                assistant.speak(msg, unique_key=f"p4:{key}", priority=priority, force=force)

            # ── Orijinal navigasyon mantığı (Kişi 1 kodu korundu) ─────────────
            active_this_frame      = {}
            current_person_det     = None
            current_person_direction = "ahead"

            for obj in analysis:
                label     = obj['label']
                zone      = obj['zone']
                direction = (
                    "on the left"  if "left"  in zone else
                    "on the right" if "right" in zone else
                    "ahead"
                )

                matched_det = next((d for d in detections if d.label == label), None)
                if matched_det:
                    area = matched_det.area_ratio
                    if label == "cell phone" and area >= 0.015:
                        dist_str = "very close"
                    else:
                        dist_str = (
                            "very close"        if area >= 0.075 else
                            "at medium distance" if area >= 0.022 else
                            "far away"
                        )

                    if label == "person":
                        current_person_det       = matched_det
                        current_person_direction = direction
                    else:
                        active_this_frame[(label, direction)] = dist_str

            # ── Aşama 1: İlk ortam kurulumu (3 saniye) ───────────────────────
            if not initial_scan_done:
                if current_person_det:
                    is_person_in_room = True
                    area = current_person_det.area_ratio
                    person_distance_state = (
                        "very close"        if area >= 0.075 else
                        "at medium distance" if area >= 0.022 else
                        "far away"
                    )
                    person_last_direction = current_person_direction

                for (label, direction), dist_str in active_this_frame.items():
                    buffered_scan_objects[(label, direction)] = dist_str

                if time.time() - start_time > 3.0:
                    assistant.speak("Environment scan ready.", unique_key="scan_init", priority=1, force=True)
                    if is_person_in_room:
                        assistant.speak(
                            f"A person is {person_last_direction} and {person_distance_state}.",
                            unique_key="init_person", priority=1,
                        )
                    for (label, direction), dist_str in buffered_scan_objects.items():
                        assistant.speak(
                            f"Detected a {label} {direction}, {dist_str}.",
                            unique_key=f"init:{label}", priority=2,
                        )
                        tracked_environment_memory[(label, direction)] = {
                            "score": 35, "distance": dist_str
                        }
                    initial_scan_done = True

            # ── Aşama 2: Gerçek zamanlı navigasyon ───────────────────────────
            else:
                # A) İnsan takibi
                if current_person_det:
                    person_missing_frames = 0
                    area = current_person_det.area_ratio
                    new_dist_state = (
                        "very close"        if area >= 0.075 else
                        "at medium distance" if area >= 0.022 else
                        "far away"
                    )

                    if not is_person_in_room:
                        assistant.speak(
                            f"A person entered {current_person_direction}.",
                            unique_key="person_entry", priority=1, force=True,
                        )
                        is_person_in_room     = True
                        person_distance_state = new_dist_state
                        person_last_direction = current_person_direction
                    else:
                        if current_person_direction != person_last_direction:
                            assistant.speak(
                                f"Person moved {current_person_direction}.",
                                unique_key="p_direction_change", priority=1, force=True,
                            )
                            person_last_direction = current_person_direction

                        if new_dist_state != person_distance_state:
                            if new_dist_state == "very close":
                                assistant.speak(
                                    "Warning! A person is getting very close to you.",
                                    unique_key="p_close", priority=1, force=True,
                                )
                            elif new_dist_state == "at medium distance" and person_distance_state == "very close":
                                assistant.speak("Person is moving away.", unique_key="p_away", priority=1, force=True)
                            elif new_dist_state == "at medium distance" and person_distance_state == "far away":
                                assistant.speak("A person is walking towards you.", unique_key="p_toward", priority=1, force=True)
                            person_distance_state = new_dist_state
                else:
                    if is_person_in_room:
                        person_missing_frames += 1
                        if person_missing_frames >= 15:
                            assistant.speak("Person left the area.", unique_key="person_exit", priority=1, force=True)
                            is_person_in_room     = False
                            person_distance_state = "unknown"
                            person_last_direction = "unknown"

                # B) Diğer nesneler
                for (label, direction), dist_str in active_this_frame.items():
                    if label == "cell phone" and dist_str == "very close":
                        assistant.speak(
                            "Warning! A cell phone is very close in front of you.",
                            unique_key="cell_close", priority=1, force=True,
                        )
                        continue

                    if (label, direction) not in tracked_environment_memory:
                        tracked_environment_memory[(label, direction)] = {"score": 1, "distance": dist_str}
                    else:
                        mem = tracked_environment_memory[(label, direction)]
                        mem["score"] = min(35, mem["score"] + 1)
                        if mem["distance"] != dist_str:
                            assistant.speak(
                                f"{label} {direction} is now {dist_str}.",
                                unique_key=f"move:{label}", priority=2,
                            )
                            mem["distance"] = dist_str

                    if tracked_environment_memory[(label, direction)]["score"] == 4:
                        assistant.speak(
                            f"New object: {label} {direction}, {dist_str}.",
                            unique_key=f"new:{label}", priority=2,
                        )

                # Ortamdan kaybolanları sil
                keys_to_delete = []
                for (label, direction), data in tracked_environment_memory.items():
                    if (label, direction) not in active_this_frame:
                        data["score"] = max(0, data["score"] - 1)
                        if data["score"] == 0:
                            assistant.speak(
                                f"{label} removed from {direction}.",
                                unique_key=f"rem:{label}", priority=2,
                            )
                            keys_to_delete.append((label, direction))
                for k in keys_to_delete:
                    del tracked_environment_memory[k]

            # ── Depth alert'leri TTS'e ilet ───────────────────────────────────
            if depth_result is not None:
                for alert in depth_result.prop_alerts:
                    assistant.speak(alert, unique_key=f"depth:{alert}", priority=2)

        # ── HUD ve ekran çizimi ───────────────────────────────────────────────
        if depth_result is not None:
            try:
                frame = depth_estimator.draw_overlay(frame, depth_result)
            except Exception:
                pass

        # Kişi 4 — danger zone overlay (her frame_skip'te hesaplanan sonuç varsa çiz)
        if ENABLE_HAZARD_DETECTION and 'p4_danger_result' in dir() and p4_danger_result:
            try:
                frame = danger_analyzer.visualize(frame, p4_danger_result)
            except Exception:
                pass

        frame = draw_detections(frame, detections)

        if SHOW_FPS:
            cv2.putText(
                frame, f"FPS: {fps_ctr.fps:.1f}",
                (frame.shape[1] - 90, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1,
            )

        cv2.imshow(WINDOW_TITLE, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
    assistant.stop()


if __name__ == "__main__":
    main()