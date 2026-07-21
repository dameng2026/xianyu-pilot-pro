<template>
  <div class="m-dsl">
    <div class="m-dsl-stats-grid">
      <div v-for="card in statCards" :key="card.key" class="m-dsl-stat-card">
        <div class="m-dsl-stat-icon" :class="`m-dsl-stat-icon-${card.color}`">
          <MIcon :name="card.icon" :size="20" />
        </div>
        <div class="m-dsl-stat-info">
          <div class="m-dsl-stat-title">{{ card.title }}</div>
          <div class="m-dsl-stat-value">{{ loading ? '—' : card.value }}</div>
          <div class="m-dsl-stat-desc" :class="`m-dsl-stat-desc-${card.color}`">{{ card.desc }}</div>
        </div>
      </div>
    </div>

    <div class="m-dsl-notice">
      <div class="m-dsl-notice-icon">
        <MIcon name="info" :size="16" />
      </div>
      <div class="m-dsl-notice-text">
        <b>卡密发货</b>从卡密分组自动扣减库存；<b>文本发货</b>直接发送固定文案。删除货源不会自动解除商品上的既有配置。
      </div>
    </div>

    <div class="m-dsl-toolbar">
      <div class="m-dsl-search">
        <MIcon name="search" :size="18" class="m-dsl-search-icon" />
        <input
          v-model="searchKeyword"
          type="text"
          class="m-dsl-search-input"
          placeholder="搜索标题 / 备注"
          aria-label="搜索货源"
          @keyup.enter="handleSearch"
          @input="debouncedSearch"
        />
        <button v-if="searchKeyword" class="m-dsl-search-clear" @click="clearSearch" aria-label="清空搜索">
          <MIcon name="x" :size="16" />
        </button>
      </div>
      <button class="m-dsl-btn m-dsl-btn-primary" :disabled="!sourcesAvailable" @click="openCreate">
        <MIcon name="plus" :size="16" />
        <span>新建</span>
      </button>
    </div>

    <div v-if="loading && sources.length === 0" class="m-dsl-skeleton-list">
      <div v-for="i in 4" :key="i" class="m-dsl-skeleton-card">
        <div class="m-dsl-skeleton-line m-dsl-skeleton-title"></div>
        <div class="m-dsl-skeleton-line m-dsl-skeleton-meta"></div>
        <div class="m-dsl-skeleton-line m-dsl-skeleton-content"></div>
        <div class="m-dsl-skeleton-tags">
          <div class="m-dsl-skeleton-tag"></div>
          <div class="m-dsl-skeleton-tag"></div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError" compact title="货源库加载失败" :description="loadError" @retry="loadSources" />

    <div v-else-if="sources.length === 0" class="m-dsl-empty">
      <div class="m-dsl-empty-icon">
        <MIcon name="package" :size="44" />
      </div>
      <div class="m-dsl-empty-text">{{ hasFilter ? '暂无符合条件的货源' : '暂无货源' }}</div>
      <div class="m-dsl-empty-desc">{{ hasFilter ? '请尝试调整搜索关键词' : '点击右上角"新建"创建第一个货源' }}</div>
      <button v-if="hasFilter" class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="clearSearch">清除搜索</button>
      <button v-else class="m-dsl-btn m-dsl-btn-primary m-dsl-btn-sm" :disabled="!sourcesAvailable" @click="openCreate">新建货源</button>
    </div>

    <div v-else class="m-dsl-list">
      <div v-for="src in sources" :key="src.id" class="m-dsl-source-card">
        <div class="m-dsl-source-header">
          <div class="m-dsl-source-icon" :class="src.deliveryMode === 'card' ? 'm-dsl-source-icon-card' : 'm-dsl-source-icon-text'">
            <MIcon :name="src.deliveryMode === 'card' ? 'key' : 'fileText'" :size="18" />
          </div>
          <div class="m-dsl-source-title-wrap">
            <div class="m-dsl-source-title" :title="src.title">{{ src.title || '未命名货源' }}</div>
            <div class="m-dsl-source-tags">
              <span class="m-dsl-tag" :class="src.deliveryMode === 'card' ? 'm-dsl-tag-orange' : 'm-dsl-tag-gray'">
                {{ src.deliveryMode === 'card' ? '卡密发货' : '文本发货' }}
              </span>
              <span v-if="src.fromMall" class="m-dsl-tag m-dsl-tag-purple">商城货源</span>
            </div>
          </div>
        </div>

        <div v-if="src.remark" class="m-dsl-source-remark">{{ src.remark }}</div>

        <div class="m-dsl-source-content">{{ src.content || '暂无正文' }}</div>

        <div class="m-dsl-source-footer">
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">库存</span>
            <span v-if="src.fromMall" class="m-dsl-source-stat-value muted">商城货源</span>
            <span v-else-if="src.deliveryMode === 'card'" class="m-dsl-source-stat-value" :class="{ low: (src.cardRemainCount ?? 0) <= 0 }">
              {{ src.cardRemainCount ?? 0 }}
            </span>
            <span v-else class="m-dsl-source-stat-value muted">文本</span>
          </div>
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">已配置</span>
            <span class="m-dsl-source-stat-value">{{ src.usageCount ?? 0 }} 个商品</span>
          </div>
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">创建</span>
            <span class="m-dsl-source-stat-value muted">{{ formatDate(src.createdAt || src.createTime || src.gmtCreate) }}</span>
          </div>
        </div>

        <div class="m-dsl-source-actions">
          <button
            v-if="src.deliveryMode === 'card' && !src.fromMall && src.cardGroupId"
            class="m-dsl-action-btn"
            @click="viewCardItems(src)"
          >
            <MIcon name="list" :size="14" />
            <span>卡密列表</span>
          </button>
          <button class="m-dsl-action-btn" @click="openEdit(src)">
            <MIcon name="edit" :size="14" />
            <span>编辑</span>
          </button>
          <button class="m-dsl-action-btn m-dsl-action-danger" @click="removeSource(src)">
            <MIcon name="trash" :size="14" />
            <span>删除</span>
          </button>
        </div>
      </div>

      <div v-if="loadingMore" class="m-dsl-loading-more">加载中...</div>
      <div v-else-if="hasMore" class="m-dsl-load-more">
        <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="loadMore">加载更多</button>
      </div>
      <div v-else-if="sources.length > 0" class="m-dsl-no-more">没有更多货源</div>
    </div>

    <div class="m-dsl-safe-bottom"></div>

    <div v-if="showEditor" class="m-dsl-sheet-mask" @click="closeEditor"></div>
    <div v-if="showEditor" class="m-dsl-sheet m-dsl-sheet-open">
      <div class="m-dsl-sheet-header">
        <h3>{{ editingId ? '编辑货源' : '新增货源' }}</h3>
        <button class="m-dsl-sheet-close" @click="closeEditor" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dsl-sheet-body">
        <div v-if="form.fromMall" class="m-dsl-info-tip">
          <MIcon name="info" :size="14" />
          <span>商城货源固定为文本模式，不可切换为卡密发货。可编辑标题、正文、备注。</span>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label"><span class="m-dsl-required">*</span>标题</label>
          <input v-model="form.title" class="m-dsl-input" placeholder="给用户和 AI 模型看的标题" maxlength="50" />
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">
            <span class="m-dsl-required">*</span>正文
            <button
              v-if="form.deliveryMode === 'card' && !form.fromMall"
              type="button"
              class="m-dsl-insert-btn"
              @click="insertCardPlaceholder"
            >+ 插入 {卡密占位}</button>
          </label>
          <textarea
            v-model="form.content"
            rows="5"
            class="m-dsl-textarea"
            :placeholder="form.deliveryMode === 'card' ? '需包含 {卡密占位}，发货时会自动替换为认领到的卡密' : '实际发货文本内容'"
            maxlength="5000"
          ></textarea>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">备注（选填）</label>
          <textarea v-model="form.remark" rows="2" class="m-dsl-textarea" placeholder="可添加备注信息，方便后续管理" maxlength="200"></textarea>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">发送类型</label>
          <div class="m-dsl-seg">
            <button
              type="button"
              class="m-dsl-seg-btn"
              :class="{ active: form.deliveryMode === 'text', disabled: form.fromMall }"
              :disabled="form.fromMall"
              @click="setDeliveryMode('text')"
            >文本发送</button>
            <button
              type="button"
              class="m-dsl-seg-btn"
              :class="{ active: form.deliveryMode === 'card', disabled: form.fromMall }"
              :disabled="form.fromMall"
              @click="setDeliveryMode('card')"
            >卡密发送</button>
          </div>
          <div class="m-dsl-form-hint">
            <MIcon name="info" :size="12" />
            <span v-if="form.fromMall">商城货源固定为文本模式</span>
            <span v-else>卡密发送将在发送时自动替换 {卡密占位} 占位符</span>
          </div>
        </div>

        <div v-if="form.deliveryMode === 'card' && !form.fromMall" class="m-dsl-form-row">
          <label class="m-dsl-form-label"><span class="m-dsl-required">*</span>卡密分组</label>
          <select v-model="form.cardGroupId" class="m-dsl-select">
            <option value="" disabled>请选择卡密分组</option>
            <option v-for="g in cardGroups" :key="g.id" :value="g.id">
              {{ g.groupName }}（余 {{ g.remainCount ?? 0 }} / 共 {{ g.totalCount ?? 0 }}）
            </option>
          </select>
          <div v-if="cardGroupsLoading" class="m-dsl-form-hint">加载中…</div>
          <div v-else-if="cardGroups.length === 0" class="m-dsl-form-hint danger">
            暂无卡密分组，请先到「卡密仓库」创建分组并导入卡密
          </div>
          <div v-else-if="selectedCardGroup" class="m-dsl-form-hint">
            当前剩余 <b :class="{ 'm-dsl-danger': selectedCardRemainCount <= 0 }">{{ selectedCardRemainCount }}</b> 张
          </div>
        </div>
      </div>
      <div class="m-dsl-sheet-footer">
        <button class="m-dsl-btn m-dsl-btn-outline" @click="closeEditor">取消</button>
        <button class="m-dsl-btn m-dsl-btn-primary" :disabled="saving" @click="saveSource">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>

    <div v-if="showCards" class="m-dsl-sheet-mask" @click="closeCards"></div>
    <div v-if="showCards" class="m-dsl-sheet m-dsl-sheet-open" style="max-height: 80vh;">
      <div class="m-dsl-sheet-header">
        <h3>卡密列表</h3>
        <button class="m-dsl-sheet-close" @click="closeCards" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dsl-sheet-body">
        <div v-if="cardsSource" class="m-dsl-cards-header">
          <div class="m-dsl-cards-source-name">{{ cardsSource.title || '未命名货源' }}</div>
          <div class="m-dsl-cards-source-meta">
            分组：{{ cardsSource.cardGroupName || cardsSource.cardGroupId || '-' }} · 剩余 {{ cardsSource.cardRemainCount ?? 0 }}
          </div>
        </div>

        <div v-if="cardsLoading" class="m-dsl-cards-loading">加载中...</div>
        <div v-else-if="cardsError" class="m-dsl-cards-empty">
          <MIcon name="alertCircle" :size="32" />
          <div>{{ cardsError }}</div>
          <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="viewCardItems(cardsSource)">重试</button>
        </div>
        <div v-else-if="cardItems.length === 0" class="m-dsl-cards-empty">
          <MIcon name="list" :size="32" />
          <div>暂无卡密</div>
        </div>
        <div v-else class="m-dsl-cards-list">
          <div v-for="item in cardItems" :key="item.id" class="m-dsl-card-item">
            <div class="m-dsl-card-content">{{ item.content || item.cardKey || item.value || '-' }}</div>
            <span class="m-dsl-card-status" :class="`m-dsl-card-status-${cardStatusType(item.status)}`">
              {{ cardStatusLabel(item.status) }}
            </span>
          </div>
          <div v-if="cardsHasMore" class="m-dsl-cards-more">
            <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" :disabled="cardsLoadingMore" @click="loadMoreCards">
              {{ cardsLoadingMore ? '加载中...' : '加载更多' }}
            </button>
          </div>
          <div v-else class="m-dsl-cards-end">共 {{ cardsTotal }} 条</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import {
  getDeliverySources,
  createDeliverySource,
  updateDeliverySource,
  deleteDeliverySource
} from '../api/autoDelivery.js'
import { getCards, getCardItems } from '../api/cards.js'
import { recordsOfOrThrow, totalOf } from '../utils/apiData.js'
import { confirmAction } from '../utils/confirmAction.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const CARD_PLACEHOLDER = '{卡密占位}'

