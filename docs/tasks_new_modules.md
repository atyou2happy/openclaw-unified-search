# New Search Modules - 规格定义

## 概述

为 openclaw-unified-search 添加 6 个新的搜索模块。

## 6 个新模块

| # | Module | API | 免费额度 | Env Var |
|---|-----|------|---------|--------|
| 1 | **Perplexity AI** | perplexity.ai | 免费注册 | PERPLEXITY_API_KEY |
| 2 | **DuckDuckGo** | html API | 无需 key |
| 3 | **Bing Search** | Microsoft | 1000次/月 | BING_API_KEY |
| 4 | **You.com** | you.com | 免费 | YOU_API_KEY |
| 5 | **Komo** | komo.ai | 免费 | 无需 key |
| 6 | **Google Serper** | serper.dev | 2500次(已有) | SERPER_API_KEY |

## 实现要求

所有模块必须继承 `BaseSearchModule`，实现：
- `name: str`
- `description: str`
- `async def search(request: SearchRequest) -> list[SearchResult]`
- `async def health_check() -> bool`

## 技术细节

### 1. Perplexity AI (perplexity.py)
- API: `https://api.perplexity.ai/chat/completions`
- Model: `llama-3.1-sonar-large-128k-online`
- Method: POST with streaming
- Auth: `Authorization: Bearer <API_KEY>`

### 2. DuckDuckGo (ddg.py)
- API: `https://html.duckduckgo.com/html/`
- 备用: `ddgs` Python 库
- Method: GET
- 无需 API key

### 3. Bing Search (bing.py)
- API: `https://api.bing.microsoft.com/v7.0/search`
- Method: GET
- Header: `Ocp-Apim-Subscription-Key: <API_KEY>`

### 4. You.com (you.py)
- API: `https://api.you.com/search`
- Method: GET
- Auth: `Authorization: Bearer <API_KEY>`

### 5. Komo (komo.py)
- API: `https://api.komo.ai/api/v3/search`
- Method: POST
- 无需 API key，但有 rate limit

### 6. Google Serper (serper.py) - 已有但需验证
- 验证现有实现是否完整
- 补充不足部分

## 任务列表

- [ ] T01: 创建 PerplexityModule
- [ ] T02: 创建 DuckDuckGoModule  
- [ ] T03: 创建 BingModule
- [ ] T04: Create YouModule
- [ ] T05: Create KomoModule
- [ ] T06: 验证 SerperModule
- [ ] T07: 注册所有新模块
- [ ] T08: 添加测试
- [ ] T09: 运行测试
- [ ] T10: 更新文档