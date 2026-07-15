# 前台优化 · 阶段 A 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复前台 P0 Bug 并替换所有假数据，让"显示出来的每一项数据都是真实的"，并做轻量视觉质感提升。

**Architecture:** 纯前端改造，不涉及后端。后端已就绪的接口直接对接（6项），后端未就绪的显示空态（3项）。视觉调整集中在 styles.css 和 EmptyState 组件，不动主色和字体。

**Tech Stack:** Vue 3 (Composition API, `<script setup>`)、Vite、原生 CSS（无 UI 框架）

**Spec:** `docs/superpowers/specs/2026-06-27-frontend-stage-a-design.md`

**约束:**
- 不动主色 `#0d6bff` 与字体族
- 不动闲鱼搜索链路（受 `.trae/rules/goofish-keyword-search.md` 约束）
- 不涉及后端修改
- 每个任务独立 commit

**验证命令:** `cd apps/user-web && npm run build`（确认无编译错误）

---

## 文件结构

| 文件 | 职责 | 涉及任务 |
|------|------|----------|
| `apps/user-web/src/components/EmptyState.vue` | 空态组件，新增 variant | Task 1 |
| `apps/user-web/src/components/Topbar.vue` | 顶栏，实现通知/帮助/全屏 | Task 11 |
| `apps/user-web/src/pages/WorkflowPage.vue` | 工作流编辑器，修 img bug + catch | Task 2, 5 |
| `apps/user-web/src/pages/DeliveryTemplatesPage.vue` | 发货模板，修 querySelector | Task 2 |
| `apps/user-web/src/pages/AutoReplyPage.vue` | 自动回复，修 querySelector + catch | Task 2, 5 |
| `apps/user-web/src/pages/ScheduledTasksPage.vue` | 定时任务，修 querySelector + 加校验 | Task 2 |
| `apps/user-web/src/pages/WorkflowTasksPage.vue` | 工作流任务，补 try/catch | Task 3 |
| `apps/user-web/src/pages/ProductPublishPage.vue` | 商品发布，取消确认+SKU+aiDesc对接+catch | Task 4, 5, 9 |
| `apps/user-web/src/pages/ProductsPage.vue` | 商品管理，文字行为对齐 | Task 4 |
| `apps/user-web/src/pages/AutoDeliveryPage.vue` | 自动发货，文字行为对齐 | Task 4 |
| `apps/user-web/src/pages/DeliveryStatementPage.vue` | 发货声明，catch 补全 | Task 5 |
| `apps/user-web/src/pages/LogsPage.vue` | 操作日志，整页重写对接真实接口 | Task 6 |
| `apps/user-web/src/pages/VipPage.vue` | VIP 中心，删 fallbackPlans | Task 7 |
| `apps/user-web/src/pages/AccountVipPage.vue` | 账号VIP，路由移除 | Task 7 |
| `apps/user-web/src/data/nav.js` | 导航配置，移除 account-vip | Task 7 |
| `apps/user-web/src/App.vue` | 路由表，移除 account-vip | Task 7 |
| `apps/user-web/src/pages/MessagesPage.vue` | 在线消息，买家画像空态+快捷回复对接+AI推荐空态 | Task 8 |
| `apps/user-web/src/pages/AccountsPage.vue` | 账号管理，健康分空态 | Task 10 |
| `apps/user-web/src/pages/ConnectionsPage.vue` | 连接管理，健康环空态 | Task 10 |
| `apps/user-web/src/styles.css` | 全局样式，视觉质感提升 | Task 12 |

---

## Task 1: EmptyState 组件增强

**Files:**
- Modify: `apps/user-web/src/components/EmptyState.vue`

为后续多个任务的空态显示提供统一组件，新增 `variant` prop 控制不同空态风格。

- [ ] **Step 1: 重写 EmptyState.vue 增加 variant**

修改 `apps/user-web/src/components/EmptyState.vue` 完整内容为：

```vue
<template>
  <div class="empty-cta" :class="variant" role="status">
    <div class="empty-cta-icon" aria-hidden="true">{{ displayIcon }}</div>
    <div>
      <h3>{{ title }}</h3>
      <p v-if="description">{{ description }}</p>
      <div v-if="$slots.actions" class="empty-cta-actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  icon: { type: String, default: '' },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '完成基础配置后，这里会展示对应数据。' },
  variant: { type: String, default: 'default' } // default | search | error | dev
})
const variantIcons = { default: '∅', search: '🔍', error: '⚠', dev: '🚧' }
const displayIcon = computed(() => props.icon || variantIcons[props.variant] || '∅')
</script>

<style scoped>
.empty-cta{display:flex;gap:16px;align-items:flex-start;padding:26px;border:1px dashed #cfd9ea;border-radius:18px;background:linear-gradient(135deg,#fbfdff,#f6f9ff);color:#526079;margin:12px 0}
.empty-cta-icon{width:48px;height:48px;border-radius:16px;background:#edf4ff;color:#0d6bff;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;flex:0 0 auto}
.empty-cta h3{margin:0 0 6px;color:#16213e;font-size:18px}
.empty-cta p{margin:0;line-height:1.7;color:#667085}
.empty-cta-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.empty-cta.search{border-color:#dbe7f5;background:linear-gradient(135deg,#fbfdff,#f0f6ff)}
.empty-cta.search .empty-cta-icon{background:#f0f6ff;color:#3b6fd4}
.empty-cta.error{border-color:#ffd1d1;background:linear-gradient(135deg,#fff8f8,#fff5f5)}
.empty-cta.error .empty-cta-icon{background:#fff0f0;color:#ef4444}
.empty-cta.dev{border-color:#ffe1b0;background:linear-gradient(135deg,#fffaf0,#fff8ea)}
.empty-cta.dev .empty-cta-icon{background:#fff5e6;color:#d97706}
</style>
```

