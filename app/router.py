"""API routes for unified search."""

from fastapi import APIRouter, HTTPException
from app.models import SearchRequest, SearchResponse, ModuleStatus
from app.engine import engine
from app.modules import get_all
from app.cache import cache

router = APIRouter()


@router.get("/health")
async def health():
    """服务健康检查"""
    modules = get_all()
    available = 0
    for m in modules.values():
        try:
            if await m.is_available():
                available += 1
        except Exception:
            pass
    return {
        "status": "ok",
        "modules_total": len(modules),
        "modules_available": available,
    }


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """统一搜索 — 智能调度 + 并行调用"""
    return await engine.search(request)

@router.post("/search/cdp", response_model=SearchResponse)
async def search_cdp_fallback(request: SearchRequest):
    """CDP AI Agent 降级搜索 — 按质量排序自动降级
    
    按搜索质量依次尝试：tabbit → deepseek → gemini → grok → kimi → glm → qwen
    第一个成功即返回，失败自动降级到下一个
    """
    return await engine.cdp_search_fallback(request)



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
    from app.modules import get
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


@router.get("/cache/stats")
async def cache_stats():
    """缓存统计"""
    return cache.stats()


@router.delete("/cache")
async def cache_clear():
    """清除缓存"""
    count = cache.clear()
    return {"cleared": count}
