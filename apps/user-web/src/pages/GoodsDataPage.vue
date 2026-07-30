<template>
  <div class="gda-page goods-data-analysis-page">
    <!-- ===== 页面外层标题 ===== -->
    <div class="page-title-section">
      <div class="header-badge">
        <span class="header-dot"></span>
        <span>商品运营数据看板</span>
      </div>
      <h1 class="page-title">商品数据分析</h1>
      <p v-if="realDateRangeText" class="page-subtitle">
        <span class="meta-val">{{ scopeLabel }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-key">数据时间</span>
        <span class="meta-val">{{ realDateRangeText }}</span>
      </p>
      <p v-else-if="loading" class="page-subtitle loading">
        <span class="loading-dots"><i></i><i></i><i></i></span>
        <span>正在加载商品数据</span>
      </p>
      <p v-else class="page-subtitle">
        <span class="meta-val">{{ scopeLabel }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-val">{{ daysLabel }}</span>
      </p>
    </div>

    <!-- ===== 筛选卡 ===== -->
    <div class="filter-card">
      <div class="filter-info">
        <span class="filter-block-name">商品数据分析</span>
        <span class="filter-sep">·</span>
        <span class="filter-label">数据时间</span>
        <span class="filter-value">{{ realDateRangeText || daysLabel }}</span>
        <span class="filter-sep">·</span>
        <span class="filter-label">更新于</span>
        <span class="filter-value">{{ updatedAt }}</span>
      </div>
      <div class="filter-controls">
        <div class="control-item">
          <label>账号</label>
          <select v-model="selectedAccountId" class="form-select" :disabled="accountsLoading">
            <option value="all">全部账号</option>
            <option v-for="acc in accountOptions" :key="acc.id" :value="acc.id">
              {{ formatAccountLabel(acc) }}
            </option>
          </select>
        </div>
        <div class="control-item">
          <label>时间范围</label>
          <div class="range-pills">
            <button
              v-for="opt in daysOptions"
              :key="opt.value"
              type="button"
              :class="['range-pill', { active: days === opt.value }]"
              :disabled="loading"
              @click="switchDays(opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <button class="refresh-btn" :disabled="loading" @click="loadAll">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :class="{ 'spin': loading }">
            <path d="M21 12a9 9 0 11-6.219-8.56" /><polyline points="21 3 21 9 15 9" />
          </svg>
          {{ loading ? '加载中' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-banner">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
      {{ error }}
      <button v-if="!loading" type="button" class="retry-link" @click="loadAll">重试</button>
    </div>

    <!-- 空状态：无账号 -->
    <EmptyState
      v-if="!accountsLoading && accountOptions.length === 0"
      icon="📦"
      title="当前没有可用的闲鱼账号"
      description="绑定闲鱼账号并同步商品后可查看数据分析。"
    />

    <!-- 加载骨架屏 -->
    <div v-else-if="loading && !summary" class="skeleton-wrap">
      <div class="skeleton-top-row">
        <div class="skeleton-kpi-grid">
          <div v-for="i in 6" :key="i" class="skeleton-card">
            <div class="sk-icon"></div>
            <div class="sk-body">
              <div class="sk-line sm"></div>
              <div class="sk-line lg"></div>
            </div>
          </div>
        </div>
        <div class="skeleton-chart">
          <div class="sk-line lg"></div>
          <div class="sk-chart-body"></div>
        </div>
      </div>
    </div>

    <template v-else-if="summary">
      <!-- ===== 运营预警横幅 ===== -->
      <div v-if="alertItems.length > 0" class="alert-banner">
        <div class="alert-header">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span class="alert-title">运营预警</span>
          <span class="alert-count">{{ alertItems.length }}</span>
        </div>
        <div class="alert-items">
          <div
            v-for="(al, idx) in alertItems"
            :key="idx"
            :class="['alert-item', `alert-${al.level}`]"
            @click="al.action && al.action()"
          >
            <span class="alert-item-icon">{{ al.icon }}</span>
            <span class="alert-item-text">{{ al.text }}</span>
            <span v-if="al.action" class="alert-item-action">→</span>
          </div>
        </div>
      </div>

      <!-- ===== KPI 卡片网格 ===== -->
      <div class="kpi-grid">
        <div
          v-for="(kpi, idx) in heroKpis"
          :key="kpi.key"
          class="kpi-card"
          :style="{ '--kpi-color': kpi.color, '--kpi-delay': idx * 70 + 'ms' }"
        >
          <div class="kpi-icon" :style="{ background: kpi.color + '14', color: kpi.color }" v-html="kpi.icon"></div>
          <div class="kpi-body">
            <span class="kpi-label">{{ kpi.label }}</span>
            <div class="kpi-value-row">
              <strong class="kpi-value">{{ kpi.display }}</strong>
              <span v-if="kpi.sub" class="kpi-sub">{{ kpi.sub }}</span>
            </div>
            <span v-if="kpi.ratio !== null" :class="['kpi-trend', 'trend-pill', ratioClass(kpi.ratio)]">
              <span class="trend-arrow">{{ ratioArrow(kpi.ratio) }}</span>{{ ratioPercent(kpi.ratio) }}
            </span>
          </div>
        </div>
      </div>

      <!-- ===== 趋势分析 + 智能诊断 ===== -->
      <div class="top-row">
        <CardPanel class="trend-panel" body-padding="0">
          <template #title>
            <div class="panel-title-row">
              <span class="panel-title-text">趋势分析</span>
              <span class="panel-title-desc">{{ trendDesc }}</span>
            </div>
          </template>
          <template #action>
            <div class="metric-switcher">
              <label>指标</label>
              <select v-model="trendMetricKey" class="metric-select">
                <option v-for="m in trendMetricOptions" :key="m.key" :value="m.key">{{ m.label }}</option>
              </select>
            </div>
          </template>
          <div v-if="trendAvailable" ref="trendChartEl" class="echart-box trend-box"></div>
          <EmptyState v-else icon="📈" title="趋势不可用" description="当前周期暂无订单数据" />
        </CardPanel>

        <CardPanel class="insights-panel">
          <template #title>
            <div class="panel-title-row">
              <span class="panel-title-text">智能诊断</span>
              <span class="panel-title-desc">基于当前周期数据自动生成</span>
            </div>
          </template>
          <div class="insights-list">
            <div
              v-for="(insight, idx) in insights"
              :key="idx"
              class="insight-item"
              :style="{ '--insight-color': insight.color }"
            >
              <div class="insight-icon" :style="{ background: insight.color + '14', color: insight.color }">{{ insight.icon }}</div>
              <div class="insight-body">
                <div class="insight-title">{{ insight.title }}</div>
                <div class="insight-desc">{{ insight.desc }}</div>
              </div>
            </div>
            <div v-if="insights.length === 0" class="insights-empty">暂无诊断信息</div>
          </div>
        </CardPanel>
      </div>

      <!-- ===== TOP 商品榜单 ===== -->
      <div v-if="topByOrders.length > 0 || topByExposure.length > 0" class="top-goods-row">
        <CardPanel class="top-goods-panel">
          <template #title>
            <div class="panel-title-row">
              <span class="panel-title-text">订单 TOP 5</span>
              <span class="panel-title-desc">{{ daysLabel }}订单数排行</span>
            </div>
          </template>
          <div class="top-goods-list">
            <div
              v-for="(item, idx) in topByOrders"
              :key="'to-' + idx"
              class="top-goods-item"
              :class="{ 'rank-medal': idx < 3, [`rank-${idx + 1}`]: idx < 3 }"
              @click="openGoodsDetail(item)"
            >
              <span class="top-rank">{{ idx + 1 }}</span>
              <div class="top-thumb">
                <img v-if="item.coverPic" :src="resolveTrustedMediaUrl(item.coverPic)" alt="" @error="onThumbError" />
                <span v-else class="thumb-placeholder">📦</span>
              </div>
              <div class="top-info">
                <div class="top-title" :title="item.title">{{ item.title || '未命名商品' }}</div>
                <div class="top-meta">
                  <span>{{ formatNumber(item.orderCount) }} 单</span>
                  <span class="dot-sep">·</span>
                  <span>{{ formatMoney(item.orderAmount) }}</span>
                  <span class="dot-sep">·</span>
                  <span>{{ formatNumber(item.soldCount) }} 件</span>
                </div>
              </div>
            </div>
            <div v-if="topByOrders.length === 0" class="top-empty">暂无订单数据</div>
          </div>
        </CardPanel>

        <CardPanel class="top-goods-panel">
          <template #title>
            <div class="panel-title-row">
              <span class="panel-title-text">曝光 TOP 5</span>
              <span class="panel-title-desc">累计曝光数排行</span>
            </div>
          </template>
          <div class="top-goods-list">
            <div
              v-for="(item, idx) in topByExposure"
              :key="'te-' + idx"
              class="top-goods-item"
              :class="{ 'rank-medal': idx < 3, [`rank-${idx + 1}`]: idx < 3 }"
              @click="openGoodsDetail(item)"
            >
              <span class="top-rank">{{ idx + 1 }}</span>
              <div class="top-thumb">
                <img v-if="item.coverPic" :src="resolveTrustedMediaUrl(item.coverPic)" alt="" @error="onThumbError" />
                <span v-else class="thumb-placeholder">📦</span>
              </div>
              <div class="top-info">
                <div class="top-title" :title="item.title">{{ item.title || '未命名商品' }}</div>
                <div class="top-meta">
                  <span>{{ formatNumber(item.exposureCount) }} 曝光</span>
                  <span class="dot-sep">·</span>
                  <span>{{ formatNumber(item.viewCount) }} 浏览</span>
                  <span class="dot-sep">·</span>
                  <span>{{ formatNumber(item.wantCount) }} 想要</span>
                </div>
              </div>
            </div>
            <div v-if="topByExposure.length === 0" class="top-empty">暂无曝光数据</div>
          </div>
        </CardPanel>
      </div>

      <!-- ===== 商品列表 ===== -->
      <CardPanel class="products-table-card">
        <template #title>
          <div class="panel-title-row">
            <span class="panel-title-text">商品列表</span>
            <span class="panel-title-desc">点击行查看单商品数据/趋势</span>
          </div>
        </template>
        <template #action>
          <div class="table-toolbar">
            <input
              v-model="productsKeyword"
              type="text"
              class="table-input"
              placeholder="搜索商品标题"
              @keyup.enter="reloadProducts"
            />
            <select v-model="productsSortBy" class="table-select" @change="reloadProducts">
              <option value="order">按订单数</option>
              <option value="orderAmount">按订单金额</option>
              <option value="exposure">按曝光数</option>
              <option value="view">按浏览数</option>
              <option value="want">按想要数</option>
              <option value="sold">按销量</option>
              <option value="conversion">按转化率</option>
              <option value="newest">按上架时间</option>
              <option value="price">按价格</option>
            </select>
            <button class="btn-secondary" :disabled="productsLoading" @click="reloadProducts">搜索</button>
          </div>
        </template>

        <div v-if="productsLoading && products.length === 0" class="table-skeleton">
          <div v-for="i in 5" :key="i" class="table-skeleton-row">
            <div class="sk-line sm"></div>
            <div class="sk-line lg"></div>
            <div class="sk-line sm"></div>
            <div class="sk-line sm"></div>
            <div class="sk-line sm"></div>
          </div>
        </div>

        <div v-else-if="products.length === 0" class="table-empty">
          <EmptyState icon="📭" title="暂无商品数据" description="同步闲鱼商品后可查看分析数据" />
        </div>

        <table v-else class="data-table">
          <thead>
            <tr>
              <th class="col-info">商品信息</th>
              <th class="col-price">价格</th>
              <th class="col-num">曝光</th>
              <th class="col-num">浏览</th>
              <th class="col-num">想要</th>
              <th class="col-num">订单数</th>
              <th class="col-num">订单金额</th>
              <th class="col-num">销量</th>
              <th class="col-num">转化率</th>
              <th class="col-status">状态</th>
              <th class="col-op">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in products"
              :key="row.id"
              class="data-row"
              :class="{ active: selectedGoodsId === row.id }"
              @click="openGoodsDetail(row)"
            >
              <td class="col-info">
                <div class="goods-info-cell">
                  <div class="goods-thumb">
                    <img v-if="row.cover_pic" :src="resolveTrustedMediaUrl(row.cover_pic)" alt="" @error="onThumbError" />
                    <span v-else class="thumb-placeholder">📦</span>
                  </div>
                  <div class="goods-meta">
                    <div class="goods-title" :title="row.title">{{ row.title || '未命名商品' }}</div>
                    <div class="goods-sub">ID: {{ row.external_goods_id || row.id }}</div>
                  </div>
                </div>
              </td>
              <td class="col-price">{{ formatMoney(row.sold_price || row.price) }}</td>
              <td class="col-num">{{ formatNumber(row.exposure_count) }}</td>
              <td class="col-num">{{ formatNumber(row.view_count) }}</td>
              <td class="col-num">{{ row.want_count > 0 ? formatNumber(row.want_count) : '-' }}</td>
              <td class="col-num num-strong">{{ formatNumber(row.order_count) }}</td>
              <td class="col-num num-strong">{{ formatMoney(row.order_amount) }}</td>
              <td class="col-num">{{ formatNumber(row.sold_count) }}</td>
              <td class="col-num">
                <span :class="['conv-badge', convClass(row.conversion_rate)]">{{ row.conversion_rate.toFixed(2) }}%</span>
              </td>
              <td class="col-status">
                <span :class="['status-badge', `status-${row.status}`]">{{ statusText(row.status) }}</span>
              </td>
              <td class="col-op" @click.stop>
                <button class="row-btn" @click="openGoodsDetail(row)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div v-if="products.length > 0" class="pagination">
          <span class="page-info">共 {{ productsTotal }} 条</span>
          <button class="page-btn" :disabled="productsCurrent <= 1 || productsLoading" @click="changePage(productsCurrent - 1)">上一页</button>
          <span class="page-current">{{ productsCurrent }} / {{ productsTotalPages }}</span>
          <button class="page-btn" :disabled="productsCurrent >= productsTotalPages || productsLoading" @click="changePage(productsCurrent + 1)">下一页</button>
          <select v-model="productsPageSize" class="page-size" @change="reloadProducts">
            <option :value="20">20 条/页</option>
            <option :value="50">50 条/页</option>
            <option :value="100">100 条/页</option>
          </select>
        </div>
      </CardPanel>

      <!-- ===== 最差商品筛选区 ===== -->
      <CardPanel class="worst-card">
        <template #title>
          <div class="panel-title-row">
            <span class="panel-title-text">低效商品筛选</span>
            <span class="panel-title-desc">一键定位低效商品，支持批量重发或删除</span>
          </div>
        </template>
        <template #action>
          <div class="worst-toolbar">
            <select v-model="worstMetric" class="table-select" @change="loadWorstProducts">
              <option value="exposure">曝光最低</option>
              <option value="view">浏览最低</option>
              <option value="want">想要最少</option>
              <option value="conversion">转化最低</option>
              <option value="order">订单最少</option>
            </select>
            <label class="worst-limit-label">筛选数量</label>
            <input v-model.number="worstLimit" type="number" min="1" max="200" class="table-input worst-limit-input" @change="loadWorstProducts" />
            <button class="btn-secondary" :disabled="worstLoading" @click="loadWorstProducts">筛选</button>
          </div>
        </template>

        <div v-if="worstLoading && worstProducts.length === 0" class="table-skeleton">
          <div v-for="i in 3" :key="i" class="table-skeleton-row">
            <div class="sk-line sm"></div>
            <div class="sk-line lg"></div>
            <div class="sk-line sm"></div>
            <div class="sk-line sm"></div>
          </div>
        </div>

        <div v-else-if="worstProducts.length === 0" class="table-empty">
          <EmptyState icon="✨" title="暂无低效商品" description="当前筛选条件下没有匹配的商品" />
        </div>

        <template v-else>
          <div class="worst-presets">
            <span class="preset-label">快速筛选</span>
            <button
              v-for="p in worstPresets"
              :key="p.key"
              :class="['preset-tag', { active: worstMetric === p.metric && worstLimit === p.limit }]"
              @click="applyWorstPreset(p)"
            >{{ p.label }}</button>
          </div>
          <div class="worst-banner">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
            <span>已筛选 {{ worstProducts.length }} 件低效商品，支持批量操作。一键重发仅对已开启"售整自动上架"且有完整快照的商品生效；一键删除将从闲鱼下架并删除本地记录，不可恢复。</span>
          </div>
          <table class="data-table worst-table">
            <thead>
              <tr>
                <th class="col-check">
                  <input type="checkbox" :checked="worstSelectedAll" @change="toggleWorstSelectAll($event.target.checked)" />
                </th>
                <th class="col-info">商品信息</th>
                <th class="col-price">价格</th>
                <th class="col-num">曝光</th>
                <th class="col-num">浏览</th>
                <th class="col-num">想要</th>
                <th class="col-num">订单</th>
                <th class="col-num">转化率</th>
                <th class="col-status">状态</th>
                <th class="col-suggest">建议</th>
                <th class="col-relist">重发支持</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in worstProducts" :key="row.id" class="data-row">
                <td class="col-check">
                  <input type="checkbox" :value="row.id" v-model="worstSelected" />
                </td>
                <td class="col-info">
                  <div class="goods-info-cell">
                    <div class="goods-thumb">
                      <img v-if="row.cover_pic" :src="resolveTrustedMediaUrl(row.cover_pic)" alt="" @error="onThumbError" />
                      <span v-else class="thumb-placeholder">📦</span>
                    </div>
                    <div class="goods-meta">
                      <div class="goods-title" :title="row.title">{{ row.title || '未命名商品' }}</div>
                      <div class="goods-sub">ID: {{ row.external_goods_id || row.id }}</div>
                    </div>
                  </div>
                </td>
                <td class="col-price">{{ formatMoney(row.sold_price || row.price) }}</td>
                <td class="col-num">{{ formatNumber(row.exposure_count) }}</td>
                <td class="col-num">{{ formatNumber(row.view_count) }}</td>
                <td class="col-num">{{ row.want_count > 0 ? formatNumber(row.want_count) : '-' }}</td>
                <td class="col-num">{{ formatNumber(row.order_count) }}</td>
                <td class="col-num">{{ row.conversion_rate.toFixed(2) }}%</td>
                <td class="col-status">
                  <span :class="['status-badge', `status-${row.status}`]">{{ statusText(row.status) }}</span>
                </td>
                <td class="col-suggest">
                  <span :class="['suggest-badge', `suggest-${suggestAction(row).type}`]">{{ suggestAction(row).label }}</span>
                </td>
                <td class="col-relist">
                  <span :class="['relist-badge', row.auto_relist_enabled == 1 && row.has_snapshot == 1 ? 'ok' : 'no']">
                    {{ row.auto_relist_enabled == 1 && row.has_snapshot == 1 ? '可重发' : '不支持' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="worst-actions">
            <span class="worst-selected-info">已选 {{ worstSelected.length }} 件</span>
            <button
              class="btn-quick-select"
              :disabled="batchRepublishing || batchDeleting"
              @click="selectOnlyRepublishable"
              title="仅选中支持重发的商品（需开启售整自动上架 + 有完整快照）"
            >仅选可重发</button>
            <button
              class="btn-republish"
              :disabled="worstSelected.length === 0 || batchRepublishing"
              @click="batchRepublish"
            >{{ batchRepublishing ? '重发中...' : '一键重发' }}</button>
            <button
              class="btn-danger"
              :disabled="worstSelected.length === 0 || batchDeleting"
              @click="batchDelete"
            >{{ batchDeleting ? '删除中...' : '一键删除' }}</button>
            <span v-if="batchProgress" class="batch-progress">{{ batchProgress }}</span>
          </div>
        </template>
      </CardPanel>
    </template>

    <!-- ===== 单商品详情右侧抽屉 ===== -->
    <div v-if="drawerVisible" class="right-drawer goods-drawer" @click.self="closeDrawer">
      <div class="drawer-panel">
        <div class="drawer-header">
          <h3 class="drawer-title">商品数据详情</h3>
          <button class="drawer-close" @click="closeDrawer">×</button>
        </div>
        <div v-if="drawerLoading" class="drawer-loading">
          <div class="loading-dots"><i></i><i></i><i></i></div>
          <span>加载中</span>
        </div>
        <div v-else-if="drawerData" class="drawer-body">
          <!-- 商品基础信息 -->
          <div class="drawer-section">
            <div class="drawer-goods-card">
              <div class="drawer-goods-thumb">
                <img v-if="drawerData.cover_pic" :src="resolveTrustedMediaUrl(drawerData.cover_pic)" alt="" @error="onThumbError" />
                <span v-else class="thumb-placeholder">📦</span>
              </div>
              <div class="drawer-goods-meta">
                <div class="drawer-goods-title">{{ drawerData.title || '未命名商品' }}</div>
                <div class="drawer-goods-sub">
                  售价 {{ formatMoney(drawerData.sold_price || drawerData.price) }} · 库存 {{ drawerData.quantity ?? 0 }}
                </div>
                <div class="drawer-goods-sub">
                  上架时间 {{ formatTime(drawerData.gmt_create || drawerData.created_time) }}
                </div>
                <div class="drawer-goods-sub" v-if="drawerData.account_nickname">
                  所属账号 {{ drawerData.account_nickname }}
                </div>
              </div>
            </div>
          </div>

          <!-- 累计数据 -->
          <div class="drawer-section">
            <div class="section-title">累计数据</div>
            <div class="drawer-kpi-grid">
              <div class="drawer-kpi">
                <div class="dk-label">累计曝光</div>
                <div class="dk-value">{{ formatNumber(drawerData.exposure_count) }}</div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">累计浏览</div>
                <div class="dk-value">{{ formatNumber(drawerData.view_count) }}</div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">想要人数</div>
                <div class="dk-value">{{ formatNumber(drawerData.want_count) }}</div>
              </div>
              <div class="drawer-kpi" v-if="drawerData.exposure_count_30d > 0">
                <div class="dk-label">30天曝光</div>
                <div class="dk-value">{{ formatNumber(drawerData.exposure_count_30d) }}</div>
              </div>
              <div class="drawer-kpi" v-if="drawerData.view_count_30d > 0">
                <div class="dk-label">30天浏览</div>
                <div class="dk-value">{{ formatNumber(drawerData.view_count_30d) }}</div>
              </div>
            </div>
          </div>

          <!-- 时间范围内订单数据 -->
          <div class="drawer-section">
            <div class="section-title">{{ daysLabel }}订单数据</div>
            <div class="drawer-kpi-grid">
              <div class="drawer-kpi">
                <div class="dk-label">订单数</div>
                <div class="dk-value">{{ formatNumber(drawerData.orders?.orderCount) }}</div>
                <div v-if="drawerData.orders?.orderCountRatio !== undefined" :class="['dk-trend', ratioClass(drawerData.orders.orderCountRatio)]">
                  环比 {{ ratioArrow(drawerData.orders.orderCountRatio) }} {{ ratioPercent(drawerData.orders.orderCountRatio) }}
                </div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">订单金额</div>
                <div class="dk-value">{{ formatMoney(drawerData.orders?.orderAmount) }}</div>
                <div v-if="drawerData.orders?.orderAmountRatio !== undefined" :class="['dk-trend', ratioClass(drawerData.orders.orderAmountRatio)]">
                  环比 {{ ratioArrow(drawerData.orders.orderAmountRatio) }} {{ ratioPercent(drawerData.orders.orderAmountRatio) }}
                </div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">买家数</div>
                <div class="dk-value">{{ formatNumber(drawerData.orders?.buyerCount) }}</div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">销量</div>
                <div class="dk-value">{{ formatNumber(drawerData.orders?.soldCount) }}</div>
              </div>
              <div class="drawer-kpi">
                <div class="dk-label">转化率</div>
                <div class="dk-value">{{ (drawerData.orders?.conversionRate || 0).toFixed(2) }}%</div>
              </div>
            </div>
          </div>

          <!-- 单商品趋势图 -->
          <div class="drawer-section">
            <div class="section-title">{{ daysLabel }}订单趋势</div>
            <div ref="drawerChartEl" class="drawer-chart"></div>
          </div>

          <!-- 商品操作 -->
          <div class="drawer-section">
            <div class="section-title">商品操作</div>
            <div class="drawer-actions">
              <button
                class="btn-republish"
                :disabled="!canRepublish(drawerData) || drawerBusy"
                @click="republishSingle(drawerData)"
                :title="republishHint(drawerData)"
              >{{ drawerBusy ? '处理中...' : '重发该商品' }}</button>
              <button
                class="btn-danger"
                :disabled="drawerBusy"
                @click="deleteSingle(drawerData)"
              >{{ drawerBusy ? '处理中...' : '删除该商品' }}</button>
              <button class="btn-secondary" @click="openEditPage(drawerData)">编辑商品</button>
            </div>
            <p v-if="!canRepublish(drawerData)" class="drawer-hint">{{ republishHint(drawerData) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import EmptyState from '../components/EmptyState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import {
  getGoodsDataSummary,
  getGoodsDataProducts,
  getGoodsDataProductSummary,
  getGoodsDataProductTrend,
  getGoodsDataWorstProducts,
} from '../api/goodsData.js'
import { remoteDeleteItem, republishItem } from '../api/items.js'
import { deleteGoodsLocal } from '../api/goods.js'
import { accountName, formatMoney, formatNumber, timeText } from '../utils/format.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import { confirmAction } from '../utils/confirmAction.js'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

const emit = defineEmits(['navigate'])

// ===== 颜色常量 =====
const C = {
  primary: '#0d6bff',
  green: '#16bf78',
  red: '#ff5b61',
  orange: '#ff9f22',
  purple: '#8b5cf6',
  cyan: '#11b5d8',
  slate: '#72809a',
  pink: '#ec4899',
}

// ===== 状态 =====
const accountsLoading = ref(false)
const accountOptions = ref([])
const selectedAccountId = ref('all')

const daysOptions = [
  { value: 1, label: '近1日' },
  { value: 3, label: '近3日' },
  { value: 7, label: '近7日' },
  { value: 30, label: '近30日' },
]
const days = ref(7)

const loading = ref(false)
const error = ref('')
const summary = ref(null)
const updatedAt = ref('')

// 商品列表
const products = ref([])
const productsLoading = ref(false)
const productsKeyword = ref('')
const productsSortBy = ref('order')
const productsCurrent = ref(1)
const productsPageSize = ref(20)
const productsTotal = ref(0)
const productsTotalPages = computed(() => Math.max(1, Math.ceil(productsTotal.value / productsPageSize.value)))

// 最差商品
const worstLoading = ref(false)
const worstProducts = ref([])
const worstMetric = ref('exposure')
const worstLimit = ref(20)
const worstSelected = ref([])
const batchRepublishing = ref(false)
const batchDeleting = ref(false)
const batchProgress = ref('')

const worstPresets = [
          { key: 'exp20', label: '曝光最低 20', metric: 'exposure', limit: 20 },
          { key: 'exp50', label: '曝光最低 50', metric: 'exposure', limit: 50 },
          { key: 'view20', label: '浏览最低 20', metric: 'view', limit: 20 },
          { key: 'want20', label: '想要最少 20', metric: 'want', limit: 20 },
          { key: 'order20', label: '订单最少 20', metric: 'order', limit: 20 },
          { key: 'conv20', label: '转化最低 20', metric: 'conversion', limit: 20 },
          { key: 'exp100', label: '曝光最低 100', metric: 'exposure', limit: 100 },
        ]

// 详情抽屉
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerData = ref(null)
const drawerTrend = ref([])
const selectedGoodsId = ref(null)
const drawerBusy = ref(false)

// 趋势图
const trendMetricKey = ref('order_count')
const trendMetricOptions = [
  { key: 'order_count', label: '订单数' },
  { key: 'order_amount', label: '订单金额' },
  { key: 'buyer_count', label: '买家数' },
  { key: 'goods_count', label: '销量' },
]
const trendChartEl = ref(null)
const drawerChartEl = ref(null)
let trendChart = null
let drawerChart = null

// ===== 计算属性 =====
const scopeLabel = computed(() => {
  if (selectedAccountId.value === 'all') return '全部账号'
  const acc = accountOptions.value.find(a => a.id === selectedAccountId.value)
  return acc ? accountName(acc) : '单账号'
})
const daysLabel = computed(() => `近 ${days.value} 日`)
const realDateRangeText = computed(() => {
  if (!summary.value?.realDateRange) return ''
  const [start, end] = summary.value.realDateRange
  return `${start} ~ ${end}`
})

const heroKpis = computed(() => {
  if (!summary.value) return []
  const g = summary.value.goods || {}
  const o = summary.value.orders || {}
  return [
    {
      key: 'goodsTotal', label: '商品总数', value: g.total, display: formatNumber(g.total),
      color: C.primary, icon: makeIcon('M20 7L12 3L4 7v10l8 4l8-4V7z'),
    },
    {
      key: 'onSale', label: '在售商品', value: g.onSale, display: formatNumber(g.onSale),
      sub: `下架 ${formatNumber(g.offShelf || 0)} · 已售 ${formatNumber(g.sold || 0)}`,
      color: C.green, icon: makeIcon('M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z'),
    },
    {
      key: 'exposure', label: '累计曝光', value: g.exposureSum, display: formatNumber(g.exposureSum),
      sub: g.exposure30dSum > 0 ? `30日 ${formatNumber(g.exposure30dSum)}` : '',
      color: C.cyan, icon: makeIcon('M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.46 12C3.73 7.94 7.5 5 12 5s8.27 2.94 9.54 7c-1.27 4.06-5.04 7-9.54 7S3.73 16.06 2.46 12z'),
    },
    {
      key: 'view', label: '累计浏览', value: g.viewSum, display: formatNumber(g.viewSum),
      sub: g.view30dSum > 0 ? `30日 ${formatNumber(g.view30dSum)}` : '',
      color: C.purple, icon: makeIcon('M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'),
    },
    {
      key: 'want', label: '想要人数', value: g.wantSum, display: formatNumber(g.wantSum),
      color: C.pink, icon: makeIcon('M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z'),
    },
    {
      key: 'orderCount', label: '订单数', value: o.orderCount, display: formatNumber(o.orderCount),
      sub: `金额 ${formatMoney(o.orderAmount)}`,
      color: C.orange, icon: makeIcon('M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2 M9 5a2 2 0 012-2h2a2 2 0 012 2 M9 5a2 2 0 002 2h2a2 2 0 002-2'),
      ratio: o.orderCountRatio,
    },
  ]
})

const insights = computed(() => {
  if (!summary.value) return []
  const list = []
  const g = summary.value.goods || {}
  const o = summary.value.orders || {}

  // 曝光为0商品占比
  if (g.total > 0) {
    const topByExposure = summary.value.topByExposure || []
    const topByOrders = summary.value.topByOrders || []
    if (topByExposure.length > 0 && topByExposure[0].exposureCount === 0) {
      list.push({
        icon: '⚠️', color: C.red,
        title: '存在零曝光商品',
        desc: `TOP 曝光商品「${topByExposure[0].title || '未命名'}」曝光为 0，建议检查标题与关键词。`,
      })
    }
    if (topByOrders.length > 0 && topByOrders[0].orderCount > 0) {
      list.push({
        icon: '🔥', color: C.orange,
        title: '爆款商品识别',
        desc: `「${topByOrders[0].title || '未命名'}」近期订单 ${topByOrders[0].orderCount} 单，金额 ${formatMoney(topByOrders[0].orderAmount)}，建议加大曝光与补货。`,
      })
    }
    if (o.conversionRate > 0 && o.conversionRate < 1) {
      list.push({
        icon: '📉', color: C.red,
        title: '转化率偏低',
        desc: `当前周期转化率 ${o.conversionRate.toFixed(2)}%，低于 1%，建议优化主图、价格与描述。`,
      })
    } else if (o.conversionRate >= 5) {
      list.push({
        icon: '🚀', color: C.green,
        title: '转化率优秀',
        desc: `当前周期转化率 ${o.conversionRate.toFixed(2)}%，超过 5%，可考虑扩充同类商品。`,
      })
    }
    if (o.orderCountRatio < 0 && o.orderCount > 0) {
      list.push({
        icon: '⬇️', color: C.red,
        title: '订单环比下降',
        desc: `订单数环比下降 ${Math.abs(o.orderCountRatio).toFixed(1)}%，建议立即排查曝光下滑原因。`,
      })
    } else if (o.orderCountRatio > 20) {
      list.push({
        icon: '⬆️', color: C.green,
        title: '订单环比上涨',
        desc: `订单数环比上涨 ${o.orderCountRatio.toFixed(1)}%，运营策略有效，可继续保持。`,
      })
    }
  }
  return list
})

const trendAvailable = computed(() => {
  if (!summary.value?.dailyTrend) return false
  return summary.value.dailyTrend.some(d => Number(d.order_count) > 0 || Number(d.order_amount) > 0)
})

const trendDesc = computed(() => {
  if (!trendAvailable.value) return '当前周期暂无订单数据'
  return `${daysLabel.value} · ${trendMetricOptions.find(m => m.key === trendMetricKey.value)?.label || ''}`
})

const worstSelectedAll = computed(() => {
  return worstProducts.value.length > 0 && worstSelected.value.length === worstProducts.value.length
})

const topByOrders = computed(() => summary.value?.topByOrders || [])
const topByExposure = computed(() => summary.value?.topByExposure || [])

// 运营预警
const alertItems = computed(() => {
  if (!summary.value?.alerts) return []
  const a = summary.value.alerts
  const items = []
  const onSale = a.onSale || 0

  if (a.zeroExposure > 0) {
    const pct = onSale > 0 ? (a.zeroExposure / onSale * 100).toFixed(0) : 0
    items.push({
      icon: '🚫',
      level: a.zeroExposure > onSale * 0.3 ? 'danger' : 'warn',
      text: `${a.zeroExposure} 件在售商品零曝光（占 ${pct}%），建议优化标题与关键词或重发`,
      action: () => { worstMetric.value = 'exposure'; worstLimit.value = 50; loadWorstProducts() },
    })
  }
  if (a.noOrder > 0) {
    const pct = onSale > 0 ? (a.noOrder / onSale * 100).toFixed(0) : 0
    items.push({
      icon: '📦',
      level: a.noOrder > onSale * 0.5 ? 'danger' : 'warn',
      text: `${daysLabel.value}有 ${a.noOrder} 件在售商品无订单（占 ${pct}%），建议筛选低效商品处理`,
      action: () => { worstMetric.value = 'order'; worstLimit.value = 50; loadWorstProducts() },
    })
  }
  if (a.zeroView > 0 && a.zeroExposure === 0) {
    items.push({
      icon: '👁',
      level: 'warn',
      text: `${a.zeroView} 件在售商品零浏览，曝光未转化为浏览，建议优化主图`,
    })
  }
  return items
})

// ===== 生命周期 =====
onMounted(async () => {
  await loadAccounts()
  await loadAll()
  // 进页面默认按"曝光最低 20"筛选一次低效商品
  loadWorstProducts()
})

onBeforeUnmount(() => {
  disposeTrendChart()
  disposeDrawerChart()
})

watch(trendMetricKey, () => {
  nextTick(renderTrendChart)
})

watch(selectedAccountId, () => {
  loadAll()
  // 重置分页
  productsCurrent.value = 1
})

watch(days, () => {
  loadAll()
  loadWorstProducts()
})

// ===== 方法 =====
function makeIcon(pathD) {
  return `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${pathD}"/></svg>`
}

function formatAccountLabel(acc) {
  return accountName(acc)
}

function statusText(status) {
  const map = { 0: '在售', 1: '下架', 2: '已售', 3: '已删除' }
  return map[status] ?? '未知'
}

function convClass(rate) {
  if (rate >= 5) return 'conv-high'
  if (rate >= 1) return 'conv-mid'
  return 'conv-low'
}

function ratioClass(ratio) {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return 'trend-flat'
  if (ratio > 0) return 'trend-up'
  if (ratio < 0) return 'trend-down'
  return 'trend-flat'
}

function ratioArrow(ratio) {
  if (ratio === null || ratio === undefined) return ''
  if (ratio > 0) return '▲'
  if (ratio < 0) return '▼'
  return '—'
}

function ratioPercent(ratio) {
  if (ratio === null || ratio === undefined) return ''
  return `${Math.abs(ratio).toFixed(1)}%`
}

function formatTime(t) {
  if (!t) return '-'
  return timeText(t)
}

function onThumbError(e) {
  e.target.style.display = 'none'
}

function switchDays(d) {
  if (days.value === d) return
  days.value = d
}

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    accountOptions.value = res?.data?.records || []
  } catch (e) {
    accountOptions.value = []
  } finally {
    accountsLoading.value = false
  }
}

async function loadAll() {
  if (accountOptions.value.length === 0) return
  loading.value = true
  productsLoading.value = true
  error.value = ''
  try {
    const params = {
      accountId: selectedAccountId.value === 'all' ? null : Number(selectedAccountId.value),
      days: days.value,
    }
    // 并行发起 summary 和 products 请求，避免串行等待
    productsCurrent.value = 1
    const productsParams = {
      accountId: params.accountId,
      days: days.value,
      keyword: productsKeyword.value || undefined,
      sortBy: productsSortBy.value,
      current: productsCurrent.value,
      size: productsPageSize.value,
    }
    const [summaryRes, productsRes] = await Promise.all([
      getGoodsDataSummary(params).catch(e => { error.value = e.message || '加载数据失败'; return null }),
      getGoodsDataProducts(productsParams).catch(() => null),
    ])
    if (summaryRes) {
      summary.value = summaryRes?.data || null
      updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      nextTick(renderTrendChart)
    }
    if (productsRes) {
      const data = productsRes?.data || {}
      products.value = data.records || []
      productsTotal.value = data.total || 0
    } else {
      products.value = []
      productsTotal.value = 0
    }
  } finally {
    loading.value = false
    productsLoading.value = false
  }
}

async function loadProducts() {
  productsLoading.value = true
  try {
    const params = {
      accountId: selectedAccountId.value === 'all' ? null : Number(selectedAccountId.value),
      days: days.value,
      keyword: productsKeyword.value || undefined,
      sortBy: productsSortBy.value,
      current: productsCurrent.value,
      size: productsPageSize.value,
    }
    const res = await getGoodsDataProducts(params)
    const data = res?.data || {}
    products.value = data.records || []
    productsTotal.value = data.total || 0
  } catch (e) {
    products.value = []
    productsTotal.value = 0
  } finally {
    productsLoading.value = false
  }
}

function reloadProducts() {
  productsCurrent.value = 1
  loadProducts()
}

function changePage(p) {
  if (p < 1 || p > productsTotalPages.value) return
  productsCurrent.value = p
  loadProducts()
}

async function loadWorstProducts() {
  worstLoading.value = true
  worstSelected.value = []
  try {
    const params = {
      accountId: selectedAccountId.value === 'all' ? null : Number(selectedAccountId.value),
      days: days.value,
      metric: worstMetric.value,
      limit: Math.max(1, Math.min(worstLimit.value || 20, 200)),
    }
    const res = await getGoodsDataWorstProducts(params)
    worstProducts.value = res?.data || []
  } catch (e) {
    worstProducts.value = []
  } finally {
    worstLoading.value = false
  }
}

function toggleWorstSelectAll(checked) {
  worstSelected.value = checked ? worstProducts.value.map(p => p.id) : []
}

function selectOnlyRepublishable() {
  const republishable = worstProducts.value.filter(canRepublish)
  worstSelected.value = republishable.map(p => p.id)
  if (republishable.length === 0) {
    showToast('warn', '当前列表中没有可重发的商品（需开启售整自动上架 + 有完整快照）')
  } else {
    showToast('success', `已选中 ${republishable.length} 件可重发商品`)
  }
}

function applyWorstPreset(preset) {
  worstMetric.value = preset.metric
  worstLimit.value = preset.limit
  loadWorstProducts()
}

// ===== 单商品详情抽屉 =====
async function openGoodsDetail(row) {
  selectedGoodsId.value = row.id
  drawerVisible.value = true
  drawerLoading.value = true
  drawerData.value = null
  drawerTrend.value = []
  try {
    const [summaryRes, trendRes] = await Promise.all([
      getGoodsDataProductSummary(row.id, { days: days.value }),
      getGoodsDataProductTrend(row.id, { days: days.value }),
    ])
    drawerData.value = summaryRes?.data || null
    drawerTrend.value = trendRes?.data || []
    nextTick(renderDrawerChart)
  } catch (e) {
    drawerData.value = null
  } finally {
    drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerVisible.value = false
  drawerData.value = null
  selectedGoodsId.value = null
  disposeDrawerChart()
}

function canRepublish(g) {
  return g && g.auto_relist_enabled == 1 && g.has_snapshot == 1
}

function suggestAction(row) {
  const exposure = Number(row.exposure_count) || 0
  const orders = Number(row.order_count) || 0
  const canRelist = canRepublish(row)

  if (exposure === 0 && orders === 0) {
    return canRelist
      ? { type: 'relist', label: '建议重发' }
      : { type: 'edit', label: '建议编辑' }
  }
  if (exposure > 0 && orders === 0) {
    return { type: 'edit', label: '优化主图' }
  }
  if (exposure > 100 && orders > 0 && orders < 3) {
    return canRelist
      ? { type: 'relist', label: '可重发' }
      : { type: 'keep', label: '观察' }
  }
  return { type: 'keep', label: '观察' }
}

function republishHint(g) {
  if (!g) return ''
  if (g.auto_relist_enabled != 1) return '需先开启"售整自动上架"开关才能重发'
  if (g.has_snapshot != 1) return '该商品没有完整快照数据，无法重发。请先编辑保存以生成快照'
  return ''
}

async function republishSingle(g) {
  if (!canRepublish(g)) return
  const ok = await confirmAction({
    title: '确认重发该商品？',
    description: '将基于商品快照删除当前商品并重新上架。原商品会从闲鱼下架删除，新商品将保留所有编辑数据。',
  })
  if (!ok) return
  drawerBusy.value = true
  try {
    // 调用重发接口
    await republishItem({ xianyuAccountId: g.account_id, xyGoodsId: g.external_goods_id })
    await openGoodsDetail(g)
    await loadAll()
    await loadWorstProducts()
    showToast('success', '重发成功')
  } catch (e) {
    showToast('error', e.message || '重发失败')
  } finally {
    drawerBusy.value = false
  }
}

async function deleteSingle(g) {
  const ok = await confirmAction({
    title: '确认删除该商品？',
    description: '该商品会从闲鱼下架并删除本地记录。操作不可逆！',
    dangerous: true,
    confirmText: 'DELETE',
  })
  if (!ok) return
  drawerBusy.value = true
  try {
    try {
      await remoteDeleteItem({ xianyuAccountId: g.account_id, xyGoodsId: g.external_goods_id })
    } catch (e) {
      // 闲鱼删除失败仍尝试本地删除
    }
    await deleteGoodsLocal(g.id)
    closeDrawer()
    await loadAll()
    await loadWorstProducts()
    showToast('success', '删除成功')
  } catch (e) {
    showToast('error', e.message || '删除失败')
  } finally {
    drawerBusy.value = false
  }
}

function openEditPage(g) {
  if (!g?.account_id || !g?.external_goods_id) {
    showToast('warn', '商品信息不完整，无法编辑')
    return
  }
  emit('navigate', `fish-shop-edit/${g.account_id}/${g.external_goods_id}`)
}

// ===== 批量重发/删除 =====
async function batchRepublish() {
  if (worstSelected.value.length === 0 || batchRepublishing.value) return
  const selected = worstProducts.value.filter(p => worstSelected.value.includes(p.id))
  const republishable = selected.filter(canRepublish)
  if (republishable.length === 0) {
    showToast('warn', '选中的商品均不支持重发（需开启售整自动上架 + 有完整快照）')
    return
  }
  const ok = await confirmAction({
    title: `确认批量重发 ${republishable.length} 件商品？`,
    description: `共选中 ${selected.length} 件，其中 ${republishable.length} 件可重发。重发会删除原商品并基于快照重新上架。不支持重发的商品将被跳过。`,
  })
  if (!ok) return

  batchRepublishing.value = true
  batchProgress.value = ''
  let success = 0
  const failed = []
  for (let i = 0; i < republishable.length; i++) {
    const g = republishable[i]
    batchProgress.value = `重发中 ${i + 1}/${republishable.length}：${g.title || g.external_goods_id}`
    try {
      await republishItem({ xianyuAccountId: g.account_id, xyGoodsId: g.external_goods_id })
      success++
    } catch (e) {
      failed.push({ title: g.title, reason: e.message })
    }
    // 间隔 1.5 秒避免风控
    if (i < republishable.length - 1) await sleep(1500)
  }
  batchProgress.value = ''
  batchRepublishing.value = false
  if (success > 0) {
    showToast('success', `成功重发 ${success} 件${failed.length ? `，失败 ${failed.length} 件` : ''}`)
  } else if (failed.length > 0) {
    showToast('error', `重发全部失败：${failed[0].reason}`)
  }
  await loadWorstProducts()
  await loadAll()
}

async function batchDelete() {
  if (worstSelected.value.length === 0 || batchDeleting.value) return
  const selected = worstProducts.value.filter(p => worstSelected.value.includes(p.id))
  const ok = await confirmAction({
    title: `确认批量删除 ${selected.length} 件商品？`,
    description: '将逐一从闲鱼下架并删除本地记录。该操作不可逆！',
    dangerous: true,
    confirmText: 'DELETE',
  })
  if (!ok) return

  batchDeleting.value = true
  batchProgress.value = ''
  let success = 0
  const failed = []
  for (let i = 0; i < selected.length; i++) {
    const g = selected[i]
    batchProgress.value = `删除中 ${i + 1}/${selected.length}：${g.title || g.external_goods_id}`
    try {
      if (g.account_id && g.external_goods_id) {
        try {
          await remoteDeleteItem({ xianyuAccountId: g.account_id, xyGoodsId: g.external_goods_id })
        } catch (e) {
          // 闲鱼删除失败仍尝试本地删除
        }
      }
      try {
        await deleteGoodsLocal(g.id)
        success++
      } catch (e) {
        failed.push({ title: g.title, reason: e.message })
      }
    } catch (e) {
      failed.push({ title: g.title, reason: e.message })
    }
    if (i < selected.length - 1) await sleep(800)
  }
  batchProgress.value = ''
  batchDeleting.value = false
  if (success > 0) {
    showToast('success', `成功删除 ${success} 件${failed.length ? `，失败 ${failed.length} 件` : ''}`)
  } else if (failed.length > 0) {
    showToast('error', `删除全部失败：${failed[0].reason}`)
  }
  await loadWorstProducts()
  await loadAll()
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms))
}

function showToast(type, text) {
  window.dispatchEvent(new CustomEvent('xya-toast', { detail: { type, text } }))
}

// ===== ECharts =====
function disposeTrendChart() {
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
}

function disposeDrawerChart() {
  if (drawerChart) {
    drawerChart.dispose()
    drawerChart = null
  }
}

function renderTrendChart() {
  if (!trendChartEl.value || !summary.value?.dailyTrend) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartEl.value)
  }
  const data = summary.value.dailyTrend
  const metricKey = trendMetricKey.value
  const metricInfo = trendMetricOptions.find(m => m.key === metricKey) || trendMetricOptions[0]
  const isMoney = metricKey === 'order_amount'
  const xData = data.map(d => String(d.ds).slice(5)) // MM-DD
  const yData = data.map(d => Number(d[metricKey]) || 0)
  const color = isMoney ? C.orange : C.primary

  trendChart.setOption({
    grid: { top: 30, left: 50, right: 24, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const p = params[0]
        const full = data[p.dataIndex]?.ds
        const val = isMoney ? formatMoney(p.value) : formatNumber(p.value)
        return `${full}<br/>${metricInfo.label}：${val}`
      },
    },
    xAxis: {
      type: 'category', data: xData, boundaryGap: false,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#72809a', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: {
        color: '#72809a', fontSize: 11,
        formatter: v => isMoney ? `¥${v}` : v,
      },
    },
    series: [{
      type: 'line', data: yData, smooth: true, symbol: 'circle', symbolSize: 6,
      lineStyle: { color, width: 2.5 },
      itemStyle: { color },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '40' },
          { offset: 1, color: color + '05' },
        ]),
      },
    }],
  })
}

