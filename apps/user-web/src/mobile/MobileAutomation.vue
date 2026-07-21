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

    <!-- 自动化功能（复用为 Tab 切换入口） -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>自动化功能</h2>
      </div>
      <div class="m-auto-grid">
        <div class="m-auto-item" :class="{ 'm-auto-active': activeTab === 'workflow' }" @click="switchTab('workflow')">
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
        <div class="m-auto-item" :class="{ 'm-auto-active': activeTab === 'autoReply' }" @click="switchTab('autoReply')">
          <div class="m-auto-icon m-auto-purple">
            <MIcon name="reply" :size="26" />
          </div>
          <div class="m-auto-title">自动回复</div>
          <div class="m-auto-desc">买家消息自动回复</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
        <div class="m-auto-item" :class="{ 'm-auto-active': activeTab === 'scheduled' }" @click="switchTab('scheduled')">
          <div class="m-auto-icon m-auto-orange">
            <MIcon name="clock" :size="26" />
          </div>
          <div class="m-auto-title">定时任务</div>
          <div class="m-auto-desc">定时执行运营任务</div>
          <MIcon name="chevronRight" :size="16" class="m-auto-arrow" />
        </div>
      </div>
    </div>

    <!-- Tab 内容区 -->
    <div class="m-section">
      <!-- 工作流 Tab -->
      <template v-if="activeTab === 'workflow'">
        <div class="m-section-header">
          <h2>工作流列表</h2>
          <button class="m-section-action" :disabled="workflowsLoading" @click="loadWorkflows">
            <MIcon name="refresh" :size="14" />刷新
          </button>
        </div>

        <div v-if="workflowsLoading" class="m-loading">
          <div class="m-loading-spinner"></div>
          <span>加载工作流...</span>
        </div>

        <MobileUnavailableState v-else-if="workflowsError" compact title="工作流列表暂时无法加载" :description="workflowsError" @retry="loadWorkflows" />

        <div v-else-if="workflows.length === 0" class="m-empty-mini">
          <MIcon name="workflow" :size="32" />
          <span>暂无工作流</span>
        </div>

        <div v-else class="m-wf-list">
          <div
            v-for="wf in workflows"
            :key="wf.id"
            class="m-wf-card"
            @click="openWorkflowDetail(wf)"
          >
            <div class="m-wf-top">
              <div class="m-wf-name">{{ wf.name || '未命名工作流' }}</div>
              <span class="m-wf-badge" :class="workflowStatusClass(wf.status)">{{ workflowStatusText(wf.status) }}</span>
            </div>
            <div v-if="wf.description" class="m-wf-desc">{{ truncate(wf.description, 50) }}</div>
            <div class="m-wf-meta">
              <span class="m-wf-meta-item">执行 {{ wf.executionCount ?? '—' }}</span>
              <span class="m-wf-meta-item">v{{ wf.version ?? '—' }}</span>
              <span v-if="wf.enabled !== undefined" class="m-wf-meta-item">{{ wf.enabled ? '已启用' : '未启用' }}</span>
            </div>
            <div class="m-wf-actions">
              <button class="m-wf-btn" @click.stop="openWorkflowDetail(wf)">查看</button>
              <button class="m-wf-btn m-wf-btn-ghost" @click.stop="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 自动回复 Tab -->
      <template v-else-if="activeTab === 'autoReply'">
        <div class="m-section-header">
          <h2>自动回复规则</h2>
          <button class="m-section-action" :disabled="autoReplyLoading" @click="loadAutoReplyRules">
            <MIcon name="refresh" :size="14" />刷新
          </button>
        </div>

        <div v-if="autoReplyLoading" class="m-loading">
          <div class="m-loading-spinner"></div>
          <span>加载自动回复规则...</span>
        </div>

        <MobileUnavailableState v-else-if="autoReplyError" compact title="自动回复规则暂时无法加载" :description="autoReplyError" @retry="loadAutoReplyRules" />

        <div v-else-if="autoReplyRules.length === 0" class="m-empty-mini">
          <MIcon name="reply" :size="32" />
          <span>暂无自动回复规则</span>
        </div>

        <div v-else class="m-rule-list">
          <div v-for="rule in autoReplyRules" :key="rule.id" class="m-rule-card">
            <div class="m-rule-head">
              <div class="m-rule-name">{{ rule.name || rule.ruleName || '未命名规则' }}</div>
              <label class="m-switch" :class="{ 'is-disabled': togglingRuleId === rule.id }">
                <input
                  type="checkbox"
                  :checked="isRuleEnabled(rule)"
                  :disabled="togglingRuleId === rule.id"
                  @change="toggleRule(rule, $event)"
                />
                <span class="m-switch-slider"></span>
              </label>
            </div>
            <div v-if="ruleTriggerText(rule)" class="m-rule-row">
              <span class="m-rule-label">触发</span>
              <span class="m-rule-value">{{ ruleTriggerText(rule) }}</span>
            </div>
            <div v-if="ruleActionText(rule)" class="m-rule-row">
              <span class="m-rule-label">动作</span>
              <span class="m-rule-value">{{ ruleActionText(rule) }}</span>
            </div>
            <div class="m-rule-foot">
              <span class="m-rule-status" :class="isRuleEnabled(rule) ? 'm-rule-on' : 'm-rule-off'">
                {{ isRuleEnabled(rule) ? '启用中' : '已停用' }}
              </span>
              <button class="m-wf-btn m-wf-btn-ghost" @click="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 定时任务 Tab -->
      <template v-else-if="activeTab === 'scheduled'">
        <div class="m-section-header">
          <h2>定时任务</h2>
          <button class="m-section-action" :disabled="scheduledLoading" @click="loadScheduledTasks">
            <MIcon name="refresh" :size="14" />刷新
          </button>
        </div>

        <div v-if="scheduledLoading" class="m-loading">
          <div class="m-loading-spinner"></div>
          <span>加载定时任务...</span>
        </div>

        <MobileUnavailableState v-else-if="scheduledError" compact title="定时任务暂时无法加载" :description="scheduledError" @retry="loadScheduledTasks" />

        <div v-else-if="scheduledTasks.length === 0" class="m-empty-mini">
          <MIcon name="clock" :size="32" />
          <span>暂无定时任务</span>
          <button class="m-empty-action" @click="hintDesktopEdit">定时任务请在桌面端管理</button>
        </div>

        <div v-else class="m-task-list">
          <div v-for="task in scheduledTasks" :key="task.id" class="m-task-card">
            <div class="m-rule-head">
              <div class="m-rule-name">{{ task.taskName || task.name || '未命名任务' }}</div>
              <label class="m-switch" :class="{ 'is-disabled': togglingTaskId === task.id }">
                <input
                  type="checkbox"
                  :checked="isTaskEnabled(task)"
                  :disabled="togglingTaskId === task.id"
                  @change="toggleTask(task, $event)"
                />
                <span class="m-switch-slider"></span>
              </label>
            </div>
            <div v-if="task.taskType" class="m-rule-row">
              <span class="m-rule-label">类型</span>
              <span class="m-rule-value">{{ taskTypeText(task.taskType) }}</span>
            </div>
            <div v-if="task.lastRunTime" class="m-rule-row">
              <span class="m-rule-label">上次</span>
              <span class="m-rule-value">{{ formatDateTime(task.lastRunTime) }}</span>
            </div>
            <div v-if="task.nextRunTime" class="m-rule-row">
              <span class="m-rule-label">下次</span>
              <span class="m-rule-value">{{ formatDateTime(task.nextRunTime) }}</span>
            </div>
            <div class="m-rule-foot">
              <span class="m-rule-status" :class="isTaskEnabled(task) ? 'm-rule-on' : 'm-rule-off'">
                {{ isTaskEnabled(task) ? '启用中' : '已停用' }}
              </span>
              <button class="m-wf-btn m-wf-btn-ghost" @click="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 最近执行记录（仅在工作流 Tab 显示） -->
    <div v-if="activeTab === 'workflow'" class="m-section">
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
          @click="openWorkflowDetail({ id: exec.workflowId || exec.definitionId, name: exec.workflowName || exec.name })"
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

    <div class="m-safe-bottom"></div>

    <!-- 工作流详情底部 Sheet（只读） -->
    <transition name="m-sheet">
      <div v-if="sheetOpen" class="m-sheet-mask" @click="closeSheet">
        <div class="m-sheet" @click.stop>
          <div class="m-sheet-handle"></div>
          <div class="m-sheet-header">
            <div class="m-sheet-title">{{ selectedWorkflow?.name || '工作流详情' }}</div>
            <button class="m-sheet-close" @click="closeSheet" aria-label="关闭">
              <MIcon name="close" :size="20" />
            </button>
          </div>

          <div v-if="workflowDetailLoading" class="m-loading">
            <div class="m-loading-spinner"></div>
            <span>加载工作流详情...</span>
          </div>

          <MobileUnavailableState v-else-if="workflowDetailError" compact title="工作流详情暂时无法加载" :description="workflowDetailError" :retryable="true" @retry="() => selectedWorkflow?.id && openWorkflowDetail({ id: selectedWorkflow.id, name: selectedWorkflow.name })" />

          <div v-else class="m-sheet-body">
            <div v-if="selectedWorkflow?.description" class="m-sheet-desc">{{ selectedWorkflow.description }}</div>
            <div class="m-sheet-meta">
              <span>状态：{{ workflowStatusText(selectedWorkflow?.status) }}</span>
              <span v-if="selectedWorkflow?.version != null">v{{ selectedWorkflow.version }}</span>
              <span v-if="selectedWorkflow?.executionCount != null">执行 {{ selectedWorkflow.executionCount }} 次</span>
            </div>

            <div class="m-sheet-section-title">节点列表（{{ workflowNodes.length }}）</div>
            <div v-if="workflowNodes.length === 0" class="m-empty-mini">
              <MIcon name="workflow" :size="28" />
              <span>该工作流暂无节点</span>
            </div>
            <div v-else class="m-node-list">
              <div v-for="(node, idx) in workflowNodes" :key="node.id || idx" class="m-node-item">
                <div class="m-node-index">{{ idx + 1 }}</div>
                <div class="m-node-body">
                  <div class="m-node-name">{{ node.name || node.nodeName || '未命名节点' }}</div>
                  <div class="m-node-type">{{ nodeTypeLabel(node.type || node.nodeType) }}</div>
                  <div v-if="node.desc || node.description" class="m-node-desc">{{ node.desc || node.description }}</div>
                </div>
              </div>
            </div>

            <div class="m-sheet-notice">
              <MIcon name="info" :size="14" />
              <span>节点编辑、连线调整等复杂操作请前往桌面端完成。</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 轻提示 -->
    <transition name="m-toast">
      <div v-if="toast" class="m-toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { workflowOverview, listWorkflowExecutions, listWorkflows, getWorkflow } from '../api/workflow.js'
