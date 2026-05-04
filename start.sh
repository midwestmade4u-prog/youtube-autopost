#!/bin/bash
# ── Bible Story Garden — Video Studio Launcher ────────────────────────────
# Run this instead of python3 video_app.py
# It automatically stops any old version and starts fresh

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Bible Story Garden — Video Studio      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Kill any existing instance on port 5001
EXISTING=$(lsof -ti:5002)
if [ ! -z "$EXISTING" ]; then
  echo "⏹  Stopping old version..."
  kill $EXISTING 2>/dev/null
  sleep 1
fi

# Also kill any stray video_app processes
pkill -f "video_app.py" 2>/dev/null
sleep 0.5

echo "✅  Starting fresh..."
echo "   Chrome will open automatically."
echo "   Keep this window open while you work."
echo ""

# Change to the script's directory (works from anywhere)
cd "$(dirname "$0")"

# Start the app
python3 video_app.py
