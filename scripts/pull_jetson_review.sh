#!/usr/bin/env bash
# pull_jetson_review.sh — Copy recent Jetson results into temp/ + HTML report
#
# Usage:
#   ./scripts/pull_jetson_review.sh           # last 7 hours (covers afternoon cal + evening)
#   ./scripts/pull_jetson_review.sh 6         # last N hours
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOURS="${1:-7}"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$ROOT/.env" | grep -v '^\s*$' | xargs)
fi
JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${JETSON_IP:-192.168.0.196}"
JETSON_PATH="/home/${JETSON_USER}/dropMosquitoes"

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$ROOT/temp/jetson_review_${STAMP}"
mkdir -p "$OUT"/{cal_hits,hunt_captures,logs,config}

echo "Pulling last ${HOURS}h from ${JETSON_USER}@${JETSON_HOST} → $OUT"

ssh "${JETSON_USER}@${JETSON_HOST}" "python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ET=ZoneInfo('America/New_York')
now=datetime.now(ET)
cut=now-timedelta(hours=int('${HOURS}'))
root=Path('${JETSON_PATH}')
def ok(p):
    return datetime.fromtimestamp(p.stat().st_mtime, ET) >= cut
cals=[]; hunts=[]
ch=root/'cal_hits'
if ch.exists():
  for d in ch.iterdir():
    if d.is_dir() and ok(d): cals.append(d.name)
    elif d.name=='index.json': cals.append(d.name)
hc=root/'hunt_captures'
if hc.exists():
  for d in hc.iterdir():
    if d.is_dir() and ok(d): hunts.append(d.name)
    elif d.name=='index.json': hunts.append(d.name)
Path('/tmp/review_manifest.json').write_text(json.dumps({
  'window_note': f'last ${HOURS}h ET',
  'cut_et': cut.isoformat(), 'now_et': now.isoformat(),
  'cal_hits': sorted(cals), 'hunt_captures': sorted(hunts),
}, indent=2))
print('cals',len([c for c in cals if c!='index.json']),'hunts',len([h for h in hunts if h!='index.json']))
PY"

scp -q "${JETSON_USER}@${JETSON_HOST}:/tmp/review_manifest.json" "$OUT/manifest.json"

python3 - <<PY
import json, subprocess
from pathlib import Path
out=Path("$OUT")
man=json.loads((out/"manifest.json").read_text())
host="${JETSON_USER}@${JETSON_HOST}"
base="${JETSON_PATH}"
for name in man.get("cal_hits") or []:
    src=f"{host}:{base}/cal_hits/{name}"
    dst=out/"cal_hits"/name
    if name.endswith(".json"):
        subprocess.check_call(["scp","-q",src,str(dst)])
    else:
        dst.mkdir(parents=True, exist_ok=True)
        subprocess.call(["rsync","-a",f"{src}/",str(dst)+"/"])
for name in man.get("hunt_captures") or []:
    if name.endswith(".json"):
        subprocess.call(["scp","-q",f"{host}:{base}/hunt_captures/{name}",str(out/"hunt_captures"/name)])
        continue
    dst=out/"hunt_captures"/name
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.call(["rsync","-a","--exclude","*.mp4","--exclude","*.avi",
                     f"{host}:{base}/hunt_captures/{name}/", str(dst)+"/"],
                    stdout=subprocess.DEVNULL)
for f in ["settings.json","calibration_visual.json","scout_config.json"]:
    subprocess.call(["scp","-q",f"{host}:{base}/{f}",str(out/"config"/f)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("synced")
PY

ssh "${JETSON_USER}@${JETSON_HOST}" "python3 - <<PY
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
ET=ZoneInfo('America/New_York')
cut=datetime.now(ET)-timedelta(hours=int('${HOURS}'))
lines=Path('${JETSON_PATH}/activity.log').read_text(errors='replace').splitlines()
keep=[]
for ln in lines:
    try:
        ts=datetime.strptime(ln[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=ET)
        if ts>=cut: keep.append(ln)
    except Exception:
        if keep: keep.append(ln)
Path('/tmp/activity_6h.log').write_text('\\n'.join(keep)+('\\n' if keep else ''))
s=Path('${JETSON_PATH}/sentry.log').read_text(errors='replace').splitlines()[-8000:]
Path('/tmp/sentry_tail.log').write_text('\\n'.join(s)+'\\n')
print('logs ready', len(keep), len(s))
PY"
scp -q "${JETSON_USER}@${JETSON_HOST}:/tmp/activity_6h.log" "$OUT/logs/activity_6h.log"
scp -q "${JETSON_USER}@${JETSON_HOST}:/tmp/sentry_tail.log" "$OUT/logs/sentry_tail.log"

python3 "$ROOT/scripts/build_jetson_review_html.py" "$OUT"
echo ""
echo "Report: $OUT/index.html"
echo "Open with: open \"$OUT/index.html\""
