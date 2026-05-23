"""
depth_estimator.py — AEye Project
Heatmap-based structural obstacle detection for visually impaired assistance.

Detects walls, floors, doors and other surfaces that YOLO cannot label,
and provides directional audio alerts ("Close obstacle on the left.").

Usage (in main.py):
    from depth_estimator import DepthEstimator

    de = DepthEstimator()          # starts loading MiDaS in background

    # inside the main loop:
    result = de.estimate(frame)
    if result:
        frame = de.draw_overlay(frame, result)
        for alert in result.prop_alerts:
            alert_manager.say(alert)   # pass to your TTS/AlertManager

Color scale (COLORMAP_JET):
    Blue  = far / safe
    Green / Yellow = medium distance
    Red   = close / danger

Performance:
    - MiDaS runs on 256px-wide frames, result is upscaled (cheap)
    - Time-based scheduling prevents overlapping inference threads
    - draw_overlay runs entirely on the main thread with no heavy math
"""

import cv2
import numpy as np
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
INFERENCE_WIDTH    = 256   # MiDaS input width — lower = faster (min ~192)
INFERENCE_INTERVAL = 0.15  # min seconds between depth updates (~6-7 fps)

CLOSE_THRESHOLD       = 0.68  # zone mean above this → "close" alert
MEDIUM_THRESHOLD      = 0.45  # zone mean above this → "medium" alert
DEPTH_ALERT_COOLDOWN  = 3.0   # min seconds between alerts for the same zone
LOCAL_NORM_PERCENTILE = 85    # suppress top N% outliers in local normalization

HEATMAP_ALPHA_MIN   = 0.03   # opacity for distant surfaces
HEATMAP_ALPHA_MAX   = 0.52   # opacity for close surfaces
HEATMAP_ALPHA_GAMMA = 3.0    # curve shape — higher keeps far areas more transparent

ZONE_ROWS = 3
ZONE_COLS = 3


# ── Helpers ───────────────────────────────────────────────────────────────────
def _odd(n: int) -> int:
    """Return n if already odd, else n+1. OpenCV kernel sizes must be odd."""
    return n if n % 2 == 1 else n + 1


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class DepthResult:
    depth_map:    np.ndarray  # global normalized depth [0-1], full frame res
    heatmap_bgr:  np.ndarray  # JET-colored overlay, inference res (upscaled in draw)
    heatmap_mask: np.ndarray  # uint8 alpha mask [0-255], inference res
    close_zones:  list = field(default_factory=list)  # e.g. ["left", "center"]
    medium_zones: list = field(default_factory=list)  # e.g. ["right"]
    prop_alerts:  list = field(default_factory=list)  # e.g. ["Close obstacle ahead."]


