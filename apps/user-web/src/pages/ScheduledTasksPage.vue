<template>
  <div class="layout-grid">
    <div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="tasksLoadError" class="global-notice error">定时任务加载失败：{{ tasksLoadError }}</div>
      <div v-if="success" class="global-notice success">{{ success }}</div>

      <CardPanel title="定时任务">
        <div v-if="loading" class="table-loading" role="status">定时任务加载中...</div>
        <EmptyState v-else-if="!tasksAvailable" icon="⚠" title="定时任务不可用" :description="tasksLoadError || '正在加载定时任务，请稍候。'" />
        <BaseTable v-else :columns="columns" :rows="rows">
          <template #taskType="{ row }">
            <div>
              <div class="strong">{{ row.taskTypeLabel }}</div>
              <div class="subtle">{{ row.taskType }}</div>
            </div>
          </template>
          <template #enabled="{ row }">
            <Badge :type="row.enabledBadge">{{ row.enabledText }}</Badge>
          </template>
          <template #op="{ row }">
            <div class="inline-actions">
              <button class="link" @click.stop="edit(row.raw)">编辑</button>
              <button class="link" @click.stop="run(row.raw.id)">
                {{ busyId === row.raw.id ? '运行中...' : '运行' }}
              </button>
              <button class="link danger-text" @click.stop="remove(row.raw.id)">删除</button>
            </div>
          </template>
        </BaseTable>
        <Pagination v-if="tasksAvailable" :total="total" :current="current" :page-size="pageSize" @page-change="goPage" />
      </CardPanel>
    </div>

    <div>
      <CardPanel :title="form.id ? '编辑任务' : '创建任务'">
        <div v-if="!tasksAvailable" class="global-notice error">任务服务状态未确认，已禁用创建、编辑、运行和删除操作。</div>
        <fieldset class="task-form-fieldset" :disabled="!tasksAvailable">
          <div class="form-field">
            <label for="scheduled-task-name">任务名称</label>
            <input id="scheduled-task-name" ref="taskNameInputRef" v-model="form.taskName" class="input" placeholder="例如：每日同步商品" />
          </div>

          <div class="form-field">
            <label for="scheduled-task-type">任务类型</label>
            <select id="scheduled-task-type" v-model="form.taskType" class="input" @change="onTaskTypeChange">
              <option v-for="option in taskTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div v-if="needsAccounts" class="form-field">
            <label>选择账号（可多选）</label>
            <div v-if="accountsLoading" class="hint">账号加载中...</div>
            <div v-else-if="accounts.length === 0" class="hint">暂无可用账号</div>
            <div v-else class="checkbox-grid" role="group" aria-label="账号多选">
              <label v-for="account in accounts" :key="account.id" class="checkbox-item">
                <input
                  type="checkbox"
                  :value="account.id"
                  :checked="form.accountIds.includes(account.id)"
                  :aria-label="`账号 ${accountLabel(account)}`"
                  @change="toggleAccount(account.id)"
                />
                <span class="checkbox-text">{{ accountLabel(account) }}</span>
              </label>
            </div>
            <div class="hint">
              已选 {{ form.accountIds.length }} 个
              <button v-if="form.accountIds.length > 0" type="button" class="link" @click="clearAccounts">清空</button>
            </div>
          </div>

          <!-- 每日运行时间：sync_goods / sync_orders / one_click_polish -->
          <div v-if="isDailyTimeTask" class="form-field">
            <label for="scheduled-daily-time">每日运行时间</label>
            <input id="scheduled-daily-time" v-model="form.dailyTime" type="time" class="input" />
          </div>

          <!-- 自动补发订单：间隔分钟 -->
          <div v-if="isAutoRedeliveryTask" class="form-field">
            <label for="scheduled-interval">执行间隔（分钟，最低 10）</label>
            <input
              id="scheduled-interval"
              ref="intervalInputRef"
              :value="form.intervalMinutes"
              type="text"
              inputmode="numeric"
              pattern="[0-9]*"
              class="input"
              @input="onIntervalInput"
              @blur="normalizeInterval"
            />
            <span class="hint">默认 10 分钟一次，最低 10 分钟</span>
            <span v-if="intervalMinutesWarning" class="hint" style="color: #d92d20;">{{ intervalMinutesWarning }}</span>
          </div>

          <!-- 工作流任务配置 -->
          <template v-if="isWorkflowTask">
            <div class="form-field">
              <label for="scheduled-workflow">选择工作流</label>
              <select id="scheduled-workflow" v-model="form.workflowId" class="input">
                <option value="">请选择工作流</option>
                <option v-for="wf in workflows" :key="wf.id" :value="String(wf.id)">
                  {{ wf.name }}
                </option>
              </select>
              <span v-if="workflows.length === 0" class="hint">暂无已配置的工作流，请先在工作流页面创建</span>
            </div>

            <div class="form-field">
              <label for="scheduled-schedule-mode">调度模式</label>
              <select id="scheduled-schedule-mode" v-model="form.scheduleMode" class="input">
                <option value="daily">每日</option>
                <option value="weekly">每周</option>
              </select>
            </div>

            <div class="form-field">
              <label for="scheduled-workflow-time">{{ form.scheduleMode === 'weekly' ? '每周运行时间' : '每日运行时间' }}</label>
              <input id="scheduled-workflow-time" v-model="form.workflowTime" type="time" class="input" />
            </div>

            <div v-if="form.scheduleMode === 'weekly'" class="form-field">
              <label>运行星期（可多选）</label>
              <div class="checkbox-grid weekday-grid" role="group" aria-label="运行星期多选">
                <label v-for="day in weekdayOptions" :key="day.value" class="checkbox-item">
                  <input
                    type="checkbox"
                    :value="day.value"
                    :checked="form.weekdays.includes(day.value)"
                    :aria-label="day.label"
                    @change="toggleWeekday(day.value)"
                  />
                  <span class="checkbox-text">{{ day.label }}</span>
                </label>
              </div>
            </div>
          </template>

          <div class="form-field">
            <label>Cron 表达式（自动生成）</label>
            <input :value="generatedCron" class="input" readonly />
          </div>

          <label class="toggle-row">
            <input v-model="form.enabled" type="checkbox" />
            <span>启用</span>
          </label>
          <div class="inline-actions">
            <AppButton type="primary" :loading="saving" :disabled="!tasksAvailable" @click="save">
              {{ saving ? '保存中...' : '保存任务' }}
            </AppButton>
            <AppButton @click="reset">重置</AppButton>
          </div>
        </fieldset>
      </CardPanel>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import Pagination from '../components/Pagination.vue'
