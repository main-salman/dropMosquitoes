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
        # ORB align must stay conservative — Scout/Sniper often barely overlap
        align_max_bias_deg: float = 18.0,
    ):
        self.alpha = alpha
        self.max_bias = max_bias_deg
        self.align_max_bias = align_max_bias_deg
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
        ORB-match Scout vs Sniper at current gimbal pose (home recommended).

        Uses Lowe ratio + RANSAC homography; rejects weak/large offsets so a
        bad match cannot yank hunt aim by tens of degrees.
        """
        if not CV2 or scout_frame is None or sniper_frame is None:
            return {"ok": False, "error": "no_frames"}

        try:
            g1 = cv2.cvtColor(scout_frame, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(sniper_frame, cv2.COLOR_BGR2GRAY)
            if g1.shape != g2.shape:
                g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]))

            orb = cv2.ORB_create(1500)
            k1, d1 = orb.detectAndCompute(g1, None)
            k2, d2 = orb.detectAndCompute(g2, None)
            n1 = len(k1) if k1 is not None else 0
            n2 = len(k2) if k2 is not None else 0
            if d1 is None or d2 is None or n1 < 20 or n2 < 20:
                return {
                    "ok": False,
                    "error": "not_enough_features",
                    "n1": n1,
                    "n2": n2,
                }

            bf = cv2.BFMatcher(cv2.NORM_HAMMING)
            knn = bf.knnMatch(d1, d2, k=2)
            good = []
            for pair in knn:
                if len(pair) < 2:
                    continue
                m, n = pair
                if m.distance < 0.75 * n.distance:
                    good.append(m)
            if len(good) < 12:
                return {
                    "ok": False,
                    "error": "not_enough_matches",
                    "n": len(good),
                }

            pts1 = np.float32([k1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            pts2 = np.float32([k2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, mask = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
            if H is None or mask is None:
                return {"ok": False, "error": "homography_failed"}
            inliers = int(mask.sum())
            if inliers < 10:
                return {
                    "ok": False,
                    "error": "not_enough_inliers",
                    "inliers": inliers,
                }

            h, w = g1.shape[:2]
            # Where Scout center lands in Sniper after homography
            c = np.float32([[[w / 2.0, h / 2.0]]])
            mapped = cv2.perspectiveTransform(c, H)[0, 0]
            med_dx = float(mapped[0] - w / 2.0)
            med_dy = float(mapped[1] - h / 2.0)
            err_yaw = (med_dx / w) * self.fov_h
            err_pitch = (med_dy / h) * self.fov_v

            if (abs(err_pitch) > self.align_max_bias
                    or abs(err_yaw) > self.align_max_bias):
                return {
                    "ok": False,
                    "error": "offset_too_large",
                    "residual_pitch_deg": round(err_pitch, 3),
                    "residual_yaw_deg": round(err_yaw, 3),
                    "inliers": inliers,
                    "hint": (
                        "Cameras may not share the same scene at home. "
                        "Point both at a nearby textured wall and retry, "
                        "or leave mount at 0 and let hunt refine online."
                    ),
                }

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
                "matches": len(good),
                "inliers": inliers,
                "mode": "homography_center",
                "median_dx_px": round(med_dx, 1),
                "median_dy_px": round(med_dy, 1),
                "residual_pitch_deg": round(err_pitch, 3),
                "residual_yaw_deg": round(err_yaw, 3),
                "pitch_bias_deg": round(bp, 3),
                "yaw_bias_deg": round(by, 3),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
