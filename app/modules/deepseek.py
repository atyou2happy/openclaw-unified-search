"""DeepSeek AI CDP module — 使用 cdp_pool 统一连接管理"""

import asyncio
import json
import logging
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule
from app.modules.cdp_pool import (
    is_cdp_available, get_cdp_ws_url, cdp_send_command,
    create_tab, close_tab
)

logger = logging.getLogger(__name__)


class DeepseekModule(BaseSearchModule):
    name = "deepseek"
    description = "DeepSeek AI 搜索（CDP）"
    MARKDOWN_SELECTOR = '[class*="markdown"]'
    THINKING_PREFIX = "嗯"
    TEXTAREA_SELECTOR = 'textarea'

    def __init__(self):
        super().__init__()
        self._is_available = None
        self._cdp_port = 9222

    async def health_check(self) -> bool:
        # Lazy check: always return True at startup, 
        # actual CDP availability checked at search time
        return True

    def reset_availability(self):
        super().__init__()
        self._is_available = None

    async def _wait_for_selector(self, ws_url: str, selector: str, timeout: int = 15) -> bool:
        for i in range(timeout):
            r = await cdp_send_command(ws_url, "Runtime.evaluate", {
                "expression": f'document.querySelector("{selector}")?"ready":"waiting"'
            }, timeout=10)
            if r and r.get("result", {}).get("result", {}).get("value") == "ready":
                return True
            await asyncio.sleep(1)
        return False

    async def _type_text(self, ws_url: str, text: str):
        for ch in text:
            await cdp_send_command(ws_url, "Input.dispatchKeyEvent", {
                "type": "char",
                "text": ch
            }, timeout=5)
            await asyncio.sleep(0.02)

    async def _press_enter(self, ws_url: str):
        for evt_type in ["keyDown", "keyUp"]:
            await cdp_send_command(ws_url, "Input.dispatchKeyEvent", {
                "type": evt_type,
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13
            }, timeout=5)

    async def _wait_for_response(self, ws_url: str, timeout: int = 60, check_interval: int = 3) -> str:
        last_text = ""
        stable_count = 0

        for i in range(timeout // check_interval):
            await asyncio.sleep(check_interval)

            r = await cdp_send_command(ws_url, "Runtime.evaluate", {
                "expression": f'''
                (() => {{
                    const mds = Array.from(document.querySelectorAll('{self.MARKDOWN_SELECTOR}'));
                    const actual = mds.filter(e => !e.textContent.startsWith('{self.THINKING_PREFIX}'));
                    const text = actual.map(e => e.textContent.trim()).join('\\n\\n');
                    return text;
                }})()
                '''
            }, timeout=15)

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

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        tab_id = None

        try:
            # 1. Create tab
            result = await create_tab("https://chat.deepseek.com/")
            if not result:
                return []
            tab_id, tab_ws_url = result

            # 2. Wait for page load
            await asyncio.sleep(8)

            # 3. Wait for textarea
            if not await self._wait_for_selector(tab_ws_url, self.TEXTAREA_SELECTOR):
                return []

            # 4. Focus and type
            await cdp_send_command(tab_ws_url, "Runtime.evaluate", {
                "expression": f'document.querySelector("{self.TEXTAREA_SELECTOR}").focus();"focused"'
            }, timeout=5)

            await self._type_text(tab_ws_url, request.query)

            # 5. Send
            await self._press_enter(tab_ws_url)

            # 6. Wait for response
            logger.info(f"DeepSeek: waiting for response to '{request.query[:30]}'")
            response_text = await self._wait_for_response(
                tab_ws_url,
                timeout=request.timeout if hasattr(request, 'timeout') and request.timeout else 60,
                check_interval=3
            )

            if not response_text:
                return []

            return [SearchResult(
                title=f"DeepSeek AI: {request.query[:50]}",
                url="https://chat.deepseek.com/",
                snippet=response_text[:500],
                source=self.name,
                score=1.0,
            )]

        except Exception as e:
            logger.error(f"DeepSeek search error: {e}")
            return []

        finally:
            if tab_id:
                await close_tab(tab_id)
