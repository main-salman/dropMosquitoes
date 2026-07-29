#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — Push code from dev machine to Jetson Orin Nano
#
# Usage:
#   ./deploy.sh                  # Uses JETSON_IP from .env, or jetson.local
#   ./deploy.sh 192.168.0.50     # Override with custom IP
#   ./deploy.sh --no-restart     # Sync only (skip sentry restart)
#
# Prerequisites:
#   - SSH key copied to Jetson: ssh-copy-id jetson@<IP>
#   - rsync installed on both machines
#   - JETSON_PASSWORD in .env for non-interactive sudo restart (same as run-ai.sh)
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env for Jetson connection details (JETSON_IP, JETSON_USER, JETSON_PASSWORD)
if [ -f "$PROJECT_DIR/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$PROJECT_DIR/.env" | grep -v '^\s*$' | xargs)
fi

JETSON_USER="${JETSON_USER:-jetson}"
DO_RESTART=1
JETSON_HOST="${JETSON_HOST:-${JETSON_IP:-jetson.local}}"

for arg in "$@"; do
  case "$arg" in
    --no-restart) DO_RESTART=0 ;;
    *) JETSON_HOST="$arg" ;;
  esac
done

JETSON_PATH="/home/${JETSON_USER}/dropMosquitoes"

echo "══════════════════════════════════════════════"
echo "  Deploying to ${JETSON_USER}@${JETSON_HOST}:${JETSON_PATH}"
echo "══════════════════════════════════════════════"

# Sync project files (excluding dev-only stuff)
rsync -avz --progress \
  --exclude='.git/' \
  --exclude='__pycache__/' \
  --exclude='venv/' \
  --exclude='.venv/' \
  --exclude='tools/' \
  --exclude='diagrams/' \
  --exclude='3d_prints/' \
  --exclude='*.drawio' \
  --exclude='*.drawio.bkp' \
  --exclude='.DS_Store' \
  --exclude='chathistory.txt' \
  --exclude='firstprompt.txt' \
  --exclude='prompt.md' \
  --exclude='rename.md' \
  --exclude='runs/' \
  --exclude='sentry.log' \
  --exclude='*.engine' \
  --exclude='temp/' \
  --exclude='.env' \
  "${PROJECT_DIR}/" "${JETSON_USER}@${JETSON_HOST}:${JETSON_PATH}/"
# Both Scout and Sniper use IMX219 NoIR sensors — native imx219-dual.dtbo handles both.
# No custom kernel drivers required.

echo ""
echo "✅ Files synced."
echo ""

# Keep Jetson wall-clock on US Eastern so logs/GUI match operator local time
echo "🕒 Ensuring America/New_York timezone on Jetson..."
if [ -n "${JETSON_PASSWORD:-}" ]; then
  ssh "${JETSON_USER}@${JETSON_HOST}" "echo '${JETSON_PASSWORD}' | sudo -S timedatectl set-timezone America/New_York" 2>/dev/null \
    && ssh "${JETSON_USER}@${JETSON_HOST}" "timedatectl | grep -E 'Time zone|Local time'" \
    || echo "  ⚠ Could not set timezone (continue deploy)."
else
  ssh -t "${JETSON_USER}@${JETSON_HOST}" "sudo timedatectl set-timezone America/New_York" \
    || echo "  ⚠ Could not set timezone (continue deploy)."
fi
# Refresh systemd unit so Environment=TZ=America/New_York is installed
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && \
  if [ -f sentry.service ]; then \
    echo '${JETSON_PASSWORD:-}' | sudo -S cp sentry.service /etc/systemd/system/sentry.service 2>/dev/null; \
    echo '${JETSON_PASSWORD:-}' | sudo -S systemctl daemon-reload 2>/dev/null; \
    echo '  - sentry.service TZ=America/New_York installed'; \
  fi" || true
echo ""

# On the Jetson, copy the newly deployed trained model weights to standard target locations
echo "🎯 Aligning model paths on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && \
  if [ -f models/trained/best.pt ]; then \
    cp models/trained/best.pt best.pt && \
    mkdir -p models && \
    cp models/trained/best.pt models/yolov8n.pt && \
    echo '  - Successfully copied models/trained/best.pt to best.pt and models/yolov8n.pt' && \
    if [ -f best.engine ]; then \
      echo '  - [NOTE] Active TensorRT engine found (best.engine/models/yolov8n.engine).' && \
      echo '           Because the class count has changed, you must run the TensorRT export script' && \
      echo '           (gemini.md §3) on the Jetson to rebuild the high-speed engines!' ; \
    fi \
  else \
    echo '  - [WARNING] No trained model found at models/trained/best.pt' ; \
  fi"
