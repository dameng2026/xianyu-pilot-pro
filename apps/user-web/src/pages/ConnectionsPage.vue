<template>
  <div class="grid wide-right">
    <div>
      <div v-if="loadError" class="global-notice error">连接列表加载失败：{{ loadError }}</div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="notice" class="global-notice success">{{ notice }}</div>
      <div class="grid stat-grid">
        <StatCard title="账号总数" :value="metricValue(connectionsAvailable, total)" change="本页统计" icon="account" />
        <StatCard title="在线连接数" :value="metricValue(connectionCountsAvailable, onlineCount)" change="本页统计" icon="product" color="green" />
        <StatCard title="离线连接数" :value="metricValue(connectionCountsAvailable, offlineCount)" change="本页统计" icon="settings" color="orange" />
        <StatCard title="需要验证" :value="metricValue(statusCountsAvailable, captchaCount)" change="本页统计" icon="data" color="purple" />
        <StatCard title="Cookie正常" :value="metricValue(cookieCountsAvailable, cookieOkCount)" change="本页统计" icon="shield" color="green" />
        <StatCard title="异常" :value="metricValue(cookieCountsAvailable, errorCount)" change="本页统计" icon="warning" color="red" />
      </div>
      <CardPanel :title="`账号连接列表（${connectionsAvailable ? rows.length : '—'}）`">
        <div class="toolbar">
          <select v-model="statusFilter" class="input" style="max-width:150px" :disabled="!connectionsAvailable">
            <option value="all">全部状态</option>
            <option value="online">仅在线</option>
            <option value="offline">仅离线</option>
            <option value="warning">Cookie/验证异常</option>
          </select>
          <input v-model="keyword" class="input large" placeholder="搜索 账号昵称/用户名" :disabled="!connectionsAvailable">
          <AppButton :disabled="loading" @click="load">{{ loading ? '加载中...' : (connectionsAvailable ? '刷新' : '重试') }}</AppButton>
        </div>
        <div v-if="!connectionsAvailable" style="padding:12px 0 24px;text-align:center">
          <EmptyState icon="⚠" title="连接数据暂不可用" :description="loadError || '正在加载账号连接数据，请稍候。'" />
        </div>
        <BaseTable v-else :columns="cols" :rows="filteredRows">
          <template #info="{row}"><div class="product-cell"><img v-if="row.avatar" :src="row.avatar" class="avatar small" alt=""><div v-else class="avatar small"></div><div><strong>{{ row.name }}</strong><em>{{ row.user }}</em></div></div></template>
          <template #cookie="{row}"><Badge :type="row.cookieType">{{ row.cookie }}</Badge></template>
          <template #ws="{row}"><div><Badge :type="connectionBadgeType(row)">{{ row.ws }}</Badge><Badge v-if="captchaSolveBadge(row.id)" :type="captchaSolveBadge(row.id).color" class="solve-badge">{{ captchaSolveBadge(row.id).text }}</Badge><button v-if="captchaSolveBadge(row.id)?.color === 'red'" class="link solve-retry-btn" :disabled="manualRetryBusy === row.id || isAccountSolving(row.id)" @click="handleManualSolve(row.id)">{{ (manualRetryBusy === row.id || isAccountSolving(row.id)) ? '求解中...' : '重试求解' }}</button><p v-if="row.retrying" class="subtle" style="color:var(--blue);max-width:180px;white-space:normal">⏳ 第 {{ row.retryAttempt }}/{{ row.retryMax }} 次尝试</p><p v-else-if="row.refreshError" class="subtle" style="color:#ef4444;max-width:180px;white-space:normal">⚠ {{ row.refreshError }}</p><p v-else-if="row.phase || row.lastError" class="subtle" style="max-width:180px;white-space:normal">{{ row.lastError || row.phase }}</p></div></template>
          <template #latency="{row}"><b :style="{color:connectionColor(row.connected)}">{{ row.latency }}</b></template>
          <template #auto><Badge type="gray">暂未开放</Badge></template>
          <template #op="{row}">
            <button class="link" :disabled="isBusy(row.id) || row.isRefreshing" @click="handlePrimaryConnectionAction(row)">{{ isBusy(row.id) ? (row.retrying ? '连接中...' : '处理中...') : primaryConnectionActionText(row) }}</button>
            <button class="link" :disabled="isBusy(row.id) || row.isRefreshing" @click="refresh(row)"><span :class="{ spinning: row.isRefreshing }">↻</span></button>
            <button class="link" @click="select(row)">详情</button>
          </template>
        </BaseTable><Pagination v-if="connectionsAvailable" :total="total" :current="current" :page-size="pageSize" @page-change="goPage" />
      </CardPanel>
      <div class="grid two-col" style="margin-top:16px"><CardPanel title="实时连接日志"><EmptyState v-if="logs.length===0" icon="📡" title="暂无连接日志" description="本次打开页面后产生的连接、断开、重连记录将在此显示。" /><div v-for="l in logs" :key="l.text+l.time" class="option-line"><span><i class="dot"></i>{{ l.text }}</span><span class="subtle">{{ l.time }}</span></div></CardPanel><CardPanel title="异常告警列表"><EmptyState v-if="!connectionsAvailable" icon="⚠" title="告警状态不可用" description="连接列表加载成功后才能判断当前告警。" /><EmptyState v-else-if="alerts.length===0" icon="✓" title="当前未发现异常" description="仅表示本次已返回的连接状态中没有发现异常。" /><div v-for="e in alerts" :key="e.id" class="option-line"><span><i class="dot orange"></i>{{ e.text }}</span><AppButton @click="handleAlert(e)">处理</AppButton></div></CardPanel></div>
    </div>
    <div class="right-drawer">
      <div style="display:flex;justify-content:space-between"><h3>连接详情</h3><button class="link" @click="selected = null">×</button></div>
      <EmptyState v-if="!connectionsAvailable" icon="⚠" title="连接详情不可用" description="请先重试加载左侧连接列表。" />
      <template v-else-if="selected">
        <div class="product-cell"><img v-if="selected.avatar" :src="selected.avatar" class="avatar" alt=""><div v-else class="avatar"></div><div><strong>{{ selected.name }} <Badge type="blue">账号</Badge></strong><p class="subtle">{{ selected.user }}</p></div><b :style="{marginLeft:'auto',color:connectionColor(selected.connected)}">{{ selected.ws }}</b></div>
        <div class="donut-row" style="margin:22px 0"><div class="health-summary-card"><div class="health-summary-title">实时状态</div><div class="health-summary-desc">暂未提供综合健康评分</div></div><div class="donut-legend"><div><i :style="{background:connectionColor(selected.connected)}"></i><span>WebSocket</span><b>{{ selected.ws }}</b></div><div><i :style="{background:connectionColor(selected.connected)}"></i><span>心跳状态</span><b>{{ selected.heartbeat }}</b></div><div><i :style="{background:badgeColor(selected.cookieType)}"></i><span>Cookie</span><b>{{ selected.cookie }}</b></div><div><i :style="{background:selected.refreshError ? '#f59e0b' : '#94a3b8'}"></i><span>状态</span><b>{{ selected.lastError || selected.status || selected.phase || '状态未知' }}</b></div></div></div>
        <CardPanel title="连接信息"><div class="option-line"><span>账号 ID</span><b>{{ selected.id }}</b></div><div class="option-line"><span>Cookie 状态</span><b>{{ selected.cookie }}</b></div><div class="option-line"><span>连接阶段</span><b>{{ selected.phase || '-' }}</b></div><div class="option-line"><span>最近错误</span><b v-if="selected.refreshError" style="color:#ef4444">{{ selected.refreshError }}</b><b v-else>{{ selected.lastError || '-' }}</b></div><div class="option-line"><span>WS Token</span><b>{{ selected.wsTokenStatus || '-' }}</b></div><div class="option-line"><span>最近消息</span><b>{{ selected.last }}</b></div><div v-if="selected.refreshError" class="option-line"><span>操作</span><AppButton size="small" @click="refresh(selected)">重新刷新状态</AppButton></div></CardPanel>
        <div class="grid" style="grid-template-columns:repeat(2,1fr);margin:16px 0">
          <AppButton type="primary" :disabled="isBusy(selected.id)" @click="handlePrimaryConnectionAction(selected)">{{ primaryConnectionActionText(selected) }}</AppButton>
          <AppButton type="danger" :disabled="isBusy(selected.id) || selected.connected !== true" @click="stop(selected)">断开连接</AppButton>
          <AppButton :disabled="isBusy(selected.id)" @click="refreshCookieAction(selected)">刷新 Cookie</AppButton>
          <AppButton :disabled="isBusy(selected.id)" @click="checkLoginAction(selected)">检查登录</AppButton>
        </div>
        <CardPanel title="重连策略"><div class="option-line"><span>前端策略</span><Badge>手动控制</Badge></div><div class="option-line"><span>验证码</span><b>{{ selected.captcha || '-' }}</b></div><div class="option-line"><span>接口状态</span><b>{{ selected.status || '-' }}</b></div></CardPanel>
      </template>
      <EmptyState v-else icon="👈" title="请选择一个连接" description="从左侧列表选择账号，查看连接详情、重连策略和实时状态。" />
    </div>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StatCard from '../components/StatCard.vue';import CardPanel from '../components/CardPanel.vue';import BaseTable from '../components/BaseTable.vue';import Badge from '../components/Badge.vue';import AppButton from '../components/AppButton.vue';import Pagination from '../components/Pagination.vue';import EmptyState from '../components/EmptyState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { globalConfirm } from '../composables/confirmState.js'