- [ ] **Step 2: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功，无错误

- [ ] **Step 3: Commit**

```bash
git add apps/user-web/src/components/EmptyState.vue
git commit -m "feat(EmptyState): 新增 variant prop 支持 default/search/error/dev 四种空态风格"
```

---

## Task 2: P0 Bug 修复 - querySelector 全局选择器 + img 响应式 bug

**Files:**
- Modify: `apps/user-web/src/pages/WorkflowPage.vue` (img @error bug)
- Modify: `apps/user-web/src/pages/DeliveryTemplatesPage.vue` (querySelector textarea/input)
- Modify: `apps/user-web/src/pages/AutoReplyPage.vue` (querySelector input)
- Modify: `apps/user-web/src/pages/ScheduledTasksPage.vue` (querySelector input)

- [ ] **Step 1: 修复 WorkflowPage.vue img @error 响应式 bug**

读取 `apps/user-web/src/pages/WorkflowPage.vue` 第 370-380 行附近，找到 `<img @error="img = null">` 模式。

修复方案：在 script setup 中添加 `imgLoadErrorSet`，在模板中用它判断。

在 script setup 的 ref 区域添加：
```javascript
const imgLoadErrorSet = reactive(new Set())
function onImgError(url) { imgLoadErrorSet.add(url) }
```

在模板中找到 `<img :src="img" @error="img = null">` 类似代码，改为：
```html
<img :src="imgLoadErrorSet.has(img) ? '' : img" @error="onImgError(img)">
```

注意：`img` 是 v-for 的循环变量，不要修改它。`imgLoadErrorSet` 必须用 `reactive(new Set())` 确保响应式。

- [ ] **Step 2: 修复 DeliveryTemplatesPage.vue querySelector bug**

读取 `apps/user-web/src/pages/DeliveryTemplatesPage.vue` 找到第 214 行 `createNew` 和第 237 行 `insertVariable`。

在 script setup 顶部添加 ref：
```javascript
const templateTextareaRef = ref(null)
const templateNameInputRef = ref(null)
```

在模板中找到 textarea 和 name input，添加 ref 绑定：
```html
<textarea ref="templateTextareaRef" ...></textarea>
<input ref="templateNameInputRef" ... />
```

修改 `createNew` 中 `document.querySelector('input')?.focus?.()` 为 `templateNameInputRef.value?.focus?.()`。

修改 `insertVariable` 中 `document.querySelector('textarea')` 为 `templateTextareaRef.value`。

- [ ] **Step 3: 修复 AutoReplyPage.vue querySelector bug**

读取 `apps/user-web/src/pages/AutoReplyPage.vue` 第 98 行 `focusRuleName`。

在 script setup 添加 ref：
```javascript
const ruleNameInputRef = ref(null)
```

在模板中找到规则名称 input，添加 `ref="ruleNameInputRef"`。

修改 `focusRuleName` 中 `document.querySelector('input')?.focus?.()` 为 `ruleNameInputRef.value?.focus?.()`。

- [ ] **Step 4: 修复 ScheduledTasksPage.vue querySelector bug**

读取 `apps/user-web/src/pages/ScheduledTasksPage.vue` 第 22 行 `focusTaskName`。

在 script setup 添加 ref：
```javascript
const taskNameInputRef = ref(null)
```

在模板中找到任务名称 input（`<input v-model="form.taskName">`），改为 `<input ref="taskNameInputRef" v-model="form.taskName">`。

修改 `focusTaskName` 中 `document.querySelector('input')?.focus?.()` 为 `taskNameInputRef.value?.focus?.()`。

- [ ] **Step 5: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add apps/user-web/src/pages/WorkflowPage.vue apps/user-web/src/pages/DeliveryTemplatesPage.vue apps/user-web/src/pages/AutoReplyPage.vue apps/user-web/src/pages/ScheduledTasksPage.vue
git commit -m "fix: 修复 querySelector 全局选择器 bug 和 WorkflowPage img @error 响应式失效 bug"
```

---

## Task 3: P0 Bug 修复 - WorkflowTasksPage try/catch + ScheduledTasksPage 校验

**Files:**
- Modify: `apps/user-web/src/pages/WorkflowTasksPage.vue`
- Modify: `apps/user-web/src/pages/ScheduledTasksPage.vue`

- [ ] **Step 1: WorkflowTasksPage.vue 补 try/catch**

读取 `apps/user-web/src/pages/WorkflowTasksPage.vue`。

在 script setup 添加 error ref：
```javascript
const error = ref('')
```

修改 `load` 函数（第 88-93 行）：
```javascript
async function load() {
  error.value = ''
  try {
    const res = await listWorkflowExecutions({ current: current.value, size: 20, status: status.value })
    tasks.value = res.data?.records || []
    total.value = res.data?.total || 0
    if (!detail.value && tasks.value[0]) open(tasks.value[0].id)
  } catch (e) {
    error.value = e.message || '任务列表加载失败'
  }
}
```

修改 `open` 函数（第 94 行）：
```javascript
async function open(id) {
  error.value = ''
  try {
    detail.value = (await getWorkflowExecution(id)).data
  } catch (e) {
    error.value = e.message || '任务详情加载失败'
  }
}
```

修改 `terminateCurrent` 函数（第 96 行）：
```javascript
async function terminateCurrent(){
  if(!detail.value) return
  error.value = ''
  try {
    const reason = await globalConfirm.prompt('请输入终止原因', '用户手动终止')
    if(reason === false || !reason) return
    await terminateWorkflowExecution(detail.value.id, {reason})
    await open(detail.value.id)
    await load()
  } catch (e) {
    error.value = e.message || '终止执行失败'
  }
}
```

修改 `retryFailed` 函数（第 97 行）：
```javascript
async function retryFailed(){
  if(!detail.value) return
  error.value = ''
  try {
    const failed = (detail.value.steps || []).find(s => s.status === 'failed')
    const res = await retryWorkflowFailedNode(detail.value.id, {nodeKey: failed?.nodeKey})
    detail.value = res.data || res
    await load()
  } catch (e) {
    error.value = e.message || '重试失败节点失败'
  }
}
```

在模板顶部 stat-grid 前添加错误提示：
```html
<div v-if="error" class="global-notice error">{{ error }}</div>
```

- [ ] **Step 2: ScheduledTasksPage.vue 加 Cron/JSON 校验**

读取 `apps/user-web/src/pages/ScheduledTasksPage.vue`。

在 script setup 添加校验函数和 ref：
```javascript
const cronError = ref('')
const jsonError = ref('')

