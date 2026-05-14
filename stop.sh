#!/bin/bash
# stop.sh — Stop the Sniper Messy Mortar server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.sentry.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found. Server may not be running."
    # Try to kill any orphaned process
    ORPHAN=$(pgrep -f "python3 app.py" 2>/dev/null)
    if [ -n "$ORPHAN" ]; then
        echo "   Found orphaned process (PID $ORPHAN). Killing..."
        kill "$ORPHAN" 2>/dev/null
        sleep 1
        kill -9 "$ORPHAN" 2>/dev/null
        echo "✅ Orphaned process killed."
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")
echo "🛑 Stopping Sniper Messy Mortar (PID $PID)..."

# Graceful shutdown (SIGINT = Ctrl+C, triggers atexit cleanup)
kill -INT "$PID" 2>/dev/null
sleep 2

# Force kill if still alive
if kill -0 "$PID" 2>/dev/null; then
    echo "   Graceful shutdown timed out. Force killing..."
    kill -9 "$PID" 2>/dev/null
fi

rm -f "$PID_FILE"
echo "✅ Server stopped."