import EmptyState from '../components/EmptyState.vue'
import { confirmDelete } from '../utils/confirmAction.js'
import { camelizeKeys, dateTime, totalOf } from '../utils/apiData.js'
import { createScheduledTask, deleteScheduledTask, getScheduledTasks, runScheduledTask, updateScheduledTask } from '../api/scheduledTasks.js'
import { getLiteAccounts } from '../api/accounts.js'
import { listWorkflows } from '../api/workflow.js'
import {
  DEFAULT_SCHEDULED_TASK_TYPES,
  buildCronExpression,
  buildTaskConfig,
  hydrateFormFromTask,
  normalizeScheduledTaskPayload,
  normalizeScheduledTaskTypes,
  taskRequiresAccounts,
  taskTypeLabel
} from '../utils/scheduledTaskState.js'

const tasks = ref([])
const total = ref(0)
const current = ref(1)
const pageSize = ref(20)
const saving = ref(false)
const busyId = ref(null)
const error = ref('')
const success = ref('')
const tasksLoadError = ref('')
const tasksAvailable = ref(false)
const loading = ref(false)
const taskNameInputRef = ref(null)

const accounts = ref([])
const accountsLoading = ref(false)
const workflows = ref([])

const form = reactive({
  id: null,
  taskName: '',
  taskType: 'sync_goods',
  accountIds: [],
  dailyTime: '00:00',
  intervalMinutes: 10,
  workflowId: '',
  scheduleMode: 'daily',
  workflowTime: '00:00',
  weekdays: [],
  enabled: true
})

const taskTypeOptions = normalizeScheduledTaskTypes(DEFAULT_SCHEDULED_TASK_TYPES)

const weekdayOptions = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

const columns = [
  { key: 'taskName', title: '任务名称' },
  { key: 'taskType', title: '任务类型' },
  { key: 'cronExpression', title: 'Cron' },
  { key: 'enabled', title: '启用状态' },
  { key: 'lastRunTimeText', title: '上次运行' },
  { key: 'nextRunTimeText', title: '下次运行' },
  { key: 'op', title: '操作' }
]

const rows = computed(() => tasks.value.map(task => ({
  ...task,
  taskTypeLabel: taskTypeLabel(task.taskType),
  enabledText: task.enabled === 1 || task.enabled === true ? '已启用' : task.enabled === 0 || task.enabled === false ? '已禁用' : '状态未知',
  enabledBadge: task.enabled === 1 || task.enabled === true ? 'green' : task.enabled === 0 || task.enabled === false ? 'gray' : 'orange',
  lastRunTimeText: dateTime(task.lastRunTime),
  nextRunTimeText: dateTime(task.nextRunTime),
  raw: task
})))

const needsAccounts = computed(() => taskRequiresAccounts(form.taskType))
const isDailyTimeTask = computed(() => ['sync_goods', 'sync_orders', 'one_click_polish'].includes(form.taskType))
const isAutoRedeliveryTask = computed(() => form.taskType === 'auto_redelivery')
const isWorkflowTask = computed(() => form.taskType === 'workflow')

