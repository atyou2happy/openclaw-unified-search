# ADR-0002: SimHash 用于搜索结果近重复检测

- **Status**: proposed
- **Date**: 2026-05-09
- **Deciders**: Hermes (dev-workflow Full mode)

## Context

当前去重策略只有两层：
1. URL归一化（去www、tracking参数、fragment）
2. 标题相似度 > 0.8（SequenceMatcher）

问题：两个不同URL描述完全相同的内容（例如：同一篇新闻在不同网站转载），上述策略全部无法检测。
在模块多样化的元搜索场景下，这种跨源重复非常常见。

## Decision

引入 **SimHash 64-bit指纹** 进行内容级近重复检测。

算法流程：
1. 对 snippet + title 提取特征（分词 → 每个词hash到64-bit → 加权 → 按位求和 → sign）
2. 计算两个SimHash的 Hamming distance
3. Hamming distance < 3 → 视为近重复 → 保留 relevance 更高的

**为什么选SimHash而非MinHash？**
- SimHash生成固定大小指纹(64-bit = 8 bytes)，比MinHash的签名矩阵节省空间
- Hamming distance计算是O(1)（XOR + popcount），比Jaccard相似度快
- Google F. Saditile 用于网页去重的成熟方案

**为什么不直接比Jaccard相似度？**
- Jaccard需要保存两个集合求交集，对于后处理场景的pairwise比较是O(n²*k)，k是词数
- SimHash把每个文档压缩到64-bit，pairwise比较是O(n²)，常数极小

## Consequences

**Positive:**
- 有效检测跨源内容重复
- 内存占用极小（每个结果+8 bytes）
- 纯Python实现，无需外部依赖
- Hamming distance阈值可调

**Negative:**
- SimHash有概率碰撞（不同文档产生相同hash）
  - 64-bit空间足够大，碰撞概率极低（< 2^-64）
- 对极短内容（标题<10字）的指纹区分度差
  - Mitigation: 极短内容跳过SimHash，走标题相似度路径

**Risks:**
- 中文SimHash效果：中文需要分词后才能hash
  - Mitigation: 简单2-gram分词，效果一般但足够用于去重
