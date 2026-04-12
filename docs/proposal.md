# Unified Search - 统一搜索服务

## 项目概述

为 OpenClaw 系统提供统一的信息搜索入口，所有搜索需求（深度调研、日常查询）都通过此服务获取全面、准确、最新、高质量的信息。

## 核心设计原则

1. **模块化** — 每个数据源一个独立模块，可插拔
2. **统一接口** — 统一的请求/响应格式
3. **优先级调度** — 按数据源质量和速度智能调度
4. **结果合并** — 多源结果去重+排序
5. **缓存层** — 相同查询命中缓存，减少重复调用
6. **本地部署** — FastAPI 本地服务，端口 8900

## 目录结构

```
unified-search/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── models.py            # 统一数据模型 (Pydantic)
│   ├── router.py            # API 路由
│   ├── engine.py            # 搜索引擎（调度+合并）
│   ├── cache.py             # 缓存层（内存/Redis可选）
│   └── modules/             # 搜索模块（每个数据源一个）
│       ├── __init__.py      # 模块注册器
│       ├── base.py          # BaseModule 抽象基类
│       ├── tabbit.py        # TabBitBrowser 搜索（核心）
│       ├── web.py           # DuckDuckGo 通用网页搜索
│       ├── github.py        # GitHub 仓库/代码搜索
│       ├── pdf.py           # 在线 PDF 获取+解析
│       ├── docs.py          # 文档站点抓取
│       └── academic.py      # 学术论文搜索
├── tests/
│   ├── test_engine.py
│   ├── test_modules.py
│   └── test_api.py
├── docs/
│   ├── proposal.md          # 本文件
│   ├── design.md            # 技术设计
│   ├── research.md          # 开源调研
│   └── tasks.md             # 任务分解
├── pyproject.toml
├── README.md
├── README_CN.md
└── .gitignore
```

## 统一数据模型

### 请求
```python
class SearchRequest(BaseModel):
    query: str                    # 搜索关键词/问题
    sources: list[str] = []       # 指定数据源，空=全部
    max_results: int = 10         # 每个源最大结果数
    timeout: int = 30             # 超时秒数
    depth: str = "normal"         # quick | normal | deep
    language: str = "auto"        # auto | zh | en
```

### 响应
```python
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str                  # 摘要
    source: str                   # 来源模块名
    content: str | None = None    # 完整内容（按需）
    relevance: float = 0.0        # 相关度评分
    timestamp: datetime | None    # 发布时间

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    elapsed: float                # 耗时秒
    sources_used: list[str]       # 实际使用的数据源
    cached: bool = False
```

## 模块接口

```python
class BaseSearchModule(ABC):
    name: str                     # 模块标识
    description: str
    
    @abstractmethod
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """执行搜索"""
        
    @abstractmethod
    async def health_check(self) -> bool:
        """检查模块是否可用"""
    
    def is_available(self) -> bool:
        """快速可用性检查"""
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /search | 统一搜索 |
| POST | /search/{module} | 指定模块搜索 |
| GET | /modules | 列出可用模块 |
| GET | /modules/{name}/status | 模块状态 |
| GET | /health | 服务健康检查 |
| GET | /cache/stats | 缓存统计 |
| DELETE | /cache | 清除缓存 |

## 模块详细设计

### 1. TabBitBrowser (tabbit.py) — 核心模块
- 集成现有 `tabbit_cdp_search.py`
- CDP WebSocket 连接池管理
- 自动重连 + 错误重试
- 支持深度模式（多轮追问）

### 2. Web Search (web.py)
- DuckDuckGo 为默认（免费无限）
- trafilatura 提取正文内容
- deep 模式：自动抓取 Top N 结果的完整页面

### 3. GitHub (github.py)
- 搜索仓库、代码、README
- 获取仓库文件树和内容
- gh CLI 作为备用（已安装）

### 4. PDF (pdf.py)
- 下载在线 PDF → pypdf 提取文本
- 支持直接传入 PDF URL
- 大文件流式处理，限制内存

### 5. Docs (docs.py)
- 输入文档站点 URL → trafilatura 提取正文
- 支持抓取页面下的子链接
- 自动识别常见文档框架（ReadTheDocs、Docusaurus 等）

### 6. Academic (academic.py)
- Semantic Scholar 搜索论文
- arXiv 下载+解析
- 返回标题、摘要、作者、引用数、PDF链接

## 调度策略

```
请求 → 并行调用所有可用模块 → 收集结果 → 合并去重 → 相关度排序 → 返回
         ↓
    模块超时独立，不影响其他模块
         ↓
    TabBitBrowser 权重最高（AI 搜索质量最好）
```

## 缓存策略
- 内存 LRU 缓存（默认1000条，TTL 1小时）
- 可选 Redis（生产环境）
- 缓存 key = hash(query + sources + language)

## 技术栈
- **框架**: FastAPI + uvicorn
- **HTTP**: httpx (异步)
- **验证**: pydantic v2
- **测试**: pytest + pytest-asyncio
- **搜索**: duckduckgo-search, httpx(GitHub), pypdf, trafilatura, semanticscholar, arxiv
