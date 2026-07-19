<template>
  <div class="workflow-drafts-page">
    <div v-if="globalError" class="global-notice error">{{ globalError }}</div>

    <!-- 顶部统计卡片 -->
    <div class="grid stat-grid">
      <StatCard title="草稿总数" :value="metricText(stats.total)" :change="statsError ? '统计不可用' : '全量草稿'" icon="document" />
      <StatCard title="待发布" :value="metricText(stats.draft)" :change="statsError ? '统计不可用' : '尚未发布'" icon="clock" color="blue" />
      <StatCard title="已发布" :value="metricText(stats.published)" :change="statsError ? '统计不可用' : '发布成功'" icon="success" color="green" />
      <StatCard title="发布失败" :value="metricText(stats.failed)" :change="statsError ? '统计不可用' : '可重试'" icon="warning" color="red" />
    </div>

    <CardPanel title="商品草稿箱" desc="工作流生成的商品草稿与发布记录，支持按状态、关键词筛选；失败草稿可重试发布">
      <!-- 筛选区 -->
      <div class="toolbar filter-bar">
        <div class="filter-chip-group">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            type="button"
            class="filter-chip"
            :class="{ active: filters.status === opt.value }"
            @click="filters.status = opt.value; onSearch()"
          >
            <span class="chip-dot" :class="opt.dot" />
            {{ opt.label }}
          </button>
        </div>
        <div class="filter-divider" />
        <input
          v-model="filters.keyword"
          class="input"
          style="flex:1;min-width:200px"
          placeholder="搜索商品标题或描述"
          @keyup.enter="onSearch"
        />
        <AppButton type="primary" :loading="loading" @click="onSearch">查询</AppButton>
        <AppButton :loading="loading" @click="onRefresh">刷新</AppButton>
      </div>

      <!-- 三态：加载中 -->
      <div v-if="loading" class="loading-wrap">
        <div class="spinner"></div>
        <p class="subtle">正在加载草稿列表...</p>
      </div>

      <!-- 三态：加载错误 -->
      <EmptyState
        v-else-if="loadError"
        variant="error"
        title="草稿列表加载失败"
        :description="loadError"
      >
        <template #actions>
          <AppButton type="primary" @click="load">重新加载</AppButton>
        </template>
      </EmptyState>

      <!-- 三态：空数据 -->
      <EmptyState
        v-else-if="!records.length"
        icon="📦"
        title="暂无商品草稿"
        description="工作流 PUBLISH 节点产出的商品会自动保存到这里，无论发布成功或失败都会保留记录。运行一次带 PUBLISH 节点的工作流后即可看到草稿。"
      />

      <!-- 草稿网格 - 与生图记录页风格对齐 -->
      <div v-else class="draft-grid">
        <article
          v-for="r in records"
          :key="r.id"
          class="draft-card"
          :class="`is-${r.publish_status || 'draft'}`"
          @click="openDetail(r)"
        >
          <!-- 顶部状态条 -->
          <div class="card-status-bar" :class="`bar-${r.publish_status || 'draft'}`" />

          <!-- 缩略图区 -->
          <div class="draft-thumb">
            <img
              v-if="r.cover_pic"
              :src="r.cover_pic"
              :alt="r.title || '商品草稿'"
              loading="lazy"
              @error="onImageError($event, r)"
            />
            <div v-else class="draft-thumb-placeholder">
              <div class="placeholder-icon-wrap">
                <Icon name="image" />
              </div>
              <span>暂无封面</span>
            </div>
            <!-- 价格角标 -->
            <div v-if="r.price" class="price-badge">
              <span class="price-symbol">¥</span>
              <span class="price-value">{{ r.price }}</span>
            </div>
            <!-- 多图指示 -->
            <div v-if="imageCount(r) > 1" class="img-count-badge">
              <Icon name="image" />
              <span>{{ imageCount(r) }}</span>
            </div>
            <!-- hover 提示 -->
            <div class="thumb-overlay">
              <div class="overlay-bottom">
                <span class="view-hint">
                  <Icon name="search" />
                  <span>查看详情</span>
                </span>
              </div>
            </div>
          </div>

          <!-- 信息区 -->
          <div class="draft-info">
            <!-- 第一行：状态 pill + 工作流标签 -->
            <div class="info-row info-row-badges">
              <span class="status-pill" :class="pillClass(r.publish_status)">
                <span class="pill-dot" />
                {{ statusText(r.publish_status) }}
              </span>
              <span v-if="r.workflow_name" class="workflow-tag" :title="r.workflow_name">
                {{ truncate(r.workflow_name, 14) }}
              </span>
            </div>

            <!-- 第二行：标题 -->
            <p class="draft-title" :title="r.title || ''">{{ r.title || '未命名商品' }}</p>

            <!-- 第三行：描述 -->
            <p class="draft-desc" :title="r.description || ''">{{ r.description || '—' }}</p>

            <!-- 第四行：分类 + 创建时间 -->
            <div class="info-row info-row-meta">
              <span v-if="r.category" class="meta-category">{{ r.category }}</span>
              <span class="meta-time">
                <Icon name="clock" />
                <span>{{ formatTime(r.created_time) }}</span>
              </span>
            </div>

            <!-- 失败错误信息 -->
            <div v-if="r.publish_status === 'failed' && r.publish_error_message" class="draft-error" :title="r.publish_error_message">
              <Icon name="warning" />
              <span>{{ truncate(r.publish_error_message, 50) }}</span>
            </div>

            <!-- 已发布标识 -->
            <div v-if="r.publish_status === 'published' && r.xianyu_goods_id" class="draft-published-info">
              <Icon name="success" />
              <span>闲鱼 ID: {{ truncate(r.xianyu_goods_id, 18) }}</span>
            </div>
          </div>
        </article>
      </div>

      <!-- 分页 -->
      <Pagination
        v-if="!loading && !loadError && records.length"
        :total="total"
        :current="page"
        :page-size="pageSize"
        :sizes="[12, 24, 48]"
        @page-change="goPage"
        @size-change="onSizeChange"
      />
    </CardPanel>

    <!-- 详情弹窗 -->
    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-body">
        <button class="modal-close" title="关闭" @click="closeDetail"><Icon name="close" /></button>
        <div class="modal-grid">
          <!-- 左侧图片区 -->
          <div class="modal-image-area">
            <div class="main-image-wrap">
              <template v-if="currentImage">
                <img
                  class="modal-main-image"
                  :src="currentImage"
                  :alt="detail.title || '商品草稿'"
                />
                <a
                  v-if="currentImage"
                  class="download-btn"
                  :href="currentImage"
                  target="_blank"
                  rel="noopener noreferrer"
                  download
                  title="新窗口打开原图"
                >
                  <Icon name="download" />
                </a>
                <div v-if="parsedImages.length > 1" class="image-index">
                  {{ currentIndex + 1 }} / {{ parsedImages.length }}
                </div>
              </template>
              <div v-else class="image-error large">
                <div class="error-icon-wrap">
                  <Icon name="image" />
                </div>
                <span>该草稿没有封面图</span>
              </div>
            </div>

            <!-- 缩略图列表（多图时可切换） -->
            <div v-if="parsedImages.length > 1" class="thumb-strip">
              <button
                v-for="(img, idx) in parsedImages"
                :key="idx"
                type="button"
                class="thumb-item"
                :class="{ active: idx === currentIndex }"
                @click="currentIndex = idx"
              >
                <img :src="img" :alt="`image-${idx + 1}`" loading="lazy" />
              </button>
            </div>
          </div>

          <!-- 右侧信息区 -->
          <div class="modal-info">
            <div class="modal-header">
              <h2 class="modal-title">{{ detail.title || '未命名商品' }}</h2>
              <div class="modal-header-badges">
                <span class="status-pill" :class="pillClass(detail.publish_status)">
                  <span class="pill-dot" />
                  {{ statusText(detail.publish_status) }}
                </span>
              </div>
            </div>

            <!-- 关键信息卡片 -->
            <div class="info-cards">
              <div class="info-card">
                <span class="info-card-label">价格</span>
                <span class="info-card-value price-text">¥{{ detail.price || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">分类</span>
                <span class="info-card-value">{{ detail.category || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">库存</span>
                <span class="info-card-value">{{ detail.stock ?? '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">图片数</span>
                <span class="info-card-value">{{ parsedImages.length }}</span>
              </div>
            </div>

            <!-- 详细字段表格 -->
            <details class="detail-collapse" open>
              <summary>完整字段</summary>
              <div class="info-grid">
                <div><span>工作流</span><b>{{ detail.workflow_name || '—' }}</b></div>
                <div><span>节点 Key</span><b class="mono">{{ detail.node_key || '—' }}</b></div>
                <div><span>账号 ID</span><b>{{ detail.account_id || '—' }}</b></div>
                <div><span>工作流 ID</span><b>{{ detail.workflow_id || '—' }}</b></div>
                <div><span>执行 ID</span><b>{{ detail.workflow_execution_id || '—' }}</b></div>
                <div><span>草稿 ID</span><b class="mono">{{ detail.id }}</b></div>
                <div><span>创建时间</span><b>{{ formatTime(detail.created_time) }}</b></div>
                <div><span>更新时间</span><b>{{ formatTime(detail.updated_time) }}</b></div>
                <div v-if="detail.publish_time"><span>发布时间</span><b>{{ formatTime(detail.publish_time) }}</b></div>
                <div v-if="detail.xianyu_goods_id"><span>闲鱼商品 ID</span><b class="mono">{{ detail.xianyu_goods_id }}</b></div>
                <div v-if="detail.publish_attempt_count"><span>发布尝试</span><b>{{ detail.publish_attempt_count }} 次</b></div>
                <div v-if="detail.source_item_id"><span>源商品 ID</span><b class="mono">{{ truncate(detail.source_item_id, 24) }}</b></div>
              </div>
            </details>

            <!-- 商品描述 -->
            <h3 v-if="detail.description" class="section-subtitle">
              <Icon name="message" />
              <span>商品描述</span>
              <button v-if="detail.description" type="button" class="copy-btn" @click="copyDescription">
                <Icon name="copy" />
                <span>{{ copied ? '已复制' : '复制' }}</span>
              </button>
            </h3>
            <pre v-if="detail.description" class="prompt-text">{{ detail.description }}</pre>

            <div v-if="detail.publish_error_message" class="error-block">
              <h3 class="section-subtitle">
                <Icon name="warning" />
                <span>发布失败原因</span>
              </h3>
              <pre class="prompt-text error">{{ detail.publish_error_message }}</pre>
            </div>

            <!-- 重试发布账号选择器（仅在可重试时显示） -->
            <div v-if="canRetry(detail.publish_status)" class="retry-account-picker">
              <label class="picker-label">
                <Icon name="user" />
                <span>发布账号</span>
              </label>
              <select v-model="retryAccountId" class="picker-select" :disabled="retrying || batchRetrying">
                <option :value="null">使用草稿原账号（{{ detail.account_id || '未绑定' }}）</option>
                <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                  {{ accountDisplayName(acc) }}（ID: {{ acc.id }}）
                </option>
              </select>
              <p class="picker-hint">
                选择账号后点击「重试发布」将使用该账号重新发布商品；不选择则回退到草稿原账号。
              </p>
            </div>

            <div class="modal-actions">
              <AppButton
                v-if="canRetry(detail.publish_status)"
                type="primary"
                :loading="retrying"
                @click="retryPublish"
              >重试发布</AppButton>
              <AppButton
                v-if="canRetry(detail.publish_status)"
                type="ghost"
                :loading="batchRetrying"
                @click="batchRetryFromDetail"
              >批量重试当前筛选</AppButton>
              <AppButton type="danger" :loading="deleting" @click="onDelete">删除草稿</AppButton>
              <AppButton @click="closeDetail">关闭</AppButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import Pagination from '../components/Pagination.vue'
import { globalConfirm } from '../composables/confirmState.js'
import { getLiteAccounts } from '../api/accounts.js'
import { accountName } from '../utils/format.js'
import {
  listWorkflowDrafts,
  getWorkflowDraftStats,
  getWorkflowDraft,
  retryPublishDraft,
  batchRetryPublishDrafts,
  deleteWorkflowDraft
} from '../api/workflowDrafts.js'

const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)
const loading = ref(false)
const loadError = ref('')
const globalError = ref('')

const filters = ref({ status: 'all', keyword: '' })

const stats = ref({ total: null, draft: null, published: null, failed: null })
const statsError = ref('')

const detail = ref(null)
const retrying = ref(false)
const batchRetrying = ref(false)
const deleting = ref(false)
const currentIndex = ref(0)
const copied = ref(false)

// 账号列表（用于重试发布时选择账号）
const accounts = ref([])
const retryAccountId = ref(null) // null 表示使用草稿原账号

function accountDisplayName(acc) {
  if (!acc) return '未知账号'
  return accountName(acc)
}

async function loadAccounts() {
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    const data = res && res.data
    const list = Array.isArray(data) ? data : (data?.records || data?.accounts || data?.list || data?.rows || [])
    accounts.value = Array.isArray(list) ? list : []
  } catch (e) {
    accounts.value = []
  }
}

const statusOptions = [
  { value: 'all', label: '全部', dot: 'dot-all' },
  { value: 'draft', label: '待发布', dot: 'dot-draft' },
  { value: 'publishing', label: '发布中', dot: 'dot-publishing' },
  { value: 'published', label: '已发布', dot: 'dot-published' },
  { value: 'failed', label: '失败', dot: 'dot-failed' }
]

const parsedImages = computed(() => {
  if (!detail.value) return []
  const raw = detail.value.image_urls
  if (Array.isArray(raw)) return raw.filter(Boolean)
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.filter(Boolean) : []
    } catch {
      return []
    }
  }
  return []
})

const currentImage = computed(() => parsedImages.value[currentIndex.value] || detail.value?.cover_pic || '')

watch(detail, () => { currentIndex.value = 0 })

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function statusText(s) {
  return ({
    draft: '待发布',
    publishing: '发布中',
    published: '已发布',
    failed: '发布失败'
  })[s] || s || '—'
}

function pillClass(s) {
  return ({
    draft: 'pill-draft',
    publishing: 'pill-publishing',
    published: 'pill-published',
    failed: 'pill-fail'
  })[s] || 'pill-draft'
}

function canRetry(s) {
  return s === 'draft' || s === 'failed'
}

function truncate(text, max) {
  const s = String(text || '')
  return s.length > max ? s.slice(0, max) + '…' : s
}

function formatTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').replace(/\.\d+$/, '').slice(0, 19)
}

function imageCount(record) {
  if (!record) return 0
  const raw = record.image_urls
  if (Array.isArray(raw)) return raw.filter(Boolean).length
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.filter(Boolean).length : 0
    } catch {
      return 0
    }
  }
  return 0
}

