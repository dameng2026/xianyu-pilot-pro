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
        <div class="filter-chip-group">
          <button
            v-for="opt in sourceOptions"
            :key="opt.value"
            type="button"
            class="filter-chip"
            :class="{ active: filters.source === opt.value }"
            @click="filters.source = opt.value; onSearch()"
          >
            <span class="chip-dot" :class="opt.dot" />
            {{ opt.label }}
          </button>
        </div>
        <div class="filter-divider" />
        <select v-model="filters.status" class="input" style="max-width:120px" @change="onSearch">
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
        icon="🎨"
        title="暂无生图记录"
        description="还没有任何生图调用记录。在工作流或商机发掘中触发一次生图后，会在此展示生成的图片与详细参数。"
      />

      <!-- 图片网格 - 重点优化的卡片视觉 -->
      <div v-else class="image-grid">
        <article
          v-for="r in records"
          :key="r.id"
          class="image-card"
          :class="[r.status === 'failed' ? 'is-failed' : 'is-success']"
          @click="openDetail(r)"
        >
          <!-- 顶部状态条 -->
          <div class="card-status-bar" :class="r.status === 'failed' ? 'bar-fail' : 'bar-success'" />

          <!-- 缩略图区 -->
          <div class="image-thumb">
            <template v-if="r.status === 'success' && firstImage(r)">
              <img
                :src="firstImage(r)"
                :alt="r.prompt || r.model || '生图结果'"
                loading="lazy"
                @error="onCardImageError($event, r)"
              />
              <!-- 渐变遮罩（hover 时显示信息） -->
              <div class="thumb-overlay">
                <div class="overlay-top">
                  <span v-if="imageCount(r) > 1" class="img-count-badge">
                    <Icon name="image" />
                    <span>{{ imageCount(r) }} 张</span>
                  </span>
                  <span class="img-size-badge" v-if="r.image_size">{{ r.image_size }}</span>
                </div>
                <div class="overlay-bottom">
                  <span class="view-hint">
                    <Icon name="search" />
                    <span>查看详情</span>
                  </span>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="image-error-block">
                <div class="error-icon-wrap">
                  <Icon name="warning" />
                </div>
                <span class="error-text">{{ truncate(r.error_message || '生图失败', 60) }}</span>
              </div>
            </template>
          </div>

          <!-- 信息区 -->
          <div class="image-info">
            <!-- 第一行：状态 + 来源 -->
            <div class="info-row info-row-badges">
              <span class="status-pill" :class="r.status === 'success' ? 'pill-success' : 'pill-fail'">
                <span class="pill-dot" />
                {{ statusText(r.status) }}
              </span>
              <span class="source-tag" :class="`tag-${r.source || 'unknown'}`">
                {{ sourceText(r.source) }}
              </span>
              <span v-if="r.model" class="model-tag" :title="r.model">{{ truncate(r.model, 18) }}</span>
            </div>

            <!-- 第二行：prompt 摘要 -->
            <p class="prompt-snippet" :title="r.prompt || ''">
              <span class="prompt-quote">“</span>{{ r.prompt || '—' }}<span class="prompt-quote">”</span>
            </p>

            <!-- 第三行：时间 + 调用方式 -->
            <div class="info-row info-row-meta">
              <span class="meta-time">
                <Icon name="clock" />
                <span>{{ formatTime(r.created_time) }}</span>
              </span>
              <span v-if="r.method_used" class="meta-method" :title="r.method_used">
                {{ methodText(r.method_used) }}
              </span>
            </div>
          </div>
        </article>
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
            <!-- 主图 -->
            <div class="main-image-wrap">
              <template v-if="detailImages.length">
                <img
                  class="modal-main-image"
                  :src="currentImage.url"
                  :alt="detail.prompt || ''"
                />
                <a
                  v-if="currentImage.url"
                  class="download-btn"
                  :href="currentImage.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  download
                  title="新窗口打开原图"
                >
                  <Icon name="download" />
                </a>
                <!-- 图片索引指示器 -->
                <div v-if="detailImages.length > 1" class="image-index">
                  {{ currentIndex + 1 }} / {{ detailImages.length }}
                </div>
              </template>
              <div v-else class="image-error large">
                <div class="error-icon-wrap">
                  <Icon name="warning" />
                </div>
                <span>{{ detail.error_message || '生图失败，未产生图片' }}</span>
              </div>
            </div>

            <!-- 缩略图列表（多图时可切换） -->
            <div v-if="detailImages.length > 1" class="thumb-strip">
              <button
                v-for="(img, idx) in detailImages"
                :key="idx"
                type="button"
                class="thumb-item"
                :class="{ active: idx === currentIndex }"
                @click="currentIndex = idx"
              >
                <img :src="img.url" :alt="`image-${idx + 1}`" loading="lazy" />
              </button>
            </div>
          </div>

          <!-- 右侧信息区 -->
          <div class="modal-info">
            <div class="modal-header">
              <h2 class="modal-title">生图详情</h2>
              <div class="modal-header-badges">
                <span class="status-pill" :class="detail.status === 'success' ? 'pill-success' : 'pill-fail'">
                  <span class="pill-dot" />
                  {{ statusText(detail.status) }}
                </span>
                <span class="source-tag" :class="`tag-${detail.source || 'unknown'}`">
                  {{ sourceText(detail.source) }}
                </span>
              </div>
            </div>

            <!-- 关键信息卡片 -->
            <div class="info-cards">
              <div class="info-card">
                <span class="info-card-label">模型</span>
                <span class="info-card-value">{{ detail.model || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">尺寸</span>
                <span class="info-card-value">{{ detail.image_size || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">数量</span>
                <span class="info-card-value">{{ detail.image_count ?? '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-card-label">调用方式</span>
                <span class="info-card-value">{{ methodText(detail.method_used) || '—' }}</span>
              </div>
            </div>

            <!-- 详细字段表格 -->
            <details class="detail-collapse" open>
              <summary>完整字段</summary>
              <div class="info-grid">
                <div><span>工作流 ID</span><b>{{ detail.workflow_id || '—' }}</b></div>
                <div><span>执行 ID</span><b>{{ detail.workflow_execution_id || '—' }}</b></div>
                <div><span>节点 Key</span><b class="mono">{{ detail.workflow_node_key || '—' }}</b></div>
                <div><span>请求 ID</span><b class="mono">{{ truncate(detail.request_id || '—', 32) }}</b></div>
                <div><span>创建时间</span><b>{{ formatTime(detail.created_time) }}</b></div>
                <div><span>记录 ID</span><b class="mono">{{ detail.id }}</b></div>
              </div>
            </details>

            <!-- Prompt 区块 -->
            <h3 class="section-subtitle">
              <Icon name="message" />
              <span>Prompt</span>
              <button v-if="detail.prompt" type="button" class="copy-btn" @click="copyPrompt">
                <Icon name="copy" />
                <span>{{ copied ? '已复制' : '复制' }}</span>
              </button>
            </h3>
            <pre class="prompt-text">{{ detail.prompt || '—' }}</pre>

            <div v-if="detail.error_message" class="error-block">
              <h3 class="section-subtitle">
                <Icon name="warning" />
                <span>错误信息</span>
              </h3>
              <pre class="prompt-text error">{{ detail.error_message }}</pre>
            </div>

            <div class="modal-actions">
              <AppButton
                v-if="detail.status === 'failed'"
                type="primary"
                :loading="recovering"
                @click="recover"
              >恢复图片</AppButton>
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
const currentIndex = ref(0)
const copied = ref(false)

const sourceOptions = [
  { value: 'all', label: '全部', dot: 'dot-all' },
  { value: 'workflow', label: '工作流', dot: 'dot-workflow' },
  { value: 'opportunity', label: '商机发掘', dot: 'dot-opportunity' }
]

const totalPages = computed(() => {
  const t = Number(total.value) || 0
  const ps = Number(pageSize.value) || 1
  return Math.max(1, Math.ceil(t / ps))
})

const detailImages = computed(() => parseImages(detail.value && detail.value.result_images))
const currentImage = computed(() => detailImages.value[currentIndex.value] || { url: '' })

watch(detail, () => { currentIndex.value = 0 })

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

function methodText(m) {
  if (!m) return ''
  const map = {
    'openai-compatible': 'OpenAI',
    'openai': 'OpenAI',
    'replicate': 'Replicate',
    'stability': 'Stability',
    'custom': '自定义'
  }
  return map[m] || m
}

function formatTime(value) {
  if (!value) return '—'
  const s = String(value).replace('T', ' ').replace(/\.\d+$/, '').slice(0, 16)
  return s
}

function truncate(text, max) {
  const s = String(text || '')
  return s.length > max ? s.slice(0, max) + '…' : s
}

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

function imageCount(record) {
  return parseImages(record && record.result_images).length
}

function onCardImageError(event, record) {
  // 加载失败时把 src 清空，让 overlay 仍可见但图片显示 broken
  if (event && event.target) {
    event.target.style.opacity = '0.2'
  }
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
  copied.value = false
}

async function copyPrompt() {
  if (!detail.value || !detail.value.prompt) return
  try {
    await navigator.clipboard.writeText(detail.value.prompt)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 兜底：使用旧 API
    const ta = document.createElement('textarea')
    ta.value = detail.value.prompt
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy'); copied.value = true; setTimeout(() => { copied.value = false }, 2000) } catch {}
    document.body.removeChild(ta)
  }
}

async function recover() {
  if (!detail.value || recovering.value) return
  globalError.value = ''
  recovering.value = true
  try {
    await recoverOpportunityImages(detail.value.id)
    await Promise.all([load(), loadStats()])
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

function onHeaderAction(event) {
  if (event.detail === 'workflow-image-records-refresh') {
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
.workflow-image-records-page {
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
.filter-chip:hover {
  color: #13213d;
}
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
.chip-dot.dot-workflow { background: #0d6bff; }
.chip-dot.dot-opportunity { background: #16bf78; }
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
  animation: wir-spin 0.8s linear infinite;
}
@keyframes wir-spin { to { transform: rotate(360deg); } }
.subtle {
  color: #7a879e;
  font-size: 13px;
  margin: 0;
}

/* === 图片网格 === */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
  margin-top: 4px;
}

/* === 图片卡片 - 重点优化 === */
.image-card {
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
.image-card:hover {
  transform: translateY(-4px);
  border-color: rgba(13, 107, 255, 0.32);
  box-shadow: 0 14px 32px rgba(31, 53, 94, 0.12),
              0 2px 6px rgba(13, 107, 255, 0.08);
}
.image-card.is-failed {
  border-color: rgba(255, 91, 97, 0.28);
}
.image-card.is-failed:hover {
  border-color: rgba(255, 91, 97, 0.5);
  box-shadow: 0 14px 32px rgba(255, 91, 97, 0.12);
}

/* 顶部状态条 */
.card-status-bar {
  height: 3px;
  width: 100%;
  flex-shrink: 0;
}
.card-status-bar.bar-success {
  background: linear-gradient(90deg, #16bf78 0%, #4ade80 100%);
}
.card-status-bar.bar-fail {
  background: linear-gradient(90deg, #ff5b61 0%, #f87171 100%);
}

/* 缩略图区 */
.image-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: linear-gradient(135deg, #f6f9ff 0%, #eef3fa 100%);
  overflow: hidden;
}
.image-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}
.image-card:hover .image-thumb img {
  transform: scale(1.06);
}

/* 缩略图遮罩（hover 显示） */
.thumb-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 10px;
  pointer-events: none;
  background: linear-gradient(180deg,
    rgba(19, 33, 61, 0.45) 0%,
    rgba(19, 33, 61, 0) 30%,
    rgba(19, 33, 61, 0) 60%,
    rgba(19, 33, 61, 0.65) 100%);
  opacity: 0;
  transition: opacity 0.22s ease;
}
.image-card:hover .thumb-overlay {
  opacity: 1;
}
.overlay-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.img-count-badge {
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
.img-size-badge {
  background: rgba(255, 255, 255, 0.95);
  color: #13213d;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 7px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
  font-family: ui-monospace, Menlo, Consolas, monospace;
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
.image-card:hover .view-hint {
  transform: translateY(0);
}
.view-hint :deep(.ui-icon) {
  width: 13px;
  height: 13px;
}

/* 失败占位 */
.image-error-block {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  text-align: center;
  background: linear-gradient(135deg, #fff5f5 0%, #fff8f8 100%);
}
.error-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(255, 91, 97, 0.12);
  color: #ff5b61;
  display: flex;
  align-items: center;
  justify-content: center;
}
.error-icon-wrap :deep(.ui-icon) {
  width: 22px;
  height: 22px;
}
.error-text {
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  max-width: 100%;
}
.image-error.large {
  min-height: 280px;
}
.image-error.large .error-icon-wrap {
  width: 56px;
  height: 56px;
}
.image-error.large .error-icon-wrap :deep(.ui-icon) {
  width: 28px;
  height: 28px;
}
.image-error.large .error-text {
  font-size: 14px;
  -webkit-line-clamp: 5;
}

/* 信息区 */
.image-info {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.pill-success {
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

/* 来源标签 */
.source-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: #f1f4f8;
  color: #718096;
}
.source-tag.tag-workflow {
  background: #edf5ff;
  color: #0d6bff;
}
.source-tag.tag-opportunity {
  background: #e9fbf3;
  color: #0e9f6e;
}

/* 模型标签 */
.model-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background: #f8f9fb;
  color: #5a6880;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* prompt 摘要 */
.prompt-snippet {
  margin: 0;
  font-size: 12.5px;
  color: #475467;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  min-height: 38px;
  flex: 1;
}
.prompt-quote {
  color: #c1c9d6;
  font-weight: 700;
  font-size: 14px;
  margin: 0 1px;
}

/* 元信息行 */
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
.meta-method {
  font-size: 11px;
  color: #7a879e;
  background: #f4f6fa;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 500;
}

/* === 分页 === */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 24px;
  padding: 14px 0 4px;
}
.page-info {
  color: #5a6880;
  font-size: 13px;
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
}
.modal-header-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  .image-grid {
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
  }
  .filter-divider {
    display: none;
  }
  .image-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  .image-info {
    padding: 10px;
  }
}
</style>
