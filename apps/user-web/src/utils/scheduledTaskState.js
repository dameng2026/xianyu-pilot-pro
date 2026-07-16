const TASK_TYPE_LABELS = {
  sync_goods: '同步商品',
  sync_orders: '同步订单',
  sync_delivery_status: '同步发货状态',
  redelivery: '安排重新发货',
  polish_goods: '商品润色',
  workflow: '工作流',
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

export const DEFAULT_SCHEDULED_TASK_TYPES = [
  'sync_goods',
  'sync_orders',
  'sync_delivery_status',
  'auto_delivery',
  'redelivery',
  'polish_goods',
  'workflow'
]

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

export function normalizeScheduledTaskPayload(form) {
  const accountValue = String(form?.accountId ?? '').trim()
  return {
    taskName: String(form?.taskName || '').trim(),
    taskType: String(form?.taskType || '').trim().toLowerCase(),
    cronExpression: String(form?.cronExpression || '').trim(),
    configJson: String(form?.configJson || '{}').trim() || '{}',
    accountId: accountValue ? Number(accountValue) : null,
    enabled: form?.enabled ? 1 : 0
  }
}
