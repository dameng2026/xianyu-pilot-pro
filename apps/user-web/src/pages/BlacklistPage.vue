<template>
  <div class="bl-page">
    <section class="bl-hero">
      <div class="bl-hero-copy">
        <h2>买家黑名单</h2>
        <p>
          将反复退款、恶意骚扰或不想交易的买家加入黑名单后，系统会在自动发货前拦截，
          不发送卡密/内容，也不调用闲鱼确认发货接口，并在发货记录中写明拦截原因。
        </p>
        <div class="bl-guide">
          <div class="bl-guide-step">
            <span class="bl-guide-num">1</span>
            <span class="bl-guide-text">加入黑名单</span>
          </div>
          <span class="bl-guide-arrow">→</span>
          <div class="bl-guide-step">
            <span class="bl-guide-num">2</span>
            <span class="bl-guide-text">自动发货前拦截</span>
          </div>
          <span class="bl-guide-arrow">→</span>
          <div class="bl-guide-step">
            <span class="bl-guide-num">3</span>
            <span class="bl-guide-text">记录拦截原因</span>
          </div>
        </div>
      </div>
      <button type="button" class="bl-primary-btn" :disabled="!accounts.length" @click="openCreate">
        + 添加黑名单
      </button>
    </section>

    <section class="bl-toolbar card">
      <label class="bl-field">
        <span>账号</span>
        <select v-model="query.accountId" @change="loadList">
          <option value="">全部账号</option>
          <option :value="0">全部账号（全租户生效）</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>
      <label class="bl-field grow">
        <span>搜索</span>
        <input v-model="query.keyword" type="text" placeholder="按买家ID / 昵称搜索，回车确认" @keyup.enter="loadList" />
      </label>
      <button type="button" class="bl-ghost-btn" :disabled="loading" @click="loadList(true)">查询</button>
    </section>

    <section class="bl-list card">
      <div v-if="loading" class="bl-state">黑名单加载中…</div>
      <div v-else-if="loadError" class="bl-state error">
        {{ loadError }}
        <button type="button" class="bl-link-btn" @click="loadList(true)">重试</button>
      </div>
      <div v-else-if="!items.length" class="bl-state empty">
        <div class="bl-empty-icon">🛡️</div>
        <strong class="bl-empty-title">暂无黑名单记录</strong>
        <p class="bl-empty-desc">
          将反复退款、恶意骚扰的买家加入黑名单后，系统会在自动发货前拦截，不发送卡密/内容。
        </p>
        <button type="button" class="bl-primary-btn" :disabled="!accounts.length" @click="openCreate">
          + 添加黑名单
        </button>
      </div>
      <div v-else class="bl-table-wrap">
        <table class="bl-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>买家ID</th>
              <th>昵称</th>
              <th>商品范围</th>
              <th>原因</th>
              <th>状态</th>
              <th>添加时间</th>
              <th class="bl-op-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ accountLabel(item.accountId) }}</td>
              <td>{{ item.buyerUserId }}</td>
              <td>{{ item.buyerNickname || '—' }}</td>
              <td>
                <span v-if="item.goodsId" class="bl-goods-badge">{{ goodsLabel(item.goodsId) }}</span>
                <span v-else class="bl-goods-badge all">全部商品</span>
              </td>
              <td class="bl-reason-cell" :title="item.reason">{{ item.reason || '—' }}</td>
              <td>
                <button
                  type="button"
                  class="bl-toggle"
                  :class="{ on: item.enabled }"
                  :disabled="saving"
                  @click="toggleItem(item)"
                >
                  {{ item.enabled ? '拦截中' : '已停用' }}
                </button>
              </td>
              <td>{{ formatTime(item.createdAt) }}</td>
              <td>
                <div class="bl-ops">
                  <button type="button" class="bl-link-btn" @click="openEdit(item)">编辑</button>
                  <button type="button" class="bl-link-btn danger" @click="removeItem(item)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="showForm" class="bl-modal-mask" @click.self="closeForm">
      <div class="bl-modal">
        <div class="bl-modal-head">
          <h3>{{ editing ? '编辑黑名单' : '添加黑名单' }}</h3>
          <button type="button" class="bl-icon-btn" aria-label="关闭" @click="closeForm">×</button>
        </div>
        <div class="bl-modal-body">
          <label class="bl-field">
            <span>适用账号 <em>*</em></span>
            <select v-model="form.accountId" :disabled="!!editing" @change="loadProducts">
              <option :value="0">全部账号（全租户生效）</option>
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
              </option>
            </select>
          </label>
          <label class="bl-field">
            <span>买家ID <em>*</em></span>
            <input v-model="form.buyerUserId" type="text" placeholder="例如：2218205491269（可带 @goofish 后缀）" />
          </label>
          <label class="bl-field">
            <span>买家昵称（可选）</span>
            <input v-model="form.buyerNickname" type="text" placeholder="便于识别" />
          </label>
          <label class="bl-field">
            <span>商品范围（可选）</span>
            <select v-model="form.goodsId">
              <option value="">全部商品</option>
              <option v-for="p in products" :key="p.goodsId" :value="p.goodsId">
                {{ p.title || p.goodsId }}（{{ p.goodsId }}）
              </option>
            </select>
          </label>
          <label class="bl-field">
            <span>拉黑原因</span>
            <textarea v-model="form.reason" rows="2" placeholder="例如：反复退款买家，禁止自动发货" />
          </label>
          <p v-if="formError" class="bl-error">{{ formError }}</p>
        </div>
        <div class="bl-modal-foot">
          <button type="button" class="bl-ghost-btn" @click="closeForm">取消</button>
          <button type="button" class="bl-primary-btn" :disabled="saving" @click="save">
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
import { getAutoReplyScopeProducts } from '../api/autoReplyScope.js'
import {
  deletePersonalBlacklist,
  listPersonalBlacklist,
  savePersonalBlacklist,
  togglePersonalBlacklist,
} from '../api/blacklist.js'