function onImageError(event, record) {
  if (event && event.target) {
    event.target.style.opacity = '0.15'
  }
}

function extractListData(res) {
  const data = res && res.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('草稿列表响应格式异常')
  }
  if (!Array.isArray(data.records)) throw new Error('草稿列表字段缺失')
  const totalValue = Number(data.total)
  return {
    records: data.records,
    total: Number.isFinite(totalValue) && totalValue >= 0 ? totalValue : data.records.length,
    page: Number(data.page) || 1,
    pageSize: Number(data.pageSize) || pageSize.value
  }
}

async function load() {
  loading.value = true
  loadError.value = ''
  globalError.value = ''
  try {
    const params = {
      page: page.value,
      pageSize: pageSize.value,
      status: filters.value.status || 'all',
      keyword: filters.value.keyword || ''
    }
    const res = await listWorkflowDrafts(params)
    const data = extractListData(res)
    records.value = data.records
    total.value = data.total
    page.value = data.page
  } catch (e) {
    records.value = []
    total.value = 0
    loadError.value = (e && e.message) || '草稿列表加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsError.value = ''
  try {
    const res = await getWorkflowDraftStats()
    const data = res && res.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('草稿统计响应格式异常')
    }
    stats.value = {
      total: Number(data.total) || 0,
      draft: Number(data.draft) || 0,
      published: Number(data.published) || 0,
      failed: Number(data.failed) || 0
    }
  } catch (e) {
    stats.value = { total: null, draft: null, published: null, failed: null }
    statsError.value = (e && e.message) || '草稿统计加载失败'
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onRefresh() {
  load()
  loadStats()
}

function goPage(p) {
  if (p < 1 || loading.value) return
  page.value = p
  load()
}

function onSizeChange(size) {
  pageSize.value = Number(size) || 12
  page.value = 1
  load()
}

function openDetail(record) {
  detail.value = record
  // 打开详情时重置账号选择为草稿原账号
  retryAccountId.value = null
}

function closeDetail() {
  detail.value = null
  copied.value = false
  retryAccountId.value = null
}

async function refreshDetail(draftId) {
  try {
    const res = await getWorkflowDraft(draftId)
    const data = res && res.data
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      detail.value = data
    }
  } catch (e) {
    // 详情刷新失败时保持当前详情，不阻塞主流程
  }
}

async function copyDescription() {
  if (!detail.value || !detail.value.description) return
  try {
    await navigator.clipboard.writeText(detail.value.description)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = detail.value.description
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy'); copied.value = true; setTimeout(() => { copied.value = false }, 2000) } catch {}
    document.body.removeChild(ta)
  }
}

async function retryPublish() {
  if (!detail.value || retrying.value) return
  globalError.value = ''
  retrying.value = true
  try {
    const res = await retryPublishDraft(detail.value.id, retryAccountId.value)
    const data = res && res.data
    if (data && data.success === false) {
      globalError.value = data.error || '重试发布失败，请稍后重试'
    }
    await Promise.all([load(), loadStats()])
    await refreshDetail(detail.value.id)
    if (!globalError.value) {
      const accountMsg = retryAccountId.value
        ? `（使用账号 ${retryAccountId.value}）`
        : ''
      window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: `重试发布已触发${accountMsg}，请稍后查看发布结果`, type: 'success' } }))
    }
  } catch (e) {
    globalError.value = (e && e.message) || '重试发布失败，请稍后重试。'
  } finally {
    retrying.value = false
  }
}

