<p align="center">
  <h1 align="center">🔍 OpenClaw Unified Search</h1>
  <p align="center">
    <b>Smart Unified Search Service — 18 Modules + True Parallel Engine v4 + RRF Fusion</b><br/>
    English | <a href="README_CN.md">中文</a>
  </p>
</p>

---

A modular, unified search service designed for [OpenClaw](https://github.com/openclaw). All search needs through one API, returning comprehensive, accurate, and up-to-date information.

## ✨ Key Features

- ⚡ **True Parallel Engine v4** — `asyncio.wait(FIRST_COMPLETED)` replaces sequential loop, all modules run concurrently
- 🥇 **TabBit Always First** — Core module hardcoded to highest priority, results always displayed first
- 🔀 **RRF Fusion** — Reciprocal Rank Fusion (industry standard) for multi-source result merging
- 🧠 **Smart Routing v4** — Intent detection + adaptive module count (3-8 based on query complexity) + news intent
- 🧩 **18 Modules** — TabBitBrowser, SearXNG, Metaso AI, Phind, Perplexity, DDG, Jina, GitHub, PDF, Docs, Academic, Wiki, Brave, Tavily, Serper, Bing, You.com, Komo
- 🧠 **Smart Dedup v4** — URL dedup + title similarity (SequenceMatcher > 0.85) + cross-source metadata merge
- 🧪 **36 Tests** — Intent detection, RRF fusion, parallel execution, tabbit priority, structured parsing
- 💾 **LRU Cache** — Configurable TTL, avoids redundant searches
- 🔌 **Zero-Barrier Extension** — Add new modules by implementing `BaseSearchModule`

## 🏗️ Architecture

```
User Query
  ↓
Intent Detection (code / academic / knowledge / news / general / content)
  ↓
TabBit Always Selected + Smart Module Selection (3-8 modules)
  ↓
True Parallel Search (asyncio.wait FIRST_COMPLETED)
  ↓
Phase 1: Collect fast results → Phase 2: Wait for slow modules
  ↓
RRF Fusion + Smart Dedup
  ↓
TabBit Results On Top → Final Results
```

## 📦 Modules

| Module | Source | Description | Config |
|--------|--------|-------------|--------|
| `tabbit` | TabBitBrowser | **Core module** — AI-powered local search via CDP | CDP 9222 |
| `searxng` | SearXNG | Aggregated search (Baidu/Sogou/360/Google/Bing/DDG/Brave, 11 engines) | Docker |
| `metaso` | Metaso AI | Best Chinese AI search (concise/deep/research modes) | METASO_TOKEN |
| `phind` | Phind | AI search engine for developers | Proxy |
| `perplexity` | Perplexity AI | AI answer engine | PERPLEXITY_API_KEY |
| `tavily` | Tavily | AI agent-optimized search | TAVILY_API_KEY |
| `you` | You.com | AI-enhanced search | YOU_API_KEY |
| `github` | GitHub + Zread.ai | Repo search + deep analysis | None |
| `academic` | arXiv + Semantic Scholar | Academic paper search | None |
| `wiki` | Baidu Baike + Wikipedia | Dual-engine encyclopedia | Proxy (Wiki) |
| `jina` | Jina Reader | Web content extraction (Markdown) | Proxy |
| `ddg` | DuckDuckGo | Free unlimited search | None |
| `brave` | Brave Search | Enterprise web search | BRAVE_API_KEY |
| `serper` | Serper.dev | Google search results | SERPER_API_KEY |
| `bing` | Bing Search | Microsoft search | BING_API_KEY |
| `komo` | Komo | Fast AI search | None |
| `web` | TabBit + DDG | TabBit primary + DDG fallback | Proxy |
| `pdf` | pypdf | Online PDF download + parsing | None |
| `docs` | Doc sites | Technical documentation crawling | None |

## 🚀 Quick Start

### Install

```bash
git clone https://github.com/atyou2happy/openclaw-unified-search.git
cd openclaw-unified-search
pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8900
```

### Search

```bash
# Smart search (auto module selection, tabbit always first)
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "how to write FastAPI endpoints", "max_results": 10}' | jq .

# Specific module
curl -s http://localhost:8900/search/github -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "openclaw", "max_results": 5}' | jq .

# Deep search
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention", "depth": "deep", "max_results": 20}' | jq .
```

## 🧠 Smart Routing Examples

| Query | Intent | Selected Modules |
|-------|--------|-----------------|
| `Python FastAPI how to write endpoints` | code | tabbit → phind → github → searxng |
| `transformer attention paper` | academic | tabbit → metaso → academic → searxng |
| `what is RAG technology` | knowledge | tabbit → wiki → searxng → metaso |
| `atyou2happy/openclaw-unified-search` | code (repo) | tabbit → github → phind |
| `https://docs.python.org/...` | content | tabbit → jina → github |
| `最新AI新闻` | news | tabbit → searxng → bing → brave |

## 🔄 RRF Fusion

Reciprocal Rank Fusion is the industry-standard algorithm for merging results from multiple search sources:

```
score(d) = Σ (1 / (k + rank_i(d))) × weight(source_i)
```

Where `k=60` (standard), and each source has a quality weight:
- `tabbit: 1.5` | `metaso: 1.4` | `perplexity: 1.35` | `phind: 1.35`
- URLs appearing in multiple sources get a significant score boost

## 🐳 SearXNG Deployment

```bash
docker pull searxng/searxng:latest

docker run -d --name searxng --restart unless-stopped \
  --network host \
  -v /var/lib/docker/searxng:/etc/searxng:rw \
  searxng/searxng:latest
```

## 🔧 Environment Variables

```bash
# Proxy (WSL environment)
export HTTP_PROXY="http://127.0.0.1:21882"
export HTTPS_PROXY="http://127.0.0.1:21882"

# Optional API Keys
export METASO_TOKEN="your-tid-token"
export BRAVE_API_KEY="xxx"
export TAVILY_API_KEY="xxx"
export SERPER_API_KEY="xxx"
export PERPLEXITY_API_KEY="xxx"
export BING_API_KEY="xxx"
export YOU_API_KEY="xxx"
export GITHUB_TOKEN="xxx"
```

## 📁 Project Structure

```
openclaw-unified-search/
├── app/
│   ├── main.py          # FastAPI entry
│   ├── engine.py        # v4 — True parallel engine + RRF fusion
│   ├── config.py        # Config (proxy etc.)
│   ├── models.py        # Data models
│   ├── cache.py         # LRU cache
│   ├── router.py        # API routes
│   └── modules/
│       ├── __init__.py  # Module registry
│       ├── base.py      # Base class
│       ├── tabbit.py    # v2 — Structured multi-result parsing
│       ├── searxng.py   # SearXNG aggregation
│       ├── metaso.py    # Metaso AI search
│       ├── phind.py     # Phind developer search
│       ├── perplexity.py # Perplexity AI
│       ├── ddg.py       # DuckDuckGo
│       ├── bing.py      # Bing Search
│       ├── you.py       # You.com
│       ├── komo.py      # Komo
│       ├── tavily.py    # Tavily
│       ├── brave.py     # Brave Search
│       ├── serper.py    # Serper.dev
│       ├── github.py    # GitHub + Zread
│       ├── wiki.py      # Baidu Baike + Wikipedia
│       ├── jina.py      # Jina Reader
│       ├── pdf.py       # PDF parsing
│       ├── docs.py      # Doc sites
│       └── academic.py  # Academic papers
├── tests/
│   └── test_search.py   # 36 tests
├── README.md            # English docs
├── README_CN.md         # Chinese docs
└── pyproject.toml
```

## 📊 Tech Stack

- **Python 3.12** + FastAPI + httpx + pydantic v2
- **asyncio.wait(FIRST_COMPLETED)** — True parallel module execution
- **Reciprocal Rank Fusion** — Industry-standard multi-source result merging
- **TabBitBrowser CDP** — AI-powered local search

## 📊 v4 vs v3 Comparison

| Feature | v3 | v4 |
|---------|----|----|
| Execution | Sequential for loop | True parallel (asyncio.wait) |
| Tabbit | In queue, may not be first | Always first, hardcoded priority |
| Fusion | Simple weight sorting | RRF (Reciprocal Rank Fusion) |
| Dedup | URL + title prefix | URL + title similarity + metadata merge |
| Module count | Fixed 5 | Adaptive 3-8 based on intent |
| News intent | Not detected | Detected and routed |
| Tabbit results | Single text blob | Structured multi-result |
| Tests | 22 | 36 |

## 📄 License

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