echo ""

# Install/update Python deps on Jetson
echo "📦 Installing Python dependencies on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && pip install -r requirements.txt 2>&1 | tail -5"

jetson_sudo() {
  # Same pattern as run-ai.sh: pipe password to sudo -S (no TTY required).
  local cmd="$1"
  if [ -n "${JETSON_PASSWORD:-}" ]; then
    ssh "${JETSON_USER}@${JETSON_HOST}" "echo '${JETSON_PASSWORD}' | sudo -S ${cmd}" 2>/dev/null
  else
    ssh -t "${JETSON_USER}@${JETSON_HOST}" "sudo ${cmd}"
  fi
}

verify_cameras_or_reboot() {
  # Soft restart often leaves Sniper CSI-1 dead (NvBufSurfaceFromFd / 0 frames).
  # Poll /api/cameras/status; if Sniper is csi_phy_dead, reboot for clean PHY.
  echo "📷 Verifying Scout + Sniper camera health..."
  local waited=0
  local max_wait=90
  local status_json=""
  local reboot_req="false"
  local sniper_ok="false"
  while [ $waited -lt $max_wait ]; do
    status_json=$(ssh "${JETSON_USER}@${JETSON_HOST}" \
      "curl -s --max-time 3 http://localhost:8000/api/cameras/status 2>/dev/null" || true)
    if echo "$status_json" | grep -q '"sniper"'; then
      reboot_req=$(echo "$status_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('reboot_required',False)).lower())" 2>/dev/null || echo "false")
      sniper_ok=$(echo "$status_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('sniper',{}).get('healthy',False)).lower())" 2>/dev/null || echo "false")
      if [ "$reboot_req" = "true" ]; then
        echo "⚠ Sniper CSI PHY dead after soft restart — rebooting Jetson (only reliable fix)..."
        jetson_sudo "systemctl stop sentry" || true
        sleep 1
        # reboot returns non-zero when SSH drops; ignore
        jetson_sudo "reboot" || true
        echo "⏳ Waiting for Jetson to come back..."
        local up=0
        while [ $up -lt 120 ]; do
          if ssh -o ConnectTimeout=3 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" >/dev/null 2>&1; then
            echo "   SSH up after ${up}s."
            break
          fi
          sleep 5
          up=$((up + 5))
          echo "   Waiting... (${up}s)"
        done
        local dash=0
        while [ $dash -lt 90 ]; do
          local code
          code=$(ssh "${JETSON_USER}@${JETSON_HOST}" \
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/ 2>/dev/null" || echo "000")
          if [ "$code" = "200" ]; then
            echo "   Dashboard HTTP 200 after reboot (${dash}s)."
            status_json=$(ssh "${JETSON_USER}@${JETSON_HOST}" \
              "curl -s --max-time 3 http://localhost:8000/api/cameras/status 2>/dev/null" || true)
            echo "   Cameras: ${status_json}"
            return 0
          fi
          sleep 5
          dash=$((dash + 5))
        done
        echo "⚠ Dashboard not ready after reboot — check sentry.log"
        return 1
      fi
      if [ "$sniper_ok" = "true" ]; then
        echo "✅ Cameras healthy: ${status_json}"
        return 0
      fi
    fi
    sleep 5
    waited=$((waited + 5))
    echo "   Waiting for camera status... (${waited}s)"
  done
  echo "⚠ Camera health still unclear after ${max_wait}s: ${status_json}"
  echo "   If Sniper is black, run: ./run-ai.sh"
  return 1
}

if [ "$DO_RESTART" -eq 1 ]; then
  echo ""
  echo "🔄 Restarting sentry.service..."
  if jetson_sudo "systemctl restart sentry"; then
    echo "✅ sentry restarted."
    sleep 5
    HTTP_CODE=$(ssh "${JETSON_USER}@${JETSON_HOST}" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/ 2>/dev/null" || echo "000")
    echo "   Dashboard HTTP ${HTTP_CODE} (expect 200 once cameras warm up)."
    verify_cameras_or_reboot || true
  else
    echo "⚠ Restart failed. Set JETSON_PASSWORD in .env (used by run-ai.sh), or run:"
    echo "    ssh -t ${JETSON_USER}@${JETSON_HOST} 'sudo systemctl restart sentry'"
  fi
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Deployment complete!"
echo "  Dashboard: http://${JETSON_HOST}:8000"
echo "══════════════════════════════════════════════"
