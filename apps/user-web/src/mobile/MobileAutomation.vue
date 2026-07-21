<template>
  <div class="m-auto">
    <!-- 顶部 Hero：KPI 大卡 -->
    <section class="m-auto-hero">
      <div class="m-auto-hero-head">
        <div class="m-auto-hero-badge">
          <span class="m-auto-hero-dot"></span>
          <span>自动化运营</span>
        </div>
        <h1 class="m-auto-hero-title">自动化中心</h1>
        <p class="m-auto-hero-sub">工作流 · 自动回复 · 定时任务</p>
      </div>
      <div class="m-auto-kpi-row">
        <div class="m-auto-kpi-cell">
          <div class="m-auto-kpi-value">{{ overviewMetric('workflowCount') }}</div>
          <div class="m-auto-kpi-label">工作流</div>
          <div class="m-auto-kpi-sub">启用 {{ overviewMetric('enabledCount') }}</div>
        </div>
        <div class="m-auto-kpi-divider"></div>
        <div class="m-auto-kpi-cell">
          <div class="m-auto-kpi-value">{{ overviewMetric('todayExecutionCount') }}</div>
          <div class="m-auto-kpi-label">今日执行</div>
        </div>
        <div class="m-auto-kpi-divider"></div>
        <div class="m-auto-kpi-cell">
          <div class="m-auto-kpi-value m-auto-kpi-value--success">{{ overviewMetric('successRate', '%') }}</div>
          <div class="m-auto-kpi-label">成功率</div>
        </div>
      </div>
    </section>

    <MobileUnavailableState v-if="overviewError" compact title="自动化统计暂时不可用" :description="overviewError" @retry="loadOverview" />

    <!-- 自动化功能 2×2 入口网格 -->
    <section class="m-auto-card">
      <div class="m-auto-card-header">
        <div class="m-auto-card-title-wrap">
          <div class="m-auto-card-title-icon m-auto-title-icon--primary">
            <MIcon name="grid" :size="18" />
          </div>
          <h2 class="m-auto-card-title">自动化功能</h2>
        </div>
      </div>
      <div class="m-auto-grid">
        <div class="m-auto-entry" :class="{ 'm-auto-entry--active': activeTab === 'workflow' }" @click="switchTab('workflow')">
          <div class="m-auto-entry-icon m-auto-entry-icon--primary">
            <MIcon name="workflow" :size="20" />
          </div>
          <div class="m-auto-entry-info">
            <div class="m-auto-entry-title">工作流</div>
            <div class="m-auto-entry-desc">设计自动化流程</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-entry-arrow" />
        </div>
        <div class="m-auto-entry" @click="$emit('navigate', 'auto-delivery')">
          <div class="m-auto-entry-icon m-auto-entry-icon--success">
            <MIcon name="truck" :size="20" />
          </div>
          <div class="m-auto-entry-info">
            <div class="m-auto-entry-title">自动发货</div>
            <div class="m-auto-entry-desc">自动处理订单发货</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-entry-arrow" />
        </div>
        <div class="m-auto-entry" :class="{ 'm-auto-entry--active': activeTab === 'autoReply' }" @click="switchTab('autoReply')">
          <div class="m-auto-entry-icon m-auto-entry-icon--purple">
            <MIcon name="reply" :size="20" />
          </div>
          <div class="m-auto-entry-info">
            <div class="m-auto-entry-title">自动回复</div>
            <div class="m-auto-entry-desc">买家消息自动回复</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-entry-arrow" />
        </div>
        <div class="m-auto-entry" :class="{ 'm-auto-entry--active': activeTab === 'scheduled' }" @click="switchTab('scheduled')">
          <div class="m-auto-entry-icon m-auto-entry-icon--warning">
            <MIcon name="clock" :size="20" />
          </div>
          <div class="m-auto-entry-info">
            <div class="m-auto-entry-title">定时任务</div>
            <div class="m-auto-entry-desc">定时执行运营任务</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-entry-arrow" />
        </div>
      </div>
    </section>

    <!-- Tab 内容区 -->
    <section class="m-auto-card">
      <!-- 工作流 Tab -->
      <template v-if="activeTab === 'workflow'">
        <div class="m-auto-card-header">
          <div class="m-auto-card-title-wrap">
            <div class="m-auto-card-title-icon m-auto-title-icon--primary">
              <MIcon name="workflow" :size="18" />
            </div>
            <h2 class="m-auto-card-title">工作流列表</h2>
          </div>
          <button class="m-auto-card-action" :disabled="workflowsLoading" @click="loadWorkflows">
            <MIcon name="refresh" :size="14" />
            <span>刷新</span>
          </button>
        </div>

        <div v-if="workflowsLoading" class="m-auto-loading">
          <div class="m-auto-spinner"></div>
          <span>加载工作流...</span>
        </div>

        <MobileUnavailableState v-else-if="workflowsError" compact title="工作流列表暂时无法加载" :description="workflowsError" @retry="loadWorkflows" />

        <div v-else-if="workflows.length === 0" class="m-auto-empty">
          <div class="m-auto-empty-icon"><MIcon name="workflow" :size="40" /></div>
          <div class="m-auto-empty-text">暂无工作流</div>
        </div>

        <div v-else class="m-auto-wf-list">
          <div
            v-for="wf in workflows"
            :key="wf.id"
            class="m-auto-wf-card"
            @click="openWorkflowDetail(wf)"
          >
            <div class="m-auto-wf-top">
              <div class="m-auto-wf-name">{{ wf.name || '未命名工作流' }}</div>
              <span class="m-auto-wf-badge" :class="workflowStatusClass(wf.status)">{{ workflowStatusText(wf.status) }}</span>
            </div>
            <div v-if="wf.description" class="m-auto-wf-desc">{{ truncate(wf.description, 50) }}</div>
            <div class="m-auto-wf-meta">
              <span class="m-auto-wf-meta-item">执行 {{ wf.executionCount ?? '—' }}</span>
              <span class="m-auto-wf-meta-dot"></span>
              <span class="m-auto-wf-meta-item">v{{ wf.version ?? '—' }}</span>
              <span v-if="wf.enabled !== undefined" class="m-auto-wf-meta-dot"></span>
              <span v-if="wf.enabled !== undefined" class="m-auto-wf-meta-item">{{ wf.enabled ? '已启用' : '未启用' }}</span>
            </div>
            <div class="m-auto-wf-actions">
              <button class="m-auto-btn m-auto-btn-outline m-auto-btn-sm" @click.stop="openWorkflowDetail(wf)">查看</button>
              <button class="m-auto-btn m-auto-btn-ghost m-auto-btn-sm" @click.stop="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 自动回复 Tab -->
      <template v-else-if="activeTab === 'autoReply'">
        <div class="m-auto-card-header">
          <div class="m-auto-card-title-wrap">
            <div class="m-auto-card-title-icon m-auto-title-icon--purple">
              <MIcon name="reply" :size="18" />
            </div>
            <h2 class="m-auto-card-title">自动回复规则</h2>
          </div>
          <button class="m-auto-card-action" :disabled="autoReplyLoading" @click="loadAutoReplyRules">
            <MIcon name="refresh" :size="14" />
            <span>刷新</span>
          </button>
        </div>

        <div v-if="autoReplyLoading" class="m-auto-loading">
          <div class="m-auto-spinner"></div>
          <span>加载自动回复规则...</span>
        </div>

        <MobileUnavailableState v-else-if="autoReplyError" compact title="自动回复规则暂时无法加载" :description="autoReplyError" @retry="loadAutoReplyRules" />

        <div v-else-if="autoReplyRules.length === 0" class="m-auto-empty">
          <div class="m-auto-empty-icon"><MIcon name="reply" :size="40" /></div>
          <div class="m-auto-empty-text">暂无自动回复规则</div>
        </div>

        <div v-else class="m-auto-rule-list">
          <div v-for="rule in autoReplyRules" :key="rule.id" class="m-auto-rule-card">
            <div class="m-auto-rule-head">
              <div class="m-auto-rule-name">{{ rule.name || rule.ruleName || '未命名规则' }}</div>
              <label class="m-auto-switch" :class="{ 'is-disabled': togglingRuleId === rule.id }">
                <input
                  type="checkbox"
                  :checked="isRuleEnabled(rule)"
                  :disabled="togglingRuleId === rule.id"
                  @change="toggleRule(rule, $event)"
                />
                <span class="m-auto-switch-slider"></span>
              </label>
            </div>
            <div v-if="ruleTriggerText(rule)" class="m-auto-rule-row">
              <span class="m-auto-rule-label">触发</span>
              <span class="m-auto-rule-value">{{ ruleTriggerText(rule) }}</span>
            </div>
            <div v-if="ruleActionText(rule)" class="m-auto-rule-row">
              <span class="m-auto-rule-label">动作</span>
              <span class="m-auto-rule-value">{{ ruleActionText(rule) }}</span>
            </div>
            <div class="m-auto-rule-foot">
              <span class="m-auto-rule-status" :class="isRuleEnabled(rule) ? 'm-auto-rule-on' : 'm-auto-rule-off'">
                {{ isRuleEnabled(rule) ? '启用中' : '已停用' }}
              </span>
              <button class="m-auto-btn m-auto-btn-ghost m-auto-btn-sm" @click="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 定时任务 Tab -->
      <template v-else-if="activeTab === 'scheduled'">
        <div class="m-auto-card-header">
          <div class="m-auto-card-title-wrap">
            <div class="m-auto-card-title-icon m-auto-title-icon--warning">
              <MIcon name="clock" :size="18" />
            </div>
            <h2 class="m-auto-card-title">定时任务</h2>
          </div>
          <button class="m-auto-card-action" :disabled="scheduledLoading" @click="loadScheduledTasks">
            <MIcon name="refresh" :size="14" />
            <span>刷新</span>
          </button>
        </div>

        <div v-if="scheduledLoading" class="m-auto-loading">
          <div class="m-auto-spinner"></div>
          <span>加载定时任务...</span>
        </div>

        <MobileUnavailableState v-else-if="scheduledError" compact title="定时任务暂时无法加载" :description="scheduledError" @retry="loadScheduledTasks" />

        <div v-else-if="scheduledTasks.length === 0" class="m-auto-empty">
          <div class="m-auto-empty-icon"><MIcon name="clock" :size="40" /></div>
          <div class="m-auto-empty-text">暂无定时任务</div>
          <button class="m-auto-btn m-auto-btn-ghost m-auto-btn-sm" @click="hintDesktopEdit">定时任务请在桌面端管理</button>
        </div>

        <div v-else class="m-auto-task-list">
          <div v-for="task in scheduledTasks" :key="task.id" class="m-auto-task-card">
            <div class="m-auto-rule-head">
              <div class="m-auto-rule-name">{{ task.taskName || task.name || '未命名任务' }}</div>
              <label class="m-auto-switch" :class="{ 'is-disabled': togglingTaskId === task.id }">
                <input
                  type="checkbox"
                  :checked="isTaskEnabled(task)"
                  :disabled="togglingTaskId === task.id"
                  @change="toggleTask(task, $event)"
                />
                <span class="m-auto-switch-slider"></span>
              </label>
            </div>
            <div v-if="task.taskType" class="m-auto-rule-row">
              <span class="m-auto-rule-label">类型</span>
              <span class="m-auto-rule-value">{{ taskTypeText(task.taskType) }}</span>
            </div>
            <div v-if="task.lastRunTime" class="m-auto-rule-row">
              <span class="m-auto-rule-label">上次</span>
              <span class="m-auto-rule-value">{{ formatDateTime(task.lastRunTime) }}</span>
            </div>
            <div v-if="task.nextRunTime" class="m-auto-rule-row">
              <span class="m-auto-rule-label">下次</span>
              <span class="m-auto-rule-value">{{ formatDateTime(task.nextRunTime) }}</span>
            </div>
            <div class="m-auto-rule-foot">
              <span class="m-auto-rule-status" :class="isTaskEnabled(task) ? 'm-auto-rule-on' : 'm-auto-rule-off'">
                {{ isTaskEnabled(task) ? '启用中' : '已停用' }}
              </span>
              <button class="m-auto-btn m-auto-btn-ghost m-auto-btn-sm" @click="hintDesktopEdit">编辑</button>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- 最近执行记录（仅在工作流 Tab 显示） -->
    <section v-if="activeTab === 'workflow'" class="m-auto-card">
      <div class="m-auto-card-header">
        <div class="m-auto-card-title-wrap">
          <div class="m-auto-card-title-icon m-auto-title-icon--neutral">
            <MIcon name="activity" :size="18" />
          </div>
          <h2 class="m-auto-card-title">最近执行</h2>
        </div>
        <button class="m-auto-card-action" :disabled="execLoading" @click="loadExecutions">
          <MIcon name="refresh" :size="14" />
          <span>刷新</span>
        </button>
      </div>

      <div v-if="execLoading" class="m-auto-loading">
        <div class="m-auto-spinner"></div>
        <span>加载执行记录...</span>
      </div>

      <MobileUnavailableState v-else-if="execError" compact title="执行记录暂时无法加载" :description="execError" @retry="loadExecutions" />

      <div v-else-if="executions.length === 0" class="m-auto-empty">
        <div class="m-auto-empty-icon"><MIcon name="clock" :size="40" /></div>
        <div class="m-auto-empty-text">暂无执行记录</div>
      </div>

      <div v-else class="m-auto-exec-list">
        <div
          v-for="exec in executions"
          :key="exec.executionId || exec.id"
          class="m-auto-exec-item"
          @click="openWorkflowDetail({ id: exec.workflowId || exec.definitionId, name: exec.workflowName || exec.name })"
        >
          <div class="m-auto-exec-top">
            <div class="m-auto-exec-name">{{ exec.workflowName || exec.name || '未命名工作流' }}</div>
            <span class="m-auto-exec-badge" :class="execStatusClass(exec.status)">{{ execStatusText(exec.status) }}</span>
          </div>
          <div class="m-auto-exec-meta">
            <span class="m-auto-exec-id">#{{ shortId(exec.executionId || exec.id) }}</span>
            <span class="m-auto-exec-time">{{ formatTime(exec.startTime || exec.startedAt || exec.createdAt) }}</span>
          </div>
          <div v-if="exec.progress != null" class="m-auto-exec-progress">
            <div class="m-auto-exec-progress-bar">
              <div class="m-auto-exec-progress-fill" :style="{ width: `${exec.progress || 0}%` }"></div>
            </div>
            <span class="m-auto-exec-progress-text">{{ exec.progress || 0 }}%</span>
          </div>
          <div v-if="exec.status === 'failed' && exec.errorMessage" class="m-auto-exec-error">
            <MIcon name="warning" :size="12" />
            <span>{{ truncate(exec.errorMessage, 60) }}</span>
          </div>
          <div v-else-if="exec.status === 'running' && exec.estimatedMinutes > 0" class="m-auto-exec-eta">
            <MIcon name="clock" :size="12" />
            <span>预计 {{ exec.estimatedMinutes }} 分钟</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 更多功能 -->
    <section class="m-auto-card">
      <div class="m-auto-card-header">
        <div class="m-auto-card-title-wrap">
          <div class="m-auto-card-title-icon m-auto-title-icon--neutral">
            <MIcon name="grid" :size="18" />
          </div>
          <h2 class="m-auto-card-title">更多功能</h2>
        </div>
      </div>
      <div class="m-auto-menu">
        <div class="m-auto-menu-item" @click="$emit('navigate', 'delivery-records')">
          <div class="m-auto-menu-icon m-auto-menu-icon--success">
            <MIcon name="package" :size="20" />
          </div>
          <div class="m-auto-menu-info">
            <div class="m-auto-menu-title">发货记录</div>
            <div class="m-auto-menu-desc">查看发货历史</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-menu-arrow" />
        </div>
        <div class="m-auto-menu-item" @click="$emit('navigate', 'card-warehouse')">
          <div class="m-auto-menu-icon m-auto-menu-icon--purple">
            <MIcon name="box" :size="20" />
          </div>
          <div class="m-auto-menu-info">
            <div class="m-auto-menu-title">卡密仓库</div>
            <div class="m-auto-menu-desc">数字商品库存管理</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-auto-menu-arrow" />
        </div>
      </div>
    </section>

    <div class="m-auto-safe-bottom"></div>

    <!-- 工作流详情底部 Sheet（只读） -->
    <transition name="m-auto-sheet">
      <div v-if="sheetOpen" class="m-auto-sheet-mask" @click="closeSheet">
        <div class="m-auto-sheet" @click.stop>
          <div class="m-auto-sheet-handle"></div>
          <div class="m-auto-sheet-header">
            <div class="m-auto-sheet-title">{{ selectedWorkflow?.name || '工作流详情' }}</div>
            <button class="m-auto-sheet-close" @click="closeSheet" aria-label="关闭">
              <MIcon name="close" :size="20" />
            </button>
          </div>

          <div v-if="workflowDetailLoading" class="m-auto-loading">
            <div class="m-auto-spinner"></div>
            <span>加载工作流详情...</span>
          </div>

          <MobileUnavailableState v-else-if="workflowDetailError" compact title="工作流详情暂时无法加载" :description="workflowDetailError" :retryable="true" @retry="() => selectedWorkflow?.id && openWorkflowDetail({ id: selectedWorkflow.id, name: selectedWorkflow.name })" />

          <div v-else class="m-auto-sheet-body">
            <div v-if="selectedWorkflow?.description" class="m-auto-sheet-desc">{{ selectedWorkflow.description }}</div>
            <div class="m-auto-sheet-meta">
              <span>状态：{{ workflowStatusText(selectedWorkflow?.status) }}</span>
              <span v-if="selectedWorkflow?.version != null">v{{ selectedWorkflow.version }}</span>
              <span v-if="selectedWorkflow?.executionCount != null">执行 {{ selectedWorkflow.executionCount }} 次</span>
            </div>

            <div class="m-auto-sheet-section-title">节点列表（{{ workflowNodes.length }}）</div>
            <div v-if="workflowNodes.length === 0" class="m-auto-empty">
              <div class="m-auto-empty-icon"><MIcon name="workflow" :size="32" /></div>
              <div class="m-auto-empty-text">该工作流暂无节点</div>
            </div>
            <div v-else class="m-auto-node-list">
              <div v-for="(node, idx) in workflowNodes" :key="node.id || idx" class="m-auto-node-item">
                <div class="m-auto-node-index">{{ idx + 1 }}</div>
                <div class="m-auto-node-body">
                  <div class="m-auto-node-name">{{ node.name || node.nodeName || '未命名节点' }}</div>
                  <div class="m-auto-node-type">{{ nodeTypeLabel(node.type || node.nodeType) }}</div>
                  <div v-if="node.desc || node.description" class="m-auto-node-desc">{{ node.desc || node.description }}</div>
                </div>
              </div>
            </div>

            <div class="m-auto-sheet-notice">
              <MIcon name="info" :size="14" />
              <span>节点编辑、连线调整等复杂操作请前往桌面端完成。</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 轻提示 -->
    <transition name="m-auto-toast">
      <div v-if="toast" class="m-auto-toast">{{ toast }}</div>
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
/* === 根容器 === */
.m-auto {
  padding: var(--m-space-3) var(--m-space-3) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === Hero === */
.m-auto-hero {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-auto-hero-head {
  margin-bottom: var(--m-space-4);
}
.m-auto-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  margin-bottom: var(--m-space-3);
  border: 1px solid var(--m-color-info-border);
}
.m-auto-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary);
  animation: m-auto-pulse 1.6s ease-in-out infinite;
}
@keyframes m-auto-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.m-auto-hero-title {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  letter-spacing: -0.3px;
}
.m-auto-hero-sub {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* KPI 行 */
.m-auto-kpi-row {
  display: flex;
  align-items: stretch;
  padding: var(--m-space-3) 0;
  border-top: 1px solid var(--m-color-border-light);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-auto-kpi-cell {
  flex: 1;
  min-width: 0;
  text-align: center;
  padding: 0 var(--m-space-2);
}
.m-auto-kpi-value {
  font-size: var(--m-font-size-hero);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5px;
}
.m-auto-kpi-value--success {
  color: var(--m-color-success);
}
.m-auto-kpi-divider {
  width: 1px;
  align-self: stretch;
  background: var(--m-color-border-light);
}
.m-auto-kpi-label {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-auto-kpi-sub {
  margin-top: 2px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

/* === 通用卡片 === */
.m-auto-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-auto-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-3);
  gap: var(--m-space-2);
}
.m-auto-card-title-wrap {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  min-width: 0;
}
.m-auto-card-title-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-auto-title-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-auto-title-icon--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-auto-title-icon--warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-auto-title-icon--neutral {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-auto-card-title {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-auto-card-action {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: transparent;
  border: none;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-primary);
  cursor: pointer;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-family: inherit;
  transition: background 0.15s;
}
.m-auto-card-action:active {
  background: var(--m-color-primary-bg);
}
.m-auto-card-action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* === 2×2 入口网格 === */
.m-auto-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
}
.m-auto-entry {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
}
.m-auto-entry:active {
  transform: scale(0.98);
}
.m-auto-entry--active {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
}
.m-auto-entry-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-auto-entry-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-auto-entry-icon--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-auto-entry-icon--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-auto-entry-icon--warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-auto-entry-info {
  flex: 1;
  min-width: 0;
}
.m-auto-entry-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-auto-entry-desc {
  margin-top: 2px;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-auto-entry-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
}

/* === Loading === */
.m-auto-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-8) var(--m-space-4);
  gap: var(--m-space-2);
}
.m-auto-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-auto-spin 0.8s linear infinite;
}
@keyframes m-auto-spin {
  to { transform: rotate(360deg); }
}

