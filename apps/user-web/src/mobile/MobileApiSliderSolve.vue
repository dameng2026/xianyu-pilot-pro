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
        <div class="m-card-value">{{ maskedKey }}</div>
        <button class="m-mini-btn" @click="copy(fullKey, '密钥')" v-if="credential?.api_key_plain">复制</button>
      </div>
      <div class="m-overview-card">
        <div class="m-card-label">Token 余额</div>
        <div class="m-card-value">{{ overview.tokenBalance ?? 0 }}</div>
        <button class="m-mini-btn m-mini-btn-primary" @click="$emit('force-desktop', 'profile-recharge')">充值</button>
      </div>
      <div class="m-overview-card">
        <div class="m-card-label">单次价格</div>
        <div class="m-card-value">{{ overview.perCallTokens ?? 5 }} Token</div>
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
  return 'https://api.xianyupilot.com/api/v1/slider/solve'
})
const maskedKey = computed(() => {
  const prefix = credential.value?.api_key_prefix
  return prefix ? `${prefix}••••••••` : '尚未生成'
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
.m-api-slider { padding: 12px 16px 32px; }
.m-api-header h1 { font-size: 20px; font-weight: 600; color: var(--m-color-text, #15213d); margin: 0 0 4px; }
.m-api-header p { font-size: 12px; color: var(--m-color-text-secondary, #72809a); margin: 0 0 16px; }
.m-overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.m-overview-card { background: var(--m-color-bg, #fff); border-radius: 12px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.m-card-label { font-size: 11px; color: var(--m-color-text-secondary, #72809a); margin-bottom: 4px; }
.m-card-value { font-size: 18px; font-weight: 600; color: var(--m-color-text, #15213d); word-break: break-all; }
.m-card-value-sm { font-size: 12px; }
.m-mini-btn { border: 1px solid var(--m-color-primary, #3380ff); background: transparent; color: var(--m-color-primary, #3380ff); border-radius: 6px; padding: 4px 10px; font-size: 11px; margin-top: 6px; }
.m-mini-btn-primary { background: var(--m-color-primary, #3380ff); color: #fff; }
.m-notice-card { background: var(--m-color-info-bg, #e3f2fd); border-radius: 12px; padding: 14px; margin-bottom: 16px; }
.m-notice-item { font-size: 12px; color: var(--m-color-text-secondary, #72809a); line-height: 1.6; padding: 6px 0; }
.m-notice-item strong { color: var(--m-color-text, #15213d); }
.m-doc-card { background: var(--m-color-bg, #fff); border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.m-doc-toggle { display: flex; justify-content: space-between; padding: 14px; font-size: 14px; color: var(--m-color-text, #15213d); }
.m-doc-body { padding: 0 14px 14px; font-size: 12px; color: var(--m-color-text-secondary, #72809a); }
.m-doc-body p { margin: 6px 0; }
.m-code { background: var(--m-color-bg-secondary, #f5f8ff); padding: 10px; border-radius: 6px; font-size: 11px; overflow-x: auto; }
.m-records-card { background: var(--m-color-bg, #fff); border-radius: 12px; padding: 14px; }
.m-records-header { font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.m-loading, .m-empty { text-align: center; color: var(--m-color-text-secondary, #72809a); padding: 20px; font-size: 13px; }
.m-record-item { padding: 10px 0; border-bottom: 1px solid var(--m-color-border, #f0f2f5); }
.m-record-item:last-child { border-bottom: none; }
.m-record-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.m-status-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: var(--m-color-bg-secondary, #f0f2f5); color: var(--m-color-text-secondary, #72809a); }
.m-status-success { background: rgba(22,191,120,0.12); color: #16bf78; }
.m-status-fail { background: rgba(239,68,68,0.12); color: #ef4444; }
.m-status-timeout { background: rgba(255,159,34,0.12); color: #ff9f22; }
.m-status-precheck_rejected { background: rgba(255,159,34,0.12); color: #ff9f22; }
.m-status-retrying, .m-status-queued { background: rgba(51,128,255,0.12); color: #3380ff; }
.m-record-time { font-size: 11px; color: var(--m-color-text-secondary, #72809a); }
.m-record-mid { display: flex; justify-content: space-between; font-size: 12px; color: var(--m-color-text, #15213d); }
.m-token { color: var(--m-color-primary, #3380ff); font-weight: 600; }
.m-record-fail { font-size: 11px; color: #ef4444; margin-top: 4px; }
.m-detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 16px; }
.m-detail-panel { background: var(--m-color-bg, #fff); border-radius: 12px; width: 100%; max-width: 360px; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column; }
.m-detail-header { display: flex; justify-content: space-between; align-items: center; padding: 14px; border-bottom: 1px solid var(--m-color-border, #f0f2f5); font-size: 14px; font-weight: 600; }
.m-detail-header button { background: none; border: none; font-size: 22px; color: var(--m-color-text-secondary, #72809a); cursor: pointer; line-height: 1; }
.m-detail-body { padding: 14px; overflow-y: auto; }
.m-detail-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 13px; border-bottom: 1px solid var(--m-color-border, #f5f6f8); }
.m-detail-row span { color: var(--m-color-text-secondary, #72809a); }
.m-detail-row b { color: var(--m-color-text, #15213d); font-weight: 500; text-align: right; word-break: break-all; }
.m-detail-row pre { margin: 4px 0 0; background: var(--m-color-bg-secondary, #f5f8ff); padding: 8px; border-radius: 6px; font-size: 11px; white-space: pre-wrap; word-break: break-word; width: 100%; }
</style>