const accounts = ref([])
const products = ref([])
const items = ref([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const formError = ref('')
const showForm = ref(false)
const editing = ref(null)

const query = reactive({ accountId: '', keyword: '' })
const form = reactive({
  accountId: '',
  buyerUserId: '',
  buyerNickname: '',
  goodsId: '',
  reason: '',
  enabled: true,
})

const accountMap = computed(() => {
  const map = {}
  for (const acc of accounts.value) map[acc.id] = acc
  return map
})
const productMap = computed(() => {
  const map = {}
  for (const p of products.value) map[p.goodsId] = p
  return map
})

function accountLabel(accountId) {
  if (Number(accountId) === 0) return '全部账号'
  const acc = accountMap.value[accountId]
  return acc ? (acc.nickname || acc.accountName || `账号 ${accountId}`) : `账号 ${accountId}`
}

function goodsLabel(goodsId) {
  const p = productMap.value[goodsId]
  return p ? (p.title || goodsId) : goodsId
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

async function loadProducts() {
  if (!form.accountId) {
    products.value = []
    return
  }
  try {
    const res = await getAutoReplyScopeProducts(form.accountId, { force: true })
    products.value = Array.isArray(res?.data?.items) ? res.data.items : []
  } catch {
    products.value = []
  }
}

async function loadList() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {}
    if (query.accountId !== '' && query.accountId !== null) params.accountId = query.accountId
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const res = await listPersonalBlacklist(params)
    items.value = Array.isArray(res?.data?.records) ? res.data.records : []
  } catch (e) {
    loadError.value = e?.message || '黑名单加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  formError.value = ''
  Object.assign(form, {
    accountId: '0',
    buyerUserId: '',
    buyerNickname: '',
    goodsId: '',
    reason: '',
    enabled: true,
  })
  loadProducts()
  showForm.value = true
}

function openEdit(item) {
  editing.value = item
  formError.value = ''
  Object.assign(form, {
    accountId: item.accountId,
    buyerUserId: item.buyerUserId,
    buyerNickname: item.buyerNickname || '',
    goodsId: item.goodsId || '',
    reason: item.reason || '',
    enabled: item.enabled,
  })
  loadProducts()
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
  if (!form.buyerUserId.trim()) {
    formError.value = '请输入买家ID'
    return
  }
  saving.value = true
  try {
    const payload = {
      accountId: form.accountId,
      buyerUserId: form.buyerUserId.trim(),
      buyerNickname: form.buyerNickname,
      goodsId: form.goodsId,
      reason: form.reason,
      enabled: form.enabled,
    }
    if (editing.value) payload.id = editing.value.id
    await savePersonalBlacklist(payload)
    closeForm()
    await loadList(true)
  } catch (e) {
    formError.value = e?.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

async function toggleItem(item) {
  saving.value = true
  try {
    await togglePersonalBlacklist(item.id, !item.enabled)
    item.enabled = !item.enabled
  } catch (e) {
    loadError.value = e?.message || '切换状态失败'
  } finally {
    saving.value = false
  }
}

async function removeItem(item) {
  if (!window.confirm(`确定将买家 ${item.buyerUserId} 移出黑名单吗？`)) return
  try {
    await deletePersonalBlacklist(item.id)
    await loadList(true)
  } catch (e) {
    loadError.value = e?.message || '删除失败'
  }
}

onMounted(async () => {
  await loadAccounts()
  await loadList()
})
</script>

<style scoped>
.bl-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.bl-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: linear-gradient(135deg, #dc2626 0%, #7c3aed 100%);
  border-radius: 14px;
  color: #fff;
}

.bl-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.bl-hero-copy p {
  margin: 0;
  max-width: 780px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.bl-guide {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.bl-guide-step {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 999px;
  padding: 5px 12px 5px 6px;
}

.bl-guide-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  color: #dc2626;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.bl-guide-text {
  font-size: 12px;
  line-height: 1.4;
  opacity: 0.98;
}

.bl-guide-arrow {
  font-size: 13px;
  opacity: 0.7;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.bl-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 16px;
  flex-wrap: wrap;
}

.bl-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 150px;
}

.bl-field.grow {
  flex: 1;
  min-width: 200px;
}

.bl-field > span {
  font-size: 12px;
  color: #6b7280;
}

.bl-field em {
  color: #ef4444;
  font-style: normal;
}

.bl-field input,
.bl-field select,
.bl-field textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  color: #111827;
  background: #fff;
  outline: none;
  box-sizing: border-box;
}

.bl-field textarea {
  resize: vertical;
}

.bl-field input:focus,
.bl-field select:focus,
.bl-field textarea:focus {
  border-color: #1f6feb;
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.12);
}

.bl-primary-btn,
.bl-ghost-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
}

.bl-primary-btn {
  background: #dc2626;
  color: #fff;
}

.bl-primary-btn:hover {
  background: #b91c1c;
}

.bl-ghost-btn {
  background: #fff;
  border-color: #d1d5db;
  color: #374151;
}

.bl-ghost-btn:hover {
  border-color: #dc2626;
  color: #dc2626;
}

.bl-primary-btn:disabled,
.bl-ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.bl-list {
  min-height: 180px;
}

.bl-state {
  padding: 48px 20px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.bl-state.error {
  color: #dc2626;
}

.bl-state.empty {
  color: #9ca3af;
  padding: 56px 20px 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.bl-empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fef2f2 0%, #f3e8ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  margin-bottom: 6px;
}

.bl-empty-title {
  font-size: 16px;
  color: #111827;
}

.bl-empty-desc {
  margin: 0;
  max-width: 460px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
}

.bl-table-wrap {
  overflow-x: auto;
}

.bl-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.bl-table th,
.bl-table td {
  padding: 11px 12px;
  border-bottom: 1px solid #f0f0f0;
  text-align: left;
  white-space: nowrap;
}

.bl-table th {
  background: #fafafa;
  color: #6b7280;
  font-weight: 600;
}

.bl-table tbody tr:hover {
  background: #fff7f7;
}

.bl-reason-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bl-goods-badge {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  padding: 3px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
}

.bl-goods-badge.all {
  background: #f3f4f6;
  color: #6b7280;
}

.bl-toggle {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  cursor: pointer;
}

.bl-toggle.on {
  border-color: #dc2626;
  background: #fef2f2;
  color: #b91c1c;
}

.bl-ops {
  display: flex;
  gap: 8px;
}

.bl-link-btn {
  border: none;
  background: none;
  color: #1f6feb;
  font-size: 13px;
  cursor: pointer;
  padding: 2px 4px;
}

.bl-link-btn.danger {
  color: #dc2626;
}

.bl-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.bl-modal {
  width: 520px;
  max-width: 100%;
  max-height: 92vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
}

.bl-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  position: sticky;
  top: 0;
  background: #fff;
}

.bl-modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.bl-icon-btn {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
}

.bl-modal-body {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bl-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
  position: sticky;
  bottom: 0;
  background: #fff;
}

.bl-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
