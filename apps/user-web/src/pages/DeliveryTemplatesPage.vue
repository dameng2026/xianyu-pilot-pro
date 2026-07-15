<template>
  <div>
    <div class="page-head">
      <div>
        <h1>模板管理</h1>
        <p>管理可复用的发货内容模板，支持变量插入与分段发送</p>
      </div>
    </div>

    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <div v-if="loading" class="templates-loading" role="status">模板数据加载中...</div>
    <EmptyState v-else-if="loadError" variant="error" title="发货模板暂时无法加载" :description="loadError">
      <template #actions><AppButton @click="loadTemplates">重新加载</AppButton></template>
    </EmptyState>

    <div v-else class="templates-layout">
      <div class="templates-list">
        <div class="toolbar">
          <input v-model="searchKeyword" class="input large" placeholder="搜索模板名称…" @input="searchTemplates">
          <AppButton type="primary" @click="createNew">+ 新建模板</AppButton>
        </div>

        <CardPanel>
          <BaseTable :columns="cols" :rows="rows">
            <template #typeName="{row}">
              <Badge :type="row.typeBadge">{{ row.typeName }}</Badge>
            </template>
            <template #status="{row}">
              <Badge :type="row.status === 1 ? 'green' : row.status === 0 ? 'gray' : 'orange'">{{ row.status === 1 ? '启用' : row.status === 0 ? '禁用' : '状态未知' }}</Badge>
            </template>
            <template #randomEnabled="{row}">
              <span v-if="row.randomEnabled !== null" :class="['switch', { on: row.randomEnabled }]" />
              <span v-else class="subtle">未知</span>
            </template>
            <template #createdTime="{row}">{{ row.createdTime }}</template>
            <template #op="{row}">
              <button class="link" @click="edit(row.raw)">编辑</button>
              <button class="link" @click="copy(row.raw.id)">复制</button>
              <button class="link danger-text" @click="remove(row.raw.id)">删除</button>
            </template>
            <template #empty>
              <EmptyState icon="📄" title="还没有发货模板" description="创建一个模板快速生成发货内容，支持变量和分段发送。">
                <template #actions>
                  <AppButton type="primary" @click="createNew">创建模板</AppButton>
                </template>
              </EmptyState>
            </template>
          </BaseTable>
          <Pagination :total="total" :current="current" :page-size="pageSize" @page-change="goPage" />
        </CardPanel>
      </div>

      <div class="templates-form">
        <CardPanel :title="form.id ? '编辑模板' : '新建模板'">
          <div class="form-grid">
            <div class="form-row">
              <label>模板名称</label>
              <input ref="templateNameInputRef" v-model="form.name" placeholder="请输入模板名称">
            </div>
            <div class="form-row">
              <label>模板类型</label>
              <select v-model.number="form.type">
                <option v-for="t in templateTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>状态</label>
              <select v-model.number="form.status">
                <option :value="1">启用</option>
                <option :value="0">禁用</option>
              </select>
            </div>
            <div class="form-row">
              <label>加入随机模板列表</label>
              <div class="toggle-row">
                <ToggleSwitch :on="!!form.randomEnabled" @click="form.randomEnabled = !form.randomEnabled" />
                <span class="subtle">{{ form.randomEnabled ? '已加入' : '未加入' }}</span>
              </div>
            </div>
          </div>

          <div class="form-row" style="margin-top:16px">
            <label>模板内容</label>
            <textarea ref="templateTextareaRef" v-model="form.content" placeholder="输入发货内容，支持变量，如：{买家昵称}、{卡密}。使用 {分段} 拆分多条消息。" rows="6"></textarea>
          </div>

          <div class="var-section">
            <label class="var-section-title">快捷插入变量</label>
            <div v-if="variablesLoadError" class="variables-warning">{{ variablesLoadError }}</div>
            <div class="var-chips">
              <span v-for="v in variables" :key="v.key" class="var-chip" @click="insertVariable(v.key)">{{ v.key }}</span>
            </div>
            <p class="subtle" style="margin-top:8px">提示：内容中包含 <code>{分段}</code> 时，系统会将内容拆成多条消息依次发送。</p>
          </div>

          <div class="form-actions">
            <AppButton type="primary" :loading="saving" :disabled="!templatesAvailable" @click="save">{{ saving ? '保存中...' : '保存' }}</AppButton>
            <AppButton :disabled="saving" @click="resetForm">清空</AppButton>
            <AppButton v-if="form.id" type="danger" :disabled="saving" @click="remove(form.id)">删除</AppButton>
          </div>
        </CardPanel>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import { confirmDelete } from '../utils/confirmAction.js'
