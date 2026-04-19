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




@router.get("/health/detailed")
async def health_detailed():
    """详细健康检查 — 实时检查每个模块（包括 CDP）"""
    from app.modules import get_all
    from app.modules.cdp_pool import is_cdp_available
    
    modules = get_all()
    results = {}
    available = 0
    cdp_reachable = await is_cdp_available(force=True)
    
    for name, m in modules.items():
        try:
            healthy = await __import__("asyncio").wait_for(
                m.health_check(), timeout=10
            )
        except Exception:
            healthy = False
        
        # For CDP modules, also report actual CDP reachability
        is_cdp = "CDP" in m.description
        status = "ok" if healthy else "down"
        
        if is_cdp and healthy and not cdp_reachable:
            status = "degraded"  # lazy check says ok but CDP unreachable
            healthy = False
            
        if healthy:
            available += 1
            
        results[name] = {
            "description": m.description,
            "status": status,
            "available": healthy,
        }
    
    return {
        "status": "ok",
        "modules_total": len(modules),
        "modules_available": available,
        "cdp_reachable": cdp_reachable,
        "modules": results,
    }

@router.post("/reload")
async def reload_modules():
    """热加载模块 — 不重启服务，重新注册所有模块
    
    适用场景：修改了模块代码后，调用此端点重新加载
    """
    from app.modules import auto_register, _registry
    from app.modules.cdp_pool import reset_cache
    
    # 清空旧注册
    old_count = len(_registry)
    _registry.clear()
    reset_cache()
    
    # 重新注册
    modules = auto_register()
    
    # 重新加载引擎
    engine.load_modules()
    
    # Reset availability cache on all modules
    for m in modules:
        m.reset_availability()
    
    # 检查可用性
    import asyncio
    available = 0
    for m in modules:
        try:
            if await asyncio.wait_for(m.health_check(), timeout=10):
                available += 1
        except:
            pass
    
    return {
        "old_modules": old_count,
        "new_modules": len(modules),
        "available": available,
        "status": "reloaded"
    }
