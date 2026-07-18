// 定时任务类型与调度配置工具
// 任务类型分为：
//   - 默认显示（用于创建下拉）：sync_goods / sync_orders / auto_redelivery / one_click_polish / workflow
//   - 历史类型（仅用于列表展示旧任务）：sync_delivery_status / redelivery / polish_goods / auto_delivery / sync_account / auto_reply 等
// 多账号通过 configJson.accountIds 数组存储；accountId 字段保留为兼容字段（取首个账号）

const TASK_TYPE_LABELS = {
  // 新增/重新定义的任务类型（默认显示在创建下拉）
  sync_goods: '同步商品（每日）',
  sync_orders: '同步订单（每日）',
  auto_redelivery: '自动补发订单（间隔）',
  one_click_polish: '一键擦亮商品（每日）',
  workflow: '执行工作流（每日/每周）',
  // 旧任务类型（保留用于历史任务展示，不在创建下拉中显示）
  sync_delivery_status: '同步发货状态',
  redelivery: '安排重新发货',
  polish_goods: '商品润色',
  auto_delivery: '自动发货',
  delivery: '发货',
  'auto-delivery': '自动发货',
  sync_account: '同步账号',
  account_sync: '同步账号',
  refresh_account: '刷新账号',
  auto_reply: '自动回复',
  reply: '回复',
  'auto-reply': '自动回复'
}

// 创建任务下拉中可选的任务类型（顺序即下拉顺序）
export const DEFAULT_SCHEDULED_TASK_TYPES = [
  'sync_goods',
  'sync_orders',
  'auto_redelivery',
  'one_click_polish',
  'workflow'
]

// 各任务类型的调度模式
export const TASK_SCHEDULE_MODES = {
  sync_goods: 'daily',
  sync_orders: 'daily',
  auto_redelivery: 'interval',
  one_click_polish: 'daily',
  workflow: 'daily_or_weekly'
}

// 是否需要选择账号（工作流任务使用工作流自带的账号配置）
export function taskRequiresAccounts(taskType) {
  return taskType !== 'workflow'
}

export function taskTypeLabel(taskType) {
  const normalized = String(taskType || '').trim().toLowerCase()
  return TASK_TYPE_LABELS[normalized] || normalized || '-'
}

export function normalizeScheduledTaskTypes(taskTypes = DEFAULT_SCHEDULED_TASK_TYPES) {
  return taskTypes.map(value => ({
    value,
    label: taskTypeLabel(value)
  }))
}

// Cron 表达式生成：根据任务类型和配置自动生成
// - daily: 每日 HH:mm → `0 mm HH * * ?`
// - interval: 每 N 分钟（最低 10）→ `0 */N * * * ?`
// - daily_or_weekly: 每日 `0 mm HH * * ?`；每周 `0 mm HH ? * DOW`
export function buildCronExpression(taskType, config = {}) {
  const type = String(taskType || '').toLowerCase()

  if (type === 'auto_redelivery') {
    const minutes = Math.max(10, Number(config.intervalMinutes) || 10)
    return `0 */${minutes} * * * ?`
  }

  if (type === 'workflow') {
    const { hh, mm } = parseTime(config.workflowTime)
    if (config.scheduleMode === 'weekly') {
      const days = Array.isArray(config.weekdays) && config.weekdays.length > 0
        ? config.weekdays.slice().sort((a, b) => a - b).join(',')
        : '1'
      return `0 ${mm} ${hh} ? * ${days}`
    }
    return `0 ${mm} ${hh} * * ?`
  }

  // sync_goods / sync_orders / one_click_polish
  const { hh, mm } = parseTime(config.dailyTime)
  return `0 ${mm} ${hh} * * ?`
}

