# Admin Dashboard Overview Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the admin overview page to match the approved white-theme long-scroll design, while keeping the existing global sidebar and top navigation untouched.

**Architecture:** Keep the route and generic module page behavior inside `apps/admin-web/src/views/admin/module/index.vue`, but move dashboard-specific data shaping into a small pure helper so the long-form layout can stay readable and contract-testable. Use the existing dashboard aggregate endpoint plus monitor endpoints as the live data surface, and degrade gracefully when some advanced metrics are unavailable.

**Tech Stack:** Vue 3 SFC, TypeScript, Element Plus, Vite, `tsx`, Node assert-based contract testing

---

## File Map

- Modify: `apps/admin-web/src/views/admin/module/index.vue`
- Create: `apps/admin-web/src/views/admin/module/dashboard-overview.ts`
- Create: `apps/admin-web/scripts/dashboard-overview-contract.test.ts`
- Modify: `apps/admin-web/package.json`

### Task 1: Add A Failing Dashboard Contract Test

**Files:**

- Create: `apps/admin-web/scripts/dashboard-overview-contract.test.ts`
- Create: `apps/admin-web/src/views/admin/module/dashboard-overview.ts`
- Modify: `apps/admin-web/package.json`

- [ ] **Step 1: Write the failing contract test**

```ts
import assert from 'node:assert/strict'
import {
  buildDashboardOverviewModel,
  createOverviewTestFixture
} from '../src/views/admin/module/dashboard-overview'

const model = buildDashboardOverviewModel(createOverviewTestFixture())

assert.equal(model.hero.title, '闲鱼助手平台后台')
assert.equal(model.kpiGroups.length, 4)
assert.deepEqual(
  model.sectionOrder,
  [
    'kpi',
    'finance',
    'funnel-growth',
    'monitoring',
    'service-stock-alerts',
    'quality-sync',
    'bottom'
  ]
)
assert.equal(model.finance.cards.length, 4)
assert.equal(model.monitoring.cards.length, 3)
assert.equal(model.bottom.cards.length, 3)
assert(model.pendingItems.length > 0, '待处理事项应被映射到新版长图结构')
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run: `npx tsx ./scripts/dashboard-overview-contract.test.ts`

Expected: FAIL because `dashboard-overview.ts` and the exported model builders do not exist yet.

- [ ] **Step 3: Create the minimal dashboard view-model helpers**

```ts
export interface DashboardOverviewFixture {
  summary: Record<string, any>
  trend: Record<string, any>
  realtimeStats: Record<string, any>
  pendingTasks: any[]
  topHotGoods: any[]
  riskDistribution: any[]
  systemHealth: Record<string, any> | null
  recentEvents: any[]
  aiMonitor: Record<string, any>
  autoReplyMonitor: Record<string, any>
  workflowMonitor: Record<string, any>
  tokenStats: Record<string, any>
  costStats: Record<string, any>
}

export function createOverviewTestFixture(): DashboardOverviewFixture {
  return {
    summary: { cards: [{ key: 'accounts', label: '账号数', value: 3, desc: '较昨日 0%' }] },
    trend: { dates: ['2026-06-26'], orders: [1], delivery: [1], ai: [1] },
    realtimeStats: { onlineAccounts: 0, todayPublished: 13, todaySalesAmount: '0.00', todayAiCalls: 50, todayAiFailures: 0, runningWorkflows: 0 },
    pendingTasks: [{ title: '工作流执行失败', time: '18:01:41', type: 'workflow', source: 'workflow', sourceId: 1 }],
    topHotGoods: [],
    riskDistribution: [{ risk_level: 0, count: 3 }],
    systemHealth: null,
    recentEvents: [],
    aiMonitor: {},
    autoReplyMonitor: {},
    workflowMonitor: {},
    tokenStats: {},
    costStats: {}
  }
}
```

- [ ] **Step 4: Re-run the contract test and keep it green**

Run: `npx tsx ./scripts/dashboard-overview-contract.test.ts`

Expected: PASS with the long-page section order and grouped model shape verified.

- [ ] **Step 5: Add a package script for the contract test**

```json
{
  "scripts": {
    "test:dashboard-overview": "tsx ./scripts/dashboard-overview-contract.test.ts"
  }
}
```

- [ ] **Step 6: Commit the contract-test slice**

```bash
git add apps/admin-web/scripts/dashboard-overview-contract.test.ts \
        apps/admin-web/src/views/admin/module/dashboard-overview.ts \
        apps/admin-web/package.json
git commit -m "test: add admin dashboard overview contract"
```

### Task 2: Build The Long-Form Dashboard View Model

**Files:**

- Modify: `apps/admin-web/src/views/admin/module/dashboard-overview.ts`

- [ ] **Step 1: Write a failing extension in the contract test for grouped sections**

```ts
assert.equal(model.kpiGroups[0].title, '平台用户与租户')
assert.equal(model.finance.chart.series.length, 2)
assert.equal(model.funnel.stages.length, 4)
assert.equal(model.servicePanels.length, 3)
assert.equal(model.qualityPanels.length, 3)
```

- [ ] **Step 2: Run the test to verify it fails for missing section builders**

Run: `npm run test:dashboard-overview`

Expected: FAIL because the richer groups and panel collections are not built yet.

- [ ] **Step 3: Implement the pure mapping helpers**

```ts
export function buildDashboardOverviewModel(input: DashboardOverviewFixture) {
  return {
    hero: buildHero(input),
    kpiGroups: buildKpiGroups(input),
    finance: buildFinanceSection(input),
    funnel: buildFunnelSection(input),
    growth: buildGrowthSection(input),
    monitoring: buildMonitoringSection(input),
    servicePanels: buildServicePanels(input),
    qualityPanels: buildQualityPanels(input),
    bottom: buildBottomPanels(input),
    pendingItems: buildPendingItems(input),
    sectionOrder: ['kpi', 'finance', 'funnel-growth', 'monitoring', 'service-stock-alerts', 'quality-sync', 'bottom']
  }
}
```

- [ ] **Step 4: Re-run the contract test and keep it green**

Run: `npm run test:dashboard-overview`

Expected: PASS with grouped business sections and chart-ready panel models returned from pure functions.

- [ ] **Step 5: Commit the view-model slice**

```bash
git add apps/admin-web/src/views/admin/module/dashboard-overview.ts \
        apps/admin-web/scripts/dashboard-overview-contract.test.ts