function validateCron(cron) {
  if (!cron) return 'Cron 表达式不能为空'
  // 简化校验：支持 5-7 段，允许 * / - , ? 数字
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5 || parts.length > 7) return 'Cron 表达式应为 5-7 段'
  if (!/^[\d*/,-?]+$(\s[\d*/,-?]+)*$/.test(cron.trim())) return 'Cron 表达式含非法字符'
  return ''
}

function validateJson(json) {
  if (!json) return ''
  try { JSON.parse(json); return '' }
  catch (e) { return 'JSON 格式错误：' + e.message }
}
```

修改 `save` 函数，在保存前校验：
```javascript
async function save(){
  if(saving.value) return
  cronError.value = validateCron(form.cronExpression)
  jsonError.value = validateJson(form.configJson)
  if (cronError.value || jsonError.value) return
  saving.value = true; error.value = ''; success.value = ''
  try{
    const data = {...form}
    if(form.id) await updateScheduledTask(form.id, data)
    else await createScheduledTask(data)
    success.value = form.id ? '任务已更新' : '任务已创建'
    reset(); await load()
  }catch(e){ error.value = e.message }finally{ saving.value = false }
}
```

在模板中 Cron 输入框下加错误提示：
```html
<div class="form-row">
  <label>Cron</label>
  <input v-model="form.cronExpression" placeholder="0 0/30 * * * ?">
  <span v-if="cronError" class="input-error">{{ cronError }}</span>
</div>
```

在模板中配置JSON输入框下加错误提示：
```html
<div class="form-row">
  <label>配置JSON</label>
  <textarea v-model="form.configJson"></textarea>
  <span v-if="jsonError" class="input-error">{{ jsonError }}</span>
</div>
```

- [ ] **Step 3: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/pages/WorkflowTasksPage.vue apps/user-web/src/pages/ScheduledTasksPage.vue
git commit -m "fix: WorkflowTasksPage 补全 try/catch 错误处理，ScheduledTasksPage 加 Cron/JSON 前端校验"
```

---

## Task 4: P0 Bug 修复 - ProductPublishPage 取消确认+SKU + 文字行为对齐

**Files:**
- Modify: `apps/user-web/src/pages/ProductPublishPage.vue`
- Modify: `apps/user-web/src/pages/ProductsPage.vue`
- Modify: `apps/user-web/src/pages/AutoDeliveryPage.vue`

- [ ] **Step 1: ProductPublishPage 取消按钮加未保存确认**

读取 `apps/user-web/src/pages/ProductPublishPage.vue` 第 291 行附近，找到"取消"按钮 `@click="emit('navigate','products')"`。

在 script setup 引入 confirmAction：
```javascript
import { confirmAction } from '../utils/confirmAction.js'
```

添加取消确认函数：
```javascript
async function handleCancel() {
  const ok = await confirmAction({
    title: '确认离开？',
    description: '未保存的更改将丢失，确定要离开吗？',
    confirmText: '离开',
    dangerous: true
  })
  if (ok) emit('navigate', 'products')
}
```

修改"取消"按钮：`@click="handleCancel"`。

- [ ] **Step 2: ProductPublishPage SKU 实现 add/remove row**

读取 ProductPublishPage.vue 第 225-231 行 SKU 表格部分。

确保 script setup 中 skus 是 ref 数组（若不是则改为）：
```javascript
const skus = ref([{ spec: '', price: '', stock: '' }])
```

在模板 SKU 表格操作列，把 `▢` 死按钮改为删除按钮：
```html
<button class="link danger-text" @click="removeSku(idx)" title="删除此行">✕</button>
```

在 SKU 表格下方添加"添加规格"按钮：
```html
<AppButton type="ghost" @click="addSku">+ 添加规格</AppButton>
```

添加函数：
```javascript
function addSku() { skus.value.push({ spec: '', price: '', stock: '' }) }
function removeSku(idx) {
  if (skus.value.length <= 1) return
  skus.value.splice(idx, 1)
}
```

- [ ] **Step 3: ProductsPage refreshSingle 文字行为对齐**

读取 `apps/user-web/src/pages/ProductsPage.vue`，搜索 `refreshSingle` 函数。

将函数内提示文字从"刷新单个商品"改为"同步全部商品"（因为实际调用的是全量同步逻辑）。

- [ ] **Step 4: AutoDeliveryPage removeConfig 文字行为对齐**

读取 `apps/user-web/src/pages/AutoDeliveryPage.vue`，搜索 `removeConfig` 函数。

将 confirmDelete 提示文字从"删除配置"改为"禁用配置"（因为实际是 enabled:0）。