const loading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const sources = ref([])
const sourcesAvailable = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(false)
const searchKeyword = ref('')
let searchTimer = null

const cardGroups = ref([])
const cardGroupsLoading = ref(false)

const showEditor = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  title: '',
  content: '',
  remark: '',
  deliveryMode: 'text',
  cardGroupId: '',
  fromMall: false
})

const showCards = ref(false)
const cardsSource = ref(null)
const cardItems = ref([])
const cardsLoading = ref(false)
const cardsLoadingMore = ref(false)
const cardsError = ref('')
const cardsTotal = ref(0)
const cardsPage = ref(1)
const cardsPageSize = ref(50)
const cardsHasMore = ref(false)

const hasFilter = computed(() => Boolean(searchKeyword.value))

const cardGroupMap = computed(() => {
  const map = new Map()
  for (const g of cardGroups.value) {
    map.set(String(g.id), g)
  }
  return map
})

const statCards = computed(() => {
  const list = sources.value || []
  const totalCount = list.length
  let availableStock = 0
  let usedStock = 0
  for (const r of list) {
    if (r.deliveryMode === 'card') {
      const remain = Number(r.cardRemainCount ?? 0)
      availableStock += remain
      const group = r.cardGroupId ? cardGroupMap.value.get(String(r.cardGroupId)) : null
      const groupTotal = Number(group?.totalCount ?? r.cardTotalCount ?? 0)
      if (groupTotal > 0) {
        usedStock += Math.max(0, groupTotal - remain)
      }
    }
  }
  const lowStock = list.filter(r => r.deliveryMode === 'card' && (r.cardRemainCount ?? 0) <= 0).length
  return [
    { key: 'total', title: '货源总数', value: totalCount, desc: '全部货源条目', icon: 'package', color: 'blue' },
    { key: 'available', title: '可用库存', value: availableStock, desc: '卡密剩余总数', icon: 'key', color: 'green' },
    { key: 'used', title: '已用库存', value: usedStock, desc: '卡密已消耗', icon: 'shoppingCart', color: 'orange' },
    { key: 'low', title: '库存预警', value: lowStock, desc: lowStock > 0 ? '需补充库存' : '库存充足', icon: 'warning', color: 'red' }
  ]
})