import { getAutoReplyRules, updateAutoReplyRule } from '../api/autoReply.js'
import { getScheduledTasks, setScheduledTaskEnabled } from '../api/scheduledTasks.js'

defineEmits(['navigate', 'force-desktop'])

const overview = ref({})
const overviewError = ref('')
const executions = ref([])
const execLoading = ref(false)
const execError = ref('')

// Tab 状态：workflow / autoReply / scheduled
const activeTab = ref('workflow')

// 工作流列表
const workflows = ref([])
const workflowsLoading = ref(false)
const workflowsError = ref('')

// 工作流详情 sheet
const sheetOpen = ref(false)
const selectedWorkflow = ref(null)
const workflowNodes = ref([])
const workflowDetailLoading = ref(false)
const workflowDetailError = ref('')

// 自动回复规则
const autoReplyRules = ref([])
const autoReplyLoading = ref(false)
const autoReplyError = ref('')
const togglingRuleId = ref(null)

// 定时任务
const scheduledTasks = ref([])
const scheduledLoading = ref(false)
const scheduledError = ref('')
const togglingTaskId = ref(null)

// 轻提示
const toast = ref('')
let toastTimer = null
function showToast(text) {
  toast.value = text
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2200)
}

function hintDesktopEdit() {
  showToast('编辑请前往桌面端')
}

