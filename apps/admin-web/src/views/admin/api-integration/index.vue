<template>
  <div class="api-integration-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>API 对接</h2>
          <p>
            查看开放 API 滑块求解能力的对接情况、成功率趋势、Token 消耗与租户分布。
            统计口径与「滑块求解记录」一致：失败原因为「服务不可用 / 预检验拒绝 / 超时 / 超时终止」的请求不计入失败次数与成功率。
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

    <!-- KPI 卡片 -->
    <div class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">求解总次数</div>
        <div class="metric-value">{{ formatNumber(stats.kpi.total) }}</div>
        <div class="metric-sub">{{ rangeLabel }}（已排除服务不可用/预检验/超时）</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功次数</div>
        <div class="metric-value text-success">{{ formatNumber(stats.kpi.success_count) }}</div>
        <div class="metric-sub">status=success</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">失败次数</div>
        <div class="metric-value text-danger">{{ formatNumber(stats.kpi.fail_count) }}</div>
        <div class="metric-sub">不含服务不可用/预检验/超时/超时终止</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功率</div>
        <div class="metric-value" :class="successRateClass">{{ formatPercent(successRate) }}</div>
        <div class="metric-sub">成功 / (成功+失败)</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日 Token 消耗</div>
        <div class="metric-value">{{ formatNumber(todayKpi.charged_tokens) }}</div>
        <div class="metric-sub">仅成功求解扣费</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日求解次数</div>
        <div class="metric-value">{{ formatNumber(todayKpi.total) }}</div>
        <div class="metric-sub">今日成功 {{ formatNumber(todayKpi.success_count) }} 次</div>
      </ElCard>
    </div>

    <!-- 统计口径说明 -->
    <ElAlert type="info" :closable="false" class="stats-scope-alert" show-icon>
      <template #title>
        <span>
          统计口径：失败原因为「服务不可用」「预检验拒绝」「超时」「超时终止（stale_terminated）」的请求不计入成功率与失败次数统计。
          当前范围已排除：
          <b>服务不可用 {{ stats.kpi.service_unavailable_count || 0 }}</b> 次、
          <b>预检验拒绝 {{ stats.kpi.precheck_rejected_count || 0 }}</b> 次、
          <b>超时 {{ stats.kpi.timeout_count || 0 }}</b> 次。
          此类记录可在下方明细列表按状态筛选查看。
        </span>
      </template>
    </ElAlert>

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
        所选时间范围内暂无 API 对接求解记录
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

    <!-- 租户分组表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>租户求解分布</span>
          <span class="muted small">按租户聚合，按总次数倒序</span>
        </div>
      </template>
      <ElTable v-loading="statsLoading" :data="stats.tenants" border stripe>
        <template #empty><div class="empty-state">暂无租户求解数据</div></template>
        <ElTableColumn label="租户 ID" prop="tenant_id" width="120" />
        <ElTableColumn label="密钥前缀" min-width="140">
          <template #default="{ row }">
            <span class="account-name">{{ row.api_key_prefix || '—' }}</span>
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
        <ElTableColumn label="成功率" width="120" sortable :sort-method="(a, b) => tenantSuccessRate(a) - tenantSuccessRate(b)">
          <template #default="{ row }">
            <ElTag :type="rateTagType(tenantSuccessRate(row))" size="small">{{ formatPercent(tenantSuccessRate(row)) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Token 消耗" width="120" sortable prop="charged_tokens">
          <template #default="{ row }">
            <span class="text-primary">{{ formatNumber(row.charged_tokens) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近求解时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_solve_time) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" size="small" @click="viewTenantDetail(row)">查看明细</ElButton>
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
              v-model="listQuery.tenantId"
              placeholder="租户 ID"
              clearable
              style="width: 130px"
              @keyup.enter="onListSearch"
              @clear="onListSearch"
            />
            <ElSelect
              v-model="listQuery.status"
              placeholder="状态"
              clearable
              style="width: 140px"
              @change="onListSearch"
            >
              <ElOption label="成功" value="success" />
              <ElOption label="失败" value="fail" />
              <ElOption label="求解中" value="retrying" />
              <ElOption label="排队中" value="queued" />
              <ElOption label="超时" value="timeout" />
              <ElOption label="预检验拒绝" value="precheck_rejected" />
            </ElSelect>
            <ElInput
              v-model="listQuery.apiKeyPrefix"
              placeholder="密钥前缀"
              clearable
              style="width: 150px"
              @keyup.enter="onListSearch"
              @clear="onListSearch"
            />
            <ElInput
              v-model="listQuery.keyword"
              placeholder="request_id / 错误信息"
              clearable
              style="width: 200px"
              @keyup.enter="onListSearch"
              @clear="onListSearch"
            />
            <ElDatePicker
              v-model="listQuery.dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 360px"
              @change="onListSearch"
            />
            <ElButton type="primary" @click="onListSearch">查询</ElButton>
            <ElButton @click="onListReset">重置</ElButton>
          </div>
        </div>
      </template>

      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取 API 对接记录" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="API 对接记录暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe>
          <template #empty>
            <div class="empty-state">暂无 API 对接求解记录</div>
          </template>
          <ElTableColumn label="ID" prop="id" width="80" />
          <ElTableColumn label="租户" width="100">
            <template #default="{ row }">
              <span>#{{ row.tenant_id }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="密钥前缀" width="130">
            <template #default="{ row }">
              <span>{{ row.api_key_prefix || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="请求 ID" min-width="180">
            <template #default="{ row }">
              <span class="mono-text">{{ row.request_id }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="客户端 IP" width="130">
            <template #default="{ row }">{{ row.client_ip || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="110">
            <template #default="{ row }">
              <ElTag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="结果" width="120">
            <template #default="{ row }">
              <ElTag v-if="row.result" :type="resultTagType(row.result)" size="small" effect="plain">
                {{ resultLabel(row.result) }}
              </ElTag>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="失败原因" width="140">
            <template #default="{ row }">
              <ElTag v-if="row.failure_reason" :type="failureReasonTagType(row.failure_reason)" size="small" effect="plain">
                {{ failureReasonLabel(row.failure_reason) }}
              </ElTag>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token" width="90">
            <template #default="{ row }">
              <span class="text-primary">{{ row.token_charged ?? 0 }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="耗时" width="100">
            <template #default="{ row }">
              <span v-if="row.duration_ms != null">{{ formatDuration(row.duration_ms) }}</span>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="求解时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
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
    <ElDrawer v-model="detailDrawer.visible" title="API 对接记录详情" size="50%">
      <template v-if="detailDrawer.row">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="记录 ID">{{ detailDrawer.row.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="租户 ID">{{ detailDrawer.row.tenant_id ?? '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="密钥前缀">{{ detailDrawer.row.api_key_prefix || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="客户端 IP">{{ detailDrawer.row.client_ip || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="请求 ID" :span="2">
            <code class="mono-text">{{ detailDrawer.row.request_id }}</code>
          </ElDescriptionsItem>
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
            <ElTag v-if="detailDrawer.row.failure_reason" :type="failureReasonTagType(detailDrawer.row.failure_reason)" size="small" effect="plain">
              {{ failureReasonLabel(detailDrawer.row.failure_reason) }}
            </ElTag>
            <span v-else>—</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="触发场景">{{ triggerSceneLabel(detailDrawer.row.trigger_scene) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="引擎">{{ detailDrawer.row.engine || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="重试次数">{{ detailDrawer.row.retry_count ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="Token 扣费">
            <span class="text-primary">{{ detailDrawer.row.token_charged ?? 0 }}</span>
            <ElTag v-if="detailDrawer.row.token_charge_failed" type="warning" size="small" effect="plain" style="margin-left: 8px">扣费失败需对账</ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="求解耗时">
            <span v-if="detailDrawer.row.duration_ms != null">{{ formatDuration(detailDrawer.row.duration_ms) }}</span>
            <span v-else>—</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="事件描述" :span="2">{{ detailDrawer.row.event_desc || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="入队时间">{{ formatDateTime(detailDrawer.row.queued_at) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="开始时间">{{ formatDateTime(detailDrawer.row.started_at) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="完成时间">{{ formatDateTime(detailDrawer.row.finished_at) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ formatDateTime(detailDrawer.row.created_at) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="错误详情" :span="2">
            <pre class="error-text">{{ detailDrawer.row.error_message || '无' }}</pre>
          </ElDescriptionsItem>
        </ElDescriptions>
      </template>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue'
  import { ElTag, ElIcon } from 'element-plus'
  import { Loading } from '@element-plus/icons-vue'
  import ArtLineChart from '@/components/core/charts/art-line-chart/index.vue'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'
  import type { LineDataItem } from '@/types/component/chart'
  import {
    getAdminStats,
    getAdminRecords,
    getAdminTodayToken,
    type ApiIntegrationStats,
    type ApiIntegrationKpi,
    type ApiIntegrationRecordRow
  } from '@/api/api-integration'

  defineOptions({ name: 'AdminApiIntegrationPage' })

  type ListState = 'loading' | 'ready' | 'error'

  // ==================== 概览统计 ====================

  const daysRange = ref<number>(7)
  const statsLoading = ref(false)
  const stats = reactive<ApiIntegrationStats>({
    kpi: { total: 0, success_count: 0, fail_count: 0, timeout_count: 0, precheck_rejected_count: 0, service_unavailable_count: 0, charged_tokens: 0 },
    trend: [],
    tenants: []
  })

  // 今日 KPI（独立加载，不受 daysRange 影响）
  const todayKpi = reactive<ApiIntegrationKpi>({
    total: 0, success_count: 0, fail_count: 0, timeout_count: 0, precheck_rejected_count: 0, service_unavailable_count: 0, charged_tokens: 0
  })

  const rangeLabel = computed(() => {
    if (daysRange.value === 0) return '全部历史'
    if (daysRange.value === 1) return '今天'
    return `近 ${daysRange.value} 天`
  })

  const successRate = computed(() => {
    const denom = stats.kpi.success_count + stats.kpi.fail_count
    if (denom <= 0) return 0
    return stats.kpi.success_count / denom
  })

  const successRateClass = computed(() => {
    const rate = successRate.value
    if (rate >= 0.9) return 'text-success'
    if (rate >= 0.7) return 'text-warning'
    return 'text-danger'
  })

  function tenantSuccessRate(row: any): number {
    const denom = Number(row.success || 0) + Number(row.fail || 0)
    if (denom <= 0) return 0
    return Number(row.success || 0) / denom
  }

  const trendXAxis = computed<string[]>(() => (stats.trend || []).map(p => p.date))
  const trendLineData = computed<LineDataItem[]>(() => [
    {
      name: '成功次数',
      data: (stats.trend || []).map(p => p.success),
      color: '#16a34a' as any,
      showAreaColor: true
    },
    {
      name: '失败次数',
      data: (stats.trend || []).map(p => p.fail),
      color: '#dc2626' as any,
      showAreaColor: true
    }
  ])

  async function loadStats() {
    statsLoading.value = true
    try {
      const data = await getAdminStats(daysRange.value > 0 ? daysRange.value : undefined)
      Object.assign(stats, data || {
        kpi: { total: 0, success_count: 0, fail_count: 0, timeout_count: 0, precheck_rejected_count: 0, service_unavailable_count: 0, charged_tokens: 0 },
        trend: [],
        tenants: []
      })
    } catch (error: any) {
      console.warn('API 对接统计加载失败:', error?.message)
    } finally {
      statsLoading.value = false
    }
  }

  async function loadTodayToken() {
    try {
      const data = await getAdminTodayToken()
      Object.assign(todayKpi, data || {
        total: 0, success_count: 0, fail_count: 0, timeout_count: 0, precheck_rejected_count: 0, service_unavailable_count: 0, charged_tokens: 0
      })
    } catch (error: any) {
      console.warn('API 对接今日 Token 加载失败:', error?.message)
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
    tenantId: '',
    status: '',
    apiKeyPrefix: '',
    keyword: '',
    dateRange: null as [string, string] | null
  })
  const list = reactive<{ records: ApiIntegrationRecordRow[]; total: number }>({ records: [], total: 0 })

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    try {
      const params: any = {
        current: listQuery.current,
        size: listQuery.size
      }
      if (listQuery.tenantId) {
        const tid = Number(listQuery.tenantId)
        if (Number.isFinite(tid) && tid > 0) params.tenantId = tid
      }
      if (listQuery.status) params.status = listQuery.status
      if (listQuery.apiKeyPrefix) params.apiKeyPrefix = listQuery.apiKeyPrefix
      if (listQuery.keyword) params.keyword = listQuery.keyword
      if (listQuery.dateRange && listQuery.dateRange.length === 2) {
        params.startTime = listQuery.dateRange[0]
        params.endTime = listQuery.dateRange[1]
      }
      const data = await getAdminRecords(params)
      list.records = data.records || []
      list.total = data.total || 0
      listState.value = 'ready'
    } catch (error: any) {
      listError.value = error?.message || 'API 对接记录读取失败，请检查服务状态后重试。'
      listState.value = 'error'
    }
  }

  function onListSearch() {
    listQuery.current = 1
    loadList()
  }

  function onListReset() {
    listQuery.tenantId = ''
    listQuery.status = ''
    listQuery.apiKeyPrefix = ''
    listQuery.keyword = ''
    listQuery.dateRange = null
    listQuery.current = 1
    loadList()
  }

  // ==================== 租户分组表「查看明细」 ====================

  function viewTenantDetail(row: any) {
    listQuery.tenantId = String(row.tenant_id ?? '')
    listQuery.current = 1
    loadList()
  }

  // ==================== 详情抽屉 ====================

  const detailDrawer = reactive<{ visible: boolean; row: ApiIntegrationRecordRow | null }>({
    visible: false,
    row: null
  })

  function openDetail(row: any) {
    detailDrawer.row = row as ApiIntegrationRecordRow
    detailDrawer.visible = true
  }

  // ==================== 标签与格式化辅助 ====================

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

  const triggerSceneLabel = (scene?: string) => {
    if (!scene) return '—'
    if (scene === 'api') return 'API 调用'
    return scene
  }

  const failureReasonLabel = (reason?: string) => {
    const map: Record<string, string> = {
      slider_fail: '滑块未通过',
      cookie_invalid: 'Cookie 失效',
      service_unavailable: '服务不可用',
      timeout: '求解超时',
      account_inactive: '账号不活跃',
      account_disabled: '账号已禁用',
      precheck_rejected: '预校验拒绝',
      stale_terminated: '超时终止'
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

  // ==================== 初始化加载 ====================

  onMounted(() => {
    loadStats()
    loadTodayToken()
    loadList()
  })
</script>

<style scoped lang="scss">
.api-integration-page {
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

.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 320px;
  color: #6b7280;
}

.account-name {
  font-weight: 600;
  color: #1f2937;
}

.mono-text {
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
  font-size: 12px;
  color: #4b5563;
  word-break: break-all;
}

.text-success {
  color: #16a34a;
  font-weight: 600;
}

.text-danger {
  color: #dc2626;
  font-weight: 600;
}

.text-primary {
  color: #2563eb;
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
