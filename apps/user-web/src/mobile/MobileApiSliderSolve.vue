<template>
  <div class="m-api-slider">
    <!-- 标题区 -->
    <div class="m-api-header">
      <h1>API滑块求解</h1>
      <p>开放滑块求解能力，对接外部系统</p>
    </div>

    <!-- 概览卡片（两列网格） -->
    <div class="m-overview-grid">
      <div class="m-overview-card">
        <div class="m-card-label">对接密钥</div>
        <div class="m-card-value">{{ fullKey || '尚未生成' }}</div>
        <button class="m-mini-btn" @click="copy(fullKey, '密钥')" v-if="fullKey">复制</button>
      </div>
      <div class="m-overview-card">
        <div class="m-card-label">Token 余额</div>
        <div class="m-card-value">{{ overview.tokenBalance ?? 0 }}</div>
        <button class="m-mini-btn m-mini-btn-primary" @click="$emit('force-desktop', 'profile-recharge')">充值</button>
      </div>
      <div class="m-overview-card">
        <div class="m-card-label">单次价格</div>
        <div class="m-card-value">{{ overview.perCallTokens != null ? `${overview.perCallTokens} Token` : '价格不可用' }}</div>
      </div>
      <div class="m-overview-card">
        <div class="m-card-label">API 地址</div>
        <div class="m-card-value m-card-value-sm">{{ apiUrl }}</div>
        <button class="m-mini-btn" @click="copy(apiUrl, 'API地址')">复制</button>
      </div>
    </div>

    <!-- 重要说明 -->
    <div class="m-notice-card">
      <div class="m-notice-item">
        <strong>能力范围：</strong>仅处理 WS 掉线引起的滑块。Cookie 失效需重新扫码登录。
      </div>
      <div class="m-notice-item">
        <strong>扣费保证：</strong>仅对成功求解扣费，失败/超时不扣费。
      </div>
      <div class="m-notice-item">
        <strong>客服微信：</strong><b>JiShu0724</b>
      </div>
    </div>

    <!-- 对接文档（可展开） -->
    <div class="m-doc-card">
      <div class="m-doc-toggle" @click="docExpanded = !docExpanded">
        <span>API 对接文档</span>
        <span>{{ docExpanded ? '收起' : '展开' }}</span>
      </div>
      <div v-if="docExpanded" class="m-doc-body">
        <p><b>请求：</b>POST /api/v1/slider/solve，Header X-Api-Key</p>
        <p><b>参数：</b>cookie（必填），仅需提交对接密钥与完整 Cookie 即可</p>
        <pre class="m-code">curl -X POST {{ apiUrl }} \
  -H "X-Api-Key: 您的密钥" \
  -d '{"cookie":"..."}'</pre>
      </div>
    </div>

    <!-- 记录列表（简化） -->
    <div class="m-records-card">
      <div class="m-records-header">求解记录</div>
      <div v-if="loading" class="m-loading">加载中...</div>
      <div v-else-if="rows.length === 0" class="m-empty">暂无记录</div>
      <div v-else class="m-record-list">
        <div v-for="r in rows" :key="r.request_id" class="m-record-item" @click="detail = r">
          <div class="m-record-top">
            <span :class="['m-status-tag', `m-status-${r.status}`]">{{ statusText(r.status) }}</span>
            <span class="m-record-time">{{ r.created_at }}</span>
          </div>
          <div class="m-record-mid">
            <span>{{ r.request_id }}</span>
            <span class="m-token">{{ r.token_charged }} Token</span>
          </div>
          <div class="m-record-fail" v-if="r.failure_reason">{{ r.failure_reason }}</div>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="detail" class="m-detail-mask" @click.self="detail = null">
      <div class="m-detail-panel">
        <div class="m-detail-header">
          <span>记录详情</span>
          <button @click="detail = null">×</button>
        </div>
        <div class="m-detail-body">
          <div class="m-detail-row"><span>记录编号</span><b>{{ detail.request_id }}</b></div>
          <div class="m-detail-row"><span>状态</span><b>{{ statusText(detail.status) }}</b></div>
          <div class="m-detail-row"><span>失败原因</span><b>{{ detail.failure_reason || '—' }}</b></div>
          <div class="m-detail-row"><span>耗时</span><b>{{ detail.duration_ms ? detail.duration_ms + 'ms' : '—' }}</b></div>
          <div class="m-detail-row"><span>Token消耗</span><b>{{ detail.token_charged }}</b></div>
          <div class="m-detail-row" v-if="detail.error_message">
            <span>错误详情</span>
            <pre>{{ detail.error_message }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getApiCredential, getApiOverview, getApiRecords } from '../api/apiSliderSolve.js'

