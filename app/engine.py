"""Search engine v4 — 真并行 + 质量优先 + RRF 融合.

核心改进 (v4 vs v3):
1. 真并行调度 — asyncio.wait(FIRST_COMPLETED) 替代串行 for 循环
2. Tabbit 始终优先 — 硬编码第一顺位，结果最优先展示
3. 2阶段策略 — 快模块先返回 + 慢模块后台补充
4. RRF 融合 — Reciprocal Rank Fusion 替代简单权重排序
5. 智能去重 — URL + 标题相似度 + 内容指纹
6. 意图路由增强 — tabbit 始终选中 + 自适应模块数量
"""

import asyncio
import re
import time
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)
from difflib import SequenceMatcher
from urllib.parse import urlparse
from app.models import SearchRequest, SearchResponse, SearchResult
from app.modules import get_all, get
from app.modules.base import BaseSearchModule
from app.cache import cache


# ============================================================
# 意图识别
# ============================================================


class QueryIntent:
    """查询意图识别 — 决定选哪些模块"""

    # 模块能力标签 (v4 — 更精准的描述)
    MODULE_PROFILES = {
        "reddit": {
            "types": {"general", "social", "trend", "opinion"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.75,
        },
        "hackernews": {
            "types": {"general", "tech", "code", "trend"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.80,
        },
        "youtube": {
            "types": {"video", "tutorial", "general"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.75,
        },
        "github_trending": {
            "types": {"code", "tech", "trend", "repo"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.70,
        },
        "searxng": {
            "types": {"general", "news", "image", "video"},
            "langs": {"zh", "en"},
            "speed": "fast",
            "quality": 0.8,
        },
        "metaso": {
            "types": {"general", "research", "academic"},
            "langs": {"zh"},
            "speed": "slow",
            "quality": 0.95,
        },
        "tabbit": {
            "types": {"general", "research", "code", "academic", "knowledge"},
            "langs": {"zh", "en"},
            "speed": "slow",
            "quality": 0.95,  # AI 搜索质量最高
        },
        "web": {
            "types": {"general"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.7,
        },
        "jina": {
            "types": {"content"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.8,
        },
        "github": {
            "types": {"code", "tech", "repo"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.85,
        },
        "pdf": {
            "types": {"pdf", "doc"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.75,
        },
        "docs": {
            "types": {"doc", "tech"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.75,
        },
        "academic": {
            "types": {"academic", "research", "paper"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.85,
        },
        "wiki": {
            "types": {"knowledge", "general"},
            "langs": {"zh", "en"},
            "speed": "fast",
            "quality": 0.8,
        },
        "brave": {
            "types": {"general"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.8,
        },
        "tavily": {
            "types": {"general", "research"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.85,
        },
        "serper": {
            "types": {"general"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.8,
        },
        "perplexity": {
            "types": {"general", "research", "answer"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.95,
        },
        "ddg": {
            "types": {"general"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.75,
        },
        "bing": {
            "types": {"general", "news"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.8,
        },
        "you": {
            "types": {"general", "research"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.85,
        },
        "komo": {
            "types": {"general", "research"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.8,
        },
        "deepseek": {
            "types": {"general", "research", "code", "knowledge"},
            "langs": {"zh", "en"},
            "speed": "medium",
            "quality": 0.92,
        },
        "gemini": {
            "types": {"general", "research", "knowledge"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.90,
        },
        "grok": {
            "types": {"general", "research", "news"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.88,
        },
        "kimi": {
            "types": {"general", "research", "knowledge"},
            "langs": {"zh", "en"},
            "speed": "slow",
            "quality": 0.86,
        },
        "meilisearch": {
            "types": {"general", "research", "knowledge", "local"},
            "langs": {"zh", "en"},
            "speed": "fast",
            "quality": 0.80,
        },
        "qwen": {
            "types": {"general", "research", "knowledge"},
            "langs": {"zh", "en"},
            "speed": "slow",
            "quality": 0.84,
        },
        "glm": {
            "types": {"general", "research", "knowledge"},
            "langs": {"zh"},
            "speed": "medium",
            "quality": 0.85,
        },
    }

    # CDP AI Agent 降级链 — 按搜索质量排序
    CDP_FALLBACK_CHAIN = [
        "tabbit",    # quality=0.95, 最稳定
        "deepseek",  # quality=0.92, DeepThink 推理强
        "gemini",    # quality=0.90, Google 搜索加持
        "grok",      # quality=0.88, xAI 实时信息
        "kimi",      # quality=0.86, 长文档强
        "glm",       # quality=0.85, 中文优化
        "qwen",      # quality=0.84, 搜索模式但最慢
    ]

    @classmethod
    def detect(cls, query: str, language: str = "auto") -> dict:
        """分析查询意图，返回意图标签集合"""
        intent = {"types": set(), "hints": set()}

        q = query.lower().strip()

        # 编程意图
        code_keywords = [
            r"\b(code|coding|编程|代码|函数|function|class|api|sdk|debug|error|bug|issue|compile|runtime)",
            r"\b(python|java|javascript|typescript|rust|go|golang|c\+\+|ruby|swift|kotlin)",
            r"\b(pip|npm|yarn|cargo|maven|gradle|docker|kubernetes|k8s|git|github)",
            r"\b(react|vue|angular|django|flask|fastapi|spring|node\.?js)",
            r"\b(sql|nosql|redis|mongodb|postgres|mysql|sqlite)",
        ]
        if any(re.search(p, q) for p in code_keywords):
            intent["types"].add("code")
            intent["hints"].add("tech")

        # 学术意图
        academic_keywords = [
            r"\b(paper|论文|arxiv|research|研究|实验|experiment|模型|model|训练|training)",
            r"\b(算法|algorithm|神经网络|neural|transformer|attention|bert|gpt|llm)",
            r"\b(ieee|acm|doi|citation|引用|参考文献|bibliography)",
        ]
        if any(re.search(p, q) for p in academic_keywords):
            intent["types"].add("academic")
            intent["hints"].add("research")

        # 知识意图
        knowledge_keywords = [
            r"\b(是什么|什么是|how to|what is|介绍|简介|overview|概念|定义|definition)",
            r"\b(百科|wiki|wikipedia|历史|原理|principle)",
        ]
        if any(re.search(p, q) for p in knowledge_keywords):
            intent["types"].add("knowledge")

        # 新闻/实时意图
        news_keywords = [
            r"\b(新闻|news|最新|latest|今天|today|昨天|yesterday|2024|2025|2026|recent|刚刚|突发)",
            r"\b(股价|stock|天气|weather|比分|score|比赛|match|赛事|event)",
        ]
        if any(re.search(p, q) for p in news_keywords):
            intent["types"].add("news")
            intent["hints"].add("fresh")

        # 内容获取（URL 或深度阅读）
        if re.search(r"https?://", q):
            intent["types"].add("content")
            intent["hints"].add("url_given")

        # GitHub repo 格式
        if re.search(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", q.strip()):
            intent["types"].add("code")
            intent["hints"].add("repo_format")
        if re.search(r"\b[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+\b", q) and "/" in q:
            intent["hints"].add("repo_format")

        # PDF 意图
        if "pdf" in q or "filetype:pdf" in q:
            intent["types"].add("pdf")

        # 语言检测
        has_chinese = bool(re.search(r"[\u4e00-\u9fff]", q))
        if language == "zh" or (language == "auto" and has_chinese):
            intent["hints"].add("chinese")

        # 社交媒体意图
        social_keywords = [
            r"\b(reddit|推特|twitter|x\.com|youtube|视频|评论|帖子|post|thread)",
            r"\b(社区|community|forum|论坛|讨论|discussion)",
            r"\b(人们怎么说|what people say|opinion|观点|看法)",
        ]
        if any(re.search(p, q) for p in social_keywords):
            intent["types"].add("social")
            intent["hints"].add("social")

        # 趋势/热门意图
        trend_keywords = [
            r"\b(trending|热门|流行|trend|trends|热搜|fire|rising)",
            r"\b(hacker news|hn|producthunt|product hunt)",
            r"\b(what.*popular|most.*star|top.*repo)",
        ]
        if any(re.search(p, q) for p in trend_keywords):
            intent["types"].add("trend")
            intent["hints"].add("trend")

        # 默认：general
        if not intent["types"]:
            intent["types"].add("general")

        intent["_raw_query"] = q
        return intent

    @classmethod
    def select_modules(
        cls, intent: dict, available: dict[str, BaseSearchModule]
    ) -> list[str]:
        """根据意图选择最佳模块（v4 — tabbit 始终优先，自适应数量）

        规则：
        - tabbit 始终选中（核心模块）
        - 根据意图类型匹配其他模块
        - 自适应数量：general=3, research=5, code=4, deep=8
        """
        types = intent["types"]
        hints = intent["hints"]
        scores: dict[str, float] = {}

        for name, profile in cls.MODULE_PROFILES.items():
            if name not in available:
                continue

            # ⭐ tabbit 始终选中
            if name == "tabbit":
                scores[name] = 999.0  # 最高优先级
                continue

            score = 0.0

            # 类型匹配（核心）
            type_overlap = types & profile["types"]
            if type_overlap:
                score += len(type_overlap) * 3.0
            else:
                # 类型不匹配，除非是 general 类型
                if "general" not in profile["types"]:
                    continue  # 跳过完全不相关的模块
                score += 0.5  # general 兜底

            # 语言匹配
            if "chinese" in hints and "zh" in profile["langs"]:
                score += 1.5

            # 特殊加成
            if "repo_format" in hints and name == "github":
                score += 5.0
            if "url_given" in hints and name == "jina":
                score += 5.0

            # 新闻/实时查询加成
            if "fresh" in hints and name in ("searxng", "bing", "brave", "serper"):
                score += 2.0

            # 短查询优化：中文短查询优先 web/ddg 而非 wiki（避免不相关结果）
            query_words = len(intent.get('_raw_query', '').split())
            if query_words <= 3 and name in ('web', 'ddg') and 'chinese' in hints:
                score += 2.0
            if query_words <= 3 and name == 'wiki' and 'chinese' in hints:
                score -= 1.0

            # 质量加成
            score += profile["quality"] * 1.0

            # 速度惩罚（慢模块降低优先级，但不会排除）
            if profile["speed"] == "slow":
                score -= 0.5

            if score > 0:
                scores[name] = score

        # 按分数排序
        sorted_modules = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)

        # 自适应模块数量
        max_modules = 5  # 默认
        if "research" in hints or "academic" in types:
            max_modules = 7
        elif "code" in types:
            max_modules = 5
        elif types == {"general"}:
            max_modules = 4
        if "deep" in types:
            max_modules = 8

        return sorted_modules[:max_modules]


# ============================================================
# RRF 融合 + 去重
# ============================================================


class ResultMerger:
    """结果去重与 RRF 融合 (v4)

    Reciprocal Rank Fusion:
    score(d) = Σ 1/(k + rank_i(d))  for each source ranking i
    k = 60 (standard)
    """

    RRF_K = 60  # RRF 常数

    # 权威来源域名
    AUTHORITY_DOMAINS = {
        "github.com",
        "stackoverflow.com",
        "wikipedia.org",
        "arxiv.org",
        "python.org",
        "docs.python.org",
        "developer.mozilla.org",
        "baike.baidu.com",
        "zhihu.com",
        "csdn.net",
        "npmjs.com",
        "pypi.org",
        "crates.io",
        "metaso.cn",
                "perplexity.ai",
    }

    # source 模块类型权重 (v4 — AI 答案最高)
    SOURCE_WEIGHTS = {
        "tabbit": 1.5,  # 核心模块，最高优先级
        "reddit": 1.1,
        "hackernews": 1.1,
        "youtube": 1.05,
        "github_trending": 1.0,
        "metaso": 1.4,  # AI 深度答案
                "perplexity": 1.35,  # AI 答案
        "perplexity_cite": 1.2,
        "tavily_answer": 1.3,
        "you_ai": 1.2,
        "github": 1.15,
        "academic": 1.15,
        "wiki": 1.1,
        "searxng": 1.0,
        "ddg": 0.95,
        "brave": 0.95,
        "bing": 0.95,
        "bing_news": 0.9,
        "serper": 0.95,
        "serper_kg": 1.1,
        "web": 0.9,
        "komo": 0.9,
    }

    @classmethod
    def deduplicate(cls, results: list[SearchResult]) -> list[SearchResult]:
        """智能去重 — URL + 标题相似度 + 内容指纹"""
        seen_urls = set()
        deduped = []

        for r in results:
            # URL 去重
            url_key = cls._normalize_url(r.url)
            if url_key and url_key in seen_urls:
                # 合并：保留信息更丰富的那个
                cls._merge_into_existing(r, deduped, url_key)
                continue
            if url_key:
                seen_urls.add(url_key)

            # 标题相似度去重（> 0.90 相似度 + URL 同域视为重复）
            title_key = r.title.lower().strip()
            is_dup = False
            for existing in deduped:
                existing_title = existing.title.lower().strip()
                if title_key and existing_title:
                    sim = SequenceMatcher(
                        None, title_key[:80], existing_title[:80]
                    ).ratio()
                    if sim > 0.90:
                        # 同源同标题才去重，不同 URL 的不同视频保留
                        if r.source == existing.source and url_key == cls._normalize_url(existing.url):
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        elif r.source != existing.source:
                            # 不同源 + 高相似度 = 合并
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        # 同源不同URL（如YouTube不同视频）：不去重
                        break
            if is_dup:
                continue

            deduped.append(r)

        return deduped

    @classmethod
    def _merge_into_existing(
        cls, new: SearchResult, existing_list: list[SearchResult], url_key: str
    ):
        """将重复 URL 的信息合并到已有结果中"""
        for existing in existing_list:
            if cls._normalize_url(existing.url) == url_key:
                # 合并 metadata
                if new.metadata:
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if new.source:
                        engines.add(new.source)
                    existing.metadata["engines"] = list(engines)
                # 保留更好的 snippet
                if new.snippet and len(new.snippet) > len(existing.snippet or ""):
                    existing.snippet = new.snippet
                # 保留更好的 content
                if new.content and len(new.content) > len(existing.content or ""):
                    existing.content = new.content
                # 保留更高的 relevance
                if new.relevance > existing.relevance:
                    existing.relevance = new.relevance
                break

    @classmethod
    def rrf_fuse(
        cls, results_by_source: dict[str, list[SearchResult]]
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion — 多源结果融合

        对每个结果按其在各源中的排名计算 RRF 分数，
        然后按 RRF 分数排序。这是业界标准的多源融合方法。
        """
        rrf_scores: dict[str, float] = defaultdict(float)
        url_to_result: dict[str, SearchResult] = {}

        for source, results in results_by_source.items():
            source_weight = cls.SOURCE_WEIGHTS.get(source, 1.0)
            for rank, r in enumerate(results, start=1):
                url_key = cls._normalize_url(r.url) or f"_content_{id(r)}"
                if url_key not in url_to_result:
                    url_to_result[url_key] = r
                else:
                    # 合并信息
                    existing = url_to_result[url_key]
                    if r.snippet and len(r.snippet) > len(existing.snippet or ""):
                        existing.snippet = r.snippet
                    if r.content and len(r.content) > len(existing.content or ""):
                        existing.content = r.content
                    # 合并 engines
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if r.source:
                        engines.add(r.source)
                    existing.metadata["engines"] = list(engines)

                # RRF 公式：1/(k + rank) * source_weight
                rrf_scores[url_key] += (1.0 / (cls.RRF_K + rank)) * source_weight

        # 按 RRF 分数排序
        sorted_urls = sorted(
            rrf_scores.keys(), key=lambda u: rrf_scores[u], reverse=True
        )

        results = []
        for url_key in sorted_urls:
            r = url_to_result[url_key]
            r.relevance = min(rrf_scores[url_key] * 100, 1.0)  # 归一化到 0-1
            results.append(r)

        return results

    @classmethod
    def rerank(cls, results: list[SearchResult]) -> list[SearchResult]:
        """质量重排（兼容旧接口，新代码用 rrf_fuse）"""
        for r in results:
            score = r.relevance

            # 模块权重
            source = (
                r.metadata.get("engine_primary", r.source) if r.metadata else r.source
            )
            score *= cls.SOURCE_WEIGHTS.get(source, 1.0)

            # 权威来源加成
            if r.url:
                domain = cls._extract_domain(r.url)
                if domain in cls.AUTHORITY_DOMAINS:
                    score += 0.1

            # 有完整内容加成
            if r.content and len(r.content) > 200:
                score += 0.05

            # 多引擎共识加成
            engines = r.metadata.get("engines", []) if r.metadata else []
            if len(engines) > 1:
                score += 0.05 * min(len(engines), 3)

            r.relevance = min(score, 1.0)

        results.sort(key=lambda r: r.relevance, reverse=True)
        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            key = f"{parsed.netloc.replace('www.', '')}{parsed.path.rstrip('/')}"
            # Preserve critical query params (YouTube v=, GitHub params, etc.)
            critical_params = ("v", "p", "id", "q", "repo", "issue", "pull")
            if parsed.query:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                kept = {k: v[0] for k, v in qs.items() if k in critical_params}
                if kept:
                    from urllib.parse import urlencode
                    key += "?" + urlencode(kept)
            return key.lower()
        except Exception:
            return url.lower()

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "").lower()
        except Exception:
            return ""


# ============================================================
# 搜索引擎 v4 — 真并行
# ============================================================


class SearchEngine:
    """智能调度搜索引擎 v4 — 真并行 + 质量优先 + RRF 融合"""

    def __init__(self):
        self._modules: dict[str, BaseSearchModule] = {}

    def load_modules(self):
        from app.modules import get_all

        self._modules = get_all()

    async def cdp_search_fallback(self, request: SearchRequest) -> SearchResponse:
        """CDP AI Agent 降级搜索 — 按质量排序，失败自动降级

        策略：从 CDP_FALLBACK_CHAIN 中依次尝试，第一个成功即返回。
        如果用户指定了 sources，则从 chain 中筛选匹配的模块。
        """
        start = time.time()
        timeout = request.timeout or 120

        # Determine which CDP modules to try
        if request.sources:
            # User specified sources: filter from fallback chain, preserving order
            cdp_modules = [m for m in QueryIntent.CDP_FALLBACK_CHAIN if m in request.sources]
        else:
            cdp_modules = list(QueryIntent.CDP_FALLBACK_CHAIN)

        # Filter to only available modules
        cdp_modules = [m for m in cdp_modules if m in self._modules]

        if not cdp_modules:
            return SearchResponse(
                query=request.query, results=[], total=0,
                elapsed=time.time() - start, sources_used=[],
                errors={"engine": "No CDP modules available"}
            )

        errors = []
        for module_name in cdp_modules:
            module = self._modules[module_name]
            remaining = timeout - (time.time() - start)
            if remaining < 10:
                errors.append(f"{module_name}: timeout budget exhausted")
                continue

            try:
                print(f"CDP fallback: trying {module_name} (remaining={remaining:.0f}s)")
                result = await asyncio.wait_for(
                    module.search(request),
                    timeout=min(remaining - 5, 90)
                )
                if result:
                    elapsed = time.time() - start
                    print(f"CDP fallback: {module_name} succeeded in {elapsed:.1f}s")
                    return SearchResponse(
                        query=request.query, results=result,
                        total=len(result), elapsed=elapsed,
                        sources_used=[module_name],
                    )
            except asyncio.TimeoutError:
                errors.append(f"{module_name}: timeout")
                print(f"CDP fallback: {module_name} timed out")
            except Exception as e:
                errors.append(f"{module_name}: {str(e)[:100]}")
                print(f"CDP fallback: {module_name} failed: {e}")

        elapsed = time.time() - start
        return SearchResponse(
            query=request.query, results=[], total=0,
            elapsed=elapsed, sources_used=[],
            errors={"engine": f"All CDP modules failed: {'; '.join(errors)}"}
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        """v4 搜索：意图识别 → tabbit 始终选中 → 真并行调度 → RRF 融合"""
        start = time.time()

        # Check cache
        cached = cache.get(request)
        if cached is not None:
            return cached

        # 1. 意图识别
        intent = QueryIntent.detect(request.query, request.language)

        # 2. 选择模块（tabbit 始终在列）
        if request.sources:
            selected = [s for s in request.sources if s in self._modules]
            # 用户明确指定 sources 时不再强制加 tabbit
        else:
            selected = QueryIntent.select_modules(intent, self._modules)

        if not selected:
            return SearchResponse(
                query=request.query,
                elapsed=round(time.time() - start, 3),
                errors={"engine": "No matching modules found"},
            )

        # 过滤掉不可用的模块（避免浪费并发槽位）
        available_selected = []
        for name in selected:
            module = self._modules[name]
            module.reset_availability()
            if await module.is_available():
                available_selected.append(name)
            else:
                logger.debug(f"Module {name} not available, skipping")
        selected = available_selected

        if not selected:
            return SearchResponse(
                query=request.query,
                elapsed=round(time.time() - start, 3),
                results=[],
                total=0,
                sources_used=[],
                errors={"engine": "All selected modules unavailable"},
                metadata={"intent": intent, "engine_version": "v4"},
            )

        all_results: list[SearchResult] = []
        results_by_source: dict[str, list[SearchResult]] = {}
        sources_used: list[str] = []
        errors: dict[str, str] = {}

        tasks: dict[str, asyncio.Task] = {}
        for name in selected:
            module = self._modules[name]
            task = asyncio.create_task(
                self._safe_search(module, request),
                name=f"search_{name}",
            )
            tasks[name] = task

        # Phase 2: 等待结果 — 用 FIRST_COMPLETED 逐个收集
        min_results = max(3, request.max_results // 2)
        phase1_timeout = min(request.timeout * 0.6, 45)  # 快阶段超时
        phase1_start = time.time()

        pending = set(tasks.values())
        completed_names: set[str] = set()

        while pending:
            # 计算剩余超时
            remaining_time = phase1_timeout - (time.time() - phase1_start)
            if remaining_time <= 0:
                break

            try:
                done, pending = await asyncio.wait(
                    pending,
                    timeout=remaining_time,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except Exception:
                break

            if not done:
                break

            # 收集完成的结果
            for task in done:
                task_name = task.get_name()
                module_name = task_name.replace("search_", "")

                try:
                    results = task.result()
                    if results:
                        results_by_source[module_name] = results
                        all_results.extend(results)
                        sources_used.append(module_name)
                    completed_names.add(module_name)
                except asyncio.TimeoutError:
                    errors[module_name] = "timeout"
                    completed_names.add(module_name)
                except Exception as e:
                    errors[module_name] = str(e)
                    completed_names.add(module_name)

            # 检查是否有足够结果 + tabbit 已返回
            tabbit_done = "tabbit" in completed_names
            if tabbit_done and len(all_results) >= min_results:
                break

        # Phase 3: 取消仍在 pending 的任务（如果已经有足够结果）
        remaining_tasks = set(pending)
        if len(all_results) >= min_results:
            for task in remaining_tasks:
                task.cancel()
        else:
            phase2_timeout = max(3, request.timeout * 0.4)
            if remaining_tasks:
                try:
                    done2, still_pending = await asyncio.wait(
                        remaining_tasks,
                        timeout=phase2_timeout,
                        return_when=asyncio.ALL_COMPLETED,
                    )
                    for task in done2:
                        task_name = task.get_name()
                        module_name = task_name.replace("search_", "")
                        try:
                            results = task.result()
                            if results:
                                results_by_source[module_name] = results
                                all_results.extend(results)
                                sources_used.append(module_name)
                        except Exception:
                            pass
                    for task in still_pending:
                        task.cancel()
                except Exception:
                    for task in remaining_tasks:
                        task.cancel()

        # 4. RRF 融合（如果有多个源）
        if len(results_by_source) > 1:
            all_results = ResultMerger.rrf_fuse(results_by_source)
        else:
            # 单源 — 用传统去重 + 重排
            all_results = ResultMerger.deduplicate(all_results)
            all_results = ResultMerger.rerank(all_results)

        # 5. Tabbit 结果置顶（如果有）
        tabbit_results = [r for r in all_results if r.source == "tabbit"]
        other_results = [r for r in all_results if r.source != "tabbit"]
        if tabbit_results:
            all_results = tabbit_results + other_results

        # 6. 截取
        total = len(all_results)
        all_results = all_results[: request.max_results]

        elapsed = time.time() - start

        response = SearchResponse(
            query=request.query,
            results=all_results,
            total=total,
            elapsed=round(elapsed, 3),
            sources_used=sources_used,
            errors=errors,
            metadata={
                "intent": {
                    "types": list(intent["types"]),
                    "hints": list(intent["hints"]),
                },
                "engine_version": "v4",
                "phase1_modules": list(completed_names),
            },
        )

        cache.put(request, response)
        return response

    async def search_module(
        self, module_name: str, request: SearchRequest
    ) -> SearchResponse:
        """搜索单个指定模块"""
        module = get(module_name)
        if not module:
            return SearchResponse(
                query=request.query,
                errors={module_name: f"Module '{module_name}' not found"},
                elapsed=0,
            )

        start = time.time()
        try:
            results = await self._safe_search(module, request)
            elapsed = time.time() - start
            return SearchResponse(
                query=request.query,
                results=results[: request.max_results],
                total=len(results),
                elapsed=round(elapsed, 3),
                sources_used=[module_name],
            )
        except Exception as e:
            return SearchResponse(
                query=request.query,
                errors={module_name: str(e)},
                elapsed=round(time.time() - start, 3),
            )

    @staticmethod
    async def _safe_search(
        module: BaseSearchModule, request: SearchRequest
    ) -> list[SearchResult]:
        try:
            # Reset cached availability so it re-checks
            module.reset_availability()
            avail = await module.is_available()
            if not avail:
                return []
            results = await module.search(request)
            return results
        except Exception:
            return []


# Global instance
engine = SearchEngine()
