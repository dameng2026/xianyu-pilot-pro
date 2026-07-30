<template>
  <div class="growth-dashboard-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>增长中心仪表盘</h2>
          <p>查看拉新、收益、提现、邀请码等核心指标与趋势，掌握增长全局。</p>
        </div>
        <div class="actions">
          <ElRadioGroup v-model="trendDays" size="small" @change="loadTrend">
            <ElRadioButton :value="7">7天</ElRadioButton>
            <ElRadioButton :value="30">30天</ElRadioButton>
            <ElRadioButton :value="90">90天</ElRadioButton>
          </ElRadioGroup>
          <ElButton :loading="loading" @click="loadAll">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 统计卡片 -->
    <AdminDataState v-if="summaryState === 'loading'" state="loading" title="正在读取增长汇总" compact />
    <AdminDataState
      v-else-if="summaryState === 'error'"
      state="error"
      title="增长汇总暂不可用"
      :description="summaryError"
      retry-text="重试汇总"
      compact
      @retry="loadDashboard"
    />
    <div v-else class="summary-grid">
      <ElCard shadow="never" class="metric-card metric-card-blue">
        <div class="metric-top">
          <div class="metric-icon metric-icon-blue">
            <i class="ri-user-add-line" />
          </div>
          <div class="metric-body">
            <div class="metric-label">累计拉新人数</div>
            <div class="metric-value">{{ formatNumber(summary.totalReferrals) }}</div>
            <div class="metric-sub">活跃邀请人 {{ formatNumber(summary.totalReferrers) }} 名</div>
          </div>
        </div>
      </ElCard>
      <ElCard shadow="never" class="metric-card metric-card-green">
        <div class="metric-top">
          <div class="metric-icon metric-icon-green">
            <i class="ri-money-cny-circle-line" />
          </div>
          <div class="metric-body">
            <div class="metric-label">累计分成收益</div>
            <div class="metric-value text-success">¥{{ formatAmount(summary.totalCommissionAmount) }}</div>
            <div class="metric-sub">已发放 Token {{ formatNumber(summary.totalTokenReward) }} 个</div>
          </div>
        </div>
      </ElCard>
      <ElCard shadow="never" class="metric-card metric-card-orange">
        <div class="metric-top">
          <div class="metric-icon metric-icon-orange">
            <i class="ri-bank-card-line" />
          </div>
          <div class="metric-body">
            <div class="metric-label">累计提现金额</div>
            <div class="metric-value text-warning">¥{{ formatAmount(summary.totalWithdrawnAmount) }}</div>
            <div class="metric-sub">提现申请 {{ formatNumber(summary.totalWithdrawals) }} 笔</div>
          </div>
        </div>
      </ElCard>
      <ElCard shadow="never" class="metric-card metric-card-purple">
        <div class="metric-top">
          <div class="metric-icon metric-icon-purple">
            <i class="ri-coupon-3-line" />
          </div>
          <div class="metric-body">
            <div class="metric-label">活跃邀请码</div>
            <div class="metric-value">{{ formatNumber(summary.activeInviteCodes) }}</div>
            <div class="metric-sub">待审批提现 {{ formatNumber(summary.pendingWithdrawals) }} 笔</div>
          </div>
        </div>
      </ElCard>
    </div>

    <!-- 今日数据 -->
    <ElCard shadow="never" class="section-card today-card">
      <template #header>
        <div class="section-title">
          <span class="title-text">今日数据</span>
          <span class="title-sub">今日 0 点至今的拉新与收益</span>
        </div>
      </template>
      <div class="today-grid">
        <div class="today-item today-total">
          <div class="today-label">今日新增拉新</div>
          <div class="today-value">{{ formatNumber(today.newReferrals) }}</div>
          <div class="today-sub">人</div>
        </div>
        <div class="today-item">
          <div class="today-label">今日分成收益</div>
          <div class="today-value text-success">¥{{ formatAmount(today.commissionAmount) }}</div>
          <div class="today-sub">¥{{ formatAmount(today.tokenReward) }} Token 奖励</div>
        </div>
        <div class="today-item">
          <div class="today-label">今日提现申请</div>
          <div class="today-value text-warning">{{ formatNumber(today.newWithdrawals) }}</div>
          <div class="today-sub">笔</div>
        </div>
      </div>
    </ElCard>

    <!-- 收益趋势 + 排行榜 -->
    <div class="trend-leader-grid">
      <ElCard shadow="never" class="section-card trend-card">
        <template #header>
          <div class="section-title">
            <span class="title-text">收益趋势</span>
            <span class="title-sub">近 {{ trendDays }} 天的分成收益与 Token 奖励</span>
          </div>
        </template>
        <AdminDataState v-if="trendState === 'loading'" state="loading" title="正在读取收益趋势" compact />
        <AdminDataState
          v-else-if="trendState === 'error'"
          state="error"
          title="收益趋势暂不可用"
          :description="trendError"
          retry-text="重试"
          compact
          @retry="loadTrend"
        />
        <template v-else>
          <div class="trend-summary">
            <div class="trend-summary-item">
              <span class="trend-summary-label">区间分成</span>
              <b class="text-success">¥{{ formatAmount(trend.totalCash) }}</b>
            </div>
            <div class="trend-summary-item">
              <span class="trend-summary-label">区间 Token</span>
              <b>{{ formatNumber(trend.totalToken) }} 个</b>
            </div>
          </div>
          <ArtLineChart
            v-if="(trend.dates || []).length"
            :data="trendCashSeries"
            :xAxisData="trend.dates || []"
            :colors="['#2d78f6', '#79a9fb']"
            height="280px"
            :showLegend="true"
            :lineWidth="3"
            symbol="circle"
            :symbolSize="6"
            :animationDelay="120"
          />
          <AdminDataState v-else state="empty" title="暂无趋势数据" :retryable="false" compact />
        </template>
      </ElCard>

      <ElCard shadow="never" class="section-card leaderboard-card">
        <template #header>
          <div class="section-title">
            <span class="title-text">拉新排行榜 TOP 10</span>
            <ElLink type="primary" :underline="false" @click="goLeaderboard">查看全部</ElLink>
          </div>
        </template>
        <AdminDataState v-if="leaderboardState === 'loading'" state="loading" title="正在读取排行榜" compact />
        <AdminDataState
          v-else-if="leaderboardState === 'error'"
          state="error"
          title="排行榜暂不可用"
          :description="leaderboardError"
          retry-text="重试"
          compact
          @retry="loadLeaderboard"
        />
        <template v-else>
          <ElTable :data="leaderboard" border stripe height="340">
            <template #empty><div class="empty-state">暂无排行数据</div></template>
            <ElTableColumn label="排名" width="60" align="center">
              <template #default="scope">
                <span :class="['rank-badge', `rank-${scope.$index + 1}`]">{{ scope.$index + 1 }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn label="用户" min-width="140" show-overflow-tooltip>
              <template #default="scope">
                <div class="user-cell">
                  <span class="user-avatar" v-if="scope.row.avatar">
                    <img :src="scope.row.avatar" alt="" />
                  </span>
                  <span class="user-name">{{ scope.row.nickname || scope.row.username || `用户${scope.row.userId}` }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="代理等级" width="110">
              <template #default="scope">
                <ElTag v-if="scope.row.tierName" size="small" type="warning">{{ scope.row.tierName }}</ElTag>
                <span v-else class="muted">—</span>
              </template>
            </ElTableColumn>
            <ElTableColumn label="拉新人数" width="100">
              <template #default="scope">
                <b>{{ formatNumber(scope.row.totalReferrals) }}</b>
                <small class="muted">（有效 {{ formatNumber(scope.row.validReferrals) }}）</small>
              </template>
            </ElTableColumn>
            <ElTableColumn label="累计收益" width="120">
              <template #default="scope">
                <span class="text-success">¥{{ formatAmount(scope.row.totalEarnings) }}</span>
              </template>
            </ElTableColumn>
          </ElTable>
        </template>
      </ElCard>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { getAdminGrowthDashboard, getAdminGrowthLeaderboard, getAdminGrowthTrend } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'
  import ArtLineChart from '@/components/core/charts/art-line-chart/index.vue'

  defineOptions({ name: 'AdminGrowthDashboardPage' })

  const router = useRouter()

  const loading = ref(false)
  const trendDays = ref(30)

  // 汇总
  const summary = reactive<any>({
    totalReferrers: 0,
    totalReferrals: 0,
    totalWithdrawals: 0,
    pendingWithdrawals: 0,
    totalWithdrawnAmount: 0,
    totalCommissionAmount: 0,
    totalTokenReward: 0,
    activeInviteCodes: 0
  })
  const summaryState = ref<'loading' | 'ready' | 'error'>('loading')
  const summaryError = ref('')

  // 今日数据
  const today = reactive<any>({
    newReferrals: 0,
    newWithdrawals: 0,
    commissionAmount: 0,
    tokenReward: 0
  })

  // 趋势
  const trend = reactive<any>({ dates: [], cashSeries: [], tokenSeries: [], totalCash: 0, totalToken: 0 })
  const trendState = ref<'loading' | 'ready' | 'error'>('loading')
  const trendError = ref('')

  // 排行榜
  const leaderboard = ref<any[]>([])
  const leaderboardState = ref<'loading' | 'ready' | 'error'>('loading')
  const leaderboardError = ref('')

  // 折线图：双系列数据
  const trendCashSeries = computed(() => {
    const cashArr = (trend.cashSeries || []).map((v: any) => Number(v) / 100)
    const tokenArr = trend.tokenSeries || []
    return [
      { name: '收益（¥）', data: cashArr },
      { name: 'Token 奖励', data: tokenArr }
    ]
  })

  function formatNumber(value: any): string {
    const n = Number(value)
    if (!Number.isFinite(n)) return '0'
    return n.toLocaleString('zh-CN')
  }

  function formatAmount(cent: any): string {
    const n = Number(cent)
    if (!Number.isFinite(n)) return '0.00'
    return (n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  async function loadDashboard() {
    summaryState.value = 'loading'
    summaryError.value = ''
    try {
      const d = await getAdminGrowthDashboard()
      const s = d?.summary || {}
      Object.assign(summary, {
        totalReferrers: s.totalReferrers ?? 0,
        totalReferrals: s.totalReferrals ?? 0,
        totalWithdrawals: s.totalWithdrawals ?? 0,
        pendingWithdrawals: s.pendingWithdrawals ?? 0,
        totalWithdrawnAmount: s.totalWithdrawnAmount ?? 0,
        totalCommissionAmount: s.totalCommissionAmount ?? 0,
        totalTokenReward: s.totalTokenReward ?? 0,
        activeInviteCodes: s.activeInviteCodes ?? 0
      })
      const t = d?.today || {}
      Object.assign(today, {
        newReferrals: t.newReferrals ?? 0,
        newWithdrawals: t.newWithdrawals ?? 0,
        commissionAmount: t.commissionAmount ?? 0,
        tokenReward: t.tokenReward ?? 0
      })
      summaryState.value = 'ready'
    } catch (e: any) {
      summaryError.value = e?.message || '未知错误'
      summaryState.value = 'error'
    }
  }

  async function loadTrend() {
    trendState.value = 'loading'
    trendError.value = ''
    try {
      const t = await getAdminGrowthTrend(trendDays.value)
      Object.assign(trend, {
        dates: t?.dates || [],
        cashSeries: t?.cashSeries || [],
        tokenSeries: t?.tokenSeries || [],
        totalCash: t?.totalCash ?? 0,
        totalToken: t?.totalToken ?? 0
      })
      trendState.value = 'ready'
    } catch (e: any) {
      trendError.value = e?.message || '未知错误'
      trendState.value = 'error'
    }
  }

  async function loadLeaderboard() {
    leaderboardState.value = 'loading'
    leaderboardError.value = ''
    try {
      leaderboard.value = await getAdminGrowthLeaderboard(10)
      leaderboardState.value = 'ready'
    } catch (e: any) {
      leaderboardError.value = e?.message || '未知错误'
      leaderboardState.value = 'error'
    }
  }

  async function loadAll() {
    loading.value = true
    await Promise.all([loadDashboard(), loadTrend(), loadLeaderboard()])
    loading.value = false
  }

  function goLeaderboard() {
    router.push({ name: 'AdminGrowthLeaderboard' })
  }

  onMounted(() => {
    loadAll()
  })
</script>

<style scoped lang="scss">
  .growth-dashboard-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .toolbar-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .page-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;

    h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 600;
    }
    p {
      margin: 0;
      font-size: 13px;
      color: #6b7280;
    }
    .actions {
      display: flex;
      gap: 8px;
      align-items: center;
    }
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;

    @media (max-width: 1280px) {
      grid-template-columns: repeat(2, 1fr);
    }
    @media (max-width: 720px) {
      grid-template-columns: 1fr;
    }
  }

  .metric-card {
    :deep(.el-card__body) {
      padding: 18px 20px;
    }
  }

  .metric-top {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .metric-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 22px;
    flex-shrink: 0;

    &.metric-icon-blue {
      background: linear-gradient(135deg, #4f8bff 0%, #2563eb 100%);
      box-shadow: 0 6px 14px rgba(37, 99, 235, 0.22);
    }
    &.metric-icon-green {
      background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
      box-shadow: 0 6px 14px rgba(16, 185, 129, 0.22);
    }
    &.metric-icon-orange {
      background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
      box-shadow: 0 6px 14px rgba(245, 158, 11, 0.22);
    }
    &.metric-icon-purple {
      background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%);
      box-shadow: 0 6px 14px rgba(124, 58, 237, 0.22);
    }
  }

  .metric-label {
    font-size: 12px;
    color: #6b7280;
  }
  .metric-value {
    font-size: 22px;
    font-weight: 700;
    color: #111827;
    margin-top: 2px;
    line-height: 1.2;
  }
  .metric-sub {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 2px;
  }
  .text-success {
    color: #10b981;
  }
  .text-warning {
    color: #f59e0b;
  }

  .today-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title-text {
      font-size: 14px;
      font-weight: 600;
      color: #111827;
    }
    .title-sub {
      font-size: 12px;
      color: #9ca3af;
      margin-left: 8px;
    }
  }

  .today-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;

    @media (max-width: 720px) {
      grid-template-columns: 1fr;
    }
  }

  .today-item {
    padding: 14px 18px;
    border-radius: 10px;
    background: #f9fafb;
    border: 1px solid #f0f0f0;

    .today-label {
      font-size: 12px;
      color: #6b7280;
    }
    .today-value {
      font-size: 22px;
      font-weight: 700;
      color: #111827;
      margin-top: 4px;
    }
    .today-sub {
      font-size: 12px;
      color: #9ca3af;
      margin-top: 2px;
    }
    &.today-total {
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      border-color: #bfdbfe;
    }
  }

  .trend-leader-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 16px;

    @media (max-width: 1280px) {
      grid-template-columns: 1fr;
    }
  }

  .trend-summary {
    display: flex;
    gap: 24px;
    margin-bottom: 12px;

    .trend-summary-item {
      display: flex;
      align-items: baseline;
      gap: 8px;

      .trend-summary-label {
        font-size: 12px;
        color: #6b7280;
      }
      b {
        font-size: 16px;
      }
    }
  }

  .user-cell {
    display: flex;
    align-items: center;
    gap: 8px;

    .user-avatar {
      width: 26px;
      height: 26px;
      border-radius: 50%;
      overflow: hidden;
      flex-shrink: 0;
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }
    .user-name {
      font-size: 13px;
    }
  }

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #f3f4f6;
    color: #6b7280;
    font-size: 12px;
    font-weight: 700;

    &.rank-1 {
      background: linear-gradient(135deg, #fde68a, #f59e0b);
      color: #fff;
    }
    &.rank-2 {
      background: linear-gradient(135deg, #e5e7eb, #9ca3af);
      color: #fff;
    }
    &.rank-3 {
      background: linear-gradient(135deg, #fed7aa, #fb923c);
      color: #fff;
    }
  }

  .muted {
    color: #9ca3af;
    font-size: 12px;
  }
  .empty-state {
    text-align: center;
    color: #9ca3af;
    padding: 24px;
  }
</style>
