# unified-search v0.3.0 升级规格

> dev-workflow full mode | 2026-04-24

## 目标

升级 unified-search 从 v0.2.1 到 v0.3.0，增加 6 个搜索维度，全面增强 OpenClaw 搜索能力。

## 升级范围

### Feature 1: 社交媒体搜索（>200行）

#### Task 1.1: Reddit 模块修复（已基本完成，50-200行）
- Sub-task 1.1.1: 修复 User-Agent + Accept headers（已完成）
- Sub-task 1.1.2: 注册到 MODULE_PROFILES + SOURCE_WEIGHTS
- Sub-task 1.1.3: 测试验证

#### Task 1.2: YouTube Transcript 模块（50-200行）
- Sub-task 1.2.1: 实现 YouTubeModule（youtube_transcript_api）
- Sub-task 1.2.2: 注册到 MODULE_PROFILES + SOURCE_WEIGHTS
- Sub-task 1.2.3: 测试验证

### Feature 2: 实时趋势聚合（>200行）

#### Task 2.1: GitHub Trending 模块（50-200行）
- Sub-task 2.1.1: 实现 GitHubTrendingModule
- Sub-task 2.1.2: 注册到 MODULE_PROFILES + SOURCE_WEIGHTS
- Sub-task 2.1.3: 测试验证

#### Task 2.2: ProductHunt 模块（50-200行）
- Sub-task 2.2.1: 实现 ProductHuntModule（GraphQL API）
- Sub-task 2.2.2: 注册到 MODULE_PROFILES + SOURCE_WEIGHTS
- Sub-task 2.2.3: 测试验证

### Feature 3: 性能优化（>200行）

#### Task 3.1: 启动加速 — 并行 health check（50-200行）
- Sub-task 3.1.1: 改造 main.py startup 为 asyncio.gather 并行检查
- Sub-task 3.1.2: 添加 health_check_timeout 到 MODULE_PROFILES
- Sub-task 3.1.3: 测试启动时间

#### Task 3.2: 意图路由增强（50-200行）
- Sub-task 3.2.1: reddit/hackernews/youtube 添加到 MODULE_PROFILES
- Sub-task 3.2.2: 社交媒体意图关键词检测
- Sub-task 3.2.3: 趋势/热门意图关键词检测

### Feature 4: Web 抓取增强（延期）
- Firecrawl Docker 自部署（等网络稳定后）

### Feature 5: 语义/向量搜索集成（延期）
- MemPalace 集成到搜索结果排序

### Feature 6: AI 聚合搜索优化（延期）
- 多 AI 搜索结果融合策略优化

## 技术约束

- Python 3.12 + FastAPI + httpx + pydantic v2
- 所有新模块必须免费（无需 API key 或有免费额度）
- 遵循 BaseSearchModule 接口
- 自动注册（放 modules/ 目录即可）

## 成功标准

1. 新增 ≥3 个工作模块（reddit + youtube + github_trending）
2. 启动时间 < 15s（当前 ~56s）
3. 搜索查询响应 < 10s（社交媒体类）
4. 所有新模块 health_check 通过
5. 28+ → 31+ 模块总数