import {
  getDeliveryTemplates,
  createDeliveryTemplate,
  updateDeliveryTemplate,
  deleteDeliveryTemplate,
  copyDeliveryTemplate,
  getTemplateVariables
} from '../api/autoDelivery.js'
import { recordsOfOrThrow, totalOf, dateTime } from '../utils/apiData.js'

const templateNameInputRef = ref(null)
const templateTextareaRef = ref(null)

const templateTypes = [
  { value: 1, label: '付款后发货模板' },
  { value: 2, label: '收货后赠送模板' },
  { value: 3, label: '好评后赠送模板' },
  { value: 4, label: '发货声明模板' },
  { value: 5, label: '卡密发货模板' },
  { value: 6, label: '普通文本模板' }
]

const variables = ref([])
const rawTemplates = ref([])
const total = ref(0)
const current = ref(1)
const pageSize = ref(20)
const error = ref('')
const success = ref('')
const loading = ref(true)
const loadError = ref('')
const variablesLoadError = ref('')
const templatesAvailable = ref(false)
const saving = ref(false)
const searchKeyword = ref('')

const form = reactive({
  id: null,
  name: '',
  type: 6,
  status: 1,
  content: '',
  randomEnabled: false
})

const cols = [
  { key: 'name', title: '模板名称' },
  { key: 'typeName', title: '类型' },
  { key: 'status', title: '状态' },
  { key: 'randomEnabled', title: '随机模板' },
  { key: 'createdTime', title: '创建时间' },
  { key: 'op', title: '操作' }
]

const typeNames = Object.fromEntries(templateTypes.map(t => [t.value, t.label]))
const typeBadges = { 1: 'blue', 2: 'green', 3: 'orange', 4: 'purple', 5: 'red', 6: 'gray' }

const rows = computed(() => {
  const mapped = rawTemplates.value.map(r => ({
    ...r,
    typeName: typeNames[r.type] || '未知',
    typeBadge: typeBadges[r.type] || 'gray',
    randomEnabled: r.randomEnabled == null && r.isRandom == null
      ? null
      : Number(r.randomEnabled ?? r.isRandom) === 1,
    createdTime: dateTime(r.createdTime),
    raw: r
  }))
  return mapped
})

function createNew() {
  if (!templatesAvailable.value) return
  resetForm()
  document.querySelector('input')?.focus?.()
  templateNameInputRef.value?.focus?.()
}

function resetForm() {
  Object.assign(form, { id: null, name: '', type: 6, status: 1, content: '', randomEnabled: false })
}

function edit(r) {
  Object.assign(form, {
    id: r.id,
    name: r.name,
    type: r.type ?? 6,
    status: r.status ?? 1,
    content: r.content || '',
    randomEnabled: Number(r.randomEnabled ?? r.isRandom ?? 0) === 1
  })
}

function insertVariable(key) {
  const ta = templateTextareaRef.value
  if (ta) {
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const before = form.content.substring(0, start)
    const after = form.content.substring(end)
    form.content = before + key + after
    requestAnimationFrame(() => {
      ta.selectionStart = ta.selectionEnd = start + key.length
      ta.focus()
    })
  } else {
    form.content += key
  }
}

