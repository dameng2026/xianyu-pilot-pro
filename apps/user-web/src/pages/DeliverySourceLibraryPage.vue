<template>
  <div class="source-library-page">
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <!-- 货源板块：统计概览 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon-circle blue"><span class="stat-icon-svg">📦</span></div>
        <div class="stat-info">
          <div class="stat-label">货源总数</div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-trend muted">统一管理的货源条目</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle orange"><span class="stat-icon-svg">🔑</span></div>
        <div class="stat-info">
          <div class="stat-label">卡密发货</div>
          <div class="stat-value">{{ stats.cardSources }}</div>
          <div class="stat-trend muted">从卡密分组自动扣减</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle green"><span class="stat-icon-svg">📝</span></div>
        <div class="stat-info">
          <div class="stat-label">文本发货</div>
          <div class="stat-value">{{ stats.textSources }}</div>
          <div class="stat-trend muted">固定文案直接发送</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle purple"><span class="stat-icon-svg">🔗</span></div>
        <div class="stat-info">
          <div class="stat-label">已配置商品</div>
          <div class="stat-value">{{ stats.totalConfigured }}</div>
          <div class="stat-trend muted">货源绑定商品总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle red"><span class="stat-icon-svg">⚠</span></div>
        <div class="stat-info">
          <div class="stat-label">库存预警</div>
          <div class="stat-value">{{ stats.lowStock }}</div>
          <div class="stat-trend" :class="stats.lowStock > 0 ? 'down' : 'muted'">
            {{ stats.lowStock > 0 ? '卡密库存不足，请补充' : '库存充足' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 货源列表 -->
    <div class="source-table-card">
      <div class="table-header">
        <h3 class="table-title">货源列表</h3>
        <div class="table-actions">
          <button class="action-btn primary-action" :disabled="!sourcesAvailable" @click="openCreate">
            <span>＋</span> 新增货源
          </button>
          <button class="action-btn icon-only" :disabled="!sourcesAvailable" @click="loadSources" title="刷新">
            <span class="refresh-icon">↻</span>
          </button>
        </div>
      </div>
      <div class="filter-row">
        <div class="filter-search">
          <input v-model="query.keyword" class="search-input" placeholder="搜索标题 / 正文 / 备注" @keyup.enter="loadSources" />
          <span class="search-icon">🔍</span>
        </div>
        <AppButton type="primary" class="btn-query" @click="loadSources">搜索</AppButton>
      </div>
      <div class="filter-tip">点击货源行可查看详情、配置商品或使用 AI 一键匹配适配商品。</div>

      <EmptyState v-if="loadError" variant="error" title="货源库暂时无法加载" :description="loadError">
        <template #actions><AppButton @click="loadSources">重新加载</AppButton></template>
      </EmptyState>
      <BaseTable v-else :columns="columns" :rows="rows" @row-click="selectSource">
        <template #title="{ row }">
          <div>
            <div class="strong">{{ row.title }}</div>
            <div class="subtle">{{ row.remark || '无备注' }}</div>
          </div>
        </template>
        <template #content="{ row }">
          <div class="content-preview">{{ row.content }}</div>
        </template>
        <template #mode="{ row }">
          <Badge :type="row.deliveryMode === 'card' ? 'orange' : 'gray'">
            {{ row.deliveryMode === 'card' ? '卡密发货' : '文本发货' }}
          </Badge>
        </template>
        <template #stock="{ row }">
          <span v-if="row.deliveryMode === 'card'" :class="['stock-cell', { low: (row.cardRemainCount ?? 0) <= 0 }]">
            剩余 {{ row.cardRemainCount ?? 0 }}
          </span>
          <span v-else class="subtle">文本</span>
        </template>
        <template #usage="{ row }">
          <Badge>{{ row.usageCount ?? '—' }} 个商品</Badge>
        </template>
        <template #op="{ row }">
          <button class="link" @click.stop="editSource(row)">编辑</button>
          <button class="link" @click.stop="analyzeSource(row)">AI一键配置</button>
          <button class="link danger-text" @click.stop="removeSource(row)">删除</button>
        </template>
      </BaseTable>
    </div>

    <CardPanel v-if="editing" :title="editing.id ? '编辑货源' : '新增货源'" style="margin-top:16px" class="source-editor-panel">
      <div class="editor-layout">
        <div class="editor-left">
          <div class="form-field">
            <label class="field-label"><span class="required">*</span>标题</label>
            <div class="field-input-wrap">
              <input v-model="form.title" class="field-input" placeholder="给用户和 AI 模型看的标题" maxlength="50" />
              <span class="char-count">{{ (form.title || '').length }}/50</span>
            </div>
          </div>

          <div class="form-field">
            <label class="field-label">
              <span class="required">*</span>正文
              <button
                v-if="form.deliveryMode === 'card'"
                type="button"
                class="placeholder-btn"
                @click="insertCardPlaceholder"
              >+ 插入 {卡密占位}</button>
            </label>
            <div class="field-input-wrap">
              <textarea
                ref="contentTextareaRef"
                v-model="form.content"
                rows="6"
                class="field-textarea"
                :placeholder="form.deliveryMode === 'card' ? '实际发货文本，需包含 {卡密占位}，发货时会自动替换为认领到的卡密' : '实际发货文本内容'"
                maxlength="5000"
              ></textarea>
              <span class="char-count">{{ (form.content || '').length }}/5000</span>
            </div>
          </div>

          <div class="form-field">
            <label class="field-label">备注（选填）</label>
            <div class="field-input-wrap">
              <textarea v-model="form.remark" rows="3" class="field-textarea" placeholder="可添加备注信息，方便后续管理（如来源、用途等）" maxlength="200"></textarea>
              <span class="char-count">{{ (form.remark || '').length }}/200</span>
            </div>
          </div>
        </div>

        <div class="editor-right">
          <div class="setting-card">
            <div class="setting-card-title">发送类型</div>
            <div class="mode-cards">
              <label class="mode-card" :class="{ active: form.deliveryMode === 'text' }">
                <input v-model="form.deliveryMode" type="radio" value="text" @change="onDeliveryModeChange" />
                <span class="mode-card-radio"></span>
                <div class="mode-card-body">
                  <span class="mode-card-title">文本发送</span>
                  <span class="mode-card-desc">通过文本消息发送给买家，适合固定文案内容</span>
                </div>
              </label>
              <label class="mode-card" :class="{ active: form.deliveryMode === 'card' }">
                <input v-model="form.deliveryMode" type="radio" value="card" @change="onDeliveryModeChange" />
                <span class="mode-card-radio"></span>
                <div class="mode-card-body">
                  <span class="mode-card-title">卡密发送</span>
                  <span class="mode-card-desc">从卡密库中选择一张卡密替换占位符后发送</span>
                </div>
              </label>
            </div>
            <div class="info-tip">
              <span class="info-tip-icon">i</span>
              <span>提示：卡密发送将在发送时自动替换占位符，例如 <code>{卡密}</code>、<code>{激活码}</code> 等占位符内容。</span>
            </div>
            <div v-if="form.deliveryMode === 'card'" class="card-group-select">
              <select v-model="form.cardGroupId" class="field-input">
                <option value="" disabled>请选择卡密分组</option>
                <option v-for="g in cardGroups" :key="g.id" :value="g.id">
                  {{ g.groupName }}（剩余 {{ g.remainCount ?? 0 }} / 共 {{ g.totalCount ?? 0 }}）
                </option>
              </select>
              <div v-if="cardGroupsLoading" class="subtle" style="margin-top:8px;font-size:13px">加载中…</div>
              <div v-else-if="cardGroups.length === 0" class="subtle danger-text" style="margin-top:8px;font-size:13px">
                暂无卡密分组，请先到「卡密仓库」创建分组并导入卡密
              </div>
              <div v-else-if="selectedCardGroup" class="stock-display" style="margin-top:10px">
                <span class="stock-label-text">当前剩余：</span>
                <span :class="['stock-value-text', { low: selectedCardRemainCount <= 0 }]">
                  {{ selectedCardRemainCount }} 张
                </span>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-card-title">库存设置</div>
            <div class="stock-setting-row">
              <div class="stock-setting-item">
                <div class="stock-setting-label">库存类型</div>
                <div class="stock-type-tag" :class="{ 'card-type': form.deliveryMode === 'card' }">
                  {{ form.deliveryMode === 'card' ? '卡密' : '文本' }}
                </div>
                <div class="stock-setting-hint">
                  {{ form.deliveryMode === 'card' ? '卡密类型自动从分组扣减库存' : '文本类型无需设置库存' }}
                </div>
              </div>
              <div class="stock-setting-item">
                <div class="stock-setting-label">已配置商品</div>
                <div class="configured-goods-row">
                  <span :class="['goods-count-text', { zero: !editingUsageCount }]">{{ editingUsageCount }} 个商品</span>
                  <button v-if="editing.id" type="button" class="manage-goods-btn" @click="manageConfiguredGoods">管理商品</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="form-actions">
        <AppButton type="primary" class="save-btn" @click="saveSource">保存</AppButton>
        <AppButton class="cancel-btn" @click="cancelEdit">取消</AppButton>
      </div>
    </CardPanel>

    <template v-if="selected">
      <CardPanel title="货源详情" style="margin-top:16px">
        <div class="source-summary">
          <div class="summary-item">
            <div class="summary-label">当前货源</div>
            <div class="summary-value">{{ selected.title || '-' }}</div>
          </div>
          <div class="summary-item">
            <div class="summary-label">已配置商品</div>
            <div class="summary-value">{{ goodsAvailable ? configuredGoods.length : '—' }}</div>
          </div>
          <div class="summary-item">
            <div class="summary-label">可选商品总数</div>
            <div class="summary-value">{{ goodsAvailable ? allGoods.length : '—' }}</div>
          </div>
        </div>
        <div class="subtle source-preview">{{ selected.content || '暂无正文内容' }}</div>
      </CardPanel>

      <CardPanel title="已配置商品" style="margin-top:16px" data-source-configured-goods>
        <div class="toolbar">
          <span class="subtle">用于查看当前货源已经绑定过的商品</span>
          <AppButton @click="refreshSelectedGoods">刷新商品列表</AppButton>
          <AppButton
            :disabled="!goodsAvailable || selectedConfiguredIds.length === 0"
            @click="batchRemoveConfiguredGoods"
          >批量删除</AppButton>
        </div>
        <EmptyState v-if="goodsLoading" title="正在加载商品数据" description="正在读取当前货源的已配置商品。" />
        <EmptyState v-else-if="goodsLoadError" variant="error" title="已配置商品暂时无法加载" :description="goodsLoadError">
          <template #actions><AppButton @click="refreshSelectedGoods">重新加载</AppButton></template>
        </EmptyState>
        <BaseTable
          v-else
          v-model:selected-keys="selectedConfiguredIds"
          :columns="configuredColumns"
          :rows="filteredConfiguredGoods"
          :selectable="true"
          :row-key="row => row.id"
        >
          <template #title="{ row }">
            <div class="goods-cell">
              <img v-if="goodsCover(row)" :src="goodsCover(row)" class="goods-thumb" alt="" />
              <div v-else class="goods-thumb placeholder"></div>
              <div class="goods-main">
                <div class="strong">{{ row.title }}</div>
                <div class="subtle">{{ row.category || '-' }}</div>
                <div class="account-chip">
                  <img v-if="accountAvatar(row)" :src="accountAvatar(row)" class="account-avatar" alt="" />
                  <div v-else class="account-avatar placeholder avatar-placeholder"></div>
                  <span class="subtle">{{ accountDisplayLabel(row) }}</span>
                </div>
              </div>
            </div>
          </template>
          <template #bind="{ row }">
            <Badge type="green">{{ bindStateLabel(row) }}</Badge>
          </template>
          <template #single="{ row }">
            <button class="link" :disabled="!goodsAvailable" @click.stop="applyOne(row)">再次配置</button>
            <button class="link danger-text" :disabled="!goodsAvailable" @click.stop="removeConfiguredGoods(row)">删除</button>
          </template>
        </BaseTable>
      </CardPanel>

      <CardPanel :title="goodsView === 'recommend' ? 'AI 推荐商品' : '商品列表'" style="margin-top:16px">
        <div class="toolbar">
          <input
            v-model="goodsKeyword"
            class="input"
            placeholder="搜索商品标题 / 分类"
            style="max-width:260px"
          />
          <AppButton :type="goodsView === 'all' ? 'primary' : 'default'" @click="showAllGoods">全部商品</AppButton>
          <AppButton :type="goodsView === 'recommend' ? 'primary' : 'default'" :disabled="!goodsAvailable" @click="showRecommendedGoods">智能推荐</AppButton>
          <AppButton type="primary" :disabled="!goodsAvailable" @click="analyzeSource(selected)">分析匹配商品</AppButton>
          <select v-model="applyTiming" class="input" style="max-width:200px" :disabled="!goodsAvailable">
            <option value="payDelivery">付款后发货</option>
            <option value="confirmDelivery">确认收货后赠送</option>
            <option value="reviewDelivery">好评后赠送</option>
          </select>
          <AppButton :disabled="!goodsAvailable || selectedGoodsIds.length === 0" @click="applySelectedGoods">批量配置</AppButton>
        </div>
        <div class="subtle" style="margin-bottom:12px">
          {{ goodsView === 'recommend' ? recommendedHint : '可先查看全部商品，再使用 AI 自动筛选高匹配商品。' }}
        </div>
        <EmptyState v-if="goodsLoading" title="正在加载商品数据" description="正在读取可配置商品。" />
        <EmptyState v-else-if="goodsLoadError" variant="error" title="商品列表暂时无法加载" :description="goodsLoadError">
          <template #actions><AppButton @click="refreshSelectedGoods">重新加载</AppButton></template>
        </EmptyState>
        <BaseTable
          v-else
          v-model:selected-keys="selectedGoodsIds"
          :columns="goodsColumns"
          :rows="filteredDisplayGoods"
          :selectable="true"
          :row-key="row => row.id"
        >
          <template #title="{ row }">
            <div class="goods-cell">
              <img v-if="goodsCover(row)" :src="goodsCover(row)" class="goods-thumb" alt="" />
              <div v-else class="goods-thumb placeholder"></div>
              <div class="goods-main">
                <div class="strong">{{ row.title }}</div>
                <div class="subtle">{{ row.category || '-' }}</div>
                <div class="account-chip">
                  <img v-if="accountAvatar(row)" :src="accountAvatar(row)" class="account-avatar" alt="" />
                  <div v-else class="account-avatar placeholder avatar-placeholder"></div>
                  <span class="subtle">{{ accountDisplayLabel(row) }}</span>
                </div>
              </div>
            </div>
          </template>
          <template #bind="{ row }">
            <Badge :type="row.configured ? 'green' : 'gray'">{{ bindStateLabel(row) }}</Badge>
          </template>
          <template #score="{ row }">
            <Badge :type="confidenceType(row.confidence, row.configured)">
              {{ confidenceLabel(row.confidence, row.configured) }}
            </Badge>
          </template>
          <template #reason="{ row }">
            <span class="subtle">{{ row.reason || (row.configured ? '该商品已配置当前货源' : '可手动配置') }}</span>
          </template>
          <template #single="{ row }">
            <button class="link" :disabled="!goodsAvailable" @click.stop="applyOne(row)">{{ row.configured ? '重新配置' : '配置到该商品' }}</button>
          </template>
        </BaseTable>
      </CardPanel>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  applyDeliverySourceToGoods,
  createDeliverySource,
  deleteDeliverySource,
  getDeliverySourceGoods,
  getDeliverySources,
  recommendDeliverySourceGoods,
  removeDeliverySourceFromGoods,
  updateDeliverySource
} from '../api/autoDelivery.js'
import { getCards } from '../api/cards.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { confirmAction } from '../utils/confirmAction.js'
import { accountName } from '../utils/format.js'

const error = ref('')
const loadError = ref('')
const sourcesAvailable = ref(false)
const success = ref('')
const rows = ref([])
const selected = ref(null)
const editing = ref(null)
const configuredGoods = ref([])
const allGoods = ref([])
const recommendedGoods = ref([])
const goodsAvailable = ref(false)
const goodsLoading = ref(false)
const goodsLoadError = ref('')
const selectedGoodsIds = ref([])
const selectedConfiguredIds = ref([])
const applyTiming = ref('payDelivery')
const goodsKeyword = ref('')
const goodsView = ref('all')
const recommendedHint = ref('点击“分析匹配商品”后，将展示适配度较高的候选商品，并注明使用 AI 或本地规则。')

// 卡密发货相关
const cardGroups = ref([])
const cardGroupsLoading = ref(false)
const contentTextareaRef = ref(null)
const CARD_PLACEHOLDER = '{卡密占位}'

const query = reactive({
  keyword: '',
  current: 1,
  size: 20
})

const form = reactive({
  title: '',
  content: '',
  remark: '',
  deliveryMode: 'text',
  cardGroupId: ''
})

const columns = [
  { key: 'title', title: '货源信息' },
  { key: 'content', title: '正文' },
  { key: 'mode', title: '发货类型' },
  { key: 'stock', title: '库存' },
  { key: 'usage', title: '已配置商品' },
  { key: 'op', title: '操作' }
]

const configuredColumns = [
  { key: 'title', title: '商品' },
  { key: 'bind', title: '状态' },
  { key: 'single', title: '操作' }
]

const goodsColumns = [
  { key: 'title', title: '商品' },
  { key: 'bind', title: '配置状态' },
  { key: 'score', title: '匹配度' },
  { key: 'reason', title: 'AI/规则理由' },
  { key: 'single', title: '操作' }
]

const configuredGoodsIds = computed(() => new Set(configuredGoods.value.map(row => String(row.id))))

const normalizedConfiguredGoods = computed(() => decorateGoodsRows(configuredGoods.value, false))
const normalizedAllGoods = computed(() => decorateGoodsRows(allGoods.value, false))
const normalizedRecommendedGoods = computed(() => decorateGoodsRows(recommendedGoods.value, true))

const filteredConfiguredGoods = computed(() => normalizedConfiguredGoods.value.filter(matchesGoodsKeyword))

const filteredDisplayGoods = computed(() => {
  const rows = goodsView.value === 'recommend' ? normalizedRecommendedGoods.value : normalizedAllGoods.value
  return rows.filter(matchesGoodsKeyword)
})

function matchesGoodsKeyword(row) {
  const keyword = goodsKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return true
  }
  return [row.title, row.category, row.description, row.detailInfo]
    .filter(Boolean)
    .some(value => String(value).toLowerCase().includes(keyword))
}

