# 开源搜索工具调研

## 1. Web 搜索模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **SearXNG** | searxng (自托管) | AGPL | 元搜索引擎，聚合Google/Bing/DuckDuckGo等70+引擎，本地部署，无API限制 |
| **DuckDuckGo Search** | duckduckgo-search | MIT | 免费无限搜索，无需API key，支持文本/图片/新闻/视频 |
| **Tavily** | tavily-python | MIT | AI优化搜索结果，免费1000次/月 |
| **TabBitBrowser** | 已有CDP脚本 | N/A | 本地AI搜索，质量最高，需CDP端口 |

**推荐**: TabBitBrowser（主）+ DuckDuckGo（备选/fallback）

## 2. GitHub 仓库模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **PyGithub** | PyGithub | LGPL | 官方Python封装，支持搜索/文件读取/README等 |
| **GitHub REST API** | requests/httpx | - | 直接调用，无需额外依赖 |
| **GitHub Search API** | 内置 | - | 搜索代码/仓库/议题，5000次/小时(认证) |

**推荐**: httpx 直接调 GitHub REST API（轻量，无需额外依赖）

## 3. PDF 在线获取模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **PyMuPDF (fitz)** | PyMuPDF | AGPL | 最快PDF解析，支持文本/表格/图片提取 |
| **pdfplumber** | pdfplumber | MIT | 表格提取优秀，文本提取准确 |
| **pypdf** | pypdf | BSD | 纯Python，轻量，提取文本/元数据 |
| **marker-pdf** | marker-pdf | MIT | AI增强PDF→Markdown转换 |

**推荐**: pypdf（轻量BSD）+ pdfplumber（表格场景）

## 4. 文档站点模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **httpx + BeautifulSoup** | httpx, bs4 | MIT | 通用网页抓取+解析 |
| **trafilatura** | trafilatura | Apache 2.0 | 专注正文提取，去除导航/广告/页脚 |
| **readability-lxml** | readability-lxml | Apache 2.0 | Mozilla Readability算法Python版 |

**推荐**: trafilatura（正文提取最佳）

## 5. 学术论文模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **Semantic Scholar** | semanticscholar | MIT | 免费API，2B+论文，无key限制(100次/5min) |
| **arxiv** | arxiv | MIT | arXiv论文搜索+全文下载 |
| **CrossRef** | requests | - | DOI元数据查询，免费 |

**推荐**: semanticscholar + arxiv

## 6. 代码搜索模块
| 工具 | pip | License | 特点 |
|------|-----|---------|------|
| **GitHub Code Search API** | httpx | - | 搜索GitHub代码，认证后30次/min |
| **Sourcegraph API** | requests | - | 代码搜索，需token |

**推荐**: GitHub Code Search API（已有GitHub生态）

## 依赖总览（核心）
```
fastapi, uvicorn, httpx, pydantic
duckduckgo-search
PyGithub 或 httpx(直接调GitHub API)
pypdf, pdfplumber
trafilatura
semanticscholar, arxiv
redis (缓存，可选)
```
