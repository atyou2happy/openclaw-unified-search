#!/usr/bin/env python3
"""
Unified Search CLI — 命令行搜索工具

Usage:
    python search_cli.py "你的搜索问题"
    python search_cli.py "query" --sources github,academic
    python search_cli.py "query" --depth deep --max-results 5
"""

import argparse
import asyncio
import json
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import SearchRequest
from app.engine import engine
from app.modules import auto_register


def format_results(response):
    """Format search results for display."""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"Query: {response.query}")
    lines.append(f"Sources: {', '.join(response.sources_used) or 'none'}")
    lines.append(f"Results: {response.total} | Elapsed: {response.elapsed}s | Cached: {response.cached}")
    lines.append(f"{'='*60}")

    for i, r in enumerate(response.results, 1):
        lines.append(f"\n[{i}] {r.title}")
        lines.append(f"    Source: {r.source} | Relevance: {r.relevance:.2f}")
        if r.url:
            lines.append(f"    URL: {r.url}")
        if r.snippet:
            lines.append(f"    {r.snippet[:200]}")
        if r.metadata:
            meta_parts = [f"{k}={v}" for k, v in r.metadata.items() if v]
            if meta_parts:
                lines.append(f"    Meta: {', '.join(meta_parts[:5])}")

    if response.errors:
        lines.append(f"\n⚠️ Errors:")
        for name, err in response.errors.items():
            lines.append(f"  {name}: {err}")

    return "\n".join(lines)


async def do_search(args):
    """Execute search."""
    auto_register()
    engine.load_modules()

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else []

    request = SearchRequest(
        query=args.query,
        sources=sources,
        max_results=args.max_results,
        timeout=args.timeout,
        depth=args.depth,
        language=args.language,
    )

    if args.module:
        response = await engine.search_module(args.module, request)
    else:
        response = await engine.search(request)

    if args.json:
        print(json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str))
    else:
        print(format_results(response))


def main():
    parser = argparse.ArgumentParser(description="Unified Search CLI")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--sources", default="", help="Comma-separated module names (default: all)")
    parser.add_argument("--module", default="", help="Single module name to search")
    parser.add_argument("--max-results", type=int, default=10, help="Max results per module")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--depth", default="normal", choices=["quick", "normal", "deep"])
    parser.add_argument("--language", default="auto", help="Language: auto|zh|en")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    asyncio.run(do_search(args))


if __name__ == "__main__":
    main()