function decorateGoodsRows(rows, fromAi) {
  return (rows || []).map(row => {
    const configured = configuredGoodsIds.value.has(String(row.id))
    return {
      ...row,
      account: accountOf(row),
      configured,
      confidence: row.confidence ?? null,
      reason: row.reason || (configured ? '该商品已配置当前货源' : (fromAi ? '推荐候选未返回匹配理由' : '可手动配置')),
      recommended: fromAi || Boolean(row.recommended)
    }
  })
}

function accountOf(row) {
  return row?.account || {
    id: row?.accountId,
    avatarUrl: row?.accountAvatarUrl || '',
    nickname: row?.accountNickname || '',
    displayName: row?.accountDisplayName || '',
    accountNote: row?.accountRemark || '',
    externalUid: row?.accountExternalUid || ''
  }
}

function goodsCover(row) {
  return row?.coverPic || row?.imageUrl || ''
}

function accountAvatar(row) {
  return accountOf(row)?.avatarUrl || ''
}

function accountDisplayLabel(row) {
  const account = accountOf(row)
  const id = row?.accountId || account?.id
  const label = accountName(account || {})
  if (!id) {
    return label || '-'
  }
  return `${label || '账号'}（${id}）`
}

async function loadSources() {
  error.value = ''
  loadError.value = ''
  sourcesAvailable.value = false
  try {
    const res = await getDeliverySources(query)
    rows.value = recordsOfOrThrow(res?.data, '货源列表响应格式异常')
    if (selected.value?.id) {
      const latest = rows.value.find(row => String(row.id) === String(selected.value.id))
      if (latest) {
        selected.value = { ...selected.value, ...latest }
      } else {
        clearSelected()
      }
    }
    sourcesAvailable.value = true
  } catch (e) {
    rows.value = []
    clearSelected()
    editing.value = null
    loadError.value = `${e.message || '货源库加载失败'}；数据成功加载前禁止新增、编辑或应用货源。`
  }
}

