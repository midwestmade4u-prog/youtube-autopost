#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  auto_watcher.sh — MidwestMade4U Auto-Post Watcher
#  Runs continuously on your Mac, picks up trigger files written
#  by Cowork's scheduled tasks, and runs the video pipeline.
#
#  Start manually:    bash auto_watcher.sh
#  Auto-start at login: load the launchd plist (see SETUP below)
# ═══════════════════════════════════════════════════════════════════

# ── Config ─────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$PROJECT_DIR/watcher.log"
PYTHON="python3"
CHECK_INTERVAL=30   # seconds between scans

# ── Startup banner ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Auto-Post Watcher — MidwestMade4U              ║"
echo "║   Watching for scheduled posts...                ║"
echo "╚══════════════════════════════════════════════════╝"
echo "   Project: $PROJECT_DIR"
echo "   Log:     $LOG"
echo "   Checking every ${CHECK_INTERVAL}s for trigger files."
echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Watcher started." >> "$LOG"

# ── Main loop ──────────────────────────────────────────────────────
while true; do
    # Look for trigger files: auto_trigger_tmf_20260416_1200.json etc.
    for trigger in "$PROJECT_DIR"/auto_trigger_*.json; do
        # Skip glob literal (no match)
        [ -f "$trigger" ] || continue

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📬 Trigger found: $(basename "$trigger")" | tee -a "$LOG"

        # Extract channel from JSON
        channel=$("$PYTHON" -c "
import json, sys
try:
    d = json.load(open('$trigger'))
    print(d.get('channel', 'bsg'))
except Exception as e:
    print('bsg')
" 2>/dev/null)

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🎬 Running pipeline for channel: $channel" | tee -a "$LOG"

        # Run auto_post.py with the trigger file (installs deps if needed, runs full pipeline)
        cd "$PROJECT_DIR"
        "$PYTHON" auto_post.py --trigger-file "$trigger" 2>&1 | tee -a "$LOG"
        EXIT_CODE=${PIPESTATUS[0]}

        if [ $EXIT_CODE -eq 0 ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Pipeline completed for $channel" | tee -a "$LOG"
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Pipeline failed (exit $EXIT_CODE) for $channel" | tee -a "$LOG"
        fi
    done

    sleep "$CHECK_INTERVAL"
done
