"""Search engine — parallel module dispatch + result merging."""

import asyncio
import time
from app.models import SearchRequest, SearchResponse, SearchResult
from app.modules import get_all, get
from app.modules.base import BaseSearchModule
from app.cache import cache


class SearchEngine:
    """Orchestrates search across all modules."""

    def __init__(self):
        self._modules: dict[str, BaseSearchModule] = {}

    def load_modules(self):
        """Load all registered modules."""
        from app.modules import get_all
        self._modules = get_all()

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Execute search across modules, merge and rank results."""
        start = time.time()

        # Check cache
        cached = cache.get(request)
        if cached is not None:
            return cached

        # Determine which modules to use
        if request.sources:
            modules = {
                name: m for name, m in self._modules.items()
                if name in request.sources
            }
        else:
            modules = dict(self._modules)

        # No matching modules — return empty
        if not modules:
            elapsed = time.time() - start
            return SearchResponse(
                query=request.query,
                elapsed=round(elapsed, 3),
                errors={"engine": "No matching modules found"},
            )

        # Parallel search with per-module timeout
        tasks = {}
        for name, module in modules.items():
            tasks[name] = asyncio.create_task(
                self._safe_search(module, request)
            )

        # Wait for all with overall timeout
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=request.timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        # Cancel any pending
        for task in pending:
            task.cancel()

        # Collect results
        all_results: list[SearchResult] = []
        sources_used: list[str] = []
        errors: dict[str, str] = {}

        for name, task in tasks.items():
            if task in done:
                try:
                    results = task.result()
                    if results:
                        all_results.extend(results)
                        sources_used.append(name)
                except Exception as e:
                    errors[name] = str(e)

        # Sort by relevance (descending)
        all_results.sort(key=lambda r: r.relevance, reverse=True)

        # Trim to max_results overall
        total = len(all_results)
        all_results = all_results[:request.max_results]

        elapsed = time.time() - start

        response = SearchResponse(
            query=request.query,
            results=all_results,
            total=total,
            elapsed=round(elapsed, 3),
            sources_used=sources_used,
            errors=errors,
        )

        # Store in cache
        cache.put(request, response)

        return response

    async def search_module(self, module_name: str, request: SearchRequest) -> SearchResponse:
        """Search a single specific module."""
        module = get(module_name)
        if not module:
            return SearchResponse(
                query=request.query,
                errors={module_name: f"Module '{module_name}' not found"},
                elapsed=0,
            )

        start = time.time()
        try:
            results = await self._safe_search(module, request)
            elapsed = time.time() - start
            return SearchResponse(
                query=request.query,
                results=results[:request.max_results],
                total=len(results),
                elapsed=round(elapsed, 3),
                sources_used=[module_name],
            )
        except Exception as e:
            return SearchResponse(
                query=request.query,
                errors={module_name: str(e)},
                elapsed=round(time.time() - start, 3),
            )

    @staticmethod
    async def _safe_search(module: BaseSearchModule, request: SearchRequest) -> list[SearchResult]:
        """Safely call module search with error handling."""
        try:
            if not await module.is_available():
                return []
            return await module.search(request)
        except Exception:
            return []


# Global engine instance
engine = SearchEngine()
