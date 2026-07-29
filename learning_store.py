# Implements: SW-001 §2.15 — Operator-feedback reinforcement (splash + insect ID)
"""
learning_store.py — Online reinforcement from operator feedback.

Splash priors (cal/hunt) + insect-class suppress policy (insect_train dry-fire).
Human reward → EMA updates. Not offline neural RL on the Jetson.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from timeutil import stamp_iso

DEFAULT_STATE = {
    "version": 2,
    "n_correct": 0,
    "n_wrong": 0,
    "n_corrections_xy": 0,
    "right_bias_px": 70.0,
    "below_bonus": 0.85,
    "prior_sigma_frac": 0.12,
    "prior_strength": 0.55,
    "insect": {
        "n_correct": 0,
        "n_wrong": 0,
        "by_class": {},   # class -> {correct, wrong, suppress}
    },
    "events": [],
}

MAX_EVENTS = 200
ALPHA = 0.22
REWARD_ALPHA = 0.08
INSECT_ALPHA = 0.20


def _as_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


class LearningStore:
    def __init__(self, root_dir: str, filename: str = "learning_state.json"):
        self.path = os.path.join(root_dir, filename)
        self._lock = threading.Lock()
        self._state = json.loads(json.dumps(DEFAULT_STATE))
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            data = json.load(open(self.path, "r"))
            if not isinstance(data, dict):
                return
            merged = json.loads(json.dumps(DEFAULT_STATE))
            for k in DEFAULT_STATE:
                if k == "insect":
                    continue
                if k in data:
                    merged[k] = data[k]
            insect = data.get("insect") if isinstance(data.get("insect"), dict) else {}
            merged["insect"] = {
                "n_correct": int(insect.get("n_correct", 0) or 0),
                "n_wrong": int(insect.get("n_wrong", 0) or 0),
                "by_class": dict(insect.get("by_class") or {}),
            }
            if isinstance(data.get("events"), list):
                merged["events"] = data["events"][-MAX_EVENTS:]
            self._state = merged
        except Exception as e:
            print(f"[Learning] load failed: {e}")

    def _save_unlocked(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._state, f, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    def _priors_unlocked(self) -> Dict[str, float]:
        return {
            "right_bias_px": float(self._state["right_bias_px"]),
            "below_bonus": float(self._state["below_bonus"]),
            "prior_sigma_frac": float(self._state["prior_sigma_frac"]),
            "prior_strength": float(self._state["prior_strength"]),
        }

    def _insect_unlocked(self) -> Dict[str, Any]:
        insect = self._state.get("insect") or {}
        by = insect.get("by_class") or {}
        suppress = {
            str(k): float((v or {}).get("suppress", 0.0) or 0.0)
            for k, v in by.items()
        }
        return {
            "n_correct": int(insect.get("n_correct", 0) or 0),
            "n_wrong": int(insect.get("n_wrong", 0) or 0),
            "by_class": by,
            "suppress": suppress,
        }

    def get_priors(self) -> Dict[str, float]:
        with self._lock:
            return self._priors_unlocked()

    def get_insect_policy(self) -> Dict[str, Any]:
        """Per-class suppress in [0,1] → hunt raises effective conf gate."""
        with self._lock:
            return self._insect_unlocked()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            ev = self._state.get("events") or []
            return {
                "n_correct": self._state["n_correct"],
                "n_wrong": self._state["n_wrong"],
                "n_corrections_xy": self._state["n_corrections_xy"],
                "priors": self._priors_unlocked(),
                "insect": self._insect_unlocked(),
                "last_events": ev[-12:],
                "path": self.path,
            }

    def apply_to_detector(self, detector) -> None:
        p = self.get_priors()
        if detector is None:
            return
        try:
            detector.RIGHT_BIAS_PX = float(p["right_bias_px"])
            detector.BELOW_BONUS = float(p["below_bonus"])
            detector.PRIOR_SIGMA_FRAC = float(p["prior_sigma_frac"])
            detector.PRIOR_STRENGTH = float(p["prior_strength"])
            print(f"[Learning] splash priors right={detector.RIGHT_BIAS_PX:.0f}px "
                  f"below={detector.BELOW_BONUS:.2f} sigma={detector.PRIOR_SIGMA_FRAC:.3f} "
                  f"strength={detector.PRIOR_STRENGTH:.2f}")
        except Exception as e:
            print(f"[Learning] apply_to_detector: {e}")

    def _class_bucket_unlocked(self, name: str) -> dict:
        insect = self._state.setdefault("insect", {"n_correct": 0, "n_wrong": 0, "by_class": {}})
        by = insect.setdefault("by_class", {})
        key = (name or "unknown").lower().strip() or "unknown"
        if key not in by or not isinstance(by[key], dict):
            by[key] = {"correct": 0, "wrong": 0, "suppress": 0.0}
        return by[key]

    def record_insect_feedback(
        self,
        *,
        item_id: str,
        correct: bool,
        predicted_class: str = "",
        true_class: str = "",
        confidence: Optional[float] = None,
        insect_present: Optional[bool] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """Reinforce insect ID policy from dry-train / operator labels."""
        pred = (predicted_class or "").lower().strip()
        true = (true_class or "").lower().strip()
        with self._lock:
            insect = self._state.setdefault(
                "insect", {"n_correct": 0, "n_wrong": 0, "by_class": {}})
            if correct:
                insect["n_correct"] = int(insect.get("n_correct", 0)) + 1
                if pred:
                    b = self._class_bucket_unlocked(pred)
                    b["correct"] = int(b.get("correct", 0)) + 1
                    b["suppress"] = max(
                        0.0, float(b.get("suppress", 0.0)) * (1.0 - INSECT_ALPHA))
            else:
                insect["n_wrong"] = int(insect.get("n_wrong", 0)) + 1
                # Wrong prediction → suppress that class; if true_class given, reward it
                if pred and pred not in ("", "none", "unknown"):
                    b = self._class_bucket_unlocked(pred)
                    b["wrong"] = int(b.get("wrong", 0)) + 1
                    b["suppress"] = min(
                        1.0, float(b.get("suppress", 0.0)) + INSECT_ALPHA)
                if true and true not in ("", "none", "unknown") and true != pred:
                    tb = self._class_bucket_unlocked(true)
                    tb["correct"] = int(tb.get("correct", 0)) + 1
                    tb["suppress"] = max(
                        0.0, float(tb.get("suppress", 0.0)) * (1.0 - INSECT_ALPHA * 0.5))
                # False positive on empty frame
                if insect_present is False and pred:
                    b = self._class_bucket_unlocked(pred)
                    b["suppress"] = min(1.0, float(b.get("suppress", 0.0)) + INSECT_ALPHA)

            event = {
                "timestamp": stamp_iso(),
                "source": "insect_train",
                "id": item_id,
                "correct": correct,
                "reward": 1.0 if correct else -1.0,
                "predicted_class": pred or None,
                "true_class": true or None,
                "confidence": confidence,
                "insect_present": insect_present,
                "note": note,
                "insect_after": self._insect_unlocked(),
            }
            ev: List[dict] = list(self._state.get("events") or [])
            ev.append(event)
            self._state["events"] = ev[-MAX_EVENTS:]
            self._save_unlocked()
            return {"ok": True, "event": event, "insect": self._insect_unlocked()}

    def record_feedback(
        self,
        *,
        source: str,
        item_id: str,
        correct: bool,
        hit_px: Optional[int] = None,
        hit_py: Optional[int] = None,
        true_px: Optional[int] = None,
        true_py: Optional[int] = None,
        aim_px: int = 640,
        aim_py: int = 360,
        note: str = "",
    ) -> Dict[str, Any]:
        """Splash localization reinforcement (cal_hit / hunt_capture)."""
        reward = 1.0 if correct else -1.0
        hit_px = _as_int(hit_px)
        hit_py = _as_int(hit_py)
        true_px = _as_int(true_px)
        true_py = _as_int(true_py)
        aim_px = _as_int(aim_px) if aim_px is not None else 640
        aim_py = _as_int(aim_py) if aim_py is not None else 360
        if aim_px is None:
            aim_px = 640
        if aim_py is None:
            aim_py = 360

        with self._lock:
            if correct:
                self._state["n_correct"] += 1
                self._state["prior_sigma_frac"] = max(
                    0.06,
                    float(self._state["prior_sigma_frac"]) * (1.0 - REWARD_ALPHA * 0.5),
                )
                self._state["prior_strength"] = min(
                    0.75,
                    float(self._state["prior_strength"]) + REWARD_ALPHA * 0.15,
                )
            else:
                self._state["n_wrong"] += 1
                self._state["prior_sigma_frac"] = min(
                    0.22,
                    float(self._state["prior_sigma_frac"]) * (1.0 + REWARD_ALPHA),
                )
                self._state["prior_strength"] = max(
                    0.25,
                    float(self._state["prior_strength"]) - REWARD_ALPHA * 0.2,
                )

            if true_px is not None and true_py is not None:
                self._state["n_corrections_xy"] += 1
                dx = float(true_px) - float(aim_px)
                dy = float(true_py) - float(aim_py)
                rb = float(self._state["right_bias_px"])
                self._state["right_bias_px"] = max(
                    10.0, min(180.0, (1.0 - ALPHA) * rb + ALPHA * dx)
                )
                if dy > 0:
                    bb = float(self._state["below_bonus"])
                    target = min(1.6, 0.5 + dy / 400.0)
                    self._state["below_bonus"] = (1.0 - ALPHA) * bb + ALPHA * target
                if hit_px is not None and abs(float(true_px) - float(hit_px)) > 40:
                    self._state["prior_strength"] = max(
                        0.3, float(self._state["prior_strength"]) - 0.05
                    )

            event = {
                "timestamp": stamp_iso(),
                "source": source,
                "id": item_id,
                "correct": correct,
                "reward": reward,
                "hit_px": hit_px,
                "hit_py": hit_py,
                "true_px": true_px,
                "true_py": true_py,
                "aim_px": aim_px,
                "aim_py": aim_py,
                "note": note,
                "priors_after": {
                    k: round(v, 3 if k != "right_bias_px" else 1)
                    for k, v in self._priors_unlocked().items()
                },
            }
            ev: List[dict] = list(self._state.get("events") or [])
            ev.append(event)
            self._state["events"] = ev[-MAX_EVENTS:]
            self._save_unlocked()
            return {"ok": True, "event": event, "priors": self._priors_unlocked()}
