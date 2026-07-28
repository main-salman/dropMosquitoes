# Implements: SW-001 §2.13 — Multi-signal water-hit verdict
"""
hit_verdict.py — Confidence that water hit the locked insect.

Core signals (always scored; HIT if ≥2/3):
  1. insect_locked     — YOLO insect near Sniper crosshair at fire
  2. traj_through_path — jet motion along ballistic corridor through insect
  3. ballistic_on_target — insect bbox meets aim + gravity corridor at range

Splash (optional — often invisible at range / off-angle):
  - Not detected → N/A (does not count for or against)
  - Detected near gravity-aware expected impact → confirms
  - Detected far from expected impact → vetoes HIT (contradiction)

PSI drop is NOT used (accumulator pressure flutters continuously).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

try:
    import cv2
    CV2 = True
except ImportError:
    CV2 = False

FRAME_W = 1280
FRAME_H = 720
FOV_V = 48.8
LOCK_FRAC = 0.14
BBOX_PAD_PX = 28
TRAJ_DIFF_THRESH = 35
TRAJ_MIN_CHANGED = 80
CORE_HIT_MIN = 2          # ≥2 of 3 core → HIT (unless splash vetoes)
# Mild stream arc in image (positive Y = down). Mostly straight; grows past 3 m.
DROP_DEG_PER_M_OVER_3 = 0.5
DROP_DEG_PER_M_NEAR = 0.12   # slight arc even under 3 m


def _best_insect_box(boxes: Optional[list]) -> Optional[dict]:
    if not boxes:
        return None
    best = None
    for b in boxes:
        name = str(b.get("class") or "").lower()
        conf = float(b.get("confidence") or 0.0)
        bbox = b.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        score = conf + (0.01 if name else 0.0)
        if best is None or score > best[0]:
            best = (score, b)
    return best[1] if best else None


def _bbox_center(bbox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def _clamp_box(x1, y1, x2, y2, w=FRAME_W, h=FRAME_H):
    return (
        max(0, int(x1)), max(0, int(y1)),
        min(w - 1, int(x2)), min(h - 1, int(y2)),
    )


def _point_in_box(px, py, box) -> bool:
    x1, y1, x2, y2 = box
    return x1 <= px <= x2 and y1 <= py <= y2


def drop_deg_for_distance(distance_m: Optional[float]) -> float:
    """Expected downward stream arc in degrees (image +pitch / +Y)."""
    if distance_m is None or distance_m < 0.3:
        return 0.0
    d = float(distance_m)
    near = DROP_DEG_PER_M_NEAR * min(d, 3.0)
    far = DROP_DEG_PER_M_OVER_3 * max(0.0, d - 3.0)
    return near + far


def drop_px_for_distance(distance_m: Optional[float],
                         frame_h: int = FRAME_H, fov_v: float = FOV_V) -> float:
    return drop_deg_for_distance(distance_m) * (frame_h / fov_v)


def ballistic_corridor(bbox, distance_m: Optional[float],
                       pad: int = BBOX_PAD_PX) -> Tuple[int, int, int, int]:
    """
    Insect bbox expanded, with extra pad below for gravity arc at range.
    Jet is mostly straight; corridor widens downward with distance.
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    drop_px = int(round(drop_px_for_distance(distance_m)))
    return _clamp_box(
        x1 - pad,
        y1 - pad,
        x2 + pad,
        y2 + pad + drop_px,
    )


