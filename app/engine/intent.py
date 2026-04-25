"""Query intent detection and module selection."""

import re
from app.modules.base import BaseSearchModule

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
            "types": {"tech", "code", "trend"},  # v0.5.0: 只在技术相关查询触发
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
        "stackoverflow": {
            "types": {"code", "tech"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.90,  # 编程问题精准
        },
        "exa": {
            "types": {"general", "research", "knowledge"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.92,  # AI 语义搜索高质量
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

            # ⭐ tabbit + web + ddg 始终选中（v0.5.0: 保证基础搜索覆盖）
            if name == "tabbit":
                scores[name] = 999.0  # 最高优先级
                continue
            if name in ("web", "ddg", "searxng"):
                scores[name] = 500.0  # v0.5.0: 基础搜索始终入选
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


# RRF 融合 + 去重


