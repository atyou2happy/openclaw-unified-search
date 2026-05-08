"""Query enhancement engine — v2.0 spell correction, expansion, rewriting.

Inspired by:
- SearXNG: query language detection + autocomplete
- Perplexica: query rewriting for multi-source search
- Elasticsearch: term-level query expansion

Design principles:
- Zero external dependencies (no LLM, no embedding model)
- Pure heuristic + statistical approach
- Sub-millisecond processing time
"""

import re
import unicodedata
from collections import Counter
from urllib.parse import quote

from app.models import QueryAnalysis


class QueryEnhancer:
    """Query enhancement — spell correction, expansion, cross-language rewrite."""

    # Common misspellings map (Chinese + English tech terms)
    _COMMON_TYPOS: dict[str, str] = {
        # English tech terms
        "pythn": "python",
        "javscript": "javascript",
        "javascrip": "javascript",
        "typescrip": "typescript",
        "dockr": "docker",
        "kuberentes": "kubernetes",
        "kubernates": "kubernetes",
        "reactjs": "react",
        "vuejs": "vue",
        "angluar": "angular",
        "fasapi": "fastapi",
        "djang": "django",
        "flsk": "flask",
        "postgress": "postgresql",
        "postgre": "postgresql",
        "mongo": "mongodb",
        "redsi": "redis",
        "sarch": "search",
        "serach": "search",
        "mchine": "machine",
        "lerning": "learning",
        "deeplearning": "deep learning",
        "neuralnetwork": "neural network",
        "transforme": "transformer",
        "atention": "attention",
        "llms": "llm",
        "ragh": "rag",
        "fintuning": "finetuning",
        "finetunnig": "finetuning",
        "deploymnet": "deployment",
        "contianer": "container",
        "orchstrator": "orchestrator",
        "micorservice": "microservice",
        "midleware": "middleware",
        "laodbalancer": "loadbalancer",
        "concurren": "concurrent",
        "asynchrnous": "asynchronous",
        "recrusive": "recursive",
        "algoritm": "algorithm",
        "funciton": "function",
        "varible": "variable",
        "databse": "database",
        "chache": "cache",
        "authenication": "authentication",
        "authroization": "authorization",
        "encrytion": "encryption",
    }

    # Synonym expansion map for search quality
    _SYNONYMS: dict[str, list[str]] = {
        # Tech synonyms
        "k8s": ["kubernetes"],
        "kubernetes": ["k8s"],
        "ai": ["artificial intelligence", "machine learning"],
        "ml": ["machine learning"],
        "dl": ["deep learning"],
        "nlp": ["natural language processing"],
        "llm": ["large language model", "gpt", "chatgpt"],
        "rag": ["retrieval augmented generation"],
        "api": ["application programming interface", "rest", "graphql"],
        "db": ["database"],
        "sql": ["structured query language"],
        "os": ["operating system"],
        "cli": ["command line interface", "terminal"],
        "ide": ["integrated development environment"],
        "ci/cd": ["continuous integration", "continuous deployment", "pipeline"],
        "devops": ["development operations", "sre", "platform engineering"],
        "微服务": ["microservice"],
        "microservice": ["微服务"],
        "分布式": ["distributed"],
        "容器化": ["containerization", "docker"],
        "负载均衡": ["load balancing", "loadbalancer"],
        "消息队列": ["message queue", "mq", "kafka", "rabbitmq"],
        # Academic synonyms
        "论文": ["paper", "arxiv"],
        "paper": ["论文", "arxiv"],
        "neural network": ["神经网络"],
        "神经网络": ["neural network"],
        "transformer": ["注意力机制", "attention"],
        "注意力机制": ["transformer", "attention"],
        # v7: Finance synonyms
        "股票": ["stock", "equity", "A股", "shares"],
        "stock": ["股票", "equity"],
        "涨停": ["limit up", "涨停板"],
        "跌停": ["limit down"],
        "量化": ["quantitative", "quant"],
        "fund": ["基金", "mutual fund"],
        "基金": ["fund"],
        "期货": ["futures"],
        "期权": ["options"],
        "估值": ["valuation", "DCF"],
        "市盈率": ["PE ratio", "price earnings"],
        "财报": ["earnings report", "financial report"],
        # v7: Extended tech synonyms
        "gpt": ["chatgpt", "openai"],
        "claude": ["anthropic"],
        "gemini": ["google ai"],
        "prompt": ["提示词"],
        "提示词": ["prompt"],
        "微调": ["finetuning", "fine-tuning"],
        "finetuning": ["微调", "fine-tuning"],
        "rlhf": ["reinforcement learning from human feedback"],
        "dpo": ["direct preference optimization"],
        "sft": ["supervised finetuning"],
        "embedding": ["向量", "vector", "embedding"],
        "向量数据库": ["vector database", "vectordb"],
        "向量": ["embedding", "vector"],
        "agent": ["智能体"],
        "智能体": ["agent", "AI agent"],
        "mcp": ["model context protocol"],
        "copilot": ["AI assistant", "编程助手"],
        "编程助手": ["copilot", "AI assistant"],
        "低代码": ["low-code", "no-code"],
        "云计算": ["cloud computing"],
        "edge computing": ["边缘计算"],
        "边缘计算": ["edge computing"],
        "serverless": ["无服务器"],
        "无服务器": ["serverless"],
        "graphql": ["graph query language"],
        "rest": ["restful api"],
        "grpc": ["grpc", "rpc"],
    }

    # Chinese-English cross-language mapping (for query rewriting)
    _CROSS_LANG: dict[str, list[str]] = {
        # Chinese -> English
        "人工智能": ["artificial intelligence", "AI"],
        "机器学习": ["machine learning"],
        "深度学习": ["deep learning"],
        "自然语言处理": ["natural language processing", "NLP"],
        "大模型": ["large language model", "LLM"],
        "搜索引擎": ["search engine"],
        "推荐系统": ["recommendation system", "recommender"],
        "知识图谱": ["knowledge graph"],
        "数据库": ["database"],
        "前端": ["frontend", "frontend development"],
        "后端": ["backend", "backend development"],
        "全栈": ["fullstack"],
        "算法": ["algorithm"],
        "数据结构": ["data structure"],
        "设计模式": ["design pattern"],
        "并发编程": ["concurrent programming"],
        "异步编程": ["async programming"],
        "函数式编程": ["functional programming"],
        "面向对象": ["object oriented", "OOP"],
        "测试": ["testing", "unit test"],
        "部署": ["deployment", "deploy"],
        "配置": ["configuration", "config"],
        "性能优化": ["performance optimization"],
        "安全": ["security"],
        "开源": ["open source"],
        # v7: Finance
        "涨停": ["limit up"],
        "跌停": ["limit down"],
        "选股": ["stock picking", "stock selection"],
        "投资": ["investment", "investing"],
        "牛市": ["bull market"],
        "熊市": ["bear market"],
        "基本面": ["fundamental analysis"],
        "技术面": ["technical analysis"],
        "K线": ["candlestick chart"],
        "均线": ["moving average", "MA"],
        "MACD": ["moving average convergence divergence"],
        "量化交易": ["quantitative trading"],
        # v7: Extended tech
        "向量数据库": ["vector database"],
        "智能体": ["AI agent", "agent"],
        "提示工程": ["prompt engineering"],
        "RAG": ["retrieval augmented generation"],
        "微服务架构": ["microservice architecture"],
        "云原生": ["cloud native"],
        "DevOps": ["development operations"],
        "网络爬虫": ["web crawler", "web scraping"],
        "数据可视化": ["data visualization"],
        "图数据库": ["graph database"],
        # English -> Chinese
        "artificial intelligence": ["人工智能"],
        "machine learning": ["机器学习"],
        "deep learning": ["深度学习"],
        "search engine": ["搜索引擎"],
        "recommendation": ["推荐"],
        "algorithm": ["算法"],
        "database": ["数据库"],
        "frontend": ["前端"],
        "backend": ["后端"],
        "deployment": ["部署"],
        "security": ["安全"],
        "optimization": ["优化"],
        "framework": ["框架"],
        # v7: Extended English -> Chinese
        "stock": ["股票"],
        "investment": ["投资"],
        "vector database": ["向量数据库"],
        "embedding": ["向量", "嵌入"],
        "finetuning": ["微调"],
        "agent": ["智能体"],
        "prompt engineering": ["提示工程"],
        "web scraping": ["网络爬虫"],
        "data visualization": ["数据可视化"],
        "microservice": ["微服务"],
        "container": ["容器"],
        "load balancing": ["负载均衡"],
        "circuit breaker": ["熔断器"],
    }

    # Question patterns
    _QUESTION_PATTERNS = [
        r"^(how|what|why|when|where|who|which|is|are|can|do|does|will|would|should)",
        r"^(怎么|如何|为什么|是什么|什么是|哪|哪个|多少|能不能|可以|是否|有没有)",
        r"\?$",
    ]

    # Language detection patterns
    _CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
    _LATIN_PATTERN = re.compile(r"[a-zA-Z]")

    @classmethod
    def enhance(cls, query: str, language: str = "auto") -> QueryAnalysis:
        """Full query enhancement pipeline.

        Pipeline: normalize → detect_lang → spell_correct → classify_intent
                  → expand_synonyms → cross_lang_rewrite → build_analysis
        """
        original = query.strip()
        if not original:
            return QueryAnalysis(
                original_query="",
                enhanced_query="",
                language="unknown",
                primary_type="general",
                confidence=0.0,
            )

        # Step 1: Normalize
        normalized = cls._normalize(original)

        # Step 2: Detect language
        detected_lang = cls._detect_language(normalized) if language == "auto" else language

        # Step 3: Spell correction
        corrected, was_corrected = cls._spell_correct(normalized)

        # Step 4: Intent classification (enhanced)
        primary_type, secondary_types, confidence, is_question = cls._classify_intent(
            corrected, detected_lang
        )

        # Step 5: Synonym expansion
        expanded = cls._expand_synonyms(corrected, primary_type)

        # Step 6: Cross-language rewrite
        rewrites = cls._cross_lang_rewrite(corrected, detected_lang, primary_type)

        # Step 7: Build enhanced query
        # Use corrected query as base, append key expansions if beneficial
        enhanced = corrected
        if expanded and len(enhanced) < 100:
            # Add top 2 expanded terms that aren't already in the query
            top_expanded = [t for t in expanded[:3] if t.lower() not in enhanced.lower()]
            if top_expanded:
                enhanced = f"{enhanced} ({' '.join(top_expanded[:2])})"

        return QueryAnalysis(
            original_query=original,
            enhanced_query=enhanced,
            rewritten_queries=rewrites,
            language=detected_lang,
            is_question=is_question,
            primary_type=primary_type,
            secondary_types=secondary_types,
            confidence=confidence,
            spell_corrected=was_corrected,
            expanded_terms=expanded,
        )

    @classmethod
    def _normalize(cls, query: str) -> str:
        """Normalize query: trim, collapse whitespace, normalize unicode."""
        # Normalize unicode (NFKC: compatibility decomposition)
        normalized = unicodedata.normalize("NFKC", query)
        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def _detect_language(cls, query: str) -> str:
        """Detect query language: zh, en, or mixed."""
        cjk_count = len(cls._CJK_PATTERN.findall(query))
        latin_count = len(cls._LATIN_PATTERN.findall(query))

        if cjk_count == 0 and latin_count > 0:
            return "en"
        if latin_count == 0 and cjk_count > 0:
            return "zh"
        if cjk_count > 0 and latin_count > 0:
            return "mixed"
        return "unknown"

    @classmethod
    def _spell_correct(cls, query: str) -> tuple[str, bool]:
        """Simple spell correction based on common typo map.

        Returns (corrected_query, was_corrected).
        """
        corrected = query
        was_corrected = False

        query_lower = query.lower()
        for typo, correction in cls._COMMON_TYPOS.items():
            if typo in query_lower:
                # Preserve original case pattern
                idx = query_lower.index(typo)
                original_word = query[idx : idx + len(typo)]
                if original_word.isupper():
                    replacement = correction.upper()
                elif original_word[0].isupper():
                    replacement = correction.capitalize()
                else:
                    replacement = correction
                corrected = corrected[:idx] + replacement + corrected[idx + len(typo) :]
                was_corrected = True
                query_lower = corrected.lower()

        return corrected, was_corrected

    @classmethod
    def _classify_intent(
        cls, query: str, language: str
    ) -> tuple[str, list[str], float, bool]:
        """Enhanced intent classification.

        Returns (primary_type, secondary_types, confidence, is_question).
        Uses multi-signal scoring: keyword match + pattern match + structural signals.
        """
        scores: Counter = Counter()
        q = query.lower()

        # Question detection
        is_question = any(re.search(p, q) for p in cls._QUESTION_PATTERNS)

        # Type scoring with weighted keywords
        type_rules = {
            "code": [
                (r"\b(code|coding|编程|代码|函数|function|class|api|sdk|debug|error|bug)", 2.0),
                (r"\b(python|java|javascript|typescript|rust|go|golang|c\+\+|ruby|swift)", 2.0),
                (r"\b(pip|npm|yarn|cargo|maven|docker|kubernetes|git|github)", 1.5),
                (r"\b(react|vue|angular|django|flask|fastapi|spring|node)", 1.5),
                (r"\b(sql|redis|mongodb|postgres|mysql|sqlite)", 1.5),
                (r"(接口|框架|库|包|安装|部署|配置|编译|调试|变量|对象)", 1.0),
                (r"(模块|组件|服务|中间件|微服务|容器|集群)", 1.0),
            ],
            "academic": [
                (r"\b(paper|论文|arxiv|research|研究|实验|experiment)", 2.0),
                (r"\b(算法|algorithm|神经网络|neural|transformer|attention|bert|gpt)", 2.0),
                (r"\b(ieee|acm|引用|citation|doi|bibliography)", 1.5),
                (r"\b(train|训练|finetune|dataset|benchmark|evaluation)", 1.5),
            ],
            "knowledge": [
                (r"\b(是什么|什么是|what is|介绍|简介|overview|概念|定义)", 2.0),
                (r"\b(百科|wiki|wikipedia|历史|原理|principle)", 1.5),
                (r"(区别|差异|对比|比较|vs\.?)", 1.5),
                (r"\b(how does|how do|工作原理|运作机制)", 1.5),
            ],
            "news": [
                (r"\b(新闻|news|最新|latest|今天|today|昨天|yesterday|recent|刚刚|突发)", 2.0),
                (r"\b(2024|2025|2026|股价|stock|天气|比分|赛事)", 1.5),
                (r"\b(breaking|update|announce|发布|上线|launch)", 1.5),
            ],
            "tutorial": [
                (r"\b(教程|tutorial|how to|怎么用|如何实现|how do i)", 2.0),
                (r"\b(guide|入门|指南|getting started|best practice)", 1.5),
                (r"\b(示例|example|demo|sample|模板|template)", 1.5),
                (r"\b(步骤|step|walkthrough|手把手|from scratch)", 1.5),
                (r"(用法|使用方法|配置方法|安装教程|使用指南)", 1.0),
            ],
            "social": [
                (r"\b(reddit|twitter|微博|知乎|forum|论坛|讨论|discussion)", 2.0),
                (r"\b(opinion|观点|评价|review|评论|反馈|feedback)", 1.5),
                (r"\b(recommendation|推荐|建议|suggestion)", 1.0),
            ],
        }

        for intent_type, rules in type_rules.items():
            for pattern, weight in rules:
                if re.search(pattern, q):
                    scores[intent_type] += weight

        # Determine primary and secondary types
        if not scores:
            return "general", [], 0.3, is_question

        ranked = scores.most_common()
        primary = ranked[0][0]
        confidence = min(ranked[0][1] / 5.0, 1.0)  # Normalize to [0, 1]

        # Secondary types: anything with score > 30% of primary
        threshold = ranked[0][1] * 0.3
        secondary = [t for t, s in ranked[1:] if s >= threshold]

        return primary, secondary, confidence, is_question

    @classmethod
    def _expand_synonyms(cls, query: str, intent_type: str) -> list[str]:
        """Expand query with synonyms for better recall."""
        expanded = []
        q_lower = query.lower()

        for term, synonyms in cls._SYNONYMS.items():
            if term in q_lower:
                for syn in synonyms:
                    if syn.lower() not in q_lower:
                        expanded.append(syn)

        # Limit to top 5
        return expanded[:5]

    @classmethod
    def _cross_lang_rewrite(
        cls, query: str, language: str, intent_type: str
    ) -> list[str]:
        """Generate cross-language query rewrites for better recall.

        For Chinese queries, generate English variants and vice versa.
        """
        rewrites = []

        for term, translations in cls._CROSS_LANG.items():
            if term in query.lower():
                for translation in translations:
                    # Build rewritten query by replacing the term
                    rewritten = re.sub(
                        re.escape(term), translation, query, flags=re.IGNORECASE
                    )
                    if rewritten != query:
                        rewrites.append(rewritten)

        # Limit rewrites to avoid overloading engines
        return rewrites[:3]