function openCreate() {
  if (!sourcesAvailable.value) return
  editing.value = {}
  Object.assign(form, {
    title: '',
    content: '',
    remark: '',
    deliveryMode: 'text',
    cardGroupId: ''
  })
  ensureCardGroupsLoaded()
}

function editSource(row) {
  if (!sourcesAvailable.value) return
  editing.value = row
  Object.assign(form, {
    title: row.title || '',
    content: row.content || '',
    remark: row.remark || '',
    deliveryMode: row.deliveryMode === 'card' ? 'card' : 'text',
    cardGroupId: row.cardGroupId ?? ''
  })
  ensureCardGroupsLoaded()
}

function cancelEdit() {
  editing.value = null
}

async function ensureCardGroupsLoaded() {
  if (cardGroups.value.length > 0 || cardGroupsLoading.value) return
  cardGroupsLoading.value = true
  try {
    const res = await getCards({ current: 1, size: 200 })
    cardGroups.value = recordsOfOrThrow(res?.data, '卡密分组响应格式异常')
  } catch (e) {
    cardGroups.value = []
    error.value = `卡密分组加载失败：${e.message || '请稍后重试'}`
  } finally {
    cardGroupsLoading.value = false
  }
}

const selectedCardGroup = computed(() => {
  const id = form.cardGroupId
  if (!id) return null
  return cardGroups.value.find(g => String(g.id) === String(id)) || null
})

