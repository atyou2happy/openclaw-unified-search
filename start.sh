#!/bin/bash
# unified-search daemon launcher
# Usage: bash start.sh [start|stop|status]

PROJ="/mnt/g/knowledge/project/openclaw-unified-search"
PYTHON="/home/zccyman/anaconda3/envs/stock/bin/python"
PIDFILE="/tmp/unified-search.pid"
LOGFILE="/tmp/unified-search.log"

case "${1:-start}" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
      echo "Already running (PID $(cat $PIDFILE))"
      exit 0
    fi
    cd "$PROJ"
    export HTTP_PROXY=http://127.0.0.1:21882
    export HTTPS_PROXY=http://127.0.0.1:21882
    export http_proxy=http://127.0.0.1:21882
    export https_proxy=http://127.0.0.1:21882
    # Double fork to fully detach from controlling terminal
    ( setsid $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8900 --log-level warning >> "$LOGFILE" 2>&1 & echo $! > "$PIDFILE" ) &
    sleep 2
    if kill -0 $(cat "$PIDFILE") 2>/dev/null; then
      echo "Started (PID $(cat $PIDFILE))"
    else
      echo "Failed to start"
    fi
    ;;
  stop)
    [ -f "$PIDFILE" ] && kill $(cat "$PIDFILE") 2>/dev/null && rm "$PIDFILE" && echo "Stopped" || echo "Not running"
    ;;
  status)
    [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null && echo "Running (PID $(cat $PIDFILE))" || echo "Not running"
    ;;
esac