function switchTab(tab) {
  if (activeTab.value === tab) return
  activeTab.value = tab
  // 首次切入时按需加载
  if (tab === 'workflow' && workflows.value.length === 0 && !workflowsError.value) loadWorkflows()
  else if (tab === 'autoReply' && autoReplyRules.value.length === 0 && !autoReplyError.value) loadAutoReplyRules()
  else if (tab === 'scheduled' && scheduledTasks.value.length === 0 && !scheduledError.value) loadScheduledTasks()
}

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

async function loadWorkflows() {
  workflowsLoading.value = true
  workflowsError.value = ''
  try {
    const res = await listWorkflows({ current: 1, size: 50 })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('工作流列表响应格式异常')
    }
    workflows.value = data.records
  } catch (error) {
    workflows.value = []
    workflowsError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    workflowsLoading.value = false
  }
}

async function openWorkflowDetail(wf) {
  if (!wf?.id) {
    showToast('该工作流缺少 ID，无法查看详情')
    return
  }
  selectedWorkflow.value = { ...wf }
  workflowNodes.value = []
  workflowDetailError.value = ''
  sheetOpen.value = true
  workflowDetailLoading.value = true
  try {
    const res = await getWorkflow(wf.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || String(data.id ?? '') !== String(wf.id)) {
      throw new Error('工作流详情响应格式异常')
    }
    selectedWorkflow.value = { ...wf, ...data }
    const nodes = Array.isArray(data.nodes) ? data.nodes : []
    workflowNodes.value = nodes.map(n => ({
      id: n.id || n.nodeKey,
      name: n.name || n.nodeName,
      type: n.type || n.nodeType,
      desc: n.desc || n.description || ''
    }))
  } catch (error) {
    workflowDetailError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    workflowDetailLoading.value = false
  }
}

