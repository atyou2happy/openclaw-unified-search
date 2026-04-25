"""Unified Search API — 统一搜索服务 for OpenClaw."""

import asyncio
from fastapi import FastAPI
from app.config import Config
from app.router import router
from app.version import __version__
from app.engine import engine
from app.modules import auto_register


app = FastAPI(
    title="Unified Search",
    description="统一搜索服务 — 全面、准确、最新、高质量的信息获取",
    version=__version__,
)

# Include routes
app.include_router(router)


@app.on_event("startup")
async def startup():
    """Load and register all search modules on startup (parallel health check)."""
    modules = auto_register()
    engine.load_modules()
    
    # Parallel health check — all modules at once
    async def check(m):
        try:
            ok = await asyncio.wait_for(m.is_available(), timeout=3.0)
        except (asyncio.TimeoutError, Exception):
            ok = False
        return m, ok
    
    results = await asyncio.gather(*[check(m) for m in modules])
    
    available = []
    for m, ok in results:
        status = "✅" if ok else "❌"
        available.append(f"  {status} {m.name}: {m.description}")
    
    ok_count = sum(1 for _, ok in results if ok)
    print(f"[unified-search v{__version__}] Loaded {len(modules)} modules ({ok_count} available):")
    for line in available:
        print(line)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=Config.DEBUG,
    )