const selectedCardGroup = computed(() => {
  const id = form.cardGroupId
  if (!id) return null
  return cardGroups.value.find(g => String(g.id) === String(id)) || null
})

const selectedCardRemainCount = computed(() => {
  const group = selectedCardGroup.value
  return group ? Number(group.remainCount ?? 0) : 0
})

function formatDate(value) {
  if (!value) return '-'
  const str = String(value).replace('T', ' ')
  return str.slice(0, 10) || '-'
}

function cardStatusLabel(status) {
  const map = { 0: '未使用', 1: '已锁定', 2: '已使用', 3: '已作废', 4: '异常' }
  return map[Number(status)] ?? String(status ?? '-')
}

function cardStatusType(status) {
  const n = Number(status)
  if (n === 0) return 'green'
  if (n === 2) return 'gray'
  if (n === 1) return 'orange'
  return 'red'
}

function showToast(message, isError = false) {
  window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message, isError } }))
}

async function loadCardGroups() {
  if (cardGroups.value.length > 0 || cardGroupsLoading.value) return
  cardGroupsLoading.value = true
  try {
    const res = await getCards({ current: 1, size: 200 })
    cardGroups.value = recordsOfOrThrow(res?.data, '卡密分组响应格式异常')
  } catch (e) {
    cardGroups.value = []
  } finally {
    cardGroupsLoading.value = false
  }
}

