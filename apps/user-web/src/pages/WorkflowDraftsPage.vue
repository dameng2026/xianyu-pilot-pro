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
        <select v-model="filters.status" class="input" style="max-width:140px">
          <option value="all">全部状态</option>
          <option value="draft">待发布</option>
          <option value="publishing">发布中</option>
          <option value="published">已发布</option>
          <option value="failed">发布失败</option>
        </select>
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
        description="工作流 PUBLISH 节点产出的商品会自动保存到这里，无论发布成功或失败都会保留记录。"
      />

      <!-- 草稿网格 -->
      <div v-else class="draft-grid">
        <div
          v-for="r in records"
          :key="r.id"
          class="draft-card"
          :class="[statusClass(r.publish_status), { failed: r.publish_status === 'failed' }]"
          @click="openDetail(r)"
        >
          <div class="draft-thumb">
            <img
              v-if="r.cover_pic"
              :src="r.cover_pic"
              :alt="r.title || '商品草稿'"
              loading="lazy"
              @error="onImageError($event, r)"
            />
            <div v-else class="draft-thumb-placeholder">
              <Icon name="image" />
              <span>暂无封面</span>
            </div>
            <div class="draft-overlay">
              <span class="overlay-status">{{ statusText(r.publish_status) }}</span>
              <span v-if="r.price" class="overlay-price">¥{{ r.price }}</span>
            </div>
          </div>
          <div class="draft-info">
            <div class="draft-badges">
              <Badge :type="statusBadgeType(r.publish_status)">{{ statusText(r.publish_status) }}</Badge>
              <Badge v-if="r.workflow_name" type="blue" :title="r.workflow_name">{{ truncate(r.workflow_name, 12) }}</Badge>
              <Badge v-if="r.category" type="gray">{{ r.category }}</Badge>
            </div>
            <p class="draft-title" :title="r.title || ''">{{ r.title || '未命名商品' }}</p>
            <p class="draft-desc" :title="r.description || ''">{{ r.description || '—' }}</p>
            <p class="draft-meta">
              <span>{{ formatTime(r.created_time) }}</span>
              <span v-if="r.image_urls && r.image_urls.length" class="meta-count">{{ r.image_urls.length }} 张图</span>
            </p>
            <div v-if="r.publish_status === 'failed' && r.publish_error_message" class="draft-error" :title="r.publish_error_message">
              <Icon name="warning" />
              <span>{{ truncate(r.publish_error_message, 40) }}</span>
            </div>
          </div>
        </div>
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
            <img
              v-if="detail.cover_pic"
              class="modal-main-image"
              :src="detail.cover_pic"
              :alt="detail.title || '商品草稿'"
            />
            <div v-else class="image-error large">
              <Icon name="image" />
              <span>该草稿没有封面图</span>
            </div>
            <div v-if="parsedImages.length > 1" class="more-images">
              <img
                v-for="(img, idx) in parsedImages.slice(1)"
                :key="idx"
                :src="img"
                :alt="`image-${idx + 1}`"
                loading="lazy"
              />
            </div>
          </div>

          <!-- 右侧信息区 -->
          <div class="modal-info">
            <h2 class="modal-title">{{ detail.title || '未命名商品' }}</h2>
            <div class="info-grid">
              <div><span>状态</span><b :class="statusTextClass(detail.publish_status)">{{ statusText(detail.publish_status) }}</b></div>
              <div><span>价格</span><b>¥{{ detail.price || '—' }}</b></div>
              <div><span>分类</span><b>{{ detail.category || '—' }}</b></div>
              <div><span>库存</span><b>{{ detail.stock ?? '—' }}</b></div>
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
            </div>

            <h3 v-if="detail.description" class="section-subtitle">商品描述</h3>
            <pre v-if="detail.description" class="prompt-text">{{ detail.description }}</pre>

            <div v-if="detail.publish_error_message" class="error-block">
              <h3 class="section-subtitle">发布失败原因</h3>
              <pre class="prompt-text error">{{ detail.publish_error_message }}</pre>
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import Pagination from '../components/Pagination.vue'
import { globalConfirm } from '../composables/confirmState.js'
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

function statusBadgeType(s) {
  return ({
    draft: 'gray',
    publishing: 'blue',
    published: 'green',
    failed: 'red'
  })[s] || 'gray'
}

function statusClass(s) {
  return `status-${s || 'draft'}`
}

