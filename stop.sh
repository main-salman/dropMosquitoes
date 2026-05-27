#!/bin/bash
# stop.sh — Stop the Sniper Messy Mortar server (local or Jetson)
#
# Usage:
#   ./stop.sh          # Stop Jetson server (default) + any local server
#   ./stop.sh --local  # Stop local server only

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.sentry.pid"

# Load .env for Jetson connection details
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^\s*$' | xargs)
fi

JETSON_USER="${JETSON_USER:-jetson}"
JETSON_HOST="${JETSON_IP:-jetson.local}"
JETSON_PATH="/home/${JETSON_USER}/dropMosquitoes"

# ---- Stop local server (if running) ----
stop_local() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "🛑 Stopping local server (PID $PID)..."
            kill -INT "$PID" 2>/dev/null
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                echo "   Graceful shutdown timed out. Force killing..."
                kill -9 "$PID" 2>/dev/null
            fi
            echo "✅ Local server stopped."
        fi
        rm -f "$PID_FILE"
    fi
    # Kill any orphaned local process
    ORPHAN=$(pgrep -f "python3 app.py" 2>/dev/null || true)
    if [ -n "$ORPHAN" ]; then
        echo "   Found orphaned local process (PID $ORPHAN). Killing..."
        kill "$ORPHAN" 2>/dev/null || true
        sleep 1
        kill -9 "$ORPHAN" 2>/dev/null || true
        echo "✅ Orphaned process killed."
    fi
}

# Always stop local
stop_local

# ---- Stop Jetson server (unless --local only) ----
if [[ "${1:-}" != "--local" ]]; then
    if ssh -o ConnectTimeout=3 -o BatchMode=yes "${JETSON_USER}@${JETSON_HOST}" "echo ok" > /dev/null 2>&1; then
        echo "🛑 Stopping server on Jetson (${JETSON_HOST})..."
        ssh "${JETSON_USER}@${JETSON_HOST}" "
            cd ${JETSON_PATH} 2>/dev/null || true
            if [ -f .sentry.pid ]; then
                PID=\$(cat .sentry.pid)
                if kill -0 \$PID 2>/dev/null; then
                    kill -INT \$PID 2>/dev/null
                    sleep 2
                    kill -9 \$PID 2>/dev/null || true
                fi
                rm -f .sentry.pid
            fi
            pkill -f 'python3 app.py' 2>/dev/null || true
            echo '✅ Jetson server stopped.'
        "
    else
        echo "ℹ️  Jetson not reachable at ${JETSON_HOST} — skipping remote stop."
    fi
fi

echo "✅ Done."
