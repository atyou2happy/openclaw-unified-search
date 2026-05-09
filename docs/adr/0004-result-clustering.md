# ADR-0004: n-gram 单遍聚类用于实时搜索结果分组

- **Status**: proposed
- **Date**: 2026-05-09
- **Deciders**: Hermes (dev-workflow Full mode)

## Context

search API 返回的15条结果混合了多个主题。用户（或下游Agent）可能只关心其中的1-2个主题，
但需要逐条浏览才能发现。搜索结果聚类可以快速呈现主题结构。

## Decision

采用 **n-gram Overlap + Single-Pass Clustering** 在线算法。

算法：
```
for each result in sorted_results:
    best_cluster = None
    best_overlap = 0
    for each existing_cluster:
        overlap = ngram_overlap(result.title+snippet, cluster.centroid)
        if overlap > best_overlap:
            best_cluster = cluster
            best_overlap = overlap
    if best_overlap > threshold:
        add result to best_cluster
        update cluster.centroid
    else:
        create new cluster with result as centroid
```

参数：
- n-gram: bigram（中文）+ word unigram（英文）
- overlap threshold: 0.25（至少25%的bigram重叠才归入同一cluster）
- max clusters: min(result_count / 3, 5)（15条 → 最多5个cluster）
- min cluster size: 2（只有1条的不算cluster）

输出：在 result.metadata 中添加 `cluster_id` 和 `cluster_label`

**为什么不选 K-Means？**
- K-Means需要预设K值且需要向量表示
- 我们的场景只有15-20条结果，不需要复杂的聚类算法
- Single-pass 是在线算法，天然适合流式处理

**为什么不选 LDA/主题模型？**
- 需要大量文本训练，不适合实时场景
- 依赖外部模型库

## Consequences

**Positive:**
- 用户可快速判断结果的主题分布
- 极轻量（15条结果聚类 < 5ms）
- 纯Python，无依赖
- 聚类结果注入metadata，不影响现有API结构

**Negative:**
- Bigram重叠是粗糙的相似度度量，可能误聚类
  - Mitigation: 阈值设为0.25（保守），宁可多分cluster也不错合并
- 对混合语言结果（中英混杂）效果差
  - Acceptable: 当前场景中英分开展示

**Risks:**
- 所有结果同主题时只有一个cluster
  - Expected behavior: 这恰好是用户想看到的
