#!/usr/bin/env python3
# Implements: SW-001 §6 — offline Jetson result review HTML
"""Build a self-contained HTML report for a temp/jetson_review_* folder.

Hunt captures + logs only (calibration hits omitted from the report UI).
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _meta_rows(folder: Path):
    rows = []
    for d in sorted(folder.iterdir() if folder.exists() else []):
        if not d.is_dir():
            continue
        meta = _load_json(d / "meta.json") or {}
        rows.append((d.name, meta, d))
    return rows


def build(review_dir: Path) -> Path:
    review_dir = review_dir.resolve()
    man = _load_json(review_dir / "manifest.json") or {}
    hunt_rows = _meta_rows(review_dir / "hunt_captures")

    hit_yes = sum(1 for _, m, _ in hunt_rows if m.get("hit_confirmed") is True)
    hit_no = sum(1 for _, m, _ in hunt_rows if m.get("hit_confirmed") is False)

    def _img_cell(label: str, p: Path) -> str:
        rel = p.relative_to(review_dir).as_posix()
        esc = html.escape(rel)
        return (
            f'<figure class="shot">'
            f'<figcaption>{html.escape(label)} · click to enlarge</figcaption>'
            f'<a href="{esc}" target="_blank" rel="noopener">'
            f'<img src="{esc}" loading="lazy" alt="{html.escape(label)}"></a>'
            f'</figure>'
        )

    def hunt_card(name, meta, d):
        # Prefer sniper/trajectory stills first (insects are tiny — need those frames large).
        stills = []
        seen = set()
        for cand in (
            "sniper_after_ann.jpg", "sniper_before_ann.jpg",
            "sniper_after.jpg", "sniper_before.jpg", "sniper_fire.jpg",
            "sniper.jpg", "trajectory.jpg", "contact.jpg",
            "after.jpg", "before.jpg", "scout.jpg",
        ):
            p = d / cand
            if p.exists():
                stills.append((cand, p))
                seen.add(cand)
        for p in sorted(d.glob("*.jpg")):
            if p.name not in seen:
                stills.append((p.name, p))
                seen.add(p.name)
        imgs = "".join(_img_cell(label, p) for label, p in stills[:6])
        verdict = meta.get("hit_verdict") or {}
        summary = verdict.get("summary") or (
            "HIT" if meta.get("hit_confirmed") is True
            else ("MISS" if meta.get("hit_confirmed") is False else "—")
        )
        cls = "hit" if meta.get("hit_confirmed") is True else (
            "miss" if meta.get("hit_confirmed") is False else ""
        )
        detail = html.escape(json.dumps({
            k: meta.get(k) for k in (
                "timestamp", "verify", "hit_confirmed", "hit_px", "hit_py",
                "distance_m", "pulse_ms", "hit_verdict", "label",
            ) if k in meta or True
        }, indent=2, default=str)[:1500])
        return (
            f'<article class="card {cls}"><h3>{html.escape(name)} · '
            f'{html.escape(str(summary))}</h3>'
            f'<div class="meta">{html.escape(str(meta.get("timestamp", "")))} · '
            f'images open full-size in a new tab</div>'
            f'<div class="shots">{imgs}</div>'
            f'<pre>{detail}</pre></article>'
        )

    hunt_html = "\n".join(hunt_card(*r) for r in hunt_rows) or "<p>No hunt captures in window.</p>"

    activity = review_dir / "logs" / "activity_6h.log"
    act_preview = ""
    if activity.exists():
        lines = activity.read_text(errors="replace").splitlines()[-80:]
        act_preview = html.escape("\n".join(lines))

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Jetson review — {html.escape(review_dir.name)}</title>
<style>
:root {{ --bg:#0f1419; --card:#1a222c; --text:#e7ecf1; --dim:#8b9aab; --hit:#1f6f4a; --miss:#6f1f1f; --accent:#4ea1ff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
  background:linear-gradient(160deg,#0f1419,#16202a 40%,#101820); color:var(--text); }}
header {{ padding:28px 32px 12px; border-bottom:1px solid #243040; }}
header h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:-0.02em; }}
header p {{ margin:4px 0; color:var(--dim); }}
nav {{ display:flex; gap:12px; padding:12px 32px; position:sticky; top:0; background:#0f1419ee; backdrop-filter:blur(8px); z-index:2; }}
nav a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
main {{ padding:16px 32px 48px; }}
.stats {{ display:flex; gap:16px; flex-wrap:wrap; margin:12px 0 24px; }}
.stat {{ background:var(--card); padding:14px 18px; border-radius:12px; min-width:140px; }}
.stat b {{ display:block; font-size:22px; }}
.stat span {{ color:var(--dim); font-size:12px; }}
.card {{ background:var(--card); border:1px solid #2a3746; border-radius:14px; padding:18px; margin:0 0 28px; }}
.card.hit {{ border-color:#2f8f62; }}
.card.miss {{ border-color:#8f3a3a; }}
.card h3 {{ margin:0 0 6px; font-size:18px; }}
.meta {{ color:var(--dim); font-size:13px; margin-bottom:12px; }}
.shots {{ display:grid; grid-template-columns:1fr; gap:16px; }}
@media (min-width:1100px) {{
  .shots {{ grid-template-columns:1fr 1fr; }}
}}
.shot {{ margin:0; }}
.shot figcaption {{ font-size:12px; color:var(--dim); margin:0 0 6px; letter-spacing:0.02em; }}
.shot a {{ display:block; border-radius:10px; overflow:hidden; border:1px solid #2a3746; background:#000; }}
.shot img {{
  width:100%;
  height:auto;
  max-height:none;
  display:block;
  image-rendering:auto;
  cursor:zoom-in;
}}
pre {{ background:#0b1016; color:#b7c4d2; padding:10px; border-radius:8px; overflow:auto; font-size:11px; max-height:220px; margin-top:14px; }}
section {{ margin-top:28px; }}
h2 {{ font-size:22px; margin:0 0 12px; }}
@media (max-width:900px) {{ main,header,nav {{ padding-left:16px; padding-right:16px; }} }}
</style>
</head>
<body>
<header>
  <h1>Jetson field review</h1>
  <p><b>{html.escape(review_dir.name)}</b></p>
  <p>Window: {html.escape(str(man.get('cut_et','?')))} → {html.escape(str(man.get('now_et','?')))}</p>
  <p>{html.escape(str(man.get('window_note','')))} · hunt captures only (cal hits omitted)</p>
</header>
<nav>
  <a href="#hunt">Hunt captures ({len(hunt_rows)})</a>
  <a href="#logs">Logs</a>
</nav>
<main>
  <div class="stats">
    <div class="stat"><b>{len(hunt_rows)}</b><span>hunt attempts</span></div>
    <div class="stat"><b>{hit_yes}</b><span>hunt HIT</span></div>
    <div class="stat"><b>{hit_no}</b><span>hunt MISS / not HIT</span></div>
  </div>

  <section id="hunt">
    <h2>Hunt captures</h2>
    {hunt_html}
  </section>

  <section id="logs">
    <h2>Activity log (tail of window)</h2>
    <pre>{act_preview or '(no activity slice)'}</pre>
    <p class="meta">Full files under <code>logs/</code> — activity_6h.log, sentry_tail.log</p>
  </section>
</main>
</body>
</html>
"""
    out = review_dir / "index.html"
    out.write_text(page)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review_dir", type=Path)
    args = ap.parse_args()
    path = build(args.review_dir)
    print(path)


if __name__ == "__main__":
    main()
