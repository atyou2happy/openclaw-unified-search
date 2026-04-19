"""Kimi search module — 通过 TabBitBrowser CDP 使用 Kimi AI 搜索.

技术方案：
- 通过 CDP 新建标签页访问 kimi.com
- contenteditable div 逐字符输入
- 点击发送按钮
- 等待回复并提取
"""

import asyncio
import json
import logging
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class KimiModule(BaseSearchModule):
    name = "kimi"
    description = "Kimi AI 搜索（TabBitBrowser CDP）"

    EDITOR_SELECTOR = ".chat-input-editor"
    SEND_SELECTOR = ".send-button-container"
    KIMI_URL = "https://www.kimi.com/"
    RESPONSE_SELECTORS = [
        '[class*="markdown"]',
        '[class*="message-content"]',
        '[class*="answer-content"]',
        '[class*="chat-message"]',
    ]

    def __init__(self):
        super().__init__()
        self._cdp_port = getattr(Config, 'TABBIT_CDP_PORT', 9222)

    async def health_check(self) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
                return resp.status_code == 200
        except Exception:
            return False

    def reset_availability(self):
        self._is_available = None

    async def _ws_connect(self, url: str):
        import os
        import websockets
        saved = {}
        for k in ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
            saved[k] = os.environ.get(k)
            os.environ.pop(k, None)
        try:
            return await websockets.connect(url)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    async def _cdp(self, ws, method, params=None, mid=1):
        cmd = {"id": mid, "method": method}
        if params:
            cmd["params"] = params
        await ws.send(json.dumps(cmd))
        # Read responses until matching id (skip CDP events)
        for _ in range(50):
            raw = await ws.recv()
            r = json.loads(raw)
            if r.get("id") == mid:
                return r
        return {"error": "CDP response timeout"}

    async def _wait(self, ws, selector, timeout=15):
        for i in range(timeout):
            r = await self._cdp(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{selector}")?"ok":""'
            }, mid=9000 + i)
            if r.get("result", {}).get("result", {}).get("value"):
                return True
            await asyncio.sleep(1)
        return False

    async def _type(self, ws, text):
        mid = 100
        for ch in text:
            await self._cdp(ws, "Input.dispatchKeyEvent", {"type": "char", "text": ch}, mid=mid)
            mid += 1
            await asyncio.sleep(0.02)

    async def _wait_response(self, ws, timeout=60, interval=3):
        last = ""
        stable = 0
        sels = ", ".join(f"'{s}'" for s in self.RESPONSE_SELECTORS)
        for i in range(timeout // interval):
            await asyncio.sleep(interval)
            r = await self._cdp(ws, "Runtime.evaluate", {
                "expression": f'''
                (() => {{
                    const sels = [{sels}];
                    let t = "";
                    for (const s of sels) {{
                        const els = document.querySelectorAll(s);
                        if (els.length > 0) {{
                            t = Array.from(els).slice(-1)[0].textContent.trim();
                            if (t.length > 10) break;
                        }}
                    }}
                    if (!t || t.length < 10) {{
                        t = Array.from(document.querySelectorAll('p'))
                            .filter(e => e.textContent.trim().length > 20)
                            .map(e => e.textContent.trim()).slice(-3).join('\\n\\n');
                    }}
                    return t;
                }})()
                '''
            }, mid=8000 + i)
            text = r.get("result", {}).get("result", {}).get("value", "")
            if text and text == last:
                stable += 1
                if stable >= 2:
                    return text
            else:
                stable = 0
                last = text
        return last

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        tab_id = None
        ws = None
        bws = None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                resp = await c.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
                browser_ws = resp.json()["webSocketDebuggerUrl"]

            bws = await self._ws_connect(browser_ws)
            await bws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": self.KIMI_URL}}))
            r = json.loads(await bws.recv())
            tab_id = r.get("result", {}).get("targetId", "")
            await bws.close()
            bws = None

            if not tab_id:
                return []

            await asyncio.sleep(6)

            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                resp = await c.get(f"http://127.0.0.1:{self._cdp_port}/json/list")
                tabs = resp.json()

            ws_url = next((t["webSocketDebuggerUrl"] for t in tabs if t.get("id", "").startswith(tab_id)), None)
            if not ws_url:
                return []

            ws = await self._ws_connect(ws_url)

            if not await self._wait(ws, self.EDITOR_SELECTOR):
                return []

            await self._cdp(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{self.EDITOR_SELECTOR}").focus();"ok"'
            })

            await self._type(ws, request.query)

            # Click send
            await self._cdp(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{self.SEND_SELECTOR}")?.click();"sent"'
            })

            logger.info(f"Kimi: waiting for response to '{request.query[:30]}'")
            text = await self._wait_response(ws, timeout=request.timeout or 60)

            if not text:
                return []

            return [SearchResult(
                title=f"Kimi AI: {request.query[:50]}",
                url=self.KIMI_URL,
                snippet=text[:500],
                source=self.name,
                score=1.0,
            )]

        except Exception as e:
            logger.error(f"Kimi search error: {e}")
            return []
        finally:
            for w in [ws, bws]:
                try:
                    if w: await w.close()
                except: pass
            if tab_id:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
                        await c.get(f"http://127.0.0.1:{self._cdp_port}/json/close/{tab_id}")
                except: pass