const selectedCardRemainCount = computed(() => {
  const group = selectedCardGroup.value
  return group ? (group.remainCount ?? 0) : 0
})

const editingUsageCount = computed(() => {
  if (!editing.value?.id) return 0
  return editing.value.usageCount ?? selected.value?.usageCount ?? 0
})

// 货源板块统计概览
const stats = computed(() => {
  const list = rows.value || []
  const total = list.length
  const cardSources = list.filter(r => r.deliveryMode === 'card').length
  const textSources = list.filter(r => r.deliveryMode === 'text').length
  const totalConfigured = list.reduce((sum, r) => sum + (Number(r.usageCount) || 0), 0)
  const lowStock = list.filter(r => r.deliveryMode === 'card' && (r.cardRemainCount ?? 0) <= 0).length
  return { total, cardSources, textSources, totalConfigured, lowStock }
})

function manageConfiguredGoods() {
  if (!editing.value?.id) return
  const row = rows.value.find(r => String(r.id) === String(editing.value.id))
  if (row) {
    cancelEdit()
    selectSource(row)
    nextTick(() => {
      const el = document.querySelector('[data-source-configured-goods]')
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
}

function onDeliveryModeChange() {
  if (form.deliveryMode === 'card') {
    ensureCardGroupsLoaded()
  } else {
    form.cardGroupId = ''
  }
}

function insertCardPlaceholder() {
  const ta = contentTextareaRef.value
  if (!ta) {
    form.content = (form.content || '') + CARD_PLACEHOLDER
    return
  }
  const start = ta.selectionStart ?? form.content.length
  const end = ta.selectionEnd ?? form.content.length
  const before = (form.content || '').slice(0, start)
  const after = (form.content || '').slice(end)
  form.content = before + CARD_PLACEHOLDER + after
  // 等待 DOM 更新后恢复光标位置到占位符之后
  requestAnimationFrame(() => {
    const pos = (before + CARD_PLACEHOLDER).length
    try {
      ta.focus()
      ta.setSelectionRange(pos, pos)
    } catch {
      // 忽略光标设置失败
    }
  })
}

function clearSelected() {
  selected.value = null
  configuredGoods.value = []
  allGoods.value = []
  recommendedGoods.value = []
  goodsAvailable.value = false
  goodsLoading.value = false
  goodsLoadError.value = ''
  selectedGoodsIds.value = []
  selectedConfiguredIds.value = []
  goodsView.value = 'all'
}

async function saveSource() {
  if (!sourcesAvailable.value) return
  error.value = ''
  success.value = ''
  // 卡密发货模式校验
  if (form.deliveryMode === 'card') {
    if (!form.cardGroupId) {
      error.value = '卡密发货模式下必须选择一个卡密分组'
      return
    }
    if (!(form.content || '').includes(CARD_PLACEHOLDER)) {
      error.value = `卡密发货的正文必须包含 ${CARD_PLACEHOLDER} 占位符，否则无法替换实际卡密`
      return
    }
  }
  try {
    const editingId = editing.value?.id
    const payload = {
      title: form.title,
      content: form.content,
      remark: form.remark,
      deliveryMode: form.deliveryMode,
      cardGroupId: form.deliveryMode === 'card' ? form.cardGroupId : null
    }
    if (editingId) {
      await updateDeliverySource(editingId, payload)
      success.value = '货源已更新'
    } else {
      await createDeliverySource(payload)
      success.value = '货源已新增'
    }
    editing.value = null
    await loadSources()
    if (editingId) {
      await loadSelectedGoods(editingId)
    }
  } catch (e) {
    error.value = e.message || '保存失败'
  }
}

async function removeSource(row) {
  if (!sourcesAvailable.value) return
  if (!await confirmAction({
    title: '确认删除该货源？',
    description: '删除后不会自动解除商品上的既有配置，请确认后继续。',
    dangerous: true,
    confirmText: '删除'
  })) return
  try {
    await deleteDeliverySource(row.id)
    if (selected.value?.id === row.id) {
      clearSelected()
    }
    success.value = '货源已删除'
    await loadSources()
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

async function loadSelectedGoods(sourceId = selected.value?.id) {
  if (!sourceId) return
  goodsAvailable.value = false
  goodsLoading.value = true
  goodsLoadError.value = ''
  try {
    const res = await getDeliverySourceGoods(sourceId)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('货源商品响应格式异常')
    }
    if (!data.source || typeof data.source !== 'object' || Array.isArray(data.source)) {
      throw new Error('货源详情响应格式异常')
    }
    if (!Array.isArray(data.configuredGoods) || !Array.isArray(data.allGoods)) {
      throw new Error('货源商品列表响应格式异常')
    }
    selected.value = { ...(selected.value || {}), ...data.source }
    configuredGoods.value = data.configuredGoods
    allGoods.value = data.allGoods
    goodsAvailable.value = true
    selectedConfiguredIds.value = []
  } catch (loadFailure) {
    configuredGoods.value = []
    allGoods.value = []
    recommendedGoods.value = []
    selectedGoodsIds.value = []
    goodsLoadError.value = `${loadFailure?.message || '货源商品加载失败'}；商品绑定状态确认前禁止配置。`
    throw loadFailure
  } finally {
    goodsLoading.value = false
  }
}

async function selectSource(row) {
  success.value = ''
  error.value = ''
  selected.value = row
  goodsView.value = 'all'
  selectedGoodsIds.value = []
  recommendedGoods.value = []
  try {
    await loadSelectedGoods(row.id)
  } catch (loadFailure) {
    error.value = loadFailure?.message || '货源商品加载失败'
  }
}

async function analyzeSource(row) {
  if (!sourcesAvailable.value) return
  selected.value = row
  error.value = ''
  success.value = ''
  try {
    await loadSelectedGoods(row.id)
    const res = await recommendDeliverySourceGoods(row.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('商品推荐响应格式异常')
    }
    if (!data.source || typeof data.source !== 'object' || Array.isArray(data.source)) {
      throw new Error('推荐结果缺少有效货源详情')
    }
    if (!Array.isArray(data.configuredGoods) || !Array.isArray(data.candidates)) {
      throw new Error('商品推荐列表响应格式异常')
    }
    if (typeof data.aiEnabled !== 'boolean') {
      throw new Error('商品推荐模式响应格式异常')
    }
    selected.value = { ...(selected.value || {}), ...data.source }
    configuredGoods.value = data.configuredGoods
    recommendedGoods.value = data.candidates
    goodsView.value = 'recommend'
    recommendedHint.value = data.message || (data.aiEnabled === true
      ? 'AI 已根据标题、正文和备注给出匹配候选。'
      : 'AI 当前未启用，已使用本地规则给出匹配候选。')
    selectedGoodsIds.value = normalizedRecommendedGoods.value
      .filter(rowItem => !rowItem.configured)
      .map(rowItem => rowItem.id)
    if (!recommendedGoods.value.length) {
      success.value = recommendedHint.value || '暂未匹配到适合的商品'
    }
  } catch (e) {
    recommendedGoods.value = []
    selectedGoodsIds.value = []
    error.value = e.message || '商品匹配分析失败'
  }
}

async function applySelectedGoods() {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value || selectedGoodsIds.value.length === 0) return
  try {
    await applyDeliverySourceToGoods(selected.value.id, {
      goodsIds: selectedGoodsIds.value,
      timing: applyTiming.value
    })
    success.value = `已配置 ${selectedGoodsIds.value.length} 个商品`
    selectedGoodsIds.value = []
  } catch (e) {
    error.value = e.message || '批量配置失败'
    return
  }
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (refreshError) {
    error.value = `配置已提交，但刷新商品绑定状态失败：${refreshError?.message || '请手动刷新'}。`
  }
}

async function applyOne(row) {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  try {
    await applyDeliverySourceToGoods(selected.value.id, {
      goodsIds: [row.id],
      timing: applyTiming.value
    })
    success.value = '已配置到商品'
  } catch (e) {
    error.value = e.message || '配置失败'
    return
  }
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (refreshError) {
    error.value = `配置已提交，但刷新商品绑定状态失败：${refreshError?.message || '请手动刷新'}。`
  }
}

async function removeConfiguredGoods(row) {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  if (!await confirmAction({
    title: '确认删除该已配置商品？',
    description: '删除后将解除该商品与当前货源的绑定关系，该商品的发货配置将被禁用。',
    dangerous: true,
    confirmText: '删除'
  })) return
  try {
    await removeDeliverySourceFromGoods(selected.value.id, row.id)
  } catch (e) {
    error.value = e.message || '删除失败'
    return
  }
  // 无感刷新：本地移除被删商品，不触发整表 loading
  configuredGoods.value = configuredGoods.value.filter(item => String(item.id) !== String(row.id))
  selectedConfiguredIds.value = selectedConfiguredIds.value.filter(id => String(id) !== String(row.id))
  if (typeof selected.value.usageCount === 'number') {
    selected.value = { ...selected.value, usageCount: Math.max(0, selected.value.usageCount - 1) }
  }
  success.value = '已删除已配置商品'
  // 静默同步货源列表计数（不阻塞、不显示 loading）
  loadSources().catch(() => {})
}

async function batchRemoveConfiguredGoods() {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  const ids = [...selectedConfiguredIds.value]
  if (ids.length === 0) return
  if (!await confirmAction({
    title: `确认删除选中的 ${ids.length} 个已配置商品？`,
    description: '删除后将解除这些商品与当前货源的绑定关系，相关商品的发货配置将被禁用。',
    dangerous: true,
    confirmText: '删除'
  })) return
  const sourceId = selected.value.id
  const results = await Promise.allSettled(ids.map(goodsId => removeDeliverySourceFromGoods(sourceId, goodsId)))
  const successIds = new Set()
  let failureCount = 0
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') {
      successIds.add(String(ids[i]))
    } else {
      failureCount += 1
    }
  })
  // 无感刷新：仅移除删除成功的商品
  if (successIds.size > 0) {
    configuredGoods.value = configuredGoods.value.filter(item => !successIds.has(String(item.id)))
    selectedConfiguredIds.value = selectedConfiguredIds.value.filter(id => !successIds.has(String(id)))
    if (typeof selected.value.usageCount === 'number') {
      selected.value = { ...selected.value, usageCount: Math.max(0, selected.value.usageCount - successIds.size) }
    }
  }
  if (failureCount > 0) {
    error.value = `部分删除失败：成功 ${successIds.size} 个，失败 ${failureCount} 个`
  } else {
    success.value = `已删除 ${successIds.size} 个已配置商品`
  }
  // 静默同步货源列表计数
  loadSources().catch(() => {})
}

