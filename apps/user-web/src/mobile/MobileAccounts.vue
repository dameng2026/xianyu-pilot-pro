<template>
  <div class="m-accounts">
    <div class="m-page-header">
      <h1>闲鱼账号</h1>
      <p class="m-page-sub">管理监控账号状态</p>
    </div>

    <div class="m-acc-stats">
      <div class="m-acc-stat-card">
        <div class="m-acc-stat-icon m-acc-stat-icon-blue">
          <MIcon name="account" :size="20" />
        </div>
        <div class="m-acc-stat-info">
          <div class="m-acc-stat-val">{{ metricText(stats.total) }}</div>
          <div class="m-acc-stat-label">账号总数</div>
        </div>
      </div>
      <div class="m-acc-stat-card">
        <div class="m-acc-stat-icon m-acc-stat-icon-green">
          <MIcon name="wifi" :size="20" />
        </div>
        <div class="m-acc-stat-info">
          <div class="m-acc-stat-val">{{ metricText(stats.online) }}</div>
          <div class="m-acc-stat-label">在线数量</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="m-loading">加载中...</div>

    <MobileUnavailableState v-else-if="loadError" title="账号数据暂时无法加载" :description="loadError" @retry="loadAccounts" />

    <div v-else-if="accounts.length === 0" class="m-empty">
      <div class="m-empty-icon">
        <MIcon name="account" :size="48" />
      </div>
      <div class="m-empty-text">暂无账号</div>
      <div class="m-empty-desc">添加闲鱼账号后将在这里显示</div>
    </div>

    <div v-else class="m-acc-list">
      <div v-for="acc in accounts" :key="acc.id" class="m-acc-card">
        <div class="m-acc-avatar">
          <img
            v-if="acc.avatarUrl || acc.avatar"
            :src="acc.avatarUrl || acc.avatar"
            :alt="accountName(acc)"
            class="m-acc-avatar-img"
            @error="onAvatarError($event, acc)"
          />
          <div v-else class="m-acc-avatar-placeholder">
            <MIcon name="user" :size="26" />
          </div>
        </div>

        <div class="m-acc-body">
          <div class="m-acc-top">
            <div class="m-acc-name">{{ accountName(acc) }}</div>
            <span v-if="accountLevel(acc) && accountLevel(acc) !== '-'" class="m-acc-level">
              <MIcon name="star" :size="11" />
              Lv{{ accountLevel(acc) }}
            </span>
          </div>

          <div class="m-acc-meta">
            <span class="m-acc-uid">UID：{{ acc.uid || acc.externalUid || acc.unb || acc.id || '-' }}</span>
          </div>

          <div v-if="accountArea(acc)" class="m-acc-meta">
            <span class="m-acc-area">
              <MIcon name="globe" :size="11" />
              {{ accountArea(acc) }}
            </span>
          </div>

          <div class="m-acc-tags">
            <span class="m-acc-tag" :class="wsStatusClass(acc)">
              <MIcon name="wifi" :size="11" />
              {{ wsStatusText(acc) }}
            </span>
            <span class="m-acc-tag" :class="cookieStatusClass(acc)">
              <MIcon name="shield" :size="11" />
              {{ cookieStatusText(acc) }}
            </span>
          </div>

          <div v-if="acc.health != null" class="m-acc-health">
            <div class="m-acc-health-row">
              <span class="m-acc-health-label">健康分</span>
              <span class="m-acc-health-val">{{ acc.health }}分</span>
            </div>
            <div class="m-acc-health-bar">
              <div
                class="m-acc-health-progress"
                :class="healthBarClass(acc.health)"
                :style="{ width: healthPercent(acc.health) + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="m-acc-tip">
      <MIcon name="warning" :size="16" />
      <span>账号详细管理与操作建议在PC端完成</span>
      <button class="m-tip-btn" @click="$emit('force-desktop')">进入桌面版</button>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { accountCookieLabel, accountCookieStatus, accountWsConnectionState } from '../utils/accountAuth.js'

defineEmits(['navigate', 'force-desktop', 'back'])

const accounts = ref([])
const loading = ref(true)
const loadError = ref('')
const stats = reactive({ total: null, online: null })

