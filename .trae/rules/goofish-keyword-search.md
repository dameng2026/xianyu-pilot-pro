# 闲鱼商品关键词搜索 - 架构与约束规则

> **强制规则**：任何 AI 模型在修改"商品关键词搜索"功能前，必须先完整阅读本文件。
> 不得更改下文定义的搜索逻辑、API 调用方式、字段映射和降级策略。
> 如需新增功能，只能在现有架构基础上扩展，不得替换或重写核心搜索链路。

## 一、功能概述

商机发掘中的"商品关键词搜索"功能支持三种搜索模式，通过 `mode` 参数选择：

| mode 值 | 名称     | 实现方式                        | 平均耗时 | 稳定性 |
|---------|----------|---------------------------------|----------|--------|
| `fast`  | 快速搜索 | 直调闲鱼 MTOP API（不经浏览器） | ~1 秒    | 低（可能触发 Baxia 风控） |
| `slow`  | 慢速搜索 | Playwright 浏览器拦截 MTOP 响应 | ~2-3 秒  | 高（浏览器自动处理反爬令牌） |
| `auto`  | 智能模式（默认）| 先快速搜索，失败自动降级到慢速搜索 | ~2-3 秒  | 最高 |

## 二、调用链路（不得更改）

```
前端 OpportunityPage.vue
  → goofishSearch(q, page, pageSize, accountId, mode)   [user-web/src/api/misc.js]
  → GET /api/goofish/search?q=&page=&pageSize=&mode=   [Java AutomationProxyController.goofishSearch()]
  → GET /automation/api/v1/goofish-search?q=&page=&pageSize=&mode=  [Python misc.py business_goofish_search()]
  → _execute_search_with_mode(keyword, page, page_size, tenant_id, cookie_str, mode)  [Python misc.py]
      ├─ mode=fast/auto → _call_mtop_search_direct()    [Python misc.py - 直调 MTOP API]
      └─ mode=slow/auto → _call_crawler_search()        [Python misc.py - 调 crawler-service]
                           → GET http://localhost:3001/api/goofish/search  [Node crawler-service]
                              → crawlGoofishSearch()    [crawler-service/dist/crawler/goofishSearch.js]
                                 → Playwright 浏览器拦截 MTOP 响应
```

## 三、快速搜索实现（不得更改）

**文件**：`apps/automation-service/app/api/v1/routes/misc.py` → `_call_mtop_search_direct()`

**原理**：直接 POST 到 `https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/`，使用 Cookie + `_m_h5_tk` 生成签名。

**关键常量**（定义在 `apps/automation-service/app/services/xianyu_goods_sync.py`）：
- `SEARCH_MTOP_API = "mtop.taobao.idlemtopsearch.pc.search"`
- 签名函数：`_xianyu_mtop_request()` — 使用 `_m_h5_tk` 的 token 部分与时间戳生成 MD5 签名

**请求参数**（不得更改字段名）：
```python
search_data = {
    "keyword": keyword,
    "pageNumber": page,
    "rowsPerPage": page_size,
    "fromFilter": False,
    "sortValue": "",
    "sortField": "",
    "searchReqFromPage": "pcSearch",
    "customDistance": "",
    "gps": "",
    "customGps": "",
    "propValueStr": {},
    "extraFilterValue": "{}",
    "userPositionJson": "{}",
}
```

**风控检测**（触发以下错误时抛出 RuntimeError，由 auto 模式降级到慢速搜索）：
- `FAIL_SYS_USER_VALIDATE` → Baxia 验证
- `RGV587_ERROR` → 风控拦截
- `_m_h5_tk` 过期 → Token 失效

**响应解析**：`_normalize_mtop_search_item()`（在 `xianyu_goods_sync.py`），从嵌套结构提取字段：
```
data.resultList[].data.item.main.exContent.detailParams.{title,itemId,soldPrice}
data.resultList[].data.item.main.exContent.{area,userNickName,picUrl,title}
data.resultList[].data.item.main.clickParam.args.{price,item_id}
```

## 四、慢速搜索实现（不得更改）

**文件**：
- Python 层：`apps/automation-service/app/api/v1/routes/misc.py` → `_call_crawler_search()`
- Node 层：`apps/crawler-service/dist/crawler/goofishSearch.js` → `crawlGoofishSearch()`
- TypeScript 源码：`apps/crawler-service/src/crawler/goofishSearch.ts`（须与 dist 保持同步）

**原理**：Playwright 启动无头浏览器访问 `https://www.goofish.com/search?q={keyword}&page={pageNum}`，通过 `page.on('response')` 拦截 MTOP 搜索 API 响应。

**核心优化（事件驱动，不得回退为固定等待）**：
1. 用 `Promise.race` 竞速等待：MTOP 响应到达 vs. 6 秒超时
2. 拦截到 MTOP 响应后立即 `mtopResolve()` 唤醒主流程，无需继续等待
3. 拦截到结果后走"快速路径"直接返回，不检测阻断/不滚动/不 DOM 提取
4. 仅当 MTOP 未拦截到结果时，才走"兜底路径"：等待 1.5 秒后做 DOM 提取

