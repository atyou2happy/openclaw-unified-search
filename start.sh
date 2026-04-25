#!/bin/bash
# Start unified-search as a detached daemon (survives exec timeout)
PORT=8900
DIR="/mnt/g/knowledge/project/openclaw-unified-search"
PYTHON="/home/zccyman/anaconda3/envs/stock/bin/python"
LOG="/tmp/unified-search.log"

# Kill existing
pkill -f "uvicorn app.main:app --port $PORT" 2>/dev/null
sleep 2

cd "$DIR"
setsid $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --log-level warning >> $LOG 2>&1 &
echo "Started, PID=$!"
sleep 8
curl -s --noproxy localhost http://localhost:8900/health | jq '{version, modules_available}'
