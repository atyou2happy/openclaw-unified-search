"""GLM search module — 通过 TabBitBrowser CDP 使用智谱 GLM 搜索.

技术方案：
- 通过 CDP 在 TabBitBrowser 中新建标签页
- 访问 bigmodel.cn 模型试用页面
- 逐字符输入查询（Element UI textarea 兼容）
- 点击发送按钮
- 等待 AI 回复完成并提取内容
"""

import asyncio
import json
import logging
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class GLMModule(BaseSearchModule):
    name = "glm"
    description = "智谱 GLM AI 搜索（TabBitBrowser CDP）"

    TEXTAREA_SELECTOR = "textarea.el-textarea__inner"
    SEND_BTN_SELECTOR = ".icon-send1, [class*='submit-']"
    GLM_URL = "https://www.bigmodel.cn/trialcenter/modeltrial/text?modelCode=glm-5.1"

    # GLM response selectors (multiple fallbacks)
    RESPONSE_SELECTORS = [
        '[class*="markdown"]',
        '[class*="message-content"]',
        '[class*="answer-content"]',
        '[class*="chat-message"]',
        '[class*="response-text"]',
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
        """WebSocket 连接（绕过代理）."""
        import os
        import websockets
        saved = {}
        for k in ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
            saved[k] = os.environ.get(k)
            os.environ.pop(k, None)
        try:
            ws = await websockets.connect(url)
            return ws
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    async def _cdp_send(self, ws, method: str, params: dict = None, msg_id: int = 1) -> dict:
        cmd = {"id": msg_id, "method": method}
        if params:
            cmd["params"] = params
        await ws.send(json.dumps(cmd))
        resp = json.loads(await ws.recv())
        return resp

    async def _wait_for_selector(self, ws, selector: str, timeout: int = 15) -> bool:
        for i in range(timeout):
            r = await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{selector}")?"ready":"waiting"'
            }, msg_id=9000 + i)
            if r.get("result", {}).get("result", {}).get("value") == "ready":
                return True
            await asyncio.sleep(1)
        return False

    async def _type_text(self, ws, text: str):
        mid = 100
        for ch in text:
            await self._cdp_send(ws, "Input.dispatchKeyEvent", {
                "type": "char", "text": ch
            }, msg_id=mid)
            mid += 1
            await asyncio.sleep(0.02)

    async def _click_send(self, ws):
        """点击 GLM 发送按钮."""
        await self._cdp_send(ws, "Runtime.evaluate", {
            "expression": f'''
            const btn = document.querySelector('{self.SEND_BTN_SELECTOR}');
            if (btn) {{ btn.click(); "clicked"; }} else {{ "no_send_btn"; }}
            '''
        })

    async def _wait_for_response(self, ws, timeout: int = 60, check_interval: int = 3) -> str:
        """等待 AI 回复完成并提取内容."""
        last_text = ""
        stable_count = 0

        for i in range(timeout // check_interval):
            await asyncio.sleep(check_interval)

            # Build selector chain for response extraction
            selectors_js = ", ".join(f"'{s}'" for s in self.RESPONSE_SELECTORS)

            r = await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'''
                (() => {{
                    const selectors = [{selectors_js}];
                    let text = "";
                    for (const sel of selectors) {{
                        const els = document.querySelectorAll(sel);
                        if (els.length > 0) {{
                            // Get last element (the AI response)
                            const last = Array.from(els).slice(-1)[0];
                            text = last.textContent.trim();
                            if (text.length > 10) break;
                        }}
                    }}
                    // Fallback: get all large text blocks
                    if (!text || text.length < 10) {{
                        const ps = Array.from(document.querySelectorAll('p'))
                            .filter(e => e.textContent.trim().length > 20)
                            .map(e => e.textContent.trim());
                        text = ps.slice(-3).join('\\n\\n');
                    }}
                    return text;
                }})()
                '''
            }, msg_id=8000 + i)

            text = r.get("result", {}).get("result", {}).get("value", "")

            if text and text == last_text:
                stable_count += 1
                if stable_count >= 2:
                    return text
            else:
                stable_count = 0
                last_text = text

        return last_text

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        import websockets

        tab_id = None
        ws = None
        bws = None

        try:
            # 1. Create new tab
            import httpx
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
                browser_ws = resp.json()["webSocketDebuggerUrl"]

            bws = await self._ws_connect(browser_ws)
            await bws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {
                "url": self.GLM_URL
            }}))
            r = json.loads(await bws.recv())
            tab_id = r.get("result", {}).get("targetId", "")
            await bws.close()
            bws = None

            if not tab_id:
                logger.error("Failed to create GLM tab")
                return []

            # 2. Wait for page load
            await asyncio.sleep(8)

            # 3. Get tab WS URL
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/list")
                tabs = resp.json()

            ws_url = None
            for t in tabs:
                if t.get("id", "").startswith(tab_id):
                    ws_url = t["webSocketDebuggerUrl"]
                    break

            if not ws_url:
                logger.error("GLM tab WebSocket not found")
                return []

            ws = await self._ws_connect(ws_url)

            # 4. Wait for textarea
            if not await self._wait_for_selector(ws, self.TEXTAREA_SELECTOR):
                logger.error("GLM textarea not found")
                return []

            # 5. Focus and type
            await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{self.TEXTAREA_SELECTOR}").focus();"focused"'
            })
            await self._type_text(ws, request.query)

            # 6. Click send
            await self._click_send(ws)

            # 7. Wait for response
            logger.info(f"GLM: waiting for response to '{request.query[:30]}'")
            response_text = await self._wait_for_response(
                ws, timeout=request.timeout or 60, check_interval=3
            )

            if not response_text:
                logger.warning("GLM returned empty response")
                return []

            # 8. Build result
            return [SearchResult(
                title=f"GLM AI: {request.query[:50]}",
                url=self.GLM_URL,
                snippet=response_text[:500],
                source=self.name,
                score=1.0,
            )]

        except Exception as e:
            logger.error(f"GLM search error: {e}")
            return []

        finally:
            for w in [ws, bws]:
                try:
                    if w:
                        await w.close()
                except Exception:
                    pass
            if tab_id:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                        await client.get(
                            f"http://127.0.0.1:{self._cdp_port}/json/close/{tab_id}"
                        )
                except Exception:
                    pass
