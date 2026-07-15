<template>
  <div class="monitor-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>智能运营监控</h2>
          <p>集中查看 AI 调用成本、自动回复命中效果与工作流执行失败率。</p>
        </div>
        <div class="actions">
          <ElSelect v-model="days" style="width: 140px" @change="loadAll">
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
      v-if="monitorState === 'loading'"
      state="loading"
      title="正在加载运营监控"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="monitorState === 'error'"
      state="error"
      title="运营监控暂时不可用"
      description="监控数据未完整加载，页面不会用 0 伪装真实指标。"
      @retry="loadAll"
    />

    <div v-if="monitorState === 'ready'" class="summary-grid">
      <ElCard shadow="never"><div class="metric-label">今日 AI 调用</div><div class="metric-value">{{ ai.todayCalls || 0 }}</div><div class="metric-sub">Token {{ ai.todayChargeTokens || 0 }} / 成本 ¥{{ cost(ai.todayCostCent) }}</div></ElCard>
      <ElCard shadow="never"><div class="metric-label">低余额用户</div><div class="metric-value danger">{{ ai.lowBalanceUsers || 0 }}</div><div class="metric-sub">Token 余额低于 100</div></ElCard>
      <ElCard shadow="never"><div class="metric-label">今日自动回复命中</div><div class="metric-value">{{ autoReply.todayHits || 0 }}</div><div class="metric-sub">自动允许 {{ autoReply.todayAutoAllowed || 0 }} / 人工接管 {{ autoReply.todayManual || 0 }}</div></ElCard>
      <ElCard shadow="never"><div class="metric-label">今日工作流失败</div><div class="metric-value warning">{{ workflow.todayFailed || 0 }}</div><div class="metric-sub">运行中 {{ workflow.running || 0 }} / 今日执行 {{ workflow.todayExecutions || 0 }}</div></ElCard>
    </div>

    <ElRow v-if="monitorState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>AI 场景成本分布</template>
          <ElTable :data="ai.byScene || []" border stripe height="300">
            <ElTableColumn prop="scene" label="场景" min-width="160" />
            <ElTableColumn prop="calls" label="调用" width="90" />
            <ElTableColumn prop="chargeTokens" label="扣费 Token" width="120" />
            <ElTableColumn label="成本" width="100"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>自动回复动作分布</template>
          <ElTable :data="autoReply.actions || []" border stripe height="300">
            <ElTableColumn prop="action" label="动作" min-width="160" />
            <ElTableColumn prop="count" label="数量" width="120" />
          </ElTable>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElRow v-if="monitorState === 'ready'" :gutter="16" class="section-row">
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>模型调用排行</template>
          <ElTable :data="ai.byModel || []" border stripe height="300">
            <ElTableColumn prop="providerName" label="Provider" min-width="150" />
            <ElTableColumn prop="modelName" label="模型" min-width="180" show-overflow-tooltip />
            <ElTableColumn prop="calls" label="调用" width="90" />
            <ElTableColumn label="成本" width="100"><template #default="scope">¥{{ cost(scope.row.costCent) }}</template></ElTableColumn>
          </ElTable>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :lg="12">
        <ElCard shadow="never" class="section-card">
          <template #header>工作流状态分布</template>
          <ElTable :data="workflow.byStatus || []" border stripe height="300">
            <ElTableColumn prop="status" label="状态" min-width="160" />
            <ElTableColumn prop="count" label="数量" width="120" />
          </ElTable>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>AI 调用日志</span>
          <div class="actions small">
            <ElInput v-model="usageQuery.keyword" placeholder="模型/Provider/请求ID/用户" clearable style="width: 260px" @keyup.enter="loadUsage" />
            <ElInput v-model="usageQuery.scene" placeholder="场景" clearable style="width: 180px" @keyup.enter="loadUsage" />
            <ElButton :loading="usageLoading" @click="loadUsage">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState
        v-if="usageState === 'loading'"
        state="loading"
        title="正在加载 AI 调用日志"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="usageState === 'error'"
        state="error"
        title="AI 调用日志暂时不可用"
        description="请求失败，不能将当前状态解释为没有调用记录。"
        @retry="loadUsage"
      />
      <AdminDataState
        v-else-if="usageState === 'empty'"
        state="empty"
        title="暂无 AI 调用日志"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="usage.records" border stripe>
        <ElTableColumn prop="createdTime" label="时间" min-width="170" />
        <ElTableColumn prop="scene" label="场景" min-width="140" />
        <ElTableColumn prop="username" label="用户" min-width="120" />
        <ElTableColumn prop="modelName" label="模型" min-width="180" show-overflow-tooltip />
        <ElTableColumn prop="totalTokens" label="总 Token" width="110" />
        <ElTableColumn prop="chargeTokens" label="扣费 Token" width="120" />
        <ElTableColumn label="成本" width="90"><template #default="scope">¥{{ scope.row.costYuan || cost(scope.row.costCent) }}</template></ElTableColumn>
        <ElTableColumn prop="statusText" label="状态" width="90" />
      </ElTable>
      <div v-if="usageState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ usage.total }} 条</span>
        <ElPagination v-model:current-page="usageQuery.current" v-model:page-size="usageQuery.size" layout="total, sizes, prev, pager, next, jumper" :total="usage.total" @change="loadUsage" />
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getAiMonitor, getAiUsagePage, getAutoReplyMonitor, getWorkflowMonitor } from '@/api/monitor'

  defineOptions({ name: 'AdminSmartMonitor' })

  const days = ref(7)
  const loading = ref(false)
  const usageLoading = ref(false)
  const monitorState = ref<'loading' | 'ready' | 'error'>('loading')
  const usageState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const ai = ref<Record<string, any>>({})
  const autoReply = ref<Record<string, any>>({})
  const workflow = ref<Record<string, any>>({})
  const usage = reactive({ records: [] as any[], total: 0 })
  const usageQuery = reactive({ current: 1, size: 20, keyword: '', scene: '' })

  onMounted(() => {
    loadAll()
    loadUsage()
  })

  async function loadAll() {
    loading.value = true
    monitorState.value = 'loading'
    try {
      const [aiRes, autoRes, wfRes] = await Promise.all([
        getAiMonitor({ days: days.value }),
        getAutoReplyMonitor({ days: days.value }),
        getWorkflowMonitor({ days: days.value })
      ])
      ai.value = aiRes || {}
      autoReply.value = autoRes || {}
      workflow.value = wfRes || {}
      monitorState.value = 'ready'
    } catch {
      ai.value = {}
      autoReply.value = {}
      workflow.value = {}
      monitorState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  async function loadUsage() {
    usageLoading.value = true
    usageState.value = 'loading'
    try {
      const params = Object.fromEntries(Object.entries(usageQuery).filter(([, v]) => v !== '' && v !== undefined && v !== null))
      const page = await getAiUsagePage(params)
      usage.records = page?.records || []
      usage.total = page?.total || 0
      usageState.value = usage.records.length > 0 ? 'ready' : 'empty'
    } catch {
      usage.records = []
      usage.total = 0
      usageState.value = 'error'
    } finally {
      usageLoading.value = false
    }
  }

  function cost(value: any) {
    const n = Number(value || 0)
    return (n / 100).toFixed(4).replace(/0+$/, '').replace(/\.$/, '') || '0'
  }
</script>

<style scoped>
.monitor-page { padding: 16px; }
.toolbar-card { margin-bottom: 16px; }
.page-title-row, .table-header, .pagination-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.actions { display: flex; align-items: center; gap: 8px; }
.actions.small { flex-wrap: wrap; justify-content: flex-end; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.metric-label { color: var(--el-text-color-secondary); font-size: 13px; }
.metric-value { font-size: 28px; font-weight: 700; margin: 8px 0; }
.metric-value.danger { color: var(--el-color-danger); }
.metric-value.warning { color: var(--el-color-warning); }
.metric-sub { color: var(--el-text-color-secondary); font-size: 12px; }
.section-row { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.pagination-row { margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 1200px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .summary-grid { grid-template-columns: 1fr; } .page-title-row, .table-header { align-items: stretch; flex-direction: column; } }
</style>
