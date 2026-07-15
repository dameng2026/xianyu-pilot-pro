<template>
  <div class="ai-token-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>Token 用量统计</h2>
          <p>查看平台 Token 消耗总量、每日趋势与用户维度统计数据。</p>
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
      title="正在加载 Token 统计"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="statsState === 'error'"
      state="error"
      title="Token 统计暂时不可用"
      description="统计请求失败，页面不会用 0 伪装真实用量。"
      @retry="loadAll"
    />

    <!-- 统计概览卡片 -->
    <div v-if="statsState === 'ready'" class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">前台总 Token 消耗</div>
        <div class="metric-value">{{ formatNumber(tokenStats.totalTokens || 0) }}</div>
        <div class="metric-sub">累计（输入+输出）</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">总扣费 Token</div>
        <div class="metric-value">{{ formatNumber(tokenStats.totalChargeTokens || 0) }}</div>
        <div class="metric-sub">实际从用户余额扣除</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">成功调用次数</div>
        <div class="metric-value">{{ formatNumber(tokenStats.totalCalls || 0) }}</div>
        <div class="metric-sub">累计成功调用</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">累计费用</div>
        <div class="metric-value">¥{{ cost(tokenStats.totalCostCent) }}</div>
        <div class="metric-sub">总成本（分转元）</div>
      </ElCard>
    </div>

    <!-- Token 每日趋势 -->
    <ElRow v-if="statsState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="16">
        <ElCard shadow="never" class="section-card">
          <template #header>每日 Token 消耗趋势</template>
          <div class="trend-chart-wrap">
            <div class="dual-trend">
              <div v-for="(d, i) in dailyTrend" :key="i" class="dual-col">
                <div class="dual-bars">
                  <span class="bar charge-token" :style="{ height: barHeight(d.chargeTokens, maxCharge) }" :title="`扣费: ${formatNumber(d.chargeTokens)}`"></span>
                  <span class="bar total-token" :style="{ height: barHeight(d.totalTokens, maxTotal) }" :title="`总Token: ${formatNumber(d.totalTokens)}`"></span>
                </div>
                <span class="dual-label">{{ d.statDate?.slice(5) }}</span>
              </div>
            </div>
            <div class="legend"><span><i class="total-token"></i>总 Token</span><span><i class="charge-token"></i>扣费 Token</span></div>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="8">
        <ElCard shadow="never" class="section-card">
          <template #header>每日费用趋势</template>
          <div class="trend-chart-wrap">
            <div class="dual-trend">
              <div v-for="(d, i) in dailyCost" :key="i" class="dual-col">
                <div class="dual-bars">
                  <span class="bar cost-bar" :style="{ height: barHeight(d.costCent, maxCostCent) }">
                    <span class="bar-val">¥{{ cost(d.costCent) }}</span>
                  </span>
                </div>
                <span class="dual-label">{{ d.statDate?.slice(5) }}</span>
              </div>
            </div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 场景 & 模型 Token 分布 -->
    <ElRow v-if="statsState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>场景扣费 Token 分布</template>
          <ElTable :data="costStats.byScene || []" border stripe height="300" size="small">
            <ElTableColumn prop="scene" label="场景" min-width="130" />
            <ElTableColumn prop="calls" label="调用" width="80" />
            <ElTableColumn prop="totalTokens" label="总 Token" width="120" />
            <ElTableColumn prop="chargeTokens" label="扣费 Token" width="120" />
            <ElTableColumn label="费用" width="90"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>模型扣费 Token 排行</template>
          <ElTable :data="costStats.byModel || []" border stripe height="300" size="small">
            <ElTableColumn prop="providerName" label="Provider" min-width="110" />
            <ElTableColumn prop="modelName" label="模型" min-width="140" show-overflow-tooltip />
            <ElTableColumn prop="calls" label="调用" width="70" />
            <ElTableColumn prop="chargeTokens" label="扣费 Token" width="120" />
            <ElTableColumn label="费用" width="90"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 用户 Token 用量排行 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>用户 Token 用量排行</span>
          <div class="actions small">
            <ElInput v-model="userQuery.keyword" placeholder="搜索用户名" clearable style="width: 200px" @keyup.enter="loadUserStats" />
            <ElButton :loading="userLoading" @click="loadUserStats">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState
        v-if="userState === 'loading'"
        state="loading"
        title="正在加载用户 Token 排行"
        :retryable="false"
        compact
      />
      <AdminDataState
        v-else-if="userState === 'error'"
        state="error"
        title="用户 Token 排行暂时不可用"
        description="请求失败，不能将当前状态解释为没有用户用量。"
        compact
        @retry="loadUserStats"
      />
      <AdminDataState
        v-else-if="userState === 'empty'"
        state="empty"
        title="暂无用户 Token 用量"
        description="查询已成功完成，当前范围内没有记录。"
        :retryable="false"
        compact
      />
      <ElTable v-else :data="userStats.records" border stripe @sort-change="onSortChange">
        <ElTableColumn type="index" label="排名" width="60" />
        <ElTableColumn prop="username" label="用户" min-width="140" />
        <ElTableColumn prop="calls" label="调用次数" width="110" sortable="custom" />
        <ElTableColumn prop="totalTokens" label="总 Token" width="130" sortable="custom">
          <template #default="scope">{{ formatNumber(scope.row.totalTokens) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="chargeTokens" label="扣费 Token" width="130" sortable="custom">
          <template #default="scope">{{ formatNumber(scope.row.chargeTokens) }}</template>
        </ElTableColumn>
        <ElTableColumn label="费用" width="100" sortable="custom" prop="costCent">
          <template #default="scope">¥{{ cost(scope.row.costCent) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="lastCallTime" label="最后调用" min-width="170" />
      </ElTable>
      <div v-if="userState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ userStats.total }} 位用户</span>
        <ElPagination v-model:current-page="userQuery.current" v-model:page-size="userQuery.size" layout="total, sizes, prev, pager, next, jumper" :total="userStats.total" @change="loadUserStats" />
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getAiCostStats, getAiTokenStats, getAiUserStats } from '@/api/monitor'

  defineOptions({ name: 'AdminAiToken' })

  const days = ref(7)
  const loading = ref(false)
  const userLoading = ref(false)
  const statsState = ref<'loading' | 'ready' | 'error'>('loading')
  const userState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')

  const tokenStats = ref<Record<string, any>>({})
  const costStats = ref<Record<string, any>>({})

  const dailyTrend = computed(() => tokenStats.value.dailyTokens || [])
  const dailyCost = computed(() => tokenStats.value.dailyCost || [])
  const maxCharge = computed(() => Math.max(1, ...dailyTrend.value.map((d: any) => Number(d.chargeTokens || 0))))
  const maxTotal = computed(() => Math.max(1, ...dailyTrend.value.map((d: any) => Number(d.totalTokens || 0))))
  const maxCostCent = computed(() => Math.max(1, ...dailyCost.value.map((d: any) => Number(d.costCent || 0))))

  const userStats = reactive({ records: [] as any[], total: 0 })
  const userQuery = reactive({ current: 1, size: 20, keyword: '', sortBy: 'chargeTokens', sortOrder: 'desc' })

  onMounted(() => {
    loadAll()
    loadUserStats()
  })

  async function loadAll() {
    loading.value = true
    statsState.value = 'loading'
    try {
      const [s, c] = await Promise.all([
        getAiTokenStats({ days: days.value }),
        getAiCostStats({ days: days.value })
      ])
      tokenStats.value = s || {}
      costStats.value = c || {}
      statsState.value = 'ready'
    } catch {
      tokenStats.value = {}
      costStats.value = {}
      statsState.value = 'error'
    } finally {
      loading.value = false
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
      userQuery.sortBy = 'chargeTokens'
      userQuery.sortOrder = 'desc'
    }
    userQuery.current = 1
    loadUserStats()
  }

  function barHeight(value: any, max: number) {
    const v = Number(value || 0)
    const h = max > 0 ? Math.round((v / max) * 140) : 0
    return `${Math.max(4, h)}px`
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
.ai-token-page { padding: 16px; }
.toolbar-card { margin-bottom: 16px; }
.page-title-row, .table-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.actions { display: flex; align-items: center; gap: 8px; }
.actions.small { flex-wrap: wrap; justify-content: flex-end; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.metric-label { color: var(--el-text-color-secondary); font-size: 13px; }
.metric-value { font-size: 24px; font-weight: 700; margin: 8px 0; }
.metric-sub { color: var(--el-text-color-secondary); font-size: 12px; }
.section-row { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.trend-chart-wrap { overflow-x: auto; padding: 8px 0; }
.dual-trend { display: flex; align-items: end; gap: 8px; min-height: 180px; }
.dual-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 36px; }
.dual-bars { display: flex; align-items: end; gap: 3px; height: 140px; }
.bar { width: 14px; border-radius: 4px 4px 0 0; display: block; transition: .3s; position: relative; }
.total-token { background: #7c3aed; }
.charge-token { background: #2463eb; }
.cost-bar { background: linear-gradient(180deg, #16a34a, #22c55e); width: 24px; display: flex; align-items: flex-start; justify-content: center; }
.bar-val { font-size: 9px; color: #fff; white-space: nowrap; margin-top: 1px; }
.dual-label { font-size: 11px; color: var(--el-text-color-secondary); }
.legend { display: flex; gap: 18px; margin-top: 12px; color: var(--el-text-color-secondary); font-size: 13px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
.legend .total-token { background: #7c3aed; }
.legend .charge-token { background: #2463eb; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 1200px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .summary-grid { grid-template-columns: 1fr; } .page-title-row, .table-header { flex-direction: column; align-items: stretch; } }
</style>
