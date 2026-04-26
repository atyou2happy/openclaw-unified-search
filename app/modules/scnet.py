"""SCNet AI Chatbot CDP module — 超算互联网 AI 助手.

https://www.scnet.cn/ui/chatbot/
默认模型: Qwen3-235B-A22B
默认开启: 深度思考 + 联网搜索

⚠️ 必须使用单个持久 WebSocket 连接。
⚠️ 不用 cdp_pool.cdp_send_command（每次新建连接导致页面刷新）。
"""

import asyncio
import json
import logging
import re

import httpx
import websockets

from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)

CHATBOT_URL = "https://www.scnet.cn/ui/chatbot/"
CDP_BASE = "http://127.0.0.1:9222"

TEXTAREA_SEL = 'textarea[placeholder="提出你想要知道的问题"]'
SEND_BTN_SEL = "button.send-btn"
REPLY_SEL = ".msg-content-inner"
THINKING_SEL = ".thinking-box"
NETWORK_SEL = ".network-box"

# 思考过程的典型开头模式
_THINKING_PATTERNS = [
    r"^好的，用户问的是",
    r"^好的，用户想",
    r"^我需要",
    r"^首先，[我咱]",
    r"^让我[想想来看分析一下]+",
    r"^用户可能",
    r"^用户[的问题][没可]有",
    r"^接下来[，我]",
    r"^需要[确检注意]",
    r"^综合[以这]",
    r"^所以[，我]",
    r"^然后[，我]",
    r"^最后[，我确保]",
    r"^是否需要",
    r"^另外，?搜索",
    r"^还要注意",
    r"^还需[要考]",
    r"^检查搜索",
    r"^根据[提供搜]",
    r"^确保回答",
    r"^由于用户",
]

# 思考过程结束标志 — 出现这些模式说明开始正式回答
_ANSWER_START_PATTERNS = [
    # Markdown 标题
    r"^#{1,4}\s",
    # 编号列表
    r"^[一二三四五六七八九十]+[、.]",
    r"^\d+[\.、)]\s",
    # 定义/概念开头
    r"^(RAG|AI|API|GPU|CPU|Python|JavaScript|量子计算)",
    # 核心特征/要点
    r"^核心[特要原]",
    r"^[主其优缺][要点势]",
    # 完整陈述句开头（非"我"/"用户"）
    r"^[A-Z\u4e00-\u9fff][^，。]*?(?:是|指|为|有)",
]


def _strip_thinking(text: str) -> str:
    """去除深度思考过程的内心独白，只保留最终答案。
    
    策略：
    1. 按段落分割
    2. 跳过思考过程段落（以特定模式开头）
    3. 遇到答案模式时开始收集
    """
    if not text:
        return text
    
    paragraphs = text.split('\n')
    answer_lines = []
    in_thinking = True
    
    for line in paragraphs:
        stripped = line.strip()
        if not stripped:
            if not in_thinking:
                answer_lines.append('')
            continue
        
        if in_thinking:
            # 检查是否匹配思考过程模式
            is_thinking = any(re.match(p, stripped) for p in _THINKING_PATTERNS)
            # 检查是否匹配答案开始模式
            is_answer = any(re.match(p, stripped) for p in _ANSWER_START_PATTERNS)
            
            if is_answer:
                in_thinking = False
                answer_lines.append(stripped)
            elif not is_thinking:
                # 既不是思考也不是明确答案开头 — 可能是过渡段
                # 如果内容较长且包含实质信息，保留
                if len(stripped) > 50 and not stripped.startswith(('我', '用户', '需要', '首先', '接下来', '然后')):
                    in_thinking = False
                    answer_lines.append(stripped)
        else:
            answer_lines.append(stripped)
    
    # 如果没提取到任何答案
    result = '\n'.join(answer_lines).strip()
    if result:
        return result
    
    # 兜底：全文都是思考过程
    # 尝试找最后一段不含思考关键词的内容
    skip_prefixes = ('好的，', '用户', '我需要', '首先', '接下来', '然后', '最后', '综合', '另外', '还要', '是否', '检查', '需要', '由于', '确保')
    for line in reversed(paragraphs):
        stripped = line.strip()
        if len(stripped) > 15 and not any(stripped.startswith(p) for p in skip_prefixes):
            return stripped
    
    # 真的全是思考过程 — 标记低质量
    return '[SCNet 回复质量不佳，思考过程未收敛]'