async function loadSources(append = false) {
  if (!append) {
    loading.value = true
  } else {
    loadingMore.value = true
  }
  loadError.value = ''
  try {
    const params = {
      current: page.value,
      size: pageSize.value
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await getDeliverySources(params)
    const list = recordsOfOrThrow(res?.data, '货源列表响应格式异常')
    total.value = totalOf(res?.data, list.length)
    if (append) {
      sources.value = [...sources.value, ...list]
    } else {
      sources.value = list
    }
    hasMore.value = sources.value.length < total.value
    sourcesAvailable.value = true
    // 静默加载卡密分组用于统计与表单
    loadCardGroups().catch(() => {})
  } catch (e) {
    if (!append) sources.value = []
    sourcesAvailable.value = false
    loadError.value = e?.message || '货源库加载失败，请稍后重试'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  page.value++
  await loadSources(true)
}

function handleSearch() {
  page.value = 1
  loadSources()
}

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    handleSearch()
  }, 400)
}

function clearSearch() {
  searchKeyword.value = ''
  handleSearch()
}

function openCreate() {
  if (!sourcesAvailable.value) return
  editingId.value = null
  Object.assign(form, {
    title: '',
    content: '',
    remark: '',
    deliveryMode: 'text',
    cardGroupId: '',
    fromMall: false
  })
  showEditor.value = true
  document.body.style.overflow = 'hidden'
  loadCardGroups().catch(() => {})
}