function statusTextClass(s) {
  if (s === 'published') return 'text-success'
  if (s === 'failed') return 'text-fail'
  return ''
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

function onImageError(event, record) {
  // 图片加载失败时，清空 cover_pic 触发占位符显示
  if (record) record.cover_pic = ''
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
}

function closeDetail() {
  detail.value = null
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

async function retryPublish() {
  if (!detail.value || retrying.value) return
  globalError.value = ''
  retrying.value = true
  try {
    const res = await retryPublishDraft(detail.value.id)
    const data = res && res.data
    if (data && data.success === false) {
      globalError.value = data.error || '重试发布失败，请稍后重试'
    }
    await Promise.all([load(), loadStats()])
    await refreshDetail(detail.value.id)
    if (!globalError.value) {
      window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '重试发布已触发，请稍后查看发布结果', type: 'success' } }))
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
  const confirmed = await globalConfirm.confirm(
    '批量重试发布',
    `将重试当前列表中的 ${failedIds.length} 条草稿，是否继续？`,
    '立即重试'
  )
  if (!confirmed) return
  globalError.value = ''
  batchRetrying.value = true
  try {
    const res = await batchRetryPublishDrafts(failedIds)
    const data = res && res.data
    const succ = Number(data?.success) || 0
    const fail = Number(data?.failed) || 0
    await Promise.all([load(), loadStats()])
    if (detail.value) await refreshDetail(detail.value.id)
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: {
        message: `批量重试完成：成功 ${succ} 条，失败 ${fail} 条`,
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
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.workflow-drafts-page {
  display: block;
}

.filter-bar {
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.loading-wrap {
  padding: 60px 0;
  text-align: center;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #eef3fa;
  border-top-color: #0d6bff;
  border-radius: 50%;
  margin: 0 auto;
  animation: wd-spin 0.8s linear infinite;
}
@keyframes wd-spin { to { transform: rotate(360deg); } }

.draft-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
  margin-top: 8px;
}

.draft-card {
  background: #fff;
  border: 1px solid rgba(231, 237, 247, 0.95);
  border-radius: 16px;
  box-shadow: 0 18px 42px rgba(31, 53, 94, 0.08);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  display: flex;
  flex-direction: column;
}
.draft-card:hover {
  transform: translateY(-2px);
  border-color: rgba(13, 107, 255, 0.35);
  box-shadow: 0 22px 50px rgba(31, 53, 94, 0.12);
}
.draft-card.failed {
  border-color: rgba(239, 68, 68, 0.4);
}
.draft-card.failed:hover {
  border-color: rgba(239, 68, 68, 0.7);
}
.draft-card.status-published {
  border-color: rgba(22, 191, 120, 0.35);
}
.draft-card.status-published:hover {
  border-color: rgba(22, 191, 120, 0.6);
}

.draft-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #f3f6fb;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.draft-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.28s ease;
}
.draft-card:hover .draft-thumb img {
  transform: scale(1.03);
}
.draft-thumb-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #98a2b3;
  font-size: 12px;
}
.draft-thumb-placeholder :deep(.ui-icon) {
  width: 32px;
  height: 32px;
}

.draft-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(19, 33, 61, 0) 50%, rgba(19, 33, 61, 0.72) 100%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 10px 12px;
  opacity: 0;
  transition: opacity 0.22s ease;
  color: #fff;
  pointer-events: none;
}
.draft-card:hover .draft-overlay {
  opacity: 1;
}
.overlay-status {
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}
.overlay-price {
  font-size: 14px;
  font-weight: 700;
  color: #ffd166;
  margin-top: 2px;
}

.draft-info {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.draft-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.draft-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #13213d;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
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
}
.draft-meta {
  margin: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #98a2b3;
}
.meta-count {
  color: #0d6bff;
  font-weight: 600;
}
.draft-error {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-top: 4px;
  padding: 6px 8px;
  background: #fff5f5;
  border: 1px solid #ffd1d1;
  border-radius: 6px;
  font-size: 11px;
  color: #b91c1c;
  line-height: 1.5;
}
.draft-error :deep(.ui-icon) {
  width: 14px;
  height: 14px;
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

/* 详情弹窗 */
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
  backdrop-filter: blur(2px);
}
.modal-body {
  position: relative;
  background: #fff;
  border-radius: 20px;
  width: min(1080px, 100%);
  max-height: calc(100vh - 48px);
  overflow: hidden;
  box-shadow: 0 32px 80px rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(231, 237, 247, 0.95);
  display: flex;
  flex-direction: column;
}
.modal-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.9);
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
  transform: scale(1.05);
}
.modal-close :deep(.ui-icon) {
  width: 18px;
  height: 18px;
  color: #13213d;
}

.modal-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 0;
  overflow: auto;
  max-height: calc(100vh - 48px);
}

.modal-image-area {
  background: #0e1726;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: flex-start;
  min-height: 320px;
}
.modal-main-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 10px;
  display: block;
}
.more-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  width: 100%;
}
.more-images img {
  width: 84px;
  height: 84px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.18);
  transition: transform 0.18s ease;
}
.more-images img:hover {
  transform: scale(1.05);
}

.modal-info {
  padding: 24px 22px;
  overflow-y: auto;
  background: #fff;
}
.modal-title {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 700;
  color: #13213d;
  word-break: break-word;
}

.info-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 10px 12px;
  font-size: 13px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #eef3fa;
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
  font-size: 12px;
}
.text-success {
  color: #16bf78 !important;
}
.text-fail {
  color: #ef4444 !important;
}

.section-subtitle {
  margin: 18px 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #13213d;
}

.prompt-text {
  background: #f3f5f7;
  border-radius: 10px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.65;
  color: #1f2937;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-height: 200px;
  overflow: auto;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  margin: 0;
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
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #eef3fa;
}

@media (max-width: 880px) {
  .modal-grid {
    grid-template-columns: 1fr;
  }
  .modal-image-area {
    min-height: 240px;
  }
}

@media (max-width: 600px) {
  .filter-bar {
    gap: 8px;
  }
  .filter-bar .input {
    max-width: 100% !important;
    width: 100%;
  }
}
</style>
