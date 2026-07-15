<template>
  <div class="m-auto">
    <div class="m-page-header">
      <h1>自动化</h1>
      <p class="m-page-sub">工作流与自动运营</p>
    </div>

    <!-- 工作流统计卡片 -->
    <div class="m-auto-stats">
      <div class="m-stat-card m-stat-purple">
        <div class="m-stat-icon">
          <MIcon name="workflow" :size="20" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-val">{{ overviewMetric('workflowCount') }}</div>
          <div class="m-stat-label">工作流</div>
        </div>
        <div class="m-stat-extra">启用 {{ overviewMetric('enabledCount') }}</div>
      </div>
      <div class="m-stat-card m-stat-blue">
        <div class="m-stat-icon">
          <MIcon name="activity" :size="20" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-val">{{ overviewMetric('todayExecutionCount') }}</div>
          <div class="m-stat-label">今日执行</div>
        </div>
      </div>
      <div class="m-stat-card m-stat-green">
        <div class="m-stat-icon">
          <MIcon name="shield" :size="20" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-val">{{ overviewMetric('successRate', '%') }}</div>
          <div class="m-stat-label">成功率</div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-if="overviewError" compact title="自动化统计暂时不可用" :description="overviewError" @retry="loadOverview" />

    <!-- 自动化功能 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>自动化功能</h2>
      </div>
      <div class="m-auto-grid">
        <div class="m-auto-item" @click="$emit('force-desktop', { page: 'workflow' })">
          <div class="m-auto-icon m-auto-blue">
            <MIcon name="workflow" :size="26" />
          </div>
          <div class="m-auto-title">工作流</div>
          <div class="m-auto-desc">设计自动化流程</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
        <div class="m-auto-item" @click="$emit('navigate', 'auto-delivery')">
          <div class="m-auto-icon m-auto-green">
            <MIcon name="truck" :size="26" />
          </div>
          <div class="m-auto-title">自动发货</div>
          <div class="m-auto-desc">自动处理订单发货</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
        <div class="m-auto-item" @click="$emit('navigate', 'auto-reply')">
          <div class="m-auto-icon m-auto-purple">
            <MIcon name="reply" :size="26" />
          </div>
          <div class="m-auto-title">自动回复</div>
          <div class="m-auto-desc">买家消息自动回复</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
        <div class="m-auto-item" @click="$emit('navigate', 'scheduled-tasks')">
          <div class="m-auto-icon m-auto-orange">
            <MIcon name="clock" :size="26" />
          </div>
          <div class="m-auto-title">定时任务</div>
          <div class="m-auto-desc">定时执行运营任务</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
      </div>
    </div>

    <!-- 最近执行记录 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>最近执行</h2>
        <button class="m-section-action" :disabled="execLoading" @click="loadExecutions">
          <MIcon name="refresh" :size="14" />刷新
        </button>
      </div>

      <div v-if="execLoading" class="m-loading">
        <div class="m-loading-spinner"></div>
        <span>加载执行记录...</span>
      </div>

      <MobileUnavailableState v-else-if="execError" compact title="执行记录暂时无法加载" :description="execError" @retry="loadExecutions" />

      <div v-else-if="executions.length === 0" class="m-empty-mini">
        <MIcon name="clock" :size="32" />
        <span>暂无执行记录</span>
      </div>

      <div v-else class="m-exec-list">
        <div
          v-for="exec in executions"
          :key="exec.executionId || exec.id"
          class="m-exec-item"
          @click="$emit('navigate', 'workflow-tasks')"
        >
          <div class="m-exec-top">
            <div class="m-exec-name">{{ exec.workflowName || exec.name || '未命名工作流' }}</div>
            <span class="m-exec-badge" :class="execStatusClass(exec.status)">{{ execStatusText(exec.status) }}</span>
          </div>
          <div class="m-exec-meta">
            <span class="m-exec-id">#{{ shortId(exec.executionId || exec.id) }}</span>
            <span class="m-exec-time">{{ formatTime(exec.startTime || exec.startedAt || exec.createdAt) }}</span>
          </div>
          <div v-if="exec.progress != null" class="m-exec-progress">
            <div class="m-exec-progress-bar">
              <div class="m-exec-progress-fill" :style="{ width: `${exec.progress || 0}%` }"></div>
            </div>
            <span class="m-exec-progress-text">{{ exec.progress || 0 }}%</span>
          </div>
          <div v-if="exec.status === 'failed' && exec.errorMessage" class="m-exec-error">
            <MIcon name="warning" :size="12" />
            <span>{{ truncate(exec.errorMessage, 60) }}</span>
          </div>
          <div v-else-if="exec.status === 'running' && exec.estimatedMinutes > 0" class="m-exec-eta">
            <MIcon name="clock" :size="12" />
            <span>预计 {{ exec.estimatedMinutes }} 分钟</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 更多功能 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>更多功能</h2>
      </div>
      <div class="m-menu-list">
        <div class="m-menu-item" @click="$emit('navigate', 'delivery-records')">
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#e2f8ee,#cdf2df);color:#16bf78">
            <MIcon name="package" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">发货记录</div>
            <div class="m-menu-desc">查看发货历史</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'card-warehouse')">
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#f0ebff,#e2d8ff);color:#8b5cf6">
            <MIcon name="box" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">卡密仓库</div>
            <div class="m-menu-desc">数字商品库存管理</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
      </div>
    </div>

    <div class="m-pc-notice">
      <div class="m-pc-notice-icon">
        <MIcon name="warning" :size="24" />
      </div>
      <div class="m-pc-notice-content">
        <div class="m-pc-notice-title">自动化配置建议在PC端操作</div>
        <div class="m-pc-notice-desc">工作流编辑、规则配置等复杂操作建议使用桌面版以获得完整体验</div>
      </div>
    </div>

    <button class="m-big-btn" @click="$emit('force-desktop')">
      <MIcon name="desktop" :size="18" />进入桌面版配置
    </button>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { workflowOverview, listWorkflowExecutions } from '../api/workflow.js'