async function batchRetryFromDetail() {
  if (!detail.value || batchRetrying.value) return
  const failedIds = records.value
    .filter(r => canRetry(r.publish_status))
    .map(r => r.id)
  if (!failedIds.length) {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '当前列表没有可重试的草稿', type: 'info' } }))
    return
  }
  const accountMsg = retryAccountId.value
    ? `（使用账号 ${retryAccountId.value}）`
    : '（使用各草稿原账号）'
  const confirmed = await globalConfirm.confirm(
    '批量重试发布',
    `将重试当前列表中的 ${failedIds.length} 条草稿${accountMsg}，是否继续？`,
    '立即重试'
  )
  if (!confirmed) return
  globalError.value = ''
  batchRetrying.value = true
  try {
    const res = await batchRetryPublishDrafts(failedIds, retryAccountId.value)
    const data = res && res.data
    const succ = Number(data?.success) || 0
    const fail = Number(data?.failed) || 0
    await Promise.all([load(), loadStats()])
    if (detail.value) await refreshDetail(detail.value.id)
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: {
        message: `批量重试完成：成功 ${succ} 条，失败 ${fail} 条${accountMsg}`,
        type: fail > 0 ? 'warn' : 'success'
      }
    }))
  } catch (e) {
    globalError.value = (e && e.message) || '批量重试失败，请稍后重试。'
  } finally {
    batchRetrying.value = false
  }
}

