"""Unified Search API — 统一搜索服务 for OpenClaw."""

from fastapi import FastAPI
from app.config import Config
from app.router import router
from app.engine import engine
from app.modules import auto_register


app = FastAPI(
    title="Unified Search",
    description="统一搜索服务 — 全面、准确、最新、高质量的信息获取",
    version="0.1.0",
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
        ok = await m.is_available()
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
