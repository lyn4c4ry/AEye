# AEye — AI-Powered Assistant for the Visually Impaired

> **Vision:** Smart glasses + earpiece providing real-time environment perception and audio guidance for visually impaired users.
> **Current prototype:** Phone camera → PC via DroidCam (Python). Mobile APK planned for future.

---

## Team

| Person | Module |
|---|---|
| Person 1 | Human & structural obstacle detection (YOLO + MiDaS depth) |
| Person 2 | Vehicle & motion analysis |
| Person 3 | Voice assistant & alert logic |
| Person 4 | Danger zone overlay & proximity system |

---

## Installation

```bash
# 1. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 2. Core dependencies
pip install -r requirements.txt

# 3. Depth system (MiDaS)
pip install torch torchvision timm
```

> On first run, MiDaS Small (~80 MB) and YOLOv8n (~6 MB) are downloaded automatically.

---

## DroidCam Setup

1. **Phone** → Download "DroidCam" from the App Store (iPhone supported ✓)
2. **PC** → Install DroidCam Client from https://www.dev47apps.com/
3. Make sure phone and PC are on the **same WiFi network**
   - Hotspot method works: open hotspot on phone, connect PC to it
   - Use the IP shown in the DroidCam app — `172.20.10.1` is the gateway, not the phone
4. Open `config.py` and set `CAMERA_SOURCE`:

```python
CAMERA_SOURCE = "http://192.168.X.X:4747/video"  # WiFi
CAMERA_SOURCE = 1                                  # DroidCam virtual cam
CAMERA_SOURCE = 0                                  # webcam
CAMERA_SOURCE = r"C:\path\to\video.mp4"           # video file
```

---

## Running

```bash
python main.py
```

Press **`q`** to quit.

---

## Project Structure

```
AEye/
├── main.py                 # Entry point — run this
├── config.py               # All settings in one place
├── depth_estimator.py      # MiDaS heatmap depth system (Person 1)
├── requirements.txt
│
├── core/
│   └── camera.py           # DroidCam / webcam connection
│
├── detection/
│   └── detector.py         # YOLO detection + drawing
│
└── utils/
    └── fps_counter.py      # Rolling FPS calculation
```

---

## Depth System (depth_estimator.py)

Detects structural obstacles — walls, doors, floors — that YOLO cannot label.
Uses MiDaS monocular depth estimation with a heatmap overlay:

| Color | Meaning |
|---|---|
| 🔵 Blue | Far / safe |
| 🟡 Yellow / Green | Medium distance |
| 🔴 Red | Close / danger |

Local normalization ensures every region of the frame uses its full color range —
a dresser 2 m away will still show red in its zone even if a closer object exists elsewhere.

```python
from depth_estimator import DepthEstimator

de = DepthEstimator()   # loads MiDaS in background thread

# Inside main loop:
result = de.estimate(frame)
if result:
    frame = de.draw_overlay(frame, result)
    for alert in result.prop_alerts:
        alert_manager.say(alert)   # e.g. "Close obstacle on the left."
```

**Key settings in `depth_estimator.py`:**

| Variable | Default | Description |
|---|---|---|
| `INFERENCE_WIDTH` | `256` | MiDaS input width — lower = faster |
| `INFERENCE_INTERVAL` | `0.15` | Seconds between depth updates |
| `CLOSE_THRESHOLD` | `0.68` | Zone mean above this → close alert |
| `MEDIUM_THRESHOLD` | `0.45` | Zone mean above this → medium alert |
| `DEPTH_ALERT_COOLDOWN` | `3.0` | Min seconds between same-zone alerts |
| `HEATMAP_ALPHA_MAX` | `0.52` | Heatmap opacity for close surfaces |
| `HEATMAP_ALPHA_GAMMA` | `3.0` | Higher = only very close surfaces go red |

---

## YOLO Detection API

```python
from detection import Detector, Detection

detector = Detector()
detections = detector.detect(frame)   # returns list[Detection]

# Filters
persons   = detector.get_persons(detections)
obstacles = detector.get_obstacles(detections)
cars      = detector.get_by_class(detections, 2)

# Detection fields:
# .class_id    int
# .label       str
# .confidence  float
# .bbox        tuple (x1, y1, x2, y2)
# .center      tuple (cx, cy)
# .area_ratio  float
# .is_person   bool
# .is_close    bool   ← use this for obstacle warnings
```

---

## Settings (config.py)

| Variable | Default | Description |
|---|---|---|
| `CAMERA_SOURCE` | `1` | Camera input |
| `YOLO_MODEL` | `yolov8n.pt` | Model weights file |
| `CONFIDENCE_THRESHOLD` | `0.45` | Minimum detection confidence |
| `FRAME_SKIP` | `2` | Run YOLO every N frames |
| `OBSTACLE_AREA_RATIO` | `0.08` | Bbox/frame ratio threshold for "close" |
| `ALERT_COOLDOWN` | `3.0` | Seconds between same-label alerts |

---

## Requirements

```
ultralytics>=8.0.0
opencv-python>=4.8.0
numpy>=1.24.0
torch
torchvision
timm
```

---

## Status

- [x] YOLO human & obstacle detection
- [x] MiDaS depth — heatmap overlay with local normalization
- [x] Structural obstacle alerts (wall / floor / door)
- [x] Alert cooldown system
- [x] FPS counter
- [x] 1280×720 resolution
- [ ] TTS integration
- [ ] Vehicle direction detection — coming from left/right
- [ ] Danger zone overlay
- [ ] APK build (Kivy)