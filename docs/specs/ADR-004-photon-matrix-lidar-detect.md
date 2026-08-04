# ADR-004: Photon Matrix LiDAR detect lessons (for Bug Sniper)

**Date:** 2026-08-03  
**Status:** RESEARCH → adopt sensing ideas (not laser effector)  
**Reference:** [photonmatrixlab.com](https://photonmatrixlab.com/)

---

## What Photon Matrix claims for detection

Product pitch (portable laser mosquito “air defense”, ≤~6 m):

1. **LiDAR scans a plane** and continuously measures distance to a **solid background**.
2. When a mosquito enters the beam, the measured range **changes** (return closer than
   background) — detect by **range anomaly**, not RGB classification.
3. **Confirm size** (FAQ: ~2–20 mm flying insects; speed ≤~1 m/s).
4. **Track + predict** flight path, then fire a laser on the **same optical path**
   (galvo mirrors — device doesn’t slew a whole turret for every zap).
5. **Safety:** no laser if background invalid / out of range; stop if human/large pet
   in zone. FAQ also lists **mmWave radar** + **AI vision** alongside LiDAR.

Core insight: **background-referenced ranging + size** is the primary mosquito filter;
vision is secondary/auxiliary.

---

## Why that works (when it works)

- A wall / floor / solid backdrop gives a stable range baseline.
- A mosquito is a small, closer interrupt on that ray → easy “something appeared.”
- Size check rejects larger animals/people (and many debris).
- Same-path sense/shoot reduces aim calibration error (laser boresight = LiDAR boresight).

**Harder outdoors:** foliage has no single flat background; range map is busy. Photon
Matrix still markets outdoor variants, but their clearest description assumes a
measurable background plane.

---

## Transfer to Bug Sniper (water turret)

| Photon Matrix | Bug Sniper takeaway | Action |
|---------------|---------------------|--------|
| Detect = Δrange vs background | Don’t rely only on YOLO JPEG match | Reinstall ranging (TF-Luna / better) and treat **range discontinuity** as a confirm |
| Size confirm | Insect-sized only | Keep `max/min_bbox_area_frac`; map to physical size when range known |
| Track + predict | Lead the flyer | Keep Scout velocity lead + streak |
| Defined scan plane / ≤6 m | Kill cone, not whole yard | Operator 5 m goal; `min/max_engage_m` when LiDAR live |
| No fire without valid background / human veto | Safety + anti-sky-fire analog | SAFE-001 human check; refuse engage if range unknown/out of window |
| mmWave / multi-sensor | Fuse modalities | Scout (motion) + Sniper (vision) + range (+ optional sonar later) |
| Galvo laser same path | Sense/shoot alignment | Boresight Sniper↔nozzle; optional future coaxial ranger on payload |
| Laser effector | Not our path | Keep water solenoid |

---

## Practical next steps (detection only)

1. **Replace dead TF-Luna** (rewire to working I2C Bus 1 with PCA9685/ADS1115).
2. When range is real: fire only if YOLO (or Scout) cue **and** range is in kill cone
   **and** (optional) range ≠ empty background / shows a small foreground object.
3. Prefer hunt geometry with a **usable backdrop** for ranger experiments (wall /
   matte board at known distance) — Photon Matrix’s easiest case.
4. Do **not** adopt Class‑4 laser kill for this project without a full SAFE redesign.

---

## One-line summary

Photon Matrix detects mosquitoes as **small range anomalies against a scanned
background**, then sizes/tracks them — Bug Sniper should fuse that ranging idea with
our camera pipeline once LiDAR (or equivalent) is back on the hardware.
