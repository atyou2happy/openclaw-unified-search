# tasks.md - 任务分解

## Phase 1: 核心框架（基础）
- [ ] T01: 项目初始化（pyproject.toml, .gitignore, 目录结构）
- [ ] T02: 统一数据模型（models.py — SearchRequest/SearchResult/SearchResponse）
- [ ] T03: BaseSearchModule 抽象基类 + 模块注册器
- [ ] T04: FastAPI 入口 + 路由（main.py, router.py）
- [ ] T05: 搜索引擎调度器（engine.py — 并行调度+结果合并）
- [ ] T06: 内存缓存层（cache.py）

## Phase 2: 核心搜索模块
- [ ] T07: TabBitBrowser 模块（集成 tabbit_cdp_search.py）
- [ ] T08: DuckDuckGo 网页搜索模块
- [ ] T09: GitHub 仓库/代码搜索模块

## Phase 3: 扩展模块
- [ ] T10: PDF 在线获取模块
- [ ] T11: 文档站点抓取模块
- [ ] T12: 学术论文搜索模块

## Phase 4: 测试+文档+交付
- [ ] T13: 单元测试 + 集成测试
- [ ] T14: README.md + README_CN.md
- [ ] T15: OpenClaw 集成配置（技能文件）
