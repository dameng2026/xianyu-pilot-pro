<template>
  <div class="workflow-image-records-page">
    <div v-if="globalError" class="global-notice error">{{ globalError }}</div>

    <!-- 顶部统计卡片 -->
    <div class="grid stat-grid">
      <StatCard title="总生成数" :value="metricText(stats.total)" :change="statsError ? '统计不可用' : '全量记录'" icon="ai" />
      <StatCard title="成功" :value="metricText(stats.success)" :change="statsError ? '统计不可用' : '全量统计'" icon="success" color="green" />
      <StatCard title="失败" :value="metricText(stats.failed)" :change="statsError ? '统计不可用' : '全量统计'" icon="warning" color="red" />
      <StatCard title="本月生成" :value="metricText(stats.thisMonth)" :change="statsError ? '统计不可用' : '本月新增'" icon="clock" color="blue" />
    </div>

    <CardPanel title="生图记录" desc="所有生图模型调用产生的图片历史，支持按来源、状态、关键词筛选">
      <!-- 筛选区 -->
      <div class="toolbar filter-bar">
        <select v-model="filters.source" class="input" style="max-width:130px">
          <option value="all">全部来源</option>
          <option value="workflow">工作流</option>
          <option value="opportunity">商机发掘</option>
        </select>
        <select v-model="filters.status" class="input" style="max-width:120px">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
        </select>
        <input
          v-model="filters.keyword"
          class="input"
          style="flex:1;min-width:200px"
          placeholder="搜索 prompt 或模型名"
          @keyup.enter="onSearch"
        />
        <AppButton type="primary" :loading="loading" @click="onSearch">查询</AppButton>
        <AppButton :loading="loading" @click="onRefresh">刷新</AppButton>
      </div>

      <!-- 三态：加载中 -->
      <div v-if="loading" class="loading-wrap">
        <div class="spinner"></div>
        <p class="subtle">正在加载生图记录...</p>
      </div>

      <!-- 三态：加载错误 -->
      <EmptyState
        v-else-if="loadError"
        variant="error"
        title="记录加载失败"
        :description="loadError"
      >
        <template #actions>
          <AppButton type="primary" @click="load">重新加载</AppButton>
        </template>
      </EmptyState>

      <!-- 三态：空数据 -->
      <EmptyState
        v-else-if="!records.length"
        icon="📭"
        title="暂无生图记录"
        description="还没有任何生图调用记录，发起一次生图后会在此展示。"
      />

      <!-- 图片网格 -->
      <div v-else class="image-grid">
        <div
          v-for="r in records"
          :key="r.id"
          class="image-card"
          :class="{ failed: r.status === 'failed' }"
          @click="openDetail(r)"
        >
          <div class="image-thumb">
            <template v-if="r.status === 'success' && firstImage(r)">
              <img :src="firstImage(r)" :alt="r.prompt || r.model || '生图结果'" loading="lazy" />
              <div class="image-overlay">
                <span class="overlay-model">{{ r.model || '未知模型' }}</span>
                <span class="overlay-time">{{ formatTime(r.created_time) }}</span>
              </div>
            </template>
            <template v-else>
              <div class="image-error">
                <Icon name="warning" />
                <span class="image-error-text">{{ r.error_message || '生图失败' }}</span>
              </div>
            </template>
          </div>
          <div class="image-info">
            <div class="image-badges">
              <Badge :type="r.status === 'success' ? 'green' : 'red'">{{ statusText(r.status) }}</Badge>
              <Badge type="blue">{{ sourceText(r.source) }}</Badge>
              <Badge v-if="r.model" type="gray">{{ r.model }}</Badge>
            </div>
            <p class="prompt-snippet" :title="r.prompt || ''">{{ r.prompt || '—' }}</p>
            <p class="image-meta">
              <span>{{ formatTime(r.created_time) }}</span>
              <span v-if="r.image_count" class="meta-count">{{ r.image_count }} 张</span>
            </p>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="!loading && !loadError && records.length" class="pagination">
        <button class="app-btn" :disabled="page <= 1 || loading" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
        <button class="app-btn" :disabled="page >= totalPages || loading" @click="goPage(page + 1)">下一页</button>
      </div>
    </CardPanel>

    <!-- 详情弹窗 -->
    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-body">
        <button class="modal-close" title="关闭" @click="closeDetail"><Icon name="close" /></button>
        <div class="modal-grid">
          <!-- 左侧图片区 -->
          <div class="modal-image-area">
            <template v-if="parseImages(detail.result_images).length">
              <img
                class="modal-main-image"
                :src="parseImages(detail.result_images)[0].url"
                :alt="detail.prompt || ''"
              />
              <div v-if="parseImages(detail.result_images).length > 1" class="more-images">
                <img
                  v-for="(img, idx) in parseImages(detail.result_images).slice(1)"
                  :key="idx"
                  :src="img.url"
                  :alt="`image-${idx + 1}`"
                  loading="lazy"
                />
              </div>
            </template>
            <div v-else class="image-error large">
              <Icon name="warning" />
              <span>{{ detail.error_message || '生图失败，未产生图片' }}</span>
            </div>
          </div>

          <!-- 右侧信息区 -->
          <div class="modal-info">
            <h2 class="modal-title">生图详情</h2>
            <div class="info-grid">
              <div><span>状态</span><b :class="detail.status === 'success' ? 'text-success' : 'text-fail'">{{ statusText(detail.status) }}</b></div>
              <div><span>来源</span><b>{{ sourceText(detail.source) }}</b></div>
              <div><span>模型</span><b>{{ detail.model || '—' }}</b></div>
              <div><span>图片尺寸</span><b>{{ detail.image_size || '—' }}</b></div>
              <div><span>图片数量</span><b>{{ detail.image_count ?? '—' }}</b></div>
              <div><span>调用方式</span><b>{{ detail.method_used || '—' }}</b></div>
              <div><span>工作流 ID</span><b>{{ detail.workflow_id || '—' }}</b></div>
              <div><span>执行 ID</span><b>{{ detail.workflow_execution_id || '—' }}</b></div>
              <div><span>节点 Key</span><b>{{ detail.workflow_node_key || '—' }}</b></div>
              <div><span>请求 ID</span><b class="mono">{{ detail.request_id || '—' }}</b></div>
              <div><span>创建时间</span><b>{{ formatTime(detail.created_time) }}</b></div>
            </div>

            <h3 class="section-subtitle">Prompt</h3>
            <pre class="prompt-text">{{ detail.prompt || '—' }}</pre>

            <div v-if="detail.error_message" class="error-block">
              <h3 class="section-subtitle">错误信息</h3>
              <pre class="prompt-text error">{{ detail.error_message }}</pre>
            </div>

            <div class="modal-actions">
              <AppButton
                v-if="detail.status === 'failed'"
                type="primary"
                :loading="recovering"
                @click="recover"
              >恢复图片</AppButton>
              <a
                v-if="parseImages(detail.result_images).length"
                class="app-btn"
                :href="parseImages(detail.result_images)[0].url"
                target="_blank"
                rel="noopener noreferrer"
              >原图新窗口</a>
              <AppButton @click="closeDetail">关闭</AppButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import { listImageRecords, recoverOpportunityImages } from '../api/opportunity.js'