async function refreshSelectedGoods() {
  error.value = ''
  if (!selected.value?.id) return
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (e) {
    error.value = e.message || '商品列表刷新失败'
  }
}

function showAllGoods() {
  goodsView.value = 'all'
}

function showRecommendedGoods() {
  if (recommendedGoods.value.length) {
    goodsView.value = 'recommend'
    return
  }
  analyzeSource(selected.value)
}

function confidenceLabel(confidence, configured) {
  if (configured) return '已配置'
  if (confidence === 'high') return '高度匹配'
  if (confidence === 'medium') return '中等匹配'
  return '待确认'
}

function confidenceType(confidence, configured) {
  if (configured) return 'green'
  if (confidence === 'high') return 'green'
  if (confidence === 'medium') return 'orange'
  return 'gray'
}

function bindStateLabel(row) {
  return row.configured ? '已配置' : '未配置'
}

function onHeaderAction(event) {
  if (event.detail === 'source-new') openCreate()
  if (event.detail === 'source-refresh') {
    loadSources()
    refreshSelectedGoods()
  }
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  loadSources()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.content-preview {
  max-width: 520px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.strong {
  font-weight: 600;
}

.source-editor-panel:deep(.card-panel) {
  border: 1px solid #edf0f5;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .04);
  padding: 24px 28px 22px;
}

.source-editor-panel:deep(.panel-head) {
  padding-bottom: 18px;
  margin-bottom: 4px;
  border-bottom: 1px solid #f1f3f7;
}

.source-editor-panel:deep(.panel-head h3) {
  font-size: 18px;
  font-weight: 700;
  color: #1a2236;
  letter-spacing: -0.2px;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 40px;
}

.editor-left {
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-width: 0;
}

.editor-right {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #1a2236;
}

.required {
  color: #ef4444;
  margin-right: 4px;
  font-size: 14px;
  line-height: 1;
}

.field-input-wrap {
  position: relative;
}

.field-input {
  width: 100%;
  height: 42px;
  padding: 0 14px;
  padding-right: 56px;
  border: 1px solid #e2e6ed;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  color: #334155;
  transition: border-color .15s, box-shadow .15s;
  box-sizing: border-box;
  outline: none;
}

.field-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}

.field-input::placeholder {
  color: #b0b7c3;
}

select.field-input {
  padding-right: 40px;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 6l3.5 3.5L11.5 6' stroke='%2394a3b8' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  cursor: pointer;
}

.field-textarea {
  width: 100%;
  padding: 12px 14px;
  padding-right: 60px;
  padding-bottom: 28px;
  border: 1px solid #e2e6ed;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  color: #334155;
  line-height: 1.7;
  resize: vertical;
  min-height: 160px;
  transition: border-color .15s, box-shadow .15s;
  box-sizing: border-box;
  outline: none;
  font-family: inherit;
}

.field-textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}