function closeSheet() {
  sheetOpen.value = false
  selectedWorkflow.value = null
  workflowNodes.value = []
  workflowDetailError.value = ''
}

async function loadAutoReplyRules() {
  autoReplyLoading.value = true
  autoReplyError.value = ''
  try {
    const res = await getAutoReplyRules({ current: 1, size: 50 })
    const data = res?.data
    // 兼容多种返回结构：{records:[]} / {list:[]} / {rows:[]} / [...]
    let list = []
    if (Array.isArray(data)) list = data
    else if (data && typeof data === 'object') list = data.records || data.list || data.rows || data.items || []
    if (!Array.isArray(list)) throw new Error('自动回复规则响应格式异常')
    autoReplyRules.value = list
  } catch (error) {
    autoReplyRules.value = []
    autoReplyError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    autoReplyLoading.value = false
  }
}

function isRuleEnabled(rule) {
  const v = rule?.enabled
  return v === true || v === 1 || v === '1' || v === 'true'
}

function ruleTriggerText(rule) {
  if (!rule) return ''
  if (Array.isArray(rule.keywords) && rule.keywords.length) return rule.keywords.join('、')
  if (rule.keyword) return rule.keyword
  if (rule.trigger) return rule.trigger
  if (rule.triggerCondition) return rule.triggerCondition
  if (rule.matchType) return rule.matchType
  return ''
}

function ruleActionText(rule) {
  if (!rule) return ''
  if (rule.reply) return truncate(rule.reply, 40)
  if (rule.message) return truncate(rule.message, 40)
  if (rule.action) return rule.action
  if (rule.replyContent) return truncate(rule.replyContent, 40)
  if (rule.content) return truncate(rule.content, 40)
  return ''
}

async function toggleRule(rule, event) {
  if (!rule?.id || togglingRuleId.value !== null) return
  const nextEnabled = event?.target?.checked ?? !isRuleEnabled(rule)
  togglingRuleId.value = rule.id
  try {
    await updateAutoReplyRule(rule.id, { enabled: nextEnabled })
    // 更新本地状态
    const idx = autoReplyRules.value.findIndex(r => r.id === rule.id)
    if (idx >= 0) {
      autoReplyRules.value[idx] = { ...autoReplyRules.value[idx], enabled: nextEnabled }
    }
    showToast(nextEnabled ? '已启用' : '已停用')
  } catch (error) {
    showToast(error?.message || '切换失败')
    // 还原 checkbox
    if (event?.target) event.target.checked = !nextEnabled
  } finally {
    togglingRuleId.value = null
  }
}

