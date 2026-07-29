# Implements: SW-001 §2.13 — Autonomous Hunt Mode (Flask dashboard)
"""
hunt_controller.py — Track flying bugs: Scout motion → aim → Sniper YOLO
closed-loop center → fire → HitDetector splash confirm + online boresight.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from timeutil import stamp_iso
from typing import Callable, Optional, Tuple

from scout_vision import ScoutVision
from hardware import pixel_to_angle, compute_predictive_lead
from hunt_capture import HuntCaptureStore
from boresight import BoresightCorrector
from hit_verdict import evaluate_hit

FRAME_W = 1280
FRAME_H = 720
FOV_H = 62.2
FOV_V = 48.8

PREDICTION_LOOKAHEAD_SEC = 0.12
SETTLE_SEC = 0.07
POST_ENGAGEMENT_COOLDOWN_SEC = 1.0
SCAN_INTERVAL_SEC = 0.05
# Rejects fill the "recent 10" ring; insect detections ignore cooldown.
CAPTURE_COOLDOWN_SEC = 3.0
TRAJ_BURST_HZ = 28.0
TRAJ_BURST_TAIL_SEC = 0.25

# Flying-bug track window — longer so YOLO+refine can lock before timeout
TRACK_MAX_SEC = 4.0
TARGET_LOST_GRACE_SEC = 0.5
MAX_CENTER_REFINES = 8
# Fire even if not perfectly centered after this many refines / this much time
OPPORTUNITY_FIRE_AFTER_SEC = 1.2

INSECT_CLASSES = {
    "spider", "bees", "butterfly", "mantis", "ant", "beetle", "caterpillar",
    "centipedes", "cockroach", "dragonfly", "fly", "grasshopper",
    "ladybug", "mosquito", "wasp",
}
LARGE_OBJECT_NAMES = {"person", "bird"}


class HuntController:
    def __init__(
        self,
        gimbal,
        scout_cam,
        sniper_cam,
        accum,
        lidar,
        cal_table,
        primer=None,
        detector=None,
        velocity_tracker=None,
        hit_detector=None,
        is_busy: Optional[Callable[[], bool]] = None,
        settings_path: str = "settings.json",
        project_dir: Optional[str] = None,
    ):
        self._gimbal = gimbal
        self._scout_cam = scout_cam
        self._sniper_cam = sniper_cam
        self._accum = accum
        self._lidar = lidar
        self._cal_table = cal_table
        self._primer = primer
        self._detector = detector
        self._velocity_tracker = velocity_tracker
        self._hit_detector = hit_detector
        self._is_busy = is_busy or (lambda: False)

        root = project_dir or os.path.dirname(os.path.abspath(__file__))
        self._scout = ScoutVision(
            config_path=os.path.join(root, "scout_config.json"),
            settings_path=settings_path if os.path.isabs(settings_path)
            else os.path.join(root, settings_path),
        )

        self._insect_model = None
        self._load_insect_model(root)

        self.captures = HuntCaptureStore(os.path.join(root, "hunt_captures"))
        self.boresight = BoresightCorrector()
        # Mount / axis config — refined online; NOT seeded from nozzle cal
        # (nozzle cal was incorrectly pulling aim ~30° low during track).
        self._pitch_sign = 1.0
        self._yaw_sign = 1.0
        self._mount_pitch = 0.0
        self._mount_yaw = 0.0
        self._apply_nozzle_cal_on_fire = True
        self._settings_path = settings_path if os.path.isabs(settings_path) \
            else os.path.join(root, settings_path)
        self.reload_hunt_geometry()

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._alive = False
        self._enabled = False
        self._engaging = False

        self._detections = 0
        self._verifications = 0
        self._rejections = 0
        self._shot_count = 0
        self._hits = 0
        self._misses = 0
        self._last_engagement: Optional[dict] = None
        self._last_error: Optional[str] = None

    def _load_insect_model(self, root: str):
        try:
            from ultralytics import YOLO
        except ImportError:
            print("[Hunt] ultralytics missing — YOLO verify disabled")
            return
        for name in ("best.engine", "best.pt",
                     os.path.join("models", "trained", "best.engine"),
                     os.path.join("models", "trained", "best.pt")):
            path = name if os.path.isabs(name) else os.path.join(root, name)
            if not os.path.exists(path):
                continue
            try:
                self._insect_model = YOLO(path)
                print(f"[Hunt] Insect verify model: {path}")
                return
            except Exception as e:
                print(f"[Hunt] Failed to load {path}: {e}")
        print("[Hunt] No insect model found")

    def start(self) -> dict:
        arm_result = None
        try:
            if not self._accum.get_status().get("armed"):
                arm_result = self._accum.arm()
                if arm_result.get("status") != "armed":
                    self._last_error = arm_result.get("error", "arm_failed")
                    with self._lock:
                        self._enabled = True
                    self._ensure_worker()
                    return self.get_status(arm=arm_result)
        except Exception as e:
            self._last_error = str(e)
            with self._lock:
                self._enabled = True
            self._ensure_worker()
            return self.get_status(arm={"status": "error", "error": str(e)})

        with self._lock:
            self._enabled = True
            self._last_error = None
        self._ensure_worker()
        print("[Hunt] STARTED (hunting)")
        try:
            from activity_log import log_event
            log_event("HUNT_START", armed=True)
        except Exception:
            pass
        return self.get_status(arm=arm_result)

    def stop(self) -> dict:
        with self._lock:
            self._enabled = False
        print("[Hunt] STOP requested (pause after current shot)")
        try:
            from activity_log import log_event
            log_event("HUNT_STOP", engaging=self._engaging)
        except Exception:
            pass
        return self.get_status()

    def shutdown(self):
        with self._lock:
            self._enabled = False
            self._alive = False
        self._scout.stop()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)

    def get_status(self, arm=None) -> dict:
        armed = bool(self._accum.get_status().get("armed"))
        with self._lock:
            enabled = self._enabled
            engaging = self._engaging
            if enabled and armed:
                mode = "HUNTING"
            elif enabled and not armed:
                mode = "DISARMED"
            else:
                mode = "PAUSED"
            return {
                "mode": mode,
                "enabled": enabled,
                "armed": armed,
                "engaging": engaging,
                "shot_count": self._shot_count,
                "hits": self._hits,
                "misses": self._misses,
                "detections": self._detections,
                "verifications": self._verifications,
                "rejections": self._rejections,
                "last_engagement": self._last_engagement,
                "last_error": self._last_error,
                "insect_model": self._insect_model is not None,
                "capture_count": self.captures.count(),
                "captures": self.captures.counts(),
                "boresight": self.boresight.status(),
                "geometry": {
                    "pitch_sign": self._pitch_sign,
                    "yaw_sign": self._yaw_sign,
                    "fov_scale": getattr(self, "_fov_scale", 1.0),
                    "min_speed_px_s": getattr(self, "_min_speed_px_s", 80.0),
                    "yolo_conf": getattr(self, "_yolo_conf", 0.75),
                    "roi_zoom": getattr(self, "_roi_zoom", 2.0),
                    "center_ok_frac": getattr(self.boresight, "center_ok_frac", 0.12),
                    "opportunity_fire": getattr(self, "_opportunity_fire", False),
                    "mount_pitch": self._mount_pitch,
                    "mount_yaw": self._mount_yaw,
                },
                "arm": arm,
            }

    def reload_scout_config(self):
        self._scout.load_config()

    def reload_hunt_geometry(self):
        """Load hunt axis signs + sniper mount offsets from settings.json."""
        try:
            data = {}
            if os.path.isfile(self._settings_path):
                import json
                with open(self._settings_path, "r") as f:
                    data = json.load(f) or {}
            hunt = data.get("hunt") or {}
            self._pitch_sign = float(hunt.get("pitch_sign", 1.0)) or 1.0
            self._yaw_sign = float(hunt.get("yaw_sign", 1.0)) or 1.0
            self._fov_scale = float(hunt.get("fov_scale", 1.0)) or 1.0
            self._min_speed_px_s = max(
                0.0, float(hunt.get("min_speed_px_s", 80.0) or 0.0))
            self._yolo_conf = max(
                0.10, min(0.95, float(hunt.get("yolo_conf", 0.75) or 0.75)))
            self._roi_zoom = max(
                1.0, min(4.0, float(hunt.get("roi_zoom", 2.0) or 2.0)))
            center_frac = max(
                0.05, min(0.40, float(hunt.get("center_ok_frac", 0.12) or 0.12)))
            self.boresight.center_ok_frac = center_frac
            self._opportunity_fire = bool(hunt.get("opportunity_fire", False))
            self._mount_pitch = float(hunt.get("sniper_mount_pitch_deg", 0.0) or 0.0)
            self._mount_yaw = float(hunt.get("sniper_mount_yaw_deg", 0.0) or 0.0)
            self._apply_nozzle_cal_on_fire = bool(
                hunt.get("apply_nozzle_cal_on_fire", True))
            self.boresight.seed_from_cal(self._mount_pitch, self._mount_yaw)
            print(f"[Hunt] geometry: pitch_sign={self._pitch_sign} "
                  f"yaw_sign={self._yaw_sign} fov_scale={self._fov_scale} "
                  f"min_speed={self._min_speed_px_s:.0f}px/s "
                  f"yolo_conf={self._yolo_conf:.2f} roi_zoom={self._roi_zoom:.1f} "
                  f"center_ok={center_frac:.2f} "
                  f"opportunity_fire={self._opportunity_fire} "
                  f"mount=({self._mount_pitch},{self._mount_yaw}) "
                  f"nozzle_on_fire={self._apply_nozzle_cal_on_fire}")
        except Exception as e:
            print(f"[Hunt] geometry load skip: {e}")

    def _nozzle_offsets(self, distance_m: float, pitch: float, yaw: float):
        if not self._apply_nozzle_cal_on_fire:
            return 0.0, 0.0
        try:
            return self._cal_table.get_correction(
                distance_m=distance_m, pitch=pitch, yaw=yaw)
        except Exception:
            return 0.0, 0.0

    def align_scout_gimbal(self) -> dict:
        """
        Automatic Scout↔Sniper align at home pose.
        ORB feature match → mount bias; persists to settings.hunt.

        Single pass only: after a large bias move the cameras no longer share
        the same center scene, so a second ORB pass is misleading.
        """
        was_enabled = False
        with self._lock:
            was_enabled = self._enabled
            self._enabled = False  # pause hunt during align
        try:
            self._gimbal.center()
            time.sleep(0.8)
            scout = self._scout_cam.get_frame()
            sniper = self._sniper_cam.get_frame()
            result = self.boresight.estimate_from_frames(scout, sniper)
            if result.get("ok"):
                self._maybe_persist_mount(force=True)
                bp, by = self.boresight.get_bias()
                self._gimbal.set_angles(bp, by)
                time.sleep(0.35)
                result["boresight"] = self.boresight.status()
                result["message"] = (
                    f"Aligned. Mount bias pitch={result['boresight']['pitch_bias_deg']}° "
                    f"yaw={result['boresight']['yaw_bias_deg']}° "
                    f"(auto-saved). Hunt will use this continuously."
                )
            else:
                result["message"] = (
                    "Align failed: "
                    + str(result.get("error") or "unknown")
                    + ". Point both cameras at a textured scene and retry."
                )
            return result
        finally:
            if was_enabled:
                with self._lock:
                    self._enabled = True

    def _maybe_persist_mount(self, force: bool = False):
        """Auto-save learned Scout↔Sniper mount bias into settings.hunt."""
        bp, by = self.boresight.get_bias()
        self._mount_pitch, self._mount_yaw = bp, by
        now = time.monotonic()
        if not force and now - getattr(self, "_last_persist_mono", 0.0) < 30.0:
            return
        self._last_persist_mono = now
        try:
            import json
            path = self._settings_path
            data = {}
            if os.path.isfile(path):
                with open(path, "r") as f:
                    data = json.load(f) or {}
            hunt = data.setdefault("hunt", {})
            hunt["sniper_mount_pitch_deg"] = round(bp, 3)
            hunt["sniper_mount_yaw_deg"] = round(by, 3)
            hunt.setdefault("pitch_sign", self._pitch_sign)
            hunt.setdefault("yaw_sign", self._yaw_sign)
            hunt.setdefault("fov_scale", getattr(self, "_fov_scale", 1.0))
            hunt.setdefault(
                "min_speed_px_s", getattr(self, "_min_speed_px_s", 80.0))
            hunt.setdefault("apply_nozzle_cal_on_fire", self._apply_nozzle_cal_on_fire)
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
            print(f"[Hunt] auto-saved mount bias pitch={bp:.2f} yaw={by:.2f}")
        except Exception as e:
            print(f"[Hunt] mount persist skip: {e}")

    def _ensure_worker(self):
        with self._lock:
            if self._alive and self._thread and self._thread.is_alive():
                return
            self._alive = True
        self._scout.start(external_frames=True)
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="hunt-loop")
        self._thread.start()

    def _loop(self):
        print("[Hunt] Worker loop running")
        while True:
            with self._lock:
                if not self._alive:
                    break
                enabled = self._enabled
            if not enabled:
                time.sleep(0.15)
                continue
            if self._is_busy():
                time.sleep(0.2)
                continue
            try:
                self._scan_once()
            except Exception as e:
                self._last_error = str(e)
                print(f"[Hunt] scan error: {e}")
                time.sleep(0.5)
            time.sleep(SCAN_INTERVAL_SEC)
        print("[Hunt] Worker loop exited")

    def _scan_once(self):
        frame = self._scout_cam.get_frame()
        self.captures.tick(frame, self._sniper_cam.get_frame())
        if frame is None:
            return
        self._scout.process_frame(frame)
        tx, ty, vx, vy = self._scout.get_target_with_velocity()
        if tx is None or ty is None:
            if self._velocity_tracker is not None:
                self._velocity_tracker.reset()
            return

        # Outdoor temper: ignore slow/static MOG2 blobs (leaves, shadows)
        min_spd = getattr(self, "_min_speed_px_s", 0.0)
        if min_spd > 0.0:
            speed = (float(vx) ** 2 + float(vy) ** 2) ** 0.5
            if speed < min_spd:
                return

        with self._lock:
            self._detections += 1
            if not self._enabled:
                return
            self._engaging = True
        try:
            self._track_and_engage(tx, ty, vx, vy)
        finally:
            with self._lock:
                self._engaging = False

    def _aim_from_scout(self, tx, ty, vx, vy, *, for_fire: bool = False
                        ) -> Tuple[float, float, float]:
        """
        Scout pixel → gimbal command so Sniper *camera* looks at the motion.

        Track path: scout FOV + axis signs + mount/boresight (camera alignment).
        Fire path: same + nozzle calibration offsets (water vs camera).
        """
        pred_x = max(0, min(FRAME_W, tx + vx * PREDICTION_LOOKAHEAD_SEC))
        pred_y = max(0, min(FRAME_H, ty + vy * PREDICTION_LOOKAHEAD_SEC))
        if self._velocity_tracker is not None:
            self._velocity_tracker.update(int(pred_x), int(pred_y))

        raw_pitch, raw_yaw = pixel_to_angle(
            int(pred_x), int(pred_y), FRAME_W, FRAME_H, FOV_H, FOV_V)
        scale = getattr(self, "_fov_scale", 1.0)
        raw_pitch *= self._pitch_sign * scale
        raw_yaw *= self._yaw_sign * scale

        # Camera alignment: mount + online boresight (NOT nozzle cal)
        bp, by = self.boresight.get_bias()
        raw_pitch += bp
        raw_yaw += by

        distance_m = self._lidar.read_distance()
        omega_p, omega_y = (0.0, 0.0)
        if self._velocity_tracker is not None:
            omega_p, omega_y = self._velocity_tracker.get_angular_velocity()

        psi = None
        try:
            psi = float(self._accum.TARGET_PSI)
        except Exception:
            pass
        aim_pitch, aim_yaw, _ = compute_predictive_lead(
            raw_pitch, raw_yaw, distance_m, omega_p, omega_y, psi=psi)

        if for_fire:
            np_, ny_ = self._nozzle_offsets(distance_m, aim_pitch, aim_yaw)
            aim_pitch += np_
            aim_yaw += ny_

        self._gimbal.set_angles(aim_pitch, aim_yaw)
        return aim_pitch, aim_yaw, distance_m

    def _track_and_engage(self, tx, ty, vx, vy):
        """Follow Scout blob; closed-loop Sniper YOLO center; fire; hit-verify."""
        t0 = time.monotonic()
        last_seen = t0
        aim_pitch = aim_yaw = 0.0
        distance_m = 0.0
        last_detail = "tracking"
        last_boxes = []
        last_tx, last_ty = int(tx), int(ty)
        saw_insect = False
        last_center = None
        refine_count = 0

        while time.monotonic() - t0 < TRACK_MAX_SEC:
            with self._lock:
                if not self._enabled:
                    return

            frame = self._scout_cam.get_frame()
            if frame is not None:
                self._scout.process_frame(frame)
            sx, sy, svx, svy = self._scout.get_target_with_velocity()
            if sx is None:
                if time.monotonic() - last_seen > TARGET_LOST_GRACE_SEC:
                    break
                time.sleep(0.03)
                continue

            last_seen = time.monotonic()
            last_tx, last_ty = int(sx), int(sy)
            aim_pitch, aim_yaw, distance_m = self._aim_from_scout(sx, sy, svx, svy)
            time.sleep(SETTLE_SEC)

            verified, detail, boxes, center = self._verify_sniper()
            with self._lock:
                self._verifications += 1
            last_detail, last_boxes = detail, boxes
            if verified and center is not None:
                saw_insect = True
                last_center = center

            if not verified or center is None:
                time.sleep(0.03)
                continue

            elapsed = time.monotonic() - t0
            centered = self.boresight.is_centered(center[0], center[1])
            allow_opportunity = bool(getattr(self, "_opportunity_fire", False))
            # Closed-loop refine toward insect, but don't miss the shot window
            if (not centered and refine_count < MAX_CENTER_REFINES
                    and elapsed < OPPORTUNITY_FIRE_AFTER_SEC + 1.5):
                err_p, err_y = self.boresight.update_from_sniper_point(
                    center[0], center[1])
                self._maybe_persist_mount()
                st = self._gimbal.get_status()
                self._gimbal.set_angles(
                    float(st.get("pitch", aim_pitch)) + err_p,
                    float(st.get("yaw", aim_yaw)) + err_y,
                )
                refine_count += 1
                print(f"[Hunt] Track refine #{refine_count} Δp={err_p:.2f} Δy={err_y:.2f} "
                      f"bias={self.boresight.status()} ({detail})")
                time.sleep(SETTLE_SEC)
                # Optional: after enough time/refines, fire even if not perfect
                if (allow_opportunity and refine_count >= 2
                        and elapsed >= OPPORTUNITY_FIRE_AFTER_SEC):
                    pass  # fall through to fire below
                else:
                    continue
            elif not centered:
                if allow_opportunity and elapsed >= OPPORTUNITY_FIRE_AFTER_SEC:
                    pass  # fall through
                else:
                    continue

            # Verified insect — fire when centered (or opportunity if enabled)
            if not centered and not allow_opportunity:
                continue
            aim_pitch, aim_yaw, distance_m = self._aim_from_scout(
                last_tx, last_ty, 0.0, 0.0, for_fire=True)
            # Final nudge toward last insect pixel so nozzle tracks the bug
            if last_center is not None and not self.boresight.is_centered(
                    last_center[0], last_center[1]):
                err_p, err_y = self.boresight.pixel_error_to_deg(
                    last_center[0], last_center[1])
                st = self._gimbal.get_status()
                self._gimbal.set_angles(
                    float(st.get("pitch", aim_pitch)) + err_p,
                    float(st.get("yaw", aim_yaw)) + err_y,
                )
                time.sleep(SETTLE_SEC)
            else:
                time.sleep(SETTLE_SEC)
            self._fire_and_verify_hit(
                target_px=(last_tx, last_ty),
                aim_pitch=aim_pitch,
                aim_yaw=aim_yaw,
                distance_m=distance_m,
                detail=detail + ("" if centered else "|opportunity"),
                boxes=boxes,
            )
            return

        # End of track: optional opportunity shot if insect was seen but never centered
        if (getattr(self, "_opportunity_fire", False)
                and saw_insect and last_center is not None):
            print(f"[Hunt] Opportunity fire at end of track ({last_detail})")
            err_p, err_y = self.boresight.pixel_error_to_deg(
                last_center[0], last_center[1])
            st = self._gimbal.get_status()
            self._gimbal.set_angles(
                float(st.get("pitch", aim_pitch)) + err_p,
                float(st.get("yaw", aim_yaw)) + err_y,
            )
            time.sleep(SETTLE_SEC)
            aim_pitch, aim_yaw, distance_m = self._aim_from_scout(
                last_tx, last_ty, 0.0, 0.0, for_fire=True)
            time.sleep(SETTLE_SEC)
            self._fire_and_verify_hit(
                target_px=(last_tx, last_ty),
                aim_pitch=aim_pitch,
                aim_yaw=aim_yaw,
                distance_m=distance_m,
                detail=str(last_detail) + "|end_track_opportunity",
                boxes=last_boxes,
            )
            return

        with self._lock:
            self._rejections += 1
        print(f"[Hunt] Track end / reject: {last_detail}")
        self._record_attempt(
            result="rejected",
            verify=last_detail,
            target_px=(last_tx, last_ty),
            aim_pitch=aim_pitch,
            aim_yaw=aim_yaw,
            distance_m=distance_m,
            boxes=last_boxes,
            insect_detected=saw_insect,
        )

    def _fire_and_verify_hit(self, *, target_px, aim_pitch, aim_yaw,
                             distance_m, detail, boxes):
        if not self._accum.get_status().get("armed"):
            arm = self._accum.arm()
            if arm.get("status") != "armed":
                self._last_error = arm.get("error", "arm_failed")
                self._record_attempt(
                    result="fire_failed",
                    verify=f"arm:{self._last_error}",
                    target_px=target_px,
                    aim_pitch=aim_pitch,
                    aim_yaw=aim_yaw,
                    distance_m=distance_m,
                    boxes=boxes,
                    insect_detected=True,
                )
                return

        if self._hit_detector is not None:
            try:
                # Noise floor + AE settle so dry flicker ≠ splash
                self._hit_detector.measure_noise_floor(self._sniper_cam, samples=3)
                self._hit_detector.capture_before_stable(self._sniper_cam)
            except Exception as e:
                print(f"[Hunt] hit before-capture: {e}")
                try:
                    self._hit_detector.capture_before(self._sniper_cam)
                except Exception:
                    pass

        # Burst-grab Sniper frames during the pulse → water trajectory strip
        traj_frames: list = []
        stop_burst = threading.Event()

        def _traj_burst():
            period = 1.0 / TRAJ_BURST_HZ
            while not stop_burst.is_set() and len(traj_frames) < 16:
                f = self._sniper_cam.get_frame()
                if f is not None:
                    traj_frames.append(f.copy())
                time.sleep(period)

        burst_t = threading.Thread(
            target=_traj_burst, daemon=True, name="hunt-traj-burst")
        burst_t.start()
        result = self._accum.fire()
        time.sleep(TRAJ_BURST_TAIL_SEC)
        stop_burst.set()
        burst_t.join(timeout=1.0)

        if self._primer is not None:
            try:
                self._primer.mark_fired()
            except Exception:
                pass

        ok = result.get("status") == "fired"
        hit_px = None
        noise = 0.0
        if self._hit_detector is not None:
            try:
                noise = float(self._hit_detector.get_state().get("noise_floor_pct") or 0.0)
            except Exception:
                pass

        if ok and self._hit_detector is not None:
            try:
                self._hit_detector.capture_after_burst(self._sniper_cam)
                hit_px_t = self._hit_detector.detect(
                    aim_xy=(FRAME_W // 2, FRAME_H // 2),
                    noise_floor_pct=noise,
                    distance_m=distance_m,
                )
                if hit_px_t is not None:
                    hit_px = list(hit_px_t)
            except Exception as e:
                print(f"[Hunt] hit detect: {e}")

        verdict = evaluate_hit(
            boxes=boxes,
            traj_frames=traj_frames,
            hit_px=hit_px,
            distance_m=distance_m,
        ) if ok else {
            "score": 0, "max_score": 3, "min_score": 2,
            "hit_confirmed": False, "label": "MISS",
            "summary": "MISS (fire_failed)", "signals": {},
        }
        hit_confirmed = bool(verdict.get("hit_confirmed")) if ok else False

        if ok and hit_confirmed and hit_px is not None:
            try:
                self.boresight.update_from_sniper_point(hit_px[0], hit_px[1])
                self._maybe_persist_mount()
            except Exception:
                pass

        with self._lock:
            if ok:
                self._shot_count += 1
                if hit_confirmed:
                    self._hits += 1
                else:
                    self._misses += 1
            self._last_engagement = {
                "timestamp": stamp_iso(),
                "target_px": [int(target_px[0]), int(target_px[1])],
                "aim_pitch": round(aim_pitch, 2),
                "aim_yaw": round(aim_yaw, 2),
                "distance_m": round(distance_m, 2),
                "verify": detail,
                "fire_status": result.get("status"),
                "shot_count": self._shot_count,
                "result": "fired" if ok else "fire_failed",
                "hit_confirmed": hit_confirmed,
                "hit_px": hit_px,
                "hit_verdict": verdict,
                "traj_frames": len(traj_frames),
                "boresight": self.boresight.status(),
            }

        outcome = "fired" if ok else "fire_failed"
        print(
            f"[Hunt] {'FIRE' if ok else 'FIRE FAIL'} "
            f"#{self._shot_count} {verdict.get('summary')} traj={len(traj_frames)} "
            f"({detail}) bias={self.boresight.status()}"
        )
        try:
            from activity_log import log_event
            log_event("HUNT_FIRE", ok=ok, hit=hit_confirmed,
                      score=verdict.get("score"), label=verdict.get("label"),
                      shot=self._shot_count, verify=detail)
        except Exception:
            pass

        self._record_attempt(
            result=outcome,
            verify=detail,
            target_px=target_px,
            aim_pitch=aim_pitch,
            aim_yaw=aim_yaw,
            distance_m=distance_m,
            boxes=boxes,
            hit_confirmed=hit_confirmed,
            hit_px=hit_px,
            insect_detected=True,
            trajectory_frames=traj_frames,
            hit_verdict=verdict,
        )
        time.sleep(POST_ENGAGEMENT_COOLDOWN_SEC)

    def _record_attempt(self, *, result, verify, target_px, aim_pitch, aim_yaw,
                        distance_m, boxes=None, hit_confirmed=None, hit_px=None,
                        insect_detected: bool = False, trajectory_frames=None,
                        hit_verdict=None):
        try:
            aid = self.captures.save_attempt_async(
                result=result,
                verify=verify,
                target_px=target_px,
                aim_pitch=aim_pitch,
                aim_yaw=aim_yaw,
                distance_m=distance_m,
                scout_cam=self._scout_cam,
                sniper_cam=self._sniper_cam,
                boxes=boxes,
                cooldown_sec=0.0 if insect_detected else CAPTURE_COOLDOWN_SEC,
                hit_confirmed=hit_confirmed,
                hit_px=hit_px,
                insect_detected=insect_detected,
                trajectory_frames=trajectory_frames,
                hit_verdict=hit_verdict,
            )
            with self._lock:
                eng = {
                    "timestamp": stamp_iso(),
                    "target_px": [int(target_px[0]), int(target_px[1])],
                    "aim_pitch": round(aim_pitch, 2),
                    "aim_yaw": round(aim_yaw, 2),
                    "distance_m": round(distance_m, 2),
                    "verify": verify,
                    "result": result,
                    "hit_confirmed": hit_confirmed,
                    "hit_px": hit_px,
                    "hit_verdict": hit_verdict,
                    "boresight": self.boresight.status(),
                }
                if aid:
                    eng["capture_id"] = aid
                self._last_engagement = eng
        except Exception as e:
            print(f"[Hunt] capture failed: {e}")

    def _sniper_yolo_view(self, frame):
        """
        Digital zoom on frame center before YOLO.

        Keeps full-sensor capture cheap (1280×720) but magnifies the crosshair
        region so flies/bees/mosquitoes occupy more pixels — matches the project
        thesis that we don't need native high-res if we ROI wisely.
        Returns (view_bgr, mapper) where mapper(cx,cy)->full-frame (x,y).
        """
        zoom = float(getattr(self, "_roi_zoom", 1.0) or 1.0)
        if zoom <= 1.01 or frame is None:
            return frame, (lambda x, y: (int(x), int(y)))

        try:
            import cv2
        except ImportError:
            return frame, (lambda x, y: (int(x), int(y)))

        h, w = frame.shape[:2]
        cw = max(32, int(round(w / zoom)))
        ch = max(32, int(round(h / zoom)))
        x0 = max(0, (w - cw) // 2)
        y0 = max(0, (h - ch) // 2)
        crop = frame[y0:y0 + ch, x0:x0 + cw]
        view = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)

        def mapper(vx, vy, _x0=x0, _y0=y0, _cw=cw, _ch=ch, _w=w, _h=h):
            fx = _x0 + (float(vx) / max(_w, 1)) * _cw
            fy = _y0 + (float(vy) / max(_h, 1)) * _ch
            return int(fx), int(fy)

        return view, mapper

    def _verify_sniper(self):
        """Return (ok, detail, boxes, center_xy|None). YOLO insects required."""
        frame = self._sniper_cam.get_frame()
        if frame is None:
            return False, "no_sniper_frame", [], None

        if self._insect_model is None:
            return False, "no_insect_model", [], None

        conf_min = float(getattr(self, "_yolo_conf", 0.75) or 0.75)
        view, mapper = self._sniper_yolo_view(frame)

        try:
            # Run slightly below gate so we can log near-misses in detail
            results = self._insect_model(view, conf=max(0.10, conf_min * 0.5),
                                         verbose=False)
            boxes = []
            best = None  # (conf, name, cx, cy)
            near = None
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = str(r.names.get(cls_id, "")).lower()
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    # Map from zoomed view back to full Sniper frame
                    cx_v, cy_v = (x1 + x2) // 2, (y1 + y2) // 2
                    cx, cy = mapper(cx_v, cy_v)
                    fx1, fy1 = mapper(x1, y1)
                    fx2, fy2 = mapper(x2, y2)
                    boxes.append({
                        "bbox": (fx1, fy1, fx2, fy2),
                        "label": f"{name} {conf:.0%}",
                        "class": name,
                        "confidence": conf,
                    })
                    if name in INSECT_CLASSES:
                        if near is None or conf > near[0]:
                            near = (conf, name, cx, cy)
                        if conf >= conf_min:
                            if best is None or conf > best[0]:
                                best = (conf, name, cx, cy)
            if best:
                return True, f"{best[1]}:{best[0]:.2f}", boxes, (best[2], best[3])
            if near is not None:
                return False, f"no_insect:best={near[1]}:{near[0]:.2f}", boxes, None
            return False, "no_insect", boxes, None
        except Exception as e:
            return False, f"insect_err:{e}", [], None
