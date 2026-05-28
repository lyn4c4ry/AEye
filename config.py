# BlindAssist — Configuration

# Camera source — webcam: 0, DroidCam: 1 or 2, video: r"C:\path\to\video.mp4"
CAMERA_SOURCE = 1

# YOLO
YOLO_MODEL = "yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.45
FRAME_SKIP = 2

# Relevant COCO classes for a visually impaired person (outdoor + indoor)
TARGET_CLASSES = {
    0:  "person",
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    7:  "truck",
    9:  "traffic light",
    11: "stop sign",
    13: "bench",
    15: "cat",
    16: "dog",
    17: "horse",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    28: "suitcase",
    32: "sports ball",
    39: "bottle",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    62: "tv",
    63: "laptop",
    64: "mouse",
    66: "keyboard",
    67: "cell phone",
    69: "oven",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    79: "toothbrush",
}

# Obstacle threshold — bbox area / frame area, above this = "close"
OBSTACLE_AREA_RATIO = 0.08

# Alert cooldown per label (seconds)
ALERT_COOLDOWN = 3.0

# Display
WINDOW_TITLE = "BlindAssist — AEye"
SHOW_LABELS = True
SHOW_FPS = True
BOX_COLOR_PERSON   = (0, 255, 100)
BOX_COLOR_OBSTACLE = (0, 100, 255)
BOX_COLOR_DEFAULT  = (200, 200, 200)

# ── HAZARD DETECTION (Kişi 4 — Melis) ────────────────────────────────────────

ENABLE_HAZARD_DETECTION = True

# Approaching object detection
APPROACHING_RISK_THRESHOLD     = 5.0   # minimum risk score to trigger alert
COLLISION_RISK_AREA_THRESHOLD  = 0.05  # object size ratio for collision risk
COLLISION_RISK_CENTER_WIDTH    = 0.3   # percentage of frame center for direct collision

# Motion analysis
MOTION_ALERT_THRESHOLD        = 0.3   # normalized motion magnitude (0-1)
FRAME_DIFF_ALERT_THRESHOLD    = 15.0  # percentage of changed pixels
CROWDED_MOTION_THRESHOLD      = 0.5   # motion severity for crowd detection
MOTION_ANALYSIS_ENABLED       = True
OPTICAL_FLOW_WINDOW_SIZE      = 15
OPTICAL_FLOW_PYRAMID_LEVELS   = 3
FRAME_DIFF_THRESHOLD_PIXEL_VALUE = 30

# Hazard alert cooldowns (seconds)
HAZARD_COOLDOWN_INFO      = 5.0
HAZARD_COOLDOWN_WARNING   = 2.5
HAZARD_COOLDOWN_DANGER    = 2.0
HAZARD_COOLDOWN_EMERGENCY = 1.0

# Global voice feedback cooldown
VOICE_FEEDBACK_GLOBAL_COOLDOWN = 1.0

# High-priority classes for collision detection
COLLISION_PRIORITY_CLASSES = {
    "car":        10,
    "truck":      12,
    "bus":        11,
    "motorcycle":  8,
    "person":      5,
}

# Environmental hazards
ENVIRONMENTAL_HAZARDS  = {"fire", "smoke"}
ROAD_WORK_INDICATORS   = {"traffic cone", "stop sign", "person"}