#!/bin/bash
# run-ai.sh — Deploy and start Sniper Messy Mortar on the Jetson
#
# Usage:
#   ./run-ai.sh              # Deploy + start on Jetson (default)
#   ./run-ai.sh --local      # Start locally on this machine (dev testing only)
#   ./run-ai.sh --no-deploy  # Start on Jetson without re-deploying code
#
# The server runs ON THE JETSON so it can access the CSI cameras.
# Access the dashboard from your browser at http://<JETSON_IP>:8000

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.sentry.pid"
LOG_FILE="$SCRIPT_DIR/sentry.log"
PORT=8000

# Load .env for Jetson connection details
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^\s*$' | xargs)
fi

JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${JETSON_IP:-jetson.local}"
JETSON_PATH="/home/${JETSON_USER}/dropMosquitoes"

# ---- LOCAL MODE (dev testing on Mac/PC with webcam) ----
if [[ "${1:-}" == "--local" ]]; then
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "⚠️  Local server already running (PID $(cat "$PID_FILE")). Run ./stop.sh first."
        exit 1
    fi
    echo "🎯 Starting Sniper Messy Mortar LOCALLY (dev mode — uses Mac webcam)..."
    cd "$SCRIPT_DIR"
    python3 app.py --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "✅ Local server started (PID $(cat "$PID_FILE"))"
        echo "   Dashboard: http://localhost:$PORT"
        echo "   Run ./stop.sh to shut down."
    else
        echo "❌ Server failed. Check $LOG_FILE"
        rm -f "$PID_FILE"; tail -20 "$LOG_FILE"; exit 1
    fi
    exit 0
fi

# ---- JETSON MODE (default — runs on the actual hardware) ----
echo "══════════════════════════════════════════════"
echo "  Sniper Messy Mortar — Jetson Deployment"
echo "  Target: ${JETSON_USER}@${JETSON_HOST}"
echo "══════════════════════════════════════════════"

# Check Jetson is reachable
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
    echo "❌ Cannot reach Jetson at ${JETSON_HOST}."
    echo "   Make sure the Jetson is powered on and connected to the network."
    echo "   You can also set JETSON_IP in .env or run: ./run-ai.sh --local"
    exit 1
fi

# Step 1: Deploy code (unless --no-deploy)
if [[ "${1:-}" != "--no-deploy" ]]; then
    echo ""
    echo "📦 Step 1/3: Deploying code to Jetson..."
    "$SCRIPT_DIR/deploy.sh" "$JETSON_HOST"
else
    echo ""
    echo "⏭  Skipping deploy (--no-deploy flag)"
fi

# Step 2: Reboot the Jetson for clean CSI camera state
# The MIPI CSI-2 PHY retains lane sync state that `modprobe -r` cannot clear.
# Only a full reboot guarantees clean video on both sensors (especially sensor-1/Sniper).
echo ""
echo "🔄 Step 2/3: Rebooting Jetson for clean camera state..."
ssh "${JETSON_USER}@${JETSON_HOST}" bash <<ENDSSH
    cd /home/jetson/dropMosquitoes 2>/dev/null || true

    # Stop the systemd sentry service first for clean shutdown
    echo '${JETSON_PASSWORD}' | sudo -S systemctl stop sentry 2>/dev/null || true
    sleep 1

    # Kill any lingering python3 processes
    echo '${JETSON_PASSWORD}' | sudo -S killall -TERM python3 2>/dev/null || true
    sleep 2
    echo '${JETSON_PASSWORD}' | sudo -S killall -9 python3 2>/dev/null || true

    # Clean up log for fresh start
    echo '${JETSON_PASSWORD}' | sudo -S chown ${JETSON_USER}:${JETSON_USER} sentry.log 2>/dev/null || true
    rm -f sentry.log

    echo '   Rebooting...'
    echo '${JETSON_PASSWORD}' | sudo -S reboot 2>/dev/null || true
ENDSSH

# Step 3: Wait for Jetson to come back up and verify dashboard
echo ""
echo "⏳ Step 3/3: Waiting for Jetson to reboot..."

# Wait for SSH to become available (up to 120 seconds)
WAIT_MAX=120
WAITED=0
while [ $WAITED -lt $WAIT_MAX ]; do
    if ssh -o ConnectTimeout=3 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
        echo "   SSH is up after ${WAITED}s."
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo "   Waiting... (${WAITED}s)"
done

if [ $WAITED -ge $WAIT_MAX ]; then
    echo "❌ Jetson did not come back after ${WAIT_MAX}s. Check power and network."
    exit 1
fi

# Wait for sentry.service to start and dashboard to become reachable
echo "   Waiting for sentry.service and dashboard..."
DASH_MAX=90
DASH_WAITED=0
while [ $DASH_WAITED -lt $DASH_MAX ]; do
    HTTP_CODE=$(ssh -o ConnectTimeout=3 "${JETSON_USER}@${JETSON_HOST}" "curl -s -o /dev/null -w '%{http_code}' http://localhost:${PORT}/ 2>/dev/null" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   Dashboard responding (HTTP 200) after ${DASH_WAITED}s."
        break
    fi
    sleep 5
    DASH_WAITED=$((DASH_WAITED + 5))
    echo "   Dashboard not ready yet... (${DASH_WAITED}s)"
done

if [ $DASH_WAITED -ge $DASH_MAX ]; then
    echo "⚠️  Dashboard not responding after ${DASH_MAX}s. Check sentry.log:"
    ssh "${JETSON_USER}@${JETSON_HOST}" "tail -20 /home/jetson/dropMosquitoes/sentry.log" 2>/dev/null || true
    exit 1
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Server running on Jetson (clean reboot)!"
echo ""
echo "  Dashboard: http://${JETSON_HOST}:${PORT}"
echo ""
echo "  To stop:   ./stop.sh"
echo "  To view logs: ssh ${JETSON_USER}@${JETSON_HOST} 'tail -f ${JETSON_PATH}/sentry.log'"
echo "══════════════════════════════════════════════"

