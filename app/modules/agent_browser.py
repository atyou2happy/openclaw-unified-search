"""Agent Browser search module — Playwright CDP 自主浏览搜索（降级策略）.

策略：
- 通过 Playwright 连接 Chrome CDP，操控浏览器搜索 Google/Bing 获取结果
- 初始优先级低（排在 web/ddg/exa 之后），作为降级备选
- 比 browser-use Agent 更轻量（无需 LLM 决策循环）
- 搜索质量由 engine 层评估，质量好再提升优先级
"""

import asyncio
import logging
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class AgentBrowserModule(BaseSearchModule):
    name = "agent_browser"
    description = "AI Agent 浏览器搜索（Playwright CDP，降级备选）"
    health_check_timeout: float = 10.0

    def __init__(self):
        super().__init__()
        self._cdp_port: int = 9222
        self._ws_url: str | None = None

    async def _get_ws_url(self) -> str | None:
        """从 CDP /json/version 获取 WebSocket URL"""
        import httpx

        for port in [9222, 9223]:
            try:
                async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                    resp = await client.get(f"http://localhost:{port}/json/version")
                    if resp.status_code == 200:
                        data = resp.json()
                        ws_url = data.get("webSocketDebuggerUrl")
                        if ws_url:
                            self._cdp_port = port
                            return ws_url
            except Exception:
                continue
        return None

    async def health_check(self) -> bool:
        self._ws_url = await self._get_ws_url()
        return self._ws_url is not None

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        timeout = min(request.timeout, 45)
        try:
            results = await asyncio.wait_for(
                self._playwright_search(request), timeout=timeout,
            )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"agent_browser timed out ({timeout}s)")
            return []
        except Exception as e:
            logger.error(f"agent_browser failed: {e}")
            return []

    async def _playwright_search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed")
            return []

        if not self._ws_url:
            self._ws_url = await self._get_ws_url()
        if not self._ws_url:
            logger.error("No CDP WebSocket URL available")
            return []

        results: list[SearchResult] = []

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(self._ws_url)
            contexts = browser.contexts
            if contexts:
                page = await contexts[0].new_page()
            else:
                context = await browser.new_context()
                page = await context.new_page()

            try:
                results = await self._search_google(page, request)
                if len(results) < 3:
                    results.extend(await self._search_bing(page, request))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        return results[:request.max_results]

    async def _search_google(self, page, request: SearchRequest) -> list[SearchResult]:
        results = []
        try:
            from urllib.parse import quote_plus
            await page.goto(
                f"https://www.google.com/search?q={quote_plus(request.query)}&hl=en",
                wait_until="domcontentloaded", timeout=20000,
            )
            await page.wait_for_timeout(3000)

            # 用 h3 定位标题，向上找父级 <a> 链接
            items = await page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                // 方法1: h3 -> 找最近的 <a> 父级/祖先
                document.querySelectorAll('h3').forEach(h3 => {
                    if (results.length >= 15) return;
                    const anchor = h3.closest('a[href]');
                    if (!anchor) return;
                    const url = anchor.href;
                    if (!url || seen.has(url)) return;
                    if (url.includes('google.com') || url.includes('webcache.') || url.includes('youtube.com')) return;
                    seen.add(url);
                    const title = h3.textContent.trim();
                    // snippet: h3 的祖父级容器的文本（排除 h3 本身）
                    const container = h3.closest('[data-sokoban-container]') || h3.parentElement?.parentElement?.parentElement;
                    let snippet = '';
                    if (container) {
                        const allText = container.innerText || '';
                        snippet = allText.replace(title, '').trim().substring(0, 300);
                    }
                    if (title && url.startsWith('http')) {
                        results.push({ title, url, snippet });
                    }
                });
                // 方法2: data-ved links（备用）
                if (results.length < 3) {
                    document.querySelectorAll('[data-ved] a[href^="http"]').forEach(a => {
                        if (results.length >= 15) return;
                        const url = a.href;
                        if (!url || seen.has(url)) return;
                        if (url.includes('google.com') || url.includes('webcache.')) return;
                        seen.add(url);
                        const title = a.textContent.trim().substring(0, 200);
                        if (title && url.startsWith('http')) {
                            results.push({ title, url, snippet: '' });
                        }
                    });
                }
                return results;
            }""")

            for item in (items or [])[:request.max_results]:
                results.append(SearchResult(
                    title=item.get("title", "")[:200],
                    url=item.get("url", ""),
                    snippet=item.get("snippet", "")[:500],
                    source=self.name,
                    relevance=0.78,
                    metadata={"engine": "google", "type": "agent_browser"},
                ))
        except Exception as e:
            logger.warning(f"Google search failed: {e}")
        return results

    async def _search_bing(self, page, request: SearchRequest) -> list[SearchResult]:
        results = []
        try:
            from urllib.parse import quote_plus
            await page.goto(
                f"https://www.bing.com/search?q={quote_plus(request.query)}",
                wait_until="domcontentloaded", timeout=20000,
            )
            await page.wait_for_timeout(3000)

            items = await page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                document.querySelectorAll('#b_results li.b_algo, #b_results .b_algo').forEach(el => {
                    if (results.length >= 10) return;
                    const link = el.querySelector('a[href^="http"]');
                    if (!link) return;
                    const url = link.href;
                    if (!url || seen.has(url) || url.includes('bing.com')) return;
                    seen.add(url);
                    const title = (el.querySelector('h2') || link).textContent.trim();
                    const snippetEl = el.querySelector('.b_caption p, p');
                    const snippet = snippetEl ? snippetEl.textContent.trim() : '';
                    if (title && url) {
                        results.push({ title, url, snippet });
                    }
                });
                return results;
            }""")

            for item in (items or [])[:request.max_results]:
                results.append(SearchResult(
                    title=item.get("title", "")[:200],
                    url=item.get("url", ""),
                    snippet=item.get("snippet", "")[:500],
                    source=self.name,
                    relevance=0.72,
                    metadata={"engine": "bing", "type": "agent_browser"},
                ))
        except Exception as e:
            logger.warning(f"Bing search failed: {e}")
        return results