def _score_relevance(text: str) -> float:
    """根据回复质量动态评分 relevance（0.3-0.9）。
    
    降级条件：
    - 回复太短（<50字）→ 降低
    - 包含"无法提供实时"等拒绝语句 → 大幅降低
    - 包含大量"用户"自称 → 中度降低（思考过程混入）
    - 正常结构化回答 → 0.85
    - 有明确引用来源 → 0.9
    """
    if not text:
        return 0.3
    
    score = 0.85
    
    # 短回复降级
    if len(text) < 50:
        score -= 0.3
    elif len(text) < 100:
        score -= 0.15
    
    # 拒绝/无法回答降级
    refusal_phrases = [
        '无法提供实时', '无法获取实时', '建议您查看',
        '我无法提供', '无法访问', '没有找到相关',
        '暂无相关数据', '无法确定',
    ]
    for phrase in refusal_phrases:
        if phrase in text:
            score -= 0.25
            break
    
    # 思考过程残留检测（清理后仍有的）
    user_refs = text.count('用户')
    if user_refs > 3:
        score -= 0.1 * min(user_refs - 3, 3)
    
    # 结构化回答加分
    if any(c in text for c in ['#', '一、', '1.', '•', '- ']):
        score = min(score + 0.05, 0.9)
    
    return round(max(0.3, min(0.9, score)), 2)


# 递增 msg_id 避免重复
_next_id = 100


def _new_id():
    global _next_id
    _next_id += 1
    return _next_id


async def _send_and_recv(ws, method, params=None, timeout=15):
    """发送 CDP 命令，等待匹配 id 的响应。忽略事件消息。"""
    msg_id = _new_id()
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(remaining, 0.1))
            msg = json.loads(raw)
            if msg.get("id") == msg_id:
                return msg
            # else: event message, ignore
        except asyncio.TimeoutError:
            return None


def _extract_value(cdp_result):
    """从 Runtime.evaluate 结果提取 value。"""
    if not cdp_result:
        return ""
    return cdp_result.get("result", {}).get("result", {}).get("value", "")