def expected_splash_xy(bbox, distance_m: Optional[float],
                       aim_xy: Tuple[int, int] = (FRAME_W // 2, FRAME_H // 2)
                       ) -> Tuple[float, float]:
    """
    Where splash should appear if jet is mostly straight with mild drop.
    Prefer insect center (we aimed there); bias slightly downward with range
    for residual arc after aim compensation.
    """
    if bbox is not None:
        cx, cy = _bbox_center(bbox)
    else:
        cx, cy = float(aim_xy[0]), float(aim_xy[1])
    return cx, cy + 0.5 * drop_px_for_distance(distance_m)


def signal_insect_locked(boxes: Optional[list],
                         frame_w: int = FRAME_W, frame_h: int = FRAME_H,
                         lock_frac: float = LOCK_FRAC) -> Dict[str, Any]:
    box = _best_insect_box(boxes)
    if box is None:
        return {"ok": False, "na": False, "reason": "no_insect_box", "bbox": None}
    cx, cy = _bbox_center(box["bbox"])
    nx = abs(cx / frame_w - 0.5)
    ny = abs(cy / frame_h - 0.5)
    ok = nx <= lock_frac and ny <= lock_frac
    return {
        "ok": ok,
        "na": False,
        "reason": "ok" if ok else "off_crosshair",
        "bbox": list(box["bbox"]),
        "center": [round(cx, 1), round(cy, 1)],
        "class": box.get("class"),
        "confidence": box.get("confidence"),
        "norm_err": [round(nx, 3), round(ny, 3)],
    }


def signal_ballistic_on_target(bbox, distance_m: Optional[float],
                               aim_xy: Tuple[int, int] = (FRAME_W // 2, FRAME_H // 2)
                               ) -> Dict[str, Any]:
    """Insect overlaps aim point and/or gravity-aware expected impact."""
    if bbox is None:
        return {"ok": False, "na": False, "reason": "no_bbox"}
    corridor = ballistic_corridor(bbox, distance_m)
    ex, ey = expected_splash_xy(bbox, distance_m, aim_xy=aim_xy)
    aim_in = _point_in_box(aim_xy[0], aim_xy[1], corridor)
    exp_in = _point_in_box(int(ex), int(ey), corridor)
    # Aim or expected impact must sit in the insect+drop corridor
    ok = aim_in or exp_in or _point_in_box(aim_xy[0], aim_xy[1],
                                           _clamp_box(bbox[0] - BBOX_PAD_PX,
                                                      bbox[1] - BBOX_PAD_PX,
                                                      bbox[2] + BBOX_PAD_PX,
                                                      bbox[3] + BBOX_PAD_PX))
    return {
        "ok": bool(ok),
        "na": False,
        "reason": "ok" if ok else "aim_misses_corridor",
        "corridor": list(corridor),
        "expected_xy": [round(ex, 1), round(ey, 1)],
        "drop_deg": round(drop_deg_for_distance(distance_m), 3),
        "drop_px": round(drop_px_for_distance(distance_m), 1),
        "distance_m": distance_m,
    }


def signal_traj_through_path(traj_frames: Optional[list], bbox,
                             distance_m: Optional[float] = None) -> Dict[str, Any]:
    if not CV2 or not traj_frames or len(traj_frames) < 2 or bbox is None:
        return {"ok": False, "na": False, "reason": "no_traj_or_bbox", "changed": 0}
    x1, y1, x2, y2 = ballistic_corridor(bbox, distance_m)
    if x2 <= x1 or y2 <= y1:
        return {"ok": False, "na": False, "reason": "bad_bbox", "changed": 0}

    base = traj_frames[0]
    if base is None:
        return {"ok": False, "na": False, "reason": "no_base", "changed": 0}
    g0 = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    g0 = cv2.GaussianBlur(g0, (5, 5), 0)
    changed = 0
    used = 0
    for fr in traj_frames[1:]:
        if fr is None:
            continue
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g, (5, 5), 0)
        if g.shape != g0.shape:
            g = cv2.resize(g, (g0.shape[1], g0.shape[0]))
        diff = cv2.absdiff(g0, g)
        roi = diff[y1:y2, x1:x2]
        _, th = cv2.threshold(roi, TRAJ_DIFF_THRESH, 255, cv2.THRESH_BINARY)
        changed += int(cv2.countNonZero(th))
        used += 1
    ok = used > 0 and changed >= TRAJ_MIN_CHANGED
    return {
        "ok": ok,
        "na": False,
        "reason": "ok" if ok else "no_jet_in_corridor",
        "changed": changed,
        "frames_used": used,
        "corridor": [x1, y1, x2, y2],
        "drop_px": round(drop_px_for_distance(distance_m), 1),
    }


def signal_splash_optional(hit_px, bbox, distance_m: Optional[float] = None
                           ) -> Dict[str, Any]:
    """
    Splash is often invisible — N/A unless HitDetector found one.
    When found, must land near gravity-aware expected impact (not raw bbox only).
    """
    if hit_px is None:
        return {
            "ok": False,
            "na": True,
            "reason": "splash_not_visible",
            "note": "common at range / off-angle — ignored",
        }
    if bbox is None:
        return {"ok": False, "na": True, "reason": "no_bbox_for_splash"}

    ex, ey = expected_splash_xy(bbox, distance_m)
    drop_px = drop_px_for_distance(distance_m)
    # Elliptical tolerance: wider below expected (arc uncertainty)
    tol_x = 56 + 0.15 * drop_px
    tol_y_up = 40
    tol_y_down = 56 + drop_px
    px, py = int(hit_px[0]), int(hit_px[1])
    dx = abs(px - ex)
    if py >= ey:
        dy_ok = (py - ey) <= tol_y_down
    else:
        dy_ok = (ey - py) <= tol_y_up
    ok = dx <= tol_x and dy_ok
    dist = ((px - ex) ** 2 + (py - ey) ** 2) ** 0.5
    return {
        "ok": ok,
        "na": False,
        "reason": "ok" if ok else "splash_far_from_expected",
        "hit_px": [px, py],
        "expected_xy": [round(ex, 1), round(ey, 1)],
        "dist_to_expected": round(float(dist), 1),
        "tol_x": round(tol_x, 1),
        "tol_y_down": round(tol_y_down, 1),
        "drop_px": round(drop_px, 1),
        "distance_m": distance_m,
        "veto": (not ok),  # visible but wrong place → blocks HIT
    }


def evaluate_hit(
    *,
    boxes: Optional[list] = None,
    traj_frames: Optional[list] = None,
    hit_px=None,
    distance_m: Optional[float] = None,
    # legacy kwargs ignored (PSI is not a hit signal)
    psi_before=None,
    psi_after=None,
    min_score: int = CORE_HIT_MIN,
) -> Dict[str, Any]:
    """
    Core HIT if ≥2/3 of lock / traj / ballistic.
    Splash N/A when invisible; vetoes HIT if visible but far from expected.
    """
    _ = (psi_before, psi_after)  # explicitly unused
    s_lock = signal_insect_locked(boxes)
    bbox = s_lock.get("bbox")
    s_ball = signal_ballistic_on_target(bbox, distance_m)
    s_traj = signal_traj_through_path(traj_frames, bbox, distance_m=distance_m)
    s_splash = signal_splash_optional(hit_px, bbox, distance_m=distance_m)

    core = {
        "insect_locked": s_lock,
        "traj_through_path": s_traj,
        "ballistic_on_target": s_ball,
    }
    core_score = sum(1 for s in core.values() if s.get("ok"))
    splash_veto = bool(s_splash.get("veto"))
    splash_confirm = bool(s_splash.get("ok") and not s_splash.get("na"))

    hit_confirmed = (core_score >= min_score) and not splash_veto
    if splash_veto:
        label = "MISS"
    elif hit_confirmed and splash_confirm:
        label = "HIT"
    elif hit_confirmed:
        label = "HIT"  # splash not required
    elif core_score == 1 or (core_score >= 1 and splash_confirm):
        label = "PROBABLE"
    else:
        label = "MISS"

    def _mark(s):
        if s.get("na"):
            return "—"
        return "Y" if s.get("ok") else "N"

    signals = {**core, "splash_optional": s_splash}
    return {
        "score": core_score,
        "max_score": 3,
        "min_score": min_score,
        "hit_confirmed": hit_confirmed,
        "label": label,
        "splash_na": bool(s_splash.get("na")),
        "splash_confirm": splash_confirm,
        "splash_veto": splash_veto,
        "signals": signals,
        "summary": (
            f"{label} {core_score}/3 "
            f"[lock={_mark(s_lock)} traj={_mark(s_traj)} ball={_mark(s_ball)} "
            f"splash={_mark(s_splash)}]"
        ),
    }