async function loadAccounts() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getLiteAccounts({ page: 1, pageSize: 100 })
    const data = res?.data
    let list = []
    if (data?.records) {
      list = data.records
    } else if (data?.list) {
      list = data.list
    } else if (Array.isArray(data)) {
      list = data
    }
    if (!Array.isArray(data) && !Array.isArray(data?.records) && !Array.isArray(data?.list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    const total = Array.isArray(data) ? list.length : Number(data?.total)
    if (!Number.isSafeInteger(total) || total < list.length) throw new Error('账号总数响应格式异常')
    stats.total = total
    const connectionStates = list.map(a => accountWsConnectionState(a))
    stats.online = connectionStates.some(state => state === null)
      ? null
      : connectionStates.filter(state => state === true).length
  } catch (error) {
    accounts.value = []
    stats.total = null
    stats.online = null
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

function accountName(acc) {
  if (!acc) return '未知账号'
  return acc.name || acc.nickname || acc.displayName || acc.accountNote || `账号${acc.id || ''}`
}

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function accountLevel(acc) {
  if (!acc) return '-'
  const lv = acc.accountLevel || acc.sellerLevel || acc.fishShopLevel || acc.level
  return lv != null && lv !== '' ? lv : '-'
}

function accountArea(acc) {
  if (!acc) return ''
  const province = acc.province
  const city = acc.city
  if (province && city) return `${province} ${city}`
  if (province) return province
  if (city) return city
  if (acc.area) return acc.area
  if (acc.ipLocation) return acc.ipLocation
  return ''
}

function cookieStatusText(acc) {
  if (!acc) return '未知'
  return accountCookieLabel(acc)
}

function cookieStatusClass(acc) {
  if (!acc) return 'm-acc-tag-unknown'
  const cs = accountCookieStatus(acc)
  if (cs === null) return 'm-acc-tag-unknown'
  if (cs === 0) return 'm-acc-tag-red'
  if (cs === 2) return 'm-acc-tag-orange'
  return 'm-acc-tag-green'
}

function wsStatusText(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return '在线'
  if (state === false) return '离线'
  return '状态未知'
}

function wsStatusClass(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return 'm-acc-tag-online'
  if (state === false) return 'm-acc-tag-offline'
  return 'm-acc-tag-unknown'
}

function healthPercent(score) {
  const num = Number(score)
  if (isNaN(num)) return 0
  if (num < 0) return 0
  if (num > 100) return 100
  return num
}

function healthBarClass(score) {
  const num = Number(score)
  if (isNaN(num)) return 'm-acc-health-progress-low'
  if (num >= 80) return 'm-acc-health-progress-high'
  if (num >= 60) return 'm-acc-health-progress-mid'
  return 'm-acc-health-progress-low'
}

function onAvatarError(e, acc) {
  if (acc) {
    acc.avatarUrl = ''
    acc.avatar = ''
  }
}

onMounted(() => {
  loadAccounts()
})
</script>

<style scoped>
.m-accounts {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-page-header { margin-bottom: 16px; }
.m-page-header h1 { margin: 0 0 4px; font-size: 26px; font-weight: 800; color: #15213d; }
.m-page-sub { margin: 0; font-size: 13px; color: #8c98ae; }

.m-acc-stats {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.m-acc-stat-card {
  flex: 1;
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
}
.m-acc-stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-acc-stat-icon-blue {
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
}
.m-acc-stat-icon-green {
  background: linear-gradient(135deg, #e2f8ee, #cdf2df);
  color: #16bf78;
}
.m-acc-stat-info { flex: 1; min-width: 0; }
.m-acc-stat-val { font-size: 22px; font-weight: 800; color: #15213d; line-height: 1.1; }
.m-acc-stat-label { font-size: 12px; color: #8c98ae; margin-top: 3px; }

@media (max-width: 360px) {
  .m-acc-stat-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    padding: 12px;
  }

  .m-acc-stat-val,
  .m-acc-stat-label {
    min-width: 0;
    overflow-wrap: anywhere;
  }
}

.m-loading { text-align: center; padding: 40px; color: #8c98ae; font-size: 14px; }

.m-empty {
  text-align: center;
  padding: 60px 20px;
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-empty-text { font-size: 16px; font-weight: 600; color: #15213d; margin-bottom: 6px; }
.m-empty-desc { font-size: 13px; color: #8c98ae; }

.m-acc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-acc-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
}
.m-acc-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}
.m-acc-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-acc-avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
}
.m-acc-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.m-acc-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-acc-name {
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-acc-level {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
  background: linear-gradient(135deg, #fff4e0, #ffe7c2);
  color: #ff9f22;
  flex-shrink: 0;
}
.m-acc-level :deep(svg) { flex-shrink: 0; }

.m-acc-meta {
  font-size: 12px;
  color: #8c98ae;
  display: flex;
  align-items: center;
  min-width: 0;
}
.m-acc-uid {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  word-break: break-all;
}
.m-acc-area {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.m-acc-area :deep(svg) { flex-shrink: 0; }

.m-acc-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.m-acc-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
}
.m-acc-tag :deep(svg) { flex-shrink: 0; }
.m-acc-tag-online {
  background: rgba(22, 191, 120, 0.12);
  color: #16bf78;
}
.m-acc-tag-offline {
  background: rgba(140, 152, 174, 0.15);
  color: #8c98ae;
}
.m-acc-tag-unknown {
  background: rgba(140, 152, 174, 0.15);
  color: #64748b;
}
.m-acc-tag-green {
  background: rgba(22, 191, 120, 0.12);
  color: #16bf78;
}
.m-acc-tag-red {
  background: rgba(255, 82, 82, 0.12);
  color: #ff5252;
}
.m-acc-tag-orange {
  background: rgba(255, 159, 34, 0.12);
  color: #ff9f22;
}

.m-acc-health {
  margin-top: 4px;
}
.m-acc-health-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.m-acc-health-label { font-size: 11px; color: #8c98ae; }
.m-acc-health-val { font-size: 11px; font-weight: 700; color: #15213d; }
.m-acc-health-bar {
  width: 100%;
  height: 6px;
  background: #f0f4fa;
  border-radius: 100px;
  overflow: hidden;
}
.m-acc-health-progress {
  height: 100%;
  border-radius: 100px;
  transition: width 0.3s ease;
}
.m-acc-health-progress-high { background: linear-gradient(90deg, #16bf78, #2dd58a); }
.m-acc-health-progress-mid { background: linear-gradient(90deg, #ff9f22, #ffb94a); }
.m-acc-health-progress-low { background: linear-gradient(90deg, #ff5252, #ff7a7a); }

.m-acc-tip {
  margin-top: 20px;
  background: #f8faff;
  border-radius: 14px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #72809a;
}
.m-acc-tip :deep(svg) { color: #ff9f22; flex-shrink: 0; }
.m-tip-btn {
  margin-left: auto;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  border: none;
  border-radius: 100px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}

.m-safe-bottom { height: 80px; }
</style>