async function onDelete() {
  if (!detail.value || deleting.value) return
  const confirmed = await globalConfirm.confirm(
    '删除草稿',
    `确定删除草稿「${detail.value.title || detail.value.id}」吗？此操作不可恢复。`,
    '删除',
    true
  )
  if (!confirmed) return
  globalError.value = ''
  deleting.value = true
  try {
    await deleteWorkflowDraft(detail.value.id)
    detail.value = null
    await Promise.all([load(), loadStats()])
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '草稿已删除', type: 'success' } }))
  } catch (e) {
    globalError.value = (e && e.message) || '删除失败，请稍后重试。'
  } finally {
    deleting.value = false
  }
}

function onHeaderAction(event) {
  if (event.detail === 'workflow-drafts-refresh') {
    load()
    loadStats()
  }
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  load()
  loadStats()
  loadAccounts()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.workflow-drafts-page {
  display: block;
}

/* === 筛选区 === */
.filter-bar {
  margin-bottom: 18px;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.filter-chip-group {
  display: inline-flex;
  background: #f4f6fa;
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}
.filter-chip {
  border: none;
  background: transparent;
  color: #5a6880;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.18s ease;
}
.filter-chip:hover { color: #13213d; }
.filter-chip.active {
  background: #fff;
  color: #0d6bff;
  box-shadow: 0 1px 3px rgba(31, 53, 94, 0.08);
}
.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #98a2b3;
}
.chip-dot.dot-all { background: linear-gradient(135deg, #0d6bff, #16bf78); }
.chip-dot.dot-draft { background: #98a2b3; }
.chip-dot.dot-publishing { background: #0d6bff; }
.chip-dot.dot-published { background: #16bf78; }
.chip-dot.dot-failed { background: #ff5b61; }
.filter-divider {
  width: 1px;
  height: 22px;
  background: #e7edf7;
  margin: 0 4px;
}

/* === 加载态 === */
.loading-wrap {
  padding: 80px 0;
  text-align: center;
}
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #eef3fa;
  border-top-color: #0d6bff;
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: wd-spin 0.8s linear infinite;
}
@keyframes wd-spin { to { transform: rotate(360deg); } }
.subtle {
  color: #7a879e;
  font-size: 13px;
  margin: 0;
}

/* === 草稿网格 === */
.draft-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
  margin-top: 4px;
}

/* === 草稿卡片 === */
.draft-card {
  position: relative;
  background: #fff;
  border: 1px solid #e7edf7;
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.22s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.22s ease;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04);
}
.draft-card:hover {
  transform: translateY(-4px);
  border-color: rgba(13, 107, 255, 0.32);
  box-shadow: 0 14px 32px rgba(31, 53, 94, 0.12),
              0 2px 6px rgba(13, 107, 255, 0.08);
}
.draft-card.is-published {
  border-color: rgba(22, 191, 120, 0.28);
}
.draft-card.is-published:hover {
  border-color: rgba(22, 191, 120, 0.5);
  box-shadow: 0 14px 32px rgba(22, 191, 120, 0.12);
}
.draft-card.is-failed {
  border-color: rgba(255, 91, 97, 0.28);
}
.draft-card.is-failed:hover {
  border-color: rgba(255, 91, 97, 0.5);
  box-shadow: 0 14px 32px rgba(255, 91, 97, 0.12);
}

/* 顶部状态条 */
.card-status-bar {
  height: 3px;
  width: 100%;
  flex-shrink: 0;
}
.card-status-bar.bar-draft {
  background: linear-gradient(90deg, #98a2b3 0%, #c1c9d6 100%);
}
.card-status-bar.bar-publishing {
  background: linear-gradient(90deg, #0d6bff 0%, #3186ff 100%);
}
.card-status-bar.bar-published {
  background: linear-gradient(90deg, #16bf78 0%, #4ade80 100%);
}
.card-status-bar.bar-failed {
  background: linear-gradient(90deg, #ff5b61 0%, #f87171 100%);
}

/* 缩略图区 */
.draft-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: linear-gradient(135deg, #f6f9ff 0%, #eef3fa 100%);
  overflow: hidden;
}
.draft-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}
.draft-card:hover .draft-thumb img {
  transform: scale(1.06);
}

/* 占位符 */
.draft-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #98a2b3;
  font-size: 12px;
}
.placeholder-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(13, 107, 255, 0.08);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.placeholder-icon-wrap :deep(.ui-icon) {
  width: 22px;
  height: 22px;
}

/* 价格角标 */
.price-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(255, 255, 255, 0.96);
  color: #ef4444;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.12);
  display: inline-flex;
  align-items: baseline;
  gap: 1px;
}
.price-symbol {
  font-size: 11px;
}
.price-value {
  font-size: 14px;
}

/* 多图指示 */
.img-count-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(13, 107, 255, 0.92);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
}
.img-count-badge :deep(.ui-icon) {
  width: 12px;
  height: 12px;
}

/* hover 遮罩 */
.thumb-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  padding: 10px;
  pointer-events: none;
  background: linear-gradient(180deg,
    rgba(19, 33, 61, 0) 50%,
    rgba(19, 33, 61, 0.65) 100%);
  opacity: 0;
  transition: opacity 0.22s ease;
}
.draft-card:hover .thumb-overlay {
  opacity: 1;
}
.overlay-bottom {
  display: flex;
  justify-content: center;
}
.view-hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(255, 255, 255, 0.95);
  color: #0d6bff;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 999px;
  backdrop-filter: blur(8px);
  transform: translateY(8px);
  transition: transform 0.22s ease;
}
.draft-card:hover .view-hint {
  transform: translateY(0);
}
.view-hint :deep(.ui-icon) {
  width: 13px;
  height: 13px;
}

/* 信息区 */
.draft-info {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  flex: 1;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.info-row-badges {
  gap: 5px;
}
.info-row-meta {
  justify-content: space-between;
  margin-top: 2px;
  padding-top: 8px;
  border-top: 1px dashed #eef2f7;
}

/* 状态 pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.pill-draft {
  background: #f1f4f8;
  color: #718096;
}
.pill-publishing {
  background: #edf5ff;
  color: #0d6bff;
}
.pill-published {
  background: #e9fbf3;
  color: #0e9f6e;
}
.pill-fail {
  background: #fff0f1;
  color: #ef4444;
}
.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* 工作流标签 */
.workflow-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: #edf5ff;
  color: #0d6bff;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 标题 */
.draft-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #13213d;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 描述 */
.draft-desc {
  margin: 0;
  font-size: 12px;
  color: #5a6880;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  min-height: 36px;
  flex: 1;
}

/* 元信息行 */
.meta-category {
  font-size: 11px;
  color: #5a6880;
  background: #f4f6fa;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 500;
}
.meta-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #98a2b3;
}
.meta-time :deep(.ui-icon) {
  width: 12px;
  height: 12px;
}

/* 错误信息 */
.draft-error {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 4px;
  padding: 7px 9px;
  background: #fff5f5;
  border: 1px solid #ffd1d1;
  border-radius: 6px;
  font-size: 11px;
  color: #b91c1c;
  line-height: 1.5;
}
.draft-error :deep(.ui-icon) {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  margin-top: 1px;
}
.draft-error span {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

/* 已发布信息 */
.draft-published-info {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 4px;
  padding: 7px 9px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 11px;
  color: #15803d;
  line-height: 1.5;
}
.draft-published-info :deep(.ui-icon) {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

/* === 详情弹窗 === */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.72);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: auto;
  backdrop-filter: blur(4px);
  animation: maskFadeIn 0.2s ease;
}
@keyframes maskFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.modal-body {
  position: relative;
  background: #fff;
  border-radius: 18px;
  width: min(1120px, 100%);
  max-height: calc(100vh - 48px);
  overflow: hidden;
  box-shadow: 0 32px 80px rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(231, 237, 247, 0.95);
  display: flex;
  flex-direction: column;
  animation: modalSlideIn 0.24s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes modalSlideIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.modal-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.95);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  box-shadow: 0 4px 12px rgba(31, 53, 94, 0.12);
  transition: background 0.18s ease, transform 0.12s ease;
}
.modal-close:hover {
  background: #fff;
  transform: scale(1.08);
}
.modal-close :deep(.ui-icon) {
  width: 18px;
  height: 18px;
  color: #13213d;
}

.modal-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 440px;
  gap: 0;
  overflow: auto;
  max-height: calc(100vh - 48px);
}

/* 左侧图片区 */
.modal-image-area {
  background: linear-gradient(135deg, #0e1726 0%, #1a2540 100%);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: center;
  justify-content: flex-start;
  min-height: 360px;
}
.main-image-wrap {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}
.modal-main-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 10px;
  display: block;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
.download-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  color: #13213d;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  transition: background 0.18s ease, transform 0.12s ease;
}
.download-btn:hover {
  background: #fff;
  transform: scale(1.05);
}
.download-btn :deep(.ui-icon) {
  width: 16px;
  height: 16px;
}
.image-index {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  backdrop-filter: blur(8px);
}

.image-error.large {
  width: 100%;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  text-align: center;
  color: rgba(255, 255, 255, 0.7);
}
.image-error.large .error-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-error.large .error-icon-wrap :deep(.ui-icon) {
  width: 28px;
  height: 28px;
}

/* 缩略图条 */
.thumb-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  width: 100%;
  max-height: 100px;
  overflow-y: auto;
}
.thumb-item {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  background: rgba(255, 255, 255, 0.06);
  padding: 0;
  transition: all 0.18s ease;
}
.thumb-item:hover {
  border-color: rgba(255, 255, 255, 0.4);
  transform: scale(1.05);
}
.thumb-item.active {
  border-color: #0d6bff;
  box-shadow: 0 0 0 2px rgba(13, 107, 255, 0.4);
}
.thumb-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 右侧信息区 */
.modal-info {
  padding: 24px 24px 20px;
  overflow-y: auto;
  background: #fff;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}
.modal-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #13213d;
  word-break: break-word;
  flex: 1;
}
.modal-header-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
  flex-shrink: 0;
}

