#!/bin/bash
# run-ai.sh — Start with full AI detection (requires TensorRT model)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.sentry.pid"
LOG_FILE="$SCRIPT_DIR/sentry.log"
PORT=8000

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "⚠️  Server already running (PID $(cat "$PID_FILE")). Run ./stop.sh first."
    exit 1
fi

echo "🎯 Starting Sniper Messy Mortar (AI mode)..."
cd "$SCRIPT_DIR"
python3 app.py --port "$PORT" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "✅ Server started (PID $(cat "$PID_FILE"))"
    echo "   Dashboard: http://localhost:$PORT"
    echo "   Run ./stop.sh to shut down."
else
    echo "❌ Server failed. Check $LOG_FILE"
    rm -f "$PID_FILE"; tail -20 "$LOG_FILE"; exit 1
fi
