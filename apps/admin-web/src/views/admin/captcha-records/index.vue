<template>
  <div class="captcha-records-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>滑块求解记录</h2>
          <p>
            查看所有闲鱼账号的滑块验证求解记录、成功率趋势和账号分布。
            可在「用户管理」点击某用户的「滑块求解记录」按钮查看该用户所有账号的求解数据；
            也可在「闲鱼账号」点击某账号的「求解记录」按钮查看单账号明细。
          </p>
        </div>
        <div class="actions">
          <ElRadioGroup v-model="daysRange" size="default" @change="onRangeChange">
            <ElRadioButton :value="1">今天</ElRadioButton>
            <ElRadioButton :value="7">近 7 天</ElRadioButton>
            <ElRadioButton :value="30">近 30 天</ElRadioButton>
            <ElRadioButton :value="0">全部</ElRadioButton>
          </ElRadioGroup>
          <ElButton :loading="statsLoading" @click="loadStats">刷新概览</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 当前过滤提示 -->
    <ElAlert v-if="accountIdFilter || userIdFilter" type="success" :closable="false" class="filter-alert" show-icon>
      <template #title>
        <span>
          <template v-if="accountIdFilter">
            已按账号过滤：账号 ID <b>{{ accountIdFilter }}</b>
            <span v-if="accountNameHint">（{{ accountNameHint }}）</span>
          </template>
          <template v-else-if="userIdFilter">
            已按用户过滤：用户 ID <b>{{ userIdFilter }}</b>
            <span v-if="usernameHint">（{{ usernameHint }}）</span>
          </template>
          ｜
          <ElLink type="primary" :underline="false" @click="clearEntryFilter">查看全部求解记录</ElLink>
        </span>
      </template>
    </ElAlert>

    <!-- KPI 卡片 -->
    <div class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">求解总次数</div>
        <div class="metric-value">{{ formatNumber(stats.kpi.total) }}</div>
        <div class="metric-sub">{{ rangeLabel }}（已排除服务不可用/预检验/超时）</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功次数</div>
        <div class="metric-value text-success">{{ formatNumber(stats.kpi.success) }}</div>
        <div class="metric-sub">status=success</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">失败次数</div>
        <div class="metric-value text-danger">{{ formatNumber(stats.kpi.fail) }}</div>
        <div class="metric-sub">不含服务不可用/预检验/超时</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功率</div>
        <div class="metric-value" :class="successRateClass">{{ formatPercent(stats.kpi.successRate) }}</div>
        <div class="metric-sub">成功 / (成功+失败)</div>
      </ElCard>
    </div>

    <!-- 统计口径说明 -->
    <ElAlert type="info" :closable="false" class="stats-scope-alert" show-icon>
      <template #title>
        <span>
          统计口径：失败原因为「服务不可用」「预检验拒绝」「超时」的请求不计入成功率与失败次数统计。
          当前范围已排除：
          <b>服务不可用 {{ stats.kpi.serviceUnavailable || 0 }}</b> 次、
          <b>预检验拒绝 {{ stats.kpi.precheckRejected || 0 }}</b> 次、
          <b>超时 {{ stats.kpi.timeout || 0 }}</b> 次。
          此三类记录可在下方明细列表按状态筛选查看。
        </span>
      </template>
    </ElAlert>

    <!-- 队列实时状态徽标 -->
    <ElCard shadow="never" class="queue-status-card">
      <div class="queue-status-row">
        <div class="queue-status-item">
          <span class="queue-label">当前排队中</span>
          <ElBadge :value="queueStatus.queued" :max="999" type="primary" class="queue-badge">
            <span class="queue-num" :class="{ 'num-active': queueStatus.queued > 0 }">{{ queueStatus.queued }}</span>
          </ElBadge>
          <span class="queue-hint">内存队列中等待处理</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-label">当前求解中</span>
          <ElBadge :value="queueStatus.retrying" :max="999" type="warning" class="queue-badge">
            <span class="queue-num" :class="{ 'num-active': queueStatus.retrying > 0 }">{{ queueStatus.retrying }}</span>
          </ElBadge>
          <span class="queue-hint">worker 已取出正在处理</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-label">超时记录</span>
          <ElBadge :value="queueStatus.timeout" :max="999" type="info" class="queue-badge">
            <span class="queue-num" :class="{ 'num-active': queueStatus.timeout > 0 }">{{ queueStatus.timeout }}</span>
          </ElBadge>
          <span class="queue-hint">求解超时自动终止</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-label">预检验拒绝</span>
          <ElBadge :value="queueStatus.precheckRejected" :max="999" type="warning" class="queue-badge">
            <span class="queue-num" :class="{ 'num-active': queueStatus.precheckRejected > 0 }">{{ queueStatus.precheckRejected }}</span>
          </ElBadge>
          <span class="queue-hint">不活跃/无效账号拒绝</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-label">worker 并发</span>
          <span class="queue-num">{{ queueStatus.workers }}</span>
          <span class="queue-hint">最大并行求解数</span>
        </div>
        <ElButton :loading="queueLoading" size="small" @click="loadQueueStatus">刷新</ElButton>
      </div>
      <div v-if="queueStatus.queued === 0 && queueStatus.retrying === 0" class="queue-empty-hint">
        当前队列无活跃任务（排队中/求解中是瞬态状态，通常在 1 秒内完成）
      </div>
    </ElCard>

    <!-- 趋势折线图 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>每日求解趋势</span>
          <span class="muted small">单位：次</span>
        </div>
      </template>
      <div v-if="statsLoading" class="chart-loading">
        <ElIcon class="is-loading"><Loading /></ElIcon>
        <span>加载中...</span>
      </div>
      <div v-else-if="!stats.trend || stats.trend.length === 0" class="empty-state">
        所选时间范围内暂无求解记录
      </div>
      <ArtLineChart
        v-else
        :data="trendLineData"
        :x-axis-data="trendXAxis"
        :height="'320px'"
        :show-legend="true"
        :show-area-color="true"
        :smooth="true"
      />
    </ElCard>

    <!-- 账号分组表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>账号求解分布</span>
          <span class="muted small">按账号聚合，按总次数倒序</span>
        </div>
      </template>
      <ElTable v-loading="statsLoading" :data="stats.accounts" border stripe>
        <template #empty><div class="empty-state">暂无账号求解数据</div></template>
        <ElTableColumn label="账号 ID" prop="accountId" width="100" />
        <ElTableColumn label="账号名称" min-width="160">
          <template #default="{ row }">
            <span class="account-name">{{ row.accountName || '—' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="总次数" prop="total" width="100" sortable />
        <ElTableColumn label="成功" prop="success" width="100" sortable>
          <template #default="{ row }">
            <span class="text-success">{{ row.success }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="失败" prop="fail" width="100" sortable>
          <template #default="{ row }">
            <span class="text-danger">{{ row.fail }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="成功率" width="120" sortable :sort-method="(a, b) => a.successRate - b.successRate">
          <template #default="{ row }">
            <ElTag :type="rateTagType(row.successRate)" size="small">{{ formatPercent(row.successRate) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近求解时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.lastSolveTime) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" size="small" @click="viewAccountDetail(row)">查看明细</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- 明细记录列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>求解记录明细</span>
          <div class="actions small">
            <ElInput
              v-model="listQuery.accountName"
              placeholder="账号名称模糊搜索"
              clearable
              style="width: 200px"
              @keyup.enter="onListSearch"
              @clear="onListSearch"
            />
            <ElSelect
              v-model="listQuery.status"
              placeholder="状态"
              clearable
              style="width: 130px"
              @change="onListSearch"
            >
              <ElOption label="成功" value="success" />
              <ElOption label="失败" value="fail" />
              <ElOption label="求解中" value="retrying" />
              <ElOption label="排队中" value="queued" />
              <ElOption label="超时" value="timeout" />
              <ElOption label="预检验拒绝" value="precheck_rejected" />
            </ElSelect>
            <ElSelect
              v-model="listQuery.triggerScene"
              placeholder="触发场景"
              clearable
              style="width: 170px"
              @change="onListSearch"
            >
              <ElOption v-for="item in triggerSceneOptions" :key="item.value" :label="item.label" :value="item.value" />
            </ElSelect>
            <ElButton type="primary" @click="onListSearch">查询</ElButton>
            <ElButton @click="onListReset">重置</ElButton>
          </div>
        </div>
      </template>

      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取求解记录" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="求解记录暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe>
          <template #empty>
            <div class="empty-state">
              <div v-if="isTransientStatus">当前没有{{ statusLabel(listQuery.status) }}的记录</div>
              <div v-else>暂无求解记录</div>
              <div v-if="isTransientStatus" class="empty-hint-sub">
                "{{ statusLabel(listQuery.status) }}"是瞬态状态，任务通常在 1 秒内完成。请查看上方"队列实时状态"了解当前队列情况
              </div>
            </div>
          </template>
          <ElTableColumn label="ID" prop="id" width="80" />
          <ElTableColumn label="账号" min-width="150">
            <template #default="{ row }">
              <div class="account-cell">
                <span class="account-name">{{ row.accountName || '—' }}</span>
                <span class="account-id">#{{ row.accountId }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="触发场景" width="150">
            <template #default="{ row }">
              <ElTag size="small" type="info">{{ triggerSceneLabel(row.triggerScene) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100">
            <template #default="{ row }">
              <ElTag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="结果" width="130">
            <template #default="{ row }">
              <ElTag v-if="row.result" :type="resultTagType(row.result)" size="small" effect="plain">
                {{ resultLabel(row.result) }}
              </ElTag>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="失败原因" width="140">
            <template #default="{ row }">
              <ElTag v-if="row.failureReason" :type="failureReasonTagType(row.failureReason)" size="small" effect="plain">
                {{ failureReasonLabel(row.failureReason) }}
              </ElTag>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="引擎" prop="engine" width="110">
            <template #default="{ row }">{{ row.engine || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="重试" prop="retryCount" width="70" />
          <ElTableColumn label="耗时" width="100">
            <template #default="{ row }">
              <span v-if="row.durationMs != null">{{ formatDuration(row.durationMs) }}</span>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="求解时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" size="small" @click="openDetail(row)">详情</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="listQuery.current"
            v-model:page-size="listQuery.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="list.total"
            :page-sizes="[10, 20, 50, 100]"
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>

    <!-- 详情抽屉 -->
    <ElDrawer v-model="detailDrawer.visible" title="求解记录详情" size="50%">
      <template v-if="detailDrawer.row">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="记录 ID">{{ detailDrawer.row.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="账号">{{ detailDrawer.row.accountName || '—' }}（#{{ detailDrawer.row.accountId }}）</ElDescriptionsItem>
          <ElDescriptionsItem label="触发场景">{{ triggerSceneLabel(detailDrawer.row.triggerScene) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="statusTagType(detailDrawer.row.status)" size="small">{{ statusLabel(detailDrawer.row.status) }}</ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="结果">
            <ElTag v-if="detailDrawer.row.result" :type="resultTagType(detailDrawer.row.result)" size="small" effect="plain">
              {{ resultLabel(detailDrawer.row.result) }}
            </ElTag>
            <span v-else>—</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="失败原因">
            <ElTag v-if="detailDrawer.row.failureReason" :type="failureReasonTagType(detailDrawer.row.failureReason)" size="small" effect="plain">
              {{ failureReasonLabel(detailDrawer.row.failureReason) }}
            </ElTag>
            <span v-else>—</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="引擎">{{ detailDrawer.row.engine || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="重试次数">{{ detailDrawer.row.retryCount ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="求解耗时">
            <span v-if="detailDrawer.row.durationMs != null">{{ formatDuration(detailDrawer.row.durationMs) }}</span>
            <span v-else>—</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="事件描述" :span="2">{{ detailDrawer.row.eventDesc || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="开启原因" :span="2">{{ detailDrawer.row.openReason || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="求解原因" :span="2">{{ detailDrawer.row.solveReason || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ formatDateTime(detailDrawer.row.createdAt) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新时间">{{ formatDateTime(detailDrawer.row.updatedAt) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="截图路径" :span="2">
            <code v-if="detailDrawer.row.screenshotPath" class="screenshot-path">{{ detailDrawer.row.screenshotPath }}</code>
            <span v-else class="muted">无</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="错误详情" :span="2">
            <pre class="error-text">{{ detailDrawer.row.errorMessageText || '无' }}</pre>
          </ElDescriptionsItem>
        </ElDescriptions>
      </template>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { ElTag, ElIcon } from 'element-plus'
  import { Loading } from '@element-plus/icons-vue'
  import ArtLineChart from '@/components/core/charts/art-line-chart/index.vue'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'
  import type { LineDataItem } from '@/types/component/chart'
  import {
    getCaptchaSolveStats,
    getCaptchaSolveRecords,
    getCaptchaQueueStatus,
    type CaptchaSolveStats,
    type CaptchaQueueStatus,
    type CaptchaRecordRow
  } from '@/api/captcha-records'

  defineOptions({ name: 'AdminCaptchaRecordsPage' })

  type ListState = 'loading' | 'ready' | 'error'

  const route = useRoute()
  const router = useRouter()

  // 触发场景选项（与 Python captcha_solve_record.TRIGGER_SCENE_DESC 保持一致）
  const triggerSceneOptions = [
    { value: 'ws_connect', label: 'WS 连接触发' },
    { value: 'cookie_keepalive', label: 'Cookie 保活触发' },
    { value: 'token_refresh', label: 'Token 刷新触发' },
    { value: 'manual', label: '手动触发求解' },
    { value: 'manual_retry', label: '手动重试求解' }
  ]

  const triggerSceneLabel = (scene?: string) => {
    if (!scene) return '—'
    const found = triggerSceneOptions.find(o => o.value === scene)
    return found ? found.label : scene
  }

  const statusLabel = (status?: string) => {
    if (status === 'success') return '成功'
    if (status === 'fail') return '失败'
    if (status === 'retrying') return '求解中'
    if (status === 'queued') return '排队中'
    if (status === 'timeout') return '超时'
    if (status === 'precheck_rejected') return '预检验拒绝'
    return status || '—'
  }

  const statusTagType = (status?: string): any => {
    if (status === 'success') return 'success'
    if (status === 'fail') return 'danger'
    if (status === 'retrying') return 'warning'
    if (status === 'queued') return 'primary'
    if (status === 'timeout') return 'info'
    if (status === 'precheck_rejected') return 'warning'
    return 'info'
  }

  const resultLabel = (result?: string) => {
    if (result === 'slider_success') return '滑块通过'
    if (result === 'slider_fail') return '滑块失败'
    if (result === 'precheck_fail') return '预校验拒绝'
    if (result === 'stale_terminated') return '超时终止'
    return result || '—'
  }

  const resultTagType = (result?: string): any => {
    if (result === 'slider_success') return 'success'
    if (result === 'slider_fail') return 'danger'
    if (result === 'precheck_fail') return 'warning'
    if (result === 'stale_terminated') return 'info'
    return 'info'
  }

  // 失败原因分类标签（与 Python captcha_queue.py / captcha_precheck.py 保持一致）
  const failureReasonLabel = (reason?: string) => {
    const map: Record<string, string> = {
      slider_fail: '滑块未通过',
      cookie_invalid: 'Cookie 失效',
      service_unavailable: '服务不可用',
      timeout: '求解超时',
      account_inactive: '账号不活跃',
      account_disabled: '账号已禁用',
      precheck_rejected: '预校验拒绝',
      stale_terminated: '超时终止',
    }
    return (reason && map[reason]) || reason || '—'
  }

  const failureReasonTagType = (reason?: string): any => {
    if (reason === 'cookie_invalid') return 'danger'
    if (reason === 'account_inactive' || reason === 'account_disabled') return 'warning'
    if (reason === 'precheck_rejected') return 'warning'
    if (reason === 'stale_terminated') return 'info'
    if (reason === 'service_unavailable' || reason === 'timeout') return 'warning'
    return 'danger'
  }

  // ==================== 入口过滤参数（从路由 query 读取） ====================

  const accountIdFilter = computed<number | null>(() => {
    const v = route.query.accountId
    if (!v) return null
    const n = Number(v)
    return Number.isFinite(n) && n > 0 ? n : null
  })

  const userIdFilter = computed<number | null>(() => {
    const v = route.query.userId
    if (!v) return null
    const n = Number(v)
    return Number.isFinite(n) && n > 0 ? n : null
  })

  const accountNameHint = ref('')
  const usernameHint = ref('')

  // ==================== 概览统计 ====================

  const daysRange = ref<number>(7)
  const statsLoading = ref(false)
  const stats = reactive<CaptchaSolveStats>({
    kpi: { total: 0, success: 0, fail: 0, timeout: 0, precheckRejected: 0, serviceUnavailable: 0, successRate: 0 },
    trend: [],
    accounts: []
  })

  // ==================== 队列实时状态 ====================
  const queueLoading = ref(false)
  const queueStatus = reactive<CaptchaQueueStatus>({ queued: 0, retrying: 0, timeout: 0, precheckRejected: 0, workers: 4 })
  let queueTimer: ReturnType<typeof setInterval> | null = null

  async function loadQueueStatus() {
    queueLoading.value = true
    try {
      const data = await getCaptchaQueueStatus()
      Object.assign(queueStatus, data || { queued: 0, retrying: 0, timeout: 0, precheckRejected: 0, workers: 4 })
    } catch (error: any) {
      console.warn('队列状态加载失败:', error?.message)
    } finally {
      queueLoading.value = false
    }
  }

  // 排队中/求解中是瞬态状态，空结果时给用户友好提示
  const isTransientStatus = computed(() => listQuery.status === 'queued' || listQuery.status === 'retrying')

  const rangeLabel = computed(() => {
    if (daysRange.value === 0) return '全部历史'
    if (daysRange.value === 1) return '今天'
    return `近 ${daysRange.value} 天`
  })

  const successRateClass = computed(() => {
    const rate = stats.kpi.successRate
    if (rate >= 0.9) return 'text-success'
    if (rate >= 0.7) return 'text-warning'
    return 'text-danger'
  })

  const trendXAxis = computed<string[]>(() => (stats.trend || []).map(p => p.date))
  const trendLineData = computed<LineDataItem[]>(() => [
    {
      name: '成功次数',
      data: (stats.trend || []).map(p => p.success),
      color: '#16a34a',
      showAreaColor: true
    },
    {
      name: '失败次数',
      data: (stats.trend || []).map(p => p.fail),
      color: '#dc2626',
      showAreaColor: true
    }
  ])

  async function loadStats() {
    statsLoading.value = true
    try {
      const params: any = {}
      if (daysRange.value > 0) params.days = daysRange.value
      if (accountIdFilter.value) params.accountId = accountIdFilter.value
      else if (userIdFilter.value) params.userId = userIdFilter.value
      const data = await getCaptchaSolveStats(params)
      Object.assign(stats, data || { kpi: { total: 0, success: 0, fail: 0, timeout: 0, precheckRejected: 0, serviceUnavailable: 0, successRate: 0 }, trend: [], accounts: [] })
      // 从账号分组提取账号名提示
      if (accountIdFilter.value && stats.accounts && stats.accounts.length > 0) {
        accountNameHint.value = stats.accounts[0].accountName || ''
      } else {
        accountNameHint.value = ''
      }
    } catch (error: any) {
      // 静默处理，仅控制台告警
      console.warn('求解统计加载失败:', error?.message)
    } finally {
      statsLoading.value = false
    }
  }

  function onRangeChange() {
    loadStats()
  }

  // ==================== 明细列表 ====================

  const listState = ref<ListState>('loading')
  const listError = ref('')
  const listQuery = reactive({
    current: 1,
    size: 20,
    accountName: '',
    status: '',
    triggerScene: ''
  })
  const list = reactive<{ records: CaptchaRecordRow[]; total: number }>({ records: [], total: 0 })

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    try {
      const params: any = {
        current: listQuery.current,
        size: listQuery.size
      }
      if (listQuery.accountName) params.accountName = listQuery.accountName
      if (listQuery.status) params.status = listQuery.status
      if (listQuery.triggerScene) params.triggerScene = listQuery.triggerScene
      if (accountIdFilter.value) params.accountId = accountIdFilter.value
      else if (userIdFilter.value) params.userId = userIdFilter.value
      const data = await getCaptchaSolveRecords(params)
      list.records = data.records || []
      list.total = data.total || 0
      // 从首条记录提取用户名/账号名提示
      if (userIdFilter.value && list.records.length > 0) {
        usernameHint.value = ''
      }
      listState.value = 'ready'
    } catch (error: any) {
      listError.value = error?.message || '求解记录读取失败，请检查服务状态后重试。'
      listState.value = 'error'
    }
  }

  function onListSearch() {
    listQuery.current = 1
    loadList()
  }

  function onListReset() {
    listQuery.accountName = ''
    listQuery.status = ''
    listQuery.triggerScene = ''
    listQuery.current = 1
    loadList()
  }

  // ==================== 账号分组表「查看明细」 ====================

  function viewAccountDetail(row: any) {
    // 跳转到本页，带 accountId 过滤
    router.push({ name: 'AdminCaptchaRecords', query: { accountId: row.accountId } })
  }

  function clearEntryFilter() {
    // 清除 userId / accountId 路由参数
    const q = { ...route.query }
    delete q.userId
    delete q.accountId
    router.replace({ query: q })
    listQuery.current = 1
  }

  // ==================== 详情抽屉 ====================

  const detailDrawer = reactive<{ visible: boolean; row: CaptchaRecordRow | null }>({
    visible: false,
    row: null
  })

  function openDetail(row: any) {
    detailDrawer.row = row as CaptchaRecordRow
    detailDrawer.visible = true
  }

  // ==================== 格式化辅助 ====================

  function formatNumber(value: any): string {
    const n = Number(value)
    if (!Number.isFinite(n)) return '0'
    return n.toLocaleString('zh-CN')
  }

  function formatPercent(rate: any): string {
    const n = Number(rate)
    if (!Number.isFinite(n)) return '0.00%'
    return (n * 100).toFixed(2) + '%'
  }

  function formatDateTime(value: any): string {
    if (!value) return '—'
    const text = String(value).trim()
    if (!text || text === '-') return '—'
    if (text.includes('T')) {
      const d = new Date(text)
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
      }
    }
    return text.replace('T', ' ').replace(/\.\d+.*$/, '').slice(0, 19)
  }

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms} ms`
    return (ms / 1000).toFixed(2) + ' s'
  }

  function rateTagType(rate: number): any {
    if (rate >= 0.9) return 'success'
    if (rate >= 0.7) return 'warning'
    return 'danger'
  }

  // ==================== 路由 query 变化触发加载 ====================

  watch(
    [() => route.query.userId, () => route.query.accountId],
    () => {
      listQuery.current = 1
      listQuery.accountName = ''
      listQuery.status = ''
      listQuery.triggerScene = ''
      // 同时刷新统计、队列状态和列表
      loadStats()
      loadQueueStatus()
      loadList()
    },
    { immediate: true }
  )

  // 队列实时状态定时刷新（15 秒一次，覆盖典型求解周期 2-30 秒）
  onMounted(() => {
    loadQueueStatus()
    queueTimer = setInterval(loadQueueStatus, 15000)
  })

  onUnmounted(() => {
    if (queueTimer) {
      clearInterval(queueTimer)
      queueTimer = null
    }
  })
</script>

<style scoped lang="scss">
.captcha-records-page {
  display: grid;
  gap: 18px;
}

.toolbar-card {
  border-radius: 18px;
}

.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title-row h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.page-title-row p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
  max-width: 760px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  align-items: center;
}

.actions.small {
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}

.summary-grid .el-card {
  border-radius: 14px;
  padding: 6px 4px;
}

.metric-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 26px;
  font-weight: 800;
  color: #1f2937;
  line-height: 1.1;
  margin-bottom: 4px;
}

.metric-value.text-success {
  color: #16a34a;
}

.metric-value.text-danger {
  color: #dc2626;
}

.metric-value.text-warning {
  color: #d97706;
}

.metric-sub {
  font-size: 12px;
  color: #9ca3af;
}

.filter-alert {
  border-radius: 12px;
}

.stats-scope-alert {
  border-radius: 12px;
}

.section-card {
  border-radius: 18px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-weight: 600;
  color: #1f2937;
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

.muted.small {
  font-size: 11px;
  font-weight: 400;
}

.empty-state {
  padding: 32px;
  color: #9ca3af;
  text-align: center;
}

.empty-hint-sub {
  margin-top: 8px;
  font-size: 12px;
  color: #d1d5db;
  line-height: 1.6;
}

.queue-status-card {
  border-radius: 14px;
}

.queue-status-row {
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
}

.queue-status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.queue-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
}

.queue-num {
  font-size: 28px;
  font-weight: 800;
  color: #9ca3af;
  line-height: 1.1;
}

.queue-num.num-active {
  color: #2563eb;
}

.queue-hint {
  font-size: 11px;
  color: #9ca3af;
}

.queue-empty-hint {
  margin-top: 12px;
  padding: 8px 14px;
  background: #f3f4f6;
  border-radius: 8px;
  font-size: 12px;
  color: #6b7280;
  text-align: center;
}

.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 320px;
  color: #6b7280;
}

.account-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.account-name {
  font-weight: 600;
  color: #1f2937;
}

.account-id {
  font-size: 11px;
  color: #9ca3af;
}

.text-success {
  color: #16a34a;
  font-weight: 600;
}

.text-danger {
  color: #dc2626;
  font-weight: 600;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.screenshot-path {
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
  font-size: 12px;
  color: #4b5563;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.error-text {
  margin: 0;
  padding: 8px 10px;
  background: #f9fafb;
  border-radius: 6px;
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .page-title-row h2 {
    font-size: 18px;
  }
  .actions.small {
    width: 100%;
  }
}
</style>
