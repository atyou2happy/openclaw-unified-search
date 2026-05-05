"""Unified Search API — 统一搜索服务 for OpenClaw."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Config
from app.router import router
from app.version import __version__
from app.engine import engine
from app.modules import auto_register, get_all

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("unified-search")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup + shutdown lifecycle.

    v1.0.0: Replaces deprecated @app.on_event("startup").
    Manages module health checks on startup and httpx client cleanup on shutdown.
    """
    # ---- Startup ----
    modules = auto_register()
    engine.load_modules()

    async def check(m):
        try:
            ok = await asyncio.wait_for(m.is_available(), timeout=3.0)
        except (asyncio.TimeoutError, Exception):
            ok = False
        return m, ok

    results = await asyncio.gather(*[check(m) for m in modules])

    ok_count = sum(1 for _, ok in results if ok)
    logger.info(
        "v%s loaded %d modules (%d available)",
        __version__, len(modules), ok_count,
    )
    for m, ok in results:
        level = logging.INFO if ok else logging.WARNING
        logger.log(level, "  %s %s: %s", "✅" if ok else "❌", m.name, m.description)

    yield  # ---- App runs here ----

    # ---- Shutdown: close all httpx connection pools ----
    all_modules = get_all()
    for m in all_modules.values():
        try:
            await m.close_http_client()
        except Exception as e:
            logger.warning("Failed to close httpx client for %s: %s", m.name, e)
    logger.info("Shutdown complete — all httpx clients closed")


app = FastAPI(
    title="Unified Search",
    description="统一搜索服务 — 全面、准确、最新、高质量的信息获取",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=Config.DEBUG,
    )
