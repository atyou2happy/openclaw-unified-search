#!/bin/bash
# unified-search Docker 容器启动脚本
# 用法: bash start-docker.sh
# 前提: Docker 已启动（Windows Docker Desktop 或 WSL sudo service docker start）

set -e

echo "=== 检查 Docker ==="
if ! docker info &>/dev/null; then
    echo "❌ Docker 未运行，请先启动："
    echo "   Windows: 打开 Docker Desktop"
    echo "   WSL: sudo service docker start"
    exit 1
fi
echo "✅ Docker 正常"

# ─── SearXNG ───
echo ""
echo "=== SearXNG (聚合搜索引擎) ==="
if docker ps --format '{{.Names}}' | grep -q '^searxng$'; then
    echo "✅ SearXNG 已在运行"
else
    if docker ps -a --format '{{.Names}}' | grep -q '^searxng$'; then
        echo "启动已有容器..."
        docker start searxng
    else
        echo "创建新容器..."
        docker run -d \
            --name searxng \
            --network host \
            -v /mnt/g/knowledge/project/openclaw-unified-search/docker/searxng:/etc/searxng:rw \
            -e SEARXNG_BASE_URL=http://localhost:8080/ \
            searxng/searxng:latest
    fi
    echo "✅ SearXNG 启动完成"
fi

# 等待 SearXNG 就绪
echo "等待 SearXNG 就绪..."
for i in $(seq 1 30); do
    if curl -s --noproxy '*' --max-time 2 http://127.0.0.1:8080/healthz 2>/dev/null | grep -q "ok"; then
        echo "✅ SearXNG 就绪 (${i}s)"
        break
    fi
    sleep 1
done

# ─── Metaso (秘塔AI搜索) ───
echo ""
echo "=== Metaso (秘塔AI搜索) ==="
METASO_TOKEN="69dd027a968b2a8345d3ad29-47c7dcfaa7784f29948e25d8b5be4ca2"
if docker ps --format '{{.Names}}' | grep -q '^metaso$'; then
    echo "✅ Metaso 已在运行"
else
    if docker ps -a --format '{{.Names}}' | grep -q '^metaso$'; then
        echo "删除旧容器（需要更新Token）..."
        docker rm -f metaso
    fi
    echo "创建新容器..."
    docker run -d \
        --name metaso \
        --network host \
        -e METASO_TOKEN="$METASO_TOKEN" \
        vinlic/metaso-free-api
    echo "✅ Metaso 启动完成"
fi

# 等待 Metaso 就绪
echo "等待 Metaso 就绪..."
for i in $(seq 1 30); do
    if curl -s --noproxy '*' --max-time 2 http://127.0.0.1:8000/ 2>/dev/null | head -c 5 | grep -q "."; then
        echo "✅ Metaso 就绪 (${i}s)"
        break
    fi
    sleep 1
done

# ─── 验证 ───
echo ""
echo "=== 验证 ==="
echo "容器状态:"
docker ps --format "  {{.Names}}\t{{.Status}}\t{{.Image}}"

echo ""
echo "SearXNG health:"
curl -s --noproxy '*' --max-time 3 http://127.0.0.1:8080/healthz 2>&1 || echo "  ❌ 无响应"

echo ""
echo "Metaso:"
curl -s --noproxy '*' --max-time 3 http://127.0.0.1:8000/ 2>&1 | head -c 100 || echo "  ❌ 无响应"

echo ""
echo "=== 完成 ==="
echo "现在重启 unified-search 服务使模块生效:"
echo "  cd /mnt/g/knowledge/project/openclaw-unified-search"
echo "  bash scripts/restart.sh"