function openEdit(src) {
  if (!sourcesAvailable.value) return
  editingId.value = src.id
  Object.assign(form, {
    title: src.title || '',
    content: src.content || '',
    remark: src.remark || '',
    deliveryMode: src.deliveryMode === 'card' ? 'card' : 'text',
    cardGroupId: src.cardGroupId ?? '',
    fromMall: !!src.fromMall
  })
  showEditor.value = true
  document.body.style.overflow = 'hidden'
  loadCardGroups().catch(() => {})
}

function closeEditor() {
  showEditor.value = false
  editingId.value = null
  saving.value = false
  document.body.style.overflow = ''
}

function setDeliveryMode(mode) {
  if (form.fromMall) return
  form.deliveryMode = mode
  if (mode !== 'card') {
    form.cardGroupId = ''
  }
}

function insertCardPlaceholder() {
  form.content = (form.content || '') + CARD_PLACEHOLDER
}

async function saveSource() {
  if (!sourcesAvailable.value) return
  if (!form.title || !form.title.trim()) {
    showToast('请填写标题', true)
    return
  }
  if (!form.content || !form.content.trim()) {
    showToast('请填写正文', true)
    return
  }
  if (form.deliveryMode === 'card') {
    if (!form.cardGroupId) {
      showToast('卡密发货模式下必须选择一个卡密分组', true)
      return
    }
    if (!form.content.includes(CARD_PLACEHOLDER)) {
      showToast(`卡密发货的正文必须包含 ${CARD_PLACEHOLDER} 占位符`, true)
      return
    }
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content,
      remark: form.remark,
      deliveryMode: form.deliveryMode,
      cardGroupId: form.deliveryMode === 'card' ? form.cardGroupId : null
    }
    if (editingId.value) {
      await updateDeliverySource(editingId.value, payload)
      showToast('货源已更新')
    } else {
      await createDeliverySource(payload)
      showToast('货源已新增')
    }
    closeEditor()
    page.value = 1
    await loadSources()
  } catch (e) {
    showToast(e?.message || '保存失败', true)
  } finally {
    saving.value = false
  }
}

async function removeSource(src) {
  if (!sourcesAvailable.value) return
  const confirmed = await confirmAction({
    title: '确认删除该货源？',
    description: '删除后不会自动解除商品上的既有配置，请确认后继续。',
    dangerous: true,
    confirmText: '删除'
  })
  if (!confirmed) return
  try {
    await deleteDeliverySource(src.id)
    showToast('货源已删除')
    if (cardsSource.value?.id === src.id) {
      closeCards()
    }
    page.value = 1
    await loadSources()
  } catch (e) {
    showToast(e?.message || '删除失败', true)
  }
}