const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(24)
const loading = ref(false)
const loadError = ref('')
const globalError = ref('')

const filters = ref({ source: 'all', status: '', keyword: '' })

const stats = ref({ total: null, success: null, failed: null, thisMonth: null })
const statsError = ref('')

const detail = ref(null)
const recovering = ref(false)

const totalPages = computed(() => {
  const t = Number(total.value) || 0
  const ps = Number(pageSize.value) || 1
  return Math.max(1, Math.ceil(t / ps))
})

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function statusText(s) {
  if (s === 'success') return '成功'
  if (s === 'failed') return '失败'
  return s || '—'
}

function sourceText(src) {
  if (src === 'workflow') return '工作流'
  if (src === 'opportunity') return '商机发掘'
  return '未知'
}

function formatTime(value) {
  if (!value) return '—'
  const s = String(value).replace('T', ' ').replace(/\.\d+$/, '').slice(0, 16)
  return s
}

// 兼容 result_images 字段：可能是 JSON 字符串、数组或单对象
function parseImages(raw) {
  if (!raw) return []
  if (Array.isArray(raw)) return raw.filter(i => i && i.url)
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed.filter(i => i && i.url)
      if (parsed && parsed.url) return [parsed]
    } catch {
      return []
    }
  } else if (typeof raw === 'object' && raw.url) {
    return [raw]
  }
  return []
}

