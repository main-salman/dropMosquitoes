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

# Step 2: Stop any existing server on Jetson
echo ""
echo "🛑 Step 2/3: Stopping any existing server on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" "
    cd ${JETSON_PATH} 2>/dev/null || true
    # Kill any existing app.py process
    pkill -f 'python3 app.py' 2>/dev/null || true
    sleep 1
    echo '   Done.'
"

# Step 3: Start server on Jetson
echo ""
echo "🎯 Step 3/3: Starting server on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" "
    cd ${JETSON_PATH}
    # Maximize Jetson performance
    sudo nvpmodel -m 0 2>/dev/null || true
    sudo jetson_clocks 2>/dev/null || true
    # Start server in background with nohup so it survives SSH disconnect
    nohup python3 app.py --port ${PORT} > sentry.log 2>&1 &
    echo \$! > .sentry.pid
    sleep 3
    if kill -0 \$(cat .sentry.pid) 2>/dev/null; then
        echo '✅ Server started on Jetson (PID '\$(cat .sentry.pid)')'
    else
        echo '❌ Server failed to start. Last 20 lines of log:'
        tail -20 sentry.log
        exit 1
    fi
"

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Server running on Jetson!"
echo ""
echo "  Dashboard: http://${JETSON_HOST}:${PORT}"
echo ""
echo "  To stop:   ./stop.sh"
echo "  To view logs: ssh ${JETSON_USER}@${JETSON_HOST} 'tail -f ${JETSON_PATH}/sentry.log'"
echo "══════════════════════════════════════════════"