const generatedCron = computed(() => {
  const config = buildTaskConfig(form.taskType, form)
  return buildCronExpression(form.taskType, config)
})

// 间隔分钟输入：用文本输入框避免 type=number 在自动化工具下 selectionEnd 不可用
// 同时提供实时校验提示，低于 10 时显示警告并强制修正为 10
const intervalMinutesWarning = ref('')
const intervalInputRef = ref(null)

function onIntervalInput(event) {
  const raw = event?.target?.value
  const trimmed = String(raw ?? '').trim()
  if (trimmed === '') {
    form.intervalMinutes = 10
    intervalMinutesWarning.value = ''
    if (event?.target) event.target.value = String(form.intervalMinutes)
    return
  }
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    intervalMinutesWarning.value = '请输入有效的正整数'
    return
  }
  if (parsed < 10) {
    intervalMinutesWarning.value = '间隔不能小于 10 分钟，将自动修正为 10'
    form.intervalMinutes = 10
    // 强制更新输入框显示为修正后的值
    if (event?.target) event.target.value = String(form.intervalMinutes)
    return
  }
  intervalMinutesWarning.value = ''
  form.intervalMinutes = Math.floor(parsed)
}

// 当离开 auto_redelivery 任务类型时，清空警告
watch(() => form.taskType, (next) => {
  if (next !== 'auto_redelivery') {
    intervalMinutesWarning.value = ''
  }
})

function clearNotice() {
  error.value = ''
  success.value = ''
}

function reset() {
  form.id = null
  form.taskName = ''
  form.taskType = 'sync_goods'
  form.accountIds = []
  form.dailyTime = '00:00'
  form.intervalMinutes = 10
  form.workflowId = ''
  form.scheduleMode = 'daily'
  form.workflowTime = '00:00'
  form.weekdays = []
  form.enabled = true
}

function onTaskTypeChange() {
  // 切换任务类型时，清理无关字段，保留通用字段（taskName/enabled）
  // 重置所有任务类型特定字段，避免残留值导致表单显示异常
  if (!taskRequiresAccounts(form.taskType)) {
    form.accountIds = []
  }
  // 非 auto_redelivery 时重置间隔分钟为默认值
  if (form.taskType !== 'auto_redelivery') {
    form.intervalMinutes = 10
    intervalMinutesWarning.value = ''
  }
  // 非 daily 时间任务时重置 dailyTime
  if (!['sync_goods', 'sync_orders', 'one_click_polish'].includes(form.taskType)) {
    form.dailyTime = '00:00'
  }
  // 非 workflow 时重置工作流相关字段
  if (form.taskType !== 'workflow') {
    form.workflowId = ''
    form.scheduleMode = 'daily'
    form.workflowTime = '00:00'
    form.weekdays = []
  }
  // 进入 workflow 时重置 dailyTime（workflow 使用 workflowTime）
  if (form.taskType === 'workflow') {
    form.dailyTime = '00:00'
  }
  // 进入 auto_redelivery 时重置 dailyTime 和 workflow 字段
  if (form.taskType === 'auto_redelivery') {
    form.dailyTime = '00:00'
    form.workflowId = ''
    form.scheduleMode = 'daily'
    form.workflowTime = '00:00'
    form.weekdays = []
  }
}

function toggleAccount(id) {
  const index = form.accountIds.indexOf(id)
  if (index >= 0) {
    form.accountIds.splice(index, 1)
  } else {
    form.accountIds.push(id)
  }
}

function clearAccounts() {
  form.accountIds = []
}

function toggleWeekday(value) {
  const index = form.weekdays.indexOf(value)
  if (index >= 0) {
    form.weekdays.splice(index, 1)
  } else {
    form.weekdays.push(value)
  }
}

function normalizeInterval() {
  if (!Number.isFinite(form.intervalMinutes) || form.intervalMinutes < 10) {
    form.intervalMinutes = 10
  }
}

function accountLabel(account) {
  const remark = account.remark || ''
  const nickname = account.nickname || account.displayName || ''
  const label = remark || nickname || account.externalUid || `账号 ${account.id}`
  return `${label}（#${account.id}）`
}

function validateForm() {
  if (!form.taskName.trim()) return '请填写任务名称'
  if (needsAccounts.value && form.accountIds.length === 0) return '请至少选择一个账号'
  if (isWorkflowTask.value) {
    if (!form.workflowId) return '请选择工作流'
    if (form.scheduleMode === 'weekly' && form.weekdays.length === 0) return '每周模式下请至少选择一个运行日'
  }
  if (isAutoRedeliveryTask.value && (!Number.isFinite(form.intervalMinutes) || form.intervalMinutes < 10)) {
    return '执行间隔不能小于 10 分钟'
  }
  return ''
}

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || []
    accounts.value = camelizeKeys(list)
  } catch (err) {
    accounts.value = []
  } finally {
    accountsLoading.value = false
  }
}

