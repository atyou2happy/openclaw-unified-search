<p align="center">
  <h1 align="center">🔍 OpenClaw 统一搜索</h1>
  <p align="center">
    <b>智能统一搜索服务 — 24 个模块 + 7 个 CDP AI 代理 + 质量降级策略</b><br/>
    <a href="README.md">English</a> | 中文
  </p>
</p>

---

为 [OpenClaw](https://github.com/openclaw) 设计的模块化统一搜索服务。所有搜索需求通过一个 API 完成，返回全面、准确、最新的信息。

## ✨ 核心特性

- ⚡ **真并行引擎 v4** — `asyncio.wait(FIRST_COMPLETED)`，所有模块并发执行
- 🤖 **7 个 CDP AI 代理** — TabBit、DeepSeek、Gemini、Grok、Kimi、GLM、Qwen 通过 TabBitBrowser CDP
- 🔄 **质量降级** — 最佳 AI 代理失败时自动降级到次优代理
- 🔀 **RRF 融合** — Reciprocal Rank Fusion 多源结果合并
- 🧠 **智能路由** — 意图识别 + 自适应模块数量（3-8 个，基于查询复杂度）
- 🧩 **24 个模块** — 7 个 CDP AI 代理 + 17 个传统搜索模块
- 🧠 **智能去重** — URL 去重 + 标题相似度 + 元数据合并
- 💾 **LRU 缓存** — 可配置 TTL，避免重复搜索
- 🔌 **零门槛扩展** — 实现 `BaseSearchModule` 即可添加新模块
- 🎯 **智能相关性评分 (v0.5.0)** — SequenceMatcher + 关键词命中，不再使用固定 relevance
- 🛡️ **基础搜索保底 (v0.5.0)** — web + ddg + searxng 始终入选，保证搜索覆盖

## 🔄 质量降级策略

CDP AI 代理按搜索质量排序。最佳代理失败或超时时，自动降级到下一个：

```
tabbit (0.95) → deepseek (0.92) → gemini (0.90) → grok (0.88) → kimi (0.86) → glm (0.85) → qwen (0.84)
```

```bash
# CDP 降级搜索 — 第一个成功即返回
curl -s http://localhost:8900/search/cdp -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是RAG?", "timeout": 120}' | jq .
```

## 🤖 CDP AI 代理模块

通过 Chrome DevTools Protocol (CDP) 经 TabBitBrowser 与 AI 聊天服务交互：

| 模块 | 服务 | 输入方式 | 发送方式 | 回复检测 |
|------|------|---------|---------|---------|
| `tabbit` | TabBitBrowser AI | textarea | 按钮点击 | 结构化解析 |
| `deepseek` | DeepSeek Chat | textarea (React) | Enter 键 | `ds-markdown` 元素 |
| `gemini` | Google Gemini | textarea | 按钮点击 | Markdown 元素 |
| `grok` | xAI Grok | ProseMirror div | **Ctrl+Enter** | Markdown 元素 |
| `kimi` | Kimi AI | contenteditable div | 按钮点击 | Markdown 元素 |
| `glm` | 智谱 GLM | textarea (Element UI) | 按钮点击 | Markdown 元素 |
| `qwen` | 通义千问 (搜索模式) | textarea | Enter 键 | mds 计数稳定 |

### CDP 架构

```
搜索服务 → CDP WebSocket → TabBitBrowser
  ↓
1. Target.createTarget（新建标签页）
2. 等待 DOM 就绪
3. 聚焦输入元素
4. Input.dispatchKeyEvent（逐字符输入）
5. 发送（Enter / 按钮点击 / Ctrl+Enter）
6. 等待 AI 回复完成
7. 从 DOM 提取回复
8. Target.close（清理标签页）
```

### 关键技术细节

- **消息 ID 过滤**：CDP 响应按 ID 过滤，避免事件通知干扰
- **代理绕过**：WebSocket 连接清除代理环境变量，避免 localhost 拦截
- **React 兼容**：DeepSeek 需要 `Input.dispatchKeyEvent` type:'char' 处理受控组件
- **回复检测**：每个 AI 服务有独特的 DOM 结构；Qwen 使用 markdown 元素计数稳定方案

## 📦 全部模块

| 模块 | 来源 | 说明 | 配置 |
|------|------|------|------|
| `tabbit` | TabBitBrowser | **核心** — AI 搜索 via CDP | CDP 9222 |
| `deepseek` | DeepSeek | DeepSeek AI 聊天 via CDP | CDP 9222 |
| `gemini` | Google Gemini | Gemini AI 搜索 via CDP | CDP 9222 |
| `grok` | xAI Grok | Grok AI 搜索 via CDP | CDP 9222 |
| `kimi` | Kimi AI | Kimi AI 搜索 via CDP | CDP 9222 |
| `glm` | 智谱 GLM | GLM AI 搜索 via CDP | CDP 9222 |
| `qwen` | 通义千问 | 千问搜索模式 via CDP | CDP 9222 |
| `searxng` | SearXNG | 聚合搜索（247+ 引擎） | Docker |
| `metaso` | 秘塔 AI | 中文 AI 搜索 | METASO_TOKEN |
| `web` | TabBit + DDG | TabBit 主 + DDG 备用 | Proxy |
| `jina` | Jina Reader | 网页内容提取（Markdown） | Proxy |
| `github` | GitHub + Zread.ai | 仓库搜索 + 深度分析 | None |
| `academic` | arXiv + Semantic Scholar | 学术论文搜索 | None |
| `wiki` | 百度百科 + Wikipedia | 双引擎百科 | Proxy |
| `pdf` | pypdf | 在线 PDF 下载 + 解析 | None |
| `docs` | 文档站点 | 技术文档爬取 | None |
| `ddg` | DuckDuckGo | 免费无限搜索 | Proxy |
| `brave` | Brave Search | 企业级网页搜索 | BRAVE_API_KEY |
| `tavily` | Tavily | AI 代理优化搜索 | TAVILY_API_KEY |
| `serper` | Serper.dev | Google 搜索结果 | SERPER_API_KEY |
| `perplexity` | Perplexity AI | AI 回答引擎 | PERPLEXITY_API_KEY |
| `bing` | Bing Search | 微软搜索 | BING_API_KEY |
| `you` | You.com | AI 增强搜索 | YOU_API_KEY |
| `komo` | Komo | 快速 AI 搜索 | None |

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/atyou2happy/openclaw-unified-search.git
cd openclaw-unified-search
pip install -r requirements.txt
```

### 启动

```bash
# 必须清除代理变量以连接 localhost
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy \
  uvicorn app.main:app --host 127.0.0.1 --port 8900
```

### 搜索

```bash
# 智能搜索（自动选择模块）
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "如何编写 FastAPI 端点", "max_results": 10}' | jq .