- [ ] **Step 5: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add apps/user-web/src/pages/ProductPublishPage.vue apps/user-web/src/pages/ProductsPage.vue apps/user-web/src/pages/AutoDeliveryPage.vue
git commit -m "fix: ProductPublishPage 取消加未保存确认+SKU增删行，ProductsPage/AutoDeliveryPage 文字行为对齐"
```

---

## Task 5: 静默 catch 补全

**Files:**
- Modify: `apps/user-web/src/pages/DeliveryStatementPage.vue`
- Modify: `apps/user-web/src/pages/WorkflowPage.vue`
- Modify: `apps/user-web/src/pages/AutoReplyPage.vue`
- Modify: `apps/user-web/src/pages/ProductPublishPage.vue`

- [ ] **Step 1: DeliveryStatementPage.vue load 函数加错误提示**

读取 `apps/user-web/src/pages/DeliveryStatementPage.vue` 第 121-136 行 `load` 函数。

修改 catch 块，从静默回退改为显示错误：
```javascript
async function load() {
  loading.value = true
  try {
    const res = await getDeliveryStatement()
    content.value = res.data?.content || defaultContent
  } catch (e) {
    error.value = e.message || '声明内容加载失败'
  } finally {
    loading.value = false
  }
}
```

在模板中加错误提示：`<div v-if="error" class="global-notice error">{{ error }}</div>`

- [ ] **Step 2: WorkflowPage.vue loadHistoryAddresses / loadImageModels 加提示**

读取 `apps/user-web/src/pages/WorkflowPage.vue` 第 717-739 行。

修改 `loadHistoryAddresses` catch 块：
```javascript
} catch (e) {
  console.warn('[loadHistoryAddresses]', e)
  historyAddressError.value = '历史地址加载失败'
}
```

修改 `loadImageModels` catch 块：
```javascript
} catch (e) {
  console.warn('[loadImageModels]', e)
  imageModelsError.value = '模型列表加载失败，请检查后台配置'
}
```

在 script setup 添加：
```javascript
const historyAddressError = ref('')
const imageModelsError = ref('')
```

在模板对应下拉框处显示错误（历史地址下拉/生图模型下拉）：
```html
<option v-if="historyAddressError" disabled>{{ historyAddressError }}</option>
<option v-if="imageModelsError" disabled>{{ imageModelsError }}</option>
```

- [ ] **Step 3: AutoReplyPage.vue loadReplyLogs/loadReplyStats 加 toast**

读取 `apps/user-web/src/pages/AutoReplyPage.vue` 第 92-93 行。

修改两个函数的 catch 块：
```javascript
} catch (e) {
  console.warn('[loadReplyLogs]', e)
  replyLogsError.value = e.message || '回复日志加载失败'
}
```
```javascript
} catch (e) {
  console.warn('[loadReplyStats]', e)
  // 统计非关键，静默
}
```

添加 ref：`const replyLogsError = ref('')`

在日志列表区域加空态：`<EmptyState v-if="replyLogsError" variant="error" :title="replyLogsError" />`

- [ ] **Step 4: ProductPublishPage 静默 catch 补全**

读取 `apps/user-web/src/pages/ProductPublishPage.vue` 第 449, 585, 729, 882 行。

修改 `loadAiCategoryStatus` catch（449行）：加 `console.warn('[loadAiCategoryStatus]', e)`（保持 disabled 默认值）

修改 `refreshCategoriesInBackground` catch（585行）：加 `console.warn('[refreshCategoriesInBackground]', e)`（非关键，保留静默但加日志）

修改 POI 搜索 catch（729行）：
```javascript
} catch (e) {
  console.warn('[poiSearch]', e)
  poiList.value = []
  toast('位置搜索失败')
}
```

修改 `runtimeConfig` catch（882行）：加 `console.warn('[runtimeConfig]', e)`（用默认配置）

- [ ] **Step 5: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add apps/user-web/src/pages/DeliveryStatementPage.vue apps/user-web/src/pages/WorkflowPage.vue apps/user-web/src/pages/AutoReplyPage.vue apps/user-web/src/pages/ProductPublishPage.vue
git commit -m "fix: 补全 9 处静默 catch 错误处理，关键路径显示 toast/EmptyState，非关键路径加 console.warn"
```

---

## Task 6: LogsPage 重写对接真实接口

**Files:**
- Modify: `apps/user-web/src/pages/LogsPage.vue`
- Modify: `apps/user-web/src/api/operationLogs.js`

- [ ] **Step 1: 扩展 operationLogs.js API 封装**

修改 `apps/user-web/src/api/operationLogs.js`：
```javascript
import request from '../utils/request.js'

export const getOperationLogs = (params = {}) => request.get('/operation-logs', { params })

export const exportOperationLogs = (params = {}) => request.get('/operation-logs/export', { params, responseType: 'blob' })
```

- [ ] **Step 2: 重写 LogsPage.vue 对接真实接口**

用以下完整内容替换 `apps/user-web/src/pages/LogsPage.vue`：

