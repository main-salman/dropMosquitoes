#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — Push code from dev machine to Jetson Orin Nano
#
# Usage:
#   ./deploy.sh                  # Uses default JETSON_HOST
#   ./deploy.sh 192.168.0.50     # Override with custom IP
#
# Prerequisites:
#   - SSH key copied to Jetson: ssh-copy-id jetson@<IP>
#   - rsync installed on both machines
# ==============================================================================

set -euo pipefail

JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${1:-${JETSON_HOST:-jetson.local}}"
JETSON_PATH="/home/${JETSON_USER}/dropMosquitoes"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

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
  "${PROJECT_DIR}/" "${JETSON_USER}@${JETSON_HOST}:${JETSON_PATH}/"
# Both Scout and Sniper use IMX219 NoIR sensors — native imx219-dual.dtbo handles both.
# No custom kernel drivers required.

echo ""
echo "✅ Files synced."
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

echo ""
echo "🔄 Restarting sentry (needs your sudo password on the Jetson)..."
# -t allocates a TTY so sudo can prompt; plain ssh 'sudo ...' fails with
# "a terminal is required to read the password".
if ssh -t "${JETSON_USER}@${JETSON_HOST}" "sudo systemctl restart sentry"; then
  echo "✅ sentry restarted."
else
  echo "⚠ Restart failed or skipped. From your Mac terminal run:"
  echo "    ssh -t ${JETSON_USER}@${JETSON_HOST} 'sudo systemctl restart sentry'"
  echo "  Or power-cycle the Jetson."
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  To install the systemd service (first time only):"
echo "    ssh -t ${JETSON_USER}@${JETSON_HOST}"
echo "    sudo cp ${JETSON_PATH}/sentry.service /etc/systemd/system/"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl enable sentry.service"
echo "══════════════════════════════════════════════"