.field-textarea::placeholder {
  color: #b0b7c3;
}

.char-count {
  position: absolute;
  right: 12px;
  bottom: 8px;
  font-size: 12px;
  color: #b0b7c3;
  pointer-events: none;
}

.placeholder-btn {
  margin-left: auto;
  padding: 3px 12px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #3b82f6;
  background: rgba(59, 130, 246, .06);
  color: #3b82f6;
  border-radius: 999px;
  cursor: pointer;
  transition: background .2s, color .2s;
}

.placeholder-btn:hover {
  background: #3b82f6;
  color: #fff;
}

.setting-card {
  border: 1px solid #e2e6ed;
  border-radius: 12px;
  padding: 20px 22px;
  background: #fff;
}

.setting-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a2236;
  margin-bottom: 14px;
}

.mode-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.mode-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border: 1.5px solid #dde1e8;
  border-radius: 10px;
  background: #f7f8fa;
  cursor: pointer;
  transition: all .18s ease;
  min-height: 80px;
}

.mode-card:hover {
  border-color: #bdd4f9;
  background: #f2f6fd;
}

.mode-card.active {
  border-color: #3b82f6;
  background: #f0f4ff;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, .15);
}

.mode-card input[type='radio'] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.mode-card-radio {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border: 2px solid #c5cad3;
  border-radius: 50%;
  transition: all .18s;
  position: relative;
  background: #fff;
}

