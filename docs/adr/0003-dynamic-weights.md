# ADR-0003: 模块权重从硬编码升级为动态调优

- **Status**: proposed
- **Date**: 2026-05-09
- **Deciders**: Hermes (dev-workflow Full mode)

## Context

`ResultMerger.SOURCE_WEIGHTS` 目前硬编码在 merger.py 中（约50行静态dict）。
这些权重不会随模块的实际表现（成功率、速度、结果质量）变化而调整。

问题：
- 某模块 API 限流后质量下降，但仍被分配高权重
- 新模块默认权重1.0，可能过高或过低
- Perplexity 和 Tabbit 同样被标记为 answer 类型，但实际质量差异巨大

## Decision

引入三层权重模型：

```
final_weight = base_weight × success_rate^0.5 × quality_factor × speed_decay
```

- **base_weight**: 从现有 SOURCE_WEIGHTS 迁移（保留初始值）
- **success_rate^0.5**: perf_tracker 的请求成功率，开平方温和惩罚失败模块
- **quality_factor**: avg_result_count / expected_count（归一化到[0.5, 1.5]）
- **speed_decay**: 1/(1+speed/10) — 慢模块(>10s)轻微降权
- **更新频率**: 每100次搜索批量更新
- **手动覆盖**: `SOURCE_WEIGHT_OVERRIDE={"tabbit":1.5}` 环境变量优先级最高

**为什么不直接放弃硬编码权重？**
- 硬编码权重代表领域知识（比如已知 Wikipedia 权威），应作为基础
- 动态调优在基础之上微调，而非替代

## Consequences

**Positive:**
- 模块权重自动反映当前网络/API健康状况
- 新模块无需手动设置权重（从1.0开始，动态调整）
- 故障模块自动降权，恢复后自动升权

**Negative:**
- 权重变动可能引起搜索结果排序的扰动
  - Mitigation: 权重变化超过20%时记录WARNING日志，便于排查
- 100次搜索的更新间隔意味着短时间内故障模块影响仍存在
  - Acceptable: 熔断器(perf_tracker.should_skip) 提供分钟级保护

**Risks:**
- 权重oscillation: 降权→少调用→数据不足→错误降权
  - Mitigation: 至少10次调用后才参与动态调权