# ── Main class ────────────────────────────────────────────────────────────────
class DepthEstimator:
    """
    Runs MiDaS depth estimation in a background thread.
    The main loop is never blocked — estimate() always returns immediately.
    """

    def __init__(self):
        self._model     = None
        self._transform = None
        self._device    = None
        self._ready     = False

        self._lock                              = threading.Lock()
        self._latest_result: Optional[DepthResult] = None
        self._processing                        = False
        self._last_inference_time               = 0.0
        self._last_alert_time: dict[str, float] = {}

        threading.Thread(target=self._load_model, daemon=True).start()

    # ── Model loading ──────────────────────────────────────────────────────────
    def _load_model(self):
        """Download and init MiDaS Small (~80 MB on first run)."""
        try:
            import torch
            import timm  # noqa: F401 — required by MiDaS internals

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            print(f"[Depth] Loading MiDaS Small on {self._device}...")

            self._model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
            self._model.to(self._device).eval()

            transforms      = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
            self._transform = transforms.small_transform

            self._ready = True
            print("[Depth] MiDaS ready ✓")
        except Exception as e:
            print(f"[Depth] Failed to load model: {e}")

    # ── Public API ─────────────────────────────────────────────────────────────
    def estimate(self, frame: np.ndarray) -> Optional[DepthResult]:
        """
        Call every frame in the main loop.
        Spawns a background inference thread only when the previous one has
        finished AND at least INFERENCE_INTERVAL seconds have passed.
        Returns the latest DepthResult, or None if the model isn't ready yet.
        """
        if not self._ready:
            return None

        now = time.time()
        if not self._processing and now - self._last_inference_time >= INFERENCE_INTERVAL:
            self._last_inference_time = now
            threading.Thread(
                target=self._run_inference, args=(frame.copy(),), daemon=True
            ).start()

        with self._lock:
            return self._latest_result

    def draw_overlay(self, frame: np.ndarray, result: DepthResult) -> np.ndarray:
        """
        Blend the depth heatmap onto frame.
        Heatmap is upscaled from inference resolution here (cheap bilinear).
        Per-pixel alpha is applied via numpy float32 — correct and artifact-free.
        """
        if result is None:
            return frame

        h, w = frame.shape[:2]
        hmap = cv2.resize(result.heatmap_bgr,  (w, h), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(result.heatmap_mask, (w, h), interpolation=cv2.INTER_LINEAR)

        a   = mask.astype(np.float32) / 255.0
        a3  = np.stack([a, a, a], axis=-1)
        out = frame.astype(np.float32) * (1.0 - a3) + hmap.astype(np.float32) * a3
        return np.clip(out, 0, 255).astype(np.uint8)

    # ── Inference (background thread) ─────────────────────────────────────────
    def _run_inference(self, frame: np.ndarray):
        self._processing = True
        try:
            import torch

            h, w = frame.shape[:2]

            # Downscale frame for faster MiDaS inference
            scale     = INFERENCE_WIDTH / w
            inf_h     = max(int(h * scale), 32)
            small_bgr = cv2.resize(frame, (INFERENCE_WIDTH, inf_h), interpolation=cv2.INTER_AREA)
            rgb       = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)

            with torch.no_grad():
                tensor = self._transform(rgb).to(self._device)
                raw    = self._model(tensor)
                raw    = torch.nn.functional.interpolate(
                    raw.unsqueeze(1), size=(inf_h, INFERENCE_WIDTH),
                    mode="bilinear", align_corners=False,
                ).squeeze()

            depth_np = raw.cpu().numpy().astype(np.float32)

            # Global norm [0=far, 1=close] — stored for potential external use
            d_min, d_max = depth_np.min(), depth_np.max()
            if d_max - d_min < 1e-6:
                return
            global_norm      = (depth_np - d_min) / (d_max - d_min)
            global_norm_full = cv2.resize(global_norm, (w, h), interpolation=cv2.INTER_LINEAR)

            # Local norm — makes distant objects visible relative to their region
            local_norm = self._local_normalize(depth_np, inf_h, INFERENCE_WIDTH)

            heatmap_bgr, heatmap_mask = self._build_heatmap(local_norm)
            close_z, medium_z         = self._analyze_zones(local_norm, inf_h, INFERENCE_WIDTH)
            alerts                    = self._build_alerts(close_z, medium_z)

            with self._lock:
                self._latest_result = DepthResult(
                    depth_map    = global_norm_full,
                    heatmap_bgr  = heatmap_bgr,
                    heatmap_mask = heatmap_mask,
                    close_zones  = close_z,
                    medium_zones = medium_z,
                    prop_alerts  = alerts,
                )
        except Exception as e:
            print(f"[Depth] Inference error: {e}")
        finally:
            self._processing = False

    # ── Local normalization ────────────────────────────────────────────────────
    def _local_normalize(self, depth_np: np.ndarray, h: int, w: int) -> np.ndarray:
        """
        Normalize each pixel relative to its local neighborhood using a large
        Gaussian window. This ensures distant objects (e.g. a dresser 1.5 m away)
        show up as red/yellow in their region even when something closer dominates
        the global depth range. No grid — output is fully continuous.
        """
        k          = _odd(max(h, w) // 2)
        local_mean = cv2.GaussianBlur(depth_np, (k, k), 0)
        residual   = depth_np - local_mean
        p_max      = np.percentile(residual, LOCAL_NORM_PERCENTILE)
        p_min      = residual.min()
        if p_max - p_min < 1e-6:
            return np.zeros_like(depth_np)
        clipped = np.clip(residual, p_min, p_max)
        return ((clipped - p_min) / (p_max - p_min)).astype(np.float32)

    # ── Heatmap builder ────────────────────────────────────────────────────────
    def _build_heatmap(self, norm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Convert normalized depth to a JET colormap image + alpha mask.
        Alpha follows a power curve: far pixels get ALPHA_MIN, close pixels
        get ALPHA_MAX. GAMMA > 1 keeps distant areas transparent so the camera
        image stays readable, then ramps up sharply for close surfaces.
        """
        depth_u8     = (norm * 255).astype(np.uint8)
        heatmap_bgr  = cv2.applyColorMap(depth_u8, cv2.COLORMAP_JET)
        alpha_f      = (HEATMAP_ALPHA_MIN +
                        (HEATMAP_ALPHA_MAX - HEATMAP_ALPHA_MIN) *
                        np.power(norm, HEATMAP_ALPHA_GAMMA))
        heatmap_mask = (alpha_f * 255).astype(np.uint8)
        return heatmap_bgr, heatmap_mask

    # ── Zone analysis ──────────────────────────────────────────────────────────
    def _analyze_zones(self, norm: np.ndarray, h: int, w: int) -> tuple[list, list]:
        """
        Divide the frame into a 3x3 grid and check mean depth per cell.
        Used only for audio alert logic — never drawn on screen.
        """
        row_h = h // ZONE_ROWS
        col_w = w // ZONE_COLS
        zone_names = {
            (0, 0): "top-left",  (0, 1): "top",    (0, 2): "top-right",
            (1, 0): "left",      (1, 1): "center",  (1, 2): "right",
            (2, 0): "bot-left",  (2, 1): "bottom",  (2, 2): "bot-right",
        }
        close_zones, medium_zones = [], []
        for r in range(ZONE_ROWS):
            for c in range(ZONE_COLS):
                patch = norm[r*row_h:(r+1)*row_h, c*col_w:(c+1)*col_w]
                mean  = float(patch.mean())
                name  = zone_names[(r, c)]
                if mean >= CLOSE_THRESHOLD:
                    close_zones.append(name)
                elif mean >= MEDIUM_THRESHOLD:
                    medium_zones.append(name)
        return close_zones, medium_zones

    # ── Alert builder ──────────────────────────────────────────────────────────
    def _build_alerts(self, close_zones: list, medium_zones: list) -> list:
        """
        Convert zone names to TTS-ready alert strings with cooldown protection.
        Direction: left-* → "on the left", right-* → "on the right", else "ahead".
        """
        now    = time.time()
        alerts = []

        def _maybe_alert(zone: str, severity: str):
            key = f"{severity}:{zone}"
            if now - self._last_alert_time.get(key, 0) < DEPTH_ALERT_COOLDOWN:
                return
            self._last_alert_time[key] = now
            direction = ("on the left"  if "left"  in zone else
                         "on the right" if "right" in zone else "ahead")
            label = "Close obstacle" if severity == "close" else "Obstacle"
            alerts.append(f"{label} {direction}.")

        for z in close_zones:
            _maybe_alert(z, "close")
        for z in medium_zones:
            _maybe_alert(z, "medium")
        return alerts