async function viewCardItems(src) {
  if (!src || !src.cardGroupId) return
  cardsSource.value = src
  cardsPage.value = 1
  cardItems.value = []
  cardsError.value = ''
  cardsTotal.value = 0
  cardsHasMore.value = false
  showCards.value = true
  document.body.style.overflow = 'hidden'
  await fetchCardItems()
}

async function fetchCardItems(append = false) {
  const src = cardsSource.value
  if (!src || !src.cardGroupId) return
  if (!append) {
    cardsLoading.value = true
  } else {
    cardsLoadingMore.value = true
  }
  cardsError.value = ''
  try {
    const res = await getCardItems(src.cardGroupId, {
      current: cardsPage.value,
      size: cardsPageSize.value
    })
    const list = recordsOfOrThrow(res?.data, '卡密列表响应格式异常')
    cardsTotal.value = totalOf(res?.data, list.length)
    if (append) {
      cardItems.value = [...cardItems.value, ...list]
    } else {
      cardItems.value = list
    }
    cardsHasMore.value = cardItems.value.length < cardsTotal.value
  } catch (e) {
    if (!append) cardItems.value = []
    cardsError.value = e?.message || '卡密列表加载失败'
  } finally {
    cardsLoading.value = false
    cardsLoadingMore.value = false
  }
}

async function loadMoreCards() {
  if (cardsLoadingMore.value || !cardsHasMore.value) return
  cardsPage.value++
  await fetchCardItems(true)
}

function closeCards() {
  showCards.value = false
  cardsSource.value = null
  cardItems.value = []
  cardsError.value = ''
  document.body.style.overflow = ''
}

