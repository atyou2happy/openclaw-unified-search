<p align="center">
  <h1 align="center">🔍 OpenClaw Unified Search</h1>
  <p align="center">
    <b>智能调度统一搜索服务 — 15 模块 + 意图识别 + 去重重排</b><br/>
    <a href="README_EN.md">English</a> | 中文
  </p>
</p>

---

一个模块化的统一搜索服务，专为 [OpenClaw](https://github.com/openclaw) 设计。所有搜索需求通过一个 API 完成，返回全面、准确、最新的高质量信息。

## ✨ 核心特性

- 🧠 **智能调度** — 意图识别自动选择最佳模块（编程→Phind/GitHub，中文→秘塔/百度，学术→arXiv）
- 🧩 **15 个模块** — SearXNG、秘塔AI、Phind、TabBitBrowser、DDG、Jina、GitHub、PDF、文档、学术、百科、Brave、Tavily、Serper
- ⚡ **并行搜索** — 选中模块并行执行，毫秒级调度
- 🔄 **去重重排** — URL去重 + 标题去重 + AI答案优先 + 权威来源加权
- 💾 **LRU 缓存** — 可配置 TTL，避免重复搜索
- 🔌 **零门槛扩展** — 实现 `BaseSearchModule` 即可添加新模块

## 🏗️ 架构

```
用户查询
  ↓
意图识别（编程/学术/知识/综合/内容）
  ↓
智能选模块（3-5 个最相关）
  ↓
并行搜索
  ↓
去重 + 质量重排
  ↓
返回结果（附带来源链接）
```

## 📦 模块列表

| 模块 | 来源 | 说明 | 需配置 |
|------|------|------|--------|
| `searxng` | SearXNG | 聚合搜索（百度/搜狗/360/Google/Bing/DDG/Brave 等 11 引擎） | Docker |
| `metaso` | 秘塔AI搜索 | 中文 AI 搜索最强（简洁/深入/研究模式） | METASO_TOKEN |
| `phind` | Phind | 程序员 AI 搜索引擎 | 代理 |
| `tabbit` | TabBitBrowser | AI 驱动的本地搜索（CDP） | CDP 9222 |
| `web` | TabBit + DDG | TabBit 优先 + DDG 备用 | 代理 |
| `jina` | Jina Reader | 网页内容提取（Markdown） | 代理 |
| `github` | GitHub + Zread.ai | 仓库搜索 + 深度分析 | 无 |
| `pdf` | pypdf | 在线 PDF 获取 + 解析 | 无 |
| `docs` | 文档站点 | 技术文档抓取 | 无 |
| `academic` | arXiv + Semantic Scholar | 学术论文搜索 | 无 |
| `wiki` | 百度百科 + 维基百科 | 双引擎百科查询 | 代理(维基) |
| `brave` | Brave Search | 企业级 Web 搜索 | BRAVE_API_KEY |
| `tavily` | Tavily | AI Agent 专用搜索 | TAVILY_API_KEY |
| `serper` | Serper.dev | Google 搜索结果 | SERPER_API_KEY |

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
# 智能搜索（自动选模块）
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
| `Python FastAPI 怎么写接口` | code | phind → github → tabbit → searxng |
| `transformer attention 论文` | academic | metaso → academic → searxng |
| `什么是 RAG 技术` | knowledge | wiki → searxng → metaso |
| `atyou2happy/openclaw-unified-search` | code (repo) | github → phind → searxng |
| `https://docs.python.org/...` | code + content | jina → github → phind |

## 🐳 SearXNG 部署

```bash
# 拉取镜像
docker pull searxng/searxng:latest

# 启动（host 模式，共享代理）
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
export GITHUB_TOKEN="xxx"  # 提高速率限制
```

## 📁 项目结构

```
openclaw-unified-search/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── engine.py        # 智能调度引擎 v2
│   ├── config.py        # 配置（代理等）
│   ├── models.py        # 数据模型
│   ├── cache.py         # LRU 缓存
│   ├── router.py        # API 路由
│   └── modules/
│       ├── __init__.py  # 模块注册
│       ├── base.py      # 基类
│       ├── searxng.py   # SearXNG 聚合
│       ├── metaso.py    # 秘塔AI搜索
│       ├── phind.py     # Phind 程序员搜索
│       ├── tabbit.py    # TabBitBrowser
│       ├── web.py       # Web 搜索
│       ├── jina.py      # Jina Reader
│       ├── github.py    # GitHub + Zread
│       ├── wiki.py      # 百度百科 + 维基百科
│       ├── pdf.py       # PDF 解析
│       ├── docs.py      # 文档站点
│       ├── academic.py  # 学术论文
│       ├── brave.py     # Brave Search
│       ├── tavily.py    # Tavily
│       └── serper.py    # Serper.dev
├── tests/
│   └── test_search.py   # 10 个测试
├── README.md            # 中文文档
├── README_EN.md         # English Docs
└── requirements.txt
```

## 📊 技术栈

- **Python 3.12** + FastAPI + httpx + pydantic v2
- **SearXNG** (Docker) — 247+ 搜索引擎聚合
- **秘塔AI** — 中文 AI 搜索
- **Jina Reader** — 网页内容提取
- **pgvector** / **Whoosh** — 混合搜索（计划中）

## 📄 License

MIT

---

<p align="center">
  <a href="https://github.com/atyou2happy/openclaw-unified-search">GitHub</a> ·
  <a href="https://openclaw.ai">OpenClaw</a> ·
  Made with ❤️ for the AI Agent community
</p>
