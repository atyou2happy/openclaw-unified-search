"""Search engine — 智能调度引擎 v3.

核心改进：
1. 意图路由 — 根据查询内容自动选择最相关模块
2. 智能选模块 — 不全跑，按意图选 3-5 个
3. 去重合并 — URL + 标题相似度去重
4. 质量重排 — AI答案 > 权威来源 > 普通结果
5. 快速返回 — FIRST_COMPLETED 模式，快模块先返回
6. 智能等待 — 根据质量要求动态调整等待时间
"""

import asyncio
import re
import time
from urllib.parse import urlparse
from app.models import SearchRequest, SearchResponse, SearchResult
from app.modules import get_all, get
from app.modules.base import BaseSearchModule
from app.cache import cache


# ============================================================
# 意图识别
# ============================================================


class QueryIntent:
    """查询意图识别"""

    # 模块能力标签 (v3)
    MODULE_PROFILES = {
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
        "phind": {
            "types": {"code", "tech"},
            "langs": {"en", "zh"},
            "speed": "slow",
            "quality": 0.9,
        },
        "tabbit": {
            "types": {"general", "research"},
            "langs": {"zh", "en"},
            "speed": "medium",
            "quality": 0.85,
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
    }

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

        # 默认：general
        if not intent["types"]:
            intent["types"].add("general")

        return intent

    @classmethod
    def select_modules(
        cls, intent: dict, available: dict[str, BaseSearchModule]
    ) -> list[str]:
        """根据意图选择最佳模块（返回模块名列表，按优先级排序）"""
        types = intent["types"]
        hints = intent["hints"]
        scores: dict[str, float] = {}

        for name, profile in cls.MODULE_PROFILES.items():
            if name not in available:
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

            # 质量加成
            score += profile["quality"] * 1.0

            # 速度惩罚（慢模块降低优先级，但不会排除）
            if profile["speed"] == "slow":
                score -= 0.5

            if score > 0:
                scores[name] = score

        # 按分数排序
        sorted_modules = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)

        # 取前 5 个（保证多样性）
        return sorted_modules[:5]


# ============================================================
# 去重 & 重排
# ============================================================


class ResultMerger:
    """结果去重与重排"""

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
        "phind.com",
    }

    # source 模块类型权重 (v3)
    SOURCE_WEIGHTS = {
        "metaso": 1.3,  # AI 深度答案
        "phind_answer": 1.3,  # AI 编程答案
        "tavily_answer": 1.3,  # AI 答案
        "perplexity": 1.3,  # AI 答案
        "perplexity_cite": 1.2,
        "searxng": 1.0,
        "tabbit": 1.0,
        "github": 1.1,
        "academic": 1.1,
        "wiki": 1.05,
        "you_ai": 1.15,
        "ddg": 0.95,
        "bing": 0.95,
        "bing_news": 0.95,
        "web": 0.9,
    }

    @classmethod
    def deduplicate(cls, results: list[SearchResult]) -> list[SearchResult]:
        """URL 去重 + 标题相似度去重"""
        seen_urls = set()
        seen_titles = set()
        deduped = []

        for r in results:
            # URL 去重
            url_key = cls._normalize_url(r.url)
            if url_key and url_key in seen_urls:
                continue
            if url_key:
                seen_urls.add(url_key)

            # 标题去重（简单前缀匹配）
            title_key = r.title.lower().strip()[:50]
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            deduped.append(r)

        return deduped

    @classmethod
    def rerank(cls, results: list[SearchResult]) -> list[SearchResult]:
        """质量重排"""
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
            # 去掉 trailing slash, www, query params
            key = f"{parsed.netloc.replace('www.', '')}{parsed.path.rstrip('/')}"
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
# 搜索引擎 v2
# ============================================================


class SearchEngine:
    """智能调度搜索引擎"""

    def __init__(self):
        self._modules: dict[str, BaseSearchModule] = {}

    def load_modules(self):
        from app.modules import get_all

        self._modules = get_all()

    async def search(self, request: SearchRequest) -> SearchResponse:
        """智能搜索 v3：意图识别 → 选模块 → 并行搜索(FIRST_COMPLETED) → 去重 → 重排"""
        start = time.time()

        # Check cache
        cached = cache.get(request)
        if cached is not None:
            return cached

        # 1. 意图识别
        intent = QueryIntent.detect(request.query, request.language)

        # 2. 选择模块
        if request.sources:
            selected = [s for s in request.sources if s in self._modules]
        else:
            selected = QueryIntent.select_modules(intent, self._modules)

        if not selected:
            return SearchResponse(
                query=request.query,
                elapsed=round(time.time() - start, 3),
                errors={"engine": "No matching modules found"},
            )

        # 3. 按速度排序 - 快的模块先查
        speed_order = [
            "wiki",
            "academic",
            "github",
            "searxng",
            "ddg",
            "brave",
            "bing",
            "tavily",
            "serper",
            "tabbit",
            "web",
        ]
        fast_modules = [m for m in speed_order if m in selected]
        slow_modules = [m for m in selected if m not in fast_modules]
        ordered = fast_modules + slow_modules

        # 4. 并行搜索 - FIRST_COMPLETED 模式
        all_results: list[SearchResult] = []
        sources_used: list[str] = []
        errors: dict[str, str] = {}
        min_results_needed = max(1, request.max_results // 2)

        for name in ordered:
            module = self._modules[name]
            try:
                results = await asyncio.wait_for(
                    self._safe_search(module, request),
                    timeout=min(request.timeout * 0.6, 15),
                )
                if results:
                    all_results.extend(results)
                    sources_used.append(name)
                    # 快速模块返回足够结果就继续
                    if len(all_results) >= min_results_needed:
                        break
            except asyncio.TimeoutError:
                errors[name] = "timeout"
            except Exception as e:
                errors[name] = str(e)

        # 5. 后台等待其他模块（不阻塞）
        for name in slow_modules:
            if name in sources_used:
                continue
            module = self._modules[name]
            try:
                results = await asyncio.wait_for(
                    self._safe_search(module, request),
                    timeout=max(5, request.timeout - sum(all_results)),
                )
                if results:
                    all_results.extend(results)
                    sources_used.append(name)
            except Exception:
                pass

        # 6. 去重
        all_results = ResultMerger.deduplicate(all_results)

        # 7. 重排
        all_results = ResultMerger.rerank(all_results)

        # 8. 截取
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
                }
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
            if not await module.is_available():
                return []
            return await module.search(request)
        except Exception:
            return []


# Global instance
engine = SearchEngine()