onMounted(() => {
  loadSources()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.m-dsl {
  padding: 10px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-dsl-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.m-dsl-stat-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
}

.m-dsl-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dsl-stat-icon-blue {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #2563eb;
}
.m-dsl-stat-icon-green {
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #16a34a;
}
.m-dsl-stat-icon-orange {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #f59e0b;
}
.m-dsl-stat-icon-red {
  background: linear-gradient(135deg, #fee2e2, #fecaca);
  color: #dc2626;
}

.m-dsl-stat-info {
  flex: 1;
  min-width: 0;
}
.m-dsl-stat-title {
  font-size: 12px;
  color: #72809a;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-dsl-stat-value {
  font-size: 22px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-dsl-stat-desc {
  font-size: 11px;
  font-weight: 500;
  margin-top: 2px;
}
.m-dsl-stat-desc-blue { color: #2563eb; }
.m-dsl-stat-desc-green { color: #16a34a; }
.m-dsl-stat-desc-orange { color: #f59e0b; }
.m-dsl-stat-desc-red { color: #dc2626; }

.m-dsl-notice {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}
.m-dsl-notice-icon {
  color: #f59e0b;
  flex-shrink: 0;
  margin-top: 1px;
}
.m-dsl-notice-text {
  font-size: 12px;
  color: #92400e;
  line-height: 1.6;
  flex: 1;
}
.m-dsl-notice-text b {
  font-weight: 600;
}

.m-dsl-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.m-dsl-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #e7edf7;
  border-radius: 12px;
  padding: 0 14px;
  height: 44px;
  min-width: 0;
}
.m-dsl-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
}
.m-dsl-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  color: #15213d;
  background: transparent;
  min-width: 0;
}
.m-dsl-search-input::placeholder {
  color: #b0bacb;
}
.m-dsl-search-clear {
  width: 28px;
  height: 28px;
  border: none;
  background: #f0f4fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8c98ae;
  cursor: pointer;
  flex-shrink: 0;
}

.m-dsl-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  padding: 10px 16px;
  min-height: 40px;
}
.m-dsl-btn:active { transform: scale(0.97); }
.m-dsl-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-dsl-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-dsl-btn-outline {
  background: white;
  color: #5a6a85;
  border: 1px solid #e7edf7;
}
.m-dsl-btn-sm {
  padding: 8px 14px;
  font-size: 12px;
  min-height: 36px;
}

.m-dsl-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-dsl-skeleton-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  border: 1px solid #f0f4fa;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.m-dsl-skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-dsl-skeleton 1.5s infinite;
}
.m-dsl-skeleton-title { width: 60%; height: 18px; }
.m-dsl-skeleton-meta { width: 40%; height: 12px; }
.m-dsl-skeleton-content { width: 90%; height: 12px; }
.m-dsl-skeleton-tags { display: flex; gap: 8px; }
.m-dsl-skeleton-tag {
  width: 70px;
  height: 20px;
  border-radius: 100px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-dsl-skeleton 1.5s infinite;
}
@keyframes m-dsl-skeleton {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-dsl-empty {
  text-align: center;
  padding: 50px 20px;
}
.m-dsl-empty-icon {
  width: 76px;
  height: 76px;
  margin: 0 auto 14px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-dsl-empty-text {
  font-size: 15px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 6px;
}
.m-dsl-empty-desc {
  font-size: 13px;
  color: #8c98ae;
  margin-bottom: 18px;
}

.m-dsl-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-dsl-source-card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 4px 14px rgba(31, 53, 94, 0.04);
  border: 1px solid #edf1f5;
}

.m-dsl-source-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}
.m-dsl-source-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dsl-source-icon-card {
  background: rgba(255, 159, 34, 0.12);
  color: #ff9f22;
}
.m-dsl-source-icon-text {
  background: rgba(13, 107, 255, 0.1);
  color: #0d6bff;
}
.m-dsl-source-title-wrap {
  flex: 1;
  min-width: 0;
}
.m-dsl-source-title {
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.m-dsl-source-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 6px;
}
.m-dsl-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 100px;
  white-space: nowrap;
}
.m-dsl-tag-gray {
  background: rgba(140, 152, 174, 0.12);
  color: #7f8a9d;
}
.m-dsl-tag-orange {
  background: rgba(255, 159, 34, 0.12);
  color: #ff9f22;
}
.m-dsl-tag-purple {
  background: rgba(145, 88, 255, 0.1);
  color: #9158ff;
}

.m-dsl-source-remark {
  font-size: 12px;
  color: #8c98ae;
  margin-bottom: 6px;
  line-height: 1.5;
}

.m-dsl-source-content {
  font-size: 13px;
  color: #5a6a85;
  line-height: 1.6;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  margin-bottom: 10px;
  max-height: 100px;
  overflow-y: auto;
  word-break: break-all;
  white-space: pre-wrap;
}

.m-dsl-source-footer {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid #f0f4fa;
  margin-bottom: 10px;
}
.m-dsl-source-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.m-dsl-source-stat-label {
  font-size: 11px;
  color: #8c98ae;
  white-space: nowrap;
}
.m-dsl-source-stat-value {
  font-size: 13px;
  font-weight: 700;
  color: #15213d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-dsl-source-stat-value.muted {
  color: #8c98ae;
  font-weight: 500;
}
.m-dsl-source-stat-value.low {
  color: #dc2626;
}

.m-dsl-source-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.m-dsl-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 12px;
  border: 1px solid #e7edf7;
  background: white;
  border-radius: 8px;
  color: #5a6a85;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.m-dsl-action-btn:active {
  transform: scale(0.97);
  background: #f5f7fb;
}
.m-dsl-action-danger {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}
.m-dsl-action-danger:active {
  background: rgba(239, 68, 68, 0.05);
}

.m-dsl-loading-more,
.m-dsl-load-more,
.m-dsl-no-more {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #8c98ae;
}

.m-dsl-safe-bottom {
  height: calc(84px + env(safe-area-inset-bottom));
}

.m-dsl-sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 25, 50, 0.4);
  z-index: 200;
  backdrop-filter: blur(2px);
}

