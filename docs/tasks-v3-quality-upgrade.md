# unified-search v3.0 任务清单

| ID | 模块 | 文件 | 描述 | 依赖 | 预估 |
|----|------|------|------|------|------|
| T01 | BM25引擎 | app/engine/text_scorer.py | 实现BM25-lite: tokenize, compute_tf, compute_idf, bm25_score, bm25_batch_rank | 无 | 1h |
| T02 | BM25测试 | tests/test_text_scorer.py | 测试: tokenize(中英), tf计算, idf计算, bm25排名, 边界(空输入) | T01 | 30m |
| T03 | BM25集成 | app/engine/merger.py | rerank()中BM25替代SequenceMatcher，Config.BM25_ENABLED控制 | T01 | 20m |
| T04 | 自适应RRF | app/engine/merger.py | rrf_fuse()中自适应k + 共识增强(positions加权) | 无 | 30m |
| T05 | 自适应RRF测试 | tests/test_merger.py | 测试: k自适应(小/中/大结果集), 共识增强 | T04 | 30m |
| T06 | SimHash去重 | app/engine/merger.py | _compute_simhash(), _hamming_distance(), 在rerank()中插入去重逻辑 | 无 | 1h |
| T07 | SimHash测试 | tests/test_merger.py | 测试: simhash计算, 不同hamming距离去重, 边界 | T06 | 30m |
| T08 | 动态权重 | app/engine/scheduler.py | 新增_compute_dynamic_weights(), 每100次搜索更新SOURCE_WEIGHTS | 无 | 1h |
| T09 | 动态权重测试 | tests/test_scheduler.py | 测试: 权重计算, 成功率影响, 质量因子, 收敛 | T08 | 30m |
| T10 | 词权重 | app/engine/query_enhancer.py | 新增_get_term_weights(), 缩写检测_expand_acronyms(), query变体生成 | 无 | 1h |
| T11 | 查询增强测试 | tests/test_query_enhancer.py | 测试: 词权重分配, 缩写展开, 变体生成 | T10 | 30m |
| T12 | 结果聚类 | app/engine/result_clustering.py | 实现n-gram单遍聚类, 关键词提取, metadata注入 | 无 | 1h |
| T13 | 聚类测试 | tests/test_result_clustering.py | 测试: 基本聚类, 不同cluster数, 关键词提取, 边界 | T12 | 30m |
| T14 | 聚类集成 | app/engine/merger.py | rerank()最后调用ResultClustering.cluster()注入metadata | T12 | 15m |
| T15 | 模型更新 | app/models.py | 无需改(聚类信息走metadata), 确认SearchResult.metadata支持 | T12 | 10m |
| T16 | 回归测试 | tests/ | 全量测试通过, 验证无现有功能回归 | T01-T15 | 30m |
| T17 | Benchmark | scripts/ | benchmark 20题跑分, 对比v2.1基线 | T16 | 20m |
| T18 | README | README.md, README_CN.md | 更新版本号, 新模块数, 新特性, 致谢表 | T16 | 30m |
| T19 | 版本号 | app/version.py | 2.1.0 → 3.0.0 | 无 | 5m |
| T20 | Commit+Push | git | conventional commit: feat: v3.0.0 search quality deep upgrade | T18,T19 | 5m |
