# BlindAssist — Person 1 Module
**Human & Obstacle Detection** · YOLO + OpenCV + pyttsx3

---

## Installation

```bash
# 1. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt
```

---

## DroidCam Setup

1. **Phone** → Download "DroidCam" from the App Store (iPhone supported ✓)
2. **PC** → Install DroidCam Client from https://www.dev47apps.com/
3. Make sure phone and PC are on the **same WiFi network**
4. Open DroidCam on your phone and copy the **IP address** shown on screen
5. Open `config.py` and update `CAMERA_SOURCE`:

```python
CAMERA_SOURCE = "http://192.168.X.X:4747/video"  # <- your IP here
```

> To test with a webcam: `CAMERA_SOURCE = 0`
> To test with a video file: `CAMERA_SOURCE = r"C:\path\to\video.mp4"`

---

## Running

```bash
python main.py
```

Press **`q`** in the window to quit.

---

## Project Structure

```
blindassist/
├── main.py               # Entry point — run this
├── config.py             # All settings in one place
├── requirements.txt
│
├── core/
│   └── camera.py         # DroidCam / webcam connection
│
├── detection/
│   └── detector.py       # YOLO detection + drawing
│                         # -> Detection dataclass (used by other team members)
│
├── audio/
│   └── tts_engine.py     # pyttsx3 + cooldown system
│
└── utils/
    └── fps_counter.py    # Rolling FPS calculation
```

---

## API for Other Team Members

```python
from detection import Detector, Detection

detector = Detector()
detections = detector.detect(frame)   # returns list[Detection]

# Helper filters
persons   = detector.get_persons(detections)       # only persons
obstacles = detector.get_obstacles(detections)     # close obstacles
cars      = detector.get_by_class(detections, 2)   # by COCO class id

# Detection dataclass fields:
# .class_id    int
# .label       str   (YOLO class name)
# .confidence  float
# .bbox        tuple (x1, y1, x2, y2)
# .center      tuple (cx, cy)
# .area_ratio  float
# .is_person   bool
# .is_close    bool  <- use this for obstacle warnings
```

---

## Settings (config.py)

| Variable | Description | Default |
|---|---|---|
| `CAMERA_SOURCE` | DroidCam URL, webcam index, or video path | `"http://..."` |
| `YOLO_MODEL` | Model weights | `yolov8n.pt` |
| `CONFIDENCE_THRESHOLD` | Minimum confidence score | `0.30` |
| `FRAME_SKIP` | Detect every N frames | `3` |
| `OBSTACLE_AREA_RATIO` | Close object threshold | `0.08` |
| `TARGET_CLASSES` | Auto-loaded from YOLO (all 80 COCO classes) | auto |
| `COOLDOWN_PERSON` | Person TTS cooldown (sec) | `3.0` |
| `COOLDOWN_OBSTACLE` | Obstacle TTS cooldown (sec) | `5.0` |
