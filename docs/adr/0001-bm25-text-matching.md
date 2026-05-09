# ADR-0001: BM25-lite 替代 SequenceMatcher 做文本匹配

- **Status**: proposed
- **Date**: 2026-05-09
- **Deciders**: Hermes (dev-workflow Full mode)

## Context

当前 merger.py 的 rerank() 使用 Python `difflib.SequenceMatcher` 计算查询与标题/摘要的相似度。
SequenceMatcher 基于 Ratcliff-Obershelp 算法（编辑距离变种），存在以下问题：
1. 对长文本效率低（O(n²) 最坏情况）
2. 不考虑词频分布（"the"和"Python"权重相同）
3. 无法处理多词查询的词汇重要性差异

## Decision

实现 **BM25-lite**（Okapi BM25 的轻量实现）替代 SequenceMatcher。

```
BM25(q, d) = Σ IDF(qi) × (TF(qi,d) × (k1+1)) / (TF(qi,d) + k1×(1-b+b×|d|/avgdl))
```

参数：k1=1.2, b=0.75（标准值）

**为什么不用 pyterrier/rank_bm25 等库？**
- 项目原则：零外部依赖。BM25的数学很简单，~50行纯Python即可实现。
- 避免引入numpy/scipy等重量级依赖。

**为什么保留 SequenceMatcher 作为 fallback？**
- 渐进迁移策略（原则 #14 Token最小化思想：保守重构）
- 通过 `Config.BM25_ENABLED` 环境变量控制，默认启用
- 1周验证期后移除旧路径

## Consequences

**Positive:**
- BM25 是信息检索领域最广泛验证的排名函数之一，相关性显著优于编辑距离
- 词级别匹配 + IDF权重，解决停用词干扰问题
- O(n) 复杂度，比 SequenceMatcher 的 O(n²) 更快
- 零外部依赖

**Negative:**
- 需要维护两套文本匹配路径（过渡期）
- BM25的参数(k1, b)虽然标准值效果好，但`avgdl`依赖每次搜索的结果集

**Risks:**
- 中文分词：简单的2-gram/字级别分词可能损失精度
  - Mitigation: 中文用bigram+unigram混合，英文用空格分词
- 冷启动：第一次搜索时avgdl未知
  - Mitigation: 默认avgdl=100字(合理初始值)
