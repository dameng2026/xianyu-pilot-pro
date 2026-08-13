<template>
  <div class="mf-page">
    <section class="mf-hero">
      <div class="mf-hero-copy">
        <h2>消息过滤</h2>
        <p>
          按账号和关键词屏蔽骚扰、广告或系统提示类消息：命中「跳过自动回复」的消息不会触发 AI/规则回复，
          命中「跳过通知」的消息不会出现在在线消息的新消息提醒中，消息本身仍会正常入库便于人工查看。
        </p>
      </div>
      <button type="button" class="mf-primary-btn" :disabled="saving || !accounts.length" @click="openCreate">
        + 新增过滤规则
      </button>
    </section>

    <section class="mf-toolbar card">
      <label class="mf-field">
        <span>账号</span>
        <select v-model="query.accountId" @change="loadRules">
          <option value="">全部账号</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>
      <label class="mf-field">
        <span>过滤类型</span>
        <select v-model="query.filterType" @change="loadRules">
          <option value="">全部类型</option>
          <option value="skip_reply">跳过自动回复</option>
          <option value="skip_notify">跳过消息通知</option>
        </select>
      </label>
      <label class="mf-field grow">
        <span>关键词</span>
        <input
          v-model="query.keyword"
          type="text"
          placeholder="搜索关键词，回车确认"
          @keyup.enter="loadRules"
        />
      </label>
      <button type="button" class="mf-ghost-btn" :disabled="loading" @click="loadRules(true)">查询</button>
      <button
        v-if="selectedIds.length"
        type="button"
        class="mf-danger-btn"
        :disabled="deleting"
        @click="batchDelete"
      >
        删除所选（{{ selectedIds.length }}）
      </button>
    </section>

    <section class="mf-list card">
      <div v-if="loading" class="mf-state">规则加载中…</div>
      <div v-else-if="loadError" class="mf-state error">
        {{ loadError }}
        <button type="button" class="mf-link-btn" @click="loadRules(true)">重试</button>
      </div>
      <div v-else-if="!rules.length" class="mf-state empty">
        暂无过滤规则，点击右上角「新增过滤规则」开始配置。
      </div>
      <div v-else class="mf-table-wrap">
        <table class="mf-table">
          <thead>
            <tr>
              <th class="mf-check-col">
                <input
                  type="checkbox"
                  :checked="selectedIds.length === rules.length && rules.length > 0"
                  @change="toggleSelectAll"
                />
              </th>
              <th>账号</th>
              <th>关键词</th>
              <th>过滤类型</th>
              <th>状态</th>
              <th>创建时间</th>
              <th class="mf-op-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in rules" :key="rule.id">
              <td>
                <input v-model="selectedIds" type="checkbox" :value="rule.id" />
              </td>
              <td>{{ accountLabel(rule.accountId) }}</td>
              <td class="mf-keyword-cell">{{ rule.keyword }}</td>
              <td>
                <span class="mf-type-badge" :class="rule.filterType">
                  {{ rule.filterType === 'skip_reply' ? '跳过自动回复' : '跳过消息通知' }}
                </span>
              </td>
              <td>
                <button
                  type="button"
                  class="mf-toggle"
                  :class="{ on: rule.enabled }"
                  :disabled="saving"
                  @click="toggleRule(rule)"
                >
                  {{ rule.enabled ? '已启用' : '已禁用' }}
                </button>
              </td>
              <td>{{ formatTime(rule.createdAt) }}</td>
              <td>
                <div class="mf-ops">
                  <button type="button" class="mf-link-btn" @click="openEdit(rule)">编辑</button>
                  <button type="button" class="mf-link-btn danger" @click="removeRule(rule)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="showForm" class="mf-modal-mask" @click.self="closeForm">
      <div class="mf-modal">
        <div class="mf-modal-head">
          <h3>{{ editing ? '编辑过滤规则' : '新增过滤规则' }}</h3>
          <button type="button" class="mf-icon-btn" aria-label="关闭" @click="closeForm">×</button>
        </div>
        <div class="mf-modal-body">
          <label class="mf-field">
            <span>适用账号 <em>*</em></span>
            <select v-model="form.accountId" :disabled="!!editing">
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
              </option>
            </select>
          </label>
          <label class="mf-field">
            <span>关键词 <em>*</em></span>
            <input v-model="form.keyword" type="text" placeholder="例如：广告、代发、加微信" maxlength="200" />
          </label>
          <div class="mf-field">
            <span>过滤类型 <em>*</em></span>
            <div class="mf-check-row">
              <label class="mf-check">
                <input v-model="form.filterTypes" type="checkbox" value="skip_reply" />
                <span>跳过自动回复</span>
              </label>
              <label class="mf-check">
                <input v-model="form.filterTypes" type="checkbox" value="skip_notify" />
                <span>跳过消息通知</span>
              </label>
            </div>
          </div>
          <p class="mf-tip">
            「跳过自动回复」：买家消息命中关键词时，AI 客服与关键词规则都不会回复；「跳过消息通知」：命中消息不产生新消息提醒。
            消息仍会保存到会话记录，可随时人工处理。
          </p>
          <p v-if="formError" class="mf-form-error">{{ formError }}</p>
        </div>
        <div class="mf-modal-foot">
          <button type="button" class="mf-ghost-btn" @click="closeForm">取消</button>
          <button type="button" class="mf-primary-btn" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getAccounts } from '../api/accounts.js'
