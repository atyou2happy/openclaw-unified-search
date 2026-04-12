# Unified Search API 统一搜索服务

一个模块化的统一搜索服务，为 [OpenClaw](https://github.com/openclaw/openclaw) 提供全面、准确、最新、高质量的信息获取。所有搜索需求 — 深度调研、日常查询 — 都通过一个 API 入口完成。

## 特性

- 🧩 **模块化** — 每个数据源独立模块，可插拔
- ⚡ **并行调度** — 所有模块并发执行，结果合并排序
- 🎯 **统一接口** — 一个端点（`POST /search`）搞定一切
- 💾 **智能缓存** — LRU 缓存，可配置 TTL
- 🔌 **易扩展** — 实现 `BaseSearchModule` 即可添加新模块

## 搜索模块

| 模块 | 数据源 | 说明 |
|------|--------|------|
| `tabbit` | TabBitBrowser | 本地 AI 搜索（质量最高） |
| `web` | DuckDuckGo | 免费无限网页搜索 |
| `github` | GitHub API | 仓库/代码/README 搜索 |
| `pdf` | pypdf | 在线 PDF 下载+文本提取 |
| `docs` | trafilatura | 文档站点抓取+正文提取 |
| `academic` | Semantic Scholar + arXiv | 学术论文搜索 |

## 快速开始

```bash
# 安装
git clone https://github.com/atyou2happy/unified-search.git
cd unified-search
pip install -e .

# 运行
uvicorn app.main:app --host 127.0.0.1 --port 8900
```

打开 http://localhost:8900/docs 查看交互式 API 文档。

## API 使用

### 统一搜索（所有模块）

```bash
curl -X POST http://localhost:8900/search \
  -H "Content-Type: application/json" \
  -d '{"query": "FastCode GitHub", "max_results": 10}'
```

### 指定模块搜索

```bash
curl -X POST http://localhost:8900/search/github \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention", "max_results": 5}'
```

### 请求参数

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | string | 必填 | 搜索关键词/问题 |
| `sources` | string[] | []（全部） | 指定数据源模块 |
| `max_results` | int | 10 | 每个模块最大结果数 |
| `timeout` | int | 30 | 超时秒数 |
| `depth` | string | "normal" | `quick`/`normal`/`deep` |
| `language` | string | "auto" | `auto`/`zh`/`en` |

### 其他端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康检查 |
| GET | `/modules` | 列出所有模块及状态 |
| GET | `/modules/{name}/status` | 单个模块状态 |
| GET | `/cache/stats` | 缓存统计 |
| DELETE | `/cache` | 清除缓存 |

## 添加新模块

1. 创建 `app/modules/your_module.py`：

```python
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult

class YourModule(BaseSearchModule):
    name = "your_module"
    description = "模块描述"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        # 你的搜索逻辑
        return [SearchResult(title="...", url="...", snippet="...", source=self.name)]
```

2. 在 `app/modules/__init__.py` 注册：

```python
from app.modules.your_module import YourModule
register(YourModule())
```

## 配置

环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GITHUB_TOKEN` | None | GitHub API token（提高速率限制） |

详细配置见 `app/config.py`。

## 技术栈

- **FastAPI** + **uvicorn** — 异步 Web 框架
- **httpx** — 异步 HTTP 客户端
- **pydantic v2** — 数据验证
- **duckduckgo-search** — 免费网页搜索
- **pypdf** — PDF 文本提取
- **trafilatura** — 网页正文提取
- **arxiv** — arXiv 论文搜索
- **Semantic Scholar API** — 学术论文搜索

## 许可证

MIT