async function loadTemplates() {
  error.value = ''
  loadError.value = ''
  loading.value = true
  templatesAvailable.value = false
  try {
    const params = { current: current.value, size: pageSize.value }
    if (searchKeyword.value.trim()) params.name = searchKeyword.value.trim()
    const res = await getDeliveryTemplates(params)
    rawTemplates.value = recordsOfOrThrow(res?.data, '发货模板列表响应格式异常')
    total.value = totalOf(res.data, rawTemplates.value.length)
    templatesAvailable.value = true
  } catch (e) {
    rawTemplates.value = []
    total.value = 0
    loadError.value = `${e.message || '后端服务不可用'}；当前不会展示或写入浏览器中的替代模板，请重试。`
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  current.value = p
  loadTemplates()
}

function searchTemplates() {
  current.value = 1
  loadTemplates()
}

async function loadVariables() {
  variablesLoadError.value = ''
  try {
    const res = await getTemplateVariables()
    if (!Array.isArray(res?.data)) throw new Error('模板变量响应格式异常')
    variables.value = res.data
    return
  } catch (e) {
    variablesLoadError.value = `${e.message || '变量列表加载失败'}，快捷变量已停用；仍可手动输入模板内容。`
  }
  variables.value = []
}

async function save() {
  if (!templatesAvailable.value) return
  if (saving.value) return
  error.value = ''
  success.value = ''

  if (!form.name.trim()) { error.value = '请输入模板名称'; return }
  if (!form.content.trim()) { error.value = '请输入模板内容'; return }

  saving.value = true
  try {
    const data = {
      name: form.name.trim(),
      type: form.type,
      status: form.status,
      content: form.content.trim(),
      randomEnabled: form.randomEnabled
    }

    if (form.id) {
      await updateDeliveryTemplate(form.id, data)
      success.value = '模板已更新'
    } else {
      await createDeliveryTemplate(data)
      success.value = '模板已创建'
    }
    resetForm()
    await loadTemplates()
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function remove(id) {
  if (!templatesAvailable.value) return
  if (!await confirmDelete('发货模板')) return
  try {
    await deleteDeliveryTemplate(id)
    success.value = '模板已删除'
    if (form.id === id) resetForm()
    await loadTemplates()
  } catch (e) {
    error.value = e.message
  }
}

async function copy(id) {
  if (!templatesAvailable.value) return
  try {
    await copyDeliveryTemplate(id)
    success.value = '模板已复制'
    await loadTemplates()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(async () => {
  window.addEventListener('xya-header-action', onHeaderAction)
  await Promise.all([loadTemplates(), loadVariables()])
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})

function onHeaderAction(event) {
  if (event.detail === 'template-new' && templatesAvailable.value) createNew()
  if (event.detail === 'template-refresh') loadTemplates()
}
</script>

<style scoped>
.templates-loading {
  padding: 48px;
  text-align: center;
  color: #667491;
}

.variables-warning {
  margin: 8px 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff8e8;
  color: #9a6700;
  font-size: 12px;
  line-height: 1.5;
}

.page-head {
  height: 62px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-right: 260px;
}
.page-head h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: .3px;
}
.page-head p {
  margin: 10px 0 0;
  color: #667491;
  font-size: 15px;
}
.templates-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 18px;
}
.templates-list {
  min-width: 0;
}
.templates-form {
  min-width: 0;
}
code {
  background: #f1f4f8;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #0d6bff;
}
.toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
}
.var-section {
  margin-top: 14px;
  padding: 14px;
  background: #f8fbff;
  border: 1px solid #e8eef8;
  border-radius: 12px;
}
.var-section-title {
  display: block;
  font-weight: 700;
  color: #34425d;
  margin-bottom: 10px;
  font-size: 14px;
}
.var-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.var-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 10px;
  background: #fff;
  border: 1px solid #dbe8ff;
  border-radius: 7px;
  font-size: 12px;
  color: #2d6ae3;
  cursor: pointer;
  font-weight: 650;
  transition: all .15s;
  white-space: nowrap;
}
.var-chip:hover {
  background: #e0e8ff;
  border-color: #b8ceff;
  transform: translateY(-1px);
}
.form-actions {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-row label {
  font-size: 13px;
  font-weight: 700;
  color: #34425d;
}
.form-row input,
.form-row select {
  width: 100%;
  height: 38px;
  border: 1px solid #e7edf7;
  border-radius: 7px;
  padding: 0 12px;
  color: #44536f;
  background: #fff;
  outline: none;
  box-sizing: border-box;
}
.form-row input:focus,
.form-row select:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13,107,255,.1);
}
.form-row textarea {
  width: 100%;
  min-height: 110px;
  padding: 12px;
  border: 1px solid #e7edf7;
  border-radius: 7px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
  outline: none;
}
.form-row textarea:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13,107,255,.1);
}
.subtle {
  color: #758198;
  font-size: 13px;
}
@media (max-width:1200px) {
  .templates-layout {
    grid-template-columns: 1fr;
  }
  .page-head {
    padding-right: 0;
  }
}
</style>
