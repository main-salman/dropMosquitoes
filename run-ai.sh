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
# NOTE: main.py runs as ROOT via systemd — needs sudo to stop.
# We pipe the password via sudo -S to avoid TTY requirement.
ssh "${JETSON_USER}@${JETSON_HOST}" bash <<ENDSSH
    cd /home/jetson/dropMosquitoes 2>/dev/null || true

    # Stop the systemd sentry service (runs main.py as root)
    echo '${JETSON_PASSWORD}' | sudo -S systemctl stop sentry 2>/dev/null || true

    # Graceful shutdown first — SIGTERM triggers our signal handler which
    # properly tears down GStreamer pipelines and releases MIPI CSI sensors.
    # Without this, nvarguscamerasrc leaves the sensor in a bad state and
    # the Sniper camera feed becomes garbled on restart.
    echo '${JETSON_PASSWORD}' | sudo -S killall -TERM python3 2>/dev/null || true
    sleep 3

    # Force-kill any stubborn processes only after giving 3s for graceful cleanup
    echo '${JETSON_PASSWORD}' | sudo -S killall -9 python3 2>/dev/null || true

    # Also kill any user-owned processes gracefully
    if [ -f .sentry.pid ]; then
        PID=\$(cat .sentry.pid)
        kill "\$PID" 2>/dev/null || true
        sleep 1
        kill -9 "\$PID" 2>/dev/null || true
        rm -f .sentry.pid
    fi
    pgrep -f '[a]pp.py' | xargs -r kill 2>/dev/null || true
    sleep 1
    pgrep -f '[a]pp.py' | xargs -r kill -9 2>/dev/null || true

    # Restart nvargus-daemon to reset MIPI CSI sensor state.
    # This prevents garbled camera feeds after an unclean shutdown.
    echo '${JETSON_PASSWORD}' | sudo -S systemctl restart nvargus-daemon 2>/dev/null || true
    sleep 1

    echo '   Done.'
ENDSSH

# Step 3: Start server on Jetson
echo ""
echo "🎯 Step 3/3: Starting server on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" bash <<ENDSSH
    cd /home/jetson/dropMosquitoes

    # Prevent systemd from restarting main.py while we run app.py
    echo '${JETSON_PASSWORD}' | sudo -S systemctl disable sentry 2>/dev/null || true

    # Maximize Jetson performance
    echo '${JETSON_PASSWORD}' | sudo -S nvpmodel -m 0 2>/dev/null || true
    echo '${JETSON_PASSWORD}' | sudo -S jetson_clocks 2>/dev/null || true

    # Configure GPIO Pin 11 (BCM 17 / PR.04) and Pin 13 (BCM 27 / PY.00) to push-pull mode by clearing Open-Drain bit (Bit 4)
    echo '${JETSON_PASSWORD}' | sudo -S PYTHONPATH=/home/jetson/.local/lib/python3.10/site-packages python3 -c 'import mmap, struct; f = open("/dev/mem", "r+b"); mem = mmap.mmap(f.fileno(), 0x10000, offset=0x02430000); mem[0x98:0x9c] = struct.pack("<I", struct.unpack("<I", mem[0x98:0x9c])[0] & ~(1 << 4)); mem[0xd030:0xd034] = struct.pack("<I", struct.unpack("<I", mem[0xd030:0xd034])[0] & ~(1 << 4))' 2>/dev/null || true


    # Fix log file ownership if root-owned from systemd
    echo '${JETSON_PASSWORD}' | sudo -S chown ${JETSON_USER}:${JETSON_USER} sentry.log 2>/dev/null || true
    rm -f sentry.log

    # Start server as ROOT in background with nohup so it has direct mmap /dev/mem write access to override pad registers
    echo '${JETSON_PASSWORD}' | sudo -S PYTHONPATH=/home/jetson/.local/lib/python3.10/site-packages nohup python3 -u app.py --port ${PORT} > sentry.log 2>&1 &

    sleep 2
    SERVER_PID=\$(pgrep -o -f 'app.py --port ${PORT}')
    if [ -n "\$SERVER_PID" ]; then
        echo \$SERVER_PID > .sentry.pid
        echo "✅ Server started on Jetson (PID \$SERVER_PID)"
    else
        echo "❌ Server failed to start. Last 20 lines of log:"
        tail -20 sentry.log
        exit 1
    fi
ENDSSH

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Server running on Jetson!"
echo ""
echo "  Dashboard: http://${JETSON_HOST}:${PORT}"
echo ""
echo "  To stop:   ./stop.sh"
echo "  To view logs: ssh ${JETSON_USER}@${JETSON_HOST} 'tail -f ${JETSON_PATH}/sentry.log'"
echo "══════════════════════════════════════════════"