import { useDebouncedRef } from '../composables/useDebouncedRef.js'
import { checkLogin, refreshCookie, startWebSocket, stopWebSocket, websocketStatus } from '../api/websocket.js'
import { accountCookieBadgeType, accountCookieLabel, accountWsConnectionState } from '../utils/accountAuth.js'
import { accountName } from '../utils/format.js'
import { useCaptchaSolver } from '../composables/useCaptchaSolver.js'

const { solveStates, isAccountSolving, getAccountSolveStatus, solveManually } = useCaptchaSolver()

const cols=[{key:'info',title:'账号信息'},{key:'cookie',title:'Cookie状态'},{key:'ws',title:'WS状态'},{key:'heartbeat',title:'心跳'},{key:'latency',title:'延迟'},{key:'last',title:'最近消息时间'},{key:'auto',title:'自动重连'},{key:'proxy',title:'代理'},{key:'op',title:'操作'}]
const accounts = ref([])
const statusMap = ref({})
const selected = ref(null)
const keyword = ref('')
const debouncedKeyword = useDebouncedRef(keyword, 300)
const statusFilter = ref('all')
const error = ref('')
const loadError = ref('')
const connectionsAvailable = ref(false)
const current = ref(1)
const pageSize = ref(20)
const total = ref(0)
const notice = ref('')
const loading = ref(false)
const logs = ref([])
const busyMap = ref({})