defineEmits(['navigate', 'force-desktop'])

const overview = ref({})
const overviewError = ref('')
const executions = ref([])
const execLoading = ref(false)
const execError = ref('')

async function loadOverview() {
  overviewError.value = ''
  try {
    const res = await workflowOverview()
    const data = res?.data
    const keys = ['workflowCount', 'enabledCount', 'todayExecutionCount', 'successRate']
    if (!data || typeof data !== 'object' || Array.isArray(data)
      || keys.some(key => typeof data[key] !== 'number' || !Number.isFinite(data[key]) || data[key] < 0)) {
      throw new Error('自动化统计响应不完整')
    }
    overview.value = data
  } catch (error) {
    overview.value = {}
    overviewError.value = error?.message || '请检查网络连接后重试。'
  }
}

function overviewMetric(key, suffix = '') {
  const value = overview.value?.[key]
  return value === null || value === undefined || value === '' ? '—' : `${value}${suffix}`
}

async function loadExecutions() {
  execLoading.value = true
  execError.value = ''
  try {
    const res = await listWorkflowExecutions({ current: 1, size: 8 })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('执行记录响应格式异常')
    }
    const total = Number(data.total)
    if (!Number.isSafeInteger(total) || total < data.records.length) throw new Error('执行记录总数响应格式异常')
    const records = data.records
    if (records.some(item => !item || typeof item !== 'object' || Array.isArray(item)
      || !(item.executionId || item.id)
      || !['success', 'failed', 'running', 'queued', 'partial_success', 'terminated'].includes(item.status)
      || (item.progress != null && (!Number.isFinite(Number(item.progress)) || Number(item.progress) < 0 || Number(item.progress) > 100)))) {
      throw new Error('执行记录内容响应格式异常')
    }
    executions.value = records
  } catch (error) {
    executions.value = []
    execError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    execLoading.value = false
  }
}

function execStatusText(s) {
  return ({ success: '成功', failed: '失败', running: '运行中', queued: '排队中', partial_success: '部分成功' })[s] || s || '-'
}

function execStatusClass(s) {
  return `m-exec-${s || 'unknown'}`
}