function firstImage(record) {
  const imgs = parseImages(record && record.result_images)
  return imgs.length ? imgs[0].url : ''
}

function extractListData(res) {
  const data = res && res.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('生图记录响应格式异常')
  }
  if (!Array.isArray(data.records)) throw new Error('生图记录列表字段缺失')
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
      source: filters.value.source || 'all',
      status: filters.value.status || '',
      keyword: filters.value.keyword || '',
      page: page.value,
      pageSize: pageSize.value
    }
    const res = await listImageRecords(params)
    const data = extractListData(res)
    records.value = data.records
    total.value = data.total
    page.value = data.page
  } catch (e) {
    records.value = []
    total.value = 0
    loadError.value = (e && e.message) || '生图记录加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsError.value = ''
  try {
    const res = await listImageRecords({ source: 'all', status: '', keyword: '', page: 1, pageSize: 1000 })
    const data = extractListData(res)
    const list = data.records
    const now = new Date()
    const thisYear = now.getFullYear()
    const thisMonth = now.getMonth() + 1
    let success = 0
    let failed = 0
    let monthCount = 0
    for (const r of list) {
      if (r && r.status === 'success') success++
      else if (r && r.status === 'failed') failed++
      if (r && r.created_time) {
        const d = new Date(String(r.created_time).replace(' ', 'T'))
        if (!isNaN(d.getTime()) && d.getFullYear() === thisYear && d.getMonth() + 1 === thisMonth) {
          monthCount++
        }
      }
    }
    stats.value = { total: list.length, success, failed, thisMonth: monthCount }
  } catch (e) {
    stats.value = { total: null, success: null, failed: null, thisMonth: null }
    statsError.value = (e && e.message) || '统计加载失败'
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
  if (p < 1 || p > totalPages.value || p === page.value) return
  page.value = p
  load()
}

function openDetail(record) {
  detail.value = record
}

function closeDetail() {
  detail.value = null
}

async function recover() {
  if (!detail.value || recovering.value) return
  globalError.value = ''
  recovering.value = true
  try {
    await recoverOpportunityImages(detail.value.id)
    // 恢复后重新拉取列表与统计
    await Promise.all([load(), loadStats()])
    // 如果当前详情仍在列表中，刷新详情数据
    if (detail.value) {
      const updated = records.value.find(r => r.id === detail.value.id)
      if (updated) detail.value = updated
    }
  } catch (e) {
    globalError.value = (e && e.message) || '恢复图片失败，请稍后重试。'
  } finally {
    recovering.value = false
  }
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<style scoped>
.workflow-image-records-page {
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
  animation: wir-spin 0.8s linear infinite;
}
@keyframes wir-spin { to { transform: rotate(360deg); } }

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-top: 8px;
}

.image-card {
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
.image-card:hover {
  transform: translateY(-2px);
  border-color: rgba(13, 107, 255, 0.35);
  box-shadow: 0 22px 50px rgba(31, 53, 94, 0.12);
}
.image-card.failed {
  border-color: rgba(239, 68, 68, 0.4);
}
.image-card.failed:hover {
  border-color: rgba(239, 68, 68, 0.7);
}

.image-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #f3f6fb;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.28s ease;
}
.image-card:hover .image-thumb img {
  transform: scale(1.03);
}

.image-overlay {
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
.image-card:hover .image-overlay {
  opacity: 1;
}
.overlay-model {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.overlay-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 2px;
}

.image-error {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  text-align: center;
  background: linear-gradient(135deg, #fff5f5, #fff8f8);
  color: #ef4444;
}
.image-error :deep(.ui-icon) {
  width: 32px;
  height: 32px;
}
.image-error-text {
  font-size: 12px;
  color: #ef4444;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  line-height: 1.5;
}
.image-error.large {
  min-height: 280px;
  gap: 12px;
}
.image-error.large :deep(.ui-icon) {
  width: 48px;
  height: 48px;
}
.image-error.large .image-error-text {
  font-size: 14px;
  -webkit-line-clamp: 5;
}

.image-info {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.image-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.prompt-snippet {
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
.image-meta {
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

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 22px;
  padding: 12px 0 4px;
}
.page-info {
  color: #5a6880;
  font-size: 13px;
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
.modal-actions .app-btn {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
