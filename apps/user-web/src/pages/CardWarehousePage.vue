<template>
  <div class="grid wide-right">
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>
    <!-- Left -->
    <div>
      <div class="grid stat-grid">
        <StatCard title="卡密组" :value="groupMetric(groups.length)" :change="groupsAvailable ? '总分组数' : '状态不可用'" icon="product" />
        <StatCard title="卡密总量" :value="groupMetric(stockStats.total)" :change="groupsAvailable ? '全部卡密' : '状态不可用'" icon="key" />
        <StatCard title="未使用" :value="groupMetric(stockStats.remain)" :change="groupsAvailable ? '可用库存' : '状态不可用'" icon="key" color="green" />
        <StatCard title="已使用" :value="groupMetric(stockStats.used)" :change="groupsAvailable ? '已消耗' : '状态不可用'" icon="account" />
        <StatCard title="异常/作废" :value="groupMetric(stockStats.invalid)" :change="groupsAvailable ? '需关注' : '状态不可用'" icon="warning" color="orange" />
        <StatCard title="低库存" :value="groupMetric(lowStockCount)" :change="groupsAvailable ? '低于预警阈值' : '状态不可用'" icon="warning" color="red" />
      </div>
      <CardPanel>
        <div class="toolbar">
          <input v-model="query.keyword" class="input large" placeholder="搜索卡密组名称" @keyup.enter="load">
          <AppButton @click="load">搜索</AppButton>
          <AppButton type="primary" :disabled="!groupsAvailable" @click="openCreateDialog">新建卡密组</AppButton>
        </div>
        <EmptyState v-if="groupsLoadError" variant="error" title="卡密分组暂时无法加载" :description="groupsLoadError">
          <template #actions><AppButton @click="load">重新加载</AppButton></template>
        </EmptyState>
        <BaseTable v-else :columns="groupCols" :rows="groupRows">
          <template #name="{row}">
            <div><strong>{{ row.groupName }}</strong><em v-if="row.remark" class="subtle" style="margin-left:6px">{{ row.remark }}</em></div>
          </template>
          <template #cardType="{row}">
            <Badge>{{ cardTypeLabel(row.cardType) }}</Badge>
          </template>
          <template #remain="{row}">
            <b :style="{ color: row.remainCount < (row.alertThreshold || 10) ? '#ef4444' : '#16bf78' }">{{ row.remainCount }}</b>
          </template>
          <template #status="{row}">
            <Badge :type="row.status === 1 ? 'green' : 'orange'">{{ row.status === 1 ? '启用' : '禁用' }}</Badge>
          </template>
          <template #op="{row}">
            <button class="link" @click="selectGroup(row.raw)">查看</button>
            <button class="link" @click="openEditDialog(row.raw)">编辑</button>
            <button class="link" @click="exportGroup(row.raw)">导出</button>
            <button class="link danger-text" @click="removeGroup(row.raw.id)">删除</button>
          </template>
          <template #empty>
            <EmptyState icon="🔑" title="还没有卡密组" description="先创建卡密组，再批量导入卡密；自动发货规则会从这里安全领取库存。">
              <template #actions><AppButton type="primary" @click="openCreateDialog">新建卡密组</AppButton></template>
            </EmptyState>
          </template>
        </BaseTable>
      </CardPanel>
      <CardPanel title="导入卡密" style="margin-top:16px">
        <div class="form-grid">
          <div class="form-row">
            <label>目标分组</label>
            <select v-model="importGroupId" class="input" :disabled="!groupsAvailable">
              <option value="">请选择分组</option>
              <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.groupName }}（余 {{ g.remainCount ?? '—' }}）</option>
            </select>
          </div>
          <div class="form-row">
            <label>导入方式</label>
            <div class="import-tabs">
              <button :class="['import-tab', { active: importMode === 'paste' }]" @click="importMode = 'paste'">粘贴导入</button>
              <button :class="['import-tab', { active: importMode === 'file' }]" @click="importMode = 'file'">文件导入</button>
            </div>
          </div>
          <div v-if="importMode === 'paste'" class="form-row">
            <label>每行一条卡密</label>
            <textarea v-model="bulkText" class="input" rows="6" placeholder="CARD-AAAA-BBBB&#10;CARD-CCCC-DDDD&#10;支持格式：卡密内容&#10;卡号----密码（卡号+密码类型）"></textarea>
            <span class="subtle" style="margin-top:4px">{{ bulkCount }} 条</span>
          </div>
          <div v-if="importMode === 'file'" class="form-row">
            <label>选择文件（TXT / CSV）</label>
            <div class="file-drop-zone" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleFileDrop">
              <input ref="fileInputRef" type="file" accept=".txt,.csv" style="display:none" @change="handleFileSelect">
              <span v-if="!importFileName">点击或拖拽 TXT/CSV 文件到此处</span>
              <span v-else class="file-name">{{ importFileName }}</span>
            </div>
            <span class="subtle" style="margin-top:4px">文件每行一条卡密，支持逗号/制表符/----分隔卡号和密码</span>
          </div>
          <div class="form-row" style="flex-direction:row;align-items:center;gap:12px">
            <AppButton type="primary" :disabled="!groupsAvailable || importing || !importGroupId" @click="submitImport">
              {{ importing ? '导入中...' : '确认导入' }}
            </AppButton>
            <span v-if="importResult" class="import-result">
              <span class="import-success">✓ 成功 {{ importResult.success }}</span>
              <span v-if="importResult.duplicate" class="import-duplicate">重复 {{ importResult.duplicate }}</span>
              <span v-if="importResult.fail" class="import-fail">失败 {{ importResult.fail }}</span>
            </span>
          </div>
        </div>
      </CardPanel>
    </div>
    <!-- Right -->
    <div>
      <CardPanel :title="selected ? selected.groupName : '卡密详情'">
        <EmptyState v-if="!selected" icon="👈" title="请选择卡密分组" description="从左侧列表选择一个卡密组，查看卡密明细、使用记录和导入历史。" style="padding:40px 0" />
        <template v-else>
          <div class="tab-bar">
            <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: activeTab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
          </div>
          <!-- 卡密明细 -->
          <div v-show="activeTab === 'items'">
            <div class="toolbar" style="margin-bottom:8px">
              <span class="table-info">共 <b>{{ itemTotal ?? '—' }}</b> 条卡密</span>
              <select v-model="itemStatusFilter" class="input" style="max-width:140px;margin-left:auto" @change="loadItems">
                <option value="">全部状态</option>
                <option value="0">未使用</option>
                <option value="1">已锁定</option>
                <option value="2">已使用</option>
                <option value="3">已作废</option>
                <option value="4">异常</option>
              </select>
            </div>
            <EmptyState v-if="itemLoadError" variant="error" title="卡密明细加载失败" :description="itemLoadError">
              <template #actions><AppButton @click="loadItems">重试</AppButton></template>
            </EmptyState>
            <BaseTable v-else :columns="itemCols" :rows="cardItems">
              <template #content="{row}">
                <code class="card-content-text">{{ row.cardContent || row.content || '-' }}</code>
              </template>
              <template #status="{row}">
                <Badge :type="itemStatusBadge(row.status)">{{ itemStatusLabel(row.status) }}</Badge>
              </template>
              <template #usedOrderId="{row}">{{ row.usedOrderId || '-' }}</template>
              <template #usedTime="{row}">{{ row.usedTime ? dateTime(row.usedTime) : '-' }}</template>
              <template #op="{row}">
                <button v-if="row.status === 0" class="link" @click="lockItem(row)">锁定</button>
                <button v-if="row.status === 1" class="link" @click="resetItem(row)">解锁</button>
                <button v-if="row.status === 2" class="link" @click="resetItem(row)">重置</button>
                <button v-if="row.status !== 3" class="link danger-text" @click="markInvalid(row)">作废</button>
                <button class="link danger-text" @click="removeItem(row)">删除</button>
              </template>
              <template #empty>
                <EmptyState icon="📦" title="当前分组暂无卡密" description="在左侧选择分组并粘贴或上传文件导入卡密。" />
              </template>
            </BaseTable>
            <div v-if="!itemLoadError && itemTotal > pageSize" class="pagination">
              <span class="page-info">第 {{ itemPage }} / {{ itemPages }} 页</span>
              <button class="page-no" :disabled="itemPage <= 1" @click="itemPage--; loadItems()">‹</button>
              <button class="page-no" :disabled="itemPage >= itemPages" @click="itemPage++; loadItems()">›</button>
            </div>
          </div>
          <!-- 使用记录 -->
          <div v-show="activeTab === 'usage'">
            <div class="toolbar" style="margin-bottom:8px">
              <span class="table-info">共 <b>{{ usageTotal ?? '—' }}</b> 条使用记录</span>
            </div>
            <EmptyState v-if="usageLoadError" variant="error" title="使用记录加载失败" :description="usageLoadError">
              <template #actions><AppButton @click="loadUsageRecords">重试</AppButton></template>
            </EmptyState>
            <BaseTable v-else :columns="usageCols" :rows="usageRecords">
              <template #content="{row}">
                <code class="card-content-text">{{ row.cardContent || row.content || '-' }}</code>
              </template>
              <template #orderInfo="{row}">
                <span>{{ row.usedOrderId || row.orderId || '-' }}</span>
              </template>
              <template #usedTime="{row}">{{ row.usedTime ? dateTime(row.usedTime) : '-' }}</template>
              <template #empty>
                <EmptyState icon="📋" title="暂无使用记录" description="卡密被使用后，记录会出现在这里。" />
              </template>
            </BaseTable>
            <div v-if="!usageLoadError && usageTotal > usagePageSize" class="pagination">
              <span class="page-info">第 {{ usagePage }} / {{ usagePages }} 页</span>
              <button class="page-no" :disabled="usagePage <= 1" @click="usagePage--; loadUsageRecords()">‹</button>
              <button class="page-no" :disabled="usagePage >= usagePages" @click="usagePage++; loadUsageRecords()">›</button>
            </div>
          </div>
          <!-- 库存统计 -->
          <div v-show="activeTab === 'stats'">
            <EmptyState v-if="stockLoadError" variant="error" title="库存统计加载失败" :description="stockLoadError">
              <template #actions><AppButton @click="loadStockStats">重试</AppButton></template>
            </EmptyState>
            <div v-else class="stock-stats">
              <div class="stat-item">
                <span class="stat-label">总数量</span>
                <strong class="stat-value">{{ stockValue('totalCount') }}</strong>
              </div>
              <div class="stat-item green">
                <span class="stat-label">未使用</span>
                <strong class="stat-value">{{ stockValue('remainCount') }}</strong>
              </div>
              <div class="stat-item orange">
                <span class="stat-label">已锁定</span>
                <strong class="stat-value">{{ stockValue('lockedCount') }}</strong>
              </div>
              <div class="stat-item gray">
                <span class="stat-label">已使用</span>
                <strong class="stat-value">{{ stockValue('usedCount') }}</strong>
              </div>
              <div class="stat-item red">
                <span class="stat-label">已作废</span>
                <strong class="stat-value">{{ stockValue('invalidCount') }}</strong>
              </div>
              <div class="stat-item red">
                <span class="stat-label">异常</span>
                <strong class="stat-value">{{ stockValue('errorCount') }}</strong>
              </div>
            </div>
          </div>
        </template>
      </CardPanel>
    </div>
    <!-- Edit / Create Dialog -->
    <div v-if="editDialogVisible" class="modal-overlay" @click.self="closeEditDialog">
      <div class="modal-content">
        <h3>{{ editForm.id ? '编辑卡密分组' : '新建卡密分组' }}</h3>
        <div class="form-grid">
          <div class="form-row">
            <label>分组名称 <span class="required">*</span></label>
            <input v-model="editForm.groupName" class="input" placeholder="例如：月卡VIP" />
          </div>
          <div class="form-row">
            <label>卡密类型</label>
            <select v-model="editForm.cardType" class="input">
              <option value="unique">唯一卡密</option>
              <option value="card_password">卡号+密码</option>
              <option value="link_code">链接+提取码</option>
              <option value="account_password">账号+密码</option>
              <option value="custom">自定义文本</option>
            </select>
          </div>
          <div class="form-row">
            <label>卡号前缀（可选）</label>
            <input v-model="editForm.cardPrefix" class="input" placeholder="例如：VIP-" />
          </div>
          <div class="form-row">
            <label>密码前缀（可选）</label>
            <input v-model="editForm.passwordPrefix" class="input" placeholder="例如：PWD-" />
          </div>
          <div class="form-row">
            <label>成本单价</label>
            <input v-model.number="editForm.costPrice" type="number" step="0.01" min="0" class="input" placeholder="0.00" />
          </div>
          <div class="form-row">
            <label>售价建议</label>
            <input v-model.number="editForm.suggestedPrice" type="number" step="0.01" min="0" class="input" placeholder="0.00" />
          </div>
          <div class="form-row">
            <label>库存预警阈值</label>
            <input v-model.number="editForm.alertThreshold" type="number" min="0" class="input" placeholder="10" />
          </div>
          <div class="form-row">
            <label>状态</label>
            <select v-model.number="editForm.status" class="input">
              <option :value="1">启用</option>
              <option :value="0">禁用</option>
            </select>
          </div>
          <div class="form-row" style="grid-column:1/-1">
            <label>备注</label>
            <textarea v-model="editForm.remark" class="input" rows="3" placeholder="可选备注信息"></textarea>
          </div>
        </div>
        <div class="toolbar" style="justify-content:flex-end;margin-top:20px">
          <AppButton @click="closeEditDialog">取消</AppButton>
          <AppButton type="primary" :loading="saving" @click="saveGroup">{{ editForm.id ? '保存' : '创建' }}</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import { confirmDelete, confirmAction } from '../utils/confirmAction.js'
