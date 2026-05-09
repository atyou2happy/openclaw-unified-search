# unified-search v3.0 技术设计

> 版本：3.0.0 | 日期：2026-05-09

## 架构总览

```
app/engine/
  intent.py              — 查询意图识别 (v3: 无大改, 复用)
  query_enhancer.py      — 查询增强 (v3: +词权重+缩写展开+变体生成)
  text_scorer.py         — [NEW] BM25文本匹配引擎
  scheduler.py           — 搜索调度 (v3: +模块权重动态调优)
  merger.py              — RRF融合+去重+重排 (v3: +自适应RRF+SimHash+聚类)
  quality_scorer.py      — 质量评分 (v3: 无大改, 复用)
  performance_tracker.py — 性能追踪 (v3: +权重计算接口)
  search_logger.py       — 搜索日志 (v3: +聚类信息记录)
  result_clustering.py   — [NEW] 搜索结果聚类
  availability.py        — 可用性缓存 (v3: 无大改)
```

## 数据流 (增强后)

```
Query → QueryEnhancer(词权重+缩写展开+变体) 
      → QueryIntent.detect(复用)
      → Scheduler: select_modules(动态权重) + parallel_search
      → ResultMerger.rrf_fuse(自适应k + 共识增强)
      → TextScorer.rank(替代SequenceMatcher)
      → QualityScorer.score(复用)
      → ResultMerger.rerank(SimHash去重 + 聚类 + 多样性)
      → SearchLogger.log
      → Response
```

## 关键设计决策

### 1. BM25替代SequenceMatcher — 渐进替换

**为什么不完全替换？**
SequenceMatcher 在短查询上表现尚可，完全替换有回归风险。

**方案**: 双路径并行验证
- 新请求走BM25路径
- 保留 SequenceMatcher 作为 fallback（环境变量控制）
- 经过1周验证后移除旧路径

```python
# merger.py rerank()
if Config.BM25_ENABLED:  # default True
    score = TextScorer.bm25_score(result, query)
else:
    score = _legacy_sequence_matcher(result, query)
```

### 2. SimHash去重阈值

| Hamming距离 | 含义 | 处理 |
|------------|------|------|
| 0 | 完全相同 | 保留高relevance |
| 1-2 | 高度相似 | 保留高relevance |
| 3 | 可能相似 | 标题再次确认 |
| 4+ | 不同 | 都保留 |

### 3. 自适应RRF k值

```python
def _adaptive_k(result_count: int) -> float:
    if result_count <= 10:
        return 30  # 小结果集强调排名
    elif result_count <= 30:
        return 60  # 标准
    else:
        return 90  # 大结果集平滑处理
```

### 4. 聚类算法选择

选用 n-gram overlap + single-pass clustering (在线算法, O(n²)):
- 对每个结果，检查是否与已有cluster的centroid有足够的n-gram overlap
- 有 → 加入该cluster
- 无 → 创建新cluster
- 聚类数上限: min(result_count / 3, 5)

选择理由:
- 无需训练数据
- 在线算法，适合实时搜索
- O(n²) 在15-20条结果时耗时 < 5ms

### 5. 模块权重动态调优公式

```python
dynamic_weight = base_weight × success_rate^0.5 × quality_factor × (1 / (1 + speed/10))
# success_rate^0.5: 温和惩罚失败模块（不直接乘成功率）
# quality_factor: avg(result_count) / expected_count
# speed decay: 1 / (1 + speed/10) — 慢模块轻微降权
```

每100次搜索后更新一次权重，结果四舍五入到2位小数。
权重变化超过20%时记录日志。
