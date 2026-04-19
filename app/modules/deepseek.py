"""DeepSeek search module — 通过 TabBitBrowser CDP 使用 DeepSeek 聊天搜索.

技术方案：
- 通过 CDP 在 TabBitBrowser 中新建标签页
- 访问 chat.deepseek.com
- 逐字符输入查询（React 受控组件兼容）
- 等待 AI 回复完成
- 提取 ds-markdown 元素内容
"""

import asyncio
import json
import logging
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class DeepSeekModule(BaseSearchModule):
    name = "deepseek"
    description = "DeepSeek AI 搜索（TabBitBrowser CDP）"

    # DeepSeek selectors
    TEXTAREA_SELECTOR = "textarea"
    MARKDOWN_SELECTOR = '[class*="ds-markdown"]'
    THINKING_PREFIX = "嗯，"  # DeepSeek 思考过程标记

    def __init__(self):
        super().__init__()
        self._cdp_port = getattr(Config, 'TABBIT_CDP_PORT', 9222)

    async def health_check(self) -> bool:
        """检查 CDP 和 DeepSeek 页面是否可用."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
                return resp.status_code == 200
        except Exception:
            return False

    def reset_availability(self):
        """重置可用性缓存."""
        self._is_available = None

    async def _get_browser_ws(self) -> str:
        """获取浏览器 WebSocket URL."""
        import httpx
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
            data = resp.json()
            return data["webSocketDebuggerUrl"]

    async def _cdp_send(self, ws, method: str, params: dict = None, msg_id: int = 1) -> dict:
        """发送 CDP 命令并等待响应."""
        cmd = {"id": msg_id, "method": method}
        if params:
            cmd["params"] = params
        await ws.send(json.dumps(cmd))
        resp = json.loads(await ws.recv())
        return resp

    async def _wait_for_selector(self, ws, selector: str, timeout: int = 15) -> bool:
        """等待 DOM 选择器出现."""
        for _ in range(timeout):
            r = await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{selector}")?"ready":"waiting"'
            }, msg_id=9000 + _)
            if r.get("result", {}).get("result", {}).get("value") == "ready":
                return True
            await asyncio.sleep(1)
        return False

    async def _type_text(self, ws, text: str):
        """逐字符输入文本（兼容 React 受控组件）."""
        mid = 100
        for ch in text:
            await self._cdp_send(ws, "Input.dispatchKeyEvent", {
                "type": "char",
                "text": ch
            }, msg_id=mid)
            mid += 1
            # Small delay to avoid overwhelming
            await asyncio.sleep(0.02)

    async def _press_enter(self, ws):
        """发送 Enter 键."""
        for evt_type in ["keyDown", "keyUp"]:
            await self._cdp_send(ws, "Input.dispatchKeyEvent", {
                "type": evt_type,
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13
            }, msg_id=5000)

    async def _wait_for_response(self, ws, timeout: int = 60, check_interval: int = 3) -> str:
        """等待 AI 回复完成并提取内容."""
        last_text = ""
        stable_count = 0

        for i in range(timeout // check_interval):
            await asyncio.sleep(check_interval)

            r = await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'''
                (() => {{
                    const mds = Array.from(document.querySelectorAll('{self.MARKDOWN_SELECTOR}'));
                    // Filter out thinking process (starts with thinking markers)
                    const actual = mds.filter(e => !e.textContent.startsWith('{self.THINKING_PREFIX}'));
                    const text = actual.map(e => e.textContent.trim()).join('\\n\\n');
                    return text;
                }})()
                '''
            }, msg_id=8000 + i)

            text = r.get("result", {}).get("result", {}).get("value", "")

            if text and text == last_text:
                stable_count += 1
                if stable_count >= 2:  # Content stable for 2 checks
                    return text
            else:
                stable_count = 0
                last_text = text

        return last_text

    async def _ws_connect(self, url: str):
        """WebSocket 连接（绕过代理）."""
        import os
        import websockets
        # Clear proxy env vars for localhost connections
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

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """执行 DeepSeek 搜索."""
        import websockets

        tab_id = None
        ws = None
        bws = None

        try:
            # 1. Get browser WebSocket and create new tab
            browser_ws = await self._get_browser_ws()
            bws = await self._ws_connect(browser_ws)

            r = await self._cdp_send(bws, "Target.createTarget", {
                "url": "https://chat.deepseek.com/"
            })
            tab_id = r.get("result", {}).get("targetId", "")
            await bws.close()
            bws = None

            if not tab_id:
                logger.error("Failed to create DeepSeek tab")
                return []

            # 2. Wait for page load
            await asyncio.sleep(8)

            # 3. Get tab's WebSocket URL
            import httpx
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{self._cdp_port}/json/list")
                tabs = resp.json()

            ws_url = None
            for t in tabs:
                if t.get("id", "").startswith(tab_id):
                    ws_url = t["webSocketDebuggerUrl"]
                    break

            if not ws_url:
                logger.error("DeepSeek tab WebSocket not found")
                return []

            ws = await self._ws_connect(ws_url)

            # 4. Wait for textarea
            if not await self._wait_for_selector(ws, self.TEXTAREA_SELECTOR):
                logger.error("DeepSeek textarea not found")
                return []

            # 5. Focus and type
            await self._cdp_send(ws, "Runtime.evaluate", {
                "expression": f'document.querySelector("{self.TEXTAREA_SELECTOR}").focus();"focused"'
            })

            await self._type_text(ws, request.query)

            # 6. Send
            await self._press_enter(ws)

            # 7. Wait for response
            logger.info(f"DeepSeek: waiting for response to '{request.query[:30]}'")
            response_text = await self._wait_for_response(
                ws,
                timeout=request.timeout or 60,
                check_interval=3
            )

            if not response_text:
                logger.warning("DeepSeek returned empty response")
                return []

            # 8. Build result
            results = [SearchResult(
                title=f"DeepSeek AI: {request.query[:50]}",
                url=f"https://chat.deepseek.com/",
                snippet=response_text[:500],
                source=self.name,
                score=1.0,
            )]

            return results

        except Exception as e:
            logger.error(f"DeepSeek search error: {e}")
            return []

        finally:
            # Cleanup: close tab and WebSocket
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass
            if bws:
                try:
                    await bws.close()
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