async function loadScheduledTasks() {
  scheduledLoading.value = true
  scheduledError.value = ''
  try {
    const res = await getScheduledTasks({ current: 1, size: 50 })
    const data = res?.data
    let list = []
    if (Array.isArray(data)) list = data
    else if (data && typeof data === 'object') list = data.records || data.list || data.rows || data.items || []
    if (!Array.isArray(list)) throw new Error('定时任务响应格式异常')
    scheduledTasks.value = list
  } catch (error) {
    scheduledTasks.value = []
    scheduledError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    scheduledLoading.value = false
  }
}

function isTaskEnabled(task) {
  const v = task?.enabled
  return v === true || v === 1 || v === '1' || v === 'true'
}

async function toggleTask(task, event) {
  if (!task?.id || togglingTaskId.value !== null) return
  const nextEnabled = event?.target?.checked ?? !isTaskEnabled(task)
  togglingTaskId.value = task.id
  try {
    await setScheduledTaskEnabled(task.id, nextEnabled)
    const idx = scheduledTasks.value.findIndex(t => t.id === task.id)
    if (idx >= 0) {
      scheduledTasks.value[idx] = { ...scheduledTasks.value[idx], enabled: nextEnabled ? 1 : 0 }
    }
    showToast(nextEnabled ? '已启用' : '已停用')
  } catch (error) {
    showToast(error?.message || '切换失败')
    if (event?.target) event.target.checked = !nextEnabled
  } finally {
    togglingTaskId.value = null
  }
}

function taskTypeText(type) {
  const map = {
    sync_goods: '商品同步',
    sync_orders: '订单同步',
    one_click_polish: '一键润色',
    auto_redelivery: '自动重发货',
    workflow: '工作流执行'
  }
  return map[type] || type || '-'
}

function workflowStatusText(s) {
  return ({ published: '已发布', draft: '草稿', archived: '已归档' })[s] || s || '-'
}

function workflowStatusClass(s) {
  return `m-wf-${s || 'unknown'}`
}