```vue
<template>
  <div class="grid" style="grid-template-columns:minmax(0,1fr) 460px;gap:18px">
    <div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div class="grid stat-grid">
        <StatCard title="总操作数" :value="total" change="真实记录" icon="record" />
        <StatCard title="当前页条数" :value="rows.length" change="本页统计" icon="shield" color="green" />
        <StatCard title="失败数" :value="failedCount" change="本页统计" icon="warning" color="red" />
        <StatCard title="成功数" :value="successCount" change="本页统计" icon="shield" color="green" />
      </div>
      <CardPanel title="操作日志">
        <div class="toolbar">
          <select class="input" v-model="filters.operationType" @change="load">
            <option value="">全部类型</option>
            <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
          </select>
          <input class="input" v-model="filters.keyword" placeholder="关键词搜索" @keyup.enter="load">
          <AppButton type="primary" :disabled="loading" @click="load">{{ loading ? '查询中...' : '查询' }}</AppButton>
          <AppButton :disabled="loading" @click="exportCsv">导出CSV</AppButton>
        </div>
        <BaseTable :columns="cols" :rows="rows">
          <template #status="{row}"><Badge :type="row.status==='失败'?'red':row.status==='部分成功'?'orange':'green'">{{ row.status || '成功' }}</Badge></template>
          <template #op="{row}"><button class="link" @click="showDetail(row)">查看</button></template>
          <template #empty><EmptyState icon="📋" title="暂无操作日志" description="系统操作记录将在此显示。" /></template>
        </BaseTable>
        <div class="pagination">
          <span>共 {{ total }} 条</span>
          <button class="page-no" :disabled="current<=1" @click="goPage(current-1)">上一页</button>
          <span class="page-no active">{{ current }}</span>
          <button class="page-no" :disabled="current*size>=total" @click="goPage(current+1)">下一页</button>
        </div>
      </CardPanel>
    </div>
    <div class="right-drawer">
      <template v-if="detail">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3>日志详情</h3>
          <button class="modal-close" @click="detail=null"><Icon name="close" /></button>
        </div>
        <p>日志ID　<b>{{ detail.id || '-' }}</b></p>
        <div class="grid" style="grid-template-columns:repeat(2,1fr);gap:10px">
          <div class="metric-tile"><span>操作类型</span><b>{{ detail.operationType || '-' }}</b></div>
          <div class="metric-tile"><span>目标类型</span><b>{{ detail.targetType || '-' }}</b></div>
          <div class="metric-tile"><span>状态</span><Badge>{{ detail.status || '成功' }}</Badge></div>
          <div class="metric-tile"><span>操作人</span><b>{{ detail.operator || '-' }}</b></div>
        </div>
        <div class="option-line"><span>操作时间</span><b>{{ detail.createdTime || '-' }}</b></div>
        <div class="option-line"><span>目标ID</span><b>{{ detail.targetId || '-' }}</b></div>
        <p class="subtle" v-if="detail.description">描述：{{ detail.description }}</p>
        <h4 v-if="detail.requestParams">请求参数</h4>
        <pre class="mock-json" v-if="detail.requestParams">{{ formatJson(detail.requestParams) }}</pre>
        <h4 v-if="detail.responseResult">响应结果</h4>
        <pre class="mock-json" v-if="detail.responseResult">{{ formatJson(detail.responseResult) }}</pre>
      </template>
      <EmptyState v-else icon="📋" title="选择日志查看详情" description="点击左侧列表中的「查看」按钮，这里会展示日志详情。" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import { getOperationLogs, exportOperationLogs } from '../api/operationLogs.js'

const loading = ref(false)
const error = ref('')
const rows = ref([])
const total = ref(0)
const current = ref(1)
const size = ref(20)
const detail = ref(null)
const filters = reactive({ operationType: '', keyword: '' })

const types = ['登录', '发送消息', '自动发货', '自动回复', '确认收货', '同步商品', '卡密发货', '其他']

const cols = [
  { key: 'id', title: '日志ID' },
  { key: 'operationType', title: '操作类型' },
  { key: 'targetType', title: '目标类型' },
  { key: 'description', title: '描述' },
  { key: 'status', title: '状态' },
  { key: 'operator', title: '操作人' },
  { key: 'createdTime', title: '操作时间' },
  { key: 'op', title: '操作' }
]

const failedCount = computed(() => rows.value.filter(r => r.status === '失败').length)
const successCount = computed(() => rows.value.filter(r => r.status !== '失败').length)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getOperationLogs({
      current: current.value,
      size: size.value,
      operationType: filters.operationType,
      keyword: filters.keyword
    })
    rows.value = res.data?.records || res.data?.list || []
    total.value = res.data?.total || 0
  } catch (e) {
    error.value = e.message || '日志加载失败'
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  if (p < 1 || (p - 1) * size.value >= total.value) return
  current.value = p
  load()
}

function showDetail(row) { detail.value = row }

function formatJson(str) {
  if (!str) return ''
  try { return JSON.stringify(JSON.parse(str), null, 2) } catch (e) { return str }
}

async function exportCsv() {
  try {
    const blob = await exportOperationLogs({ operationType: filters.operationType, keyword: filters.keyword })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `operation-logs-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e.message || '导出失败'
  }
}

onMounted(load)
</script>
```

- [ ] **Step 3: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/pages/LogsPage.vue apps/user-web/src/api/operationLogs.js
git commit -m "feat(LogsPage): 重写对接真实操作日志接口，移除整页 mock 数据，支持分页/筛选/导出"
```

---

## Task 7: VIP 相关 - AccountVipPage 路由移除 + VipPage 删 fallbackPlans

**Files:**
- Modify: `apps/user-web/src/App.vue`
- Modify: `apps/user-web/src/data/nav.js`
- Modify: `apps/user-web/src/pages/VipPage.vue`

- [ ] **Step 1: App.vue 移除 account-vip 路由和 headerActions**

读取 `apps/user-web/src/App.vue`。

第 87 行删除 `'account-vip': asyncPage(() => import('./pages/AccountVipPage.vue')),`

第 357 行删除 `'account-vip': [{ text:'升级当前账号', type:'primary' }]` 整行。

- [ ] **Step 2: nav.js 移除 account-vip 导航项**

读取 `apps/user-web/src/data/nav.js`，搜索 `account-vip` 并删除对应的导航项。

- [ ] **Step 3: VipPage.vue 删 fallbackPlans，失败显示 EmptyState**

读取 `apps/user-web/src/pages/VipPage.vue`。

删除 `fallbackPlans` 常量（第 161-165 行附近）。

修改 `loadPlans` 函数，失败时不再回退：
```javascript
async function loadPlans() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getBillingPlans()
    plans.value = res.data || []
  } catch (e) {
    plans.value = []
    loadError.value = e.message || '套餐加载失败'
  } finally {
    loading.value = false
  }
}
```

