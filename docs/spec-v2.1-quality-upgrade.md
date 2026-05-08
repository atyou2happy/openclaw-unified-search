# unified-search v2.1 — 搜索质量升级规格

> 版本：2.1.0 | 日期：2026-05-08 | 状态：completed

## v2.0 → v2.1 改动

### 1. P0: 修复 SOURCE_WEIGHTS 双重加权
- **问题**: rrf_fuse() 和 rerank() 都应用了 SOURCE_WEIGHTS，导致 tabbit 实际权重 1.5×1.5=2.25x
- **修复**: rerank() 中移除 SOURCE_WEIGHTS 重复应用，只在 rrf_fuse() 中应用一次
- **文件**: `app/engine/merger.py`

### 2. 结果自动分类 (Category)
- **新增**: MODULE_CATEGORY_MAP 将模块映射到 8 种 category (academic/code/social/video/news/knowledge/answer/web)
- **新增**: categorize() 方法自动标注结果类别
- **集成**: _inject_diversity() 自动为结果添加 metadata.category 标签
- **文件**: `app/engine/merger.py`

### 3. Category 级多样性保证
- **改进**: _inject_diversity() 从纯 per-source 限制升级为 source+category 双层多样性
- **保证**: 每种出现的 category 至少有 1 条结果在 diverse 部分
- **文件**: `app/engine/merger.py`

### 4. 查询增强词典扩展
- **同义词**: 从 28 条扩展到 68 条，新增金融(14条) + AI/工程(26条) 领域术语
- **跨语言**: 从 34 条扩展到 66 条，新增金融(13条) + 技术(19条) 领域映射
- **文件**: `app/engine/query_enhancer.py`

### 5. 动态超时分配
- **集成**: scheduler 使用 perf_tracker.suggest_timeout() 为每个模块分配独立超时
- **修复**: _safe_search 不再每次 reset_availability()，让 avail_cache 正常工作
- **新增**: _safe_search 添加 asyncio.wait_for 超时保护（之前依赖模块内部超时）
- **文件**: `app/engine/scheduler.py`

### 6. 搜索日志 + 分析
- **新增**: SearchLogger 类，JSONL 格式追加日志（10MB 自动轮转）
- **记录**: query/sources/results/elapsed/errors/intent/analysis
- **分析**: get_stats() 计算平均耗时/结果数/错误率/高频查询/高频源
- **集成**: scheduler.search() 每次搜索后自动记录
- **文件**: `app/engine/search_logger.py` (新建)

## 测试

| 测试文件 | 数量 | 状态 |
|----------|------|------|
| test_unit.py | 19 | ✅ |
| test_intent.py | 9 | ✅ |
| test_merger.py | 13 | ✅ (新增5: categorize/diversity/no-double-weight) |
| test_query_enhancer.py | 22 | ✅ |
| test_quality_scorer.py | 18 | ✅ |
| test_performance_tracker.py | 16 | ✅ |
| test_search_logger.py | 10 | ✅ (新增) |
| **总计** | **126** | **126 passed** |

## 不做什么

- ❌ 不引入 LLM 调用
- ❌ 不增加新外部依赖
- ❌ 不改动 API 接口（向后兼容）
- ❌ 不改动 BaseSearchModule 接口
