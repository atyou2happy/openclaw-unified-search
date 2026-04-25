"""API routes for unified search."""

import asyncio

from fastapi import APIRouter, HTTPException
from app.models import SearchRequest, SearchResponse, ModuleStatus
from app.engine import engine, avail_cache
from app.modules import get_all, get, auto_register, _registry
from app.cache import cache
from app.version import __version__

router = APIRouter()


# ============================================================
# Health helpers
# ============================================================

async def _count_available() -> int:
    """Count available modules using cached availability."""
    modules = get_all()
    available = 0
    for name, m in modules.items():
        try:
            cached = avail_cache.get(name)
            if cached is True:
                available += 1
            elif cached is False:
                pass
            elif await m.is_available():
                available += 1
                avail_cache.set(name, True)
        except Exception:
            pass
    return available, len(modules)


# ============================================================
# Search endpoints
# ============================================================


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """统一搜索 — 智能调度 + 并行调用"""
    return await engine.search(request)


@router.post("/search/cdp", response_model=SearchResponse)
async def search_cdp_fallback(request: SearchRequest):
    """CDP AI Agent 降级搜索 — 按质量排序自动降级"""
    return await engine.cdp_search_fallback(request)


@router.post("/search/{module_name}", response_model=SearchResponse)
async def search_module(module_name: str, request: SearchRequest):
    """指定模块搜索"""
    return await engine.search_module(module_name, request)


# ============================================================
# Status endpoints
# ============================================================


@router.get("/health")
async def health():
    """服务健康检查"""
    available, total = await _count_available()
    return {
        "status": "ok",
        "version": __version__,
        "modules_total": total,
        "modules_available": available,
    }


@router.get("/health/detailed")
async def health_detailed():
    """详细健康检查 — 实时检查每个模块（包括 CDP）"""
    from app.modules.cdp_pool import is_cdp_available

    modules = get_all()
    results = {}
    available = 0
    cdp_reachable = await is_cdp_available(force=True)

    for name, m in modules.items():
        try:
            healthy = await asyncio.wait_for(m.health_check(), timeout=10)
        except Exception:
            healthy = False

        is_cdp = "CDP" in m.description
        status = "ok" if healthy else "down"

        if is_cdp and healthy and not cdp_reachable:
            status = "degraded"
            healthy = False

        if healthy:
            available += 1

        results[name] = {
            "description": m.description,
            "status": status,
            "available": healthy,
            "error": getattr(m, "_last_error", None),
        }

    return {
        "status": "ok",
        "version": __version__,
        "modules_total": len(modules),
        "modules_available": available,
        "cdp_reachable": cdp_reachable,
        "modules": results,
    }


@router.get("/modules", response_model=list[ModuleStatus])
async def list_modules():
    """列出所有已注册模块及状态"""
    modules = get_all()
    statuses = []
    for name, mod in modules.items():
        try:
            available = await mod.is_available()
        except Exception:
            available = False
        statuses.append(ModuleStatus(
            name=name,
            description=mod.description,
            available=available,
        ))
    return statuses


@router.get("/modules/{name}/status", response_model=ModuleStatus)
async def module_status(name: str):
    """获取单个模块状态"""
    mod = get(name)
    if not mod:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")
    try:
        available = await mod.is_available()
    except Exception:
        available = False
    return ModuleStatus(
        name=name,
        description=mod.description,
        available=available,
    )


# ============================================================
# Cache endpoints
# ============================================================


@router.get("/cache/stats")
async def cache_stats():
    """缓存统计"""
    return cache.stats()


@router.delete("/cache")
async def cache_clear():
    """清除缓存"""
    count = cache.clear()
    return {"cleared": count}


# ============================================================
# Admin endpoints
# ============================================================


@router.post("/reload")
async def reload_modules():
    """热加载模块 — 不重启服务，重新注册所有模块"""
    from app.modules.cdp_pool import reset_cache

    old_count = len(_registry)
    _registry.clear()
    reset_cache()
    avail_cache.invalidate()

    modules = auto_register()
    engine.load_modules()

    for m in modules:
        m.reset_availability()

    available = 0
    for m in modules:
        try:
            if await asyncio.wait_for(m.health_check(), timeout=10):
                available += 1
        except Exception:
            pass

    return {
        "old_modules": old_count,
        "new_modules": len(modules),
        "available": available,
        "status": "reloaded",
    }
