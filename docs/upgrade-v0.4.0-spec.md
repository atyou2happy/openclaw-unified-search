# unified-search v0.4.0 升级规格

> 日期：2026-04-25 | 模式：dev-workflow Full | 目标：v0.3.0 → v0.4.0

## 背景

unified-search 当前 30 模块（22 可用），v0.3.0 已稳定运行。通过实际使用和代码审计发现以下需改进的问题。

## 问题清单（按优先级）

### P0 — 必须修复

| ID | 问题 | 根因 | 修复方案 |
|----|------|------|---------|
| P0-1 | **搜索速度慢**（5模块 20s+） | ① 每次搜索前逐个 `is_available()` 串行检查；② phase1_timeout 最高 45s；③ 无并发上限 | ① 可用性结果缓存（TTL 60s），避免每次重新检查；② phase1 默认 15s；③ 添加 `asyncio.Semaphore(MAX_CONCURRENT)` |
| P0-2 | **缓存空结果导致"搜不到"** | `cache.put()` 不检查结果是否为空 | `put()` 加守卫：空结果不缓存（或短 TTL 60s） |
| P0-3 | **默认 timeout=120s 过高** | `cdp_search_fallback` 用 `request.timeout or 120` | 默认降至 30s（与 `SearchRequest.timeout` 默认值一致） |

### P1 — 应该修复

| ID | 问题 | 修复方案 |
|----|------|---------|
| P1-1 | **API 无 execution_time_ms** | `SearchResponse` 已有 `elapsed` 字段，确认路由层正确返回；添加 `metadata.execution_time_ms` |
| P1-2 | **不可用模块 reason: null** | `ModuleStatus` 已有 `last_error` 字段，`health/detailed` 端点需收集并填充错误信息 |
| P1-3 | **版本管理混乱** | 创建 `app/version.py`，`main.py` 引用；所有 API 返回 `version` 字段 |
| P1-4 | **conda 启动不稳定** | 心跳已用绝对路径 python，更新文档/脚本统一用绝对路径启动 |

### P2 — 改进

| ID | 问题 | 修复方案 |
|----|------|---------|
| P2-1 | **无 benchmark 数据** | 完善 `benchmark.py`，运行并保存结果 |
| P2-2 | **TabBit 模块联调未完成** | 联调测试（需 TabBitBrowser 运行） |

## 设计文档

### 1. 可用性缓存（解决 P0-1 的核心）

```python
# engine.py — 新增
class AvailabilityCache:
    """模块可用性缓存，避免每次搜索都检查"""
    def __init__(self, ttl: int = 60):
        self._cache: dict[str, tuple[bool, float]] = {}
        self._ttl = ttl
    
    def get(self, module_name: str) -> bool | None:
        if module_name in self._cache:
            available, ts = self._cache[module_name]
            if time.time() - ts < self._ttl:
                return available
        return None
    
    def set(self, module_name: str, available: bool):
        self._cache[module_name] = (available, time.time())
    
    def invalidate(self, module_name: str = None):
        if module_name:
            self._cache.pop(module_name, None)
        else:
            self._cache.clear()
```

**修改 `engine.search()` 中的可用性检查**：
- Before: 逐个 `await module.is_available()` → N 次网络请求
- After: 先查缓存 → 命中直接用 → 未命中才检查并缓存

### 2. 空结果不缓存（解决 P0-2）

```python
# cache.py — put() 添加守卫
def put(self, request, response):
    if not response.results:  # 空结果不缓存
        return
    # ... 原有逻辑
```

### 3. 超时优化（解决 P0-3）

- `cdp_search_fallback`: `timeout = request.timeout or 30`（从 120 降至 30）
- `search()`: phase1_timeout 从 `min(timeout*0.6, 45)` 降至 `min(timeout*0.5, 15)`
- 新增 `Config.SEARCH_TIMEOUT = 30` 统一管理

### 4. 模块错误信息（解决 P1-2）

```python
# health/detailed 端点改进
results[name] = {
    "description": m.description,
    "status": status,
    "available": healthy,
    "error": getattr(m, '_last_error', None),  # 新增
}
```

### 5. 版本管理（解决 P1-3）

创建 `app/version.py`:
```python
__version__ = "0.4.0"
```

`main.py` 和 `/health` 端点引用此版本。

## Tasks 拆分

### Feature: 性能优化 + Bug修复（>200行，GLM-5.1）

| Task | 说明 | 预估行数 |
|------|------|---------|
| T1 | 可用性缓存（AvailabilityCache） | 80行 |
| T2 | 空结果缓存守卫 | 10行 |
| T3 | 超时参数优化 | 20行 |
| T4 | 版本管理（version.py + API） | 30行 |
| T5 | 模块错误信息填充 | 30行 |
| T6 | benchmark.py 完善 | 50行 |
| T7 | 测试更新（36个现有 + 新增） | 80行 |
| T8 | 文档更新（README + CHANGELOG） | 50行 |

## 成功标准

1. ✅ 5模块搜索 < 5s（从 20s 降至 5s 内）
2. ✅ 空结果不被缓存
3. ✅ 默认 timeout = 30s
4. ✅ `/health` 和 `/health/detailed` 返回版本号
5. ✅ `/health/detailed` 不可用模块有错误原因
6. ✅ 所有现有 36 个测试通过
7. ✅ 新增测试覆盖可用性缓存 + 空结果守卫

## 风险

- TabBitBrowser 模块联调（P2-2）需要 TabBitBrowser 运行，暂不包含在此版本
- 可用性缓存 TTL 60s 可能导致刚挂的模块 60s 内仍被认为可用 → 可接受，搜索会优雅降级