添加 ref：`const loadError = ref('')`

修改 `displayPlans` 计算属性，移除对 fallbackPlans 的回退：
```javascript
const displayPlans = computed(() => plans.value)
```

在套餐列表区域加错误空态：
```html
<EmptyState v-if="loadError" variant="error" :title="loadError" description="请稍后重试">
  <template #actions><AppButton type="primary" @click="loadPlans">重试</AppButton></template>
</EmptyState>
```

- [ ] **Step 4: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/App.vue apps/user-web/src/data/nav.js apps/user-web/src/pages/VipPage.vue
git commit -m "refactor: 移除 AccountVipPage 路由(与VipPage重叠)，VipPage 删 fallbackPlans 改用 EmptyState"
```

---

## Task 8: MessagesPage 买家画像空态 + 快捷回复对接 + AI推荐空态

**Files:**
- Modify: `apps/user-web/src/pages/MessagesPage.vue`

- [ ] **Step 1: 买家画像字段显示空态**

读取 `apps/user-web/src/pages/MessagesPage.vue` 第 296-344 行右侧详情面板。

找到写死的买家画像字段（'阳光男孩'、'2023-05-12'、'上海市 浦东新区'、'750' 等），将它们改为显示"—"：

```html
<!-- 买家画像区域 -->
<div class="buyer-profile">
  <p class="subtle" style="margin-bottom:8px">买家画像数据待后端补全</p>
  <div class="option-line"><span>注册时间</span><b>{{ conv.registeredAt || '—' }}</b></div>
  <div class="option-line"><span>地区</span><b>{{ conv.region || '—' }}</b></div>
  <div class="option-line"><span>近期咨询数</span><b>{{ conv.recentInquiryCount || '—' }}</b></div>
</div>
```

保留商品侧真实数据不变。

- [ ] **Step 2: 快捷回复对接 autoReply 接口**

在 script setup 引入：
```javascript
import { getAutoReplyRules } from '../api/autoReply.js'
```

替换写死的 `quickTemplates`（第 454-458 行）为 ref + 加载逻辑：
```javascript
const quickTemplates = ref([])
async function loadQuickTemplates() {
  try {
    const res = await getAutoReplyRules({ size: 50 })
    const rules = res.data?.records || res.data || []
    quickTemplates.value = rules.map(r => r.reply || r.content).filter(Boolean).slice(0, 6)
  } catch (e) {
    console.warn('[loadQuickTemplates]', e)
    quickTemplates.value = []
  }
}
```

在 `onMounted` 或会话切换时调用 `loadQuickTemplates()`。

模板中快捷回复为空时显示链接：
```html
<div v-if="quickTemplates.length === 0" class="subtle">
  暂无快捷回复模板，<a href="javascript:void(0)" @click="$emit('navigate','auto-reply')">去配置</a>
</div>
<div v-else v-for="t in quickTemplates" :key="t" class="chip" @click="insertQuickReply(t)">{{ t }}</div>
```

- [ ] **Step 3: AI 推荐回复显示空态**

找到 `aiReplies`（第 449-453 行）写死的 3 条，改为空数组：
```javascript
const aiReplies = ref([])
```

模板中 AI 推荐区域改为：
```html
<div class="ai-replies">
  <EmptyState variant="dev" icon="🤖" title="AI 推荐回复开发中" description="该功能正在开发，暂未上线。" />
</div>
```

隐藏"换一批"按钮（加 `v-if="false"` 或直接删除）。

- [ ] **Step 4: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/MessagesPage.vue
git commit -m "fix(MessagesPage): 买家画像显示空态，快捷回复对接autoReply接口，AI推荐显示开发中空态"
```

---

## Task 9: ProductPublishPage aiDesc 对接真实 AI 接口

**Files:**
- Modify: `apps/user-web/src/pages/ProductPublishPage.vue`
- Modify: `apps/user-web/src/api/aiChat.js` (确认接口是否存在)

- [ ] **Step 1: 确认 aiRewriteGoods 接口**

读取 `apps/user-web/src/api/aiChat.js` 或 `apps/user-web/src/api/opportunity.js`，查找 `aiRewriteGoods` 函数。WorkflowPage.vue 已使用此接口，确认其 import 路径。

- [ ] **Step 2: ProductPublishPage aiDesc 改调真实接口**

读取 `apps/user-web/src/pages/ProductPublishPage.vue` 第 895-897 行 `aiDesc` 函数。

在 script setup 引入（路径以 WorkflowPage 实际 import 为准）：
```javascript
import { aiRewriteGoods } from '../api/aiChat.js'
```

重写 `aiDesc` 函数：
```javascript
const aiDescLoading = ref(false)
async function aiDesc() {
  if (aiDescLoading.value) return
  if (!form.title && !form.description) {
    error.value = '请先填写商品标题或基础描述'
    return
  }
  aiDescLoading.value = true
  error.value = ''
  try {
    const res = await aiRewriteGoods({
      title: form.title,
      description: form.description || ''
    })
    form.description = res.data?.content || res.data?.description || res.data || ''
  } catch (e) {
    error.value = e.message || 'AI 描述生成失败'
  } finally {
    aiDescLoading.value = false
  }
}
```

模板中 AI 描述按钮加 loading：
```html
<AppButton type="primary" :disabled="aiDescLoading" @click="aiDesc">
  {{ aiDescLoading ? 'AI 生成中...' : 'AI 生成描述' }}
</AppButton>
```