git commit -m "feat: add long-form admin dashboard overview model"
```

### Task 3: Rebuild The Dashboard Template And White-Theme Layout

**Files:**

- Modify: `apps/admin-web/src/views/admin/module/index.vue`

- [ ] **Step 1: Add a failing contract assertion for the new template sections**

```ts
import fs from 'node:fs'
import path from 'node:path'

const page = fs.readFileSync(path.resolve('src/views/admin/module/index.vue'), 'utf8')
assert(page.includes('经营总览'))
assert(page.includes('收入 vs AI 成本'))
assert(page.includes('订单转化漏斗'))
assert(page.includes('消息与客服效率'))
assert(page.includes('通知投递统计'))
assert(page.includes('最近后台操作'))
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run: `npm run test:dashboard-overview`

Expected: FAIL because the existing template still renders the old compact dashboard.

- [ ] **Step 3: Replace the dashboard branch in `index.vue` with the long-scroll structure**

```vue
<div class="overview-shell">
  <section class="overview-hero">...</section>
  <section class="overview-section">
    <div class="section-heading">经营总览</div>
    <div class="kpi-group-grid">...</div>
  </section>
  <section class="overview-section">
    <div class="section-heading">收入 vs AI 成本</div>
    <div class="finance-layout">...</div>
  </section>
</div>
```

- [ ] **Step 4: Bind the template to the new view-model helpers**

```ts
const overviewMonitor = reactive({ ai: {}, autoReply: {}, workflow: {}, token: {}, cost: {} })

const dashboardOverview = computed(() =>
  buildDashboardOverviewModel({
    summary: summary.value,
    trend: trend.value,
    realtimeStats: realtimeStats.value,
    pendingTasks: pendingTasks.value,
    topHotGoods: topHotGoods.value,
    riskDistribution: riskDistribution.value,
    systemHealth: systemHealth.value,
    recentEvents: recentEvents.value,
    aiMonitor: overviewMonitor.ai,
    autoReplyMonitor: overviewMonitor.autoReply,
    workflowMonitor: overviewMonitor.workflow,
    tokenStats: overviewMonitor.token,
    costStats: overviewMonitor.cost
  })
)
```

- [ ] **Step 5: Re-run the contract test and keep it green**

Run: `npm run test:dashboard-overview`

Expected: PASS with the new long-scroll section labels present in the SFC and the model still intact.

- [ ] **Step 6: Commit the layout slice**

```bash
git add apps/admin-web/src/views/admin/module/index.vue \
        apps/admin-web/scripts/dashboard-overview-contract.test.ts
git commit -m "feat: rebuild admin overview page as long-form white dashboard"
```

### Task 4: Wire Advanced Monitor Data And Verify Compilation

**Files:**

- Modify: `apps/admin-web/src/views/admin/module/index.vue`

- [ ] **Step 1: Write a failing contract assertion for advanced monitor wiring**

```ts
assert(page.includes('getAiMonitor'))
assert(page.includes('getAiCostStats'))
assert(page.includes('getAutoReplyMonitor'))
assert(page.includes('getWorkflowMonitor'))
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run: `npm run test:dashboard-overview`

Expected: FAIL because the page still only uses `/admin/dashboard/init`.

- [ ] **Step 3: Load advanced insight endpoints during dashboard refresh**

```ts
const [base, ai, autoReply, workflow, token, cost] = await Promise.all([
  getDashboardInit(),
  getAiMonitor({ days: 7 }).catch(() => ({})),
  getAutoReplyMonitor({ days: 7 }).catch(() => ({})),
  getWorkflowMonitor({ days: 7 }).catch(() => ({})),
  getAiTokenStats({ days: 7 }).catch(() => ({})),
  getAiCostStats({ days: 7 }).catch(() => ({}))
])
```

- [ ] **Step 4: Run the contract test and type check**

Run: `npm run test:dashboard-overview`

Expected: PASS with the extra data hooks wired.

Run: `npm run typecheck`

Expected: PASS with the redesigned dashboard compiling cleanly.

- [ ] **Step 5: Build the admin app**

Run: `npm run build`

Expected: PASS with a successful Vite production build.

- [ ] **Step 6: Commit the data-wiring and verification slice**

```bash
git add apps/admin-web/src/views/admin/module/index.vue
git commit -m "feat: wire advanced monitor metrics into admin overview"
```

## Self-Review

**Spec coverage:** The plan covers the approved redesign constraints: white theme, long vertical page, unchanged global navigation, grouped KPI bands, finance, conversion, monitoring, service/stock/alerts, quality/sync, and bottom health/activity panels.

**Placeholder scan:** The tasks avoid `TODO`/`TBD` placeholders and name concrete files, commands, and expected outcomes.

**Type consistency:** The shared helper file centralizes the dashboard section model so the SFC and contract test can use the same names: `kpiGroups`, `finance`, `funnel`, `servicePanels`, `qualityPanels`, `bottom`.
