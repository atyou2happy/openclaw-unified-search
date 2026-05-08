# unified-search v2.0 — 搜索质量升级规格

> 版本：2.0.0 | 日期：2026-05-08 | 状态：proposal

## 目标

将 unified-search 从"聚合器"升级为"智能搜索服务"，核心提升搜索结果质量（准确率、召回率、相关性），使其作为唯一信息搜索入口时能产出高质量结果。

## 核心改进

### 1. 查询增强引擎 (QueryEnhancer)
- **拼写纠错**：基于编辑距离的中文/英文拼写检查
- **查询扩展**：同义词扩展 + 相关词推荐（启发式规则，非LLM）
- **查询改写**：语言检测后，对中文查询自动生成英文变体（反之亦然），提升跨语言召回
- **查询分类**：增强版意图识别，输出 `{primary_type, secondary_types, confidence, language, is_question}`

### 2. 自适应调度引擎 (AdaptiveScheduler)
- **模块性能追踪**：记录每个模块的历史成功率、平均响应时间、结果质量评分
- **动态权重调整**：基于历史数据动态调整模块选择和超时分配
- **智能超时分配**：快速模块给短超时，慢速模块给长超时，总预算约束
- **失败模式学习**：连续N次失败的模块自动降级，定期恢复探测

### 3. 增强融合算法 (EnhancedMerger)
- **RRF修复**：修复 score 截断问题，使用原始 RRF 分数排序后再归一化到 [0,1]
- **语义相似度重排**：查询与标题/snippet 的 TF-IDF 余弦相似度（轻量级，无需外部模型）
- **质量衰减**：结果位置越靠后衰减越大，避免低质量结果占据尾部
- **多样性注入**：同源结果不超过 max_per_source（默认3），确保结果多样化
- **Category聚合**：按类型（网页/学术/代码/社交）分组，确保各类型都有代表

### 4. 结果质量评估 (QualityScorer)
- **多维度评分**：relevance(40%) + authority(20%) + freshness(20%) + completeness(20%)
- **authority评分**：基于域名权威度数据库，动态更新
- **freshness评分**：基于发布时间戳（如果有）+ 域名时效性
- **completeness评分**：有标题(10%) + 有snippet(30%) + 有content(60%)

### 5. 搜索反馈环 (FeedbackLoop)
- **搜索日志**：记录每次搜索的 query、模块选择、结果、耗时、错误
- **质量指标**：自动计算 MRR(Mean Reciprocal Rank)、覆盖率、模块可靠性
- **Benchmark集成**：定期运行 benchmark.py，追踪质量趋势

## 不做什么

- ❌ 不引入 LLM 调用（避免增加延迟和成本）
- ❌ 不引入向量数据库（过度设计）
- ❌ 不改动现有模块接口（BaseSearchModule）
- ❌ 不增加新的外部搜索引擎模块
- ❌ 不改动 API 接口（保持向后兼容）

## 文件变更规划

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/engine/query_enhancer.py` | 新增 | 查询增强引擎 |
| `app/engine/adaptive_scheduler.py` | 新增 | 自适应调度 |
| `app/engine/quality_scorer.py` | 新增 | 结果质量评分 |
| `app/engine/merger.py` | 重构 | 增强融合算法 |
| `app/engine/intent.py` | 重构 | 增强意图识别 |
| `app/engine/scheduler.py` | 重构 | 集成自适应调度 |
| `app/engine/performance_tracker.py` | 新增 | 模块性能追踪 |
| `app/models.py` | 增强 | 新增 QueryAnalysis 模型 |
| `tests/test_query_enhancer.py` | 新增 | 查询增强测试 |
| `tests/test_quality_scorer.py` | 新增 | 质量评分测试 |
| `tests/test_adaptive_scheduler.py` | 新增 | 自适应调度测试 |
| `app/version.py` | 更新 | 2.0.0 |

## 验收标准

1. Benchmark 20题关键词命中率从当前水平提升 ≥15%
2. 55个现有测试全部通过
3. 新增测试覆盖率 ≥80%（新模块）
4. 单次搜索延迟 ≤ 当前水平的 110%（性能不退化）
5. 多源融合结果的多样性（同源占比 ≤ 30%）