.mode-card.active .mode-card-radio {
  border-color: #2563eb;
  border-width: 2px;
}

.mode-card.active .mode-card-radio::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2563eb;
}

.mode-card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mode-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}

.mode-card.active .mode-card-title {
  color: #1e40af;
}

.mode-card-desc {
  font-size: 12.5px;
  color: #6b7280;
  line-height: 1.5;
}

.info-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f0f5ff;
  border: 1px solid #dbeafe;
  color: #2563eb;
  font-size: 13px;
  line-height: 1.6;
}

.info-tip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-weight: 700;
  font-size: 11px;
  font-style: normal;
  flex-shrink: 0;
  margin-top: 2px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.info-tip code {
  padding: 1px 5px;
  background: #dbeafe;
  border-radius: 4px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  margin: 0 1px;
}

.card-group-select {
  margin-top: 14px;
}

.stock-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.stock-label-text {
  color: #6b7280;
}

.stock-value-text {
  font-weight: 600;
  color: #16a34a;
}

.stock-value-text.low {
  color: #dc2626;
}

.stock-setting-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.stock-setting-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stock-setting-label {
  font-size: 13px;
  color: #4b5563;
  font-weight: 500;
}

.stock-type-tag {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  align-self: flex-start;
  padding: 8px 18px;
  border-radius: 8px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 14px;
  font-weight: 500;
  min-width: 80px;
}

.stock-type-tag.card-type {
  background: rgba(59, 130, 246, .08);
  color: #2563eb;
}

.stock-setting-hint {
  font-size: 12px;
  color: #b0b7c3;
}

.configured-goods-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.goods-count-text {
  font-size: 18px;
  font-weight: 700;
  color: #22c55e;
}

