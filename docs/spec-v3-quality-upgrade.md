# unified-search v3.0 — 搜索质量深度升级

> 版本：3.0.0 | 日期：2026-05-09 | 状态：proposed

## 1. 为什么需要 v3.0

v2.1 已经修复了最关键的 P0 问题（RRF截断、双重加权），添加了基础的质量评分和多样性注入。但在以下方面仍有提升空间：

| 维度 | v2.1 现状 | v3.0 目标 |
|------|----------|----------|
| 文本匹配 | SequenceMatcher 编辑距离 | BM25-lite + Jaccard + 词权重 |
| 排序融合 | RRF (k=60固定) | 自适应RRF + 加权Borda Count混合 |
| 内容去重 | URL+标题相似度 | +SimHash内容指纹 |
| 模块权重 | 硬编码 SOURCE_WEIGHTS | perf_tracker 动态调权 |
| 查询理解 | 固定同义词表 | 上下文感知扩展 |
| 结果聚类 | 无 | 基础主题聚类 |
| 缓存策略 | TTL逐出 | 查询感知缓存预热 |

## 2. 调研来源

| 项目 | 借鉴点 | 参考原则 |
|------|--------|---------|
| SearXNG (29K⭐) | 引擎权重×共识×位置的三元评分，result_container merge策略 | RRF增强 |
| Perplexica (34K⭐) | 查询改写→多路搜索→rerank流程 | 查询增强 |
| Meilisearch (48K⭐) | BM25算法、typo-tolerant搜索 | 文本匹配 |
| Elasticsearch | function_score decay函数，BM25 | 评分函数 |
| Whoogle (11K⭐) | 轻量去重、Feeling Lucky快速答案 | 去重增强 |
| SimHash (Google) | 近重复文档检测 | 内容去重 |

## 3. 六大升级模块

### 3.1 BM25文本匹配引擎 (app/engine/text_scorer.py)

**问题**: 当前只用 SequenceMatcher (编辑距离) + 简单关键词命中。编辑距离对短查询有效，但对长查询和内容匹配效果差。

**方案**: 实现轻量BM25-lite，无需外部依赖：
- TF: term frequency in document
- IDF: inverse document frequency across result set
- BM25: `IDF * (TF * (k1+1)) / (TF + k1 * (1-b + b * doc_len/avg_doc_len))`
- 参数: k1=1.2, b=0.75 (标准值)
- 应用于: rerank阶段替代 SequenceMatcher

**来源**: Meilisearch core ranking + Elasticsearch BM25

### 3.2 自适应RRF融合 (app/engine/merger.py 增强)

**问题**: RRF的 k 值固定为60，无法针对不同查询类型调优。

**方案**:
- k值自适应: 小结果集用较小k(更强调排名)，大结果集用较大k(更平滑)
- 加权RRF: 在每个source的RRF贡献中，除了SOURCE_WEIGHTS，乘以perf_tracker的质量因子
- 共识增强: SearXNG式的 `weight *= len(positions)`（多引擎共识加权重）

**来源**: SearXNG calculate_score + weighted Borda Count

### 3.3 SimHash内容去重 (app/engine/merger.py 增强)

**问题**: 当前只做URL归一化 + 标题相似度 > 0.8。无法检测内容页面（描述同一事物但URL不同的两个结果）。

**方案**: SimHash 64-bit指纹:
- 对snippet+title提取特征（分词→hash→加权求和→sign）
- Hamming distance < 3 视为近重复
- 保留relevance更高的那条
- 纯Python实现，无外部依赖

**来源**: Google SimHash for near-duplicate detection

### 3.4 模块权重自动调优 (app/engine/scheduler.py 增强)

**问题**: SOURCE_WEIGHTS 在 merger.py 硬编码，不会随模块表现变化而调整。

**方案**:
- 每次搜索后，perf_tracker更新模块表现
- 定期（每100次搜索）自动计算动态权重:
  `dynamic_weight = base_weight * success_rate * quality_factor * speed_factor`
- 新模块加入时自动以基础权重开始，经过预热期后参与动态调权
- 保留手动权重覆盖能力（环境变量 SOURCE_WEIGHT_OVERRIDE）

**来源**: SearXNG engine weight system + PerformanceTracker EMA

### 3.5 查询上下文感知扩展 (app/engine/query_enhancer.py 增强)

**问题**: 查询扩展完全基于固定映射表。对"新概念"（如新出的AI模型名、新技术栈）无法扩展。

**方案**:
- 词重要性权重: 基于位置和词性给查询中不同词分配不同权重
  - 标题词（前2个词）权重 ×2
  - 专有名词/大写词权重 ×1.5
  - 停用词权重 ×0.1
- 缩写自动展开: 基于规则（大写连续字母 → 可能是缩写）
- 查询变体生成: 生成2-3个变体用于fallback搜索
  - 原始查询 + 移除停用词版本 + 只保留核心词版本

**来源**: Perplexica query rewriting + Elasticsearch query expansion

### 3.6 搜索结果聚类 (app/engine/result_clustering.py - 新建)

**问题**: 搜索返回15条结果混合在一起，用户难以快速定位。没有按主题分组的展示。

**方案**:
- 基于标题/snippet的n-gram重叠做快速聚类
- 每个cluster提取关键词作为标签
- 聚类数自适应: min(results_count / 3, 5)
- 输出: metadata.cluster_id, metadata.cluster_label
- 下游消费者（如OpenClaw）可选展示聚类视图

**来源**: SearXNG category facet aggregation

## 4. 不做什么

- ❌ 不引入 LLM 调用（保持延迟约束）
- ❌ 不引入新外部依赖（纯Python标准库）
- ❌ 不改动 API 接口（向后兼容）
- ❌ 不改动 BaseSearchModule 接口
- ❌ 不做向量搜索/embedding（需要模型依赖，超出范围）
- ❌ 不做学习排序模型训练（需要训练数据和框架）

## 5. 验收标准

| 指标 | v2.1 基线 | v3.0 目标 |
|------|----------|----------|
| 关键词命中率 (20题) | 待测 | ≥ 基线 + 20% |
| 同源占比前10 | ≤ 30% (source) | ≤ 25% |
| 聚类准确率 | N/A | ≥ 80% |
| 模块权重动态调优 | 硬编码 | 100次搜索内收敛 |
| 延迟增加 | 基线 | ≤ 5% |
| 现有测试通过 | 126 | 126 + 新增 |
| 代码覆盖率 | ~60% | ≥ 65% |

## 6. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | app/engine/text_scorer.py | BM25文本匹配引擎 |
| 新建 | app/engine/result_clustering.py | 搜索结果聚类 |
| 修改 | app/engine/merger.py | 自适应RRF + SimHash去重 |
| 修改 | app/engine/scheduler.py | 模块权重动态调优 |
| 修改 | app/engine/query_enhancer.py | 词权重 + 缩写展开 + 变体生成 |
| 修改 | app/models.py | 新增cluster相关字段(metadata) |
| 新建 | tests/test_text_scorer.py | BM25测试 |
| 新建 | tests/test_result_clustering.py | 聚类测试 |
| 修改 | tests/test_merger.py | SimHash + 自适应RRF测试 |
| 修改 | tests/test_scheduler.py | 动态权重测试 |
| 修改 | tests/test_query_enhancer.py | 词权重+缩写展开测试 |
| 修改 | README.md / README_CN.md | version+新模块+致谢 |
