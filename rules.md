# AI Coding Rules for Jetson Edge Robotics

> **Master Specs:** All rules below are derived from the formal specifications in `docs/specs/`.
> Any rule change here MUST be reflected in the corresponding spec document.
> All changes MUST be logged in [docs/HISTORY.md](docs/HISTORY.md).

## Coding Rules

1. **NO VANILLA PYTORCH:** All YOLOv8 models MUST be exported to TensorRT (`.engine`) formats for inference. *(SW-001 §1)*
2. **GSTREAMER IS MANDATORY:** Do not use `cv2.VideoCapture(0)` natively. You MUST write highly optimized GStreamer pipelines to utilize the Jetson's hardware ISP. *(SW-001 §1)*
3. **NON-BLOCKING I/O:** The vision tracking loop cannot be blocked by serial commands. Use `asyncio` or dedicated `threading` for Storm32 communications. *(SW-001 §2.2)*
4. **THE "DEATH SPIRAL" PREVENTION:** The Yaw axis of the Storm32 gimbal MUST be hard-limited in code to `-130 degrees` and `+130 degrees`. If a target crosses the 180-degree rear threshold, the turret must rapidly unwind to the opposite side. Do not allow continuous 360-degree rotation. *(SAFE-001 §2)*
5. **BIOLOGICAL HEURISTICS:** Do not fire at everything classified as an `insect`. If the bounding box is too large (indicating a moth or June bug), ignore it. *(SAFE-001 §2)*
6. **HUMAN OVERRIDE:** If `person`, `dog`, or `cat` confidence > 0.45 anywhere in the Sniper frame, `is_safe_to_fire` must instantly return `False`. *(SAFE-001 §2)*
7. **FAIL-SAFE FIRST:** Every script that touches GPIO 18 must have a `try/finally` block ensuring the pin is set to `LOW` if the script crashes. *(SAFE-001 §2)*

## Spec-Driven Development Process

8. **SPEC BEFORE CODE:** No feature, agent, or hardware change may be implemented without a corresponding entry in `docs/specs/`. Write or update the spec FIRST, get approval, then implement.
9. **HISTORY IS MANDATORY:** Every significant action (code change, procurement decision, architecture decision, bug fix) MUST be appended to `docs/HISTORY.md` with a timestamp, `[CATEGORY]` tag, and one-line description.
10. **TRACEABILITY:** All source code files MUST include a docstring header referencing the governing spec (e.g., `# Implements: SW-001 §2.1 — ScoutAgent`).
11. **SPEC INTEGRITY:** If implementation reveals that a spec is wrong or incomplete, update the spec FIRST, then update the code. Never let code and specs diverge.
12. **AUTO-PUSH TO GITHUB:** Every time changes are made to the project, they MUST be committed and pushed to the GitHub remote (`origin/main`). Additionally, a summary of the changes MUST be appended to `project_history.md` at the project root before the push. No changes should remain local-only.