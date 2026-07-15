<template>
  <div class="admin-page">
    <template v-if="moduleKey === 'dashboard'">
      <div class="overview-shell">
        <AdminDataState
          v-if="dashboardState.status === 'loading'"
          state="loading"
          title="正在加载运营仪表盘"
          description="正在读取核心业务与监控数据。"
        />
        <AdminDataState
          v-else-if="dashboardState.status === 'empty'"
          state="empty"
          title="暂无可展示的仪表盘数据"
          description="接口已成功响应，但当前没有业务或监控记录。"
          :retryable="false"
        />
        <AdminDataState
          v-else-if="dashboardState.status === 'unavailable'"
          state="error"
          title="运营仪表盘暂不可用"
          :description="dashboardState.message"
          retry-text="重新加载仪表盘"
          @retry="loadDashboard"
        />
        <AdminDataState
          v-else-if="dashboardState.status === 'degraded'"
          state="degraded"
          title="仪表盘数据不完整"
          :description="dashboardState.message"
          retry-text="重试全部数据"
          @retry="loadDashboard"
        />

        <div v-show="dashboardContentVisible" class="dashboard-data-content">
        <ElCard shadow="never" class="dashboard-hero dashboard-hero--light">
          <div class="hero-copy">
            <span class="hero-eyebrow">运营指挥视角</span>
            <h2>{{ dashboardOverview.hero.title }}</h2>
            <p>{{ dashboardOverview.hero.description }}</p>
          </div>
          <div class="hero-side">
            <div class="hero-side__top">
              <div class="hero-status-cluster">
                <div class="hero-chip-grid">
                  <div v-for="chip in heroPrimaryChips" :key="chip.key" :class="['hero-chip', toneClass(chip.tone)]">
                    <span>{{ chip.label }}</span>
                    <strong :class="toneClass(chip.tone)">{{ chip.value }}</strong>
                  </div>
                </div>
                <div v-if="heroSecondaryChip" :class="['hero-status-note', toneClass(heroSecondaryChip.tone)]">
                  <span>{{ heroSecondaryChip.label }}</span>
                  <strong :class="toneClass(heroSecondaryChip.tone)">{{ heroSecondaryChip.value }}</strong>
                </div>
              </div>
              <div class="hero-visual" aria-hidden="true">
                <span class="hero-visual__halo"></span>
                <span class="hero-visual__beam"></span>
                <span class="hero-visual__bar hero-visual__bar--sm"></span>
                <span class="hero-visual__bar hero-visual__bar--md"></span>
                <span class="hero-visual__bar hero-visual__bar--lg"></span>
                <span class="hero-visual__dot hero-visual__dot--left"></span>
                <span class="hero-visual__dot hero-visual__dot--right"></span>
              </div>
            </div>
            <div class="hero-actions">
              <ElButton type="primary" size="large" :loading="loading" @click="loadDashboard">刷新概览</ElButton>
              <ElButton size="large" @click="refreshRealtimeStats">刷新实时状态</ElButton>
              <ElButton v-if="isSuperAdmin" size="large" @click="goModule('/admin/user-permission/users')">进入用户管理</ElButton>
            </div>
          </div>
        </ElCard>

        <section class="overview-section">
          <div class="overview-section__heading">
            <div>
              <h3>经营总览</h3>
              <p>从平台、交易、客服和利润四个维度查看关键指标。</p>
            </div>
          </div>
          <div class="kpi-group-grid">
            <ElCard
              v-for="group in dashboardOverview.kpiGroups"
              :key="group.key"
              shadow="never"
              :class="['surface-card', 'kpi-group-card', `kpi-group-card--${group.key}`]"
            >
              <div class="group-title">{{ group.title }}</div>
              <div class="group-metrics">
                <div v-for="item in group.items" :key="item.key" class="mini-metric">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong class="mini-metric__value">{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                  <small v-if="item.note" class="mini-metric__note">{{ item.note }}</small>
                </div>
              </div>
            </ElCard>
          </div>
        </section>

        <section class="overview-section">
          <div class="overview-section__heading">
            <div>
              <h3>收入与 AI 成本</h3>
              <p>卡片展示今日收入与估算利润；趋势图仅展示已接入的 AI 成本历史，不推算历史收入。</p>
            </div>
            <ElRadioGroup v-model="trendRange" size="small" @change="loadTrendByRange(trendRange)">
              <ElRadioButton :value="7">7天</ElRadioButton>
              <ElRadioButton :value="30">30天</ElRadioButton>
              <ElRadioButton :value="90">90天</ElRadioButton>
            </ElRadioGroup>
          </div>
          <div class="finance-grid">
            <ElCard shadow="never" class="surface-card finance-chart-card">
              <div class="finance-chart-stage">
                <div class="finance-chart-stage__header">
                  <div class="chart-legend chart-legend--wide">
                    <span v-for="series in dashboardOverview.finance.chart.series" :key="series.key">
                      <i :style="{ background: series.color }"></i>{{ series.label }}
                    </span>
                  </div>
                  <span class="finance-chart-stage__tag">AI 成本 {{ trendRange }} 日走势</span>
                </div>
                <ArtLineChart
                  v-if="dashboardOverview.finance.chart.labels.length"
                  :data="lineChartData(dashboardOverview.finance.chart, 'finance')"
                  :xAxisData="dashboardOverview.finance.chart.labels"
                  :colors="chartColors(dashboardOverview.finance.chart)"
                  :yAxisMin="lineChartBounds(dashboardOverview.finance.chart, 'finance').min"
                  :yAxisMax="lineChartBounds(dashboardOverview.finance.chart, 'finance').max"
                  :showYAxisLabel="false"
                  :splitNumber="4"
                  :gridPadding="{ top: 24, right: 8, bottom: 0, left: 6 }"
                  height="268px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :lineWidth="4"
                  symbol="circle"
                  :symbolSize="6"
                  :animationDelay="120"
                />
                <AdminDataState
                  v-else
                  state="empty"
                  :title="dashboardSourceFailed('AI 成本趋势') ? 'AI 成本趋势暂不可用' : '暂无 AI 成本趋势'"
                  :description="dashboardSourceFailed('AI 成本趋势') ? 'AI 成本趋势请求失败，请重试后再查看。' : '接口已成功响应，但当前没有带日期的 AI 成本记录。'"
                  :retryable="false"
                  compact
                />
              </div>
            </ElCard>

            <div class="finance-side-panel">
              <div class="finance-stat-grid">
                <ElCard
                  v-for="item in dashboardOverview.finance.cards"
                  :key="item.key"
                  shadow="never"
                  :class="['surface-card', 'finance-stat-card', toneClass(item.tone)]"
                >
                  <div class="finance-stat-card__top">
                    <span class="mini-metric__label finance-stat-card__label">{{ item.label }}</span>
                    <span :class="['finance-stat-card__marker', toneClass(item.tone)]"></span>
                  </div>
                  <strong class="finance-stat-card__value">{{ item.value }}</strong>
                  <div class="finance-stat-card__meta">
                    <span :class="['mini-metric__delta', 'finance-stat-card__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                    <small v-if="item.note" class="mini-metric__note finance-stat-card__note">{{ item.note }}</small>
                  </div>
                  <span class="finance-stat-card__glow" aria-hidden="true"></span>
                </ElCard>
              </div>
              <ElCard shadow="never" class="surface-card finance-gauge-card">
                <div class="gauge-title">利润率分析</div>
                <div class="gauge-ring" :style="gaugeStyle(dashboardOverview.finance.gauge.value)">
                  <div class="gauge-ring__inner">
                    <strong>{{ dashboardOverview.finance.gauge.value === null ? '--' : `${dashboardOverview.finance.gauge.value}%` }}</strong>
                    <span>{{ dashboardOverview.finance.gauge.detail }}</span>
                  </div>
                </div>
                <div class="breakdown-list">
                  <div v-for="row in dashboardOverview.finance.breakdown" :key="row.label" class="status-row">
                    <span :class="['status-dot', toneClass(row.tone)]"></span>
                    <span class="status-row__label">{{ row.label }}</span>
                    <strong>{{ row.value }}</strong>
                  </div>
                </div>
              </ElCard>
            </div>
          </div>
        </section>

        <section class="overview-section overview-section--compact">
          <div class="two-col-grid">
            <ElCard shadow="never" class="surface-card feature-card feature-card--funnel">
              <div class="section-card__header">
                <div>
                  <h4>订单转化漏斗</h4>
                  <span>近7天</span>
                </div>
              </div>
              <div class="funnel-stage-grid">
                <div v-for="stage in dashboardOverview.funnel.stages" :key="stage.key" class="funnel-stage">
                  <span>{{ stage.label }}</span>
                  <strong>{{ stage.value }}</strong>
                  <small>{{ stage.percent }}</small>
                </div>
              </div>
              <div class="highlight-metrics">
                <div v-for="item in dashboardOverview.funnel.highlights" :key="item.key" class="highlight-metric">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                </div>
              </div>
            </ElCard>

            <ElCard shadow="never" class="surface-card feature-card feature-card--growth">
              <div class="section-card__header">
                <div>
                  <h4>平台用户 / 会员 / 租户增长</h4>
                  <span>近30天</span>
                </div>
              </div>
              <div class="highlight-metrics highlight-metrics--three">
                <div v-for="item in dashboardOverview.growth.cards" :key="item.key" class="highlight-metric">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                </div>
              </div>
              <AdminDataState
                v-if="dashboardOverview.growth.chart.series.length === 0"
                state="empty"
                title="增长趋势暂不可用"
                description="用户增长、付费租户与历史活跃数据源尚未接入。"
                :retryable="false"
                compact
              />
              <div v-else class="chart-legend chart-legend--panel">
                <span v-for="series in dashboardOverview.growth.chart.series" :key="series.key">
                  <i :style="{ background: series.color }"></i>{{ series.label }}
                </span>
              </div>
              <div v-if="dashboardOverview.growth.chart.series.length" class="panel-chart-shell panel-chart-shell--growth">
                <ArtLineChart
                  :data="lineChartData(dashboardOverview.growth.chart, 'growth')"
                  :xAxisData="dashboardOverview.growth.chart.labels"
                  :colors="chartColors(dashboardOverview.growth.chart)"
                  :yAxisMin="lineChartBounds(dashboardOverview.growth.chart, 'growth').min"
                  :yAxisMax="lineChartBounds(dashboardOverview.growth.chart, 'growth').max"
                  :showYAxisLabel="false"
                  :splitNumber="4"
                  :gridPadding="{ top: 12, right: 6, bottom: 0, left: 4 }"
                  height="152px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :lineWidth="3"
                  symbol="circle"
                  :symbolSize="5"
                  :animationDelay="90"
                />
              </div>
            </ElCard>
          </div>
        </section>

        <section class="overview-section">
          <div class="overview-section__heading">
            <div>
              <h3>实时运营监控</h3>
              <p>按监控、健康、工作流三个视角同步观察异常与效率。</p>
            </div>
          </div>
          <div class="three-col-grid">
            <ElCard
              v-for="panel in dashboardOverview.monitoring.cards"
              :key="panel.key"
              shadow="never"
              :class="['surface-card', 'panel-card', `panel-card--${panel.key}`]"
            >
              <div class="section-card__header">
                <div>
                  <h4>{{ panel.title }}</h4>
                  <span>{{ panel.subtitle }}</span>
                </div>
              </div>

              <div v-if="panel.emptyState" class="panel-empty-state">
                <span class="panel-empty-state__icon" aria-hidden="true"><span class="panel-empty-state__shield"></span></span>
                <strong>{{ panel.emptyState.title }}</strong>
                <p>{{ panel.emptyState.description }}</p>
              </div>

              <div v-if="panel.metrics?.length" :class="['mini-metric-grid', { 'mini-metric-grid--three': panel.metrics.length >= 6 }]">
                <div v-for="item in panel.metrics" :key="item.key" class="mini-metric mini-metric--panel">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong class="mini-metric__value">{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                </div>
              </div>

              <div v-if="panel.gauge" class="panel-gauge-inline">
                <div class="mini-gauge" :style="gaugeStyle(panel.gauge.value)">
                  <div class="mini-gauge__inner">
                    <strong>{{ panel.gauge.value }}%</strong>
                    <span>{{ panel.gauge.label }}</span>
                  </div>
                </div>
                <div class="panel-gauge-inline__detail">{{ panel.gauge.detail }}</div>
              </div>

              <div v-if="panel.chart?.series?.length" class="chart-legend chart-legend--panel">
                <span v-for="series in panel.chart.series" :key="series.key">
                  <i :style="{ background: series.color }"></i>{{ series.label }}
                </span>
              </div>

              <div v-if="isBarChart(panel.chart)" class="panel-chart-shell panel-chart-shell--bar">
                <ArtBarChart
                  :data="barChartData(panel.chart)"
                  :xAxisData="panel.chart.labels"
                  :colors="chartColors(panel.chart)"
                  height="132px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :borderRadius="999"
                  barWidth="10"
                />
              </div>

              <div v-else-if="panel.chart" class="panel-chart-shell">
                <ArtLineChart
                  :data="lineChartData(panel.chart, 'panel')"
                  :xAxisData="panel.chart.labels"
                  :colors="chartColors(panel.chart)"
                  :yAxisMin="lineChartBounds(panel.chart, 'panel').min"
                  :yAxisMax="lineChartBounds(panel.chart, 'panel').max"
                  :showYAxisLabel="false"
                  :splitNumber="4"
                  :gridPadding="{ top: 10, right: 4, bottom: 0, left: 4 }"
                  height="132px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :lineWidth="2.6"
                  symbol="circle"
                  :symbolSize="4"
                  :animationDelay="90"
                />
              </div>

              <div v-if="panel.table?.length" class="status-table">
                <div v-for="row in panel.table" :key="`${panel.key}-${row.label}`" class="status-row">
                  <span :class="['status-dot', toneClass(row.tone)]"></span>
                  <span class="status-row__label">{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                  <span v-if="row.extra" class="status-row__extra">{{ row.extra }}</span>
                </div>
              </div>

              <p v-if="panel.footer" class="panel-footer">{{ panel.footer }}</p>
            </ElCard>
          </div>
        </section>

        <section class="overview-section">
          <div class="overview-section__heading">
            <div>
              <h3>消息与客服效率</h3>
              <p>跟踪会话处理、库存承载和优先告警。</p>
            </div>
          </div>
          <div class="three-col-grid">
            <ElCard
              v-for="panel in dashboardOverview.servicePanels"
              :key="panel.key"
              shadow="never"
              :class="['surface-card', 'panel-card', `panel-card--${panel.key}`]"
            >
              <div class="section-card__header">
                <div>
                  <h4>{{ panel.title }}</h4>
                  <span>{{ panel.subtitle }}</span>
                </div>
              </div>

              <div v-if="panel.emptyState" class="panel-empty-state">
                <span class="panel-empty-state__icon" aria-hidden="true"><span class="panel-empty-state__shield"></span></span>
                <strong>{{ panel.emptyState.title }}</strong>
                <p>{{ panel.emptyState.description }}</p>
              </div>

              <div v-if="panel.metrics?.length" :class="['mini-metric-grid', { 'mini-metric-grid--three': panel.metrics.length >= 6 }]">
                <div v-for="item in panel.metrics" :key="item.key" class="mini-metric mini-metric--panel">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong class="mini-metric__value">{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                </div>
              </div>

              <div v-if="panel.table?.length" class="table-stack">
                <div v-for="row in panel.table" :key="`${panel.key}-${row.label}`" class="table-stack__row">
                  <span class="table-stack__label">{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                  <span :class="['table-stack__extra', toneClass(row.tone)]">{{ row.extra }}</span>
                </div>
              </div>

              <div v-if="panel.pending?.length" class="pending-stack">
                <div v-for="item in panel.pending" :key="`${item.title}-${item.time}`" class="pending-stack__item">
                  <div class="pending-stack__content">
                    <span :class="['pending-pill', toneClass(item.severity)]">{{ item.type }}</span>
                    <b>{{ item.title }}</b>
                  </div>
                  <span class="pending-stack__time">{{ item.time }}</span>
                </div>
              </div>

              <p v-if="panel.footer" class="panel-footer panel-footer--link">{{ panel.footer }}</p>
            </ElCard>
          </div>
        </section>

        <section class="overview-section">
          <div class="overview-section__heading">
            <div>
              <h3>通知投递统计</h3>
              <p>补充错误、同步和投递质量的运营面板。</p>
            </div>
          </div>
          <div class="three-col-grid">
            <ElCard
              v-for="panel in dashboardOverview.qualityPanels"
              :key="panel.key"
              shadow="never"
              :class="['surface-card', 'panel-card', `panel-card--${panel.key}`]"
            >
              <div class="section-card__header">
                <div>
                  <h4>{{ panel.title }}</h4>
                  <span>{{ panel.subtitle }}</span>
                </div>
              </div>

              <div
                v-if="panel.metrics?.length"
                :class="[
                  'mini-metric-grid',
                  'mini-metric-grid--tight',
                  { 'mini-metric-grid--quad': panel.metrics.length === 4 }
                ]"
              >
                <div v-for="item in panel.metrics" :key="item.key" class="mini-metric mini-metric--panel">
                  <span class="mini-metric__label">{{ item.label }}</span>
                  <strong class="mini-metric__value">{{ item.value }}</strong>
                  <span :class="['mini-metric__delta', toneClass(item.tone)]">{{ item.delta }}</span>
                </div>
              </div>

              <div v-if="panel.chart?.series?.length" class="chart-legend chart-legend--panel">
                <span v-for="series in panel.chart.series" :key="series.key">
                  <i :style="{ background: series.color }"></i>{{ series.label }}
                </span>
              </div>

              <div v-if="panel.emptyState" class="panel-empty-state">
                <span class="panel-empty-state__icon" aria-hidden="true">
                  <span class="panel-empty-state__shield"></span>
                </span>
                <strong>{{ panel.emptyState.title }}</strong>
                <p>{{ panel.emptyState.description }}</p>
              </div>

              <div v-if="isBarChart(panel.chart)" class="panel-chart-shell panel-chart-shell--bar">
                <ArtBarChart
                  :data="barChartData(panel.chart)"
                  :xAxisData="panel.chart.labels"
                  :colors="chartColors(panel.chart)"
                  height="132px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :borderRadius="999"
                  barWidth="10"
                />
              </div>

              <div v-else-if="panel.chart" class="panel-chart-shell">
                <ArtLineChart
                  :data="lineChartData(panel.chart, 'panel')"
                  :xAxisData="panel.chart.labels"
                  :colors="chartColors(panel.chart)"
                  :yAxisMin="lineChartBounds(panel.chart, 'panel').min"
                  :yAxisMax="lineChartBounds(panel.chart, 'panel').max"
                  :showYAxisLabel="false"
                  :splitNumber="4"
                  :gridPadding="{ top: 10, right: 4, bottom: 0, left: 4 }"
                  height="132px"
                  :showAxisLine="false"
                  :showLegend="false"
                  :lineWidth="2.6"
                  symbol="circle"
                  :symbolSize="4"
                  :animationDelay="90"
                />
              </div>

              <p v-if="panel.footer" class="panel-footer">{{ panel.footer }}</p>
            </ElCard>
          </div>
        </section>

        <section class="overview-section overview-section--bottom">
          <div class="overview-section__heading">
            <div>
              <h3>最近后台操作</h3>
              <p>保留系统健康、热销商品与后台时间线，作为长图页底部收束。</p>
            </div>
          </div>
          <div class="three-col-grid">
            <ElCard
              v-for="panel in dashboardOverview.bottom.cards"
              :key="panel.key"
              shadow="never"
              :class="['surface-card', 'panel-card', `panel-card--${panel.key}`]"
            >
              <div class="section-card__header">
                <div>
                  <h4>{{ panel.title }}</h4>
                  <span>{{ panel.subtitle }}</span>
                </div>
              </div>

              <div v-if="panel.emptyState" class="panel-empty-state">
                <span class="panel-empty-state__icon" aria-hidden="true"><span class="panel-empty-state__shield"></span></span>
                <strong>{{ panel.emptyState.title }}</strong>
                <p>{{ panel.emptyState.description }}</p>
              </div>

              <div v-else-if="panel.key === 'hot-goods'" class="hot-goods-list">
                <div v-for="(row, index) in panel.table" :key="`${panel.key}-${row.label}`" class="hot-goods-row">
                  <span class="hot-goods-row__rank">{{ index + 1 }}</span>
                  <span class="hot-goods-row__label">{{ row.label }}</span>
                  <strong class="hot-goods-row__value">{{ row.value }}</strong>
                </div>
              </div>

              <div v-else-if="panel.key === 'system-health'" class="system-health-stack">
                <div class="table-stack">
                  <div v-for="row in bottomServiceRows(panel)" :key="`${panel.key}-${row.label}`" class="table-stack__row">
                    <span class="table-stack__label">{{ row.label }}</span>
                    <span :class="['service-status-pill', toneClass(row.tone)]">{{ row.value }}</span>
                    <span class="table-stack__extra">{{ row.extra }}</span>
                  </div>
                </div>
                <div class="usage-meter-list">
                  <div v-for="row in bottomUsageRows(panel)" :key="`${panel.key}-${row.label}`" class="usage-meter">
                    <div class="usage-meter__top">
                      <span>{{ row.label }}</span>
                      <strong>{{ row.value }}</strong>
                    </div>
                    <div class="usage-meter__track">
                      <span class="usage-meter__fill" :style="{ width: `${usagePercent(row.value)}%` }"></span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else class="event-timeline">
                <div v-for="row in panel.table" :key="`${panel.key}-${row.label}`" class="table-stack__row">
                  <span :class="['status-dot', toneClass(row.tone)]"></span>
                  <div class="event-timeline__content">
                    <span class="table-stack__label">{{ row.label }}</span>
                    <span :class="['table-stack__extra', toneClass(row.tone)]">{{ row.extra }}</span>
                  </div>
                  <strong>{{ row.value }}</strong>
                </div>
              </div>

              <p v-if="panel.footer" class="panel-footer panel-footer--link">{{ panel.footer }}</p>
            </ElCard>
          </div>
        </section>

        <footer class="overview-page-footer">© 2026 闲鱼助手平台后台 · v1.0.0</footer>
        </div>
      </div>
    </template>

    <template v-else>
      <ElCard shadow="never" class="filter-card">
        <div class="page-title-row">
          <div>
            <h2>{{ meta.title || routeTitle }}</h2>
            <p>{{ meta.description || '平台后台运营管理模块' }}</p>
          </div>
          <div class="toolbar-actions">
            <ElTag v-if="readonlyModule" type="info" effect="plain" round>只读视图</ElTag>
            <ElButton v-if="moduleKey === 'hot-goods' && canRefreshStats" type="primary" :loading="refreshing" @click="refreshHotGoods">
              <i class="ri:refresh-line"></i> 刷新统计数据
            </ElButton>
            <ElButton @click="reload">刷新</ElButton>
            <ElButton v-if="canExport" @click="exportCsv">导出</ElButton>
            <ElButton v-if="canAdd" type="primary" @click="openCreate">新增</ElButton>
          </div>
        </div>

        <div class="module-stats">
          <ElCard v-for="item in moduleStatCards" :key="item.label" shadow="never" class="mini-stat">
            <span>{{ item.label }}</span>
            <b>{{ item.value }}</b>
          </ElCard>
        </div>

        <ElForm :inline="true" :model="query" class="search-form">
          <ElFormItem label="关键词">
            <ElInput v-model="query.keyword" placeholder="搜索名称、编号、用户、备注" clearable @keyup.enter="reload" />
          </ElFormItem>
          <ElFormItem label="状态">
            <ElSelect v-model="query.status" clearable placeholder="全部" style="width:150px">
              <ElOption label="正常/启用/成功" value="正常" />
              <ElOption label="待处理/待支付" value="待处理" />
              <ElOption label="异常/失败/禁用" value="异常" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem>
            <ElButton type="primary" @click="reload">查询</ElButton>
            <ElButton @click="reset">重置</ElButton>
          </ElFormItem>
        </ElForm>

        <div v-if="canEdit || canDelete" class="quick-actions">
          <ElButton v-if="canEdit" :disabled="!selectedIds.length" @click="batchStatus('正常')">批量设为正常</ElButton>
          <ElButton v-if="canEdit" :disabled="!selectedIds.length" type="warning" @click="batchStatus('待处理')">批量待处理</ElButton>
          <ElButton v-if="canDelete" :disabled="!selectedIds.length" type="danger" @click="batchDelete">批量删除</ElButton>
          <ElButton v-for="action in moduleActions" :key="action.text" :type="action.type" plain @click="handleModuleAction(action)">{{ action.text }}</ElButton>
        </div>
      </ElCard>

      <ElCard shadow="never" class="table-card">
        <ElTable v-loading="loading" :data="records" border stripe style="width:100%" @selection-change="onSelectionChange">
          <template #empty><div class="empty-state">暂无数据</div></template>
          <ElTableColumn v-if="canEdit || canDelete" type="selection" width="48" fixed />
          <ElTableColumn v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :min-width="col.width || 120" show-overflow-tooltip>
            <template #default="scope">
              <ElTag v-if="col.type === 'tag'" :type="tagType(scope.row[col.prop])">{{ scope.row[col.prop] }}</ElTag>
              <ElTag v-else-if="col.type === 'bool'" :type="normalizeBooleanValue(scope.row[col.prop]) ? 'success' : 'danger'">
                {{ normalizeBooleanValue(scope.row[col.prop]) ? '启用' : '停用' }}
              </ElTag>
              <ElImage v-else-if="col.type === 'image' && scope.row[col.prop]" :src="scope.row[col.prop]" :preview-src-list="[scope.row[col.prop]]" fit="cover" style="width:60px;height:60px;border-radius:6px;cursor:pointer;" />
              <a v-else-if="col.type === 'image'" class="img-placeholder">无图</a>
              <span v-else>{{ formatFieldValue(col, scope.row[col.prop]) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn fixed="right" label="操作" :width="readonlyModule ? 100 : 250">
            <template #default="scope">
              <ElButton link type="primary" @click="openDetail(scope.row)">详情</ElButton>
              <template v-if="canEdit || canDelete">
                <ElButton v-if="canEdit" link type="primary" @click="openEdit(scope.row)">编辑</ElButton>
                <ElButton v-if="canEdit" link type="warning" @click="changeStatus(scope.row)">状态</ElButton>
                <ElPopconfirm v-if="canDelete" title="确认删除这条记录？" @confirm="remove(scope.row)">
                  <template #reference><ElButton link type="danger">删除</ElButton></template>
                </ElPopconfirm>
              </template>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="selected-tip">已选 {{ selectedIds.length }} 条</span>
          <ElPagination v-model:current-page="query.current" v-model:page-size="query.size" layout="total, sizes, prev, pager, next, jumper" :total="total" @change="reload" />
        </div>
      </ElCard>
    </template>

    <ElDrawer v-model="drawer.visible" :title="drawer.title" size="46%">
      <ElDescriptions v-if="drawer.mode === 'detail'" :column="2" border>
        <ElDescriptionsItem v-for="col in detailColumns" :key="col.prop" :label="col.label">{{ formatFieldValue(col, drawer.form[col.prop]) }}</ElDescriptionsItem>
      </ElDescriptions>
      <ElForm v-else label-width="120px" :model="drawer.form" class="drawer-form">
        <ElFormItem v-for="col in editableColumns" :key="col.prop" :label="col.label">
          <ElSelect v-if="isStatusField(col.prop)" v-model="drawer.form[col.prop]" style="width: 100%">
            <ElOption label="正常" value="正常" />
            <ElOption label="禁用" value="禁用" />
          </ElSelect>
          <ElSwitch v-else-if="isBooleanField(col)" v-model="drawer.form[col.prop]" inline-prompt active-text="启用" inactive-text="停用" />
          <ElInput
            v-else-if="isTextareaField(col.prop)"
            v-model="drawer.form[col.prop]"
            type="textarea"
            :rows="col.prop === 'promptTemplate' ? 14 : 5"
            :placeholder="`请输入${col.label}`"
          />
          <ElInput v-else v-model="drawer.form[col.prop]" :placeholder="`请输入${col.label}`" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawer.visible = false">取消</ElButton>
        <ElButton v-if="drawer.mode === 'create' ? canAdd : drawer.mode === 'edit' ? canEdit : false" type="primary" @click="save">保存</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
  import {
    batchDeleteModuleRecords,
    batchUpdateModuleStatus,
    deleteModuleRecord,
    getAdminSummary,
    getAdminTrend,
    getDashboardInit,
    getModuleDetail,
    getModuleExportUrl,
    getModuleMeta,
    getModulePage,
    getModuleStats,
    getRealtimeStats,
    getSystemHealth,
    type PendingTask,
    type ServiceHealthItem,
    getRecentEvents,
    refreshHotGoodsStat,
    saveModuleRecord,
    updateModuleStatus
  } from '@/api/admin'
  import { getAiCostStats, getAiMonitor, getAiTokenStats, getAutoReplyMonitor, getWorkflowMonitor } from '@/api/monitor'
  import { useUserStore } from '@/store/modules/user'
  import { getAdminButtonCapabilities } from '@/utils/admin-permissions'
  import type { BarDataItem, LineDataItem } from '@/types/component/chart'
  import { buildDashboardOverviewModel, type DashboardChartModel, type DashboardDataState, type DashboardTableRow, type DashboardTone } from './dashboard-overview'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminModulePage' })

  const route = useRoute()
  const router = useRouter()
  const userStore = useUserStore()
  const moduleKey = computed(() => String((route.meta as any).moduleKey || 'dashboard'))
  const routeTitle = computed(() => String(route.meta.title || '后台管理'))
  const loading = ref(false)
  const refreshing = ref(false)
  const meta = ref<any>({ title: '', columns: [] })
  const records = ref<any[]>([])
  const total = ref(0)
  const summary = ref<any>({})
  const trend = ref<any>({})
  const recentEvents = ref<any[]>([])
  const pendingTasks = ref<PendingTask[]>([])
  const realtimeStats = ref<Partial<{
    onlineAccounts: number | string
    todayPublished: number | string
    todaySalesAmount: number | string
    todayAiCalls: number | string
    todayAiFailures: number | string
    runningWorkflows: number | string
  }>>({})
  const topHotGoods = ref<Array<{ id: number; title: string; price: number | string; imageUrl: string; sales: number; stat_date: string; accountName: string }>>([])
  const riskDistribution = ref<Array<{ risk_level: number; count: number }>>([])
  const systemHealth = ref<{ coreApi: ServiceHealthItem; automationService: ServiceHealthItem; crawlerService: ServiceHealthItem } | null>(null)
  const trendRange = ref<7 | 30 | 90>(7)
  const moduleStats = ref<any>({})
  const query = reactive({ current: 1, size: 10, keyword: '', status: '' })
  const selectedIds = ref<Array<number | string>>([])
  const drawer = reactive({ visible: false, title: '', mode: 'detail', form: {} as Record<string, any> })
  const overviewMonitor = reactive({
    ai: {} as Record<string, any>,
    autoReply: {} as Record<string, any>,
    workflow: {} as Record<string, any>,
    token: {} as Record<string, any>,
    cost: {} as Record<string, any>
  })
  const dashboardState = reactive<DashboardDataState>({
    status: 'loading',
    message: '正在加载仪表盘数据',
    failedSources: []
  })

  const columns = computed(() => meta.value.columns || [])
  const isImagePromptModule = computed(() => moduleKey.value === 'model-config-image-prompts')
  const detailColumns = computed(() => columns.value)
  const editableColumns = computed(() => {
    const filtered = columns.value.filter((c: any) => !['id', 'createdTime', 'updatedTime', 'lastLoginTime', 'lastActiveTime'].includes(c.prop))
    return isImagePromptModule.value ? filtered : filtered.slice(0, 10)
  })
  const dashboardOverview = computed(() =>
    buildDashboardOverviewModel({
      summary: summary.value,
      trend: trend.value,
      realtimeStats: realtimeStats.value,
      pendingTasks: pendingTasks.value,
      topHotGoods: topHotGoods.value,
      riskDistribution: riskDistribution.value,
      systemHealth: systemHealth.value,
      recentEvents: recentEvents.value,
      aiMonitor: overviewMonitor.ai,
      autoReplyMonitor: overviewMonitor.autoReply,
      workflowMonitor: overviewMonitor.workflow,
      tokenStats: overviewMonitor.token,
      costStats: overviewMonitor.cost,
      dataState: {
        status: dashboardState.status,
        message: dashboardState.message,
        failedSources: [...dashboardState.failedSources]
      }
    })
  )
  const dashboardContentVisible = computed(() => ['ready', 'degraded'].includes(dashboardState.status))
  const heroPrimaryChips = computed(() => dashboardOverview.value.hero.chips.slice(0, 3))
  const heroSecondaryChip = computed(() => dashboardOverview.value.hero.chips[3] || null)
  const moduleStatCards = computed(() => [
    { label: '总数', value: moduleStats.value.total || 0 },
    { label: '正常', value: moduleStats.value.normal || 0 },
    { label: '待处理', value: moduleStats.value.warning || 0 },
    { label: '异常', value: moduleStats.value.danger || 0 },
    { label: '今日新增', value: moduleStats.value.today || 0 }
  ])
  // 7 个真实业务模块由 AdminRealDataModuleService 提供只读数据视图，不支持新增/编辑/删除
  const READONLY_MODULE_KEYS = ['goods', 'orders', 'messages', 'delivery', 'auto-reply', 'kami', 'hot-goods']
  const inherentlyReadonlyModule = computed(() => READONLY_MODULE_KEYS.includes(moduleKey.value))
  const buttonCapabilities = computed(() => getAdminButtonCapabilities(userStore.info?.buttons))
  const canAdd = computed(() => !inherentlyReadonlyModule.value && buttonCapabilities.value.canAdd)
  const canEdit = computed(() => !inherentlyReadonlyModule.value && buttonCapabilities.value.canEdit)
  const canDelete = computed(() => !inherentlyReadonlyModule.value && buttonCapabilities.value.canDelete)
  const canExport = computed(() => buttonCapabilities.value.canExport)
  const canRefreshStats = computed(() => buttonCapabilities.value.canEdit)
  const isSuperAdmin = computed(() => userStore.info?.roles?.includes('R_SUPER') === true)
  const readonlyModule = computed(() =>
    inherentlyReadonlyModule.value || (!canAdd.value && !canEdit.value && !canDelete.value)
  )
  const moduleActions = computed(() => canEdit.value ? (actionMap[moduleKey.value] || []) : [])
  let moduleLoadVersion = 0

function beginModuleLoad() {
  moduleLoadVersion += 1
  return moduleLoadVersion
}

function resolveModuleLoadVersion(loadVersion?: number | Event) {
  return typeof loadVersion === 'number' && Number.isFinite(loadVersion)
    ? loadVersion
    : beginModuleLoad()
}

function isStaleModuleLoad(loadVersion: number) {
  return loadVersion !== moduleLoadVersion
}

function isCancelledRequest(error: unknown) {
  return !!error && typeof error === 'object' && (error as { cancelled?: boolean }).cancelled === true
}

function shouldIgnoreModuleLoadError(error: unknown, loadVersion: number) {
  return isCancelledRequest(error) || isStaleModuleLoad(loadVersion)
}

function denyUnauthorizedAction() {
  ElMessage.error('当前账号无此操作权限')
}

function isTextareaField(prop: string) {
  return isImagePromptModule.value && ['matchKeywords', 'promptTemplate'].includes(prop)
}

function isBooleanField(col: any) {
  return col?.type === 'bool'
}

function isStatusField(prop: string) {
  return prop === 'status'
}

function drawerDefaults() {
  return isImagePromptModule.value ? { status: '正常', enabled: true, sortOrder: 100 } : { status: '正常' }
}

function normalizeBooleanValue(value: any) {
  if (value === true || value === false) return value
  const text = String(value ?? '').trim().toLowerCase()
  return ['1', 'true', '正常', '启用', 'yes', 'on'].includes(text)
}

function normalizeDrawerForm(form: Record<string, any>) {
  if (!isImagePromptModule.value) return { ...form }
  return {
    ...drawerDefaults(),
    ...form,
    enabled: normalizeBooleanValue(form.enabled ?? true),
    sortOrder: form.sortOrder ?? 100,
  }
}

function formatFieldValue(col: any, value: any) {
  if (col?.type === 'bool') {
    return normalizeBooleanValue(value) ? '启用' : '停用'
  }
  if (value == null || value === '') return '-'
  // 识别 ISO 日期格式并格式化为 YYYY-MM-DD HH:mm:ss
  const text = String(value)
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(text)) {
    // 带时区的 ISO 格式，转为本地时间
    if (text.includes('+') || text.includes('Z')) {
      const d = new Date(text)
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
      }
    }
    // 无时区的 ISO 格式，直接替换 T
    return text.replace('T', ' ').replace(/\.\d+.*$/, '').slice(0, 19)
  }
  return value ?? '-'
}

  type ActionButtonType = '' | 'primary' | 'success' | 'warning' | 'info' | 'default' | 'text' | 'danger'

  const actionMap: Record<string, Array<{ text: string; type?: ActionButtonType; status?: string }>> = {
    users: [{ text: '禁用用户', type: 'danger', status: '禁用' }, { text: '恢复用户', type: 'success', status: '正常' }],
    subscriptions: [{ text: '标记续费', type: 'success', status: '正常' }, { text: '标记过期', type: 'warning', status: '过期' }],
    'xianyu-accounts': [{ text: '标记风险', type: 'warning', status: '异常' }, { text: '解除风险', type: 'success', status: '正常' }],
    delivery: [{ text: '重试失败', type: 'warning', status: '待处理' }],
    'risk-events': [{ text: '标记处理中', type: 'warning', status: '待处理' }, { text: '标记已处理', type: 'success', status: '正常' }],
    alerts: [{ text: '标记已处理', type: 'success', status: '正常' }],
    'task-queue': [{ text: '暂停任务', type: 'warning', status: '待处理' }, { text: '恢复任务', type: 'success', status: '正常' }]
  }

  const DASHBOARD_REQUEST_OPTIONS = { showErrorMessage: false } as const

  watch(() => route.fullPath, () => { void init() }, { immediate: true })

  async function init() {
    const loadVersion = beginModuleLoad()
    selectedIds.value = []
    if (moduleKey.value === 'dashboard') return loadDashboard(loadVersion)
    query.current = 1
    await Promise.all([loadMeta(loadVersion), reload(loadVersion)])
    // 注意：reload() 内部已调用 loadStats()，此处不再重复调用
  }

  async function loadDashboard(loadVersion?: number | Event) {
    const activeLoadVersion = resolveModuleLoadVersion(loadVersion)
    loading.value = true
    setDashboardState('loading', '正在加载核心业务与监控数据', [])
    try {
      const [data, insights] = await Promise.all([
        getDashboardInit(DASHBOARD_REQUEST_OPTIONS),
        fetchDashboardInsights(trendRange.value)
      ])
      if (isStaleModuleLoad(activeLoadVersion)) return
      summary.value = data?.summary || {}
      trend.value = data?.trend || {}
      recentEvents.value = data?.recentEvents || []
      pendingTasks.value = data?.pendingTasks || []
      realtimeStats.value = data?.realtimeStats || realtimeStats.value
      topHotGoods.value = data?.topHotGoods || []
      riskDistribution.value = data?.riskDistribution || []
      systemHealth.value = data?.systemHealth || null
      applyDashboardInsights(insights)
      if (!hasDashboardCoreData(data) && !hasDashboardInsightData(insights)) {
        setDashboardState('empty', '接口已成功响应，但当前没有业务或监控记录。', insights.failedSources)
      } else if (insights.failedSources.length) {
        setDashboardState(
          'degraded',
          `核心业务数据已加载，但以下监控数据暂不可用：${insights.failedSources.join('、')}。不可用指标不会显示为 0 或正常。`,
          insights.failedSources
        )
      } else {
        setDashboardState('ready', '仪表盘数据已加载', [])
      }
    } catch (err: any) {
      if (shouldIgnoreModuleLoadError(err, activeLoadVersion)) return
      const fallback = await Promise.allSettled([
        getAdminSummary(DASHBOARD_REQUEST_OPTIONS),
        getRecentEvents(DASHBOARD_REQUEST_OPTIONS)
      ])
      if (isStaleModuleLoad(activeLoadVersion)) return
      resetDashboardData()
      const summaryResult = fallback[0]
      const eventsResult = fallback[1]
      if (summaryResult.status === 'fulfilled') summary.value = summaryResult.value || {}
      if (eventsResult.status === 'fulfilled') recentEvents.value = eventsResult.value || []
      const fallbackHasData = Object.keys(summary.value || {}).length > 0 || recentEvents.value.length > 0
      if (fallbackHasData) {
        const failedSources = [
          '仪表盘聚合接口',
          ...(summaryResult.status === 'rejected' ? ['经营汇总'] : []),
          ...(eventsResult.status === 'rejected' ? ['操作日志'] : []),
          '趋势与监控明细'
        ]
        setDashboardState(
          'degraded',
          `仅加载到部分降级数据；${failedSources.join('、')}暂不可用。页面不会用默认值补齐缺失指标。`,
          failedSources
        )
      } else {
        setDashboardState(
          'unavailable',
          err?.message || '核心与降级数据源均读取失败，请检查网络或服务状态后重试。',
          ['仪表盘聚合接口', '经营汇总', '操作日志', '监控明细']
        )
      }
    } finally {
      if (!isStaleModuleLoad(activeLoadVersion)) {
        loading.value = false
      }
    }
  }

  /**
   * 切换趋势图时间范围（7/30/90 天），仅刷新趋势数据
   */
  async function loadTrendByRange(range: 7 | 30 | 90) {
    trendRange.value = range
    const results = await Promise.allSettled([
      getAdminTrend(range, DASHBOARD_REQUEST_OPTIONS),
      fetchDashboardInsights(range)
    ])
    const failedSources: string[] = []
    const trendResult = results[0]
    const insightResult = results[1]
    if (trendResult.status === 'fulfilled') {
      trend.value = trendResult.value || {}
    } else {
      failedSources.push('经营趋势')
    }
    if (insightResult.status === 'fulfilled') {
      applyDashboardInsights(insightResult.value)
      failedSources.push(...insightResult.value.failedSources)
    } else {
      failedSources.push('监控趋势')
    }
    if (failedSources.length) {
      setDashboardState(
        'degraded',
        `时间范围已切换，但以下数据刷新失败：${failedSources.join('、')}。当前仅展示成功读取的数据。`,
        Array.from(new Set([...dashboardState.failedSources, ...failedSources]))
      )
      ElMessage.warning('部分趋势数据刷新失败，已标记为降级状态')
    }
  }

  /**
   * 单独刷新实时监控数据（用于定时刷新或手动刷新按钮）
   */
  async function refreshRealtimeStats() {
    const [realtimeResult, healthResult, workflowResult] = await Promise.allSettled([
      getRealtimeStats(DASHBOARD_REQUEST_OPTIONS),
      getSystemHealth(DASHBOARD_REQUEST_OPTIONS),
      getWorkflowMonitor({ days: trendRange.value }, DASHBOARD_REQUEST_OPTIONS)
    ] as const)
    const sources = [
      { label: '实时运营', result: realtimeResult },
      { label: '系统健康', result: healthResult },
      { label: '工作流监控', result: workflowResult }
    ] as const
    const failedSources: string[] = []
    sources.forEach(source => {
      if (source.result.status === 'rejected') failedSources.push(source.label)
    })
    if (realtimeResult.status === 'fulfilled') realtimeStats.value = realtimeResult.value || {}
    if (healthResult.status === 'fulfilled') systemHealth.value = healthResult.value || null
    if (workflowResult.status === 'fulfilled') overviewMonitor.workflow = workflowResult.value || {}
    if (failedSources.length) {
      setDashboardState(
        'degraded',
        `实时刷新未全部成功：${failedSources.join('、')}暂不可用。`,
        Array.from(new Set([...dashboardState.failedSources, ...failedSources]))
      )
      ElMessage.warning('部分实时状态刷新失败')
    } else if (dashboardState.status === 'ready') {
      ElMessage.success('实时状态已刷新')
    }
  }

  async function fetchDashboardInsights(days: 7 | 30 | 90) {
    const sources = [
      { key: 'ai', label: 'AI 调用监控', request: getAiMonitor({ days }, DASHBOARD_REQUEST_OPTIONS) },
      { key: 'autoReply', label: '自动回复监控', request: getAutoReplyMonitor({ days }, DASHBOARD_REQUEST_OPTIONS) },
      { key: 'workflow', label: '工作流监控', request: getWorkflowMonitor({ days }, DASHBOARD_REQUEST_OPTIONS) },
      { key: 'token', label: 'Token 统计', request: getAiTokenStats({ days }, DASHBOARD_REQUEST_OPTIONS) },
      { key: 'cost', label: 'AI 成本趋势', request: getAiCostStats({ days }, DASHBOARD_REQUEST_OPTIONS) }
    ] as const
    const settled = await Promise.allSettled(sources.map(source => source.request))
    const result: Record<string, Record<string, any>> = {}
    const failedSources: string[] = []

    settled.forEach((item, index) => {
      const source = sources[index]
      if (item.status === 'fulfilled') {
        result[source.key] = item.value || {}
      } else {
        result[source.key] = {}
        failedSources.push(source.label)
      }
    })

    return {
      ai: result.ai || {},
      autoReply: result.autoReply || {},
      workflow: result.workflow || {},
      token: result.token || {},
      cost: result.cost || {},
      failedSources
    }
  }

  function applyDashboardInsights(insights: {
    ai: Record<string, any>
    autoReply: Record<string, any>
    workflow: Record<string, any>
    token: Record<string, any>
    cost: Record<string, any>
    failedSources: string[]
  }) {
    overviewMonitor.ai = insights.ai || {}
    overviewMonitor.autoReply = insights.autoReply || {}
    overviewMonitor.workflow = insights.workflow || {}
    overviewMonitor.token = insights.token || {}
    overviewMonitor.cost = insights.cost || {}
  }

  function resetDashboardInsights() {
    overviewMonitor.ai = {}
    overviewMonitor.autoReply = {}
    overviewMonitor.workflow = {}
    overviewMonitor.token = {}
    overviewMonitor.cost = {}
  }

  function resetDashboardData() {
    summary.value = {}
    trend.value = {}
    recentEvents.value = []
    pendingTasks.value = []
    realtimeStats.value = {}
    topHotGoods.value = []
    riskDistribution.value = []
    systemHealth.value = null
    resetDashboardInsights()
  }

  function hasDashboardCoreData(data: any) {
    return Boolean(
      data && (
        data.summary?.cards?.length ||
        data.trend?.dates?.length ||
        data.pendingTasks?.length ||
        data.topHotGoods?.length ||
        data.riskDistribution?.length ||
        data.recentEvents?.length ||
        data.systemHealth ||
        Object.keys(data.realtimeStats || {}).length
      )
    )
  }

  function hasDashboardInsightData(insights: {
    ai: Record<string, any>
    autoReply: Record<string, any>
    workflow: Record<string, any>
    token: Record<string, any>
    cost: Record<string, any>
  }) {
    return [insights.ai, insights.autoReply, insights.workflow, insights.token, insights.cost]
      .some(item => item && Object.keys(item).length > 0)
  }

  function setDashboardState(status: DashboardDataState['status'], message: string, failedSources: string[]) {
    dashboardState.status = status
    dashboardState.message = message
    dashboardState.failedSources = failedSources
  }

  function dashboardSourceFailed(sourceName: string) {
    return dashboardState.failedSources.some(source => source.includes(sourceName))
  }

  async function loadMeta(loadVersion = moduleLoadVersion) {
    const nextMeta = await getModuleMeta(moduleKey.value)
    if (isStaleModuleLoad(loadVersion)) return
    meta.value = nextMeta
  }

  async function loadStats(loadVersion = moduleLoadVersion) {
    const nextStats = await getModuleStats(moduleKey.value)
    if (isStaleModuleLoad(loadVersion)) return
    moduleStats.value = nextStats
  }

  async function reload(loadVersion?: number | Event) {
    const activeLoadVersion = resolveModuleLoadVersion(loadVersion)
    if (moduleKey.value === 'dashboard') return loadDashboard(activeLoadVersion)
    loading.value = true
    try {
      const page = await getModulePage(moduleKey.value, { ...query })
      if (isStaleModuleLoad(activeLoadVersion)) return
      records.value = page.records || []
      total.value = page.total || 0
      await loadStats(activeLoadVersion)
    } catch (error) {
      if (!shouldIgnoreModuleLoadError(error, activeLoadVersion)) throw error
    } finally {
      if (!isStaleModuleLoad(activeLoadVersion)) {
        loading.value = false
      }
    }
  }

  function reset() {
    query.keyword = ''
    query.status = ''
    query.current = 1
    reload()
  }

function openCreate() {
  if (!canAdd.value) return denyUnauthorizedAction()
  drawer.visible = true
  drawer.mode = 'create'
  drawer.title = `新增${meta.value.title || routeTitle.value}`
  drawer.form = normalizeDrawerForm(drawerDefaults())
}

function openEdit(row: any) {
  if (!canEdit.value) return denyUnauthorizedAction()
  drawer.visible = true
  drawer.mode = 'edit'
  drawer.title = `编辑${meta.value.title || routeTitle.value}`
  drawer.form = normalizeDrawerForm(row)
}

  async function openDetail(row: any) {
    drawer.visible = true
    drawer.mode = 'detail'
    drawer.title = `${meta.value.title || routeTitle.value}详情`
    drawer.form = await getModuleDetail(moduleKey.value, row.id)
  }

  async function save() {
    const allowed = drawer.mode === 'create' ? canAdd.value : drawer.mode === 'edit' && canEdit.value
    if (!allowed) return denyUnauthorizedAction()
    await saveModuleRecord(moduleKey.value, drawer.form)
    drawer.visible = false
    reload()
  }

  async function changeStatus(row: any) {
    if (!canEdit.value) return denyUnauthorizedAction()
    const next = String(row.status).includes('禁用') || String(row.status).includes('异常') || row.status === '0' ? '正常' : '异常'
    await updateModuleStatus(moduleKey.value, row.id, next)
    reload()
  }

  async function remove(row: any) {
    if (!canDelete.value) return denyUnauthorizedAction()
    await deleteModuleRecord(moduleKey.value, row.id)
    ElMessage.success('删除成功')
    reload()
  }

  function onSelectionChange(rows: any[]) {
    selectedIds.value = rows.map((r) => r.id)
  }

  async function batchStatus(status: string) {
    if (!canEdit.value) return denyUnauthorizedAction()
    if (!selectedIds.value.length) return
    await batchUpdateModuleStatus(moduleKey.value, selectedIds.value, status)
    ElMessage.success(`已批量更新 ${selectedIds.value.length} 条`)
    reload()
  }

  async function batchDelete() {
    if (!canDelete.value) return denyUnauthorizedAction()
    if (!selectedIds.value.length) return
    await ElMessageBox.confirm(`确认批量删除 ${selectedIds.value.length} 条记录？`, '批量删除', { type: 'warning' })
    await batchDeleteModuleRecords(moduleKey.value, selectedIds.value)
    ElMessage.success('批量删除成功')
    reload()
  }

  async function handleModuleAction(action: { text: string; status?: string }) {
    if (!canEdit.value) return denyUnauthorizedAction()
    if (!selectedIds.value.length) return ElMessage.warning('请先选择记录')
    if (action.status) return batchStatus(action.status)
  }

  async function exportCsv() {
    if (!canExport.value) return denyUnauthorizedAction()
    const token = userStore.accessToken?.startsWith('Bearer ') ? userStore.accessToken : `Bearer ${userStore.accessToken}`
    const res = await fetch(getModuleExportUrl(moduleKey.value, query), { headers: { Authorization: token } })
    if (!res.ok) throw new Error('导出失败')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${moduleKey.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function refreshHotGoods() {
    if (!canRefreshStats.value) return denyUnauthorizedAction()
    refreshing.value = true
    try {
      const res = await refreshHotGoodsStat(5)
      if (res) {
        ElMessage.success(`统计数据刷新完成，共记录 ${res.count} 条`)
        await reload()
      }
    } catch (err: any) {
      ElMessage.error(err?.message || '刷新统计数据失败')
    } finally {
      refreshing.value = false
    }
  }

  function goModule(path: string) { router.push(path) }

  function toneClass(tone?: DashboardTone) {
    return tone ? `tone-${tone}` : 'tone-muted'
  }

  function chartColors(chart: DashboardChartModel) {
    return chart.series.map((series) => series.color)
  }

  function lineChartData(chart: DashboardChartModel, variant: 'finance' | 'growth' | 'panel' = 'panel'): LineDataItem[] {
    return chart.series.map((series, index) => {
      const withArea = variant === 'finance'
        ? index === 0
        : variant === 'growth'
          ? index === 1
          : chart.series.length === 1 || index === 0
      const isSecondaryLine = variant === 'growth'
        ? index !== 1
        : variant === 'panel'
          ? chart.series.length > 1 && index === chart.series.length - 1
          : index === 1

      return {
        name: series.label,
        data: series.values,
        smooth: true,
        symbol: 'circle',
        symbolSize: variant === 'finance' ? (index === 0 ? 7.5 : 5.5) : variant === 'growth' ? (index === 1 ? 5.5 : 4.2) : chart.series.length === 1 ? 5.2 : 4.2,
        lineWidth: variant === 'finance' ? (index === 0 ? 5.2 : 3.4) : variant === 'growth' ? (index === 1 ? 3.8 : 2.8) : chart.series.length === 1 ? 3.4 : 2.7,
        lineStyleType: isSecondaryLine ? 'dashed' : 'solid',
        shadowBlur: variant === 'finance' ? (index === 0 ? 3 : 3) : variant === 'growth' ? 14 : 12,
        shadowColor: variant === 'finance' && index === 0 ? 'rgba(59, 130, 246, 0.07)' : series.color,
        shadowOffsetY: variant === 'finance' ? 1 : 5,
        areaStyle: withArea
          ? {
              startOpacity: variant === 'finance' ? 0.14 : variant === 'growth' ? 0.22 : 0.18,
              endOpacity: 0.02
            }
          : undefined
      }
    })
  }

  function lineChartBounds(chart: DashboardChartModel, variant: 'finance' | 'growth' | 'panel' = 'panel') {
    const values = chart.series.reduce<number[]>((acc, series) => {
      series.values.forEach((value) => {
        const numeric = Number(value)
        if (Number.isFinite(numeric)) acc.push(numeric)
      })
      return acc
    }, [])

    if (!values.length) {
      return { min: 0, max: 1 }
    }

    const min = Math.min(...values)
    const max = Math.max(...values)

    if (max <= 0) {
      return { min: 0, max: 1 }
    }

    const baseline = variant === 'finance' ? 0.4 : variant === 'growth' ? 0.3 : 0.26
    const range = Math.max(max - min, max * baseline, 0.4)
    const minPadding = variant === 'finance'
      ? Math.max(range * 0.22, max * 0.08, 0.2)
      : Math.max(range * 0.52, max * 0.14, 0.1)
    const maxPadding = variant === 'finance'
      ? Math.max(range * 0.18, max * 0.1, 0.24)
      : Math.max(range * 0.34, max * 0.14, 0.14)

    const precision = max < 10 ? 2 : 0
    const minBound = variant === 'finance'
      ? 0
      : Math.max(0, Number((min - minPadding).toFixed(precision)))
    const maxBound = Number((max + maxPadding).toFixed(precision))

    return {
      min: minBound,
      max: maxBound > minBound ? maxBound : minBound + 1
    }
  }

  function barChartData(chart: DashboardChartModel): BarDataItem[] {
    return chart.series.map((series) => ({
      name: series.label,
      data: series.values,
      barWidth: chart.series.length > 1 ? 8 : 10
    }))
  }

  function isBarChart(chart?: DashboardChartModel | null) {
    return !!chart && chart.kind === 'bar'
  }

  function bottomServiceRows(panel: { table?: DashboardTableRow[] }) {
    return (panel.table || []).filter((row) => !row.label.includes('使用率'))
  }

  function bottomUsageRows(panel: { table?: DashboardTableRow[] }) {
    return (panel.table || []).filter((row) => row.label.includes('使用率'))
  }

  function usagePercent(value: string) {
    const numeric = Number.parseFloat(String(value || '').replace('%', ''))
    return Math.max(0, Math.min(100, Number.isFinite(numeric) ? numeric : 0))
  }

  function gaugeStyle(value: number | null) {
    const percent = value === null ? 0 : Math.max(0, Math.min(100, Number(value || 0)))
    return {
      background: value === null
        ? '#e6eefc'
        : `conic-gradient(#3b82f6 ${percent}%, #e6eefc ${percent}% 100%)`
    }
  }

  function tagType(v: any) {
    const text = String(v || '')
    if (text.includes('正常') || text.includes('启用') || text.includes('成功') || text.includes('已支付') || text.includes('在线') || text === '1') return 'success'
    if (text.includes('异常') || text.includes('失败') || text.includes('禁用') || text.includes('高') || text === '0') return 'danger'
    if (text.includes('待') || text.includes('过期') || text.includes('告警') || text.includes('离线')) return 'warning'
    return 'info'
  }
</script>

<style scoped lang="scss">
.admin-page { padding: 4px; }
.overview-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.surface-card {
  overflow: hidden;
  border: 1px solid #d8e4f3;
  border-radius: 20px;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  box-shadow:
    0 12px 26px rgba(134, 156, 194, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.92) inset;
}
.dashboard-hero--light {
  position: relative;
  overflow: hidden;
  border: 1px solid #d8e4f3;
  border-radius: 22px;
  background:
    radial-gradient(circle at 78% 22%, rgba(118, 154, 255, 0.22), transparent 23%),
    radial-gradient(circle at 12% 64%, rgba(113, 184, 255, 0.1), transparent 22%),
    linear-gradient(180deg, #ffffff, #f6faff);
  box-shadow:
    0 16px 34px rgba(125, 152, 199, 0.09),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}
.dashboard-hero--light::before {
  content: '';
  position: absolute;
  left: 32px;
  bottom: 26px;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(170, 203, 255, 0.52), rgba(170, 203, 255, 0));
  opacity: 0.92;
}
.dashboard-hero--light :deep(.el-card__body) {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(500px, 0.92fr);
  align-items: center;
  gap: 18px;
  padding: 22px 24px 20px;
}
.hero-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  max-width: 720px;
}
.hero-eyebrow {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.10);
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 10px;
}
.dashboard-hero--light h2 {
  margin: 0;
  color: #0f172a;
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.12;
}
.dashboard-hero--light p {
  max-width: 560px;
  margin: 0;
  color: #6e7f99;
  font-size: 13px;
  line-height: 1.66;
}
.hero-side {
  display: grid;
  min-width: 0;
  max-width: none;
  gap: 10px;
}
.hero-side__top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(168px, 33%, 214px);
  align-items: stretch;
  gap: 14px;
}
.hero-status-cluster {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
}
.hero-chip-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.hero-chip {
  display: flex;
  min-height: 64px;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid rgba(217, 229, 248, 0.92);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 250, 255, 0.98));
  padding: 12px 14px 10px;
}
.hero-chip span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #71819a;
  font-size: 11px;
  margin-bottom: 6px;
}
.hero-chip span::before,
.hero-status-note span::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgba(79, 125, 255, 0.25);
  box-shadow: 0 0 0 4px rgba(79, 125, 255, 0.08);
  flex-shrink: 0;
}
.hero-chip.tone-success span::before,
.hero-status-note.tone-success span::before {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.1);
}
.hero-chip.tone-warning span::before,
.hero-status-note.tone-warning span::before {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1);
}
.hero-chip.tone-danger span::before,
.hero-status-note.tone-danger span::before {
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1);
}
.hero-chip.tone-brand span::before,
.hero-status-note.tone-brand span::before {
  background: #4f7dff;
  box-shadow: 0 0 0 4px rgba(79, 125, 255, 0.1);
}
.hero-chip strong {
  color: #0f172a;
  font-size: 17px;
  font-weight: 800;
}
.hero-status-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid rgba(217, 229, 248, 0.9);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(250, 252, 255, 0.96), rgba(245, 250, 255, 0.98));
  color: #71819a;
  font-size: 12px;
  padding: 10px 14px;
}
.hero-status-note span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.hero-status-note strong {
  color: #0f172a;
  font-size: 17px;
  font-weight: 800;
}
.hero-visual {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(213, 226, 248, 0.98);
  border-radius: 18px;
  background:
    radial-gradient(circle at 28% 24%, rgba(123, 166, 255, 0.38), transparent 34%),
    radial-gradient(circle at 76% 18%, rgba(147, 197, 253, 0.36), transparent 26%),
    linear-gradient(180deg, rgba(245, 249, 255, 0.98), rgba(232, 241, 255, 0.98));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
  min-height: 148px;
}
.hero-visual__halo,
.hero-visual__beam,
.hero-visual__bar,
.hero-visual__dot {
  position: absolute;
}
.hero-visual__halo {
  inset: 18px 24px auto 24px;
  height: 42px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(191, 219, 254, 0), rgba(191, 219, 254, 0.55), rgba(191, 219, 254, 0));
  filter: blur(2px);
}
.hero-visual__beam {
  right: 24px;
  bottom: 22px;
  left: 24px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(125, 172, 255, 0.18), rgba(125, 172, 255, 0.04));
}
.hero-visual__bar {
  bottom: 32px;
  width: 24px;
  border-radius: 16px 16px 10px 10px;
  background: linear-gradient(180deg, rgba(160, 193, 255, 0.62), rgba(70, 126, 250, 0.98));
  box-shadow:
    0 18px 32px rgba(74, 127, 248, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
}
.hero-visual__bar--sm {
  left: 38px;
  height: 52px;
}
.hero-visual__bar--md {
  left: 74px;
  height: 84px;
}
.hero-visual__bar--lg {
  right: 34px;
  width: 30px;
  height: 106px;
}
.hero-visual__dot {
  width: 11px;
  height: 11px;
  border: 3px solid rgba(90, 146, 255, 0.32);
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 0 0 7px rgba(147, 197, 253, 0.12);
}
.hero-visual__dot--left {
  top: 50px;
  left: 24px;
}
.hero-visual__dot--right {
  top: 28px;
  right: 28px;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
.hero-actions :deep(.el-button) {
  height: 36px;
  border-radius: 11px;
  padding: 0 16px;
  border-color: #d9e7ff;
  box-shadow: 0 10px 22px rgba(133, 157, 202, 0.08);
}
.hero-actions :deep(.el-button--primary) {
  border-color: transparent;
  background: linear-gradient(135deg, #4f7dff, #6d9dff);
}
.overview-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.overview-section__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.overview-section__heading h3 {
  margin: 0 0 2px;
  color: #0f172a;
  font-size: 21px;
  font-weight: 800;
}
.overview-section__heading p {
  margin: 0;
  color: #7f90aa;
  font-size: 12px;
}
.kpi-group-grid,
.three-col-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.three-col-grid {
  align-items: stretch;
}
.kpi-group-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.two-col-grid {
  display: grid;
  grid-template-columns: 1.35fr .95fr;
  gap: 12px;
}
.finance-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-template-areas:
    'stats stats stats stats'
    'chart chart chart gauge';
  gap: 14px;
}
.group-title,
.section-card__header h4 {
  margin: 0;
  color: #2563eb;
  font-size: 14px;
  font-weight: 800;
}
.section-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.section-card__header span {
  color: #8192ad;
  font-size: 12px;
}
.kpi-group-card :deep(.el-card__body),
.finance-chart-card :deep(.el-card__body),
.finance-stat-card :deep(.el-card__body),
.finance-gauge-card :deep(.el-card__body) {
  padding: 16px;
}
.kpi-group-card {
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.12), transparent 28%),
    linear-gradient(180deg, #ffffff, #f8fbff);
}
.kpi-group-card--platform {
  background:
    radial-gradient(circle at 100% 0, rgba(96, 165, 250, 0.16), transparent 30%),
    linear-gradient(180deg, #ffffff, #f6fbff);
}
.kpi-group-card--trade {
  background:
    radial-gradient(circle at 100% 0, rgba(245, 158, 11, 0.16), transparent 30%),
    linear-gradient(180deg, #ffffff, #fffaf2);
}
.kpi-group-card--service {
  background:
    radial-gradient(circle at 100% 0, rgba(34, 197, 94, 0.14), transparent 30%),
    linear-gradient(180deg, #ffffff, #f7fdf9);
}
.kpi-group-card--revenue {
  background:
    radial-gradient(circle at 100% 0, rgba(139, 92, 246, 0.16), transparent 30%),
    linear-gradient(180deg, #ffffff, #faf7ff);
}
.panel-card :deep(.el-card__body) {
  display: flex;
  height: 100%;
  flex-direction: column;
  padding: 15px;
}
.group-metrics,
.mini-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.mini-metric-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.mini-metric-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.mini-metric-grid--quad {
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
}
.mini-metric-grid--tight {
  gap: 8px;
}
.mini-metric {
  display: flex;
  min-height: 76px;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid #e8eff9;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff, #f9fbff);
  padding: 11px 11px 9px;
}
.mini-metric--panel {
  min-height: 68px;
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.08), transparent 22%),
    linear-gradient(180deg, #ffffff, #f9fbff);
}
.mini-metric--panel .mini-metric__value {
  font-size: 22px;
}
.mini-metric__label {
  color: #73839d;
  font-size: 12px;
}
.mini-metric__value,
.finance-stat-card__value,
.highlight-metric strong {
  color: #0f172a;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.05;
}
.finance-stat-card__value {
  position: relative;
  z-index: 1;
  font-size: 28px;
  letter-spacing: -0.02em;
}
.mini-metric__delta,
.mini-metric__note,
.panel-footer,
.table-stack__extra,
.status-row__extra,
.pending-stack__time {
  color: #8596b1;
  font-size: 12px;
}
.mini-metric__note {
  font-size: 11px;
}
.finance-side-panel {
  display: contents;
}
.finance-stat-grid {
  grid-area: stats;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  align-content: start;
}
.finance-gauge-card,
.finance-stat-card {
  height: 100%;
}
.finance-chart-card {
  grid-area: chart;
}
.finance-gauge-card {
  grid-area: gauge;
}
.finance-gauge-card :deep(.el-card__body) {
  display: flex;
  height: 100%;
  flex-direction: column;
}
.finance-chart-card,
.finance-gauge-card,
.finance-stat-card {
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.08), transparent 28%),
    linear-gradient(180deg, #ffffff, #f7fbff);
}
.finance-chart-stage {
  position: relative;
  overflow: hidden;
  border: 1px solid #e5edf9;
  border-radius: 20px;
  background:
    radial-gradient(circle at 84% 12%, rgba(79, 125, 255, 0.06), transparent 30%),
    radial-gradient(circle at 16% 0, rgba(191, 219, 254, 0.14), transparent 26%),
    linear-gradient(180deg, #fcfdff, #f3f8ff);
  padding: 18px 18px 12px;
}
.finance-chart-stage__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.finance-chart-stage__tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  padding: 5px 10px;
}
.finance-stat-card {
  position: relative;
  overflow: hidden;
  border-color: #e0e9f7;
  min-height: 148px;
  box-shadow:
    0 16px 30px rgba(126, 148, 188, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.92) inset;
}
.finance-stat-card :deep(.el-card__body) {
  position: relative;
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 12px;
}
.finance-stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 124px;
  height: 124px;
  border-radius: 0 0 999px 0;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.04));
}
.finance-stat-card.tone-success::before {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.04));
}
.finance-stat-card.tone-warning::before {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.24), rgba(245, 158, 11, 0.05));
}
.finance-stat-card.tone-muted::before {
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.22), rgba(148, 163, 184, 0.04));
}
.finance-stat-card__top,
.finance-stat-card__meta {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.finance-stat-card__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.finance-stat-card__marker {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #cfe0ff;
  box-shadow: 0 0 0 6px rgba(79, 125, 255, 0.1);
  flex-shrink: 0;
}
.finance-stat-card__marker.tone-brand {
  background: #3b82f6;
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.12);
}
.finance-stat-card__marker.tone-success {
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.12);
}
.finance-stat-card__marker.tone-warning {
  background: #f59e0b;
  box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.14);
}
.finance-stat-card__marker.tone-muted {
  background: #94a3b8;
  box-shadow: 0 0 0 6px rgba(148, 163, 184, 0.14);
}
.finance-stat-card__glow {
  position: absolute;
  right: -18px;
  bottom: -22px;
  width: 104px;
  height: 104px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.18), rgba(59, 130, 246, 0));
  pointer-events: none;
}
.finance-stat-card.tone-success .finance-stat-card__glow {
  background: radial-gradient(circle, rgba(34, 197, 94, 0.18), rgba(34, 197, 94, 0));
}
.finance-stat-card.tone-warning .finance-stat-card__glow {
  background: radial-gradient(circle, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0));
}
.finance-stat-card.tone-muted .finance-stat-card__glow {
  background: radial-gradient(circle, rgba(148, 163, 184, 0.18), rgba(148, 163, 184, 0));
}
.finance-gauge-card {
  background:
    radial-gradient(circle at 50% 0, rgba(59, 130, 246, 0.12), transparent 34%),
    linear-gradient(180deg, #ffffff, #f7fbff);
}
.finance-gauge-card :deep(.el-card__body) {
  display: flex;
  height: 100%;
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
  padding-top: 18px;
}
.finance-stat-card__delta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 8px;
}
.finance-stat-card__note {
  color: #6f84a4;
  font-size: 11px;
  line-height: 1.5;
}
.finance-stat-card.tone-brand .finance-stat-card__delta {
  background: rgba(59, 130, 246, 0.1);
}
.finance-stat-card.tone-success .finance-stat-card__delta {
  background: rgba(34, 197, 94, 0.12);
}
.finance-stat-card.tone-warning .finance-stat-card__delta {
  background: rgba(245, 158, 11, 0.14);
}
.finance-stat-card.tone-muted .finance-stat-card__delta {
  background: rgba(148, 163, 184, 0.16);
}
.chart-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  color: #61728f;
  font-size: 12px;
  margin-bottom: 10px;
}
.chart-legend span {
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(220, 230, 246, 0.92);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  padding: 4px 10px;
}
.chart-legend--panel {
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  margin-top: 8px;
  margin-bottom: 8px;
}
.chart-legend i {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-right: 6px;
}
.chart-legend--wide {
  flex-wrap: wrap;
  margin-bottom: 0;
}
.finance-chart-stage :deep(.relative),
.panel-chart-shell :deep(.relative) {
  width: 100% !important;
}
.finance-chart-stage :deep(canvas),
.panel-chart-shell :deep(canvas) {
  border-radius: 14px;
}
.panel-chart-shell {
  margin-top: 8px;
  overflow: hidden;
  border: 1px solid #e6eef9;
  border-radius: 18px;
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.12), transparent 24%),
    linear-gradient(180deg, #fcfdff, #f6faff);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.85),
    0 10px 20px rgba(143, 166, 204, 0.06);
  padding: 12px 12px 6px;
}
.panel-chart-shell--bar {
  padding-top: 10px;
}
.panel-chart-shell--growth {
  margin-top: 0;
  padding-top: 14px;
}
.feature-card {
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.1), transparent 30%),
    linear-gradient(180deg, #ffffff, #f9fbff);
}
.feature-card--funnel {
  background:
    radial-gradient(circle at 100% 0, rgba(245, 158, 11, 0.13), transparent 30%),
    linear-gradient(180deg, #ffffff, #fffaf3);
}
.feature-card--growth {
  background:
    radial-gradient(circle at 100% 0, rgba(34, 197, 94, 0.12), transparent 30%),
    linear-gradient(180deg, #ffffff, #f7fdf9);
}
.line-chart {
  display: flex;
  gap: 10px;
}
.line-chart--compact {
  margin-top: 8px;
}
.line-chart__axis {
  display: flex;
  min-width: 34px;
  flex-direction: column;
  justify-content: space-between;
  color: #8f9eb8;
  font-size: 11px;
  padding-bottom: 20px;
}
.line-chart__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.line-chart__body--full {
  width: 100%;
}
.line-chart__svg {
  width: 100%;
  height: 148px;
}
.line-chart--compact .line-chart__svg {
  height: 88px;
}
.panel-card .line-chart--compact .line-chart__svg {
  height: 112px;
}
.line-chart__grid {
  stroke: #e1eaf6;
  stroke-width: .8;
}
.line-chart__point {
  filter: drop-shadow(0 3px 8px rgba(79, 125, 255, 0.22));
}
.line-chart__labels {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  color: #8596b0;
  font-size: 11px;
}
.line-chart__labels span {
  text-align: center;
}
.bar-chart {
  margin-top: 10px;
}
.bar-chart__groups {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}
.bar-chart__group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.bar-chart__bars {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 78px;
  border-bottom: 1px solid #e4edf8;
}
.panel-card .bar-chart__bars {
  height: 92px;
}
.bar-chart__bars::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(#e7eef9 1px, transparent 1px) top / 100% 31px repeat-y;
  opacity: 0.8;
  pointer-events: none;
}
.bar-chart__bar {
  position: relative;
  z-index: 1;
  width: 9px;
  border-radius: 999px 999px 4px 4px;
  box-shadow: 0 12px 22px rgba(59, 130, 246, 0.12);
}
.bar-chart__label {
  color: #8596b0;
  font-size: 10px;
}
.gauge-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 0;
  text-align: center;
}
.gauge-ring,
.mini-gauge {
  position: relative;
  display: grid;
  place-items: center;
  width: 128px;
  height: 128px;
  border-radius: 999px;
  margin: 0 auto 10px;
}
.finance-gauge-card .gauge-ring {
  margin: 0;
  align-self: center;
}
.mini-gauge {
  width: 88px;
  height: 88px;
  margin: 0;
}
.gauge-ring__inner,
.mini-gauge__inner {
  position: absolute;
  inset: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #fff;
  box-shadow: inset 0 0 0 1px #e8eff9;
}
.mini-gauge__inner {
  inset: 10px;
}
.gauge-ring__inner strong,
.mini-gauge__inner strong {
  color: #0f172a;
  font-size: 28px;
  font-weight: 800;
}
.mini-gauge__inner strong {
  font-size: 18px;
}
.gauge-ring__inner span,
.mini-gauge__inner span,
.panel-gauge-inline__detail {
  color: #8ea0ba;
  font-size: 12px;
}
.breakdown-list,
.status-table,
.table-stack,
.pending-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.breakdown-list {
  margin-top: 0;
}
.status-row,
.table-stack__row,
.pending-stack__item {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e7eef8;
  padding-bottom: 6px;
}
.status-row:last-child,
.table-stack__row:last-child,
.pending-stack__item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #cbd5e1;
  flex-shrink: 0;
}
.status-row__label,
.table-stack__label {
  flex: 1;
  min-width: 0;
  color: #2f405a;
  font-size: 12px;
  line-height: 1.45;
}
.table-stack__extra,
.status-row__extra {
  margin-left: auto;
}
.funnel-stage-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin-bottom: 10px;
}
.funnel-stage,
.highlight-metric {
  border: 1px solid #e7eef9;
  border-radius: 16px;
  background:
    radial-gradient(circle at 100% 0, rgba(79, 125, 255, 0.08), transparent 24%),
    linear-gradient(180deg, #ffffff, #f8fbff);
  padding: 12px;
  box-shadow:
    0 8px 18px rgba(138, 160, 200, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.84);
}
.funnel-stage {
  position: relative;
  border-radius: 14px;
  padding: 11px 18px 11px 12px;
}
.funnel-stage:not(:last-child) {
  margin-right: 10px;
}
.funnel-stage:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -10px;
  width: 20px;
  height: 20px;
  border-top: 1px solid #e7eef9;
  border-right: 1px solid #e7eef9;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  transform: translateY(-50%) rotate(45deg);
  z-index: 1;
}
.funnel-stage span,
.highlight-metric span {
  display: block;
}
.funnel-stage span {
  color: #71829c;
  font-size: 12px;
  margin-bottom: 8px;
}
.funnel-stage strong {
  color: #0f172a;
  font-size: 22px;
  font-weight: 800;
}
.funnel-stage small {
  color: #5e7090;
  font-size: 12px;
}
.highlight-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.highlight-metrics--three {
  margin-bottom: 10px;
}
.panel-gauge-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
  margin-bottom: 8px;
}
.panel-footer {
  margin: auto 0 0;
  padding-top: 8px;
  line-height: 1.6;
}
.panel-footer--link {
  color: #2563eb;
}
.panel-empty-state {
  display: flex;
  min-height: 132px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
  border: 1px dashed #dbe6f5;
  border-radius: 18px;
  background: linear-gradient(180deg, #fcfdff, #f7fbff);
  text-align: center;
  padding: 18px 16px;
}
.panel-empty-state__icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  border-radius: 999px;
  background: radial-gradient(circle at 50% 30%, rgba(132, 173, 255, 0.18), rgba(132, 173, 255, 0.05));
  box-shadow: inset 0 0 0 1px rgba(151, 181, 244, 0.14);
}
.panel-empty-state__shield {
  width: 18px;
  height: 22px;
  background: linear-gradient(180deg, #72a3ff, #3b82f6);
  clip-path: polygon(50% 0, 100% 14%, 100% 58%, 50% 100%, 0 58%, 0 14%);
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.22);
}
.panel-empty-state strong {
  color: #1d2d45;
  font-size: 13px;
  font-weight: 800;
}
.panel-empty-state p {
  max-width: 240px;
  margin: 0;
  color: #7f90aa;
  font-size: 12px;
  line-height: 1.65;
}
.panel-card {
  position: relative;
  height: 100%;
}
.panel-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 18px;
  right: 18px;
  height: 1px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0), rgba(59, 130, 246, 0.34), rgba(59, 130, 246, 0));
}
.panel-card--realtime {
  background:
    radial-gradient(circle at 100% 0, rgba(96, 165, 250, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff, #f7fbff);
}
.panel-card--health {
  background:
    radial-gradient(circle at 100% 0, rgba(34, 197, 94, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff, #f7fdf9);
}
.panel-card--workflow,
.panel-card--notify {
  background:
    radial-gradient(circle at 100% 0, rgba(139, 92, 246, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff, #faf7ff);
}
.panel-card--workflow .panel-gauge-inline {
  margin-top: 8px;
  margin-bottom: 10px;
  border: 1px solid #ece7fb;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(249, 246, 255, 0.98));
  padding: 12px 14px;
}
.panel-card--workflow .panel-gauge-inline__detail {
  color: #7e6bb4;
  font-weight: 700;
}
.panel-card--workflow .status-table {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.panel-card--workflow .status-row {
  align-items: flex-start;
  flex-direction: column;
  border: 1px solid #ece7fb;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  padding: 10px 12px;
}
.panel-card--workflow .status-row__label {
  color: #6c5aa2;
}
.panel-card--workflow .status-row__extra {
  margin-left: 0;
}
.panel-card--stock {
  background:
    radial-gradient(circle at 100% 0, rgba(245, 158, 11, 0.16), transparent 28%),
    linear-gradient(180deg, #ffffff, #fffaf3);
}
.panel-card--alerts,
.panel-card--recent-events {
  background:
    radial-gradient(circle at 100% 0, rgba(248, 113, 113, 0.12), transparent 28%),
    linear-gradient(180deg, #ffffff, #fffafb);
}
.panel-card--client-error,
.panel-card--system-health {
  background:
    radial-gradient(circle at 100% 0, rgba(148, 163, 184, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff, #f8fafc);
}
.panel-card--sync,
.panel-card--service-efficiency,
.panel-card--hot-goods {
  background:
    radial-gradient(circle at 100% 0, rgba(56, 189, 248, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff, #f5fbff);
}
.pending-stack__content {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.pending-stack__content b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
  font-size: 12px;
}
.pending-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
}
.panel-card--alerts .pending-stack__item,
.panel-card--recent-events .table-stack__row,
.panel-card--hot-goods .hot-goods-row,
.panel-card--stock .table-stack__row,
.panel-card--system-health .table-stack__row {
  border: 1px solid #e7eef8;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  padding: 10px 12px;
}
.panel-card--alerts .pending-stack {
  gap: 8px;
}
.panel-card--alerts .pending-stack__item {
  padding: 8px 10px;
}
.hot-goods-list,
.system-health-stack,
.event-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hot-goods-row {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e7eef8;
  padding-bottom: 6px;
}
.hot-goods-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.hot-goods-row__rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}
.hot-goods-row__label {
  overflow: hidden;
  color: #2f405a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hot-goods-row__value {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}
.service-status-pill {
  display: inline-flex;
  min-width: 42px;
  justify-content: center;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
}
.service-status-pill.tone-success {
  background: rgba(22, 163, 74, 0.12);
}
.service-status-pill.tone-warning {
  background: rgba(245, 158, 11, 0.14);
}
.service-status-pill.tone-danger {
  background: rgba(239, 68, 68, 0.12);
}
.usage-meter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}
.usage-meter {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.usage-meter__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #60718d;
  font-size: 11px;
}
.usage-meter__top strong {
  color: #0f172a;
  font-size: 11px;
}
.usage-meter__track {
  position: relative;
  overflow: hidden;
  height: 5px;
  border-radius: 999px;
  background: #e6edf8;
}
.usage-meter__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #4f7dff, #6ba9ff);
}
.event-timeline .table-stack__row {
  align-items: flex-start;
}
.event-timeline__content {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}
.event-timeline__content .table-stack__label {
  line-height: 1.45;
}
.muted { color: var(--art-gray-500); }
.tone-brand { color: #2563eb; }
.tone-success { color: #16a34a; }
.tone-warning { color: #f59e0b; }
.tone-danger { color: #ef4444; }
.tone-muted { color: #94a3b8; }
.status-dot.tone-brand,
.pending-pill.tone-brand { background: rgba(37, 99, 235, 0.12); }
.status-dot.tone-success,
.pending-pill.tone-success { background: rgba(22, 163, 74, 0.14); }
.status-dot.tone-warning,
.pending-pill.tone-warning { background: rgba(245, 158, 11, 0.16); }
.status-dot.tone-danger,
.pending-pill.tone-danger { background: rgba(239, 68, 68, 0.14); }
.status-dot.tone-muted,
.pending-pill.tone-muted { background: rgba(148, 163, 184, 0.18); }
.overview-page-footer {
  color: #a3b2ca;
  font-size: 12px;
  text-align: center;
  padding: 2px 0 8px;
}
.filter-card, .table-card { margin-bottom: 16px; border-radius: 16px; }
.page-title-row { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }
.module-stats { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; margin-bottom: 18px; }
.mini-stat :deep(.el-card__body) { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; }
.mini-stat span { color: var(--art-gray-500); }
.mini-stat b { font-size: 22px; }
.quick-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; }
.selected-tip { color: var(--art-gray-500); }
.drawer-form { padding-right: 20px; }
.empty-state { padding: 40px 0; text-align: center; color: var(--art-gray-500); font-size: 14px; }
@media (max-width: 1180px) {
  .two-col-grid,
  .finance-grid {
    grid-template-columns: 1fr;
  }
  .finance-grid {
    grid-template-areas:
      'stats'
      'chart'
      'gauge';
  }
  .finance-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .finance-gauge-card :deep(.el-card__body) {
    grid-template-columns: 154px minmax(0, 1fr);
  }
  .kpi-group-grid,
  .three-col-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 1180px) {
  .dashboard-hero--light :deep(.el-card__body) {
    grid-template-columns: 1fr;
  }
  .hero-side {
    min-width: 0;
    max-width: none;
  }
  .hero-side__top {
    grid-template-columns: minmax(0, 1fr) 220px;
  }
  .hero-actions {
    justify-content: flex-start;
  }
}
@media (max-width: 1080px) {
  .kpi-group-grid,
  .three-col-grid,
  .group-metrics,
  .mini-metric-grid,
  .highlight-metrics,
  .funnel-stage-grid,
  .hero-side__top {
    grid-template-columns: 1fr;
  }
  .finance-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hero-chip-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hero-visual {
    min-height: 160px;
  }
}
@media (max-width: 768px) {
  .page-title-row,
  .dashboard-hero--light :deep(.el-card__body),
  .hero-actions,
  .line-chart,
  .panel-gauge-inline {
    flex-direction: column;
    align-items: stretch;
  }
  .hero-chip-grid {
    grid-template-columns: 1fr;
  }
  .module-stats {
    grid-template-columns: 1fr;
  }
  .hero-side,
  .hero-actions {
    width: 100%;
  }
  .dashboard-hero--light :deep(.el-card__body) {
    padding: 24px 20px;
  }
  .finance-stat-grid,
  .finance-gauge-card :deep(.el-card__body) {
    grid-template-columns: 1fr;
  }
  .line-chart__axis {
    display: none;
  }
  .line-chart__labels {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
