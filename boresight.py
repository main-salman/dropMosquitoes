# Implements: SW-001 §2.13 — Online Scout↔Sniper boresight
"""
boresight.py — Running pitch/yaw bias between fixed Scout and gimbal Sniper.

Updated from Sniper insect off-center error, splash miss, and ORB align.
"""

from __future__ import annotations

import threading
from typing import Tuple

try:
    import cv2
    import numpy as np
    CV2 = True
except ImportError:
    CV2 = False


class BoresightCorrector:
    """EMA bias (degrees) added to Scout pixel→angle aim."""

    def __init__(
        self,
        *,
        alpha: float = 0.18,
        max_bias_deg: float = 35.0,
        sniper_fov_h: float = 62.2,
        sniper_fov_v: float = 48.8,
        frame_w: int = 1280,
        frame_h: int = 720,
        center_ok_frac: float = 0.08,
    ):
        self.alpha = alpha
        self.max_bias = max_bias_deg
        self.fov_h = sniper_fov_h
        self.fov_v = sniper_fov_v
        self.fw = frame_w
        self.fh = frame_h
        self.center_ok_frac = center_ok_frac
        self._lock = threading.Lock()
        self.pitch_bias = 0.0
        self.yaw_bias = 0.0

    def seed_from_cal(self, pitch: float, yaw: float) -> None:
        with self._lock:
            self.pitch_bias = self._clamp(pitch)
            self.yaw_bias = self._clamp(yaw)

    def set_bias(self, pitch: float, yaw: float) -> None:
        with self._lock:
            self.pitch_bias = self._clamp(pitch)
            self.yaw_bias = self._clamp(yaw)

    def get_bias(self) -> Tuple[float, float]:
        with self._lock:
            return self.pitch_bias, self.yaw_bias

    def status(self) -> dict:
        with self._lock:
            return {
                "pitch_bias_deg": round(self.pitch_bias, 3),
                "yaw_bias_deg": round(self.yaw_bias, 3),
            }

    def _clamp(self, v: float) -> float:
        return max(-self.max_bias, min(self.max_bias, float(v)))

    def pixel_error_to_deg(self, px: int, py: int) -> Tuple[float, float]:
        """Sniper pixel → degrees from frame center (positive pitch = down)."""
        err_yaw = ((px / self.fw) - 0.5) * self.fov_h
        err_pitch = ((py / self.fh) - 0.5) * self.fov_v
        return err_pitch, err_yaw

    def is_centered(self, px: int, py: int) -> bool:
        nx = abs((px / self.fw) - 0.5)
        ny = abs((py / self.fh) - 0.5)
        return nx <= self.center_ok_frac and ny <= self.center_ok_frac

    def update_from_sniper_point(self, px: int, py: int) -> Tuple[float, float]:
        """
        Insect/splash at (px,py) should be at crosshair.
        Integrates pixel error into bias and returns immediate aim correction.
        """
        err_p, err_y = self.pixel_error_to_deg(px, py)
        with self._lock:
            self.pitch_bias = self._clamp(self.pitch_bias + self.alpha * err_p)
            self.yaw_bias = self._clamp(self.yaw_bias + self.alpha * err_y)
        return err_p, err_y

    def estimate_from_frames(self, scout_frame, sniper_frame,
                             *, accumulate: bool = False) -> dict:
        """
        ORB-match Scout vs Sniper at current gimbal pose.

        Returns mount bias so content near Scout center lands on Sniper
        crosshair. If accumulate=True, add residual onto existing bias
        (used for refine after a coarse move).
        """
        if not CV2 or scout_frame is None or sniper_frame is None:
            return {"ok": False, "error": "no_frames"}

        try:
            g1 = cv2.cvtColor(scout_frame, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(sniper_frame, cv2.COLOR_BGR2GRAY)
            if g1.shape != g2.shape:
                g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]))

            orb = cv2.ORB_create(1200)
            k1, d1 = orb.detectAndCompute(g1, None)
            k2, d2 = orb.detectAndCompute(g2, None)
            n1 = len(k1) if k1 is not None else 0
            n2 = len(k2) if k2 is not None else 0
            if d1 is None or d2 is None or n1 < 12 or n2 < 12:
                return {
                    "ok": False,
                    "error": "not_enough_features",
                    "n1": n1,
                    "n2": n2,
                }

            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = sorted(bf.match(d1, d2), key=lambda m: m.distance)[:80]
            if len(matches) < 8:
                return {
                    "ok": False,
                    "error": "not_enough_matches",
                    "n": len(matches),
                }

            h, w = g1.shape[:2]
            cx, cy = w / 2.0, h / 2.0
            dxs, dys = [], []
            for m in matches:
                p1 = k1[m.queryIdx].pt
                p2 = k2[m.trainIdx].pt
                if abs(p1[0] - cx) > w * 0.35 or abs(p1[1] - cy) > h * 0.35:
                    continue
                dxs.append(p2[0] - cx)
                dys.append(p2[1] - cy)

            used_mode = "center_neighbors"
            if len(dxs) < 5:
                used_mode = "pairwise_delta"
                dxs, dys = [], []
                for m in matches:
                    p1 = k1[m.queryIdx].pt
                    p2 = k2[m.trainIdx].pt
                    dxs.append(p2[0] - p1[0])
                    dys.append(p2[1] - p1[1])

            med_dx = float(np.median(dxs))
            med_dy = float(np.median(dys))
            # Feature right/down of Sniper crosshair → need +yaw / +pitch
            err_yaw = (med_dx / w) * self.fov_h
            err_pitch = (med_dy / h) * self.fov_v

            with self._lock:
                if accumulate:
                    self.pitch_bias = self._clamp(self.pitch_bias + err_pitch)
                    self.yaw_bias = self._clamp(self.yaw_bias + err_yaw)
                else:
                    self.pitch_bias = self._clamp(err_pitch)
                    self.yaw_bias = self._clamp(err_yaw)
                bp, by = self.pitch_bias, self.yaw_bias

            return {
                "ok": True,
                "matches": len(matches),
                "used": len(dxs),
                "mode": used_mode,
                "median_dx_px": round(med_dx, 1),
                "median_dy_px": round(med_dy, 1),
                "residual_pitch_deg": round(err_pitch, 3),
                "residual_yaw_deg": round(err_yaw, 3),
                "pitch_bias_deg": round(bp, 3),
                "yaw_bias_deg": round(by, 3),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
