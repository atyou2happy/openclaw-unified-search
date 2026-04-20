#!/usr/bin/env python3
"""unified-search 搜索质量 Benchmark

用法：
  python benchmark.py                    # 运行全部测试
  python benchmark.py --quick             # 快速模式（5题）
  python benchmark.py --url URL           # 指定 US 地址

输出：data/benchmark-history.json（追加记录）
"""

import json
import os
import sys
import time
import httpx

US_URL = os.environ.get("US_URL", "http://localhost:8900")
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark-history.json")

# 标准测试集（20题）
FULL_TESTS = [
    # 编程
    {"q": "Python async await 用法", "expect_keywords": ["async", "await", "coroutine"], "category": "编程"},
    {"q": "Rust ownership 所有权", "expect_keywords": ["ownership", "borrow", "lifetime"], "category": "编程"},
    {"q": "Docker Compose 多容器编排", "expect_keywords": ["docker", "compose", "container"], "category": "DevOps"},
    {"q": "git rebase 和 merge 区别", "expect_keywords": ["rebase", "merge", "commit"], "category": "编程"},
    # AI/ML
    {"q": "Transformer attention mechanism", "expect_keywords": ["attention", "query", "key", "value"], "category": "AI"},
    {"q": "RAG 检索增强生成", "expect_keywords": ["retrieval", "generation", "augmented"], "category": "AI"},
    {"q": "LoRA 微调大模型", "expect_keywords": ["lora", "fine-tun", "adapter"], "category": "AI"},
    {"q": "RLHF 人类反馈强化学习", "expect_keywords": ["rlhf", "reinforcement", "human", "feedback"], "category": "AI"},
    # 科技新闻
    {"q": "2026年 AI 最新进展", "expect_keywords": ["ai", "model", "2026"], "category": "新闻"},
    {"q": "开源大模型排行榜", "expect_keywords": ["open", "source", "model", "benchmark"], "category": "AI"},
    # 工具/项目
    {"q": "vLLM 部署大模型推理", "expect_keywords": ["vllm", "inference", "deploy"], "category": "工具"},
    {"q": "Meilisearch 搜索引擎", "expect_keywords": ["meilisearch", "search"], "category": "工具"},
    {"q": "SearXNG 元搜索引擎", "expect_keywords": ["searxng", "meta", "search"], "category": "工具"},
    {"q": "Ollama 本地模型运行", "expect_keywords": ["ollama", "local", "model"], "category": "工具"},
    # 知识库（本地）
    {"q": "unified-search 多模块搜索", "expect_keywords": ["unified", "search", "module"], "category": "知识库"},
    {"q": "OpenClaw 插件系统", "expect_keywords": ["openclaw", "plugin"], "category": "知识库"},
    {"q": "CDP Chrome DevTools Protocol", "expect_keywords": ["cdp", "chrome", "devtools"], "category": "知识库"},
    # 中文
    {"q": "A股市场情绪分析", "expect_keywords": ["A股", "情绪", "分析"], "category": "财经"},
    {"q": "微信公众号文章自动化", "expect_keywords": ["微信", "公众号", "自动化"], "category": "工具"},
    {"q": "Kilocode AI编码助手", "expect_keywords": ["kilocode", "ai", "cod"], "category": "工具"},
]

QUICK_TESTS = FULL_TESTS[:5]


def run_search(query: str, timeout: int = 30) -> dict:
    """调用 unified-search API"""
    try:
        r = httpx.post(
            f"{US_URL}/search",
            json={"query": query, "max_results": 5},
            timeout=timeout,
            trust_env=False,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}", "results": []}
    except Exception as e:
        return {"error": str(e), "results": []}


def score_result(result: dict, test: dict) -> float:
    """评分：关键词命中率"""
    if "error" in result:
        return 0.0
    
    results = result.get("results", [])
    if not results:
        return 0.0
    
    # 检查前 3 个结果是否包含期望关键词
    hits = 0
    total_keywords = len(test["expect_keywords"])
    
    for r in results[:3]:
        text = (r.get("title", "") + " " + r.get("snippet", "") + " " + r.get("content", "")).lower()
        for kw in test["expect_keywords"]:
            if kw.lower() in text:
                hits += 1
    
    # 归一化到 0-1
    return min(hits / max(total_keywords, 1), 1.0)


def run_benchmark(tests: list) -> dict:
    """运行 benchmark"""
    results = []
    total_score = 0
    total_time = 0
    
    for i, test in enumerate(tests):
        t0 = time.time()
        result = run_search(test["q"])
        elapsed = time.time() - t0
        
        score = score_result(result, test)
        total_score += score
        total_time += elapsed
        
        status = "✅" if score >= 0.5 else "❌" if score < 0.2 else "⚠️"
        results.append({
            "query": test["q"],
            "category": test["category"],
            "score": round(score, 2),
            "elapsed": round(elapsed, 2),
            "status": status,
            "n_results": len(result.get("results", [])),
            "error": result.get("error"),
        })
        
        print(f"  {status} [{test['category']}] {test['q'][:30]:30s} score={score:.2f} time={elapsed:.1f}s n={len(result.get('results', []))}")
    
    avg_score = total_score / len(tests) if tests else 0
    avg_time = total_time / len(tests) if tests else 0
    
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tests": len(tests),
        "avg_score": round(avg_score, 3),
        "avg_time": round(avg_time, 2),
        "total_time": round(total_time, 2),
        "results": results,
    }


def save_history(entry: dict):
    """追加到历史记录"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    history = []
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            history = json.load(f)
    history.append(entry)
    # 只保留最近 30 次
    if len(history) > 30:
        history = history[-30:]
    with open(STATE_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    url_idx = sys.argv.index("--url") + 1 if "--url" in sys.argv else None
    if url_idx and url_idx < len(sys.argv):
        US_URL = sys.argv[url_idx]
    
    tests = QUICK_TESTS if quick else FULL_TESTS
    
    print(f"🔍 unified-search Benchmark")
    print(f"   URL: {US_URL}")
    print(f"   Tests: {len(tests)} ({'quick' if quick else 'full'})")
    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    entry = run_benchmark(tests)
    
    print()
    print(f"📊 结果:")
    print(f"   平均分: {entry['avg_score']:.3f}")
    print(f"   平均耗时: {entry['avg_time']:.2f}s")
    print(f"   总耗时: {entry['total_time']:.1f}s")
    
    # 分类统计
    categories = {}
    for r in entry["results"]:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"score": 0, "count": 0}
        categories[cat]["score"] += r["score"]
        categories[cat]["count"] += 1
    
    print(f"\n   分类:")
    for cat, data in sorted(categories.items()):
        avg = data["score"] / data["count"]
        print(f"     {cat}: {avg:.2f} ({data['count']}题)")
    
    save_history(entry)
    print(f"\n   已保存到 {STATE_FILE}")