import {
  getCards,
  createCard,
  updateCard,
  deleteCard,
  getCardItems,
  batchCreateCardItems,
  deleteCardItem,
  resetCardItem,
  markCardItemInvalid,
  getCardStockStats,
  getCardUsageRecords,
  exportCardItems
} from '../api/cards.js'
import { recordsOfOrThrow, totalOf, dateTime } from '../utils/apiData.js'

// ─── State ───
const error = ref('')
const success = ref('')
const groupsAvailable = ref(false)
const groupsLoadError = ref('')
const groups = ref([])
const selected = ref(null)
const cardItems = ref([])
const usageRecords = ref([])
const stockDetail = ref({})
const itemLoadError = ref('')
const usageLoadError = ref('')
const stockLoadError = ref('')
const query = reactive({ keyword: '' })

// ─── Import ───
const importGroupId = ref('')
const importMode = ref('paste')
const bulkText = ref('')
const importing = ref(false)
const importResult = ref(null)
const fileInputRef = ref(null)
const importFileName = ref('')

// ─── Items pagination ───
const itemPage = ref(1)
const itemTotal = ref(0)
const pageSize = 50
const itemStatusFilter = ref('')

// ─── Usage pagination ───
const usagePage = ref(1)
const usageTotal = ref(0)
const usagePageSize = 20