// 连接重试状态追踪
const retryMap = ref({})  // { [id]: { attempt, max, phase, message } }
// 刷新状态追踪
const refreshingMap = ref({})  // { [id]: true/false }
// 刷新错误追踪
const refreshErrorMap = ref({})  // { [id]: errorMessage }
// 重试间隔（毫秒）
const RETRY_INTERVAL = 2000
// 最大重试次数
const MAX_RETRIES = 3
const rows = computed(() => accounts.value.map(a => {
  const s = statusMap.value[a.id] || {}
  const phase = s.phase || s.status || ''
  const lastError = s.lastError || s.error || ''
  const retry = retryMap.value[a.id]
  const isRefreshing = !!refreshingMap.value[a.id]
  const refreshErr = refreshErrorMap.value[a.id]
  const connected = accountWsConnectionState(a, s)
  const cookieText = accountCookieLabel(a, s)
  const cookieType = accountCookieBadgeType(a, s)

  // 判断 WS 状态文本
  let wsText
  if (isRefreshing) {
    wsText = '刷新中...'
  } else if (retry?.phase === 'retrying') {
    wsText = `连接中 (${retry.attempt}/${retry.max})`
  } else if (connected === true) {
    wsText = '连接中'
  } else if (lastError) {
    wsText = '异常'
  } else if (['starting','refresh_token','connecting','registering','syncing'].includes(phase)) {
    wsText = '启动中'
  } else if (connected === false) {
    wsText = '断开'
  } else {
    wsText = '状态未知'
  }

  return { id:a.id, raw:a, avatar:a.avatarUrl || a.avatar, name:accountName(a), user:a.externalUid || a.unb || a.loginUsername || `account_${a.id}`, cookie:cookieText, cookieType, connected, ws:wsText, heartbeat:connected === true ? '正常' : connected === false ? '停止' : '状态未知', latency:connected === true ? '在线' : connected === false ? '离线' : '—', last:s.lastMessageTime || s.last || '-', proxy:a.proxyHost || '-', status:s.status, phase, lastError, captcha:s.captchaStatus, wsTokenStatus:s.wsTokenStatus, isRefreshing, refreshError: refreshErr, retrying: retry?.phase === 'retrying', retryAttempt: retry?.attempt || 0, retryMax: retry?.max || 0 }
}))
const filteredRows = computed(() => rows.value.filter(r => {
  const kw = debouncedKeyword.value.trim().toLowerCase()
  if (kw && !JSON.stringify(r).toLowerCase().includes(kw)) return false
  if (statusFilter.value === 'online') return r.connected === true
  if (statusFilter.value === 'offline') return r.connected === false
  if (statusFilter.value === 'warning') return r.cookieType !== 'green' || Boolean(r.refreshError) || String(r.status || '').includes('验证')
  return true
}))
const onlineCount = computed(() => rows.value.filter(r=>r.connected === true).length)
const offlineCount = computed(() => rows.value.filter(r=>r.connected === false).length)
const connectionCountsAvailable = computed(() => connectionsAvailable.value && rows.value.every(r => typeof r.connected === 'boolean'))
const statusCountsAvailable = computed(() => connectionsAvailable.value && rows.value.every(r => !r.refreshError))
const cookieCountsAvailable = computed(() => connectionsAvailable.value && rows.value.every(r => r.cookieType !== 'gray'))
const captchaCount = computed(() => rows.value.filter(r=>String(r.status||'').includes('验证码') || r.raw.status === -2).length)
const cookieOkCount = computed(() => rows.value.filter(r => r.cookieType === 'green').length)
const errorCount = computed(() => rows.value.filter(r => ['red', 'orange'].includes(r.cookieType)).length)
const alerts = computed(() => rows.value
  .filter(r => r.connected !== true || r.cookieType !== 'green' || r.refreshError)
  .map(r => {
    let reason = '账号登录异常'
    if (r.refreshError) reason = '连接状态获取失败'
    else if (r.connected === null) reason = '连接状态未知'
    else if (r.connected === false) reason = 'WebSocket 断开'
    else if (r.cookieType === 'gray') reason = 'Cookie 状态未知'
    return { id:r.id, row:r, text:`${r.name}：${reason}` }
  }).slice(0,5))
