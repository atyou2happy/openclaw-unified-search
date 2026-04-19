<p align="center">
  <h1 align="center">🔍 OpenClaw Unified Search</h1>
  <p align="center">
    <b>Smart Unified Search Service — 24 Modules + 7 CDP AI Agents + Quality Fallback</b><br/>
    English | <a href="README_CN.md">中文</a>
  </p>
</p>

---

A modular, unified search service designed for [OpenClaw](https://github.com/openclaw). All search needs through one API, returning comprehensive, accurate, and up-to-date information.

## ✨ Key Features

- ⚡ **True Parallel Engine v4** — `asyncio.wait(FIRST_COMPLETED)`, all modules run concurrently
- 🤖 **7 CDP AI Agents** — TabBit, DeepSeek, Gemini, Grok, Kimi, GLM, Qwen via TabBitBrowser CDP
- 🔄 **Quality Fallback** — Auto-degrade from best to next-best AI agent on failure
- 🔀 **RRF Fusion** — Reciprocal Rank Fusion for multi-source result merging
- 🧠 **Smart Routing** — Intent detection + adaptive module count (3-8 based on query complexity)
- 🧩 **24 Modules** — 7 CDP AI agents + 17 traditional search modules
- 🧠 **Smart Dedup** — URL dedup + title similarity + metadata merge
- 💾 **LRU Cache** — Configurable TTL, avoids redundant searches
- 🔌 **Zero-Barrier Extension** — Add new modules by implementing `BaseSearchModule`

## 🔄 Quality Fallback

CDP AI agents are ordered by search quality. When the best agent fails or times out, it automatically degrades to the next:

```
tabbit (0.95) → deepseek (0.92) → gemini (0.90) → grok (0.88) → kimi (0.86) → glm (0.85) → qwen (0.84)
```

```bash
# CDP fallback search — first success wins
curl -s http://localhost:8900/search/cdp -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "what is RAG?", "timeout": 120}' | jq .
```

## 🤖 CDP AI Agent Modules

These modules interact with AI chat services via Chrome DevTools Protocol (CDP) through TabBitBrowser:

| Module | Service | Input Method | Send Method | Response Detection |
|--------|---------|-------------|-------------|-------------------|
| `tabbit` | TabBitBrowser AI | textarea | Button click | Structured parsing |
| `deepseek` | DeepSeek Chat | textarea (React) | Enter key | `ds-markdown` elements |
| `gemini` | Google Gemini | textarea | Button click | Markdown elements |
| `grok` | xAI Grok | ProseMirror div | **Ctrl+Enter** | Markdown elements |
| `kimi` | Kimi AI | contenteditable div | Button click | Markdown elements |
| `glm` | Zhipu GLM | textarea (Element UI) | Button click | Markdown elements |
| `qwen` | Qwen AI (search mode) | textarea | Enter key | mds count stabilization |

### CDP Architecture

```
US Service → CDP WebSocket → TabBitBrowser
  ↓
1. Target.createTarget (new tab)
2. Wait for DOM ready
3. Focus input element
4. Input.dispatchKeyEvent (char by char)
5. Send (Enter / Button click / Ctrl+Enter)
6. Wait for AI response completion
7. Extract response from DOM
8. Target.close (cleanup tab)
```

### Key Technical Details

- **Message ID filtering**: CDP responses filtered by ID to avoid event notification interference
- **Proxy bypass**: WebSocket connections clear proxy env vars to avoid localhost interception
- **React compatibility**: DeepSeek requires `Input.dispatchKeyEvent` type:'char' for controlled components
- **Response detection**: Each AI service has unique DOM structures; Qwen uses markdown element count stabilization

## 📦 All Modules

| Module | Source | Description | Config |
|--------|--------|-------------|--------|
| `tabbit` | TabBitBrowser | **Core** — AI-powered search via CDP | CDP 9222 |
| `deepseek` | DeepSeek | DeepSeek AI chat via CDP | CDP 9222 |
| `gemini` | Google Gemini | Gemini AI search via CDP | CDP 9222 |
| `grok` | xAI Grok | Grok AI search via CDP | CDP 9222 |
| `kimi` | Kimi AI | Kimi AI search via CDP | CDP 9222 |
| `glm` | Zhipu GLM | GLM AI search via CDP | CDP 9222 |
| `qwen` | Qwen AI | Qwen search mode via CDP | CDP 9222 |
| `searxng` | SearXNG | Aggregated search (247+ engines) | Docker |
| `metaso` | Metaso AI | Chinese AI search | METASO_TOKEN |
| `web` | TabBit + DDG | TabBit primary + DDG fallback | Proxy |
| `jina` | Jina Reader | Web content extraction (Markdown) | Proxy |
| `github` | GitHub + Zread.ai | Repo search + deep analysis | None |
| `academic` | arXiv + Semantic Scholar | Academic paper search | None |
| `wiki` | Baidu Baike + Wikipedia | Dual-engine encyclopedia | Proxy |
| `pdf` | pypdf | Online PDF download + parsing | None |
| `docs` | Doc sites | Technical documentation crawling | None |
| `ddg` | DuckDuckGo | Free unlimited search | Proxy |
| `brave` | Brave Search | Enterprise web search | BRAVE_API_KEY |
| `tavily` | Tavily | AI agent-optimized search | TAVILY_API_KEY |
| `serper` | Serper.dev | Google search results | SERPER_API_KEY |
| `perplexity` | Perplexity AI | AI answer engine | PERPLEXITY_API_KEY |
| `bing` | Bing Search | Microsoft search | BING_API_KEY |
| `you` | You.com | AI-enhanced search | YOU_API_KEY |
| `komo` | Komo | Fast AI search | None |

## 🚀 Quick Start

### Install

```bash
git clone https://github.com/atyou2happy/openclaw-unified-search.git
cd openclaw-unified-search
pip install -r requirements.txt
```

### Run

```bash
# Must unset proxy vars for localhost connections
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy \
  uvicorn app.main:app --host 127.0.0.1 --port 8900
```

### Search

```bash
# Smart search (auto module selection)
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "how to write FastAPI endpoints", "max_results": 10}' | jq .

# CDP fallback search (quality-ordered degradation)
curl -s http://localhost:8900/search/cdp -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "what is RAG?", "timeout": 120}' | jq .

# Specific AI agent
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "what is RAG", "sources": ["deepseek", "kimi", "grok"]}' | jq .
```

## 🧠 Smart Routing Examples

| Query | Intent | Selected Modules |
|-------|--------|-----------------|
| `Python FastAPI endpoints` | code | tabbit → deepseek → github → searxng |
| `transformer attention paper` | academic | tabbit → academic → searxng → metaso |
| `what is RAG technology` | knowledge | tabbit → wiki → searxng → kimi |
| `最新AI新闻` | news | tabbit → searxng → bing → brave |

## 🔄 RRF Fusion

Reciprocal Rank Fusion — industry-standard algorithm for merging multi-source results:

```
score(d) = Σ (1 / (k + rank_i(d))) × weight(source_i)
```

Where `k=60` (standard), with quality weights per source.

## 🔧 Environment Variables

```bash
# Proxy — MUST unset for localhost connections
# Do NOT set HTTP_PROXY when running uvicorn

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
│   ├── main.py          # FastAPI entry + module registration
│   ├── engine.py        # v4 — Parallel engine + RRF fusion + CDP fallback
│   ├── config.py        # Config (proxy, CDP port)
│   ├── models.py        # Data models
│   ├── cache.py         # LRU cache
│   ├── router.py        # API routes
│   └── modules/         # 24 search modules
│       ├── tabbit.py    # Core CDP search
│       ├── deepseek.py  # DeepSeek CDP
│       ├── gemini.py    # Gemini CDP
│       ├── grok.py      # Grok CDP
│       ├── kimi.py      # Kimi CDP
│       ├── glm.py       # GLM CDP
│       ├── qwen.py      # Qwen CDP
│       ├── searxng.py   # SearXNG aggregation
│       ├── metaso.py    # Metaso AI
│       └── ...          # + 14 more modules
├── tests/
├── README.md
├── README_CN.md
└── pyproject.toml
```

## 📊 Tech Stack

- **Python 3.12** + FastAPI + httpx + pydantic v2
- **Chrome DevTools Protocol** — AI agent interaction via TabBitBrowser
- **asyncio.wait(FIRST_COMPLETED)** — True parallel module execution
- **Reciprocal Rank Fusion** — Multi-source result merging
- **websockets** — CDP communication with message ID filtering

## 📄 License

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
