# Refactor Spec v1.0 — openclaw-unified-search

> 版本: 1.0.0 | 日期: 2026-05-07 | 范围: A+B+C+D 全量重构

---

## 1. 背景与动机

当前 v0.9.5 代码存在以下问题影响可维护性和性能：

1. **每次 HTTP 请求创建新的 httpx.AsyncClient**（38 个模块，20+ 处），浪费连接资源
2. **FastAPI 废弃 API** `@app.on_event("startup")` — 不支持 async cleanup
3. **配置路径硬编码** — config.py 向上 4 级目录导航
4. **CDP 连接池用全局变量** — 难以测试和扩展
5. **7 处 print()** 替代 logger
6. **10+ 处静默吞异常** except...pass
7. **测试分层不足** — 现有测试偏集成，纯逻辑覆盖不全

## 2. 设计目标

- **性能提升**: httpx 连接池复用，减少 TCP 握手开销
- **架构现代化**: FastAPI lifespan + async 安全
- **代码质量**: 消除 print、静默异常、全局变量
- **测试分层**: Unit(多) → Business(中) → Integration(少)
- **向后兼容**: 所有外部 API 端点不变，模块接口不变

## 3. 不做什么清单

- **不改变 API 端点** — 所有 /search, /health, /modules 路径不变
- **不删除任何搜索模块** — 38 个模块全部保留
- **不改变数据模型** — SearchRequest/SearchResponse/SearchResult 不变
- **不引入新依赖** — 只用现有的 httpx/FastAPI/pydantic
- **不改变 RRF 融合算法** — merger.py 逻辑不变
- **不改变意图识别** — intent.py 模块选择逻辑不变
- **不升级 Python 版本要求** — 保持 >=3.10

## 4. 架构变更

### 4.1 httpx 连接池

**Before**: 每个模块每次搜索创建新 AsyncClient
```python
async with httpx.AsyncClient(timeout=30) as client:
    r = await client.get(url)
```

**After**: BaseSearchModule 维护共享 _http_client，lifespan 管理生命周期
```python
class BaseSearchModule(ABC):
    _http_client: httpx.AsyncClient | None = None

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30, trust_env=False,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._http_client

    async def close_http_client(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
```

### 4.2 FastAPI Lifespan

**Before**: `@app.on_event("startup")`
**After**: `contextlib.asynccontextmanager` lifespan

```python
@asynccontextmanager
async def lifespan(app):
    # startup
    modules = auto_register()
    engine.load_modules()
    await _check_modules(modules)
    yield
    # shutdown — close all httpx clients
    for m in get_all().values():
        await m.close_http_client()
```

### 4.3 CDPPool 类封装

**Before**: 全局变量 `_cdp_available`, `_last_check`, `_check_lock`
**After**: CDPPool 单例类

### 4.4 配置集中化

**Before**: `Path(__file__).parent.parent.parent.parent / "claw-mem" / ...`
**After**: 环境变量 `TABBIT_SCRIPT_PATH` + 合理默认值

## 5. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/main.py` | 修改 | lifespan 替代 on_event |
| `app/config.py` | 修改 | 路径集中化 + env-first |
| `app/modules/base.py` | 修改 | 增加 httpx 连接池支持 |
| `app/modules/cdp_pool.py` | 重写 | 全局变量 → CDPPool 类 |
| `app/modules/web.py` | 修改 | 使用基类 httpx client |
| `app/modules/github.py` | 修改 | 使用基类 httpx client |
| `app/modules/ddg.py` | 修改 | 使用基类 httpx client |
| `app/modules/searxng.py` | 修改 | 使用基类 httpx client |
| 其他 ~20 个 modules/*.py | 修改 | httpx client 复用 |
| `app/engine/scheduler.py` | 修改 | print → logger |
| `tests/conftest.py` | 新增 | 统一 fixture |
| `tests/test_unit_*.py` | 新增 | 纯逻辑单元测试 |
| `pyproject.toml` | 修改 | 补全 [tool.pytest] 配置 |

## 6. 版本号

v0.9.5 → **v1.0.0**（架构级变更，语义版本 Major bump）

## 7. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| httpx 连接池泄漏 | 低 | 中 | lifespan shutdown 清理 |
| 模块初始化顺序变化 | 低 | 低 | 保持 _PRIORITY_ORDER |
| 测试回归 | 中 | 中 | 先跑纯逻辑测试确认 |

## 8. 任务分解

### Phase 1: 核心架构 (T1-T3)
- T1: BaseSearchModule 增加 httpx 连接池 + close_http_client
- T2: FastAPI lifespan 替代 on_event
- T3: CDPPool 类封装

### Phase 2: 模块迁移 (T4-T5)
- T4: 高频模块迁移（web/github/ddg/searxng/cdp_pool）
- T5: 批量迁移其余模块（httpx client + print → logger）

### Phase 3: 代码质量 (T6-T7)
- T6: 配置集中化（config.py 路径 + pyproject.toml）
- T7: 静默异常清理（except...pass → logger.warning）

### Phase 4: 测试增强 (T8-T9)
- T8: conftest.py + 纯逻辑单元测试
- T9: pyproject.toml pytest 配置 + coverage gate

### Phase 5: 文档+交付 (T10)
- T10: README 更新 + 版本号 bump + commit
