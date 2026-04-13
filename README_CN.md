<p align="center">
  <h1 align="center">🔍 OpenClaw Unified Search</h1>
  <p align="center">
    <b>智能调度统一搜索服务 — 18 模块 + 真并行引擎 v4 + RRF 融合</b><br/>
    <a href="README.md">English</a> | 中文
  </p>
</p>

---

一个模块化的统一搜索服务，专为 [OpenClaw](https://github.com/openclaw) 设计。所有搜索需求通过一个 API 完成，返回全面、准确、最新的高质量信息。

## ✨ 核心特性

- ⚡ **真并行引擎 v4** — `asyncio.wait(FIRST_COMPLETED)` 替代串行循环，所有模块真正并行执行
- 🥇 **TabBit 始终优先** — 核心模块硬编码最高优先级，结果始终置顶
- 🔀 **RRF 融合** — Reciprocal Rank Fusion（业界标准算法）实现多源结果融合
- 🧠 **智能路由 v4** — 意图识别 + 自适应模块数（3-8个）+ 新闻意图检测
- 🧩 **18 个模块** — TabBitBrowser、SearXNG、秘塔AI、Phind、Perplexity、DDG、Jina、GitHub、PDF、文档、学术、百科、Brave、Tavily、Serper、Bing、You.com、Komo
- 🧠 **智能去重 v4** — URL 去重 + 标题相似度（SequenceMatcher > 0.85）+ 跨源元数据合并
- 🧪 **36 个测试** — 意图识别、RRF 融合、并行执行、tabbit 优先级、结构化解析
- 💾 **LRU 缓存** — 可配置 TTL，避免重复搜索
- 🔌 **零门槛扩展** — 实现 `BaseSearchModule` 即可添加新模块

## 🏗️ 架构

```
用户查询
  ↓
意图识别（编程/学术/知识/新闻/综合/内容）
  ↓
TabBit 始终选中 + 智能选模块（3-8 个）
  ↓
真并行搜索（asyncio.wait FIRST_COMPLETED）
  ↓
Phase 1: 收集快速结果 → Phase 2: 等待慢模块
  ↓
RRF 融合 + 智能去重
  ↓
TabBit 结果置顶 → 最终结果
```

## 📦 模块列表

| 模块 | 来源 | 说明 | 需配置 |
|------|------|------|--------|
| `tabbit` | TabBitBrowser | **核心模块** — AI 驱动的本地搜索（CDP） | CDP 9222 |
| `searxng` | SearXNG | 聚合搜索（百度/搜狗/360/Google/Bing/DDG/Brave 等 11 引擎） | Docker |
| `metaso` | 秘塔AI搜索 | 中文 AI 搜索最强（简洁/深入/研究模式） | METASO_TOKEN |
| `phind` | Phind | 程序员 AI 搜索引擎 | 代理 |
| `perplexity` | Perplexity AI | AI 答案引擎 | PERPLEXITY_API_KEY |
| `tavily` | Tavily | AI Agent 专用搜索 | TAVILY_API_KEY |
| `you` | You.com | AI 增强搜索 | YOU_API_KEY |
| `github` | GitHub + Zread.ai | 仓库搜索 + 深度分析 | 无 |
| `academic` | arXiv + Semantic Scholar | 学术论文搜索 | 无 |
| `wiki` | 百度百科 + 维基百科 | 双引擎百科查询 | 代理(维基) |
| `jina` | Jina Reader | 网页内容提取（Markdown） | 代理 |
| `ddg` | DuckDuckGo | 免费无限搜索 | 无需 |
| `brave` | Brave Search | 企业级 Web 搜索 | BRAVE_API_KEY |
| `serper` | Serper.dev | Google 搜索结果 | SERPER_API_KEY |
| `bing` | Bing Search | 微软搜索 | BING_API_KEY |
| `komo` | Komo | 快速 AI 搜索 | 无需 |
| `web` | TabBit + DDG | TabBit 优先 + DDG 备用 | 代理 |
| `pdf` | pypdf | 在线 PDF 获取 + 解析 | 无 |
| `docs` | 文档站点 | 技术文档抓取 | 无 |

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/atyou2happy/openclaw-unified-search.git
cd openclaw-unified-search
pip install -r requirements.txt
```

### 启动

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8900
```

### 搜索

```bash
# 智能搜索（自动选模块，tabbit 始终优先）
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "FastAPI 怎么写接口", "max_results": 10}' | jq .

# 指定模块
curl -s http://localhost:8900/search/github -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "openclaw", "max_results": 5}' | jq .

# 深度搜索
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention", "depth": "deep", "max_results": 20}' | jq .
```

## 🧠 智能调度示例

| 查询 | 识别意图 | 选择模块 |
|------|---------|---------|
| `Python FastAPI 怎么写接口` | code | tabbit → phind → github → searxng |
| `transformer attention 论文` | academic | tabbit → metaso → academic → searxng |
| `什么是 RAG 技术` | knowledge | tabbit → wiki → searxng → metaso |
| `atyou2happy/openclaw-unified-search` | code (repo) | tabbit → github → phind |
| `https://docs.python.org/...` | content | tabbit → jina → github |
| `最新AI新闻` | news | tabbit → searxng → bing → brave |

## 🔄 RRF 融合算法

Reciprocal Rank Fusion 是业界标准的多源搜索结果融合算法：

```
score(d) = Σ (1 / (k + rank_i(d))) × weight(source_i)
```

其中 `k=60`（标准值），每个源有质量权重：
- `tabbit: 1.5` | `metaso: 1.4` | `perplexity: 1.35` | `phind: 1.35`
- 出现在多个源中的 URL 会获得显著的分数提升

## 🐳 SearXNG 部署

```bash
docker pull searxng/searxng:latest

docker run -d --name searxng --restart unless-stopped \
  --network host \
  -v /var/lib/docker/searxng:/etc/searxng:rw \
  searxng/searxng:latest
```

## 🔧 环境变量

```bash
# 代理（WSL 环境）
export HTTP_PROXY="http://127.0.0.1:21882"
export HTTPS_PROXY="http://127.0.0.1:21882"

# 可选 API Keys
export METASO_TOKEN="your-tid-token"
export BRAVE_API_KEY="xxx"
export TAVILY_API_KEY="xxx"
export SERPER_API_KEY="xxx"
export PERPLEXITY_API_KEY="xxx"
export BING_API_KEY="xxx"
export YOU_API_KEY="xxx"
export GITHUB_TOKEN="xxx"
```

## 📁 项目结构

```
openclaw-unified-search/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── engine.py        # v4 — 真并行引擎 + RRF 融合
│   ├── config.py        # 配置（代理等）
│   ├── models.py        # 数据模型
│   ├── cache.py         # LRU 缓存
│   ├── router.py        # API 路由
│   └── modules/
│       ├── __init__.py  # 模块注册
│       ├── base.py      # 基类
│       ├── tabbit.py    # v2 — 结构化多结果解析
│       ├── searxng.py   # SearXNG 聚合
│       ├── metaso.py    # 秘塔AI搜索
│       ├── phind.py     # Phind 程序员搜索
│       ├── perplexity.py # Perplexity AI
│       ├── ddg.py       # DuckDuckGo
│       ├── bing.py      # Bing Search
│       ├── you.py       # You.com
│       ├── komo.py      # Komo
│       ├── tavily.py    # Tavily
│       ├── brave.py     # Brave Search
│       ├── serper.py    # Serper.dev
│       ├── github.py    # GitHub + Zread
│       ├── wiki.py      # 百度百科 + 维基百科
│       ├── jina.py      # Jina Reader
│       ├── pdf.py       # PDF 解析
│       ├── docs.py      # 文档站点
│       └── academic.py  # 学术论文
├── tests/
│   └── test_search.py   # 36 个测试
├── README.md            # English Docs
├── README_CN.md         # 中文文档
└── pyproject.toml
```

## 📊 v4 vs v3 对比

| 特性 | v3 | v4 |
|------|----|----|
| 执行方式 | 串行 for 循环 | 真并行 (asyncio.wait) |
| Tabbit | 在队列中，可能不是第一个 | 始终第一，硬编码最高优先级 |
| 融合算法 | 简单权重排序 | RRF（Reciprocal Rank Fusion） |
| 去重 | URL + 标题前缀 | URL + 标题相似度 + 元数据合并 |
| 模块数量 | 固定 5 个 | 自适应 3-8 个 |
| 新闻意图 | 不检测 | 检测并路由 |
| Tabbit 结果 | 单一文本块 | 结构化多结果 |
| 测试数 | 22 | 36 |

## 📄 License

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
