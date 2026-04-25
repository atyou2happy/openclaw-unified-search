"""Search engine — parallel scheduling with two-phase strategy."""

import asyncio
import logging
import time
from app.models import SearchRequest, SearchResponse, SearchResult
from app.modules import get
from app.modules.base import BaseSearchModule
from app.cache import cache
from app.engine.availability import avail_cache
from app.engine.intent import QueryIntent
from app.engine.merger import ResultMerger

logger = logging.getLogger(__name__)

class SearchEngine:
    """智能调度搜索引擎 v4 — 真并行 + 质量优先 + RRF 融合"""

    def __init__(self):
        self._modules: dict[str, BaseSearchModule] = {}

    def load_modules(self):
        from app.modules import get_all

        self._modules = get_all()

    async def cdp_search_fallback(self, request: SearchRequest) -> SearchResponse:
        """CDP AI Agent 降级搜索 — 按质量排序，失败自动降级

        策略：从 CDP_FALLBACK_CHAIN 中依次尝试，第一个成功即返回。
        如果用户指定了 sources，则从 chain 中筛选匹配的模块。
        """
        start = time.time()
        timeout = request.timeout or 30  # v0.4.0: lowered from 120

        # Determine which CDP modules to try
        if request.sources:
            # User specified sources: filter from fallback chain, preserving order
            cdp_modules = [m for m in QueryIntent.CDP_FALLBACK_CHAIN if m in request.sources]
        else:
            cdp_modules = list(QueryIntent.CDP_FALLBACK_CHAIN)

        # Filter to only available modules
        cdp_modules = [m for m in cdp_modules if m in self._modules]

        if not cdp_modules:
            return SearchResponse(
                query=request.query, results=[], total=0,
                elapsed=time.time() - start, sources_used=[],
                errors={"engine": "No CDP modules available"}
            )

        errors = []
        for module_name in cdp_modules:
            module = self._modules[module_name]
            remaining = timeout - (time.time() - start)
            if remaining < 10:
                errors.append(f"{module_name}: timeout budget exhausted")
                continue

            try:
                print(f"CDP fallback: trying {module_name} (remaining={remaining:.0f}s)")
                result = await asyncio.wait_for(
                    module.search(request),
                    timeout=min(remaining - 5, 90)
                )
                if result:
                    elapsed = time.time() - start
                    print(f"CDP fallback: {module_name} succeeded in {elapsed:.1f}s")
                    return SearchResponse(
                        query=request.query, results=result,
                        total=len(result), elapsed=elapsed,
                        sources_used=[module_name],
                    )
            except asyncio.TimeoutError:
                errors.append(f"{module_name}: timeout")
                print(f"CDP fallback: {module_name} timed out")
            except Exception as e:
                errors.append(f"{module_name}: {str(e)[:100]}")
                print(f"CDP fallback: {module_name} failed: {e}")

        elapsed = time.time() - start
        return SearchResponse(
            query=request.query, results=[], total=0,
            elapsed=elapsed, sources_used=[],
            errors={"engine": f"All CDP modules failed: {'; '.join(errors)}"}
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        """v4 搜索：意图识别 → tabbit 始终选中 → 真并行调度 → RRF 融合"""
        start = time.time()

        # Check cache
        cached = cache.get(request)
        if cached is not None:
            return cached

        # 1. 意图识别
        intent = QueryIntent.detect(request.query, request.language)

        # 2. 选择模块（tabbit 始终在列）
        if request.sources:
            selected = [s for s in request.sources if s in self._modules]
            # 用户明确指定 sources 时不再强制加 tabbit
        else:
            selected = QueryIntent.select_modules(intent, self._modules)

        if not selected:
            return SearchResponse(
                query=request.query,
                elapsed=round(time.time() - start, 3),
                errors={"engine": "No matching modules found"},
            )

        # 过滤掉不可用的模块（v0.4.0: 用缓存避免串行检查）
        available_selected = []
        check_tasks = {}
        for name in selected:
            cached = avail_cache.get(name)
            if cached is True:
                available_selected.append(name)
            elif cached is False:
                logger.debug(f"Module {name} not available (cached), skipping")
            else:
                # 未缓存，需要检查
                module = self._modules[name]
                module.reset_availability()
                check_tasks[name] = module.is_available()

        if check_tasks:
            results = await asyncio.gather(*check_tasks.values(), return_exceptions=True)
            for (name, _), result in zip(check_tasks.items(), results):
                avail = result if isinstance(result, bool) else False
                avail_cache.set(name, avail)
                if avail:
                    available_selected.append(name)
                else:
                    logger.debug(f"Module {name} not available, skipping")

        selected = available_selected

        if not selected:
            return SearchResponse(
                query=request.query,
                elapsed=round(time.time() - start, 3),
                results=[],
                total=0,
                sources_used=[],
                errors={"engine": "All selected modules unavailable"},
                metadata={"intent": intent, "engine_version": "v4"},
            )

        all_results: list[SearchResult] = []
        results_by_source: dict[str, list[SearchResult]] = {}
        sources_used: list[str] = []
        errors: dict[str, str] = {}

        tasks: dict[str, asyncio.Task] = {}
        for name in selected:
            module = self._modules[name]
            task = asyncio.create_task(
                self._safe_search(module, request),
                name=f"search_{name}",
            )
            tasks[name] = task

        # Phase 2: 等待结果 — 用 FIRST_COMPLETED 逐个收集
        min_results = max(3, request.max_results // 2)
        phase1_timeout = min(request.timeout * 0.5, 15)  # v0.4.0: 快阶段 15s 上限
        phase1_start = time.time()

        pending = set(tasks.values())
        completed_names: set[str] = set()

        while pending:
            # 计算剩余超时
            remaining_time = phase1_timeout - (time.time() - phase1_start)
            if remaining_time <= 0:
                break

            try:
                done, pending = await asyncio.wait(
                    pending,
                    timeout=remaining_time,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except Exception:
                break

            if not done:
                break

            # 收集完成的结果
            for task in done:
                task_name = task.get_name()
                module_name = task_name.replace("search_", "")

                try:
                    results = task.result()
                    if results:
                        results_by_source[module_name] = results
                        all_results.extend(results)
                        sources_used.append(module_name)
                    completed_names.add(module_name)
                except asyncio.TimeoutError:
                    errors[module_name] = "timeout"
                    completed_names.add(module_name)
                except Exception as e:
                    errors[module_name] = str(e)
                    completed_names.add(module_name)

            # 检查是否有足够结果 + tabbit 已返回
            tabbit_done = "tabbit" in completed_names
            if tabbit_done and len(all_results) >= min_results:
                break

        # Phase 3: 取消仍在 pending 的任务（如果已经有足够结果）
        remaining_tasks = set(pending)
        if len(all_results) >= min_results:
            for task in remaining_tasks:
                task.cancel()
        else:
            phase2_timeout = max(3, request.timeout * 0.5)  # v0.4.0: 余量阶段
            if remaining_tasks:
                try:
                    done2, still_pending = await asyncio.wait(
                        remaining_tasks,
                        timeout=phase2_timeout,
                        return_when=asyncio.ALL_COMPLETED,
                    )
                    for task in done2:
                        task_name = task.get_name()
                        module_name = task_name.replace("search_", "")
                        try:
                            results = task.result()
                            if results:
                                results_by_source[module_name] = results
                                all_results.extend(results)
                                sources_used.append(module_name)
                        except Exception:
                            pass
                    for task in still_pending:
                        task.cancel()
                except Exception:
                    for task in remaining_tasks:
                        task.cancel()

        # 4. RRF 融合（如果有多个源）
        if len(results_by_source) > 1:
            all_results = ResultMerger.rrf_fuse(results_by_source)
        else:
            # 单源 — 用传统去重 + 重排（v0.5.0: 传入查询词）
            all_results = ResultMerger.deduplicate(all_results)
            all_results = ResultMerger.rerank(all_results, query=request.query)

        # 5. Tabbit 结果置顶（如果有）
        tabbit_results = [r for r in all_results if r.source == "tabbit"]
        other_results = [r for r in all_results if r.source != "tabbit"]
        if tabbit_results:
            all_results = tabbit_results + other_results

        # 6. 截取
        total = len(all_results)
        all_results = all_results[: request.max_results]

        elapsed = time.time() - start

        response = SearchResponse(
            query=request.query,
            results=all_results,
            total=total,
            elapsed=round(elapsed, 3),
            sources_used=sources_used,
            errors=errors,
            metadata={
                "intent": {
                    "types": list(intent["types"]),
                    "hints": list(intent["hints"]),
                },
                "engine_version": "v4",
                "search_version": "0.5.0",
                "phase1_modules": list(completed_names),
            },
        )

        cache.put(request, response)
        return response

    async def search_module(
        self, module_name: str, request: SearchRequest
    ) -> SearchResponse:
        """搜索单个指定模块"""
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
                results=results[: request.max_results],
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
    async def _safe_search(
        module: BaseSearchModule, request: SearchRequest
    ) -> list[SearchResult]:
        try:
            # Reset cached availability so it re-checks
            module.reset_availability()
            avail = await module.is_available()
            if not avail:
                return []
            results = await module.search(request)
            return results
        except Exception:
            return []


# Global instance
