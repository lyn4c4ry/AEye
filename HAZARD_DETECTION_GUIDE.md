"""
HAZARD DETECTION SYSTEM - IMPLEMENTATION GUIDE
==============================================

This document describes the Dynamic Hazard Detection System added to AEye.

OVERVIEW
--------
The hazard detection system enhances the original YOLO + OpenCV assistive system
by detecting dangerous environmental situations and providing context-aware warnings
to visually impaired users.

Key Principles:
- Accessibility-first: Minimize speech, prioritize critical information
- Context-aware: Combines multiple detections for intelligent hazard inference
- Non-repetitive: Smart cooldowns prevent overwhelming users
- Real-time: Optimized for low-latency hazard detection


MODULES
-------

1. hazard_analyzer.py - Core Hazard Detection Engine
   Location: /hazard_analyzer.py
   
   Features:
   - Context-based hazard detection (cones+barriers+workers → road work)
   - Environmental hazard detection (smoke, fire)
   - Approaching object risk calculation
   - Collision risk detection
   - Hazard prioritization (INFO, WARNING, DANGER, EMERGENCY)
   
   Usage:
   ```python
   from hazard_analyzer import HazardAnalyzer, HazardLevel
   
   analyzer = HazardAnalyzer()
   hazards = analyzer.analyze(detections, depth_result, motion_data)
   
   for hazard in hazards:
       if hazard.level == HazardLevel.DANGER:
           announce(hazard.message)
   ```
   
   Hazard Types:
   - "approaching_object": Fast-moving vehicle/person
   - "environmental_hazard": Fire, smoke, etc.
   - "collision_risk": Person directly ahead
   - "road_work": Work zone indicators detected
   - "abnormal_motion": Sudden/fast motion detected


2. motion_analyzer.py - Advanced Motion Detection
   Location: /motion_analyzer.py
   
   Features:
   - Optical flow analysis for velocity detection
   - Frame differencing for sudden changes
   - Zone-based motion analysis (left/center/right)
   - Crowd motion detection
   - Motion severity scoring
   
   Usage:
   ```python
   from motion_analyzer import MotionAnalyzer
   
   analyzer = MotionAnalyzer(frame_width, frame_height)
   motion_result = analyzer.analyze(frame)
   
   if motion_result["is_abnormal"]:
       for event in motion_result["events"]:
           handle_motion_event(event)
   ```
   
   Returns:
   - events: List of detected motion events
   - avg_motion: Average motion magnitude (0-1)
   - zones: Motion intensity by zone
   - is_abnormal: Whether abnormal motion was detected
   - frame_diff: Percentage of changed pixels


3. voice_feedback_manager.py - Smart Voice Feedback
   Location: /voice_feedback_manager.py
   
   Features:
   - Priority-based voice feedback queuing
   - Cooldown management (prevents overwhelming users)
   - Message deduplication
   - Accessibility filtering
   - Feedback statistics
   
   Usage:
   ```python
   from voice_feedback_manager import VoiceFeedbackManager, FeedbackPriority
   
   manager = VoiceFeedbackManager(global_cooldown=1.5)
   
   # Add feedback
   manager.add_feedback(
       "Vehicle approaching quickly.",
       unique_key="vehicle_alert",
       priority=FeedbackPriority.HIGH,
       cooldown=2.0
   )
   
   # Get next message
   message, key = manager.get_next_feedback()
   ```
   
   Priority Levels:
   - CRITICAL (0): Immediate danger
   - HIGH (1): Important warnings
   - NORMAL (2): Standard alerts
   - LOW (3): Background information


CONFIGURATION
--------------
All hazard detection parameters are in config.py:

```python
# Enable/Disable hazard detection
ENABLE_HAZARD_DETECTION = True

# Approaching object thresholds
APPROACHING_RISK_THRESHOLD = 5.0
COLLISION_RISK_AREA_THRESHOLD = 0.05
COLLISION_RISK_CENTER_WIDTH = 0.3

# Motion analysis thresholds
MOTION_ALERT_THRESHOLD = 0.3
FRAME_DIFF_ALERT_THRESHOLD = 15.0
CROWDED_MOTION_THRESHOLD = 0.5

# Alert cooldowns (seconds)
HAZARD_COOLDOWN_INFO = 5.0
HAZARD_COOLDOWN_WARNING = 2.5
HAZARD_COOLDOWN_DANGER = 2.0
HAZARD_COOLDOWN_EMERGENCY = 1.0

# Voice feedback cooldown
VOICE_FEEDBACK_GLOBAL_COOLDOWN = 1.0
```


HAZARD LEVELS
--------------
Hazards are prioritized into 4 levels:

INFO (0)
- Low-priority information
- Cooldown: 5 seconds
- Example: "Chair detected ahead."
- Non-interrupting

WARNING (1)
- Moderate-priority warnings
- Cooldown: 2.5 seconds
- Example: "Road work ahead."
- Non-interrupting

DANGER (2)
- High-priority hazards
- Cooldown: 2 seconds
- Example: "Vehicle approaching quickly."
- Interrupts lower-priority alerts

EMERGENCY (3)
- Critical hazards requiring immediate action
- Cooldown: 1 second
- Example: "Danger, fire detected."
- Immediately interrupts all other alerts


HAZARD DETECTION LOGIC
-----------------------

1. APPROACHING OBJECTS
   - Detects vehicles, motorcycles, buses, and people
   - Calculates risk: (velocity × object_priority) / distance
   - High risk triggers DANGER alert
   - Low risk triggers WARNING alert
   
   Example:
   Car at distance 0.04, velocity 1.0, priority 10
   Risk = (1.0 × 10) / 0.04 = 250 → DANGER

2. ENVIRONMENTAL HAZARDS
   - Detects smoke, fire
   - Triggers DANGER/EMERGENCY immediately
   - Persistent alerts while hazard visible

3. COLLISION RISK
   - Detects people close in central zone
   - Suggests directional evasion
   - Triggers DANGER alert

4. CONTEXT HAZARDS
   - Combines multiple detections
   - Road work: cones + barriers + workers
   - Crowded areas: multiple people + abnormal motion
   - Triggers WARNING alert

5. ABNORMAL MOTION
   - Optical flow detects fast movement
   - Frame differencing detects sudden changes
   - Crowd motion detection
   - Triggers WARNING/DANGER based on severity


INTEGRATION WITH EXISTING SYSTEM
----------------------------------

The hazard detection system integrates seamlessly:

1. Imports in main.py:
   ```python
   from hazard_analyzer import HazardAnalyzer, HazardLevel
   from motion_analyzer import MotionAnalyzer
   from voice_feedback_manager import VoiceFeedbackManager
   ```

2. Initialization (after camera open):
   ```python
   if ENABLE_HAZARD_DETECTION:
       hazard_analyzer = HazardAnalyzer()
       feedback_manager = VoiceFeedbackManager()
   
   if MOTION_ANALYSIS_ENABLED:
       motion_analyzer = MotionAnalyzer(width, height)
   ```

3. In main loop (per frame):
   ```python
   # Motion analysis
   motion_result = motion_analyzer.analyze(frame)
   
   # Hazard analysis
   hazards = hazard_analyzer.analyze(detections, depth_result, motion_data)
   
   # Convert to voice feedback
   for hazard in hazards:
       message, key, priority = feedback_manager.hazard_to_feedback(
           hazard.hazard_type, hazard.level.value, hazard.location
       )
       feedback_manager.add_feedback(message, key, priority)
   ```

4. Visualization (optional):
   ```python
   danger_zones = hazard_analyzer.get_danger_zones()
   # {"left": "danger", "center": "safe", "right": "warning"}
   ```


MESSAGE TEMPLATES
------------------
Predefined, accessible messages:

approaching_vehicle: "Warning, vehicle approaching quickly."
person_ahead: "Person directly ahead."
move_left: "Move slightly left."
move_right: "Move slightly right."
collision_risk: "Collision risk ahead."
road_work: "Road work detected."
fire_hazard: "Danger, fire detected."
smoke_hazard: "Smoke detected."
abnormal_motion: "Abnormal movement detected."
crowded_area: "Crowded area detected."

All messages:
- Under 10 words
- Actionable
- Non-technical
- Clear directional guidance


VOICE FEEDBACK FLOW
-------------------

User Scenario: Vehicle approaching from the left

1. YOLO detects: car at bbox area 0.05, velocity 1.0
2. HazardAnalyzer calculates risk: (1.0 × 10) / 0.05 = 200 (HIGH)
3. Creates HazardEvent:
   - type: "approaching_object"
   - level: DANGER
   - location: "left"
   - message: "Warning, vehicle approaching quickly."
4. VoiceFeedbackManager:
   - Converts to feedback: "On the left: Warning, vehicle approaching quickly."
   - Priority: HIGH
   - Cooldown: 2 seconds
5. Enqueues in priority queue
6. VoiceAssistant announces immediately (force=True for DANGER)


ACCESSIBILITY CONSIDERATIONS
-----------------------------

1. Minimize Speech:
   - Hazards only announce when critical
   - Duplicate messages filtered by cooldowns
   - INFO level messages rarely announced

2. Non-Repetitive:
   - Unique keys prevent same message repeatedly
   - Cooldowns increase with hazard frequency
   - Context switches (e.g., "left" to "right") trigger new alerts

3. Actionable Information:
   - "Move slightly left" instead of "Obstacle detected"
   - "Vehicle approaching quickly" instead of "car detected"
   - Directional guidance when possible

4. Cognitive Load:
   - Maximum 1-2 announcements per second
   - Global cooldown prevents audio overload
   - Hazards grouped by zone for clarity

5. Emergency Mode:
   - EMERGENCY level hazards interrupt immediately
   - All other alerts cleared from queue
   - User gets critical information without delay


PERFORMANCE NOTES
------------------

1. Optical Flow:
   - Farneback algorithm (dense optical flow)
   - Computed at frame resolution
   - ~15-20ms per frame on modern hardware

2. Motion Analysis:
   - Frame differencing: O(n)
   - Zone analysis: O(n)
   - Low computational overhead

3. Hazard Analysis:
   - O(m²) worst case (m = number of detections)
   - Typically very fast (m ≤ 20)
   - Context detection is O(m log m)

4. Memory Usage:
   - HazardAnalyzer: ~2MB
   - MotionAnalyzer: ~5-10MB (frame buffers)
   - VoiceFeedbackManager: <1MB


TROUBLESHOOTING
----------------

Issue: Too many voice alerts
Solution:
- Increase VOICE_FEEDBACK_GLOBAL_COOLDOWN in config.py
- Decrease APPROACHING_RISK_THRESHOLD
- Adjust motion thresholds

Issue: Missing approaching object warnings
Solution:
- Lower APPROACHING_RISK_THRESHOLD
- Check COLLISION_PRIORITY_CLASSES includes your objects
- Verify frame rate is sufficient

Issue: Excessive motion alerts
Solution:
- Increase MOTION_ALERT_THRESHOLD
- Increase FRAME_DIFF_ALERT_THRESHOLD
- Disable MOTION_ANALYSIS_ENABLED if not needed

Issue: Performance issues
Solution:
- Increase FRAME_SKIP to process fewer frames
- Disable MOTION_ANALYSIS_ENABLED
- Reduce YOLO model complexity (use yolov8n instead of yolov8m)


TESTING
-------

Test the hazard detection system:

1. Approach the camera quickly (test approaching object detection)
2. Move objects side-to-side (test directional hazards)
3. Create crowded motion (test abnormal motion detection)
4. Observe console output for hazard events
5. Verify voice announcements are clear and timely


EXTENDING THE SYSTEM
---------------------

Adding New Hazard Types:

1. Update HazardAnalyzer._detect_*() methods
2. Add entries to MESSAGE_TEMPLATES in VoiceFeedbackManager
3. Update config.py with new thresholds
4. Test with representative scenarios

Example - Weather Detection:
```python
def _detect_weather_hazards(self, detections):
    hazards = []
    for det in detections:
        if det.label == "rain":
            hazard = HazardEvent(
                hazard_type="heavy_rain",
                level=HazardLevel.WARNING,
                message="Heavy rain detected. Be careful.",
                location=self._get_direction(det.center, det.bbox),
                ...
            )
            hazards.append(hazard)
    return hazards
```


VERSION INFO
-----------
System: AEye - Hazard Detection System v1.0
Date: 2024
Compatibility: Python 3.8+, OpenCV 4.5+, YOLOv8
"""