/* 关键信息卡片 */
.info-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}
.info-card {
  background: #f8fafc;
  border: 1px solid #eef3fa;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-card-label {
  font-size: 11px;
  color: #7a879e;
  font-weight: 500;
}
.info-card-value {
  font-size: 13px;
  color: #13213d;
  font-weight: 600;
  word-break: break-word;
}
.info-card-value.price-text {
  color: #ef4444;
  font-size: 16px;
}

/* 折叠详情 */
.detail-collapse {
  margin-bottom: 14px;
}
.detail-collapse summary {
  cursor: pointer;
  font-size: 12px;
  color: #5a6880;
  font-weight: 600;
  padding: 6px 0;
  user-select: none;
}
.detail-collapse summary:hover {
  color: #0d6bff;
}
.info-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 8px 12px;
  font-size: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #eef3fa;
  margin-top: 8px;
}
.info-grid span {
  color: #7a879e;
}
.info-grid b {
  color: #13213d;
  font-weight: 600;
  word-break: break-word;
}
.info-grid b.mono {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 11px;
}

/* 子标题 */
.section-subtitle {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #13213d;
  display: flex;
  align-items: center;
  gap: 6px;
}
.section-subtitle :deep(.ui-icon) {
  width: 14px;
  height: 14px;
  color: #5a6880;
}
.copy-btn {
  margin-left: auto;
  border: 1px solid #e7edf7;
  background: #f8fafc;
  color: #5a6880;
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.18s ease;
}
.copy-btn:hover {
  background: #edf5ff;
  border-color: #0d6bff;
  color: #0d6bff;
}
.copy-btn :deep(.ui-icon) {
  width: 12px;
  height: 12px;
}