defineEmits(['navigate', 'force-desktop', 'back'])

const credential = ref(null)
const overview = ref({})
const rows = ref([])
const loading = ref(false)
const detail = ref(null)
const docExpanded = ref(false)

const apiUrl = computed(() => {
  if (typeof window !== 'undefined') return `${window.location.origin}/api/v1/slider/solve`
  return '/api/v1/slider/solve'
})
const fullKey = computed(() => credential.value?.api_key_plain || '')

async function loadAll() {
  loading.value = true
  try {
    const [cred, ov, recs] = await Promise.all([
      getApiCredential(),
      getApiOverview(),
      getApiRecords({ page: 1, pageSize: 20 }),
    ])
    credential.value = cred?.data || null
    overview.value = ov?.data || {}
    const payload = recs?.data || {}
    rows.value = payload.list || payload.records || []
  } catch (e) {
    console.error('load failed', e)
  } finally {
    loading.value = false
  }
}

async function copy(text, label) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: `${label}已复制` } }))
  } catch {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '复制失败', isError: true } }))
  }
}

function statusText(status) {
  const map = { success: '成功', fail: '失败', timeout: '超时', precheck_rejected: '预检验拒绝', retrying: '处理中', queued: '处理中' }
  return map[status] || status
}

onMounted(loadAll)
</script>