.goods-count-text.zero {
  color: #b0b7c3;
  font-weight: 500;
}

.manage-goods-btn {
  padding: 6px 16px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #4b5563;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}

.manage-goods-btn:hover {
  border-color: #9ca3af;
  background: #f9fafb;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 0;
}

.save-btn:deep(.app-btn) {
  min-width: 110px !important;
  height: 44px !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 15px !important;
  background: #2563eb !important;
  color: #fff !important;
  border: none !important;
  box-shadow: 0 4px 12px rgba(37, 99, 235, .28) !important;
  padding: 0 24px !important;
  transition: all .15s !important;
}

.save-btn:deep(.app-btn:hover) {
  background: #1d4ed8 !important;
  box-shadow: 0 6px 16px rgba(37, 99, 235, .35) !important;
}

.cancel-btn:deep(.app-btn) {
  min-width: 100px !important;
  height: 44px !important;
  border-radius: 10px !important;
  font-weight: 500 !important;
  font-size: 15px !important;
  border: 1px solid #d1d5db !important;
  background: #fff !important;
  color: #4b5563 !important;
  padding: 0 24px !important;
  box-shadow: none !important;
  transition: all .15s !important;
}

.cancel-btn:deep(.app-btn:hover) {
  border-color: #9ca3af !important;
  background: #f9fafb !important;
  color: #374151 !important;
}

.stock-cell {
  font-weight: 600;
  color: #059669;
}

.stock-cell.low {
  color: #dc2626;
}

.goods-cell {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 260px;
}

.goods-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: cover;
  background: #eef2ff;
  flex-shrink: 0;
}

.goods-thumb.placeholder,
.account-avatar.placeholder {
  background: #eef2ff;
}

.goods-main {
  min-width: 0;
}

.account-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.account-avatar {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  object-fit: cover;
  flex-shrink: 0;
}

.avatar-placeholder {
  position: relative;
}

.avatar-placeholder::before {
  content: '';
  position: absolute;
  inset: 5px;
  border-radius: 999px;
  background: #cbd5e1;
}

.source-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.summary-item {
  position: relative;
  padding: 16px 18px 16px 20px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.summary-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, var(--primary), var(--primary2));
}

.summary-label {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
  font-weight: 500;
}

.summary-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.2;
  word-break: break-all;
}

.source-preview {
  white-space: pre-wrap;
  line-height: 1.7;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  color: #475569;
  font-size: 13px;
  max-height: 160px;
  overflow-y: auto;
}

@media (max-width: 1100px) {
  .editor-layout {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .source-editor-panel :deep(.card-panel-body) {
    padding: 20px;
  }

  .mode-cards {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .mode-cards {
    grid-template-columns: 1fr;
  }
  .stock-setting-row {
    grid-template-columns: 1fr;
  }
}

/* ===== 货源板块：统计概览 ===== */
.source-library-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}

.stat-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: transform .15s ease, box-shadow .15s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(31, 53, 94, .08), 0 12px 32px rgba(31, 53, 94, .10);
}

.stat-icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 20px;
}
.stat-icon-circle.blue { background: #eff6ff; color: #2563eb; }
.stat-icon-circle.orange { background: #fff7ed; color: #ea580c; }
.stat-icon-circle.green { background: #ecfdf5; color: #059669; }
.stat-icon-circle.purple { background: #f5f3ff; color: #7c3aed; }
.stat-icon-circle.red { background: #fef2f2; color: #dc2626; }

.stat-icon-svg {
  font-size: 22px;
  line-height: 1;
}

.stat-info {
  min-width: 0;
  flex: 1;
}

.stat-label {
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.stat-trend {
  font-size: 12px;
  margin-top: 6px;
  font-weight: 500;
}
.stat-trend.muted { color: var(--muted); }
.stat-trend.down { color: var(--red); }

/* ===== 货源列表卡片 ===== */
.source-table-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 18px 22px 22px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.table-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all .15s;
}
.action-btn:hover:not(:disabled) {
  border-color: #bfdbfe;
  background: #f8fbff;
  color: var(--primary);
}
.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.action-btn.primary-action {
  border-color: transparent;
  background: linear-gradient(135deg, var(--primary), var(--primary2));
  color: #fff;
  box-shadow: 0 4px 12px rgba(13, 107, 255, .22);
}
.action-btn.primary-action:hover:not(:disabled) {
  background: linear-gradient(135deg, #0b5fe0, #1f74f0);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(13, 107, 255, .3);
}
.action-btn.icon-only {
  width: 34px;
  padding: 0;
  justify-content: center;
  font-size: 16px;
}
.refresh-icon { display: inline-block; font-size: 15px; }

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.filter-search {
  position: relative;
  flex: 1;
  min-width: 240px;
  max-width: 420px;
}
.search-input {
  width: 100%;
  height: 38px;
  padding: 0 36px 0 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: 14px;
  outline: none;
  transition: border-color .15s, background .15s, box-shadow .15s;
  box-sizing: border-box;
}
.search-input::placeholder { color: #94a3b8; }
.search-input:focus {
  border-color: var(--primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, .1);
}
.search-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  color: #94a3b8;
  pointer-events: none;
}

.btn-query {
  height: 38px;
  padding: 0 18px;
  border-radius: 8px;
  font-weight: 600;
}

.filter-tip {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 14px;
  padding-left: 2px;
}

/* ===== 响应式 ===== */
@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 860px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .table-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .filter-search {
    max-width: none;
  }
}

@media (max-width: 560px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .source-summary {
    grid-template-columns: 1fr;
  }
  .source-table-card {
    padding: 14px;
  }
}
</style>
