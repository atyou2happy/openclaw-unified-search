# unified-search Bug 检查报告

**日期**: 2026-04-14 07:00  
**版本**: v0.2.1 (commit d583a7e)  
**服务**: 18模块 / 10可用

## 模块状态

| 模块 | 状态 | 说明 |
|------|------|------|
| searxng | ❌ | Docker 容器未运行 |
| metaso | ❌ | Docker 容器未运行（Token已配） |
| tabbit | ✅ | CDP搜索正常，但可能阻塞服务 |
| web | ✅ | DDG备用工作正常 |
| jina | ✅ | 网页提取正常 |
| github | ✅ | 仓库搜索正常 |
| pdf | ✅ | PDF解析正常 |
| docs | ✅ | 文档抓取正常 |
| academic | ✅ | 学术搜索正常 |
| wiki | ✅ | 百科搜索正常 |
| brave | ✅ | 但单独搜索返回0结果 |
| tavily | ❌ | 需API Key |
| serper | ❌ | 需API Key |
| perplexity | ❌ | 需API Key |
| ddg | ✅ | ddgs库正常（已修复） |
| bing | ❌ | 需API Key |
| you | ❌ | 需API Key |
| komo | ❌ | API已变更，已禁用 |
| phind | ❌ | Cloudflare TLS，已禁用 |

## 已修复 Bug

| Bug | 描述 | 修复 |
|-----|------|------|
| #1 | DDG 返回0结果 | 重写：ddgs库在线程中运行 |
| #2 | Komo 返回0 | API v3 返回404，已禁用 |
| #3 | tabbit 不被智能搜索选中 | MODULE_PROFILES 缺 tabbit，已补回 |
| #5 | modules_used 为空 | 误报，字段名是 sources_used |

## 新发现 Bug

### 🔴 Bug 6: tabbit 搜索可能阻塞整个服务
- **现象**: 智能搜索触发 tabbit CDP 脚本时，如果脚本卡住，整个服务无响应
- **根因**: tabbit 用 `asyncio.create_subprocess_exec` 调外部脚本，脚本卡住时占住事件循环
- **影响**: 所有请求（包括不相关的）都会超时
- **修复建议**: 给 tabbit 的 subprocess 加独立超时，或限制 tabbit 只在直接调用时使用

### 🟡 Bug 7: Brave 单独搜索返回0
- **现象**: Brave health_check 通过但搜索返回空
- **根因**: 可能 API Key 无效或配额用完
- **影响**: 低（智能搜索时会走其他模块）

### 🟡 Bug 8: 缓存命中但耗时仍然长
- **现象**: 第一次搜索耗时15s（包含 tabbit 超时），第二次缓存命中但 elapsed 仍显示15s
- **根因**: cache.put 在 response 生成后保存，elapsed 已包含了完整耗时
- **影响**: 低（缓存命中的实际响应时间正常，只是 elapsed 字段不准）

### 🟡 Bug 9: 中文短查询智能搜索结果不相关
- **现象**: "什么是RAG" 返回日语wiki无关结果
- **根因**: "RAG" 太短，wiki 模块匹配到日语词条
- **影响**: 中（长查询正常，短查询质量差）
- **建议**: 对短查询（<3词）优先走 DDG/web 而非 wiki

## 非Bug
- Bug 4: SearXNG/Metaso 不可用 → Docker 容器未运行
- Bug 5: modules_used 为空 → 字段名是 sources_used
