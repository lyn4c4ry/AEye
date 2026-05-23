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
WINDOW_TITLE = "BlindAssist — Person 1 Module"
SHOW_LABELS = True
SHOW_FPS = True
BOX_COLOR_PERSON   = (0, 255, 100)
BOX_COLOR_OBSTACLE = (0, 100, 255)
BOX_COLOR_DEFAULT  = (200, 200, 200)