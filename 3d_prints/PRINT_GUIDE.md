# 3D Printed Parts — Print Guide

> **Project:** Sniper Messy Mortar — Mosquito Sentry Turret
> **Total savings:** ~$34 CAD by printing instead of buying
> **Filament required:** ~80g total (~$3 CAD at $25/kg)

---

## How to Use These Files

1. Install [OpenSCAD](https://openscad.org/) (free, open-source)
2. Open each `.scad` file
3. Press **F6** to render, then **File → Export as STL**
4. Slice the STL in your slicer (Cura, PrusaSlicer, etc.)
5. Print with the settings listed below for each part

> **Important:** Measure YOUR actual hardware before printing! The `.scad` files have labeled parameters at the top of each file — adjust them to match your specific Storm32 gimbal, OV9281 module, pole diameter, etc.

---

## Part 1: Gimbal Nozzle Bracket
**File:** `01_nozzle_bracket.scad`
**Replaces:** "3D-Printed Nozzle Bracket" from moreparts.csv ($5)

| Setting | Value |
|:--------|:------|
| Material | PETG or ABS (heat resistance near gimbal motors) |
| Infill | 100% |
| Layer Height | 0.2mm |
| Supports | No |
| Print Time | ~45 min |

**What it does:** Mounts the Orbit 66190 nozzle alongside the IMX219 camera on the Storm32 gimbal payload plate. Has 4x M2.5 mounting holes matching the Storm32 pattern and a bore tube for the nozzle.

---

## Part 2: Scout Camera Mount Plate
**File:** `02_scout_camera_mount.scad`
**Replaces:** "M3 Nylon Standoff Assortment Kit" from moreparts.csv ($12)

| Setting | Value |
|:--------|:------|
| Material | PETG |
| Infill | 80% |
| Layer Height | 0.2mm |
| Supports | No |
| Print Time | ~30 min |

**What it does:** Single-piece mount that replaces buying a whole standoff kit. Has 4x integrated standoff posts (8mm tall) for the OV9281 PCB, plus 4x M3 holes for bolting to the enclosure lid. Includes a centered lens aperture hole.

---

## Part 3: Enclosure Post Clamp (print 2x)
**File:** `03_post_clamp.scad`
**Replaces:** "U-Bolt Pipe Clamps" from moreparts.csv ($8)

| Setting | Value |
|:--------|:------|
| Material | PETG or ABS |
| Infill | 100% |
| Layer Height | 0.2mm |
| Supports | No |
| Qty | 2 clamps × 2 halves = 4 prints |
| Print Time | ~25 min each |

**What it does:** Two-piece clamp that wraps around a 1" (25.4mm) aluminum pole and bolts together with M5 bolts. Each clamp has a bottom cradle and a top piece — they sandwich the pole.

---

## Part 4: Cable Management Clips (print 15-20x)
**File:** `04_cable_clips.scad`
**Replaces:** "Adhesive-Backed Zip Tie Mounts" from moreparts.csv ($9)

| Setting | Value |
|:--------|:------|
| Material | PLA or PETG |
| Infill | 100% |
| Layer Height | 0.15mm |
| Supports | No |
| Qty | 15-20 clips |
| Print Time | ~5 min each (batch 5 at a time) |

**What it does:** Snap-on C-clips for routing 1/4" tubing and wire bundles inside the enclosure. 8mm channel fits silicone tubing. Optional M3 screw hole in base, or use hot glue / VHB tape.

---

## Part 5: Lens Window Retainer Ring
**File:** `05_lens_retainer.scad`
**Still need to buy:** Acrylic disc (50mm x 3mm) and O-ring (~45mm ID)

| Setting | Value |
|:--------|:------|
| Material | PETG |
| Infill | 100% |
| Layer Height | 0.15mm |
| Supports | No |
| Print Time | ~20 min |

**What it does:** Press-fit ring that holds the acrylic lens window and O-ring seal over the scout camera aperture in the enclosure lid. Has a machined O-ring groove for weatherproofing.

---

## Bill of Materials Update

After printing these 5 parts, you can **remove these from moreparts.csv:**
- M3 Nylon Standoff Assortment Kit ($12)
- Adhesive-Backed Zip Tie Mounts ($9)
- U-Bolt Pipe Clamps ($8)
- 3D-Printed Nozzle Bracket ($5)

**Net savings: $34 CAD**