import {
  batchDeleteMessageFilters,
  deleteMessageFilter,
  listMessageFilters,
  saveMessageFilter,
  toggleMessageFilter,
} from '../api/messageFilter.js'

const accounts = ref([])
const rules = ref([])
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const deleting = ref(false)
const formError = ref('')
const selectedIds = ref([])
const showForm = ref(false)
const editing = ref(null)

const query = reactive({ accountId: '', filterType: '', keyword: '' })
const form = reactive({ accountId: '', keyword: '', filterTypes: [] })

const accountMap = computed(() => {
  const map = {}
  for (const acc of accounts.value) map[acc.id] = acc
  return map
})

function accountLabel(accountId) {
  const acc = accountMap.value[accountId]
  return acc ? (acc.nickname || acc.accountName || `账号 ${accountId}`) : `账号 ${accountId}`
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(String(value).includes('T') ? value : String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return value
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadAccounts() {
  try {
    const res = await getAccounts({ current: 1, size: 100 })
    const list = Array.isArray(res?.data) ? res.data : (res?.data?.records || [])
    accounts.value = list
    if (list.length && !form.accountId) form.accountId = list[0].id
  } catch (e) {
    loadError.value = e?.message || '账号列表加载失败'
  }
}

async function loadRules() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {}
    if (query.accountId) params.accountId = query.accountId
    if (query.filterType) params.filterType = query.filterType
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const res = await listMessageFilters(params)
    rules.value = Array.isArray(res?.data?.records) ? res.data.records : []
    selectedIds.value = selectedIds.value.filter(id => rules.value.some(r => r.id === id))
  } catch (e) {
    loadError.value = e?.message || '规则加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  formError.value = ''
  form.accountId = accounts.value[0]?.id || ''
  form.keyword = ''
  form.filterTypes = ['skip_reply', 'skip_notify']
  showForm.value = true
}

function openEdit(rule) {
  editing.value = rule
  formError.value = ''
  form.accountId = rule.accountId
  form.keyword = rule.keyword
  form.filterTypes = [rule.filterType]
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editing.value = null
  formError.value = ''
}

async function save() {
  formError.value = ''
  if (!form.accountId) {
    formError.value = '请选择适用账号'
    return
  }
  if (!form.keyword.trim()) {
    formError.value = '请输入关键词'
    return
  }
  if (!form.filterTypes.length) {
    formError.value = '请至少选择一种过滤类型'
    return
  }
  saving.value = true
  try {
    const payload = {
      accountId: form.accountId,
      keyword: form.keyword.trim(),
      filterTypes: form.filterTypes,
    }
    if (editing.value) payload.id = editing.value.id
    await saveMessageFilter(payload)
    closeForm()
    await loadRules(true)
  } catch (e) {
    formError.value = e?.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

async function toggleRule(rule) {
  saving.value = true
  try {
    await toggleMessageFilter(rule.id, !rule.enabled)
    rule.enabled = !rule.enabled
  } catch (e) {
    loadError.value = e?.message || '切换状态失败'
  } finally {
    saving.value = false
  }
}

async function removeRule(rule) {
  if (!window.confirm(`确定删除关键词「${rule.keyword}」的过滤规则吗？`)) return
  deleting.value = true
  try {
    await deleteMessageFilter(rule.id)
    await loadRules(true)
  } catch (e) {
    loadError.value = e?.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

async function batchDelete() {
  if (!selectedIds.value.length) return
  if (!window.confirm(`确定删除选中的 ${selectedIds.value.length} 条过滤规则吗？`)) return
  deleting.value = true
  try {
    await batchDeleteMessageFilters(selectedIds.value)
    await loadRules(true)
  } catch (e) {
    loadError.value = e?.message || '批量删除失败'
  } finally {
    deleting.value = false
  }
}

function toggleSelectAll(e) {
  selectedIds.value = e.target.checked ? rules.value.map(r => r.id) : []
}

onMounted(async () => {
  await loadAccounts()
  await loadRules()
})
</script>

<style scoped>
.mf-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.mf-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: linear-gradient(135deg, #1f6feb 0%, #7b5cff 100%);
  border-radius: 14px;
  color: #fff;
}

.mf-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.mf-hero-copy p {
  margin: 0;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.92;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.mf-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 16px;
  flex-wrap: wrap;
}

.mf-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 150px;
}

.mf-field.grow {
  flex: 1;
  min-width: 200px;
}

.mf-field > span {
  font-size: 12px;
  color: #6b7280;
}

.mf-field em {
  color: #ef4444;
  font-style: normal;
}

.mf-field input,
.mf-field select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #111827;
  outline: none;
}

.mf-field input:focus,
.mf-field select:focus {
  border-color: #1f6feb;
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.12);
}

.mf-primary-btn,
.mf-ghost-btn,
.mf-danger-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: opacity 0.15s ease;
}

.mf-primary-btn {
  background: #1f6feb;
  color: #fff;
}

.mf-primary-btn:hover {
  background: #1858c0;
}

.mf-ghost-btn {
  background: #fff;
  border-color: #d1d5db;
  color: #374151;
}

.mf-ghost-btn:hover {
  border-color: #1f6feb;
  color: #1f6feb;
}

.mf-danger-btn {
  background: #ef4444;
  color: #fff;
}

.mf-primary-btn:disabled,
.mf-ghost-btn:disabled,
.mf-danger-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mf-list {
  min-height: 180px;
}

.mf-state {
  padding: 48px 20px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.mf-state.error {
  color: #dc2626;
}

.mf-state.empty {
  color: #9ca3af;
}

.mf-link-btn {
  border: none;
  background: none;
  color: #1f6feb;
  font-size: 13px;
  cursor: pointer;
  padding: 2px 4px;
}

.mf-link-btn.danger {
  color: #dc2626;
}

.mf-table-wrap {
  overflow-x: auto;
}

.mf-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.mf-table th,
.mf-table td {
  padding: 11px 12px;
  border-bottom: 1px solid #f0f0f0;
  text-align: left;
  white-space: nowrap;
}

.mf-table th {
  background: #fafafa;
  color: #6b7280;
  font-weight: 600;
}

.mf-table tbody tr:hover {
  background: #f8faff;
}

.mf-check-col {
  width: 40px;
}

.mf-keyword-cell {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mf-type-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.mf-type-badge.skip_reply {
  background: #eef2ff;
  color: #4338ca;
}

.mf-type-badge.skip_notify {
  background: #ecfdf5;
  color: #047857;
}

.mf-toggle {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  cursor: pointer;
}

.mf-toggle.on {
  border-color: #10b981;
  background: #ecfdf5;
  color: #047857;
}

.mf-ops {
  display: flex;
  gap: 8px;
}

.mf-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.mf-modal {
  width: 480px;
  max-width: 100%;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
}

.mf-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.mf-modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.mf-icon-btn {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
}

.mf-modal-body {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mf-check-row {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.mf-check {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  cursor: pointer;
}

.mf-tip {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.7;
  background: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
}

.mf-form-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}

.mf-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
}
</style>