// ─── Tab ───
const activeTab = ref('items')
const tabs = [
  { key: 'items', label: '卡密明细' },
  { key: 'usage', label: '使用记录' },
  { key: 'stats', label: '库存统计' }
]

// ─── Edit Dialog ───
const editDialogVisible = ref(false)
const saving = ref(false)
const editForm = reactive({
  id: null,
  groupName: '',
  cardType: 'unique',
  cardPrefix: '',
  passwordPrefix: '',
  costPrice: 0,
  suggestedPrice: 0,
  alertThreshold: 10,
  remark: '',
  status: 1
})

// ─── Card Type Labels ───
const cardTypeMap = {
  unique: '唯一卡密',
  card_password: '卡号+密码',
  link_code: '链接+提取码',
  account_password: '账号+密码',
  custom: '自定义文本'
}
function cardTypeLabel(type) {
  return cardTypeMap[type] || type || '-'
}

// ─── Item Status ───
const itemStatusMap = {
  0: { label: '未使用', badge: 'green' },
  1: { label: '已锁定', badge: 'orange' },
  2: { label: '已使用', badge: 'gray' },
  3: { label: '已作废', badge: 'red' },
  4: { label: '异常', badge: 'red' }
}
function itemStatusLabel(status) {
  return itemStatusMap[status]?.label || '未知'
}
function itemStatusBadge(status) {
  return itemStatusMap[status]?.badge || 'gray'
}