function renderDrawerChart() {
  if (!drawerChartEl.value || !drawerTrend.value?.length) return
  if (!drawerChart) {
    drawerChart = echarts.init(drawerChartEl.value)
  }
  const data = drawerTrend.value
  const xData = data.map(d => String(d.ds).slice(5))
  const orderData = data.map(d => Number(d.order_count) || 0)
  const amountData = data.map(d => Number(d.order_amount) || 0)

  drawerChart.setOption({
    grid: { top: 30, left: 50, right: 50, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const full = data[params[0].dataIndex]?.ds
        return `${full}<br/>订单数：${params[0].value}<br/>订单金额：¥${params[1].value.toFixed(2)}`
      },
    },
    legend: {
      data: ['订单数', '订单金额'],
      top: 0, right: 10,
      textStyle: { color: '#72809a', fontSize: 11 },
    },
    xAxis: {
      type: 'category', data: xData, boundaryGap: false,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#72809a', fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value', name: '订单数',
        position: 'left',
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#72809a', fontSize: 11 },
      },
      {
        type: 'value', name: '金额',
        position: 'right',
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#72809a', fontSize: 11, formatter: v => `¥${v}` },
      },
    ],
    series: [
      {
        name: '订单数', type: 'line', data: orderData, smooth: true,
        symbol: 'circle', symbolSize: 5,
        lineStyle: { color: C.primary, width: 2 },
        itemStyle: { color: C.primary },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: C.primary + '30' },
            { offset: 1, color: C.primary + '05' },
          ]),
        },
      },
      {
        name: '订单金额', type: 'line', yAxisIndex: 1, data: amountData, smooth: true,
        symbol: 'circle', symbolSize: 5,
        lineStyle: { color: C.orange, width: 2 },
        itemStyle: { color: C.orange },
      },
    ],
  })
}
</script>

