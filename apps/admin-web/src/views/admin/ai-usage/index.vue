<template>
  <div class="ai-usage-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>AI 调用日志</h2>
          <p>查看 AI 调用记录、Token 消耗与费用明细。</p>
        </div>
        <div class="actions">
          <ElSelect v-model="days" style="width: 140px" @change="handleDaysChange">
            <ElOption :value="1" label="近 1 天" />
            <ElOption :value="7" label="近 7 天" />
            <ElOption :value="30" label="近 30 天" />
            <ElOption :value="90" label="近 90 天" />
          </ElSelect>
          <ElButton type="primary" :loading="loading" @click="loadAll">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <AdminDataState
      v-if="statsState === 'loading'"
      state="loading"
      title="正在加载 AI 用量统计"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="statsState === 'error'"
      state="error"
      title="AI 用量统计暂时不可用"
      description="统计请求失败，页面不会用 0 伪装真实调用量或费用。"
      @retry="loadAll"
    />

    <!-- 统计概览卡片 -->
    <div v-if="statsState === 'ready'" class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">总调用次数</div>
        <div class="metric-value">{{ stats.totalCalls || 0 }}</div>
        <div class="metric-sub">成功调用</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">总 Token 消耗</div>
        <div class="metric-value">{{ formatNumber(stats.totalTokens || 0) }}</div>
        <div class="metric-sub">输入 {{ formatNumber(stats.totalPromptTokens || 0) }} / 输出 {{ formatNumber(stats.totalCompletionTokens || 0) }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">缓存命中 Token</div>
        <div class="metric-value">{{ formatNumber(stats.totalCachedTokens || 0) }}</div>
        <div class="metric-sub">DeepSeek 上下文缓存（低价计费）</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">总扣费 Token</div>
        <div class="metric-value">{{ formatNumber(stats.totalChargeTokens || 0) }}</div>
        <div class="metric-sub">实际扣除量</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">总费用</div>
        <div class="metric-value">¥{{ cost(stats.totalCostCent) }}</div>
        <div class="metric-sub">累计成本</div>
      </ElCard>
    </div>

    <!-- 费用趋势 & 模型排行 -->
    <ElRow v-if="statsState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="14">
        <ElCard shadow="never" class="section-card">
          <template #header>每日费用趋势（分）</template>
          <div class="trend-chart-wrap">
            <div class="trend-chart">
              <div v-for="(d, i) in costTrend.dates" :key="i" class="trend-col">
                <div class="trend-bar" :style="{ height: trendBarHeight(d.costCent) }">
                  <span class="trend-val">¥{{ cost(d.costCent) }}</span>
                </div>
                <span class="trend-label">{{ d.statDate?.slice(5) }}</span>
              </div>
            </div>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="10">
        <ElCard shadow="never" class="section-card">
          <template #header>模型费用排行</template>
          <ElTable :data="costStats.byModel || []" border stripe height="300" size="small">
            <ElTableColumn prop="providerName" label="Provider" min-width="110" />
            <ElTableColumn prop="modelName" label="模型" min-width="140" show-overflow-tooltip />
            <ElTableColumn prop="calls" label="调用" width="65" />
            <ElTableColumn prop="cachedTokens" label="缓存命中" width="90" />
            <ElTableColumn label="费用" width="85"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 场景分布 -->
    <ElRow v-if="statsState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>场景费用分布</template>
          <ElTable :data="costStats.byScene || []" border stripe height="260" size="small">
            <ElTableColumn prop="scene" label="场景" min-width="130" />
            <ElTableColumn prop="calls" label="调用" width="65" />
            <ElTableColumn prop="cachedTokens" label="缓存命中" width="90" />
            <ElTableColumn prop="chargeTokens" label="扣费 Token" width="100" />
            <ElTableColumn label="费用" width="85"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>单用户调用统计</template>
          <div class="user-stats-toolbar">
            <ElInput v-model="userQuery.keyword" placeholder="搜索用户名" clearable style="width: 200px" @keyup.enter="loadUserStats" />
            <ElButton size="small" :loading="userLoading" @click="loadUserStats">查询</ElButton>
          </div>
          <AdminDataState
            v-if="userState === 'loading'"
            state="loading"
            title="正在加载用户统计"
            :retryable="false"
            compact
          />
          <AdminDataState
            v-else-if="userState === 'error'"
            state="error"
            title="用户统计暂时不可用"
            description="请求失败，不能将当前状态解释为没有用户调用。"
            compact
            @retry="loadUserStats"
          />
          <AdminDataState
            v-else-if="userState === 'empty'"
            state="empty"
            title="暂无用户调用统计"
            description="查询已成功完成，当前范围内没有记录。"
            :retryable="false"
            compact
          />
          <ElTable v-else :data="userStats.records" border stripe height="260" size="small" @sort-change="onSortChange">
            <ElTableColumn prop="username" label="用户" min-width="110" />
            <ElTableColumn prop="calls" label="调用次数" width="90" sortable="custom" />
            <ElTableColumn prop="cachedTokens" label="缓存命中" width="90" />
            <ElTableColumn prop="totalTokens" label="总 Token" width="100" sortable="custom" />
            <ElTableColumn prop="chargeTokens" label="扣费 Token" width="100" sortable="custom" />
            <ElTableColumn label="费用" width="85" sortable="custom" prop="costCent"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
          <div v-if="userState === 'ready'" class="pagination-row">
            <span class="muted">共 {{ userStats.total }} 人</span>
            <ElPagination v-model:current-page="userQuery.current" v-model:page-size="userQuery.size" layout="total, sizes, prev, pager, next, jumper" :total="userStats.total" size="small" @change="loadUserStats" />
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 调用日志表格 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>调用日志明细</span>
          <div class="actions small">
            <ElInput v-model="logQuery.keyword" placeholder="模型/Provider/请求ID/用户" clearable style="width: 240px" @keyup.enter="loadLogs" />
            <ElInput v-model="logQuery.userId" placeholder="用户 ID 精确过滤" clearable style="width: 160px" @keyup.enter="loadLogs" @clear="loadLogs" />
            <ElInput v-model="logQuery.scene" placeholder="场景" clearable style="width: 160px" @keyup.enter="loadLogs" />
            <ElSelect v-model="logQuery.status" clearable placeholder="状态" style="width: 120px">
              <ElOption label="成功" value="success" />
              <ElOption label="失败" value="failed" />
            </ElSelect>
            <ElButton :loading="logLoading" @click="onLogSearch">查询</ElButton>
            <ElButton v-if="activeUserIdFilter" @click="clearUserIdFilter">清除用户过滤</ElButton>
          </div>
        </div>
      </template>
      <ElAlert v-if="activeUserIdFilter" type="success" :closable="false" class="user-filter-alert" show-icon>
        <template #title>
          <span>
            已按用户过滤：用户 ID <b>{{ activeUserIdFilter }}</b>
            ｜
            <router-link :to="{ name: 'AdminRechargeRecords', query: { userId: activeUserIdFilter } }" class="inline-link">
              查看该用户的充值记录
            </router-link>
            ｜
            <ElLink type="primary" :underline="false" @click="clearUserIdFilter">查看全部用户消费记录</ElLink>
          </span>
        </template>
      </ElAlert>
      <AdminDataState
        v-if="logState === 'loading'"
        state="loading"
        title="正在加载 AI 调用日志"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="logState === 'error'"
        state="error"
        title="AI 调用日志暂时不可用"
        description="请求失败，不能将当前状态解释为没有调用记录。"
        @retry="loadLogs"
      />
      <AdminDataState
        v-else-if="logState === 'empty'"
        state="empty"
        title="暂无 AI 调用日志"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="logs.records" border stripe height="480">
        <ElTableColumn prop="createdTime" label="时间" min-width="150" />
        <ElTableColumn prop="scene" label="场景" min-width="110" />
        <ElTableColumn prop="username" label="用户" min-width="100" />
        <ElTableColumn prop="providerName" label="Provider" min-width="110" />
        <ElTableColumn prop="modelName" label="模型" min-width="150" show-overflow-tooltip />
        <ElTableColumn prop="promptTokens" label="输入Token" width="95" />
        <ElTableColumn label="缓存命中" width="90">
          <template #default="scope">
            <span :class="{ 'cache-hit': scope.row.cachedTokens > 0 }">{{ scope.row.cachedTokens || 0 }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="completionTokens" label="输出Token" width="95" />
        <ElTableColumn prop="totalTokens" label="总Token" width="85" />
        <ElTableColumn prop="chargeTokens" label="扣费Token" width="95" />
        <ElTableColumn label="费用" width="80"><template #default="scope">¥{{ scope.row.costYuan || cost(scope.row.costCent) }}</template></ElTableColumn>
        <ElTableColumn prop="statusText" label="状态" width="75" />
      </ElTable>
      <div v-if="logState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ logs.total }} 条</span>
        <ElPagination v-model:current-page="logQuery.current" v-model:page-size="logQuery.size" layout="total, sizes, prev, pager, next, jumper" :total="logs.total" @change="loadLogs" />
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { getAiCostStats, getAiTokenStats, getAiUsagePage, getAiUserStats } from '@/api/monitor'

  defineOptions({ name: 'AdminAiUsage' })

  const route = useRoute()
  const router = useRouter()

  const days = ref(7)
  const loading = ref(false)
  const logLoading = ref(false)
  const userLoading = ref(false)
  const statsState = ref<'loading' | 'ready' | 'error'>('loading')
  const logState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const userState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')

  const stats = ref<Record<string, any>>({})
  const costStats = ref<Record<string, any>>({})
  const costTrend = computed(() => {
    const daily = costStats.value.dailyTrend || []
    return {
      dates: daily,
      maxCent: Math.max(1, ...daily.map((d: any) => Number(d.costCent || 0)))
    }
  })

  const logs = reactive({ records: [] as any[], total: 0 })
  const logQuery = reactive({ current: 1, size: 20, keyword: '', scene: '', status: '', userId: '' })

  const userStats = reactive({ records: [] as any[], total: 0 })
  const userQuery = reactive({ current: 1, size: 10, keyword: '', sortBy: 'calls', sortOrder: 'desc' })

  // 从路由 query.userId 读取用户过滤（账号管理处跳转过来时携带）
  const activeUserIdFilter = computed<number | null>(() => {
    const v = route.query.userId
    if (!v) return null
    const n = Number(v)
    return Number.isFinite(n) && n > 0 ? n : null
  })

  onMounted(() => {
    // 初始化时同步路由中的 userId 到输入框
    if (activeUserIdFilter.value) {
      logQuery.userId = String(activeUserIdFilter.value)
    }
    loadAll()
    loadLogs()
    loadUserStats()
  })

  // 路由 userId 变化时自动加载该用户的消费记录
  watch(
    () => route.query.userId,
    (val) => {
      logQuery.userId = val ? String(val) : ''
      logQuery.current = 1
      loadLogs()
    }
  )

  async function loadAll() {
    loading.value = true
    statsState.value = 'loading'
    try {
      const [s, c] = await Promise.all([
        getAiTokenStats({ days: days.value }),
        getAiCostStats({ days: days.value })
      ])
      stats.value = s || {}
      costStats.value = c || {}
      statsState.value = 'ready'
    } catch {
      // 错误已由 HTTP 拦截器统一处理
      stats.value = {}
      costStats.value = {}
      statsState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  async function loadLogs() {
    logLoading.value = true
    logState.value = 'loading'
    try {
      const params: Record<string, any> = { current: logQuery.current, size: logQuery.size }
      if (logQuery.keyword) params.keyword = logQuery.keyword
      if (logQuery.scene) params.scene = logQuery.scene
      if (logQuery.status) params.status = logQuery.status
      // 优先使用路由 userId 过滤，其次使用输入框的值
      const filterUserId = activeUserIdFilter.value || (logQuery.userId ? Number(logQuery.userId) : null)
      if (filterUserId && Number.isFinite(filterUserId) && filterUserId > 0) {
        params.userId = filterUserId
      }
      const page = await getAiUsagePage(params)
      logs.records = page?.records || []
      logs.total = page?.total || 0
      logState.value = logs.records.length > 0 ? 'ready' : 'empty'
    } catch {
      logs.records = []
      logs.total = 0
      logState.value = 'error'
    } finally {
      logLoading.value = false
    }
  }

  // 手动查询：重置页码后加载
  function onLogSearch() {
    logQuery.current = 1
    loadLogs()
  }

  // 清除用户过滤：清空输入框与路由 query，重新加载全部
  function clearUserIdFilter() {
    logQuery.userId = ''
    logQuery.current = 1
    if (route.query.userId) {
      router.replace({ name: 'AdminAiUsage', query: {} })
    } else {
      loadLogs()
    }
  }

  async function loadUserStats() {
    userLoading.value = true
    userState.value = 'loading'
    try {
      const page = await getAiUserStats({
        current: userQuery.current,
        size: userQuery.size,
        days: days.value,
        keyword: userQuery.keyword,
        sortBy: userQuery.sortBy,
        sortOrder: userQuery.sortOrder
      })
      userStats.records = page?.records || []
      userStats.total = page?.total || 0
      userState.value = userStats.records.length > 0 ? 'ready' : 'empty'
    } catch {
      userStats.records = []
      userStats.total = 0
      userState.value = 'error'
    } finally {
      userLoading.value = false
    }
  }

  function handleDaysChange() {
    userQuery.current = 1
    void Promise.all([loadAll(), loadUserStats()])
  }

  function onSortChange(sort: any) {
    if (sort.prop && sort.order) {
      userQuery.sortBy = sort.prop
      userQuery.sortOrder = sort.order === 'ascending' ? 'asc' : 'desc'
    } else {
      userQuery.sortBy = 'calls'
      userQuery.sortOrder = 'desc'
    }
    userQuery.current = 1
    loadUserStats()
  }

  function trendBarHeight(costCent: any) {
    const v = Number(costCent || 0)
    const max = costTrend.value.maxCent
    const h = max > 0 ? Math.round((v / max) * 160) : 0
    return h > 0 ? `${Math.max(20, h)}px` : '4px'
  }

  function formatNumber(n: any) {
    return Number(n || 0).toLocaleString()
  }

  function cost(value: any) {
    const n = Number(value || 0)
    return (n / 100).toFixed(4).replace(/0+$/, '').replace(/\.$/, '') || '0'
  }
</script>

<style scoped>
.ai-usage-page { padding: 16px; }
.toolbar-card { margin-bottom: 16px; }
.page-title-row, .table-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.actions { display: flex; align-items: center; gap: 8px; }
.actions.small { flex-wrap: wrap; justify-content: flex-end; }
.summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.metric-label { color: var(--el-text-color-secondary); font-size: 13px; }
.metric-value { font-size: 24px; font-weight: 700; margin: 8px 0; }
.metric-sub { color: var(--el-text-color-secondary); font-size: 12px; }
.section-row { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.trend-chart-wrap { overflow-x: auto; padding: 8px 0; }
.trend-chart { display: flex; align-items: end; gap: 8px; min-height: 200px; }
.trend-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 36px; }
.trend-bar { width: 100%; max-width: 40px; background: linear-gradient(180deg, #2463eb, #7c3aed); border-radius: 6px 6px 0 0; display: flex; align-items: flex-start; justify-content: center; transition: .3s; min-height: 4px; }
.trend-val { font-size: 10px; color: #fff; white-space: nowrap; margin-top: 2px; }
.trend-label { font-size: 11px; color: var(--el-text-color-secondary); }
.user-stats-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.cache-hit { color: #10b981; font-weight: 600; }
.user-filter-alert { margin-bottom: 12px; }
.user-filter-alert .inline-link { color: var(--el-color-primary); text-decoration: none; margin: 0 4px; }
.user-filter-alert .inline-link:hover { text-decoration: underline; }
@media (max-width: 1200px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .summary-grid { grid-template-columns: 1fr; } .page-title-row, .table-header { flex-direction: column; align-items: stretch; } }
</style>
