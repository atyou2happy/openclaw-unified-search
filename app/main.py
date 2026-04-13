"""Unified Search API — 统一搜索服务 for OpenClaw."""

import asyncio
from fastapi import FastAPI
from app.config import Config
from app.router import router
from app.engine import engine
from app.modules import auto_register


app = FastAPI(
    title="Unified Search",
    description="统一搜索服务 — 全面、准确、最新、高质量的信息获取",
    version="0.2.0",
)

# Include routes
app.include_router(router)


@app.on_event("startup")
async def startup():
    """Load and register all search modules on startup."""
    modules = auto_register()
    engine.load_modules()
    available = []
    for m in modules:
        try:
            ok = await asyncio.wait_for(m.is_available(), timeout=6.0)
        except (asyncio.TimeoutError, Exception):
            ok = False
        status = "✅" if ok else "❌"
        available.append(f"  {status} {m.name}: {m.description}")
    print(f"[unified-search] Loaded {len(modules)} modules:")
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
