#!/bin/bash
# unified-search 服务重启脚本
# 用法: bash scripts/restart.sh

set -e

echo "=== 停止旧服务 ==="
pkill -f 'uvicorn.*8900' 2>/dev/null && echo "已停止" || echo "无运行进程"
sleep 2

echo "=== 启动 unified-search ==="
cd /mnt/g/knowledge/project/openclaw-unified-search
setsid /home/zccyman/anaconda3/envs/stock/bin/python -m uvicorn app.main:app \
    --host 127.0.0.1 --port 8900 \
    > /tmp/us.log 2>&1 &
disown

echo "等待服务就绪..."
for i in $(seq 1 30); do
    HEALTH=$(curl -s --noproxy '*' --max-time 2 http://127.0.0.1:8900/health 2>/dev/null)
    if echo "$HEALTH" | grep -q '"ok"'; then
        echo "✅ 服务就绪 (${i}s)"
        echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  模块: {d[\"modules_total\"]}个, 可用: {d[\"modules_available\"]}个')"
        exit 0
    fi
    sleep 1
done

echo "❌ 启动超时，检查日志: /tmp/us.log"
exit 1