function nodeTypeLabel(type) {
  const map = {
    TRIGGER: '触发器',
    PRODUCT_FETCH: '商品获取',
    PRODUCT_FILTER: '商品筛选',
    PRODUCT_POLISH: '商品润色',
    IMAGE_GENERATE: '图片生成',
    PUBLISH: '商品发布',
    CONDITION: '条件判断',
    DELAY: '延时',
    NOTIFY: '通知'
  }
  return map[type] || type || '节点'
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
  const s = String(text)
  return s.length > max ? s.slice(0, max) + '...' : s
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

function formatDateTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return String(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getMonth()+1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  loadOverview()
  loadExecutions()
  loadWorkflows()
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
.m-section-action:disabled { opacity: 0.5; }

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
  transition: background 0.15s, box-shadow 0.15s;
  border: 2px solid transparent;
}
.m-auto-item:active { background: #eef4ff; }
.m-auto-item.m-auto-active {
  background: #eef4ff;
  border-color: #0d6bff;
  box-shadow: 0 4px 12px rgba(13,107,255,0.12);
}
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
.m-empty-action {
  margin-top: 4px;
  background: #f0f4fa;
  border: none;
  color: #5a6a85;
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 100px;
  cursor: pointer;
}
.m-empty-action:active { background: #e7edf7; }

/* 工作流卡片 */
.m-wf-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-wf-card {
  background: #f8faff;
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.m-wf-card:active { background: #eef4ff; border-color: #d4e4ff; }
.m-wf-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.m-wf-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-wf-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 100px;
  font-weight: 600;
  flex-shrink: 0;
}
.m-wf-published { background: #e2f8ee; color: #16bf78; }
.m-wf-draft { background: #e8f1ff; color: #0d6bff; }
.m-wf-archived { background: #f0f4fa; color: #72809a; }
.m-wf-unknown { background: #f0f4fa; color: #72809a; }
.m-wf-desc {
  font-size: 12px;
  color: #8c98ae;
  margin-bottom: 6px;
  line-height: 1.4;
}
.m-wf-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #8c98ae;
  margin-bottom: 8px;
}
.m-wf-actions {
  display: flex;
  gap: 8px;
}
.m-wf-btn {
  background: #0d6bff;
  color: white;
  border: none;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 100px;
  cursor: pointer;
}
.m-wf-btn:active { transform: scale(0.96); }
.m-wf-btn-ghost {
  background: white;
  color: #5a6a85;
  border: 1px solid #e0e7f0;
}
.m-wf-btn-ghost:active { background: #f8faff; }

/* 自动回复 / 定时任务 卡片 */
.m-rule-list, .m-task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-rule-card, .m-task-card {
  background: #f8faff;
  border-radius: 12px;
  padding: 12px;
  border: 1px solid transparent;
}
.m-rule-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.m-rule-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-rule-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
  line-height: 1.4;
}
.m-rule-label {
  color: #8c98ae;
  flex-shrink: 0;
  min-width: 32px;
}
.m-rule-value {
  color: #15213d;
  flex: 1;
  min-width: 0;
  word-break: break-all;
}
.m-rule-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.m-rule-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 100px;
  font-weight: 600;
}
.m-rule-on { background: #e2f8ee; color: #16bf78; }
.m-rule-off { background: #f0f4fa; color: #72809a; }

/* 开关 */
.m-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  flex-shrink: 0;
  cursor: pointer;
}
.m-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.m-switch-slider {
  position: absolute;
  inset: 0;
  background: #d4dae5;
  border-radius: 100px;
  transition: background 0.2s;
}
.m-switch-slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  left: 2px;
  top: 2px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.m-switch input:checked + .m-switch-slider {
  background: #16bf78;
}
.m-switch input:checked + .m-switch-slider::before {
  transform: translateX(18px);
}
.m-switch.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.m-safe-bottom { height: 80px; }

/* 底部 Sheet */
.m-sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(15,25,50,0.5);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-sheet {
  background: white;
  width: 100%;
  max-width: 560px;
  max-height: 85vh;
  border-radius: 20px 20px 0 0;
  display: flex;
  flex-direction: column;
  padding: 8px 16px calc(20px + env(safe-area-inset-bottom));
  box-shadow: 0 -8px 32px rgba(15,25,50,0.18);
}
.m-sheet-handle {
  width: 36px;
  height: 4px;
  background: #e0e7f0;
  border-radius: 100px;
  margin: 4px auto 8px;
}
.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f4fa;
  margin-bottom: 12px;
}
.m-sheet-title {
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f0f4fa;
  color: #5a6a85;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-sheet-close:active { background: #e7edf7; }
.m-sheet-body {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.m-sheet-desc {
  font-size: 13px;
  color: #5a6a85;
  line-height: 1.5;
  margin-bottom: 8px;
}
.m-sheet-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #8c98ae;
  margin-bottom: 14px;
}
.m-sheet-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  margin: 6px 0 10px;
}
.m-node-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.m-node-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #f8faff;
  border-radius: 10px;
}
.m-node-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-node-body { flex: 1; min-width: 0; }
.m-node-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
}
.m-node-type {
  font-size: 11px;
  color: #0d6bff;
  background: #e8f1ff;
  display: inline-block;
  padding: 1px 8px;
  border-radius: 100px;
  font-weight: 600;
}
.m-node-desc {
  font-size: 12px;
  color: #8c98ae;
  margin-top: 4px;
  line-height: 1.4;
}
.m-sheet-notice {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  background: #f5f0ff;
  color: #5b3fb0;
  font-size: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  line-height: 1.4;
}
.m-sheet-notice :deep(svg) { flex-shrink: 0; margin-top: 1px; }

.m-sheet-enter-active, .m-sheet-leave-active {
  transition: opacity 0.2s;
}
.m-sheet-enter-active .m-sheet, .m-sheet-leave-active .m-sheet {
  transition: transform 0.25s ease;
}
.m-sheet-enter-from, .m-sheet-leave-to { opacity: 0; }
.m-sheet-enter-from .m-sheet, .m-sheet-leave-to .m-sheet { transform: translateY(100%); }

/* 轻提示 */
.m-toast {
  position: fixed;
  left: 50%;
  bottom: calc(96px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  background: rgba(21,33,61,0.92);
  color: white;
  font-size: 13px;
  padding: 10px 18px;
  border-radius: 100px;
  z-index: 400;
  box-shadow: 0 6px 20px rgba(15,25,50,0.25);
  max-width: 80vw;
  text-align: center;
}
.m-toast-enter-active, .m-toast-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.m-toast-enter-from, .m-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
</style>