// 从表单数据构建 configJson 对象
export function buildTaskConfig(taskType, form = {}) {
  const type = String(taskType || '').toLowerCase()
  const config = {}

  if (type !== 'workflow') {
    config.accountIds = (Array.isArray(form.accountIds) ? form.accountIds : [])
      .map(id => Number(id))
      .filter(id => Number.isFinite(id) && id > 0)
  }

  if (type === 'auto_redelivery') {
    config.intervalMinutes = Math.max(10, Number(form.intervalMinutes) || 10)
    return config
  }

  if (type === 'workflow') {
    config.workflowId = form.workflowId ? Number(form.workflowId) : null
    config.scheduleMode = form.scheduleMode === 'weekly' ? 'weekly' : 'daily'
    config.workflowTime = form.workflowTime || '00:00'
    if (config.scheduleMode === 'weekly') {
      config.weekdays = (Array.isArray(form.weekdays) ? form.weekdays : [])
        .map(d => Number(d))
        .filter(d => Number.isFinite(d) && d >= 1 && d <= 7)
    }
    return config
  }

  // sync_goods / sync_orders / one_click_polish
  config.dailyTime = form.dailyTime || '00:00'
  return config
}

// 将表单标准化为提交给后端的 payload
// 同时生成 cronExpression 与 configJson，前端无需用户手填
export function normalizeScheduledTaskPayload(form) {
  const taskType = String(form?.taskType || '').trim().toLowerCase()
  const config = buildTaskConfig(taskType, form || {})
  const cronExpression = buildCronExpression(taskType, config)
  const accountIds = Array.isArray(config.accountIds) ? config.accountIds : []
  const primaryAccountId = accountIds.length > 0 ? Number(accountIds[0]) : null

  return {
    taskName: String(form?.taskName || '').trim(),
    taskType,
    cronExpression,
    configJson: JSON.stringify(config),
    accountId: primaryAccountId,
    accountIds,
    enabled: form?.enabled ? 1 : 0
  }
}

// 从后端任务数据还原表单字段（用于编辑时回填）
export function hydrateFormFromTask(task) {
  const config = parseConfigJson(task?.configJson)
  const taskType = String(task?.taskType || '').toLowerCase()

  const form = {
    id: task?.id ?? null,
    taskName: task?.taskName || '',
    taskType,
    enabled: task?.enabled === 1 || task?.enabled === true
  }

  // 还原 accountIds：优先取 config.accountIds，否则退回到 task.accountId
  const configIds = Array.isArray(config.accountIds) ? config.accountIds : []
  const accountIds = configIds.length > 0
    ? configIds.map(id => Number(id)).filter(id => Number.isFinite(id) && id > 0)
    : (task?.accountId ? [Number(task.accountId)] : [])
  form.accountIds = accountIds

  if (taskType === 'auto_redelivery') {
    form.intervalMinutes = Math.max(10, Number(config.intervalMinutes) || 10)
  } else if (taskType === 'workflow') {
    form.workflowId = config.workflowId ? String(config.workflowId) : ''
    form.scheduleMode = config.scheduleMode === 'weekly' ? 'weekly' : 'daily'
    form.workflowTime = config.workflowTime || '00:00'
    form.weekdays = Array.isArray(config.weekdays)
      ? config.weekdays.map(d => Number(d)).filter(d => Number.isFinite(d) && d >= 1 && d <= 7)
      : []
  } else if (taskType === 'sync_goods' || taskType === 'sync_orders' || taskType === 'one_click_polish') {
    form.dailyTime = config.dailyTime || '00:00'
  }

  return form
}

function parseTime(value) {
  const text = String(value || '00:00').trim()
  const match = /^(\d{1,2}):(\d{1,2})$/.exec(text)
  if (!match) return { hh: '0', mm: '0' }
  const hh = Math.max(0, Math.min(23, Number(match[1]) || 0))
  const mm = Math.max(0, Math.min(59, Number(match[2]) || 0))
  return { hh: String(hh), mm: String(mm) }
}

function parseConfigJson(raw) {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try {
    const parsed = JSON.parse(String(raw))
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}
