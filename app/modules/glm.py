"""GLM AI 搜索（CDP） — 使用 cdp_pool 统一连接管理
默认开启: 深度思考 + 联网搜索

GLM-5.1 深度思考: button.thinking-status (class含enabled=已开启, name=disabled=可关闭)
联网搜索: li.tool-list-item[data-sensors-click] name="tools_web_search"
"""

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
    description = "GLM AI 搜索（CDP，深度思考+联网搜索）"
    URL = "https://www.bigmodel.cn/trialcenter/modeltrial/text?modelCode=glm-5.1"
    TEXTAREA_SELECTOR = "textarea.el-textarea__inner"
    MARKDOWN_SELECTOR = '[class*="markdown"]'
    THINKING_PREFIX = "嗯"

    def __init__(self):
        super().__init__()
        self._is_available = None

    async def health_check(self) -> bool:
        return True

    def reset_availability(self):
        super().__init__()
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

    async def _enable_features(self, ws_url):
        """开启深度思考 + 联网搜索

        深度思考: button.thinking-status — 如果不含'enabled'类则需要点击开启
        联网搜索: 需要先展开工具面板，再点击联网搜索的 li 项
        """
        # 1. 深度思考
        r = await cdp_send_command(ws_url, "Runtime.evaluate", {
            "expression": (
                "(() => {"
                "const btn = document.querySelector('.thinking-status');"
                "if (btn && !btn.classList.contains('enabled')) {"
                "btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));"
                "return 'clicked';"
                "}"
                "return btn ? 'already_enabled' : 'not_found';"
                "})()"
            )
        }, timeout=10)

        # 2. 联网搜索 — 点击 tools-setting 区域触发 popover，再点击"联网搜索"选项
        # 先点击工具区域展开
        await cdp_send_command(ws_url, "Runtime.evaluate", {
            "expression": (
                "(() => {"
                "const toolArea = document.querySelector('.tools-setting');"
                "if (toolArea) {"
                "toolArea.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));"
                "return 'opened';"
                "}"
                "return 'not_found';"
                "})()"
            )
        }, timeout=10)
        await asyncio.sleep(0.8)

        # 点击联网搜索列表项
        await cdp_send_command(ws_url, "Runtime.evaluate", {
            "expression": (
                "(() => {"
                "const items = document.querySelectorAll('.tool-list-item');"
                "for (const item of items) {"
                "const name = item.getAttribute('name');"
                "if (name === 'tools_web_search') {"
                "item.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));"
                "return 'clicked';"
                "}"
                "}"
                "return 'not_found';"
                "})()"
            )
        }, timeout=10)
        await asyncio.sleep(0.5)

        logger.info("GLM: 深度思考+联网搜索已开启")

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

            # 开启深度思考 + 联网搜索
            await self._enable_features(tab_ws_url)

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
