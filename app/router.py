"""API routes for unified search."""

from fastapi import APIRouter, HTTPException
from app.models import SearchRequest, SearchResponse, ModuleStatus
from app.engine import engine
from app.modules import get_all
from app.cache import cache

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """统一搜索 — 并行调用所有可用模块"""
    return await engine.search(request)


@router.post("/search/{module_name}", response_model=SearchResponse)
async def search_module(module_name: str, request: SearchRequest):
    """指定模块搜索"""
    return await engine.search_module(module_name, request)


@router.get("/modules", response_model=list[ModuleStatus])
async def list_modules():
    """列出所有已注册模块及状态"""
    modules = get_all()
    statuses = []
    for name, mod in modules.items():
        available = await mod.is_available()
        statuses.append(ModuleStatus(
            name=name,
            description=mod.description,
            available=available,
        ))
    return statuses


@router.get("/modules/{name}/status", response_model=ModuleStatus)
async def module_status(name: str):
    """获取单个模块状态"""
    from app.modules import get
    mod = get(name)
    if not mod:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")
    available = await mod.is_available()
    return ModuleStatus(
        name=name,
        description=mod.description,
        available=available,
    )


@router.get("/health")
async def health():
    """服务健康检查"""
    modules = get_all()
    available = sum(1 for m in modules.values() if await m.is_available())
    return {
        "status": "ok",
        "modules_total": len(modules),
        "modules_available": available,
    }


@router.get("/cache/stats")
async def cache_stats():
    """缓存统计"""
    return cache.stats()


@router.delete("/cache")
async def cache_clear():
    """清除缓存"""
    count = cache.clear()
    return {"cleared": count}
