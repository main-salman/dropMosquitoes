#!/bin/bash
# Stop the Sentry Control Center Streamlit app

echo "Stopping Sentry Control Center..."
pkill -f "streamlit run app.py"

if [ $? -eq 0 ]; then
    echo "Successfully stopped."
else
    echo "Sentry Control Center was not running."
fi
