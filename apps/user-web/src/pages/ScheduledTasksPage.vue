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
          <input id="scheduled-task-name" ref="taskNameInputRef" v-model="form.taskName" class="input" />
        </div>
        <div class="form-field">
          <label for="scheduled-task-account">账号 ID</label>
          <input id="scheduled-task-account" v-model="form.accountId" class="input" placeholder="可选账号 ID" />
        </div>
        <div class="form-field">
          <label for="scheduled-task-type">任务类型</label>
          <select id="scheduled-task-type" v-model="form.taskType" class="input">
            <option v-for="option in taskTypeOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label for="scheduled-task-cron">Cron 表达式</label>
          <input id="scheduled-task-cron" v-model="form.cronExpression" class="input" placeholder="0 0/30 * * * ?" />
          <span v-if="cronError" class="input-error">{{ cronError }}</span>
        </div>
        <div class="form-field">
          <label for="scheduled-task-config">配置 JSON</label>
          <textarea id="scheduled-task-config" v-model="form.configJson" class="textarea" rows="8"></textarea>
          <span v-if="jsonError" class="input-error">{{ jsonError }}</span>
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import Pagination from '../components/Pagination.vue'
import EmptyState from '../components/EmptyState.vue'
import { confirmDelete } from '../utils/confirmAction.js'
import { camelizeKeys, dateTime, totalOf } from '../utils/apiData.js'
import { createScheduledTask, deleteScheduledTask, getScheduledTasks, runScheduledTask, updateScheduledTask } from '../api/scheduledTasks.js'
import {
  DEFAULT_SCHEDULED_TASK_TYPES,
  normalizeScheduledTaskPayload,
  normalizeScheduledTaskTypes,
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
const cronError = ref('')
const jsonError = ref('')
const taskNameInputRef = ref(null)

const form = reactive({
  id: null,
  taskName: '',
  accountId: '',
  taskType: 'sync_goods',
  cronExpression: '0 0/30 * * * ?',
  configJson: '{}',
  enabled: true
})

const taskTypeOptions = normalizeScheduledTaskTypes(DEFAULT_SCHEDULED_TASK_TYPES)

const columns = [
  { key: 'taskName', title: '任务名称' },
  { key: 'accountId', title: '账号 ID' },
  { key: 'taskType', title: '任务类型' },
  { key: 'cronExpression', title: 'Cron' },
  { key: 'enabled', title: '启用状态' },
  { key: 'lastRunTimeText', title: '上次运行' },
  { key: 'nextRunTimeText', title: '下次运行' },
  { key: 'op', title: '操作' }
]

const rows = computed(() => tasks.value.map(task => ({
  ...task,
  accountId: task.accountId ?? '-',
  taskTypeLabel: taskTypeLabel(task.taskType),
  enabledText: task.enabled === 1 || task.enabled === true ? '已启用' : task.enabled === 0 || task.enabled === false ? '已禁用' : '状态未知',
  enabledBadge: task.enabled === 1 || task.enabled === true ? 'green' : task.enabled === 0 || task.enabled === false ? 'gray' : 'orange',
  lastRunTimeText: dateTime(task.lastRunTime),
  nextRunTimeText: dateTime(task.nextRunTime),
  raw: task
})))

function clearNotice() {
  error.value = ''
  success.value = ''
}

function reset() {
  form.id = null
  form.taskName = ''
  form.accountId = ''
  form.taskType = 'sync_goods'
  form.cronExpression = '0 0/30 * * * ?'
  form.configJson = '{}'
  form.enabled = true
  cronError.value = ''
  jsonError.value = ''
}

function validateCron(cron) {
  if (!cron) return 'Cron 表达式必填'
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5 || parts.length > 7) return 'Cron 应有 5 到 7 段'
  if (!/^[\d*/,\-?\s]+$/.test(cron)) return 'Cron 包含不支持的字符'
  return ''
}

function validateJson(json) {
  if (!json) return ''
  try {
    JSON.parse(json)
    return ''
  } catch (jsonValidationError) {
    return `无效 JSON：${jsonValidationError.message}`
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
  form.id = task.id
  form.taskName = task.taskName || ''
  form.accountId = task.accountId == null ? '' : String(task.accountId)
  form.taskType = task.taskType || 'sync_goods'
  form.cronExpression = task.cronExpression || '0 0/30 * * * ?'
  form.configJson = typeof task.configJson === 'string' ? task.configJson : JSON.stringify(task.configJson || {}, null, 2)
  form.enabled = task.enabled === 1 || task.enabled === true
  cronError.value = ''
  jsonError.value = ''
}

async function save() {
  if (saving.value) return
  if (!tasksAvailable.value) {
    error.value = '定时任务服务不可用，无法保存任务'
    return
  }
  clearNotice()

  cronError.value = validateCron(form.cronExpression)
  jsonError.value = validateJson(form.configJson)
  if (cronError.value || jsonError.value) return

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

.textarea {
  width: 100%;
  min-height: 160px;
  padding: 10px 12px;
  border: 1px solid #d9e2f0;
  border-radius: 10px;
  resize: vertical;
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

@media (max-width: 1080px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>
