#!/bin/bash
# start-all-services.sh — 一键启动所有依赖服务 + unified-search
# 用法：bash start-all-services.sh [--skip-us]
# 版本：1.0 | 2026-04-20

set -e

# ===== 配置 =====
PYTHON=/home/zccyman/anaconda3/envs/stock/bin/python
US_DIR=/mnt/g/knowledge/project/openclaw-unified-search
US_PORT=8900
MEILI_PORT=7700
MEILI_DATA=/mnt/d/meilisearch/data
MEILI_KEY=claw2026
SEARXNG_PORT=8080
CDP_PORT=9222
OLLAMA_PORT=11434

# ===== 颜色 =====
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }
wait() { echo -e "${YELLOW}⏳ $1${NC}"; }

# ===== Step 0: 清理环境变量 =====
unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1

echo "========================================="
echo "  OpenClaw 全服务启动脚本 v1.0"
echo "========================================="
echo ""

# ===== Step 1: Docker =====
if ! docker info > /dev/null 2>&1; then
    wait "启动 Docker daemon..."
    sudo nohup dockerd > /tmp/docker.log 2>&1 &
    for i in $(seq 1 30); do
        docker info > /dev/null 2>&1 && break
        sleep 1
    done
    if docker info > /dev/null 2>&1; then
        ok "Docker daemon 已启动"
    else
        fail "Docker daemon 启动失败"
        exit 1
    fi
else
    ok "Docker daemon 运行中"
fi

# ===== Step 2: SearXNG =====
if curl -s --max-time 3 http://localhost:$SEARXNG_PORT/healthz > /dev/null 2>&1; then
    ok "SearXNG 运行中 (port $SEARXNG_PORT)"
else
    wait "启动 SearXNG..."
    if docker ps -a --format '{{.Names}}' | grep -q searxng; then
        docker start searxng > /dev/null 2>&1
    else
        fail "SearXNG 容器不存在，请先创建"
    fi
    # 等待就绪
    for i in $(seq 1 30); do
        curl -s --max-time 3 http://localhost:$SEARXNG_PORT/healthz > /dev/null 2>&1 && break
        sleep 1
    done
    if curl -s --max-time 3 http://localhost:$SEARXNG_PORT/healthz > /dev/null 2>&1; then
        ok "SearXNG 已启动"
    else
        fail "SearXNG 启动超时"
    fi
fi

# ===== Step 3: metaso (秘塔) =====
if docker ps --format '{{.Names}}' | grep -q metaso; then
    ok "metaso 运行中"
else
    wait "启动 metaso..."
    if docker ps -a --format '{{.Names}}' | grep -q metaso; then
        docker start metaso > /dev/null 2>&1
        ok "metaso 已启动"
    else
        fail "metaso 容器不存在（非必须，跳过）"
    fi
fi

# ===== Step 4: Meilisearch =====
if curl -s --max-time 3 http://localhost:$MEILI_PORT/health 2>/dev/null | grep -q available; then
    ok "Meilisearch 运行中 (port $MEILI_PORT)"
else
    wait "启动 Meilisearch..."
    pkill -f "meilisearch.*--http-addr" 2>/dev/null || true
    sleep 1
    MEILI_MASTER_KEY=$MEILI_KEY nohup meilisearch \
        --db-path $MEILI_DATA \
        --http-addr 0.0.0.0:$MEILI_PORT \
        --no-analytics \
        > /tmp/meilisearch.log 2>&1 &
    
    for i in $(seq 1 15); do
        curl -s --max-time 3 http://localhost:$MEILI_PORT/health 2>/dev/null | grep -q available && break
        sleep 1
    done
    if curl -s --max-time 3 http://localhost:$MEILI_PORT/health 2>/dev/null | grep -q available; then
        ok "Meilisearch 已启动"
    else
        fail "Meilisearch 启动失败"
    fi
fi

# ===== Step 5: Ollama =====
if pgrep ollama > /dev/null 2>&1; then
    ok "Ollama 运行中 (port $OLLAMA_PORT)"
else
    wait "启动 Ollama..."
    OLLAMA_HOST=0.0.0.0 nohup ollama serve > /tmp/ollama.log 2>&1 &
    for i in $(seq 1 15); do
        curl -s --max-time 3 http://localhost:$OLLAMA_PORT/api/tags > /dev/null 2>&1 && break
        sleep 1
    done
    if curl -s --max-time 3 http://localhost:$OLLAMA_PORT/api/tags > /dev/null 2>&1; then
        ok "Ollama 已启动"
    else
        fail "Ollama 启动失败（非必须）"
    fi
fi

# ===== Step 6: TabBitBrowser CDP 检测 =====
if curl -s --noproxy '*' --max-time 3 http://127.0.0.1:$CDP_PORT/json/version > /dev/null 2>&1; then
    ok "TabBitBrowser CDP 可达 (port $CDP_PORT)"
else
    fail "TabBitBrowser CDP 不可达 — CDP 模块将不可用"
    echo "   请确认 TabBitBrowser 已开启远程调试端口 $CDP_PORT"
fi

# ===== Step 7: unified-search =====
if [ "$1" = "--skip-us" ]; then
    echo ""
    ok "跳过 US 启动（--skip-us）"
    exit 0
fi

# Kill existing US
pkill -f "uvicorn app.main:app.*--port $US_PORT" 2>/dev/null || true
sleep 2

wait "启动 unified-search..."
cd $US_DIR
nohup $PYTHON -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $US_PORT \
    --log-level info \
    > /tmp/unified-search.log 2>&1 &

US_PID=$!
echo "   PID: $US_PID"

# 等待就绪
for i in $(seq 1 30); do
    curl -s --max-time 3 http://localhost:$US_PORT/health > /dev/null 2>&1 && break
    sleep 1
done

if curl -s --max-time 5 http://localhost:$US_PORT/health > /dev/null 2>&1; then
    # 统计可用模块
    HEALTH=$(curl -s --max-time 5 http://localhost:$US_PORT/health 2>/dev/null)
    AVAIL=$(echo $HEALTH | python3 -c "import sys,json; print(json.load(sys.stdin).get('modules_available',0))" 2>/dev/null)
    TOTAL=$(echo $HEALTH | python3 -c "import sys,json; print(json.load(sys.stdin).get('modules_total',0))" 2>/dev/null)
    ok "unified-search 已启动 — $AVAIL/$TOTAL 模块可用 (port $US_PORT)"
else
    fail "unified-search 启动失败，查看日志：tail -20 /tmp/unified-search.log"
fi

echo ""
echo "========================================="
echo "  启动完成！"
echo "========================================="