- [ ] **Step 3: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/pages/ProductPublishPage.vue
git commit -m "feat(ProductPublishPage): aiDesc 对接真实 AI 接口，移除写死 mock 文案，加 loading 防抖"
```

---

## Task 10: AccountsPage/ConnectionsPage 健康分显示空态

**Files:**
- Modify: `apps/user-web/src/pages/AccountsPage.vue`
- Modify: `apps/user-web/src/pages/ConnectionsPage.vue`

- [ ] **Step 1: AccountsPage 健康分和 recentActivities 显示空态**

读取 `apps/user-web/src/pages/AccountsPage.vue` 第 512-675 行。

找到 `accountHealth` 函数（返回 98/70）和 `metricScore` 默认值（100/96/98/98），改为返回 null 或 '—'：
```javascript
function accountHealth() { return null } // 健康分接口开发中
```

模板中健康分显示位置改为：
```html
<b>{{ healthScore ?? '—' }}</b>
<span class="subtle" title="健康分接口开发中">健康分接口开发中</span>
```

找到 `recentActivities` 回退 mock 逻辑（第 618-675 行），删除 mock 回退，无数据时返回空数组：
```javascript
const recentActivities = computed(() => {
  // 无真实数据来源，返回空，待后端补全
  return []
})
```

模板中 recentActivities 列表区域，无数据时显示 EmptyState：
```html
<EmptyState v-if="recentActivities.length === 0" icon="📋" title="暂无最近活动" description="账号操作记录将在此显示。" />
```

- [ ] **Step 2: ConnectionsPage 健康环显示空态**

读取 `apps/user-web/src/pages/ConnectionsPage.vue` 第 44 行。

找到 `{{ selected.connected ? 96 : 60 }}` 写死分数，改为 '—'：
```html
<b>—</b>
```

找到 `conic-gradient(#16bf78 0 86%)` 写死健康环，改为灰色：
```html
<div class="health-ring" style="background:conic-gradient(#cbd5e1 0 100%)" title="健康分接口开发中">
  <span>—</span>
</div>
```

健康分明细面板（若有）显示 EmptyState：
```html
<EmptyState variant="dev" icon="💚" title="健康分接口开发中" description="账号健康分功能正在开发。" />
```

- [ ] **Step 3: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/pages/AccountsPage.vue apps/user-web/src/pages/ConnectionsPage.vue
git commit -m "fix: AccountsPage/ConnectionsPage 健康分和最近活动移除 mock，显示空态「接口开发中」"
```

---

## Task 11: Topbar 死按钮实现

**Files:**
- Modify: `apps/user-web/src/components/Topbar.vue`

- [ ] **Step 1: 重写 Topbar.vue 实现通知抽屉/帮助/全屏，隐藏搜索**

用以下完整内容替换 `apps/user-web/src/components/Topbar.vue`：

```vue
<template>
  <div class="topbar">
    <!-- 搜索本轮隐藏，待后端全局检索接口就绪 -->
    <button v-if="false" class="top-icon" type="button" aria-label="搜索"><Icon name="search" /></button>

    <!-- 通知 -->
    <button class="top-icon bell" type="button" aria-label="通知中心" @click="toggleNoticePanel">
      <span v-if="unreadCount > 0">{{ unreadCount }}</span>
      <Icon name="bell" />
    </button>

    <!-- 帮助 -->
    <button class="top-icon" type="button" aria-label="帮助文档" @click="openHelp">
      <Icon name="help" />
    </button>

    <!-- 全屏 -->
    <button class="top-icon" type="button" :aria-label="isFullscreen ? '退出全屏' : '进入全屏'" @click="toggleFullscreen">
      <Icon name="fullscreen" />
    </button>

    <button class="top-user" type="button" @click="$emit('open-profile-center')">
      <div class="avatar small avatar-img"></div>
      <span>{{ displayName }}</span>
      <em>{{ sseLabel }}</em>
      <b aria-hidden="true">⌄</b>
    </button>
    <div class="top-user-menu logout-only">
      <button type="button" @click="$emit('logout')">退出登录</button>
    </div>

    <!-- 通知抽屉 -->
    <div v-if="showNoticePanel" class="notice-panel" role="dialog" aria-label="通知中心">
      <div class="notice-panel-head">
        <h3>通知中心</h3>
        <button class="modal-close" @click="showNoticePanel = false" aria-label="关闭"><Icon name="close" /></button>
      </div>
      <div class="notice-panel-body">
        <EmptyState v-if="recentEvents.length === 0" icon="🔔" title="暂无通知" description="系统实时事件会在此显示。" />
        <div v-for="(ev, i) in recentEvents" :key="i" class="notice-item" @click="onNoticeClick(ev)">
          <b>{{ ev.title || ev.type || '事件' }}</b>
          <span>{{ ev.content || ev.message || '' }}</span>
          <small>{{ ev.time || '' }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import Icon from './Icon.vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  user: { type: Object, default: () => ({}) },
  sseStatus: { type: String, default: 'disconnected' },
  unreadCount: { type: [String, Number], default: 0 }
})
defineEmits(['logout', 'open-profile-center'])

const displayName = computed(() => props.user?.username || props.user?.displayName || props.user?.name || '管理员')
const sseLabel = computed(() => ({ connected: '在线', connecting: '连接中', disconnected: '离线' }[props.sseStatus] || '在线'))

const showNoticePanel = ref(false)
const recentEvents = ref([])
const isFullscreen = ref(false)

function toggleNoticePanel() {
  showNoticePanel.value = !showNoticePanel.value
}

function onSseEvent(e) {
  const detail = e.detail || {}
  recentEvents.value.unshift({
    type: detail.type || detail.eventType,
    title: detail.title || detail.eventType,
    content: detail.content || detail.message,
    time: new Date().toLocaleTimeString(),
    raw: detail
  })
  if (recentEvents.value.length > 50) recentEvents.value.pop()
}

