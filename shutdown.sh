#!/bin/bash
# shutdown.sh — Gracefully stop the system and power off the Jetson Orin Nano
#
# Usage:
#   ./shutdown.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env for Jetson connection details
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^\s*$' | xargs)
fi

JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${JETSON_IP:-jetson.local}"

echo "══════════════════════════════════════════════"
echo "  Sniper Messy Mortar — Jetson Shutdown"
echo "  Target: ${JETSON_USER}@${JETSON_HOST}"
echo "══════════════════════════════════════════════"

# Stop running servers/services first
if [ -f "$SCRIPT_DIR/stop.sh" ]; then
    echo "🛑 Step 1/2: Stopping sentry servers..."
    "$SCRIPT_DIR/stop.sh"
else
    echo "⚠️  stop.sh not found. Skipping stop script..."
fi

echo ""
echo "🔌 Step 2/2: Sending shutdown command to Jetson..."

# Check if Jetson is reachable before attempting SSH
if ssh -o ConnectTimeout=3 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
    ssh "${JETSON_USER}@${JETSON_HOST}" bash <<ENDSSH
        echo '🔌 Initiating remote shutdown...'
        echo '${JETSON_PASSWORD}' | sudo -S shutdown now 2>/dev/null || true
ENDSSH
    echo "⚡ Shutdown command sent successfully. The Jetson is powering down."
else
    echo "❌ Cannot reach Jetson at ${JETSON_HOST}. (Is it already off or disconnected?)"
    exit 1
fi
echo "══════════════════════════════════════════════"