.m-dsl-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: white;
  border-radius: 20px 20px 0 0;
  z-index: 201;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.m-dsl-sheet-open {
  transform: translateY(0);
}
.m-dsl-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f4fa;
  flex-shrink: 0;
}
.m-dsl-sheet-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-dsl-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: #f5f7fb;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5a6a85;
  cursor: pointer;
  flex-shrink: 0;
}
.m-dsl-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.m-dsl-info-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 16px;
}
.m-dsl-info-tip svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.m-dsl-form-row {
  margin-bottom: 16px;
}
.m-dsl-form-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 8px;
}
.m-dsl-required {
  color: #ef4444;
}
.m-dsl-input {
  width: 100%;
  height: 44px;
  border: 1px solid #e7edf7;
  border-radius: 10px;
  padding: 0 14px;
  font-size: 14px;
  color: #15213d;
  background: white;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.m-dsl-input:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1);
}
.m-dsl-textarea {
  width: 100%;
  border: 1px solid #e7edf7;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 14px;
  color: #15213d;
  background: white;
  line-height: 1.6;
  resize: vertical;
  min-height: 100px;
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.m-dsl-textarea:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1);
}
.m-dsl-textarea::placeholder {
  color: #b0bacb;
}
.m-dsl-insert-btn {
  margin-left: auto;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #0d6bff;
  background: rgba(13, 107, 255, 0.06);
  color: #0d6bff;
  border-radius: 999px;
  cursor: pointer;
}
.m-dsl-insert-btn:active {
  background: #0d6bff;
  color: white;
}

.m-dsl-seg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.m-dsl-seg-btn {
  height: 44px;
  border: 1px solid #e7edf7;
  background: white;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #5a6a85;
  cursor: pointer;
  transition: all 0.15s;
}
.m-dsl-seg-btn:active {
  background: #f5f7fb;
}
.m-dsl-seg-btn.active {
  border-color: #0d6bff;
  background: #eef4ff;
  color: #0d6bff;
}
.m-dsl-seg-btn.disabled,
.m-dsl-seg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-dsl-form-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #8c98ae;
  line-height: 1.5;
}
.m-dsl-form-hint.danger {
  color: #dc2626;
}
.m-dsl-form-hint b {
  color: #15213d;
  font-weight: 700;
}
.m-dsl-form-hint b.m-dsl-danger {
  color: #dc2626;
}

.m-dsl-select {
  width: 100%;
  height: 44px;
  border: 1px solid #e7edf7;
  border-radius: 10px;
  padding: 0 14px;
  font-size: 14px;
  color: #15213d;
  background: white;
  outline: none;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 6l3.5 3.5L11.5 6' stroke='%2394a3b8' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  cursor: pointer;
}

.m-dsl-sheet-footer {
  display: flex;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid #f0f4fa;
  flex-shrink: 0;
}
.m-dsl-sheet-footer .m-dsl-btn {
  flex: 1;
}

.m-dsl-cards-header {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f5f7fb;
  margin-bottom: 12px;
}
.m-dsl-cards-source-name {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 4px;
}
.m-dsl-cards-source-meta {
  font-size: 12px;
  color: #8c98ae;
}

.m-dsl-cards-loading,
.m-dsl-cards-empty {
  text-align: center;
  padding: 40px 20px;
  color: #8c98ae;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.m-dsl-cards-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.m-dsl-card-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #edf1f5;
  border-radius: 10px;
  background: white;
}
.m-dsl-card-content {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #15213d;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  word-break: break-all;
  line-height: 1.5;
}
.m-dsl-card-status {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
  white-space: nowrap;
  flex-shrink: 0;
}
.m-dsl-card-status-green {
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
}
.m-dsl-card-status-gray {
  background: rgba(140, 152, 174, 0.12);
  color: #7f8a9d;
}
.m-dsl-card-status-orange {
  background: rgba(255, 159, 34, 0.12);
  color: #ff9f22;
}
.m-dsl-card-status-red {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.m-dsl-cards-more {
  text-align: center;
  padding: 12px 0;
}
.m-dsl-cards-end {
  text-align: center;
  padding: 12px 0;
  font-size: 12px;
  color: #b0bacb;
}

@media (max-width: 360px) {
  .m-dsl { padding: 10px 12px 0; }
  .m-dsl-stats-grid { gap: 8px; }
  .m-dsl-stat-card { padding: 12px; gap: 10px; }
  .m-dsl-stat-icon { width: 40px; height: 40px; }
  .m-dsl-stat-value { font-size: 20px; }
  .m-dsl-source-footer { gap: 6px; }
  .m-dsl-source-stat-value { font-size: 12px; }
}

@media (min-width: 430px) {
  .m-dsl-stats-grid { gap: 12px; }
  .m-dsl-stat-card { padding: 16px; }
}
</style>
