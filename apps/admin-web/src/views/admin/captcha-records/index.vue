<template>
  <div class="captcha-records-page">
    <!-- 惊喜提示：用户不在场时的自动求解摘要 -->
    <Transition name="surprise-pop">
      <div v-if="surprise.visible" class="surprise-banner" role="status" aria-live="polite">
        <div class="surprise-glow surprise-glow-1"></div>
        <div class="surprise-glow surprise-glow-2"></div>
        <button
          class="surprise-close"
          type="button"
          aria-label="关闭提示"
          @click="closeSurprise"
        >
          <ElIcon><Close /></ElIcon>
        </button>
        <div class="surprise-icon">
          <ElIcon><MagicStick /></ElIcon>
        </div>
        <div class="surprise-body">
          <div class="surprise-headline">在您离开的这段时间里</div>
          <div class="surprise-stats">
            滑块求解已自动为您化解
            <span class="surprise-number">{{ surprise.displaySuccess }}</span>
            次验证
          </div>
          <div class="surprise-meta">
            共触发 {{ surprise.total }} 次｜成功 {{ surprise.success }} 次｜涉及 {{ surprise.accountCount }} 个账号
            <span v-if="surprise.lastSolveTime">｜最近一次 {{ formatRelativeTime(surprise.lastSolveTime) }}</span>
          </div>
        </div>
      </div>
    </Transition>

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
        <div class="metric-sub">{{ rangeLabel }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功次数</div>
        <div class="metric-value text-success">{{ formatNumber(stats.kpi.success) }}</div>
        <div class="metric-sub">status=success</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">失败次数</div>
        <div class="metric-value text-danger">{{ formatNumber(stats.kpi.fail) }}</div>
        <div class="metric-sub">status=fail</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功率</div>
        <div class="metric-value" :class="successRateClass">{{ formatPercent(stats.kpi.successRate) }}</div>
        <div class="metric-sub">成功 / 总数</div>
      </ElCard>
    </div>

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
              <ElOption label="进行中" value="retrying" />
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
          <template #empty><div class="empty-state">暂无求解记录</div></template>
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
  import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { ElTag, ElIcon } from 'element-plus'
  import { Close, Loading, MagicStick } from '@element-plus/icons-vue'
  import ArtLineChart from '@/components/core/charts/art-line-chart/index.vue'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'
  import type { LineDataItem } from '@/types/component/chart'
  import {
    getCaptchaSolveStats,
    getCaptchaSolveRecords,
    getCaptchaSilentSummary,
    type CaptchaSolveStats,
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
    if (status === 'retrying') return '进行中'
    return status || '—'
  }

  const statusTagType = (status?: string): any => {
    if (status === 'success') return 'success'
    if (status === 'fail') return 'danger'
    if (status === 'retrying') return 'warning'
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
    kpi: { total: 0, success: 0, fail: 0, successRate: 0 },
    trend: [],
    accounts: []
  })

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
      Object.assign(stats, data || { kpi: { total: 0, success: 0, fail: 0, successRate: 0 }, trend: [], accounts: [] })
      // 从账号分组提取账号名提示
      if (accountIdFilter.value && stats.accounts && stats.accounts.length > 0) {
        accountNameHint.value = stats.accounts[0].accountName || ''
      } else {
        accountNameHint.value = ''
      }
    } catch (error: any) {
      // 静默处理，仅控制台告警
      // eslint-disable-next-line no-console
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

  // ==================== 惊喜提示：用户不在场时的自动求解摘要 ====================

  // sessionStorage key：记录上次访问本页面的时间（ISO 字符串）
  const LAST_VISIT_KEY = 'captcha_records_last_visit'
  // 距上次访问至少 5 分钟才显示提示，避免频繁刷新页面时打扰
  const MIN_INTERVAL_MS = 5 * 60 * 1000

  const surprise = reactive({
    visible: false,
    total: 0,
    success: 0,
    fail: 0,
    accountCount: 0,
    since: '',
    until: '',
    lastSolveTime: '',
    // 动画展示用，从 0 递增到 success
    displaySuccess: 0
  })

  let countUpRaf = 0

  function easeOutCubic(t: number): number {
    return 1 - Math.pow(1 - t, 3)
  }

  function animateCountUp(from: number, to: number, duration = 1500) {
    if (typeof window === 'undefined' || !window.requestAnimationFrame) {
      surprise.displaySuccess = to
      return
    }
    cancelAnimationFrame(countUpRaf)
    const start = performance.now()
    const step = (now: number) => {
      const elapsed = now - start
      const t = Math.min(1, elapsed / duration)
      const eased = easeOutCubic(t)
      surprise.displaySuccess = Math.round(from + (to - from) * eased)
      if (t < 1) {
        countUpRaf = requestAnimationFrame(step)
      }
    }
    countUpRaf = requestAnimationFrame(step)
  }

  function closeSurprise() {
    surprise.visible = false
  }

  /**
   * 计算"刚刚 / N 分钟前 / N 小时前 / N 天前"相对时间文案
   */
  function formatRelativeTime(value: string): string {
    if (!value) return ''
    const t = new Date(value.replace(' ', 'T')).getTime()
    if (isNaN(t)) return ''
    const diff = Date.now() - t
    if (diff < 60 * 1000) return '刚刚'
    if (diff < 60 * 60 * 1000) return Math.floor(diff / 60000) + ' 分钟前'
    if (diff < 24 * 60 * 60 * 1000) return Math.floor(diff / 3600000) + ' 小时前'
    return Math.floor(diff / (24 * 3600000)) + ' 天前'
  }

  /**
   * 进入页面时加载"用户不在场时"自动求解摘要。
   * 1. 读取 sessionStorage 中的上次访问时间
   * 2. 距上次访问 < 5 分钟则跳过（避免刷新打扰）
   * 3. 调用 silent-summary 接口（仅统计 ws_connect/cookie_keepalive/token_refresh）
   * 4. 若 total > 0，显示惊喜提示并触发数字递增动画
   * 5. 立即写入新的访问时间
   */
  async function loadSurprise() {
    const now = Date.now()
    const lastVisitStr = sessionStorage.getItem(LAST_VISIT_KEY)
    let lastVisit: Date | null = null
    if (lastVisitStr) {
      const t = Date.parse(lastVisitStr)
      if (!isNaN(t)) lastVisit = new Date(t)
    }

    // 立即更新访问时间，确保下次进入时基线正确
    sessionStorage.setItem(LAST_VISIT_KEY, new Date(now).toISOString())

    // 首次访问或距上次访问 < 5 分钟，不显示提示
    if (!lastVisit || now - lastVisit.getTime() < MIN_INTERVAL_MS) {
      return
    }

    try {
      const params: any = { since: lastVisit.toISOString() }
      if (accountIdFilter.value) params.accountId = accountIdFilter.value
      else if (userIdFilter.value) params.userId = userIdFilter.value

      const data = await getCaptchaSilentSummary(params)
      surprise.total = data.total || 0
      surprise.success = data.success || 0
      surprise.fail = data.fail || 0
      surprise.accountCount = data.accountCount || 0
      surprise.since = data.since || ''
      surprise.until = data.until || ''
      surprise.lastSolveTime = data.lastSolveTime || ''

      // 有自动求解记录才显示提示
      if (surprise.total > 0) {
        surprise.visible = true
        // 等待 Transition 进入后再触发数字动画
        requestAnimationFrame(() => animateCountUp(0, surprise.success, 1500))
      }
    } catch (error: any) {
      // 静默失败，不打扰用户
      // eslint-disable-next-line no-console
      console.warn('滑块自动求解摘要加载失败:', error?.message)
    }
  }

  onMounted(() => {
    loadSurprise()
  })

  onBeforeUnmount(() => {
    if (countUpRaf) cancelAnimationFrame(countUpRaf)
  })

  // ==================== 路由 query 变化触发加载 ====================

  watch(
    [() => route.query.userId, () => route.query.accountId],
    () => {
      listQuery.current = 1
      listQuery.accountName = ''
      listQuery.status = ''
      listQuery.triggerScene = ''
      // 同时刷新统计和列表
      loadStats()
      loadList()
    },
    { immediate: true }
  )
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
