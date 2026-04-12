"""TabBitBrowser search module — 核心 AI 搜索."""

import asyncio
import sys
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class TabBitModule(BaseSearchModule):
    name = "tabbit"
    description = "TabBitBrowser AI 搜索（本地 CDP，质量最高）"

    def __init__(self):
        super().__init__()
        self._cdp_port = Config.TABBIT_CDP_PORT
        self._script_path = Config.TABBIT_SCRIPT_PATH

    async def health_check(self) -> bool:
        """检查 TabBitBrowser CDP 端口是否可达"""
        import httpx
        proxy = Config.get_proxy()
        kwargs = {"timeout": 5}
        if proxy:
            kwargs["proxy"] = proxy
        try:
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    f"http://localhost:{self._cdp_port}/json",
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """通过 CDP 脚本执行搜索"""
        timeout = min(request.timeout, Config.TABBIT_TIMEOUT)
        max_chars = 8000 if request.depth == "deep" else 5000

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, self._script_path,
                request.query,
                "--port", str(self._cdp_port),
                "--timeout", str(timeout),
                "--max-chars", str(max_chars),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 10
            )

            if proc.returncode != 0:
                self._available = False
                return []

            content = stdout.decode("utf-8", errors="replace").strip()
            if not content:
                return []

            return [SearchResult(
                title=f"TabBitBrowser: {request.query}",
                url="",
                snippet=content[:500],
                content=content,
                source=self.name,
                relevance=0.95,
            )]

        except asyncio.TimeoutError:
            return []
        except Exception:
            return []