// ─── Computed ───
const groupRows = computed(() => groups.value.map(g => ({ ...g, raw: g })))

const groupCols = [
  { key: 'name', title: '分组名称' },
  { key: 'cardType', title: '类型' },
  { key: 'totalCount', title: '总量' },
  { key: 'remain', title: '可用' },
  { key: 'usedCount', title: '已使用' },
  { key: 'status', title: '状态' },
  { key: 'op', title: '操作' }
]

const itemCols = [
  { key: 'content', title: '卡密内容' },
  { key: 'status', title: '状态' },
  { key: 'usedOrderId', title: '订单ID' },
  { key: 'usedTime', title: '使用时间' },
  { key: 'op', title: '操作' }
]

const usageCols = [
  { key: 'content', title: '卡密内容' },
  { key: 'orderInfo', title: '关联订单' },
  { key: 'usedTime', title: '使用时间' }
]

const stockStats = computed(() => {
  const sum = keys => {
    const values = groups.value.map(group => keys.reduce((total, key) => total + Number(group[key]), 0))
    return values.every(Number.isFinite) ? values.reduce((total, value) => total + value, 0) : null
  }
  return {
    total: sum(['totalCount']),
    remain: sum(['remainCount']),
    used: sum(['usedCount']),
    invalid: sum(['invalidCount', 'errorCount'])
  }
})