<style scoped>
/* ===== 全局容器 ===== */
.gda-page {
  padding: 20px 24px 32px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  min-height: 100%;
  color: #1f2937;
}

/* ===== 标题区 ===== */
.page-title-section {
  margin-bottom: 18px;
}
.header-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 4px 12px;
  background: linear-gradient(135deg, #0d6bff14, #11b5d814);
  border: 1px solid #0d6bff20;
  border-radius: 999px;
  color: #0d6bff;
  font-size: 12px; font-weight: 600;
  margin-bottom: 10px;
}
.header-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #0d6bff;
  box-shadow: 0 0 8px #0d6bff;
}
.page-title {
  font-size: 26px; font-weight: 700; color: #1f2937;
  margin: 0 0 6px;
  letter-spacing: -0.5px;
}
.page-subtitle {
  font-size: 13px; color: #72809a; margin: 0;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.page-subtitle.loading { color: #94a3b8; }
.meta-key { color: #94a3b8; }
.meta-val { color: #475569; font-weight: 500; }
.meta-sep { color: #cbd5e1; }
.loading-dots { display: inline-flex; gap: 3px; }
.loading-dots i {
  width: 4px; height: 4px; border-radius: 50%;
  background: currentColor;
  animation: pulse 1.4s infinite ease-in-out both;
}
.loading-dots i:nth-child(2) { animation-delay: 0.16s; }
.loading-dots i:nth-child(3) { animation-delay: 0.32s; }
@keyframes pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ===== 筛选卡 ===== */
.filter-card {
  background: #fff;
  border-radius: 14px;
  padding: 14px 18px;
  margin-bottom: 18px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
}
.filter-info {
  font-size: 12px; color: #72809a;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.filter-block-name { color: #1f2937; font-weight: 600; font-size: 13px; }
.filter-label { color: #94a3b8; }
.filter-value { color: #475569; font-weight: 500; }
.filter-sep { color: #cbd5e1; }
.filter-controls {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
}
.control-item {
  display: flex; align-items: center; gap: 8px;
}
.control-item label {
  font-size: 12px; color: #72809a; font-weight: 500;
}
.form-select, .metric-select, .table-select {
  height: 32px; padding: 0 10px;
  border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; color: #1f2937;
  font-size: 13px;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s;
}
.form-select:hover, .metric-select:hover, .table-select:hover { border-color: #cbd5e1; }
.form-select:focus, .metric-select:focus, .table-select:focus { border-color: #0d6bff; }
.range-pills {
  display: inline-flex; background: #f1f5f9; border-radius: 8px; padding: 3px; gap: 2px;
}
.range-pill {
  border: none; background: transparent;
  padding: 5px 12px; border-radius: 6px;
  font-size: 12px; color: #64748b;
  cursor: pointer; transition: all 0.15s;
}
.range-pill:hover:not(:disabled) { color: #1f2937; }
.range-pill.active {
  background: #fff; color: #0d6bff;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.range-pill:disabled { opacity: 0.5; cursor: not-allowed; }
.refresh-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px; padding: 0 14px;
  background: #0d6bff; color: #fff;
  border: none; border-radius: 8px;
  font-size: 13px; font-weight: 500;
  cursor: pointer; transition: background 0.15s;
}
.refresh-btn:hover:not(:disabled) { background: #0b5ed7; }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.refresh-btn .spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

/* ===== 错误提示 ===== */
.error-banner {
  background: #fef2f2; color: #b91c1c;
  padding: 10px 14px; border-radius: 10px;
  margin-bottom: 14px;
  display: flex; align-items: center; gap: 8px;
  font-size: 13px;
}
.error-banner.warn { background: #fffbeb; color: #b45309; }
.retry-link {
  margin-left: auto; background: transparent; border: none;
  color: inherit; text-decoration: underline; cursor: pointer;
  font-size: 12px;
}

/* ===== 骨架屏 ===== */
.skeleton-wrap { margin-bottom: 18px; }
.skeleton-top-row {
  display: grid; grid-template-columns: 2fr 1fr; gap: 14px;
}
.skeleton-kpi-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}
.skeleton-card {
  background: #fff; border-radius: 12px; padding: 16px;
  display: flex; gap: 12px; align-items: center;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.sk-icon { width: 36px; height: 36px; border-radius: 8px; background: #e2e8f0; }
.sk-body { flex: 1; }
.sk-line { height: 8px; background: #e2e8f0; border-radius: 4px; margin-bottom: 6px; }
.sk-line.sm { width: 40%; }
.sk-line.lg { width: 70%; height: 14px; }
.skeleton-chart {
  background: #fff; border-radius: 12px; padding: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  min-height: 200px;
}
.sk-chart-body {
  height: 160px; background: linear-gradient(180deg, #f1f5f9, #e2e8f0);
  border-radius: 8px; margin-top: 12px;
}

/* ===== 运营预警横幅 ===== */
.alert-banner {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 14px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  border-left: 4px solid #ff9f22;
  animation: kpiIn 0.3s ease both;
}
.alert-header {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 10px;
  color: #b45309;
}
.alert-title {
  font-size: 13px; font-weight: 600;
}
.alert-count {
  background: #fef3c7; color: #92400e;
  padding: 1px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
}
.alert-items {
  display: flex; flex-direction: column; gap: 6px;
}
.alert-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: 8px;
  font-size: 13px; cursor: default;
  transition: background 0.15s;
}
.alert-item.alert-warn { background: #fffbeb; color: #92400e; }
.alert-item.alert-danger { background: #fef2f2; color: #b91c1c; }
.alert-item[style*="cursor"] { cursor: pointer; }
.alert-item:has(.alert-item-action) { cursor: pointer; }
.alert-item:has(.alert-item-action):hover { filter: brightness(0.97); }
.alert-item-icon { font-size: 14px; flex-shrink: 0; }
.alert-item-text { flex: 1; line-height: 1.4; }
.alert-item-action { font-size: 14px; opacity: 0.6; }

/* ===== 快速选择按钮 ===== */
.btn-quick-select {
  height: 32px; padding: 0 14px;
  background: #fff; color: #0d6bff;
  border: 1px solid #0d6bff40; border-radius: 8px;
  font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.btn-quick-select:hover:not(:disabled) {
  background: #0d6bff08; border-color: #0d6bff;
}
.btn-quick-select:disabled { opacity: 0.5; cursor: not-allowed; }

/* ===== KPI 网格 ===== */
.kpi-grid {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px;
  margin-bottom: 18px;
}
.kpi-card {
  background: #fff; border-radius: 12px; padding: 14px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  display: flex; gap: 10px;
  position: relative;
  animation: kpiIn 0.4s ease both;
  animation-delay: var(--kpi-delay);
  border-left: 3px solid var(--kpi-color);
}
@keyframes kpiIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.kpi-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-body { flex: 1; min-width: 0; }
.kpi-label {
  font-size: 12px; color: #72809a;
  display: block; margin-bottom: 4px;
}
.kpi-value-row {
  display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap;
}
.kpi-value {
  font-size: 20px; font-weight: 700; color: #1f2937;
  letter-spacing: -0.5px;
}
.kpi-sub {
  font-size: 11px; color: #94a3b8;
}
.kpi-trend {
  font-size: 11px; padding: 2px 6px; border-radius: 4px;
  margin-top: 4px; display: inline-block;
}
.trend-pill.trend-up { background: #dcfce7; color: #16a34a; }
.trend-pill.trend-down { background: #fee2e2; color: #dc2626; }
.trend-pill.trend-flat { background: #f1f5f9; color: #64748b; }

/* ===== top-row ===== */
.top-row {
  display: grid; grid-template-columns: 2fr 1fr; gap: 14px;
  margin-bottom: 18px;
}

/* ===== TOP 商品榜单 ===== */
.top-goods-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  margin-bottom: 18px;
}
.top-goods-panel { min-height: 0; }
.top-goods-list {
  display: flex; flex-direction: column; gap: 6px;
}
.top-goods-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 8px;
  cursor: pointer; transition: background 0.15s;
  border: 1px solid transparent;
}
.top-goods-item:hover { background: #f8fafc; border-color: #e2e8f0; }
.top-rank {
  flex-shrink: 0;
  width: 22px; height: 22px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #94a3b8;
  background: #f1f5f9;
}
.top-goods-item.rank-medal .top-rank { color: #fff; }
.top-goods-item.rank-1 .top-rank { background: #f59e0b; box-shadow: 0 2px 6px #f59e0b40; }
.top-goods-item.rank-2 .top-rank { background: #94a3b8; box-shadow: 0 2px 6px #94a3b840; }
.top-goods-item.rank-3 .top-rank { background: #b45309; box-shadow: 0 2px 6px #b4530940; }
.top-thumb {
  flex-shrink: 0;
  width: 36px; height: 36px; border-radius: 6px; overflow: hidden;
  background: #f1f5f9; display: flex; align-items: center; justify-content: center;
  border: 1px solid #e2e8f0;
}
.top-thumb img { width: 100%; height: 100%; object-fit: cover; }
.top-thumb .thumb-placeholder { font-size: 16px; }
.top-info { flex: 1; min-width: 0; }
.top-title {
  font-size: 13px; font-weight: 500; color: #1f2937;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.4;
}
.top-meta {
  font-size: 11px; color: #72809a;
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  margin-top: 2px;
}
.dot-sep { color: #cbd5e1; }
.top-empty {
  font-size: 12px; color: #94a3b8; text-align: center; padding: 16px 0;
}
.panel-title-row {
  display: flex; align-items: baseline; gap: 8px;
}
.panel-title-text {
  font-size: 14px; font-weight: 600; color: #1f2937;
}
.panel-title-desc {
  font-size: 12px; color: #94a3b8;
}
.metric-switcher {
  display: flex; align-items: center; gap: 6px;
}
.metric-switcher label {
  font-size: 12px; color: #72809a;
}
.echart-box {
  width: 100%;
}
.trend-box { height: 280px; }

/* ===== 智能诊断 ===== */
.insights-list {
  display: flex; flex-direction: column; gap: 10px;
}
.insight-item {
  display: flex; gap: 10px; padding: 10px;
  background: #f8fafc; border-radius: 8px;
  border-left: 3px solid var(--insight-color);
}
.insight-icon {
  width: 28px; height: 28px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; font-size: 14px;
}
.insight-body { flex: 1; }
.insight-title {
  font-size: 13px; font-weight: 600; color: #1f2937; margin-bottom: 2px;
}
.insight-desc {
  font-size: 12px; color: #64748b; line-height: 1.5;
}
.insights-empty {
  text-align: center; color: #94a3b8; font-size: 13px; padding: 20px;
}

/* ===== 商品表格 ===== */
.products-table-card, .worst-card {
  margin-bottom: 18px;
}
.table-toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.table-input {
  height: 32px; padding: 0 10px;
  border: 1px solid #e2e8f0; border-radius: 8px;
  font-size: 13px; outline: none;
  min-width: 180px;
}
.table-input:focus { border-color: #0d6bff; }
.btn-secondary {
  height: 32px; padding: 0 12px;
  background: #f1f5f9; color: #475569;
  border: 1px solid #e2e8f0; border-radius: 8px;
  font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn-secondary:hover:not(:disabled) { background: #e2e8f0; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.table-skeleton {
  padding: 12px;
}
.table-skeleton-row {
  display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid #f1f5f9;
}
.table-empty {
  padding: 30px 0;
}

.data-table {
  width: 100%; border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed;
}
.data-table thead th {
  padding: 10px 8px;
  color: #64748b; font-weight: 500; font-size: 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  white-space: nowrap;
  vertical-align: middle;
}
.data-table tbody td {
  padding: 10px 8px;
  border-bottom: 1px solid #f1f5f9;
  color: #1f2937;
  vertical-align: middle;
  overflow: hidden; text-overflow: ellipsis;
  word-break: break-all;
}
.data-row {
  cursor: pointer; transition: background 0.15s;
}
.data-row:hover { background: #f8fafc; }
.data-row.active { background: #eff6ff; }

/* 列宽固定分配，表头与内容统一对齐 */
.col-check { width: 44px; text-align: center; }
.col-info { width: 260px; text-align: left; }
.col-price { width: 84px; text-align: center; }
.col-num { width: 80px; text-align: center; font-variant-numeric: tabular-nums; }
.col-status { width: 70px; text-align: center; }
.col-suggest { width: 84px; text-align: center; white-space: nowrap; }
.col-relist { width: 84px; text-align: center; }
.col-op { width: 70px; text-align: center; }
.num-strong { font-weight: 600; color: #0d6bff; }

.goods-info-cell {
  display: flex; align-items: center; gap: 10px;
}
.goods-thumb {
  width: 40px; height: 40px; border-radius: 8px;
  background: #f1f5f9; overflow: hidden; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.goods-thumb img {
  width: 100%; height: 100%; object-fit: cover;
}
.thumb-placeholder { font-size: 18px; }
.goods-meta { flex: 1; min-width: 0; }
.goods-title {
  font-size: 13px; font-weight: 500; color: #1f2937;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 240px;
}
.goods-sub {
  font-size: 11px; color: #94a3b8; margin-top: 2px;
}

.conv-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 500;
}
.conv-high { background: #dcfce7; color: #16a34a; }
.conv-mid { background: #fef3c7; color: #d97706; }
.conv-low { background: #fee2e2; color: #dc2626; }

.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px;
}
.status-0 { background: #dcfce7; color: #16a34a; }
.status-1 { background: #f1f5f9; color: #64748b; }
.status-2 { background: #fef3c7; color: #d97706; }
.status-3 { background: #fee2e2; color: #dc2626; }

.row-btn {
  background: transparent; border: 1px solid #e2e8f0;
  padding: 4px 10px; border-radius: 6px;
  font-size: 12px; color: #475569;
  cursor: pointer; transition: all 0.15s;
}
.row-btn:hover { background: #0d6bff; color: #fff; border-color: #0d6bff; }

/* ===== 分页 ===== */
.pagination {
  display: flex; align-items: center; gap: 10px; justify-content: flex-end;
  padding: 12px 8px;
  font-size: 12px; color: #64748b;
}
.page-info { color: #94a3b8; }
.page-btn {
  height: 28px; padding: 0 10px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
  color: #475569; cursor: pointer; font-size: 12px;
}
.page-btn:hover:not(:disabled) { background: #f1f5f9; }
.page-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.page-current { font-weight: 500; color: #1f2937; }
.page-size {
  height: 28px; padding: 0 6px;
  border: 1px solid #e2e8f0; border-radius: 6px;
  font-size: 12px;
}

/* ===== 最差商品区 ===== */
.worst-toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.worst-limit-label { font-size: 12px; color: #72809a; }
.worst-limit-input { min-width: 80px; }
.worst-presets {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-bottom: 12px;
}
.preset-label {
  font-size: 12px; color: #72809a; margin-right: 2px;
}
.preset-tag {
  border: 1px solid #e2e8f0; background: #fff;
  padding: 4px 10px; border-radius: 6px;
  font-size: 12px; color: #475569;
  cursor: pointer; transition: all 0.15s;
}
.preset-tag:hover { border-color: #0d6bff; color: #0d6bff; }
.preset-tag.active {
  background: #0d6bff; color: #fff; border-color: #0d6bff;
  font-weight: 500;
}
.worst-banner {
  background: #fffbeb; color: #92400e;
  padding: 8px 12px; border-radius: 8px; margin-bottom: 12px;
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 12px; line-height: 1.5;
}
.worst-banner svg { flex-shrink: 0; margin-top: 2px; }
.relist-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px;
}
.relist-badge.ok { background: #dcfce7; color: #16a34a; }
.relist-badge.no { background: #f1f5f9; color: #94a3b8; }

.suggest-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 500; white-space: nowrap;
}
.suggest-relist { background: #dbeafe; color: #2563eb; }
.suggest-edit { background: #fef3c7; color: #d97706; }
.suggest-keep { background: #f1f5f9; color: #64748b; }

.worst-actions {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 8px; border-top: 1px solid #f1f5f9;
  margin-top: 8px;
}
.worst-selected-info {
  font-size: 12px; color: #64748b;
  margin-right: auto;
}
.btn-republish {
  height: 32px; padding: 0 16px;
  background: #16bf78; color: #fff;
  border: none; border-radius: 8px;
  font-size: 13px; font-weight: 500;
  cursor: pointer; transition: background 0.15s;
}
.btn-republish:hover:not(:disabled) { background: #0f9d6a; }
.btn-republish:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger {
  height: 32px; padding: 0 16px;
  background: #ff5b61; color: #fff;
  border: none; border-radius: 8px;
  font-size: 13px; font-weight: 500;
  cursor: pointer; transition: background 0.15s;
}
.btn-danger:hover:not(:disabled) { background: #e63946; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.batch-progress {
  font-size: 12px; color: #475569;
  background: #f1f5f9; padding: 4px 8px; border-radius: 6px;
}

/* ===== 单商品详情抽屉 ===== */
.right-drawer {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: 100%; max-width: 520px;
  background: rgba(15, 23, 42, 0.4);
  z-index: 1000;
  display: flex; justify-content: flex-end;
  animation: drawerFade 0.2s ease;
}
@keyframes drawerFade {
  from { opacity: 0; }
  to { opacity: 1; }
}
.drawer-panel {
  width: 100%; max-width: 520px;
  background: #fff;
  height: 100%;
  display: flex; flex-direction: column;
  box-shadow: -4px 0 16px rgba(15, 23, 42, 0.1);
  animation: drawerSlide 0.25s ease;
}
@keyframes drawerSlide {
  from { transform: translateX(20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.drawer-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  display: flex; align-items: center; justify-content: space-between;
}
.drawer-title {
  font-size: 16px; font-weight: 600; color: #1f2937; margin: 0;
}
.drawer-close {
  background: transparent; border: none;
  font-size: 24px; color: #94a3b8;
  cursor: pointer; line-height: 1;
}
.drawer-close:hover { color: #1f2937; }
.drawer-loading {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px; color: #94a3b8; font-size: 13px;
}
.drawer-body {
  flex: 1; overflow-y: auto;
  padding: 16px 20px;
}
.drawer-section {
  margin-bottom: 18px;
}
.drawer-goods-card {
  display: flex; gap: 12px;
  padding: 12px;
  background: #f8fafc; border-radius: 10px;
}
.drawer-goods-thumb {
  width: 64px; height: 64px; border-radius: 8px;
  background: #e2e8f0; overflow: hidden; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.drawer-goods-thumb img {
  width: 100%; height: 100%; object-fit: cover;
}
.drawer-goods-meta { flex: 1; min-width: 0; }
.drawer-goods-title {
  font-size: 14px; font-weight: 600; color: #1f2937;
  margin-bottom: 4px;
  word-break: break-word;
}
.drawer-goods-sub {
  font-size: 12px; color: #64748b; margin-bottom: 2px;
}
.section-title {
  font-size: 13px; font-weight: 600; color: #475569;
  margin-bottom: 8px; padding-left: 8px;
  border-left: 3px solid #0d6bff;
}
.drawer-kpi-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.drawer-kpi {
  background: #f8fafc; border-radius: 8px; padding: 10px;
  text-align: center;
}
.dk-label {
  font-size: 11px; color: #94a3b8; margin-bottom: 4px;
}
.dk-value {
  font-size: 16px; font-weight: 600; color: #1f2937;
}
.dk-trend {
  font-size: 11px; margin-top: 4px;
}
.dk-trend.trend-up { color: #16a34a; }
.dk-trend.trend-down { color: #dc2626; }
.dk-trend.trend-flat { color: #64748b; }
.drawer-chart {
  width: 100%; height: 220px;
  background: #f8fafc; border-radius: 8px;
}
.drawer-actions {
  display: flex; gap: 8px; flex-wrap: wrap;
}
.drawer-actions button {
  flex: 1; min-width: 100px;
}
.drawer-hint {
  font-size: 12px; color: #94a3b8; margin-top: 8px;
}

/* ===== 响应式 ===== */
@media (max-width: 1280px) {
  .kpi-grid { grid-template-columns: repeat(3, 1fr); }
  .top-row { grid-template-columns: 1fr; }
  .top-goods-row { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .gda-page { padding: 12px; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .skeleton-top-row { grid-template-columns: 1fr; }
  .skeleton-kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-card { flex-direction: column; align-items: stretch; }
  .filter-controls { width: 100%; }
  .table-toolbar { width: 100%; }
  .right-drawer { max-width: 100%; }
  .drawer-panel { max-width: 100%; }
  .data-table { font-size: 12px; }
  .col-info { width: 160px; }
  .col-num { width: 64px; }
  .col-price { width: 70px; }
}
</style>