<style scoped>
.m-api-slider { padding: var(--m-space-3) var(--m-space-4) var(--m-space-8); }
.m-api-header h1 { font-size: var(--m-font-size-h1); font-weight: var(--m-font-weight-extrabold); color: var(--m-color-text-primary); margin: 0 0 var(--m-space-1); }
.m-api-header p { font-size: var(--m-font-size-body-sm); color: var(--m-color-text-tertiary); margin: 0 0 var(--m-space-4); }
.m-overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--m-space-3); margin-bottom: var(--m-space-4); }
.m-overview-card { background: var(--m-color-bg-card); border-radius: var(--m-radius-xl); padding: var(--m-space-4); box-shadow: var(--m-shadow-xs); position: relative; }
.m-card-label { font-size: var(--m-font-size-tiny); color: var(--m-color-text-tertiary); margin-bottom: var(--m-space-1); }
.m-card-value { font-size: var(--m-font-size-h3); font-weight: var(--m-font-weight-bold); color: var(--m-color-text-primary); word-break: break-all; }
.m-card-value-sm { font-size: var(--m-font-size-body-sm); }
.m-mini-btn { border: 0; background: var(--m-color-bg-hover); color: var(--m-color-primary); border-radius: var(--m-radius-lg); padding: var(--m-space-1) var(--m-space-3); font-size: var(--m-font-size-tiny); margin-top: var(--m-space-2); font-weight: var(--m-font-weight-semibold); cursor: pointer; transition: background 0.15s ease; }
.m-mini-btn:active { background: var(--m-color-bg-subtle); }
.m-mini-btn-primary { background: var(--m-color-primary); color: var(--m-color-text-inverse); }
.m-mini-btn-primary:active { background: var(--m-color-primary-hover); }
.m-notice-card { background: var(--m-color-info-bg); border-radius: var(--m-radius-xl); padding: var(--m-space-4); margin-bottom: var(--m-space-4); box-shadow: var(--m-shadow-xs); }
.m-notice-item { font-size: var(--m-font-size-body-sm); color: var(--m-color-text-secondary); line-height: var(--m-line-height-relaxed); padding: var(--m-space-1) 0; }
.m-notice-item strong { color: var(--m-color-text-primary); font-weight: var(--m-font-weight-semibold); }
.m-doc-card { background: var(--m-color-bg-card); border-radius: var(--m-radius-xl); margin-bottom: var(--m-space-4); overflow: hidden; box-shadow: var(--m-shadow-xs); }
.m-doc-toggle { display: flex; justify-content: space-between; align-items: center; padding: var(--m-space-4); font-size: var(--m-font-size-body); color: var(--m-color-text-primary); font-weight: var(--m-font-weight-semibold); cursor: pointer; }
.m-doc-body { padding: 0 var(--m-space-4) var(--m-space-4); font-size: var(--m-font-size-body-sm); color: var(--m-color-text-secondary); }
.m-doc-body p { margin: var(--m-space-2) 0; }
.m-code { background: var(--m-color-bg-subtle); padding: var(--m-space-3); border-radius: var(--m-radius-lg); font-size: var(--m-font-size-tiny); overflow-x: auto; line-height: var(--m-line-height-relaxed); }
.m-records-card { background: var(--m-color-bg-card); border-radius: var(--m-radius-xl); padding: var(--m-space-4); box-shadow: var(--m-shadow-xs); }
.m-records-header { font-size: var(--m-font-size-body); font-weight: var(--m-font-weight-semibold); margin-bottom: var(--m-space-3); color: var(--m-color-text-primary); }
.m-loading, .m-empty { text-align: center; color: var(--m-color-text-tertiary); padding: var(--m-space-6); font-size: var(--m-font-size-body-sm); }
.m-record-item { padding: var(--m-space-3) 0; border-bottom: 1px solid var(--m-color-border-light); }
.m-record-item:last-child { border-bottom: none; }
.m-record-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--m-space-2); }
.m-status-tag { font-size: var(--m-font-size-tiny); padding: 2px var(--m-space-2); border-radius: var(--m-radius-sm); background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); font-weight: var(--m-font-weight-semibold); }
.m-status-success { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-status-fail { background: var(--m-color-danger-bg); color: var(--m-color-danger); }
.m-status-timeout { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-status-precheck_rejected { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-status-retrying, .m-status-queued { background: var(--m-color-primary-bg); color: var(--m-color-primary); }
.m-record-time { font-size: var(--m-font-size-tiny); color: var(--m-color-text-tertiary); }
.m-record-mid { display: flex; justify-content: space-between; align-items: center; font-size: var(--m-font-size-body-sm); color: var(--m-color-text-primary); }
.m-token { color: var(--m-color-primary); font-weight: var(--m-font-weight-semibold); }
.m-record-fail { font-size: var(--m-font-size-tiny); color: var(--m-color-danger); margin-top: var(--m-space-1); }
.m-detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 100; padding: var(--m-space-4); }
.m-detail-panel { background: var(--m-color-bg-card); border-radius: var(--m-radius-xl); width: 100%; max-width: 360px; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column; box-shadow: var(--m-shadow-xs); }
.m-detail-header { display: flex; justify-content: space-between; align-items: center; padding: var(--m-space-4); border-bottom: 1px solid var(--m-color-border-light); font-size: var(--m-font-size-body); font-weight: var(--m-font-weight-semibold); color: var(--m-color-text-primary); }
.m-detail-header button { background: none; border: none; font-size: 22px; color: var(--m-color-text-tertiary); cursor: pointer; line-height: 1; padding: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--m-radius-lg); transition: background 0.15s ease; }
.m-detail-header button:active { background: var(--m-color-bg-hover); }
.m-detail-body { padding: var(--m-space-4); overflow-y: auto; }
.m-detail-row { display: flex; justify-content: space-between; gap: var(--m-space-4); padding: var(--m-space-2) 0; font-size: var(--m-font-size-body-sm); border-bottom: 1px solid var(--m-color-border-light); }
.m-detail-row:last-child { border-bottom: none; }
.m-detail-row span { color: var(--m-color-text-tertiary); flex-shrink: 0; }
.m-detail-row b { color: var(--m-color-text-primary); font-weight: var(--m-font-weight-medium); text-align: right; word-break: break-all; }
.m-detail-row pre { margin: var(--m-space-1) 0 0; background: var(--m-color-bg-subtle); padding: var(--m-space-3); border-radius: var(--m-radius-lg); font-size: var(--m-font-size-tiny); white-space: pre-wrap; word-break: break-word; width: 100%; line-height: var(--m-line-height-relaxed); }
</style>
