#!/bin/bash
# Respawn wrapper for unified-search
# Auto-restarts on crash, logs to /tmp/

PORT=8900
DIR="/mnt/g/knowledge/project/openclaw-unified-search"
PYTHON="/home/zccyman/anaconda3/envs/stock/bin/python"
LOG="/tmp/unified-search.log"
ERR="/tmp/unified-search-err.log"
PIDFILE="/tmp/unified-search.pid"

cd "$DIR"

# Kill existing instance
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    kill "$OLD_PID" 2>/dev/null
    sleep 2
fi

# Check if port is in use
if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[$(date)] Port $PORT already in use, killing..."
    fuser -k ${PORT}/tcp 2>/dev/null
    sleep 2
fi

echo "[$(date)] Starting unified-search (respawn wrapper)..." > "$LOG"

while true; do
    echo "[$(date)] Starting uvicorn..." >> "$LOG"
    $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --log-level warning >> "$LOG" 2>> "$ERR"
    EXIT_CODE=$?
    echo "[$(date)] Exited with code $EXIT_CODE, restarting in 5s..." >> "$LOG"
    sleep 5
done &
echo $! > "$PIDFILE"
echo "Started with PID $(cat $PIDFILE)"