/* === Empty === */
.m-auto-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-8) var(--m-space-4);
  gap: var(--m-space-2);
}
.m-auto-empty-icon {
  color: var(--m-color-text-disabled);
  margin-bottom: var(--m-space-1);
}
.m-auto-empty-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}

/* === 工作流列表 === */
.m-auto-wf-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-auto-wf-card {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-auto-wf-card:active {
  transform: scale(0.99);
}
.m-auto-wf-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-1);
}
.m-auto-wf-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.m-auto-wf-badge {
  flex-shrink: 0;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-wf-published {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-wf-draft {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-wf-archived {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-wf-unknown {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-auto-wf-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
  margin-bottom: var(--m-space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.m-auto-wf-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-auto-wf-meta-item {
  font-weight: var(--m-font-weight-medium);
}
.m-auto-wf-meta-dot {
  width: 3px;
  height: 3px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-text-disabled);
}
.m-auto-wf-actions {
  display: flex;
  gap: var(--m-space-2);
}

/* === 按钮 === */
.m-auto-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  border: none;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  padding: var(--m-space-2) var(--m-space-3);
}
.m-auto-btn-sm {
  padding: var(--m-space-1) var(--m-space-2);
  font-size: var(--m-font-size-tiny);
}
.m-auto-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-auto-btn-primary:active {
  background: var(--m-color-primary-active);
}
.m-auto-btn-outline {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  border: 1px solid var(--m-color-primary);
}
.m-auto-btn-outline:active {
  background: var(--m-color-primary-bg);
}
.m-auto-btn-ghost {
  background: transparent;
  color: var(--m-color-text-secondary);
}
.m-auto-btn-ghost:active {
  background: var(--m-color-bg-subtle);
}

/* === 规则/任务卡 === */
.m-auto-rule-list,
.m-auto-task-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-auto-rule-card,
.m-auto-task-card {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
}
.m-auto-rule-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}
.m-auto-rule-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-auto-rule-row {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-1);
  font-size: var(--m-font-size-caption);
}
.m-auto-rule-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  min-width: 36px;
}
.m-auto-rule-value {
  color: var(--m-color-text-secondary);
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.m-auto-rule-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--m-space-2);
  padding-top: var(--m-space-2);
  border-top: 1px solid var(--m-color-border-light);
}
.m-auto-rule-status {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
}
.m-auto-rule-on {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-auto-rule-off {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

/* === Switch 开关 === */
.m-auto-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  flex-shrink: 0;
  cursor: pointer;
}
.m-auto-switch input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}
.m-auto-switch-slider {
  position: absolute;
  inset: 0;
  background: var(--m-color-text-disabled);
  border-radius: var(--m-radius-pill);
  transition: background 0.2s;
}
.m-auto-switch-slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  left: 2px;
  top: 2px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  transition: transform 0.2s;
  box-shadow: var(--m-shadow-card);
}
.m-auto-switch input:checked + .m-auto-switch-slider {
  background: var(--m-color-success);
}
.m-auto-switch input:checked + .m-auto-switch-slider::before {
  transform: translateX(18px);
}
.m-auto-switch.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* === 执行记录 === */
.m-auto-exec-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-auto-exec-item {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-auto-exec-item:active {
  transform: scale(0.99);
}
.m-auto-exec-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-1);
}
.m-auto-exec-name {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.m-auto-exec-badge {
  flex-shrink: 0;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-exec-success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-exec-failed {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-exec-running {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-exec-queued {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-exec-partial_success {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-exec-unknown {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-auto-exec-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-auto-exec-id {
  font-weight: var(--m-font-weight-medium);
  font-variant-numeric: tabular-nums;
}
.m-auto-exec-progress {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-top: var(--m-space-2);
}
.m-auto-exec-progress-bar {
  flex: 1;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  overflow: hidden;
}
.m-auto-exec-progress-fill {
  height: 100%;
  background: var(--m-color-primary);
  border-radius: var(--m-radius-pill);
  transition: width 0.3s ease;
}
.m-auto-exec-progress-text {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.m-auto-exec-error {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1);
  margin-top: var(--m-space-2);
  padding: var(--m-space-2);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-tiny);
  line-height: var(--m-line-height-base);
}
.m-auto-exec-eta {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  margin-top: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

/* === 更多功能菜单 === */
.m-auto-menu {
  display: flex;
  flex-direction: column;
}
.m-auto-menu-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
}
.m-auto-menu-item:last-child {
  border-bottom: none;
}
.m-auto-menu-item:active {
  background: var(--m-color-bg-subtle);
}
.m-auto-menu-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-auto-menu-icon--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-auto-menu-icon--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-auto-menu-info {
  flex: 1;
  min-width: 0;
}
.m-auto-menu-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-auto-menu-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: 2px;
}
.m-auto-menu-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
}

/* === 底部安全区 === */
.m-auto-safe-bottom {
  height: 80px;
}

/* === 工作流详情 Sheet === */
.m-auto-sheet-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-auto-sheet {
  width: 100%;
  max-width: 480px;
  max-height: 85vh;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.m-auto-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  margin: var(--m-space-2) auto var(--m-space-1);
  flex-shrink: 0;
}
.m-auto-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-2) var(--m-space-4) var(--m-space-3);
  border-bottom: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}
.m-auto-sheet-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-auto-sheet-close {
  background: transparent;
  border: none;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  padding: var(--m-space-1);
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-auto-sheet-close:active {
  background: var(--m-color-bg-subtle);
}
.m-auto-sheet-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-4);
}
.m-auto-sheet-desc {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
  margin-bottom: var(--m-space-3);
}
.m-auto-sheet-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-4);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-auto-sheet-section-title {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}
.m-auto-node-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-4);
}
.m-auto-node-item {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-md);
}
.m-auto-node-index {
  width: 24px;
  height: 24px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
  flex-shrink: 0;
}
.m-auto-node-body {
  flex: 1;
  min-width: 0;
}
.m-auto-node-name {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-auto-node-type {
  margin-top: 2px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-auto-node-desc {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}
.m-auto-sheet-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-base);
}

