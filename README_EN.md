<p align="center">
  <h1 align="center">🔍 OpenClaw Unified Search</h1>
  <p align="center">
    <b>Smart Unified Search Service — 15 Modules + Intent Routing + Dedup & Rerank</b><br/>
    English | <a href="README.md">中文</a>
  </p>
</p>

---

A modular, unified search service designed for [OpenClaw](https://github.com/openclaw). All search needs through one API, returning comprehensive, accurate, and up-to-date information.

## ✨ Key Features

- 🧠 **Smart Routing** — Intent detection auto-selects best modules (code→Phind/GitHub, Chinese→Metaso/Baidu, academic→arXiv)
- 🧩 **15 Modules** — SearXNG, Metaso AI, Phind, TabBitBrowser, DDG, Jina, GitHub, PDF, Docs, Academic, Wiki, Brave, Tavily, Serper
- ⚡ **Parallel Search** — Selected modules run concurrently, millisecond-level orchestration
- 🔄 **Dedup & Rerank** — URL dedup + title dedup + AI answers first + authority boosting
- 💾 **LRU Cache** — Configurable TTL, avoids redundant searches
- 🔌 **Zero-Barrier Extension** — Add new modules by implementing `BaseSearchModule`

## 🏗️ Architecture

```
User Query
  ↓
Intent Detection (code / academic / knowledge / general / content)
  ↓
Smart Module Selection (3-5 most relevant)
  ↓
Parallel Search
  ↓
Dedup + Quality Rerank
  ↓
Results (with source URLs)
```

## 📦 Modules

| Module | Source | Description | Config |
|--------|--------|-------------|--------|
| `searxng` | SearXNG | Aggregated search (Baidu/Sogou/360/Google/Bing/DDG/Brave, 11 engines) | Docker |
| `metaso` | Metaso AI | Best Chinese AI search (concise/deep/research modes) | METASO_TOKEN |
| `phind` | Phind | AI search engine for developers | Proxy |
| `tabbit` | TabBitBrowser | AI-powered local search via CDP | CDP 9222 |
| `web` | TabBit + DDG | TabBit primary + DDG fallback | Proxy |
| `jina` | Jina Reader | Web content extraction (Markdown) | Proxy |
| `github` | GitHub + Zread.ai | Repo search + deep analysis | None |
| `pdf` | pypdf | Online PDF download + parsing | None |
| `docs` | Doc sites | Technical documentation crawling | None |
| `academic` | arXiv + Semantic Scholar | Academic paper search | None |
| `wiki` | Baidu Baike + Wikipedia | Dual-engine encyclopedia | Proxy (Wiki) |
| `brave` | Brave Search | Enterprise web search | BRAVE_API_KEY |
| `tavily` | Tavily | AI agent-optimized search | TAVILY_API_KEY |
| `serper` | Serper.dev | Google search results | SERPER_API_KEY |

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
# Smart search (auto module selection)
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
| `Python FastAPI how to write endpoints` | code | phind → github → tabbit → searxng |
| `transformer attention paper` | academic | metaso → academic → searxng |
| `what is RAG technology` | knowledge | wiki → searxng → metaso |
| `atyou2happy/openclaw-unified-search` | code (repo) | github → phind → searxng |
| `https://docs.python.org/...` | code + content | jina → github → phind |

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
export GITHUB_TOKEN="xxx"  # Higher rate limits
```

## 📁 Project Structure

```
openclaw-unified-search/
├── app/
│   ├── main.py          # FastAPI entry
│   ├── engine.py        # Smart orchestration engine v2
│   ├── config.py        # Config (proxy etc.)
│   ├── models.py        # Data models
│   ├── cache.py         # LRU cache
│   ├── router.py        # API routes
│   └── modules/
│       ├── __init__.py  # Module registry
│       ├── base.py      # Base class
│       ├── searxng.py   # SearXNG aggregation
│       ├── metaso.py    # Metaso AI search
│       ├── phind.py     # Phind developer search
│       ├── tabbit.py    # TabBitBrowser
│       ├── web.py       # Web search
│       ├── jina.py      # Jina Reader
│       ├── github.py    # GitHub + Zread
│       ├── wiki.py      # Baidu Baike + Wikipedia
│       ├── pdf.py       # PDF parsing
│       ├── docs.py      # Doc sites
│       ├── academic.py  # Academic papers
│       ├── brave.py     # Brave Search
│       ├── tavily.py    # Tavily
│       └── serper.py    # Serper.dev
├── tests/
│   └── test_search.py   # 10 tests
├── README.md            # Chinese docs
├── README_EN.md         # English docs
└── requirements.txt
```

## 📊 Tech Stack

- **Python 3.12** + FastAPI + httpx + pydantic v2
- **SearXNG** (Docker) — 247+ search engine aggregation
- **Metaso AI** — Chinese AI search
- **Jina Reader** — Web content extraction
- **pgvector** / **Whoosh** — Hybrid search (planned)

## 📄 License

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
