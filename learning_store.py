# Implements: SW-001 §2.15 — Operator-feedback reinforcement for splash priors
"""
learning_store.py — Lightweight reinforcement learning from operator feedback.

Not a neural RL agent: reward-weighted EMA updates to HitDetector soft priors
(right bias, gravity/below weight, prior tightness) so splash localization
improves over sessions when the operator marks HIT correct/wrong (and optionally
clicks the true landing).
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from timeutil import stamp_iso

DEFAULT_STATE = {
    "version": 1,
    "n_correct": 0,
    "n_wrong": 0,
    "n_corrections_xy": 0,
    # Soft priors consumed by HitDetector
    "right_bias_px": 70.0,
    "below_bonus": 0.85,
    "prior_sigma_frac": 0.12,
    "prior_strength": 0.55,   # weight of prior vs pure vision in score blend
    "events": [],             # rolling feedback log (last N)
}

MAX_EVENTS = 200
ALPHA = 0.22                  # EMA learning rate on spatial corrections
REWARD_ALPHA = 0.08           # slower tweak when only correct/wrong


class LearningStore:
    def __init__(self, root_dir: str, filename: str = "learning_state.json"):
        self.path = os.path.join(root_dir, filename)
        self._lock = threading.Lock()
        self._state = dict(DEFAULT_STATE)
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            data = json.load(open(self.path, "r"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_STATE)
                merged.update({k: data[k] for k in DEFAULT_STATE if k in data})
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

    def get_priors(self) -> Dict[str, float]:
        with self._lock:
            return {
                "right_bias_px": float(self._state["right_bias_px"]),
                "below_bonus": float(self._state["below_bonus"]),
                "prior_sigma_frac": float(self._state["prior_sigma_frac"]),
                "prior_strength": float(self._state["prior_strength"]),
            }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            ev = self._state.get("events") or []
            priors = {
                "right_bias_px": float(self._state["right_bias_px"]),
                "below_bonus": float(self._state["below_bonus"]),
                "prior_sigma_frac": float(self._state["prior_sigma_frac"]),
                "prior_strength": float(self._state["prior_strength"]),
            }
            return {
                "n_correct": self._state["n_correct"],
                "n_wrong": self._state["n_wrong"],
                "n_corrections_xy": self._state["n_corrections_xy"],
                "priors": priors,
                "last_events": ev[-10:],
                "path": self.path,
            }

    def apply_to_detector(self, detector) -> None:
        """Push learned priors into a HitDetector instance."""
        p = self.get_priors()
        if detector is None:
            return
        try:
            detector.RIGHT_BIAS_PX = float(p["right_bias_px"])
            detector.BELOW_BONUS = float(p["below_bonus"])
            detector.PRIOR_SIGMA_FRAC = float(p["prior_sigma_frac"])
            detector.PRIOR_STRENGTH = float(p["prior_strength"])
            print(f"[Learning] applied priors right={detector.RIGHT_BIAS_PX:.0f}px "
                  f"below={detector.BELOW_BONUS:.2f} sigma={detector.PRIOR_SIGMA_FRAC:.3f} "
                  f"strength={detector.PRIOR_STRENGTH:.2f}")
        except Exception as e:
            print(f"[Learning] apply_to_detector: {e}")

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
        """
        Reinforcement step.
        reward = +1 correct, -1 wrong.
        If true_px/true_py given on a wrong (or refine), update spatial priors toward
        (true - aim).
        """
        reward = 1.0 if correct else -1.0
        with self._lock:
            if correct:
                self._state["n_correct"] += 1
                # Correct → tighten prior slightly, reinforce current right bias
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
                # Wrong → widen search prior, rely more on vision next time
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
                # Learn right bias from horizontal offset of true landing vs aim
                rb = float(self._state["right_bias_px"])
                self._state["right_bias_px"] = max(
                    10.0, min(180.0, (1.0 - ALPHA) * rb + ALPHA * dx)
                )
                # More below aim → increase below_bonus
                if dy > 0:
                    bb = float(self._state["below_bonus"])
                    target = min(1.6, 0.5 + dy / 400.0)
                    self._state["below_bonus"] = (1.0 - ALPHA) * bb + ALPHA * target
                # If operator moved hit markedly right of detector HIT, note it
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
                    "right_bias_px": round(float(self._state["right_bias_px"]), 1),
                    "below_bonus": round(float(self._state["below_bonus"]), 3),
                    "prior_sigma_frac": round(float(self._state["prior_sigma_frac"]), 3),
                    "prior_strength": round(float(self._state["prior_strength"]), 3),
                },
            }
            ev: List[dict] = list(self._state.get("events") or [])
            ev.append(event)
            self._state["events"] = ev[-MAX_EVENTS:]
            self._save_unlocked()
            return {"ok": True, "event": event, "priors": self.get_priors()}