function metricValue(available, value){ return available ? value : '—' }
function connectionColor(state){ return state === true ? '#16bf78' : state === false ? '#ef4444' : '#94a3b8' }
function connectionBadgeType(row){ return row.connected === true ? 'green' : row.refreshError || row.lastError ? 'orange' : row.connected === false ? 'red' : 'gray' }
function badgeColor(type){ return ({ green:'#16bf78', red:'#ef4444', orange:'#f59e0b', blue:'#3b82f6' }[type] || '#94a3b8') }
function primaryConnectionActionText(row){ return row?.connected === true ? '断开' : row?.connected === false ? '启动' : '重试状态' }

function captchaSolveBadge(accountId) {
  const state = getAccountSolveStatus(accountId)
  if (!state) return null
  if (state.status === 'retrying') return { text: '滑块求解中', color: 'orange' }
  if (state.status === 'success') return { text: '求解成功', color: 'green' }
  if (state.status === 'fail') return { text: '求解失败', color: 'red' }
  return null
}

const manualRetryBusy = ref(null)
async function handleManualSolve(accountId) {
  if (!accountId || manualRetryBusy.value === accountId || isAccountSolving(accountId)) return
  manualRetryBusy.value = accountId
  try {
    // 根据当前求解状态判断场景：已有失败状态时为"重试求解"，否则为"手动触发"
    const state = getAccountSolveStatus(accountId)
    const scene = state && state.status === 'fail' ? 'manual_retry' : 'manual'
    await solveManually(accountId, scene, {
      openReason: '用户在连接管理页点击滑块求解按钮',
      solveReason: scene === 'manual_retry'
        ? '用户在连接管理页点击重试求解（上次求解失败）'
        : '用户在连接管理页主动触发滑块求解',
    })
  } finally {
    manualRetryBusy.value = null
  }
}
function log(text){ logs.value.unshift({text,time:new Date().toLocaleTimeString('zh-CN',{hour12:false})}); logs.value=logs.value.slice(0,12) }
function showNotice(text){ notice.value=text; setTimeout(()=>{ if(notice.value===text) notice.value='' }, 3500) }
function setBusy(id, busy){ busyMap.value = { ...busyMap.value, [id]: busy } }
function isBusy(id){ return !!busyMap.value[id] }
function syncSelected(accountId){ const latest = rows.value.find(r=>r.id===accountId); if(latest) selected.value = latest }
function patchAccountAuth(accountId, patch = {}) {
  if (!accountId) return
  const account = accounts.value.find(item => item.id === accountId)
  if (!account) return
  Object.assign(account, patch)
  syncSelected(accountId)
}
function requireConnectionStatus(res, label = '连接状态') {
  const data = res?.data
  if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.connected !== 'boolean') {
    throw new Error(`${label}响应格式异常`)
  }
  return data
}
async function refreshRowLoginStateBeforeConnect(row) {
  if (!row?.id) return { auth: null, data: {} }
  const res = await checkLogin(row.id)
  const data = res?.data
  const auth = data?.status
  if (!data || typeof data !== 'object' || Array.isArray(data) || !auth || typeof auth !== 'object' || Array.isArray(auth) || typeof auth.usable !== 'boolean') {
    throw new Error('登录检查响应格式异常')
  }
  patchAccountAuth(row.id, {
    cookieStatus: auth.cookieStatus,
    authUsable: auth.usable,
    loginStatusCode: auth.loginStatusCode,
    loginStatusMessage: auth.loginStatusMessage,
    loginCheckTime: auth.checkedAt,
  })
  return { auth, data }
}
async function load(){
  loading.value = true
  error.value=''
  loadError.value=''
  connectionsAvailable.value = false
  accounts.value = []
  statusMap.value = {}
  refreshErrorMap.value = {}
  selected.value = null
  total.value = 0
  try {
    const res=await getLiteAccounts({ current: current.value, size: pageSize.value })
    const data = res?.data
    const records = Array.isArray(data)
      ? data
      : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(records)) throw new Error('账号连接列表响应格式异常')
    accounts.value=records
    const rawTotal = data?.total ?? data?.totalCount ?? data?.count ?? records.length
    const parsedTotal = Number(rawTotal)
    total.value = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : records.length
    await Promise.allSettled(accounts.value.map(a=>refresh({id:a.id,name:accountName(a)}, { silent: true, skipRefreshState: true })))
    connectionsAvailable.value = true
    if(rows.value.length) selected.value=rows.value[0]
    return true
  } catch(e){
    loadError.value=e?.message||'加载失败，请稍后重试'
    return false
  }
  finally { loading.value = false }
}
function goPage(p) {
  current.value = p
  load()
}
async function refresh(row, { silent = false, skipRefreshState = false } = {}){
  const id = typeof row === 'object' ? row.id : row
  const name = typeof row === 'object' ? (row.name || row.id) : id

  // 批量加载时不显示"刷新中"状态（由 loading 状态统一指示）
  if (!skipRefreshState) {
    refreshingMap.value = { ...refreshingMap.value, [id]: true }
  }
  // 清除之前的刷新错误
  delete refreshErrorMap.value[id]
  refreshErrorMap.value = { ...refreshErrorMap.value }

  try {
    const res = await websocketStatus(id)
    const data = requireConnectionStatus(res)
    statusMap.value = { ...statusMap.value, [id]: data }
    if (!silent) {
      const stateText = data.connected === true ? 'connected' : data.connected === false ? 'offline' : 'unknown'
      log(`${name} 状态刷新完成：${data.lastError || data.phase || stateText}`)
    }
    // 刷新成功，清除错误
    delete refreshErrorMap.value[id]
    refreshErrorMap.value = { ...refreshErrorMap.value }
    return data
  } catch(e) {
    statusMap.value = { ...statusMap.value, [id]: { connected: null, status: '状态未知', lastError: e.message } }
    refreshErrorMap.value = { ...refreshErrorMap.value, [id]: e.message || '状态刷新失败' }
    if (!silent) {
      log(`${name} 状态刷新失败：${e.message}`)
    }
    throw e
  } finally {
    if (!skipRefreshState) {
      refreshingMap.value = { ...refreshingMap.value, [id]: false }
    }
  }
}
function select(row){ selected.value=row }
async function toggle(row){
  if (!row?.id || isBusy(row.id)) return
  if (!connectionsAvailable.value || typeof row.connected !== 'boolean') {
    error.value = '连接状态未知，已阻止启动或断开操作；请先刷新状态。'
    return
  }
  setBusy(row.id, true); error.value=''
  try {
    if(row.connected === true) {
      // === 断开连接 ===
      await stopWebSocket(row.id)
      showNotice(`${row.name} 已提交断开`)
      log(`${row.name} 断开连接`)
      await new Promise(r => setTimeout(r, 300))
      await refresh(row, { silent: true })
      syncSelected(row.id)
    } else {
      // === 连接（带自动重试） ===
      let lastError = null
      let connected = false
      const { auth } = await refreshRowLoginStateBeforeConnect(row)
      if (auth?.usable === false) {
        showNotice(auth.loginStatusMessage || '统一登录校验暂未通过，继续尝试恢复连接...')
      }

      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        // 更新重试状态
        retryMap.value = {
          ...retryMap.value,
          [row.id]: { attempt, max: MAX_RETRIES, phase: 'retrying', message: `连接中 (${attempt}/${MAX_RETRIES})` }
        }

        try {
          if (attempt > 1) {
            log(`${row.name} 第 ${attempt} 次重试连接...`)
          }

          const res = await startWebSocket(row.id, { forceReconnect: true })
          const data = requireConnectionStatus(res, '连接启动')
          statusMap.value = { ...statusMap.value, [row.id]: { ...(statusMap.value[row.id]||{}), ...data } }

          if (data.connected === true) {
            // 连接成功
            connected = true
            retryMap.value = { ...retryMap.value, [row.id]: { attempt, max: MAX_RETRIES, phase: 'success' } }
            showNotice(`${row.name}：WS 连接已就绪，正在接收消息`)
            log(`${row.name} 连接成功（第 ${attempt} 次尝试）`)
            break
          }

          // 后端未返回 connected=true，但也没有报错 → 等待后检查状态
          lastError = data.message || data.lastError || data.error || '服务返回未连接状态'
          if (attempt < MAX_RETRIES) {
            log(`${row.name} 第 ${attempt} 次尝试：${lastError}，${RETRY_INTERVAL/1000}秒后重试...`)
            await new Promise(r => setTimeout(r, RETRY_INTERVAL))

            // 重试前先刷新状态检查是否已经从其他渠道连接
            try {
              const statusRes = await websocketStatus(row.id)
              const statusData = requireConnectionStatus(statusRes)
              if (statusData.connected === true) {
                statusMap.value = { ...statusMap.value, [row.id]: { ...(statusMap.value[row.id]||{}), ...statusData } }
                connected = true
                retryMap.value = { ...retryMap.value, [row.id]: { attempt, max: MAX_RETRIES, phase: 'success' } }
                showNotice(`${row.name}：WS 连接已就绪`)
                log(`${row.name} 连接成功（状态检查确认）`)
                break
              }
            } catch {
              // The next retry remains authoritative if this status probe fails.
            }
          }
        } catch (e) {
          lastError = e.message || '连接失败'
          if (attempt < MAX_RETRIES) {
            log(`${row.name} 第 ${attempt} 次重试失败：${lastError}，${RETRY_INTERVAL/1000}秒后重试...`)
            await new Promise(r => setTimeout(r, RETRY_INTERVAL))
          } else {
            log(`${row.name} 所有重试均已失败：${lastError}`)
          }
        }
      }

      // 最终状态确认
      if (!connected) {
        try {
          await refresh(row, { silent: true })
        } catch {
          // Preserve the original connection failure when final refresh also fails.
        }
        const finalStatus = statusMap.value[row.id] || {}
        const errMsg = lastError || finalStatus.lastError || '多次重试后连接仍未成功'
        error.value = `${row.name} 连接失败：${errMsg}`
        showNotice(`${row.name} 连接失败，请检查账号状态后重试`)
        log(`${row.name} 连接失败：${errMsg}（已重试 ${MAX_RETRIES} 次）`)
      }

      // 清除重试状态
      retryMap.value = { ...retryMap.value, [row.id]: undefined }
      syncSelected(row.id)
    }
  } catch(e){
    error.value = e.message || '连接操作失败'
  }
  finally { setBusy(row.id, false) }
}
async function stop(row){
  if (!row?.id || isBusy(row.id)) return
  if (!connectionsAvailable.value || row.connected !== true) {
    error.value = '当前未确认连接在线，已阻止断开操作；请先刷新状态。'
    return
  }
  setBusy(row.id, true)
  error.value = ''
  try {
    log(`${row.name} 正在断开连接...`)
    await stopWebSocket(row.id)
    // 等待短暂时间确保后端处理完成
    await new Promise(r => setTimeout(r, 500))
    const refreshed = await refresh(row, { silent: true })
    syncSelected(row.id)
    if (refreshed.connected === false) {
      showNotice(`${row.name} 已断开`)
      log(`${row.name} 断开成功，状态已确认`)
    } else {
      showNotice(`${row.name} 断开请求已提交，当前仍显示在线，请稍后刷新确认`)
      log(`${row.name} 断开请求已提交，但服务端状态尚未确认断开`)
    }
  } catch(e){
    const errMsg = e.message || '断开连接失败'
    error.value = errMsg
    log(`${row.name} 断开失败：${errMsg}`)
    // 即使失败也刷新状态
    try { await refresh(row, { silent: true }) } catch {
      // Preserve the disconnect error; status refresh is best-effort here.
    }
  }
  finally { setBusy(row.id, false) }
}
async function refreshCookieAction(row){
  if (!row?.id || isBusy(row.id)) return
  setBusy(row.id, true)
  try {
    await refreshCookie(row.id)
    if (!await load()) {
      error.value = 'Cookie 刷新已提交，但连接列表刷新失败，请重试加载确认最新状态。'
      return
    }
    await refresh(row, { silent: true })
    syncSelected(row.id)
    log(`${row.name} Cookie 刷新完成`)
    showNotice('Cookie 刷新完成')
  } catch(e){ error.value=e.message }
  finally { setBusy(row.id, false) }
}
async function checkLoginAction(row){
  if (!row?.id || isBusy(row.id)) return
  setBusy(row.id, true)
  try {
    const { auth, data } = await refreshRowLoginStateBeforeConnect(row)
    if (!await load()) {
      error.value = '登录检查已完成，但连接列表刷新失败，请重试加载确认最新状态。'
      return
    }
    await refresh(row, { silent: true })
    syncSelected(row.id)
    showNotice(auth.loginStatusMessage || data?.message || '检查完成')
  } catch(e){ error.value=e.message }
  finally { setBusy(row.id, false) }
}
async function handlePrimaryConnectionAction(row){
  if (!row?.id) return
  if (row.connected === null) {
    try { await refresh(row) } catch { /* refresh exposes the row-level error */ }
    syncSelected(row.id)
    return
  }
  await toggle(row)
}
async function batchStart(){
  if (!connectionsAvailable.value) return showNotice('连接列表不可用，请先重试加载')
  const targets = filteredRows.value.filter(r=>r.connected === false)
  if(!targets.length) return showNotice('当前没有需要启动的离线连接')
  if(!await globalConfirm.confirm(`确认批量启动 ${targets.length} 个连接？`)) return
  for (const row of targets) await toggle(row)
}
async function batchStop(){
  if (!connectionsAvailable.value) return showNotice('连接列表不可用，请先重试加载')
  const targets = filteredRows.value.filter(r=>r.connected === true)
  if(!targets.length) return showNotice('当前没有在线连接')
  if(!await globalConfirm.confirm(`确认批量断开 ${targets.length} 个连接？`)) return
  for (const row of targets) await stop(row)
}
function handleAlert(alert){
  select(alert.row)
  if (alert.row.connected === null || alert.row.refreshError) handlePrimaryConnectionAction(alert.row)
  else if (alert.row.connected === true) refreshCookieAction(alert.row)
  else toggle(alert.row)
}
function onHeader(e){
  if(e.detail === 'connections-batch-start') batchStart()
  if(e.detail === 'connections-batch-stop') batchStop()
  if(e.detail === 'connections-proxy-settings') showNotice('代理设置入口已预留，请在账号详情或系统设置中维护代理配置')
}
function onSseEvent(e) {
  const event = e.detail
  if (!event || !event.type) return
  if (event.type === 'cookie_status_changed') {
    const accountId = event.accountId
    if (!accountId) return
    const cookieStatus = Number(event.cookieStatus)
    if (![0, 1].includes(cookieStatus)) {
      log(`账号 ${accountId} 收到未知 Cookie 状态，已忽略并等待服务端刷新`)
      return
    }
    const invalid = cookieStatus !== 1
    patchAccountAuth(accountId, {
      cookieStatus,
      authUsable: !invalid,
      loginStatusMessage: event.reason || (invalid ? 'Cookie 已失效，请重新登录闲鱼账号' : '账号登录状态正常'),
      loginStatusCode: invalid ? 'COOKIE_EXPIRED' : 'OK',
    })
    if (invalid) {
      statusMap.value = {
        ...statusMap.value,
        [accountId]: {
          ...(statusMap.value[accountId] || {}),
          connected: false,
          lastError: event.reason || 'Cookie 已失效',
          phase: 'cookie_expired',
          status: 'Cookie 失效',
        }
      }
      log(`账号 ${accountId} Cookie 已失效，连接已断开`)
    } else {
      log(`账号 ${accountId} Cookie 状态已恢复正常`)
    }
  }
}
onMounted(()=>{ window.addEventListener('xya-header-action', onHeader); window.addEventListener('xya-sse-event', onSseEvent); load() })
onBeforeUnmount(()=>{ window.removeEventListener('xya-header-action', onHeader); window.removeEventListener('xya-sse-event', onSseEvent) })
</script>

<style scoped>
.solve-badge {
  margin-left: 4px;
  font-size: 11px;
  line-height: 18px;
}

.solve-retry-btn {
  margin-right: 0;
  margin-left: 4px;
  padding: 0;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
}

.solve-retry-btn:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}
</style>
