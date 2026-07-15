# 前台优化 · 阶段 A 设计文档

> 日期：2026-06-27
> 范围：apps/user-web 前台
> 目标：修 Bug + 去假数据，让"显示出来的每一项数据都是真实的"，并做轻量视觉质感提升
> 约束：不动主色(#0d6bff)与字体族；不动闲鱼搜索链路（受 goofish-keyword-search.md 约束）；本轮纯前端，不涉及后端修改

---

## 一、背景与动机

前台 22 个页面经审计存在 200+ 个体验问题，分 4 阶段推进。本阶段聚焦 P0/P1：

- **P0 功能性 Bug**（约 20 处）：死按钮、querySelector 全局选择器 bug、静默 catch、文字行为不一致、SKU 死按钮等
- **P1 假数据**（约 30 处）：LogsPage 整页 mock、AccountVipPage 整页 mock、健康分写死、AI 推荐写死、VIP 套餐回退 mock 等

经后端接口探查，8 项假数据中 **6 项后端已就绪可直接对接**，2 项需后端新增（按用户策略显示空态）。

---

## 二、模块设计

### 模块 1：P0 Bug 修复

| ID | 文件 | 问题 | 修复方案 |
|----|------|------|----------|
| 1.1 | WorkflowPage.vue:373 | `<img @error="img = null">` 循环变量赋值，响应式不生效 | 改用 `imgLoadErrorSet`（`reactive(new Set())`）+ `:src` 计算 fallback |
| 1.2 | DeliveryTemplatesPage.vue:214,237 / ScheduledTasksPage.vue:22 / AutoReplyPage.vue:98 | `document.querySelector('textarea'/'input')` 全局选择器，会命中页面任意 textarea | 全部改用 `ref()` 绑定当前组件 textarea/input |
| 1.3 | WorkflowTasksPage.vue:88,94,96,97 | `load/open/terminateCurrent/retryFailed` 全无 try/catch | 4 个函数补 try/catch + error.value + toast |
| 1.4 | ScheduledTasksPage.vue | `remove` 引入 confirmDelete 未调用 + Cron/JSON 无前端校验 | remove 加 `await confirmDelete('定时任务')`；Cron 加正则校验提示；configJson 加 `JSON.parse` 实时校验 + 错误提示 |
| 1.5 | ProductPublishPage.vue:291 / SKU 表格 | 取消直接跳转无未保存提示；SKU 行 `▢` 死按钮 | 取消加 `confirmAction`「未保存的更改将丢失」；SKU 实现 add/remove row（基于现有 skus 数组） |
| 1.6 | ProductsPage.vue refreshSingle / AutoDeliveryPage.vue removeConfig | 文字与行为不一致 | refreshSingle 提示改"同步全部商品"；removeConfig 提示改"禁用配置"（保持 enabled:0 行为不变） |

### 模块 2：假数据替换 · 后端已就绪（6 项对接）

| ID | 文件 | 现状 | 对接方案 |
|----|------|------|----------|
| 2.1 | LogsPage.vue | 整页 mock，日期停在 2025-06，统计用 `Math.random` | 调 `getOperationLogs({operationType, keyword, current, size})`；StatCard 改为后端 countFiltered（若无 countFiltered 则前端统计当前筛选结果数）；表格接真实分页；CSV 导出接 `/operation-logs/export`；移除右侧"日志详情"抽屉的死按钮（复制/重新执行/标记为异常），改为只读详情 |
| 2.2 | AccountVipPage.vue + VipPage.vue | 两页功能重叠、价格矛盾(¥99 vs ¥29.9) | AccountVipPage 从 Sidebar/路由移除（文件保留不删，避免破坏 import）；ProfileCenter「升级会员」改跳 VipPage；headerActions 中 'account-vip' 条目移除 |
| 2.3 | MessagesPage.vue:296-344 右侧详情 | 商品已对接，买家画像写死('阳光男孩'/'2023-05-12') | 商品侧保留真实数据；买家画像字段(registeredAt/region/recentInquiryCount)显示"—"，顶部加 subtle 提示"买家画像数据待后端补全" |
| 2.4 | MessagesPage.vue:454-458 快捷回复 | 写死 3 条 | 引入 `getAutoReplyRules`，按 keyword 模糊匹配或拉全部后前端过滤；为空时显示「去配置快捷回复」链接跳 AutoReplyPage |
| 2.5 | ProductPublishPage.vue:895 aiDesc | 写死"成色良好，功能正常..." | 改调 `aiRewriteGoods({title, description})`（复用 WorkflowPage 同款接口）；按钮加 loading + 防抖；失败 toast |
| 2.6 | VipPage.vue:161-165 fallbackPlans | 接口失败回退 mock 套餐 | 删 fallbackPlans；loadPlans 失败时 plans=[] + 显示 EmptyState「套餐加载失败，请刷新重试」+ 重试按钮 |

### 模块 3：假数据替换 · 后端未就绪（3 项显示空态）

按用户策略：后端没接口就显示空态，不展示假数据。

| ID | 文件 | 现状 | 空态方案 |
|----|------|------|----------|
| 3.1 | AccountsPage.vue:512-675 健康分 + recentActivities | 写死 98/96/98 + 假活动记录 | 健康分显示「—」+ tooltip「健康分接口开发中」；recentActivities 用 EmptyState「暂无最近活动」 |
| 3.2 | ConnectionsPage.vue:44 健康环 | `conic-gradient(... 0 86%)` 写死 86%/96/60 | 健康环显示灰色「—」+ tooltip「健康分接口开发中」；健康分明细面板隐藏或显示 EmptyState |
| 3.3 | MessagesPage.vue:449-453 aiReplies | 写死 3 条 + "换一批"死按钮 | 显示 EmptyState「AI 推荐回复开发中」；隐藏"换一批"按钮 |

### 模块 4：Topbar 死按钮处理

Topbar.vue:3-6 共 4 个死按钮：

| 按钮 | 处理 |
|------|------|
| 🔍 搜索 | **本轮隐藏**（需后端新增全局检索接口，下轮做） |
| 🔔 通知 | 实现通知抽屉：聚合 SSE 事件历史（监听 `xya-sse-event` 缓存最近 50 条），点击跳转对应页面；unreadCount=0 时隐藏徽章；补 aria-label |
| ❓ 帮助 | 跳转外部文档链接（`window.open`，暂用 GitHub README 或 about 页面）；补 aria-label |
| ⛶ 全屏 | 调 `document.documentElement.requestFullscreen()` / `exitFullscreen()` 切换，icon 根据状态切换；补 aria-label |

### 模块 5：静默 catch 补全（9 处）

统一模式：`catch (e) { error.value = e.message; toast(e.message || '操作失败') }` 或 `catch (e) { console.warn(e); /* 非关键路径 */ }`。

| 文件 | 函数 | 处理 |
|------|------|------|
| DeliveryStatementPage.vue:121 | `load` | 加 error toast |
| WorkflowPage.vue:717 | `loadHistoryAddresses` | console.warn + 历史地址下拉显示"加载失败" |
| WorkflowPage.vue:726 | `loadImageModels` | console.warn + 模型下拉显示"加载失败，请检查后台配置" |
| WorkflowTasksPage.vue | `load/open/terminateCurrent/retryFailed` | 4 处加 error toast |
| AutoReplyPage.vue:92,93 | `loadReplyLogs/loadReplyStats` | 加 toast + EmptyState |
| ProductPublishPage.vue:449 | `loadAiCategoryStatus` | console.warn + 默认 disabled |
| ProductPublishPage.vue:585 | `refreshCategoriesInBackground` | console.warn（非关键，保留静默但加日志） |
| ProductPublishPage.vue:729 | POI 搜索 | toast"位置搜索失败" + 清空列表 |
| ProductPublishPage.vue:882 | `runtimeConfig` | console.warn + 默认配置 |

### 模块 6：视觉质感轻量提升（不动主色和字体）

集中在 styles.css 调整，不改组件结构：

| 项 | 现状 | 优化 |
|----|------|------|
| 阴影 | `0 12px 34px rgba(31,53,94,.08)` 偏硬 | 改为双层柔和阴影：`0 1px 2px rgba(31,53,94,.04), 0 8px 24px rgba(31,53,94,.06)` |
| 卡片圆角层级 | 全用 14px | panel 14px / sub-card 10px / input 7px / chip 6px，建立层级 |
| hover/transition | 多数无 | 卡片 hover `transform: translateY(-2px)` + `transition: .18s`；按钮 `:active` scale(.98) |
| 空态插画 | 5 套不同写法 | 全部统一为 `EmptyState` 组件，新增 4 种内置插画变体（默认/搜索无结果/错误/开发中） |
| 焦点态 | 输入框 focus 无明显环 | `:focus-visible` 加 `outline: 2px solid var(--primary); outline-offset: 1px` |
| 字重 | 大量 800/900 | 标题 800 / 副标题 700 / 正文 520-650，建立层级（仅调整新增/修改处，不大面积改） |

**不改动**：主色 `#0d6bff`、字体族、侧边栏宽度、卡片骨架结构。

---

## 三、数据流与错误处理约定

### 统一错误处理模式

```javascript
// 列表加载
async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api({ current: page.value, size: 20 })
    rows.value = res.data?.records || []
    total.value = res.data?.total || 0
  } catch (e) {
    error.value = e.message || '加载失败'
    toast(error.value)
  } finally {
    loading.value = false
  }
}

// 非关键路径（背景刷新）
async function refreshInBackground() {
  try {
    const res = await api()
    // ...
  } catch (e) {
    console.warn('[refreshInBackground]', e)
  }
}
```

### EmptyState 组件增强

现有 EmptyState 接收 `icon/title/description`，新增 `variant` prop：

- `default` - 通用空态
- `search` - 搜索无结果（带"清空筛选"按钮 slot）
- `error` - 加载失败（带"重试"按钮 slot）
- `dev` - 功能开发中（带"了解更多"链接 slot）

### 通知抽屉数据流

```
App.vue startSse()
  → window.dispatchEvent('xya-sse-event', { detail: event })
  → Topbar.vue 监听，缓存到 recentEvents（最多 50 条）
  → 点击 🔔 → 展开抽屉，列表渲染 recentEvents
  → 点击某条 → 跳转对应页面（按 event.type 路由映射）
```

---

## 四、测试与验证

每个模块完成后验证：

1. **P0 Bug 修复**：手动触发原 bug 场景，确认不再复现
2. **假数据对接**：Network 面板确认请求真实发出，响应正确渲染
3. **空态显示**：模拟后端无数据，确认 EmptyState 正确显示而非假数据
4. **Topbar**：点击每个按钮确认行为正确，aria-label 可被屏幕阅读器读出
5. **视觉**：1280px / 1440px / 1920px 三档屏幕检查无破版

**验证命令**：
```bash
cd apps/user-web
npm run build  # 确认无编译错误
npm run dev    # 本地验证
```

---

## 五、不在本轮范围

以下留待后续阶段：

- **阶段 B**：12 处假分页接入真分页、BaseTable 抽标准分页器
- **阶段 C**：1280-1400px 中屏适配、aria-label 全面补全、Skeleton 骨架屏、按钮 loading/防抖全面补全
- **阶段 D**：信息密度、间距、移动端 MobileLite 完善
- **后端新增接口**：账号健康分、消息买家画像、AI 推荐回复、全局检索

---

## 六、风险与回滚

| 风险 | 缓解 |
|------|------|
| AccountVipPage 移除路由后，外部书签失效 | 文件保留，路由重定向到 VipPage |
| LogsPage 重写后字段缺失 | 保留原有列，仅换数据源；后端字段不全的列显示"—" |
| 视觉调整影响现有页面 | styles.css 改动集中在 `--shadow` 变量和新增 class，不改现有 class 语义 |
| EmptyState variant 新增破坏现有调用 | variant 默认值 'default'，与现有行为一致 |

每个模块独立 commit，出问题可单独 revert。