.prompt-text {
  background: #f4f6fa;
  border-radius: 10px;
  padding: 14px;
  font-size: 12px;
  line-height: 1.65;
  color: #1f2937;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-height: 220px;
  overflow: auto;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  margin: 0;
  border: 1px solid #eef3fa;
}
.prompt-text.error {
  background: #fff5f5;
  color: #b91c1c;
  border: 1px solid #ffd1d1;
}
.error-block {
  margin-top: 4px;
}

.modal-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #eef3fa;
}

/* === 重试发布账号选择器 === */
.retry-account-picker {
  margin-top: 18px;
  padding: 14px 16px;
  background: #f8faff;
  border: 1px solid #dde7f5;
  border-radius: 10px;
}
.retry-account-picker .picker-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #13213d;
  margin-bottom: 8px;
}
.retry-account-picker .picker-label :deep(svg) {
  width: 14px;
  height: 14px;
}
.retry-account-picker .picker-select {
  width: 100%;
  padding: 8px 10px;
  font-size: 13px;
  color: #13213d;
  background: #fff;
  border: 1px solid #d1dced;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  outline: none;
}
.retry-account-picker .picker-select:hover {
  border-color: #0d6bff;
}
.retry-account-picker .picker-select:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.12);
}
.retry-account-picker .picker-select:disabled {
  background: #f4f6fa;
  color: #98a2b3;
  cursor: not-allowed;
}
.retry-account-picker .picker-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #5a6880;
  line-height: 1.5;
}

/* 全局错误提示 */
.global-notice {
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}
.global-notice.error {
  background: #fff5f5;
  color: #b91c1c;
  border: 1px solid #ffd1d1;
}

/* === 响应式 === */
@media (max-width: 960px) {
  .modal-grid {
    grid-template-columns: 1fr;
  }
  .modal-image-area {
    min-height: 280px;
    padding: 16px;
  }
  .modal-info {
    padding: 18px;
  }
}

@media (max-width: 720px) {
  .draft-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
  }
  .info-cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .filter-bar {
    gap: 8px;
  }
  .filter-bar .input {
    max-width: 100% !important;
    width: 100%;
  }
  .filter-chip-group {
    width: 100%;
    justify-content: space-between;
  }
  .filter-chip {
    flex: 1;
    justify-content: center;
    padding: 6px 8px;
  }
  .filter-divider {
    display: none;
  }
  .draft-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  .draft-info {
    padding: 10px;
  }
}
</style>
