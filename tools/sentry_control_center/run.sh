#!/bin/bash
# Start the Sentry Control Center Streamlit app

cd "$(dirname "$0")"

if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "Sentry Control Center is already running!"
    exit 1
fi

echo "Starting Sentry Control Center..."
streamlit run app.py &
echo "Started with PID $!"