class ScnetModule(BaseSearchModule):
    name = "scnet"
    description = "超算互联网 AI 助手（SCNet Chatbot，深度思考+联网，CDP）"

    def __init__(self):
        super().__init__()

    async def health_check(self) -> bool:
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        tab_id = None
        try:
            # 1. 创建新 tab
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                r = await client.put(f"{CDP_BASE}/json/new")
                data = r.json()
                tab_id = data["id"]
                tab_ws = data["webSocketDebuggerUrl"]

            # 2. 单个持久 WebSocket 连接
            async with websockets.connect(
                tab_ws, max_size=10 * 1024 * 1024, open_timeout=10
            ) as ws:
                # 3. Page.enable + navigate + drain events
                await _send_and_recv(ws, "Page.enable", timeout=10)
                await _send_and_recv(ws, "Page.navigate", {"url": CHATBOT_URL}, timeout=15)
                for _ in range(10):
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=1)
                    except asyncio.TimeoutError:
                        break
                await asyncio.sleep(5)

                # 4. 等待 textarea（最多 25s）
                found = False
                for _ in range(25):
                    await asyncio.sleep(1)
                    r = await _send_and_recv(ws, "Runtime.evaluate", {
                        "expression": f"document.querySelector('{TEXTAREA_SEL}')?'ready':'no'"
                    })
                    if _extract_value(r) == "ready":
                        found = True
                        break
                if not found:
                    logger.warning("SCNet: textarea not found")
                    return []

                # 5. 开启深度思考 + 联网搜索
                for sel in (THINKING_SEL, NETWORK_SEL):
                    await _send_and_recv(ws, "Runtime.evaluate", {
                        "expression": (
                            f"(() => {{"
                            f"const el = document.querySelector('{sel}');"
                            f"if (el && !el.classList.contains('active')) {{"
                            f"el.dispatchEvent(new MouseEvent('click', {{bubbles:true, cancelable:true}}));"
                            f"return 'clicked';"
                            f"}}"
                            f"return 'already';"
                            f"}})()"
                        )
                    }, timeout=10)
                    for _ in range(5):
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=0.5)
                        except asyncio.TimeoutError:
                            break
                    await asyncio.sleep(1)
                logger.info("SCNet: 深度思考+联网已开启")

                # 6. 输入 + 发送
                escaped = (
                    request.query
                    .replace("\\", "\\\\")
                    .replace("'", "\\'")
                    .replace("\n", "\\n")
                )
                r = await _send_and_recv(ws, "Runtime.evaluate", {
                    "expression": (
                        f"(() => {{"
                        f"const ta = document.querySelector('{TEXTAREA_SEL}');"
                        f"ta.focus();"
                        f"Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set.call(ta,'{escaped}');"
                        f"ta.dispatchEvent(new Event('input',{{bubbles:true}}));"
                        f"document.querySelector('{SEND_BTN_SEL}').click();"
                        f"return 'sent';"
                        f"}})()"
                    )
                }, timeout=10)
                if _extract_value(r) != "sent":
                    logger.warning(f"SCNet: send failed: {_extract_value(r)}")
                    return []

                # 7. 等待回复（稳定性检测）
                timeout = getattr(request, "timeout", 60) or 60
                logger.info(f"SCNet: waiting for response to '{request.query[:30]}'")
                last_text = ""
                stable_count = 0
                for _ in range(timeout // 3):
                    await asyncio.sleep(3)
                    r = await _send_and_recv(ws, "Runtime.evaluate", {
                        "expression": (
                            f"(() => {{"
                            f"const ms = document.querySelectorAll('{REPLY_SEL}');"
                            f"if (!ms.length) return '';"
                            f"return ms[ms.length-1].textContent.trim();"
                            f"}})()"
                        )
                    }, timeout=15)
                    text = _extract_value(r)
                    if text and text == last_text:
                        stable_count += 1
                        if stable_count >= 2:
                            return self._build_result(request.query, text)
                    else:
                        stable_count = 0
                        last_text = text

                if last_text:
                    return self._build_result(request.query, last_text)
                return []

        except Exception as e:
            logger.error(f"SCNet search error: {e}")
            return []

        finally:
            if tab_id:
                try:
                    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                        await client.get(f"{CDP_BASE}/json/close/{tab_id}")
                except Exception:
                    pass

    def _build_result(self, query: str, raw_text: str) -> list[SearchResult]:
        """构建搜索结果：去除思考过程 + 质量评分。"""
        # 去除思考过程
        clean_text = _strip_thinking(raw_text)
        # 动态评分
        relevance = _score_relevance(clean_text)
        
        logger.info(f"SCNet: raw={len(raw_text)}chars, clean={len(clean_text)}chars, relevance={relevance}")
        
        return [SearchResult(
            title=f"SCNet AI: {query[:50]}",
            url=CHATBOT_URL,
            snippet=clean_text[:500],
            content=clean_text,
            source=self.name,
            relevance=relevance,
            metadata={
                "type": "ai_answer",
                "model": "Qwen3-235B-A22B",
                "thinking": True,
                "web_search": True,
                "raw_length": len(raw_text),
                "clean_length": len(clean_text),
            },
        )]