**MTOP 响应标识**（用于精确匹配网络响应，不得更改）：
```javascript
const SEARCH_API_MARKER = 'mtop.taobao.idlemtopsearch.pc.search';
```

**MTOP 响应解析**：`parseMtopSearchResponse()` 函数，从 `data.resultList[].data.item.main.exContent` 提取：
- `itemId` ← `exContent.itemId` 或 `clickParam.args.item_id`
- `title` ← `exContent.title`
- `price` ← `exContent.price`（数组格式，取 `type="integer"` 的 `text`）或 `clickParam.args.price`
- `picUrl` ← `exContent.picUrl`
- `userNickName` ← `exContent.userNickName`
- `area` ← `exContent.area`

**Cookie 注入**：浏览器启动时通过 `contextOptions.storageState = { cookies }` 注入用户 Cookie，domain 为 `.goofish.com`。

## 五、自动降级逻辑（不得更改）

**文件**：`apps/automation-service/app/api/v1/routes/misc.py` → `_execute_search_with_mode()`

```python
def _execute_search_with_mode(keyword, page, page_size, tenant_id, cookie_str, mode):
    # mode=fast/auto → 先尝试快速搜索
    if mode in ("fast", "auto"):
        try:
            result = _call_mtop_search_direct(keyword, page, page_size, cookie_str)
            if result.get("items"):
                result["searchMode"] = "fast"
                return result
        except Exception as e:
            if mode == "fast":
                raise  # fast 模式不降级
            # auto 模式继续降级

    # mode=slow/auto → 慢速搜索
    result = _call_crawler_search(keyword, page, page_size, tenant_id, cookie_str)
    result["searchMode"] = "slow"
    return result
```

返回结果中 `searchMode` 字段标识实际使用的搜索方式（`fast` 或 `slow`）。

## 六、字段映射标准（不得更改）

Python 层 `_call_crawler_search()` 将 crawler-service 返回的字段标准化为前端格式：

| crawler-service 字段 | 标准化字段 | 说明 |
|---------------------|-----------|------|
| `itemId` | `itemId`, `link` | link 拼接为 `https://www.goofish.com/item?itemId={itemId}` |
| `title` | `title`, `description` | |
| `price` | `price` | |
| `imageUrl` | `imageUrl` | |
| `userNickName` | `seller` | |
| `area` | `area` | |
| - | `soldCount` | 固定 0 |
| - | `wantCount` | 固定 0 |

## 七、Java 网关层（不得更改参数透传逻辑）

**文件**：`apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java` → `goofishSearch()`

- 接收前端参数：`q`, `page`, `pageSize`, `accountId`, `mode`（默认 `auto`）
- `mode` 参数校验：只允许 `fast`/`slow`/`auto`，其他值默认 `auto`
- 透传到 Python：`/automation/api/v1/goofish-search?q=&page=&pageSize=&mode=`

## 八、关键约束（违反即为 Bug）

1. **不得用固定 `waitForTimeout` 替代 `Promise.race` 事件驱动**：固定等待是性能倒退，MTOP 响应到达后应立即返回。
2. **不得删除 `SEARCH_API_MARKER` 精确匹配逻辑**：宽泛的 JSON 递归提取会导致非商品数据混入。
3. **不得删除 Cookie 注入逻辑**：无 Cookie 时搜索会触发登录跳转。
4. **不得更改 MTOP API 端点**：必须是 `mtop.taobao.idlemtopsearch.pc.search`。
5. **不得删除 Baxia 风控检测**：快速搜索触发 `FAIL_SYS_USER_VALIDATE` 时必须能降级到慢速搜索。
6. **源码与编译产物必须同步**：`src/crawler/goofishSearch.ts` 必须与 `dist/crawler/goofishSearch.js` 逻辑一致，否则 `tsc` 编译会覆盖优化。
7. **不得更改 `searchMode` 返回字段**：前端依赖此字段显示实际使用的搜索方式。

## 九、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/user-web/src/api/misc.js` | 前端 API 函数 `goofishSearch()` |
| `apps/user-web/src/pages/OpportunityPage.vue` | 前端页面，搜索方式选择器 |
| `apps/core-api/.../AutomationProxyController.java` | Java 网关，参数透传 |
| `apps/automation-service/app/api/v1/routes/misc.py` | Python 路由，搜索执行器 |
| `apps/automation-service/app/services/xianyu_goods_sync.py` | MTOP API 常量、签名、字段标准化 |
| `apps/crawler-service/src/crawler/goofishSearch.ts` | TypeScript 源码（须与 dist 同步） |
| `apps/crawler-service/dist/crawler/goofishSearch.js` | 编译产物，实际运行 |
| `闲鱼搜索接口.md` | 项目根目录的 MTOP API 文档参考 |