/* === Toast === */
.m-auto-toast {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(31, 35, 41, 0.9);
  color: var(--m-color-text-inverse);
  padding: var(--m-space-2) var(--m-space-4);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  z-index: 2000;
  max-width: 80%;
  text-align: center;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

/* === Sheet / Toast 过渡 === */
.m-auto-sheet-enter-active,
.m-auto-sheet-leave-active {
  transition: opacity 0.25s;
}
.m-auto-sheet-enter-active .m-auto-sheet,
.m-auto-sheet-leave-active .m-auto-sheet {
  transition: transform 0.3s ease;
}
.m-auto-sheet-enter-from,
.m-auto-sheet-leave-to {
  opacity: 0;
}
.m-auto-sheet-enter-from .m-auto-sheet,
.m-auto-sheet-leave-to .m-auto-sheet {
  transform: translateY(100%);
}
.m-auto-toast-enter-active,
.m-auto-toast-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.m-auto-toast-enter-from,
.m-auto-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}

/* === 响应式 === */
@media (max-width: 360px) {
  .m-auto {
    padding: var(--m-space-2) var(--m-space-2) 0;
  }
  .m-auto-hero {
    padding: var(--m-space-3);
  }
  .m-auto-kpi-value {
    font-size: var(--m-font-size-h1);
  }
  .m-auto-grid {
    gap: var(--m-space-2);
  }
  .m-auto-entry {
    padding: var(--m-space-2);
  }
  .m-auto-entry-icon {
    width: 32px;
    height: 32px;
  }
  .m-auto-entry-title {
    font-size: var(--m-font-size-body);
  }
}
</style>
