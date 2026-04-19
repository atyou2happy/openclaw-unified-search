"""GLM AI 搜索（CDP） — 使用 cdp_pool 统一连接管理"""

import asyncio
import logging
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule
from app.modules.cdp_pool import (
    is_cdp_available, cdp_send_command, create_tab, close_tab
)

logger = logging.getLogger(__name__)


class GlmModule(BaseSearchModule):
    name = "glm"
    description = "GLM AI 搜索（CDP）"
    URL = "https://www.bigmodel.cn/trialcenter/modeltrial/text?modelCode=glm-5.1"
    TEXTAREA_SELECTOR = "textarea.el-textarea__inner"
    MARKDOWN_SELECTOR = '[class*="markdown"]'
    THINKING_PREFIX = "嗯"

    def __init__(self):
        self._is_available = None

    async def health_check(self) -> bool:
        if self._is_available is not None:
            return self._is_available
        self._is_available = await is_cdp_available()
        return self._is_available

    def reset_availability(self):
        self._is_available = None

    async def _wait_for_selector(self, ws_url, selector, timeout=15):
        for i in range(timeout):
            r = await cdp_send_command(ws_url, "Runtime.evaluate", {
                "expression": 'document.querySelector("' + selector + '")?"ready":"waiting"'
            }, timeout=10)
            if r and r.get("result", {}).get("result", {}).get("value") == "ready":
                return True
            await asyncio.sleep(1)
        return False

    async def _type_text(self, ws_url, text):
        for ch in text:
            await cdp_send_command(ws_url, "Input.dispatchKeyEvent", {
                "type": "char", "text": ch
            }, timeout=5)
            await asyncio.sleep(0.02)

    async def _press_enter(self, ws_url):
        for evt_type in ["keyDown", "keyUp"]:
            await cdp_send_command(ws_url, "Input.dispatchKeyEvent", {
                "type": evt_type, "key": "Enter",
                "code": "Enter", "windowsVirtualKeyCode": 13
            }, timeout=5)

    async def _wait_for_response(self, ws_url, timeout=60, check_interval=3):
        last_text = ""
        stable_count = 0
        md_sel = self.MARKDOWN_SELECTOR
        think_prefix = self.THINKING_PREFIX

        for i in range(timeout // check_interval):
            await asyncio.sleep(check_interval)
            expr = (
                "(() => {"
                "const mds = Array.from(document.querySelectorAll('" + md_sel + "'));"
                "const actual = mds.filter(e => !e.textContent.startsWith('" + think_prefix + "'));"
                "const text = actual.map(e => e.textContent.trim()).join('\\n\\n');"
                "return text;"
                "})()"
            )
            r = await cdp_send_command(ws_url, "Runtime.evaluate", {"expression": expr}, timeout=15)
            if not r:
                continue
            text = r.get("result", {}).get("result", {}).get("value", "")
            if text and text == last_text:
                stable_count += 1
                if stable_count >= 2:
                    return text
            else:
                stable_count = 0
                last_text = text
        return last_text

    async def search(self, request):
        tab_id = None
        try:
            result = await create_tab(self.URL)
            if not result:
                return []
            tab_id, tab_ws_url = result
            await asyncio.sleep(8)
            if not await self._wait_for_selector(tab_ws_url, self.TEXTAREA_SELECTOR):
                return []
            await cdp_send_command(tab_ws_url, "Runtime.evaluate", {
                "expression": 'document.querySelector("' + self.TEXTAREA_SELECTOR + '").focus();"focused"'
            }, timeout=5)
            await self._type_text(tab_ws_url, request.query)
            await self._press_enter(tab_ws_url)
            logger.info("glm: waiting for response")
            response_text = await self._wait_for_response(tab_ws_url)
            if not response_text:
                return []
            return [SearchResult(
                title="glm AI: " + request.query[:50],
                url=self.URL, snippet=response_text[:500],
                source=self.name, score=1.0,
            )]
        except Exception as e:
            logger.error("glm search error: " + str(e))
            return []
        finally:
            if tab_id:
                await close_tab(tab_id)