function onNoticeClick(ev) {
  // 按事件类型路由映射（可扩展）
  const routeMap = { message: 'messages', order: 'auto-delivery', account: 'accounts', workflow: 'workflow-tasks' }
  const key = Object.keys(routeMap).find(k => (ev.type || '').toLowerCase().includes(k))
  if (key) {
    location.hash = `#/${routeMap[key]}`
    showNoticePanel.value = false
  }
}

function openHelp() {
  window.open('https://github.com/', '_blank', 'noopener')
}

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    document.documentElement.requestFullscreen().catch(() => {})
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  window.addEventListener('xya-sse-event', onSseEvent)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})
onBeforeUnmount(() => {
  window.removeEventListener('xya-sse-event', onSseEvent)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<style scoped>
.notice-panel {
  position: absolute;
  right: 0;
  top: 46px;
  width: 360px;
  max-height: 480px;
  background: #fff;
  border: 1px solid var(--line, #e7edf7);
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(30, 52, 92, .14);
  z-index: 40;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.notice-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef3fa;
}
.notice-panel-head h3 { margin: 0; font-size: 16px; }
.notice-panel-body { overflow: auto; padding: 8px; }
.notice-item {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background .15s;
}
.notice-item:hover { background: #f3f8ff; }
.notice-item b { display: block; font-size: 14px; color: #16213e; }
.notice-item span { display: block; color: #667085; font-size: 13px; margin-top: 3px; }
.notice-item small { color: #98a2b3; font-size: 11px; }
.modal-close {
  border: 0; background: transparent; width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
</style>
```

- [ ] **Step 2: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
git add apps/user-web/src/components/Topbar.vue
git commit -m "feat(Topbar): 实现通知抽屉(SSE事件聚合)/帮助跳转/全屏切换，隐藏搜索，补全aria-label"
```

---

## Task 12: 视觉质感轻量提升

**Files:**
- Modify: `apps/user-web/src/styles.css`

- [ ] **Step 1: 调整全局阴影变量为双层柔和阴影**

读取 `apps/user-web/src/styles.css` 第 14 行。

修改：
```css
:root {
  /* ... 其他变量不变 ... */
  --shadow: 0 1px 2px rgba(31, 53, 94, .04), 0 8px 24px rgba(31, 53, 94, .06);
  /* ... */
}
```

- [ ] **Step 2: 添加 hover/transition/focus-visible 全局样式**

在 styles.css 末尾追加：

```css
/* 视觉质感提升：hover/transition/focus */
.stat-card,
.card-panel,
.right-drawer,
.list-card,
.detail-card,
.quick-card,
.feature-card,
.vip-card,
.preview-card,
.metric-tile {
  transition: transform .18s ease, box-shadow .18s ease;
}

.quick-card:hover,
.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 1px 2px rgba(31, 53, 94, .04), 0 12px 32px rgba(31, 53, 94, .10);
}

.app-btn {
  transition: transform .12s ease, box-shadow .18s ease, opacity .15s ease;
}

.app-btn:active:not(:disabled) {
  transform: scale(.98);
}

/* 焦点态：键盘导航可见环 */
.input:focus-visible,
select:focus-visible,
input:focus-visible,
textarea:focus-visible,
.app-btn:focus-visible,
button:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 1px;
}

/* 圆角层级：panel 14px / sub-card 10px / input 7px / chip 6px */
.metric-tile { border-radius: 10px; }
.chip { border-radius: 6px; }
```

- [ ] **Step 3: 统一空态样式**

在 styles.css 末尾追加，统一原有的 `.empty-state`、`.empty-mini`、`.empty-box`、`.empty-placeholder` 为一致风格（保留原 class 名以免破坏现有引用）：

```css
/* 空态统一风格 */
.empty-state,
.empty-mini,
.empty-box,
.empty-placeholder,
.table-empty {
  padding: 24px;
  text-align: center;
  color: #8a96aa;
  background: linear-gradient(135deg, #fbfdff, #f6f9ff);
  border: 1px dashed #cfd9ea;
  border-radius: 14px;
}
```

- [ ] **Step 4: 构建验证**

Run: `cd apps/user-web && npm run build`
Expected: 构建成功

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/styles.css
git commit -m "style: 视觉质感提升 - 双层柔和阴影/卡片hover/焦点环/圆角层级/空态统一"
```

---

## 自审清单

**Spec coverage（设计文档覆盖检查）:**

- [x] 模块1 P0 Bug: Task 2 (querySelector+img), Task 3 (try/catch+校验), Task 4 (取消确认+SKU+文字)
- [x] 模块2 假数据对接: Task 6 (LogsPage), Task 7 (VIP), Task 8 (MessagesPage), Task 9 (aiDesc)
- [x] 模块3 假数据空态: Task 8 (AI推荐), Task 10 (健康分)
- [x] 模块4 Topbar: Task 11
- [x] 模块5 静默catch: Task 5
- [x] 模块6 视觉: Task 12 + Task 1 (EmptyState)

**Placeholder scan:** 无 TBD/TODO，每个 step 都有具体代码或精确修改点。

**Type consistency:** `imgLoadErrorSet`、`templateTextareaRef`、`aiDescLoading` 等命名前后一致。`EmptyState` 的 variant 取值（default/search/error/dev）在 Task 1 定义，后续 Task 5/7/8/10/11 使用一致。

**修正记录:**
- 审计报告称 ScheduledTasksPage remove 未调用 confirmDelete，实际已调用（第21行）。计划中 Task 3 移除该项，只保留 querySelector 和校验修复。

---

## 执行顺序建议

按 Task 编号顺序执行（1→12）。Task 1 (EmptyState) 必须先做，因为 Task 5/7/8/10/11 依赖它。

每个 Task 完成后 `npm run build` 验证，独立 commit。