async function loadWorkflows() {
  try {
    const res = await listWorkflows({ current: 1, size: 100 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || []
    workflows.value = camelizeKeys(list)
  } catch (err) {
    workflows.value = []
  }
}

async function load() {
  clearNotice()
  tasksLoadError.value = ''
  tasksAvailable.value = false
  tasks.value = []
  total.value = 0
  reset()
  loading.value = true
  try {
    const res = await getScheduledTasks({ current: current.value, size: pageSize.value })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || data?.rows || data?.items
    if (!Array.isArray(list)) throw new Error('定时任务响应格式异常')
    tasks.value = camelizeKeys(list)
    total.value = totalOf(data, tasks.value.length)
    tasksAvailable.value = true
    return true
  } catch (requestError) {
    tasksLoadError.value = requestError?.message || '加载定时任务失败'
    return false
  } finally {
    loading.value = false
  }
}

function edit(task) {
  const hydrated = hydrateFormFromTask(task)
  Object.assign(form, hydrated)
}

async function save() {
  if (saving.value) return
  if (!tasksAvailable.value) {
    error.value = '定时任务服务不可用，无法保存任务'
    return
  }
  clearNotice()

  const validationError = validateForm()
  if (validationError) {
    error.value = validationError
    return
  }

  saving.value = true
  try {
    const payload = normalizeScheduledTaskPayload(form)
    let savedMessage = ''
    if (form.id) {
      await updateScheduledTask(form.id, payload)
      savedMessage = '定时任务已更新'
    } else {
      await createScheduledTask(payload)
      savedMessage = '定时任务已创建'
    }
    reset()
    const reloaded = await load()
    if (reloaded) success.value = savedMessage
    else error.value = `${savedMessage}，但任务列表刷新失败，请重新加载确认最新状态。`
  } catch (requestError) {
    error.value = requestError.message || '保存定时任务失败'
  } finally {
    saving.value = false
  }
}

async function run(id) {
  if (busyId.value) return
  if (!tasksAvailable.value) {
    error.value = '定时任务服务不可用，无法运行任务'
    return
  }
  clearNotice()
  busyId.value = id
  try {
    const res = await runScheduledTask(id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.ok !== true) {
      throw new Error(data?.message || '任务运行响应未确认执行成功')
    }
    const runMessage = data.message || `任务 #${id} 已执行`
    const reloaded = await load()
    if (reloaded) success.value = runMessage
    else error.value = `${runMessage}，但任务列表刷新失败，请重新加载确认最新状态。`
  } catch (requestError) {
    error.value = requestError.message || '运行定时任务失败'
  } finally {
    busyId.value = null
  }
}

async function remove(id) {
  if (!tasksAvailable.value) {
    error.value = '定时任务服务不可用，无法删除任务'
    return
  }
  const confirmed = await confirmDelete('定时任务')
  if (!confirmed) return

  clearNotice()
  try {
    await deleteScheduledTask(id)
    const reloaded = await load()
    if (reloaded) success.value = `任务 #${id} 已删除`
    else error.value = `任务 #${id} 已删除，但任务列表刷新失败，请重新加载确认最新状态。`
  } catch (requestError) {
    error.value = requestError.message || '删除定时任务失败'
  }
}

function goPage(page) {
  current.value = page
  load()
}

function focusTaskName() {
  taskNameInputRef.value?.focus?.()
}

function onHeaderAction(event) {
  if (!tasksAvailable.value) {
    if (event.detail?.startsWith('scheduled-task-')) error.value = '定时任务服务不可用，请先重试加载'
    return
  }
  if (event.detail === 'scheduled-task-new') {
    reset()
    focusTaskName()
  }
  if (event.detail === 'scheduled-task-save') save()
  if (event.detail === 'scheduled-task-run-current' && form.id) run(form.id)
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  load()
  loadAccounts()
  loadWorkflows()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.layout-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 18px;
}

.form-field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.task-form-fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.task-form-fieldset:disabled {
  opacity: .65;
}

.toggle-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.strong {
  font-weight: 600;
}

.success {
  background: #ecfdf3;
  color: #067647;
  border-color: #abefc6;
}

.hint {
  color: #6b7280;
  font-size: 12px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
  padding: 8px;
  border: 1px solid #d9e2f0;
  border-radius: 8px;
  background: #fff;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  cursor: pointer;
  font-size: 13px;
}

.checkbox-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.weekday-grid {
  grid-template-columns: repeat(4, 1fr);
}

@media (max-width: 1080px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>