const lowStockCount = computed(() => {
  if (groups.value.some(group => (
    !Number.isFinite(Number(group.remainCount))
    || (group.alertThreshold != null && !Number.isFinite(Number(group.alertThreshold)))
  ))) return null
  return groups.value.filter(group => Number(group.remainCount) < Number(group.alertThreshold ?? 10)).length
})

const bulkCount = computed(() => {
  return bulkText.value.split(/\n+/).map(s => s.trim()).filter(Boolean).length
})

const itemPages = computed(() => Math.max(1, Math.ceil(itemTotal.value / pageSize)))
const usagePages = computed(() => Math.max(1, Math.ceil(usageTotal.value / usagePageSize)))

// ─── Group CRUD ───
async function load({ preserveNotice = false } = {}) {
  if (!preserveNotice) {
    error.value = ''
    success.value = ''
  }
  groupsAvailable.value = false
  groupsLoadError.value = ''
  try {
    const res = await getCards(query)
    groups.value = recordsOfOrThrow(res?.data, '卡密分组响应格式异常')
    if (!selected.value && groups.value[0]) {
      await selectGroup(groups.value[0])
    }
    if (selected.value) {
      const current = groups.value.find(g => String(g.id) === String(selected.value.id))
      if (current) {
        selected.value = current
      } else {
        selected.value = null
        cardItems.value = []
        usageRecords.value = []
        stockDetail.value = {}
      }
    }
    groupsAvailable.value = true
  } catch (e) {
    groups.value = []
    selected.value = null
    importGroupId.value = ''
    editDialogVisible.value = false
    groupsLoadError.value = `${e.message || '卡密分组加载失败'}；分组成功加载前禁止创建、编辑、删除或导入卡密。`
  }
}

function groupMetric(value) {
  return groupsAvailable.value && value !== null && value !== undefined ? value : '—'
}

async function selectGroup(g) {
  selected.value = g
  importGroupId.value = g.id
  activeTab.value = 'items'
  itemPage.value = 1
  itemStatusFilter.value = ''
  await loadItems()
}