# CDP 降级搜索（质量排序自动降级）
curl -s http://localhost:8900/search/cdp -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是RAG?", "timeout": 120}' | jq .

# 指定 AI 代理
curl -s http://localhost:8900/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是RAG", "sources": ["deepseek", "kimi", "grok"]}' | jq .
```

## 🧠 智能路由示例

| 查询 | 意图 | 选中模块 |
|------|------|---------|
| `Python FastAPI 端点` | code | tabbit → deepseek → github → searxng |
| `transformer attention 论文` | academic | tabbit → academic → searxng → metaso |
| `什么是 RAG 技术` | knowledge | tabbit → wiki → searxng → kimi |
| `最新AI新闻` | news | tabbit → searxng → bing → brave |

## 🔄 RRF 融合

Reciprocal Rank Fusion — 业界标准的多源结果合并算法：

```
score(d) = Σ (1 / (k + rank_i(d))) × weight(source_i)
```

其中 `k=60`（标准值），每个源有质量权重。

## 🔧 环境变量

```bash
# 代理 — 启动 uvicorn 时必须清除
# 不要设置 HTTP_PROXY

# 可选 API Keys
export METASO_TOKEN="your-tid-token"
export BRAVE_API_KEY="xxx"
export TAVILY_API_KEY="xxx"
export SERPER_API_KEY="xxx"
export PERPLEXITY_API_KEY="xxx"
export BING_API_KEY="xxx"
export YOU_API_KEY="xxx"
export GITHUB_TOKEN="xxx"\nexport EXA_API_KEY="xxx"
```

## 📁 项目结构

```
openclaw-unified-search/
├── app/
│   ├── main.py          # FastAPI 入口 + 模块注册
│   ├── engine.py        # v4 — 并行引擎 + RRF 融合 + CDP 降级
│   ├── config.py        # 配置（代理、CDD 端口）
│   ├── models.py        # 数据模型
│   ├── cache.py         # LRU 缓存
│   ├── router.py        # API 路由
│   └── modules/         # 24 个搜索模块
│       ├── tabbit.py    # 核心 CDP 搜索
│       ├── deepseek.py  # DeepSeek CDP
│       ├── gemini.py    # Gemini CDP
│       ├── grok.py      # Grok CDP
│       ├── kimi.py      # Kimi CDP
│       ├── glm.py       # GLM CDP
│       ├── qwen.py      # Qwen CDP
│       ├── searxng.py   # SearXNG 聚合
│       ├── metaso.py    # 秘塔 AI
│       └── ...          # + 14 个模块
├── tests/
├── README.md
├── README_CN.md
└── pyproject.toml
```

## 📊 技术栈

- **Python 3.12** + FastAPI + httpx + pydantic v2
- **Chrome DevTools Protocol** — 通过 TabBitBrowser 与 AI 代理交互
- **asyncio.wait(FIRST_COMPLETED)** — 真并行模块执行
- **Reciprocal Rank Fusion** — 多源结果合并
- **websockets** — CDP 通信（消息 ID 过滤）

## 📄 许可证

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
