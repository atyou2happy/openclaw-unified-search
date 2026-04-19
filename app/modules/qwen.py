"""Qwen search module — 通过 TabBitBrowser CDP 使用通义千问 AI 搜索.

技术方案：
- CDP 新建标签页访问 chat.qwen.ai（搜索模式）
- textarea 逐字符输入 + Enter 发送
- 等 markdown 元素数量稳定（回复完成信号）
- 提取 assistant 容器全文
"""

import asyncio
import json
import logging
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)
DEBUG_LOG = "/tmp/qwen-debug.log"


def _d(msg):
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{msg}\n")
            f.flush()
    except Exception:
        pass


class QwenModule(BaseSearchModule):
    name = "qwen"
    description = "通义千问 AI 搜索（TabBitBrowser CDP）"

    TEXTAREA_SELECTOR = "textarea.message-input-textarea"
    QWEN_URL = "https://chat.qwen.ai/?inputFeature=search"

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
        # Read responses until we get the one matching our id
        for _ in range(50):
            raw = await ws.recv()
            r = json.loads(raw)
            if r.get("id") == mid:
                if "error" in r:
                    _d(f"  CDP ERROR mid={mid}: {r['error']}")
                return r
            # CDP event, skip
            _d(f"  CDP skip event: {r.get('method','?')[:30]}")
        _d(f"  CDP TIMEOUT: never got response for mid={mid}")
        return {"error": "timeout waiting for CDP response"}

    async def _wait(self, ws, selector, timeout=20):
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

    async def _send_enter(self, ws):
        await self._cdp(ws, "Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13
        })
        await self._cdp(ws, "Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13
        })

    async def _wait_for_response(self, ws, timeout=120, interval=2) -> str:
        """等 markdown 元素数量稳定（= AI 回复完成），然后提取 assistant 全文."""
        last_mds = 0
        stable = 0
        for i in range(timeout // interval):
            await asyncio.sleep(interval)
            r = await self._cdp(ws, "Runtime.evaluate", {
                "expression": 'document.querySelectorAll("[class*=markdown]").length'
            }, mid=8000 + i)
            result_obj = r.get("result", {}).get("result", {})
            raw_val = result_obj.get("value", None)
            mds = int(raw_val) if raw_val is not None else -1
            _d(f"  poll[{i}]: mds={mds} raw_type={result_obj.get('type','?')} raw_val={repr(raw_val)[:50]} stable={stable}")
            if mds == last_mds and mds > 0:
                stable += 1
                if stable >= 3:
                    _d(f"  mds stabilized at {mds}")
                    break
            else:
                stable = 0
            last_mds = mds
        else:
            _d(f"  timeout, last mds={last_mds}")

        # Extract full assistant text
        r = await self._cdp(ws, "Runtime.evaluate", {
            "expression": """
            (() => {
                const asst = document.querySelector('[class*=assistant]');
                if (!asst) return '';
                return asst.textContent.trim();
            })()
            """
        })
        text = r.get("result", {}).get("result", {}).get("value", "")
        _d(f"  assistant text len: {len(text)}")
        return text

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        _d(f"=== Qwen search: {request.query[:30]} ===")
        tab_id = None
        ws = None
        bws = None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                resp = await c.get(f"http://127.0.0.1:{self._cdp_port}/json/version")
                browser_ws = resp.json()["webSocketDebuggerUrl"]

            bws = await self._ws_connect(browser_ws)
            await bws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": self.QWEN_URL}}))
            r = json.loads(await bws.recv())
            tab_id = r.get("result", {}).get("targetId", "")
            await bws.close()
            bws = None
            _d(f"tab_id: {tab_id}")

            if not tab_id:
                return []

            await asyncio.sleep(8)

            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                resp = await c.get(f"http://127.0.0.1:{self._cdp_port}/json/list")
                tabs = resp.json()

            ws_url = next((t["webSocketDebuggerUrl"] for t in tabs if t.get("id", "").startswith(tab_id)), None)
            if not ws_url:
                _d("ERROR: no ws_url")
                return []

            ws = await self._ws_connect(ws_url)

            ta_ok = await self._wait(ws, self.TEXTAREA_SELECTOR)
            if not ta_ok:
                ta_ok = await self._wait(ws, "textarea")
            _d(f"textarea: {ta_ok}")
            if not ta_ok:
                return []

            await self._cdp(ws, "Runtime.evaluate", {
                "expression": 'document.querySelector("textarea").focus();"ok"'
            })

            await self._type(ws, request.query)
            await asyncio.sleep(0.5)
            await self._send_enter(ws)

            logger.info(f"Qwen: waiting for response to '{request.query[:30]}'")
            text = await self._wait_for_response(ws, timeout=request.timeout or 120)
            _d(f"final response len: {len(text) if text else 0}")

            if not text:
                return []

            return [SearchResult(
                title=f"Qwen AI: {request.query[:50]}",
                url=self.QWEN_URL,
                snippet=text[:500],
                source=self.name,
                score=1.0,
            )]

        except Exception as e:
            _d(f"ERROR: {e}")
            import traceback
            _d(traceback.format_exc())
            return []
        finally:
            _d("=== cleanup ===")
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