function openCreateDialog() {
  if (!groupsAvailable.value) return
  editForm.id = null
  editForm.groupName = ''
  editForm.cardType = 'unique'
  editForm.cardPrefix = ''
  editForm.passwordPrefix = ''
  editForm.costPrice = 0
  editForm.suggestedPrice = 0
  editForm.alertThreshold = 10
  editForm.remark = ''
  editForm.status = 1
  editDialogVisible.value = true
}

function openEditDialog(group) {
  if (!groupsAvailable.value) return
  editForm.id = group.id
  editForm.groupName = group.groupName || ''
  editForm.cardType = group.cardType || 'unique'
  editForm.cardPrefix = group.cardPrefix || ''
  editForm.passwordPrefix = group.passwordPrefix || ''
  editForm.costPrice = Number(group.costPrice || 0)
  editForm.suggestedPrice = Number(group.suggestedPrice || 0)
  editForm.alertThreshold = Number(group.alertThreshold || 10)
  editForm.remark = group.remark || ''
  editForm.status = group.status !== undefined ? group.status : 1
  editDialogVisible.value = true
}

function closeEditDialog() {
  editDialogVisible.value = false
}

async function saveGroup() {
  if (!groupsAvailable.value) return
  if (!editForm.groupName.trim()) {
    error.value = '请输入分组名称'
    return
  }
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    const data = { ...editForm }
    if (editForm.id) {
      await updateCard(editForm.id, data)
      success.value = '卡密分组已更新'
    } else {
      await createCard(data)
      success.value = '卡密分组已创建'
    }
    editDialogVisible.value = false
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function removeGroup(id) {
  if (!groupsAvailable.value) return
  if (!await confirmAction({ title: '确认删除卡密分组？', description: '该操作会影响自动发货库存，请确认没有正在使用的发货规则。', dangerous: true, confirmText: 'DELETE' })) return
  try {
    await deleteCard(id)
    success.value = '卡密分组已删除'
    if (selected.value && String(selected.value.id) === String(id)) {
      selected.value = null
    }
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message
  }
}

// ─── Import ───
async function submitImport() {
  if (!groupsAvailable.value) return
  if (importing.value) return
  if (!importGroupId.value) {
    error.value = '请选择目标分组'
    return
  }
  let lines = []
  if (importMode.value === 'paste') {
    lines = bulkText.value.split(/\n+/).map(s => s.trim()).filter(Boolean)
  } else if (importFileName.value) {
    // lines already populated from file read
    lines = parsedFileLines.value
  }
  if (!lines.length) {
    error.value = importMode.value === 'paste' ? '请粘贴卡密内容' : '请选择文件'
    return
  }
  importing.value = true
  error.value = ''
  success.value = ''
  importResult.value = null
  try {
    const payload = lines.map(line => {
      // Support "----" separator for card+password types
      const sepIdx = line.indexOf('----')
      if (sepIdx > 0) {
        return { content: line, cardContent: line.slice(0, sepIdx), password: line.slice(sepIdx + 4) }
      }
      // Support comma/tab separator
      const commaIdx = line.indexOf(',')
      if (commaIdx > 0) {
        return { content: line, cardContent: line.slice(0, commaIdx), password: line.slice(commaIdx + 1) }
      }
      const tabIdx = line.indexOf('\t')
      if (tabIdx > 0) {
        return { content: line, cardContent: line.slice(0, tabIdx), password: line.slice(tabIdx + 1) }
      }
      return { content: line }
    })
    const res = await batchCreateCardItems(importGroupId.value, { items: payload })
    const resultData = res?.data
    if (!resultData || typeof resultData !== 'object' || Array.isArray(resultData)) {
      throw new Error('卡密导入结果响应格式异常')
    }
    const successCount = Number(resultData.successCount ?? resultData.success)
    const duplicateCount = Number(resultData.duplicateCount ?? resultData.duplicate)
    const failCount = Number(resultData.failCount ?? resultData.fail)
    if (![successCount, duplicateCount, failCount].every(value => Number.isSafeInteger(value) && value >= 0)) {
      throw new Error('卡密导入结果缺少有效统计')
    }
    importResult.value = {
      success: successCount,
      duplicate: duplicateCount,
      fail: failCount
    }
    success.value = `成功导入 ${importResult.value.success} 条卡密`
    bulkText.value = ''
    importFileName.value = ''
    parsedFileLines.value = []
    await load({ preserveNotice: true })
    const g = groups.value.find(x => String(x.id) === String(importGroupId.value))
    if (g) {
      selected.value = g
      await loadItems()
    }
  } catch (e) {
    error.value = e.message || '导入失败'
    importResult.value = null
  } finally {
    importing.value = false
  }
}

const parsedFileLines = ref([])

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) readImportFile(file)
}

function handleFileDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file) readImportFile(file)
}

function readImportFile(file) {
  importFileName.value = file.name
  parsedFileLines.value = []
  const reader = new FileReader()
  reader.onload = (ev) => {
    const text = ev.target?.result || ''
    const lines = text.split(/\r?\n/).map(s => s.trim()).filter(Boolean)
    parsedFileLines.value = lines
  }
  reader.onerror = () => {
    error.value = '文件读取失败'
  }
  reader.readAsText(file)
}

// ─── Export ───
async function exportGroup(group) {
  try {
    const res = await exportCardItems(group.id, {})
    if (!(res instanceof Blob) || res.size === 0) throw new Error('导出文件为空或格式异常')
    const blob = res
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${group.groupName}_卡密导出.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    success.value = `「${group.groupName}」卡密已导出`
  } catch (e) {
    error.value = e.message || '导出失败'
  }
}

// ─── Items ───
async function loadItems() {
  if (!selected.value) return
  itemLoadError.value = ''
  try {
    const params = { current: itemPage.value, size: pageSize }
    if (itemStatusFilter.value !== '') {
      params.status = itemStatusFilter.value
    }
    const res = await getCardItems(selected.value.id, params)
    const pageData = recordsOfOrThrow(res?.data, '卡密明细响应格式异常')
    cardItems.value = pageData
    itemTotal.value = totalOf(res.data, cardItems.value.length)
  } catch (loadError) {
    cardItems.value = []
    itemTotal.value = null
    itemLoadError.value = loadError?.message || '卡密明细加载失败，请重试。'
  }
}

async function removeItem(item) {
  if (!selected.value || !await confirmDelete('该卡密')) return
  try {
    await deleteCardItem(selected.value.id, item.id)
    success.value = '卡密已删除'
    await loadItems()
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message
  }
}

async function resetItem(item) {
  if (!selected.value) return
  try {
    await resetCardItem(selected.value.id, item.id)
    success.value = '卡密已重置'
    await loadItems()
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message
  }
}

async function lockItem(item) {
  if (!selected.value) return
  try {
    const { lockCardItem } = await import('../api/cards.js')
    await lockCardItem(selected.value.id, item.id)
    success.value = '卡密已锁定'
    await loadItems()
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message || '锁定失败'
  }
}

async function markInvalid(item) {
  if (!selected.value) return
  if (!await confirmAction({ title: '确认作废该卡密？', dangerous: true })) return
  try {
    await markCardItemInvalid(selected.value.id, item.id)
    success.value = '卡密已作废'
    await loadItems()
    await load({ preserveNotice: true })
  } catch (e) {
    error.value = e.message
  }
}

// ─── Usage Records ───
async function loadUsageRecords() {
  if (!selected.value) return
  usageLoadError.value = ''
  try {
    const params = { current: usagePage.value, size: usagePageSize }
    const res = await getCardUsageRecords(selected.value.id, params)
    const pageData = recordsOfOrThrow(res?.data, '卡密使用记录响应格式异常')
    usageRecords.value = pageData
    usageTotal.value = totalOf(res.data, usageRecords.value.length)
  } catch (loadError) {
    usageRecords.value = []
    usageTotal.value = null
    usageLoadError.value = loadError?.message || '使用记录加载失败，请重试。'
  }
}

