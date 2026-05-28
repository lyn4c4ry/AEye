"""
depth_estimator.py — AEye Project
Edge-based structural obstacle detection for visually impaired assistance.

Draws colored depth edges on surfaces (walls, floors, doors).
Close edges = red/orange, far edges = cyan/blue.
No heatmap flood — camera image stays clean and readable.
"""

import cv2
import numpy as np
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
INFERENCE_WIDTH    = 192
INFERENCE_INTERVAL = 0.25

CLOSE_THRESHOLD      = 0.68
MEDIUM_THRESHOLD     = 0.45
DEPTH_ALERT_COOLDOWN = 3.0

# Edge detection
SOBEL_THRESHOLD  = 15    # düşür = daha fazla kenar, artır = sadece belirgin kenarlar
EDGE_LINE_WIDTH  = 1     # kenar çizgi kalınlığı (piksel)

# Renk geçişi: uzak=cyan, yakın=kırmızı (BGR)
COLOR_FAR   = (255, 200, 0)   # cyan-mavi
COLOR_MID   = (0, 200, 255)   # turuncu-sarı
COLOR_CLOSE = (0, 50, 255)    # kırmızı

ZONE_ROWS = 3
ZONE_COLS = 3


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class DepthResult:
    depth_map:    np.ndarray  # global normalized depth [0-1], full frame res
    heatmap_bgr:  np.ndarray  # edge overlay (API compat adı korundu)
    heatmap_mask: np.ndarray  # edge mask
    close_zones:  list = field(default_factory=list)
    medium_zones: list = field(default_factory=list)
    prop_alerts:  list = field(default_factory=list)


# ── Main class ────────────────────────────────────────────────────────────────
class DepthEstimator:
    def __init__(self):
        self._model     = None
        self._transform = None
        self._device    = None
        self._ready     = False

        self._lock                                 = threading.Lock()
        self._latest_result: Optional[DepthResult] = None
        self._processing                           = False
        self._last_inference_time                  = 0.0
        self._last_alert_time: dict[str, float]    = {}

        threading.Thread(target=self._load_model, daemon=True).start()

    # ── Model loading ──────────────────────────────────────────────────────────
    def _load_model(self):
        try:
            import torch
            import timm  # noqa: F401

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

    def draw_overlay(self, frame: np.ndarray, result: Optional[DepthResult]) -> np.ndarray:
        """
        Edge overlay: sadece yüzey kenarlarını renkli çizer.
        Kamera görüntüsü temiz kalır, duvar/zemin sınırları belirginleşir.
        """
        if result is None or result.heatmap_bgr is None:
            return frame

        h, w = frame.shape[:2]
        edge_overlay = cv2.resize(result.heatmap_bgr, (w, h), interpolation=cv2.INTER_NEAREST)

        # Sadece kenar olan pikselleri üst üste koy
        edge_mask = cv2.resize(result.heatmap_mask, (w, h), interpolation=cv2.INTER_NEAREST)
        mask_bool = edge_mask > 0

        output = frame.copy()
        output[mask_bool] = cv2.addWeighted(
            edge_overlay, 0.85, frame, 0.15, 0
        )[mask_bool]

        return output

    # ── Inference (background thread) ─────────────────────────────────────────
    def _run_inference(self, frame: np.ndarray):
        self._processing = True
        try:
            import torch

            h, w = frame.shape[:2]

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

            # Percentile norm — outlier'lar skalayı ezmesin
            p_low  = np.percentile(depth_np, 5)
            p_high = np.percentile(depth_np, 95)
            if p_high - p_low < 1e-6:
                return

            norm      = np.clip((depth_np - p_low) / (p_high - p_low), 0.0, 1.0)
            norm_full = cv2.resize(norm, (w, h), interpolation=cv2.INTER_LINEAR)

            edge_overlay, edge_mask = self._build_edges(norm)
            close_z, medium_z       = self._analyze_zones(norm, inf_h, INFERENCE_WIDTH)
            alerts                  = self._build_alerts(close_z, medium_z)

            with self._lock:
                self._latest_result = DepthResult(
                    depth_map    = norm_full,
                    heatmap_bgr  = edge_overlay,
                    heatmap_mask = edge_mask,
                    close_zones  = close_z,
                    medium_zones = medium_z,
                    prop_alerts  = alerts,
                )
        except Exception as e:
            print(f"[Depth] Inference error: {e}")
        finally:
            self._processing = False

    # ── Edge builder ───────────────────────────────────────────────────────────
    def _build_edges(self, norm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Sobel gradient ile depth kenarlarını tespit et.
        Her kenar pikselini derinliğine göre renklendir:
          yakın → kırmızı, orta → turuncu/sarı, uzak → cyan
        """
        depth_u8 = (norm * 255).astype(np.uint8)

        # Sobel edge detection
        sobel_x = cv2.Sobel(depth_u8, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(depth_u8, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        magnitude = np.clip(magnitude / magnitude.max(), 0, 1) if magnitude.max() > 0 else magnitude

        # Threshold — sadece belirgin kenarlar
        edge_mask_bool = magnitude > (SOBEL_THRESHOLD / 255.0)

        h, w = norm.shape
        edge_overlay = np.zeros((h, w, 3), dtype=np.uint8)
        edge_mask    = np.zeros((h, w),    dtype=np.uint8)

        if not edge_mask_bool.any():
            return edge_overlay, edge_mask

        # Her kenar pikselini derinliğine göre renklendir
        edge_depths = norm[edge_mask_bool]

        colors = np.zeros((edge_depths.shape[0], 3), dtype=np.uint8)

        # Uzak (0.0 - 0.4) → cyan
        far_mask = edge_depths < 0.4
        colors[far_mask] = COLOR_FAR

        # Orta (0.4 - 0.7) → turuncu/sarı
        mid_mask = (edge_depths >= 0.4) & (edge_depths < 0.7)
        colors[mid_mask] = COLOR_MID

        # Yakın (0.7 - 1.0) → kırmızı
        close_mask = edge_depths >= 0.7
        colors[close_mask] = COLOR_CLOSE

        edge_overlay[edge_mask_bool] = colors
        edge_mask[edge_mask_bool]    = 255

        # Kenar çizgilerini biraz kalınlaştır — ince piksel çizgiler görünmez olur
        if EDGE_LINE_WIDTH > 1:
            kernel = np.ones((EDGE_LINE_WIDTH, EDGE_LINE_WIDTH), np.uint8)
            edge_mask    = cv2.dilate(edge_mask,    kernel, iterations=1)
            edge_overlay = cv2.dilate(edge_overlay, kernel, iterations=1)

        return edge_overlay, edge_mask

    # ── Zone analysis ──────────────────────────────────────────────────────────
    def _analyze_zones(self, norm: np.ndarray, h: int, w: int) -> tuple[list, list]:
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