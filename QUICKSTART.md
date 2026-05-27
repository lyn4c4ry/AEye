"""
HAZARD DETECTION SYSTEM - QUICK START GUIDE
============================================

INSTALLATION & SETUP
--------------------

1. Ensure all dependencies are installed:
   - OpenCV 4.5+
   - YOLOv8 (ultralytics)
   - NumPy
   - Optional: PyTorch for GPU acceleration

2. The hazard detection is integrated into main.py
   No additional setup needed!

3. Configuration is in config.py
   Default settings work for most scenarios


RUNNING THE SYSTEM
-------------------

1. Basic run with hazard detection:
   ```
   python main.py
   ```

2. Enable/disable hazard detection in config.py:
   ```python
   ENABLE_HAZARD_DETECTION = True      # Enable
   ENABLE_HAZARD_DETECTION = False     # Disable
   ```

3. Enable/disable motion analysis:
   ```python
   MOTION_ANALYSIS_ENABLED = True      # Enable
   MOTION_ANALYSIS_ENABLED = False     # Disable
   ```


QUICK TEST SCENARIOS
--------------------

Test 1: Approaching Vehicle
- Walk toward the camera quickly
- Expected: "Warning, vehicle approaching quickly."
- Or: "Warning, person approaching quickly."
- Zone: "ahead"

Test 2: Fast Lateral Motion
- Move quickly from left to right across camera view
- Expected: "Abnormal movement detected."
- Or: "Person moved left/right"

Test 3: Crowded Motion
- Multiple people moving rapidly in same frame
- Expected: "Abnormal movement detected."
- Or: "Crowded area detected."

Test 4: Fire/Smoke Detection
- Show fire/smoke object to camera
- Expected: "Danger, fire detected." or "Smoke detected."
- Level: DANGER/EMERGENCY

Test 5: Road Work Detection
- Show traffic cones + stop sign + person
- Expected: "Road work detected."
- Level: WARNING


EXPECTED CONSOLE OUTPUT
-----------------------

Startup:
```
==================================================
  BlindAssist — Hazard Detection Mode
==================================================
[Detector] Loading model: yolov8n.pt
[Detector] Model ready.
[Hazard Detection] Enabled
[Motion Analysis] Enabled

[Main Loop] Running — press 'q' to quit
```

During operation:
```
Frame: 150 | FPS: 28.5 | Detections: 3 | Active Hazards: 1 | Motion Events: 0
Frame: 151 | FPS: 28.2 | Detections: 2 | Active Hazards: 0 | Motion Events: 1
```


VOICE FEEDBACK EXAMPLES
-----------------------

Scenario 1: Car Approaching from Left
Voice: "On the left: Warning, vehicle approaching quickly."
Action: User should move to the right

Scenario 2: Person Directly Ahead (Close)
Voice: "Collision risk ahead."
Action: User should move left or right

Scenario 3: Road Work Ahead
Voice: "Road work ahead."
Action: User should proceed with caution

Scenario 4: Abnormal Motion
Voice: "Abnormal movement detected."
Action: User should stop and assess situation

Scenario 5: Fire Detected
Voice: "Danger, fire detected."
Action: IMMEDIATE evacuation recommended


CUSTOMIZATION
--------------

Adjust sensitivity to approaching objects:
config.py:
```python
# Lower = more sensitive
APPROACHING_RISK_THRESHOLD = 3.0  # Default: 5.0
```

Adjust motion detection sensitivity:
```python
# Lower = more sensitive
MOTION_ALERT_THRESHOLD = 0.2  # Default: 0.3
```

Adjust voice feedback frequency:
```python
# Higher = less frequent
VOICE_FEEDBACK_GLOBAL_COOLDOWN = 2.0  # Default: 1.0
```

Add custom hazard message:
hazard_analyzer.py - update HAZARD_DEFINITIONS
voice_feedback_manager.py - update MESSAGE_TEMPLATES


MODULE REFERENCE
----------------

Core Hazard Detection:
```python
from hazard_analyzer import HazardAnalyzer
analyzer = HazardAnalyzer()
hazards = analyzer.analyze(detections)
```

Motion Analysis:
```python
from motion_analyzer import MotionAnalyzer
analyzer = MotionAnalyzer(width, height)
motion = analyzer.analyze(frame)
```

Voice Feedback Management:
```python
from voice_feedback_manager import VoiceFeedbackManager
manager = VoiceFeedbackManager()
manager.add_feedback(message, key, priority)
```

Danger Zone Analysis:
```python
from danger_zone_analyzer import DangerZoneAnalyzer
analyzer = DangerZoneAnalyzer(width, height)
zones = analyzer.analyze(detections)
```


TROUBLESHOOTING
----------------

Problem: No voice announcements
Solution 1: Check ENABLE_HAZARD_DETECTION = True
Solution 2: Verify audio system is working
Solution 3: Increase APPROACHING_RISK_THRESHOLD or motion thresholds lower

Problem: Too many announcements
Solution 1: Increase VOICE_FEEDBACK_GLOBAL_COOLDOWN
Solution 2: Increase hazard thresholds
Solution 3: Disable MOTION_ANALYSIS_ENABLED

Problem: Misses approaching objects
Solution 1: Decrease APPROACHING_RISK_THRESHOLD
Solution 2: Check if objects are in TARGET_CLASSES
Solution 3: Adjust COLLISION_RISK_AREA_THRESHOLD

Problem: High CPU usage
Solution 1: Disable MOTION_ANALYSIS_ENABLED
Solution 2: Increase FRAME_SKIP in config.py
Solution 3: Use simpler YOLO model (yolov8n vs yolov8m)


HAZARD LEVELS RECAP
-------------------

EMERGENCY (3) - Red Alert
- Fire, smoke, collision imminent
- Cooldown: 1 second
- Interrupts ALL other audio
- Example: "Danger, fire detected."

DANGER (2) - High Alert
- Fast approaching vehicle/person
- Cooldown: 2 seconds
- Interrupts lower priorities
- Example: "Warning, vehicle approaching quickly."

WARNING (1) - Caution
- Moderate hazards, road work, crowded areas
- Cooldown: 2.5 seconds
- Standard priority
- Example: "Road work detected."

INFO (0) - Background
- General information
- Cooldown: 5 seconds
- Non-interrupting
- Example: "Chair detected ahead."


ACCESSIBILITY TIPS
-------------------

1. Keep users informed without overwhelming:
   - Hazard messages are short (under 10 words)
   - Avoid technical terms
   - Include directional guidance when possible

2. Provide actionable feedback:
   - "Move left" instead of "obstacle"
   - "Vehicle approaching" instead of "detection alert"
   - Spatial information for navigation

3. Respect user attention:
   - Space out announcements (1-2 per second max)
   - Group related hazards
   - Avoid repeating same message

4. Critical safety first:
   - Emergency alerts bypass all cooldowns
   - Fire/collision detected = immediate voice feedback
   - User safety is highest priority


LOGGING & DEBUGGING
-------------------

To see detailed debug info, modify main.py:

```python
# Add after creating hazard_analyzer
hazard_analyzer.debug_mode = True  # Enable debug output

# In main loop, after hazard analysis:
if hazards:
    for h in hazards:
        print(f"[HAZARD] {h.hazard_type} | Level: {h.level} | Conf: {h.confidence:.2f}")
```

Monitor active hazards:
```python
active = hazard_analyzer.get_active_hazards()
print(f"[ACTIVE HAZARDS] {len(active)} detected")
for h in active:
    print(f"  - {h.hazard_type}: {h.message}")
```


REAL-WORLD SCENARIOS
---------------------

Outdoor Scenario 1: Street Crossing
- System detects: car (approaching), traffic light (ahead), person (center)
- Announces: "Vehicle approaching from left. Traffic light ahead."
- User Decision: Wait for safer moment

Outdoor Scenario 2: Crowded Market
- System detects: multiple people, fast motion, stalls
- Announces: "Crowded area. Multiple people around you."
- User Decision: Proceed slowly with caution

Indoor Scenario 1: Office Navigation
- System detects: chair (right), desk (center), person (left)
- Announces: "Chair on the right. Person on the left."
- User Decision: Move forward through center path

Indoor Scenario 2: Emergency
- System detects: fire, smoke, people running
- Announces: "Danger, fire detected. Evacuate immediately."
- User Decision: EMERGENCY EVACUATION


PERFORMANCE METRICS
-------------------

Expected Performance (on modern PC):
- Frame rate: 25-30 FPS
- Hazard detection latency: 50-100ms
- Voice announcement latency: 200-500ms
- CPU usage: 15-25% (single core)
- Memory usage: 300-400MB

Mobile/Embedded:
- May need to disable motion analysis
- Reduce YOLO model complexity
- Increase FRAME_SKIP for performance


NEXT STEPS
----------

1. Test with various scenarios
2. Adjust thresholds based on feedback
3. Monitor console for hazard events
4. Fine-tune voice feedback timing
5. Deploy in real-world environment
6. Collect user feedback and iterate

For detailed technical documentation, see:
- HAZARD_DETECTION_GUIDE.md (comprehensive documentation)
- hazard_analyzer.py (hazard detection logic)
- motion_analyzer.py (motion detection)
- voice_feedback_manager.py (voice feedback)
- danger_zone_analyzer.py (spatial analysis)
"""