// ─── Stock Stats ───
async function loadStockStats() {
  if (!selected.value) return
  stockLoadError.value = ''
  try {
    const res = await getCardStockStats(selected.value.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('库存统计响应格式异常')
    }
    const fields = ['totalCount', 'remainCount', 'lockedCount', 'usedCount', 'invalidCount', 'errorCount']
    if (fields.some(key => !Number.isSafeInteger(data[key]) || data[key] < 0)) {
      throw new Error('库存统计响应缺少有效指标')
    }
    stockDetail.value = data
  } catch (loadError) {
    stockDetail.value = {}
    stockLoadError.value = loadError?.message || '库存统计加载失败，请重试。'
  }
}

function stockValue(key) {
  const value = stockDetail.value?.[key]
  return value === null || value === undefined ? '—' : value
}

// ─── Tab Switching ───
function switchTab(key) {
  activeTab.value = key
  if (key === 'items') {
    itemPage.value = 1
    loadItems()
  } else if (key === 'usage') {
    usagePage.value = 1
    loadUsageRecords()
  } else if (key === 'stats') {
    loadStockStats()
  }
}

function onHeaderAction(event) {
  if (event.detail === 'cards-create-group') openCreateDialog()
  if (event.detail === 'cards-export-current' && selected.value) exportGroup(selected.value)
  if (event.detail === 'cards-refresh') load()
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
.success { background: #ecfdf3; color: #067647; border-color: #abefc6; }

.import-tabs {
  display: flex;
  gap: 4px;
  background: #f5f6fa;
  border-radius: 10px;
  padding: 3px;
}
.import-tab {
  flex: 1;
  padding: 7px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #526079;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
  transition: all .15s;
}
.import-tab.active {
  background: #fff;
  color: #2d5bff;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.import-tab:hover:not(.active) { color: #2d5bff; }

.file-drop-zone {
  border: 1px dashed #b8c9e5;
  border-radius: 10px;
  background: #fbfdff;
  padding: 24px 16px;
  text-align: center;
  color: #0d6bff;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.file-drop-zone:hover {
  border-color: #0d6bff;
  background: #f0f6ff;
}
.file-drop-zone .file-name {
  color: #16213e;
  font-weight: 600;
}

.import-result {
  display: inline-flex;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
}
.import-success { color: #16bf78; }
.import-duplicate { color: #f59e0b; }
.import-fail { color: #ef4444; }

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  background: #f5f6fa;
  border-radius: 10px;
  padding: 3px;
}
.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #526079;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
  transition: all .15s;
}
.tab-btn.active {
  background: #fff;
  color: #2d5bff;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.tab-btn:hover:not(.active) { color: #2d5bff; }

.table-info {
  font-size: 14px;
  color: #526079;
}

.card-content-text {
  max-width: 280px;
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

/* Stock Stats */
.stock-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 4px 0;
}
.stat-item {
  background: #f8faff;
  border: 1px solid #eef3fa;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}
.stat-item .stat-label {
  display: block;
  font-size: 13px;
  color: #667085;
  margin-bottom: 6px;
}
.stat-item .stat-value {
  font-size: 22px;
  color: #16213e;
}
.stat-item.green .stat-value { color: #16bf78; }
.stat-item.orange .stat-value { color: #f59e0b; }
.stat-item.gray .stat-value { color: #667085; }
.stat-item.red .stat-value { color: #ef4444; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 0 4px;
  font-size: 13px;
  color: #667085;
}
.page-info {
  margin-right: 8px;
}
.page-no {
  min-width: 32px;
  height: 32px;
  border: 1px solid #e4ebf5;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  cursor: pointer;
  font-size: 15px;
  color: #526079;
  transition: all .15s;
}
.page-no:hover:not(:disabled) {
  border-color: #0d6bff;
  color: #0d6bff;
}
.page-no:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #fff;
  border-radius: 20px;
  padding: 28px;
  max-width: 540px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,.2);
}
.modal-content h3 {
  margin: 0 0 16px;
  font-size: 18px;
  color: #16213e;
}

.required { color: #ef4444; }

.subtle { color: #98a2b3; font-size: 13px; }
</style>
