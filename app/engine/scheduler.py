"""Search engine — parallel scheduling with adaptive two-phase strategy (v6).

v6 changes:
- QueryEnhancer integration: query analysis before search
- PerformanceTracker integration: dynamic module selection + timeout
- Enhanced intent dict format for v6 merger compatibility
"""

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
from app.engine.query_enhancer import QueryEnhancer
from app.engine.performance_tracker import perf_tracker
from app.engine.search_logger import search_logger

logger = logging.getLogger(__name__)

class SearchEngine:
    """智能调度搜索引擎 v4 — 真并行 + 质量优先 + RRF 融合"""

    # v3.0: Dynamic weight update interval (every N searches)
    _WEIGHT_UPDATE_INTERVAL = 100
    _DYNAMIC_WEIGHTS_ENABLED = True

    def __init__(self):
        self._modules: dict[str, BaseSearchModule] = {}
        self._search_count: int = 0

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
                logger.info("CDP fallback: trying %s (remaining=%.0fs)", module_name, remaining)
                result = await asyncio.wait_for(
                    module.search(request),
                    timeout=min(remaining - 5, 90)
                )
                if result:
                    elapsed = time.time() - start
                    logger.info("CDP fallback: %s succeeded in %.1fs", module_name, elapsed)
                    return SearchResponse(
                        query=request.query, results=result,
                        total=len(result), elapsed=elapsed,
                        sources_used=[module_name],
                    )
            except asyncio.TimeoutError:
                errors.append(f"{module_name}: timeout")
                logger.warning("CDP fallback: %s timed out", module_name)
            except Exception as e:
                errors.append(f"{module_name}: {str(e)[:100]}")
                logger.warning("CDP fallback: %s failed: %s", module_name, e)

        elapsed = time.time() - start
        return SearchResponse(
            query=request.query, results=[], total=0,
            elapsed=elapsed, sources_used=[],
            errors={"engine": f"All CDP modules failed: {'; '.join(errors)}"}
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        """v6 search: query enhance → intent → adaptive select → parallel → RRF + quality."""
        start = time.time()

        # Check cache
        cached = cache.get(request)
        if cached is not None:
            return cached

        # 1. Query enhancement (v6)
        analysis = QueryEnhancer.enhance(request.query, request.language)

        # Use enhanced query for search if beneficial
        search_query = analysis.enhanced_query or request.query

        # 2. Intent detection (existing + enhanced analysis)
        intent = QueryIntent.detect(search_query, analysis.language)

        # v6: Merge enhanced intent data
        if analysis.primary_type != "general":
            intent["types"].add(analysis.primary_type)
        for st in analysis.secondary_types:
            intent["types"].add(st)
        intent["hints"].add(f"lang:{analysis.language}")
        if analysis.is_question:
            intent["hints"].add("question")
        intent["confidence"] = analysis.confidence

        # 3. Module selection (existing logic + perf tracker filtering)
        if request.sources:
            selected = [s for s in request.sources if s in self._modules]
        else:
            selected = QueryIntent.select_modules(intent, self._modules)

        # v6: Filter out modules with poor performance history
        selected = [s for s in selected if not perf_tracker.should_skip(s)]

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
                metadata={"intent": intent, "engine_version": "v5"},
            )

        all_results: list[SearchResult] = []
        results_by_source: dict[str, list[SearchResult]] = {}
        sources_used: list[str] = []
        errors: dict[str, str] = {}

        tasks: dict[str, asyncio.Task] = {}
        for name in selected:
            module = self._modules[name]
            # v7: Dynamic timeout allocation based on perf history
            dyn_timeout = perf_tracker.suggest_timeout(name, default_timeout=request.timeout)
            task = asyncio.create_task(
                self._safe_search(module, request, timeout_override=dyn_timeout),
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
            phase2_timeout = max(5, request.timeout * 0.5)  # v0.4.0: 余量阶段
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
            # v5: RRF 融合后再 rerank（传入 intent 用于 freshness boost）
            all_results = ResultMerger.rerank(all_results, query=request.query, intent=intent)
        else:
            # 单源 — 用传统去重 + 重排（v0.5.0: 传入查询词）
            all_results = ResultMerger.deduplicate(all_results)
            all_results = ResultMerger.rerank(all_results, query=request.query, intent=intent)

        # v5: 不再硬置顶 tabbit，按 relevance 自然排序（已在 rerank 中加权）

        # 6. 截取
        total = len(all_results)
        all_results = all_results[: request.max_results]

        elapsed = time.time() - start

        # v6: Save performance data periodically
        perf_tracker.save()

        # v6: Convert intent sets to lists for JSON serialization
        intent_types = list(intent.get("types", set()))
        intent_hints = list(intent.get("hints", set()))

        response = SearchResponse(
            query=request.query,
            results=all_results,
            total=total,
            elapsed=round(elapsed, 3),
            sources_used=sources_used,
            errors=errors,
            metadata={
                "intent": {
                    "types": intent_types,
                    "hints": intent_hints,
                    "confidence": intent.get("confidence", 0.5),
                },
                "engine_version": "v6",
                "search_version": "2.0.0",
                "phase1_modules": list(completed_names),
                "query_analysis": {
                    "enhanced_query": analysis.enhanced_query,
                    "language": analysis.language,
                    "is_question": analysis.is_question,
                    "primary_type": analysis.primary_type,
                    "spell_corrected": analysis.spell_corrected,
                },
            },
        )

        cache.put(request, response)

        # v7: Log search for analytics
        search_logger.log_search(
            query=request.query,
            sources_used=sources_used,
            total_results=total,
            elapsed=elapsed,
            errors=errors if errors else None,
            intent=intent,
            query_analysis={
                "language": analysis.language,
                "primary_type": analysis.primary_type,
                "spell_corrected": analysis.spell_corrected,
            },
        )

        # v3.0: Periodic dynamic weight update
        self._search_count += 1
        if (
            self._DYNAMIC_WEIGHTS_ENABLED
            and self._search_count % self._WEIGHT_UPDATE_INTERVAL == 0
        ):
            self._update_dynamic_weights()

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
        module: BaseSearchModule, request: SearchRequest,
        timeout_override: float | None = None,
    ) -> list[SearchResult]:
        module_name = module.name
        start_time = time.time()
        try:
            # v7: Do NOT reset availability — let avail_cache work properly
            avail = await module.is_available()
            if not avail:
                perf_tracker.record_failure(module_name, time.time() - start_time)
                return []

            # v7: Use dynamic timeout from perf_tracker if available
            effective_timeout = timeout_override or request.timeout

            results = await asyncio.wait_for(
                module.search(request),
                timeout=effective_timeout,
            )
            elapsed = time.time() - start_time

            # v6: Record performance
            if results:
                # Estimate quality score from results
                avg_rel = sum(r.relevance for r in results) / len(results) if results else 0
                perf_tracker.record_success(
                    module_name, elapsed, len(results), avg_rel
                )
            else:
                perf_tracker.record_failure(module_name, elapsed)

            return results
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            perf_tracker.record_failure(module_name, elapsed)
            return []
        except Exception:
            elapsed = time.time() - start_time
            perf_tracker.record_failure(module_name, elapsed)
            return []

    def _update_dynamic_weights(self) -> None:
        """v3.0: Update SOURCE_WEIGHTS based on module performance.

        Uses PerformanceTracker.get_dynamic_weight() which considers
        success rate, quality score, and response speed.

        Modules need at least 5 calls before dynamic adjustment.
        Weight changes > 20% are logged as WARNING.
        """
        from app.engine.merger import ResultMerger

        updated_count = 0
        for name in self._modules:
            base_weight = ResultMerger.SOURCE_WEIGHTS.get(name, 1.0)
            perf = perf_tracker.get_performance(name)

            # Skip modules with insufficient data
            if perf.total_requests < 5:
                continue

            # Use existing dynamic weight computation
            new_weight = perf_tracker.get_dynamic_weight(name, base_weight)
            new_weight = round(new_weight, 2)

            # Only update if change is significant (> 5%)
            old_weight = ResultMerger.SOURCE_WEIGHTS.get(name, base_weight)
            change_pct = abs(new_weight - old_weight) / max(old_weight, 0.01)

            if change_pct > 0.05:
                if change_pct > 0.2:
                    logger.warning(
                        "Dynamic weight for %s: %.2f → %.2f (%.0f%% change, sr=%.2f, q=%.2f)",
                        name, old_weight, new_weight, change_pct * 100,
                        perf.success_rate, perf.avg_quality_score,
                    )
                else:
                    logger.info(
                        "Dynamic weight for %s: %.2f → %.2f",
                        name, old_weight, new_weight,
                    )
                ResultMerger.SOURCE_WEIGHTS[name] = new_weight
                updated_count += 1

        if updated_count > 0:
            logger.info("Dynamic weights updated: %d modules", updated_count)


# Global instance
