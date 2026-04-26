"""Query intent detection and module selection (v5)."""

import re
from app.modules.base import BaseSearchModule


class QueryIntent:
    """查询意图识别 v5 — 多信号融合 + 动态 tabbit + 教程意图"""

    # 模块能力标签 (v5 — 新增 tutorial 类型，动态 tabbit)
    MODULE_PROFILES = {
        "reddit": {
            "types": {"general", "social", "trend", "opinion", "discussion"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.82,
        },
        "hackernews": {
            "types": {"tech", "code", "trend"},
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
            "quality": 0.80,
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
            "quality": 0.95,
        },
        "web": {
            "types": {"general"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.70,
        },
        "jina": {
            "types": {"content"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.80,
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
            "types": {"doc", "tech", "tutorial"},
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
            "quality": 0.80,
        },
        "brave": {
            "types": {"general"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.80,
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
            "quality": 0.80,
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
            "quality": 0.80,
        },
        "you": {
            "types": {"general", "research"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.85,
        },
        "stackoverflow": {
            "types": {"code", "tech", "tutorial"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.90,
        },
        "exa": {
            "types": {"general", "research", "knowledge"},
            "langs": {"en", "zh"},
            "speed": "medium",
            "quality": 0.92,
        },
        "komo": {
            "types": {"general", "research"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.80,
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
        "crossref": {
            "types": {"academic", "research", "paper"},
            "langs": {"en"},
            "speed": "medium",
            "quality": 0.85,
        },
        "dblp": {
            "types": {"academic", "research", "paper"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.88,
        },
        "wikipedia": {
            "types": {"knowledge", "general", "research"},
            "langs": {"en", "zh"},
            "speed": "fast",
            "quality": 0.90,
        },
        "vane": {
            "types": {"general", "research", "knowledge", "academic"},
            "langs": {"en", "zh"},
            "speed": "slow",
            "quality": 0.95,
        },
        "devto": {
            "types": {"code", "tutorial", "general", "tech"},
            "langs": {"en"},
            "speed": "fast",
            "quality": 0.85,
        },
    }

    # CDP AI Agent 降级链 — 按搜索质量排序
    CDP_FALLBACK_CHAIN = [
        "tabbit",
        "deepseek",
        "gemini",
        "grok",
        "kimi",
        "glm",
        "qwen",
    ]

    @classmethod
    def detect(cls, query: str, language: str = "auto") -> dict:
        """分析查询意图，返回意图标签集合 (v5 — 新增 tutorial 意图)"""
        intent = {"types": set(), "hints": set()}

        q = query.lower().strip()

        # 编程意图 (v5: 新增中文编程关键词)
        code_keywords = [
            r"\b(code|coding|编程|代码|函数|function|class|api|sdk|debug|error|bug|issue|compile|runtime)",
            r"\b(python|java|javascript|typescript|rust|go|golang|c\+\+|ruby|swift|kotlin)",
            r"\b(pip|npm|yarn|cargo|maven|gradle|docker|kubernetes|k8s|git|github)",
            r"\b(react|vue|angular|django|flask|fastapi|spring|node\.?js)",
            r"\b(sql|nosql|redis|mongodb|postgres|mysql|sqlite)",
            # v5: 中文编程关键词
            r"(接口|框架|库|包|安装|部署|配置|编译|调试|变量|对象|继承|封装|多态|并发|异步|同步)",
            r"(模块|组件|服务|中间件|微服务|容器|集群|负载均衡|缓存|消息队列)",
        ]
        if any(re.search(p, q) for p in code_keywords):
            intent["types"].add("code")
            intent["hints"].add("tech")

        # 教程意图 (v5: 新增)
        tutorial_keywords = [
            r"\b(教程|tutorial|how to|怎么用|如何实现|how do i|guide|入门|指南|getting started)",
            r"\b(最佳实践|best practice|示例|example|demo|sample|模板|template)",
            r"\b(步骤|step|walkthrough|手把手|从零开始|from scratch|learn)",
            r"(用法|使用方法|配置方法|安装教程|使用指南)",
        ]
        if any(re.search(p, q) for p in tutorial_keywords):
            intent["types"].add("tutorial")
            intent["hints"].add("tutorial")

        # 学术意图
        academic_keywords = [
            r"\b(paper|论文|arxiv|research|研究|实验|experiment|模型|model|训练|training)",
            r"\b(算法|algorithm|神经网络|neural|transformer|attention|bert|gpt|llm|doi|citation)",
            r"\b(ieee|acm|引用|参考文献|bibliography)",
        ]
        if any(re.search(p, q) for p in academic_keywords):
            intent["types"].add("academic")
            intent["hints"].add("research")

        # 知识意图
        knowledge_keywords = [
            r"\b(是什么|什么是|what is|介绍|简介|overview|概念|定义|definition)",
            r"\b(百科|wiki|wikipedia|历史|原理|principle)",
            r"(区别|差异|对比|比较|vs\.?)",
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
        """根据意图选择最佳模块 (v5 — 动态 tabbit + 教程模块 + 智能数量)

        改进：
        - tabbit 动态优先级：不再固定999，基于可用性动态调整
        - 教程意图 → devto + stackoverflow + youtube + docs
        - 专业模块命中意图时获得更高基础分
        """
        types = intent["types"]
        hints = intent["hints"]
        scores: dict[str, float] = {}

        for name, profile in cls.MODULE_PROFILES.items():
            if name not in available:
                continue

            # v5: 基础搜索始终入选，但 tabbit 不再固定999
            if name in ("web", "ddg", "searxng"):
                scores[name] = 50.0  # 基础搜索始终入选
                continue

            score = 0.0

            # 类型匹配（核心）
            type_overlap = types & profile["types"]
            if type_overlap:
                # v5: 专业模块命中意图时基础分更高
                base_per_type = 4.0 if name not in ("web", "ddg", "searxng") else 3.0
                score += len(type_overlap) * base_per_type
            else:
                if "general" not in profile["types"]:
                    continue
                score += 0.5

            # 语言匹配
            if "chinese" in hints and "zh" in profile["langs"]:
                score += 1.5

            # 特殊加成
            if "repo_format" in hints and name == "github":
                score += 60.0
            if "url_given" in hints and name == "jina":
                score += 60.0

            # 代码查询特殊加成
            if "code" in types and name in ("github", "stackoverflow", "devto"):
                score += 20.0

            # v5: 教程查询特殊加成
            if "tutorial" in types and name in ("devto", "stackoverflow", "youtube", "docs"):
                score += 25.0

            # 社交查询特殊加成
            if "social" in types and name == "reddit":
                score += 25.0

            # 趋势查询特殊加成
            if "trend" in types and name in ("hackernews", "github_trending"):
                score += 30.0

            # 新闻/实时查询加成
            if "fresh" in hints and name in ("searxng", "bing", "brave", "serper"):
                score += 2.0

            # 短查询优化
            query_words = len(intent.get("_raw_query", "").split())
            if query_words <= 3 and name in ("web", "ddg") and "chinese" in hints:
                score += 2.0
            if query_words <= 3 and name == "wiki" and "chinese" in hints:
                score -= 1.0

            # 知识查询特殊加成
            if "knowledge" in types and name == "wikipedia":
                score += 3.0
            if "knowledge" in types and name == "wiki":
                score += 1.5

            # 学术查询特殊加成
            if "academic" in types and name in ("crossref", "dblp"):
                score += 3.0

            # 质量加成
            score += profile["quality"] * 1.0

            # 速度惩罚
            if profile["speed"] == "slow":
                score -= 0.5

            if score > 0:
                scores[name] = score

        # v5: tabbit 动态优先级 — 检查可用性
        if "tabbit" in available:
            module = available["tabbit"]
            # 如果模块之前标记为不可用，降低优先级
            if hasattr(module, "_available") and module._available is False:
                scores["tabbit"] = 5.0  # 很低但不完全排除
            else:
                scores["tabbit"] = 80.0  # 高优先级但不是999

        # 按分数排序
        sorted_modules = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)

        # v5: 自适应模块数量
        max_modules = 5
        if "research" in hints or "academic" in types:
            max_modules = 7
        elif "trend" in types:
            max_modules = 7
        elif "tutorial" in types:
            max_modules = 6  # v5: 教程查询需要多个源
        elif "code" in types:
            max_modules = 6
        elif types == {"general"}:
            max_modules = 4
        if "deep" in types:
            max_modules = 8

        return sorted_modules[:max_modules]