function shortId(id) {
  if (!id) return '-'
  const s = String(id)
  return s.length > 12 ? s.slice(-12) : s
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today - msgDay) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) {
    return `今天 ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  }
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  return `${d.getMonth()+1}/${d.getDate()}`
}

onMounted(() => {
  loadOverview()
  loadExecutions()
})
</script>

<style scoped>
.m-auto {
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

.m-auto-stats {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  margin-left: -16px;
  margin-right: -16px;
  padding-left: 16px;
  padding-right: 16px;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-auto-stats::-webkit-scrollbar { display: none; }
.m-stat-card {
  flex: 0 0 auto;
  width: 124px;
  border-radius: 16px;
  padding: 14px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 10px;
}
.m-stat-purple {
  background: linear-gradient(135deg, #f0ebff, #e2d8ff);
  color: #5b3fb0;
}
.m-stat-blue {
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
}
.m-stat-green {
  background: linear-gradient(135deg, #e2f8ee, #cdf2df);
  color: #16bf78;
}
.m-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255,255,255,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-stat-info { flex: 1; min-width: 0; }
.m-stat-val { font-size: 20px; font-weight: 800; line-height: 1.1; }
.m-stat-label { font-size: 11px; opacity: 0.8; margin-top: 2px; }
.m-stat-extra {
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 10px;
  background: rgba(255,255,255,0.6);
  padding: 2px 6px;
  border-radius: 100px;
  font-weight: 600;
}

.m-section {
  background: white;
  border-radius: 20px;
  padding: 16px;
  margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
}
.m-section-header {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-section-header h2 { margin: 0; font-size: 17px; font-weight: 700; color: #15213d; }
.m-section-action {
  background: none;
  border: none;
  color: #0d6bff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 100px;
}
.m-section-action:active { background: rgba(13,107,255,0.08); }

.m-auto-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.m-auto-item {
  background: #f8faff;
  border-radius: 14px;
  padding: 16px 12px;
  position: relative;
  cursor: pointer;
  transition: background 0.15s;
}
.m-auto-item:active { background: #eef4ff; }
.m-auto-icon {
  width: 48px;
  height: 48px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}
.m-auto-blue { background: linear-gradient(135deg,#e8f1ff,#d0e2ff); color: #0d6bff; }
.m-auto-green { background: linear-gradient(135deg,#e2f8ee,#cdf2df); color: #16bf78; }
.m-auto-purple { background: linear-gradient(135deg,#f0ebff,#e2d8ff); color: #8b5cf6; }
.m-auto-orange { background: linear-gradient(135deg,#fff4e0,#ffe7c2); color: #ff9f22; }
.m-auto-title { font-size: 14px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-auto-desc { font-size: 11px; color: #8c98ae; }
.m-auto-arrow {
  position: absolute;
  top: 14px;
  right: 12px;
  color: #c4cddb;
}

@media (max-width: 360px) {
  .m-auto-grid {
    grid-template-columns: 1fr;
  }

  .m-auto-item {
    min-height: 112px;
  }
}

.m-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 30px 20px;
  color: #8c98ae;
  font-size: 13px;
}
.m-loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #e8edf5;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: m-spin 0.8s linear infinite;
}
@keyframes m-spin { to { transform: rotate(360deg); } }

.m-empty-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: #b0bacb;
  font-size: 13px;
}

.m-exec-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-exec-item {
  background: #f8faff;
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.m-exec-item:active { background: #eef4ff; border-color: #d4e4ff; }
.m-exec-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.m-exec-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-exec-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 100px;
  font-weight: 600;
  flex-shrink: 0;
}
.m-exec-success { background: #e2f8ee; color: #16bf78; }
.m-exec-failed { background: #ffefef; color: #ef4444; }
.m-exec-running { background: #e8f1ff; color: #0d6bff; }
.m-exec-queued { background: #fff4e0; color: #ff9f22; }
.m-exec-partial_success { background: #fff4e0; color: #f0a020; }
.m-exec-unknown { background: #f0f4fa; color: #72809a; }

.m-exec-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #8c98ae;
  margin-bottom: 6px;
}
.m-exec-id { font-family: monospace; }

.m-exec-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-exec-progress-bar {
  flex: 1;
  height: 4px;
  background: #e8edf5;
  border-radius: 100px;
  overflow: hidden;
}
.m-exec-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0d6bff, #3b9bff);
  transition: width 0.3s;
}
.m-exec-progress-text { font-size: 11px; color: #0d6bff; font-weight: 600; min-width: 32px; }

.m-exec-error {
  margin-top: 6px;
  font-size: 11px;
  color: #ef4444;
  display: flex;
  align-items: flex-start;
  gap: 4px;
  background: #ffefef;
  padding: 6px 8px;
  border-radius: 8px;
  line-height: 1.4;
}
.m-exec-error :deep(svg) { flex-shrink: 0; margin-top: 1px; }
.m-exec-eta {
  margin-top: 6px;
  font-size: 11px;
  color: #0d6bff;
  display: flex;
  align-items: center;
  gap: 4px;
}

.m-menu-list { display: flex; flex-direction: column; gap: 2px; }
.m-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 4px;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s;
}
.m-menu-item:active { background: #f8faff; }
.m-menu-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-menu-info { flex: 1; }
.m-menu-title { font-size: 14px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-menu-desc { font-size: 12px; color: #8c98ae; }
.m-menu-arrow { color: #c4cddb; flex-shrink: 0; }

.m-pc-notice {
  background: linear-gradient(135deg, #f5f0ff 0%, #faf7ff 100%);
  border: 1px solid #e8defd;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.m-pc-notice-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-pc-notice-title { font-size: 14px; font-weight: 600; color: #5b3fb0; margin-bottom: 3px; }
.m-pc-notice-desc { font-size: 12px; color: #8c7bc5; line-height: 1.5; }

.m-big-btn {
  width: 100%;
  height: 50px;
  border-radius: 25px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 15px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 8px 20px rgba(13,107,255,0.25);
  cursor: pointer;
  margin-bottom: 8px;
}
.m-big-btn:active { transform: scale(0.98); }

.m-safe-bottom { height: 80px; }
</style>
