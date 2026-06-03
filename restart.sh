#!/bin/bash
# restart.sh — Restart the Jetson remotely and wait for it to come back.
#
# Usage:
#   ./restart.sh              # Restart Jetson (sentry auto-starts on boot)
#   ./restart.sh --wait       # Restart and wait until dashboard is accessible
#
# After reboot, the sentry.service systemd unit auto-starts app.py.
# Video is always clean after a fresh boot.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env for Jetson connection details
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^\s*$' | xargs)
fi

JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${JETSON_IP:-jetson.local}"
PORT=8000

echo "══════════════════════════════════════════════"
echo "  Restarting Jetson: ${JETSON_USER}@${JETSON_HOST}"
echo "══════════════════════════════════════════════"

# Check Jetson is reachable
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
    echo "❌ Cannot reach Jetson at ${JETSON_HOST}."
    exit 1
fi

# Send reboot command
echo "🔄 Sending reboot command..."
ssh "${JETSON_USER}@${JETSON_HOST}" "echo '${JETSON_PASSWORD}' | sudo -S reboot" 2>/dev/null || true

echo "✅ Reboot command sent."
echo "   Jetson is rebooting now (~60-90 seconds)."
echo ""
echo "   After boot, sentry.service will auto-start:"
echo "   Dashboard: http://${JETSON_HOST}:${PORT}"

# Wait mode: poll until the dashboard is accessible
if [[ "${1:-}" == "--wait" ]]; then
    echo ""
    echo "⏳ Waiting for Jetson to come back online..."
    
    # Wait for SSH to come back (up to 120 seconds)
    TIMEOUT=120
    ELAPSED=0
    sleep 10  # Give it time to actually shut down first
    
    while [ $ELAPSED -lt $TIMEOUT ]; do
        if ssh -o ConnectTimeout=3 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
            echo "   SSH is back after ~${ELAPSED}s."
            break
        fi
        sleep 5
        ELAPSED=$((ELAPSED + 5))
        printf "   %ds..." "$ELAPSED"
    done
    
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo ""
        echo "❌ Jetson did not come back within ${TIMEOUT}s."
        exit 1
    fi
    
    # Wait for the dashboard to be accessible (app.py takes ~15-20s to start)
    echo "   Waiting for sentry service to start..."
    sleep 20
    
    DASHBOARD_TIMEOUT=60
    ELAPSED=0
    while [ $ELAPSED -lt $DASHBOARD_TIMEOUT ]; do
        if curl -s --connect-timeout 3 "http://${JETSON_HOST}:${PORT}/api/status" > /dev/null 2>&1; then
            echo ""
            echo "══════════════════════════════════════════════"
            echo "  ✅ Jetson is back online!"
            echo ""
            echo "  Dashboard: http://${JETSON_HOST}:${PORT}"
            echo "  Logs: ssh ${JETSON_USER}@${JETSON_HOST} 'tail -f /home/jetson/dropMosquitoes/sentry.log'"
            echo "══════════════════════════════════════════════"
            exit 0
        fi
        sleep 5
        ELAPSED=$((ELAPSED + 5))
        printf "   %ds..." "$ELAPSED"
    done
    
    echo ""
    echo "⚠️  SSH is up but dashboard not responding yet."
    echo "   Check logs: ssh ${JETSON_USER}@${JETSON_HOST} 'tail -f /home/jetson/dropMosquitoes/sentry.log'"
fi
