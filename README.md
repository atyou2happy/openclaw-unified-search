# Unified Search API

A modular, unified search service for [OpenClaw](https://github.com/openclaw/openclaw). All search needs — deep research, daily queries — go through one API, returning comprehensive, accurate, up-to-date, and high-quality information.

## Features

- 🧩 **Modular** — Each data source is an independent, pluggable module
- ⚡ **Parallel** — All modules run concurrently, results merged and ranked
- 🎯 **Unified API** — One endpoint (`POST /search`) for everything
- 💾 **Caching** — LRU cache with configurable TTL
- 🔌 **Extensible** — Add new modules by implementing `BaseSearchModule`

## Search Modules

| Module | Source | Description |
|--------|--------|-------------|
| `tabbit` | TabBitBrowser | AI-powered local search via CDP (highest quality) |
| `web` | DuckDuckGo | Free unlimited web search |
| `github` | GitHub API | Repository, code, and README search |
| `pdf` | pypdf | Online PDF download + text extraction |
| `docs` | trafilatura | Documentation site scraping + content extraction |
| `academic` | Semantic Scholar + arXiv | Academic paper search |

## Quick Start

```bash
# Install
git clone https://github.com/atyou2happy/unified-search.git
cd unified-search
pip install -e .

# Run
uvicorn app.main:app --host 127.0.0.1 --port 8900
```

Open http://localhost:8900/docs for interactive API documentation.

## API

### Search (all modules)

```bash
curl -X POST http://localhost:8900/search \
  -H "Content-Type: application/json" \
  -d '{"query": "FastCode GitHub", "max_results": 10}'
```

### Search (specific module)

```bash
curl -X POST http://localhost:8900/search/github \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention", "max_results": 5}'
```

### Request Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query |
| `sources` | string[] | [] (all) | Specific modules to use |
| `max_results` | int | 10 | Max results per module |
| `timeout` | int | 30 | Timeout in seconds |
| `depth` | string | "normal" | `quick` / `normal` / `deep` |
| `language` | string | "auto" | `auto` / `zh` / `en` |

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| GET | `/modules` | List all modules with status |
| GET | `/modules/{name}/status` | Single module status |
| GET | `/cache/stats` | Cache statistics |
| DELETE | `/cache` | Clear cache |

## Adding a New Module

1. Create `app/modules/your_module.py`:

```python
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult

class YourModule(BaseSearchModule):
    name = "your_module"
    description = "Your module description"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        # Your search logic
        return [SearchResult(title="...", url="...", snippet="...", source=self.name)]
```

2. Register it in `app/modules/__init__.py`:

```python
from app.modules.your_module import YourModule
register(YourModule())
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | None | GitHub API token (higher rate limits) |

Config in `app/config.py`.

## Tech Stack

- **FastAPI** + **uvicorn** — async web framework
- **httpx** — async HTTP client
- **pydantic v2** — data validation
- **duckduckgo-search** — free web search
- **pypdf** — PDF text extraction
- **trafilatura** — web content extraction
- **arxiv** — arXiv paper search
- **Semantic Scholar API** — academic paper search

## License

MIT
