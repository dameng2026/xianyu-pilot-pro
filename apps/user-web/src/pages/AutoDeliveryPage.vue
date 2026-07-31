<template>
  <div class="ad-page">
    <!-- 页面标题 -->
    <div class="ad-header">
      <div>
        <h2 class="ad-title">自动发货</h2>
        <p class="ad-subtitle">按商品配置自动发货时机，支持文本发货、卡密发货，以及引用货源库快速配置</p>
      </div>
      <div class="ad-header-actions">
        <button class="ad-header-btn" @click="scanPendingOrders">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
          扫描待发货
        </button>
        <button class="ad-header-btn ad-header-btn-primary" @click="goSourceLibrary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
          货源库
        </button>
      </div>
    </div>

    <!-- 功能说明横幅 -->
    <div class="ad-banner">
      <div class="ad-banner-icon">🚀</div>
      <div class="ad-banner-content">
        <div class="ad-banner-title">自动发货省心省力</div>
        <p class="ad-banner-desc">
          买家付款后系统自动发送卡密或文本内容，支持付款后发货、确认收货后赠送、好评后赠送三种时机。多规格商品可按 SKU 独立配置发货规则。
        </p>
      </div>
      <div class="ad-banner-stats">
        <div class="ad-stat-item ad-stat-green">
          <b>{{ statValue(stats.todaySuccess) }}</b>
          <span>今日成功</span>
        </div>
        <div class="ad-stat-item" :class="stats.todayFail > 0 ? 'ad-stat-red' : 'ad-stat-gray'">
          <b>{{ statValue(stats.todayFail) }}</b>
          <span>今日失败</span>
        </div>
        <div class="ad-stat-item ad-stat-orange">
          <b>{{ statValue(stats.pendingOrders) }}</b>
          <span>待处理</span>
        </div>
        <div class="ad-stat-item" :class="stats.lowStockGoods > 0 ? 'ad-stat-red' : 'ad-stat-blue'">
          <b>{{ statValue(stats.lowStockGoods) }}</b>
          <span>库存预警</span>
        </div>
        <div class="ad-stat-item ad-stat-indigo">
          <b>{{ statValue(stats.enabledGoods) }}</b>
          <span>已启用</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="ad-toast ad-toast-error">
      <span class="ad-toast-icon">❌</span>{{ error }}
    </div>
    <div v-if="success" class="ad-toast ad-toast-success">
      <span class="ad-toast-icon">✅</span>{{ success }}
    </div>
    <div v-if="statsError" class="ad-toast ad-toast-warn">
      <span class="ad-toast-icon">⚠️</span>{{ statsError }}
    </div>
    <div v-if="sourcesError" class="ad-toast ad-toast-warn">
      <span class="ad-toast-icon">⚠️</span>{{ sourcesError }}
    </div>
    <div v-if="dependenciesError" class="ad-toast ad-toast-warn">
      <span class="ad-toast-icon">⚠️</span>{{ dependenciesError }}
    </div>

    <div class="ad-layout">
      <aside class="ad-sidebar">
        <div class="ad-filter-card">
          <div class="ad-card-header">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
            <span>筛选条件</span>
          </div>
          <div class="ad-filter-body">
            <div class="ad-filter-item">
              <label class="ad-filter-label">闲鱼账号</label>
              <select v-model="query.accountId" class="ad-input" :disabled="!accountsAvailable" @change="loadGoods">
                <option value="">全部账号</option>
                <option v-for="account in accounts" :key="account.id" :value="account.id">{{ accountName(account) }}</option>
              </select>
            </div>
            <div class="ad-filter-item">
              <label class="ad-filter-label">搜索商品</label>
              <input v-model="query.keyword" class="ad-input" placeholder="标题 / ID" @keyup.enter="loadGoods" />
            </div>
            <div class="ad-filter-item">
              <label class="ad-filter-label">发货形式</label>
              <select v-model="query.deliveryType" class="ad-input">
                <option value="">全部</option>
                <option value="text">文本发货</option>
                <option value="card">卡密发货</option>
                <option value="none">未配置</option>
              </select>
            </div>
            <div class="ad-filter-item">
              <label class="ad-filter-label">配置状态</label>
              <select v-model="query.configStatus" class="ad-input">
                <option value="">全部</option>
                <option value="configured">已配置</option>
                <option value="unconfigured">未配置</option>
              </select>
            </div>
            <div class="ad-filter-item">
              <label class="ad-filter-label">商品状态</label>
              <select v-model="query.goodsStatus" class="ad-input">
                <option value="">全部</option>
                <option value="0">在售</option>
                <option value="1">下架</option>
              </select>
            </div>
            <div class="ad-filter-actions">
              <button class="ad-btn ad-btn-primary ad-btn-block" @click="applyFilter">应用筛选</button>
              <button class="ad-btn ad-btn-ghost ad-btn-block" @click="resetFilter">重置筛选</button>
            </div>
          </div>
        </div>
      </aside>

      <main class="ad-main">
        <div class="ad-tip">
          <div class="ad-tip-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
          <div class="ad-tip-content">
            <b>付款后发货</b>会由系统定时扫描自动执行；<b>确认收货后赠送</b>和<b>好评后赠送</b>可在发货记录页手动触发。
          </div>
        </div>

        <div class="ad-table-card">
          <div class="ad-table-header">
            <div class="ad-table-title-row">
              <span class="ad-table-count">共 <b>{{ filteredGoods.length }}</b> 个商品</span>
              <span class="ad-table-hint">点击状态列可快速进入对应时机配置</span>
            </div>
          </div>
          <BaseTable :columns="columns" :rows="tableRows">
            <template #goodsInfo="{ row }">
              <div class="goods-cell">
                <img v-if="row.imageUrl" :src="row.imageUrl" class="goods-thumb" alt="" />
                <div v-else class="goods-thumb placeholder"></div>
                <div class="goods-detail">
                  <div class="goods-title" :title="row.title">{{ row.title }}</div>
                  <div class="goods-meta">
                    <span>ID: {{ row.id }}</span>
                    <span class="price">{{ row.price }}</span>
                  </div>
                </div>
              </div>
            </template>
            <template #category="{ row }">
              <Badge>{{ row.category || '-' }}</Badge>
            </template>
            <template #account="{ row }">
              <span class="subtle">{{ accountName(row._account) || '-' }}</span>
            </template>
            <template #payDelivery="{ row }">
              <div class="delivery-status" :class="statusClass(row._config?.payDelivery, row._configUnavailable)" @click="openConfig(row, 'payDelivery')">
                <span class="status-dot" :class="statusDotClass(row._config?.payDelivery, row._configUnavailable)"></span>
                {{ statusLabel(row._config?.payDelivery, row._configUnavailable) }}
              </div>
            </template>
            <template #confirmDelivery="{ row }">
              <div class="delivery-status" :class="statusClass(row._config?.confirmDelivery, row._configUnavailable)" @click="openConfig(row, 'confirmDelivery')">
                <span class="status-dot" :class="statusDotClass(row._config?.confirmDelivery, row._configUnavailable)"></span>
                {{ statusLabel(row._config?.confirmDelivery, row._configUnavailable) }}
              </div>
            </template>
            <template #reviewDelivery="{ row }">
              <div class="delivery-status" :class="statusClass(row._config?.reviewDelivery, row._configUnavailable)" @click="openConfig(row, 'reviewDelivery')">
                <span class="status-dot" :class="statusDotClass(row._config?.reviewDelivery, row._configUnavailable)"></span>
                {{ statusLabel(row._config?.reviewDelivery, row._configUnavailable) }}
              </div>
            </template>
            <template #op="{ row }">
              <button class="link" :disabled="row._configUnavailable" @click="openConfig(row, null)">配置</button>
              <button class="link danger-text" :disabled="row._configUnavailable" @click="removeConfig(row)">禁用</button>
            </template>
            <template #empty>
              <EmptyState icon="📦" title="暂无商品" description="请先同步商品，或调整当前筛选条件。">
                <template #actions>
                  <AppButton type="primary" @click="loadGoods">刷新数据</AppButton>
                </template>
              </EmptyState>
            </template>
          </BaseTable>
          <Pagination :total="filteredGoods.length" :current="current" :page-size="pageSize" @page-change="goPage" />
        </div>
      </main>
    </div>

    <div v-if="showBatchDialog" class="modal-overlay" @click.self="showBatchDialog = false">
      <div class="modal-content">
        <h3>批量设置发货配置</h3>
        <p class="subtle">将影响 <b>{{ filteredGoods.length }}</b> 个商品</p>
        <div class="form-grid">
          <div class="form-row">
            <label>发货时机</label>
            <select v-model="batchForm.action" class="input">
              <option value="payDelivery">付款后发货</option>
              <option value="confirmDelivery">确认收货后赠送</option>
              <option value="reviewDelivery">好评后赠送</option>
            </select>
          </div>
          <div class="form-row">
            <label>启用状态</label>
            <select v-model.number="batchForm.enabled" class="input">
              <option :value="1">启用</option>
              <option :value="0">停用</option>
            </select>
          </div>
          <div class="form-row">
            <label>发货模式</label>
            <select v-model="batchForm.mode" class="input">
              <option value="">保持不变</option>
              <option value="text">文本发货</option>
              <option value="card">卡密发货</option>
            </select>
          </div>
          <div v-if="batchForm.mode === 'card'" class="form-row">
            <label>卡密分组</label>
            <select v-model="batchForm.cardGroupId" class="input" :disabled="!cardGroupsAvailable">
              <option value="">请选择</option>
              <option v-for="group in cardGroups" :key="group.id" :value="group.id">{{ group.groupName }}</option>
            </select>
          </div>
          <div v-if="batchForm.mode === 'text'" class="form-row">
            <label>货源库</label>
            <select v-model="batchForm.sourceId" class="input" :disabled="!sourcesAvailable">
              <option value="">不指定货源库</option>
              <option v-for="source in textSources" :key="source.id" :value="source.id">{{ source.title }}</option>
            </select>
          </div>
        </div>
        <div class="toolbar" style="justify-content:flex-end">
          <AppButton @click="showBatchDialog = false">取消</AppButton>
          <AppButton type="primary" :loading="batchLoading" :disabled="batchSubmitDisabled" @click="submitBatch">确认执行</AppButton>
        </div>
      </div>
    </div>

    <div v-if="configTarget" class="modal-overlay" @click.self="closeConfig">
      <div class="modal-content config-modal-content">
        <div class="config-modal-header">
          <div class="config-modal-heading">
            <div class="config-modal-title">配置自动发货</div>
            <div class="config-modal-subtitle" :title="configTarget.goods.title">{{ configTarget.goods.title }}</div>
          </div>
          <button class="config-modal-close" type="button" aria-label="关闭" @click="closeConfig">×</button>
        </div>

        <div class="config-tabs config-modal-tabs">
          <button v-for="timing in configTimings" :key="timing.key" type="button" :class="['config-tab', { active: configTiming === timing.key }]" @click="switchTiming(timing.key)">
            {{ timing.label }}
          </button>
          <button v-if="isMultiSpecGoods || skuLoading" type="button" :class="['config-tab', { active: configTiming === 'skuRules' }]" @click="switchTiming('skuRules')">
            多规格配置
            <span v-if="isMultiSpecGoods" class="sku-count-badge">{{ skuList.length }}</span>
          </button>
        </div>

        <div class="config-modal-body">
          <!-- SKU 多规格配置面板 -->
          <div v-if="configTiming === 'skuRules'" class="sku-config-panel">
            <div v-if="skuLoading" class="sku-loading">正在加载规格信息...</div>
            <div v-else-if="skuError" class="global-notice error" style="margin:0 0 12px">{{ skuError }}</div>
            <div v-else-if="!isMultiSpecGoods" class="sku-empty">
              该商品未检测到多规格 SKU，无需进行 SKU 维度配置。<br>
              可直接使用上方的「付款后发货 / 确认收货后赠送 / 好评后赠送」进行商品通用配置。
            </div>
            <div v-else>
              <div class="sku-config-hint">
                <div class="sku-config-hint-text">
                  <b>多规格发货说明：</b>为每个 SKU 独立配置发货规则。付款触发后，系统会反查订单 SKU 并按 SKU 精确匹配发货规则；未匹配到的 SKU 自动回退到商品通用配置。
                </div>
                <div class="sku-config-actions">
                  <AppButton class="sku-btn-small" @click="applyToAllSkus('payDelivery')">应用通用付款配置</AppButton>
                  <AppButton class="sku-btn-small" type="primary" :loading="skuSaving" :disabled="!isMultiSpecGoods" @click="saveSkuRules">保存 SKU 规则</AppButton>
                </div>
              </div>
              <div v-if="skuSuccess" class="global-notice success" style="margin:0 0 12px">{{ skuSuccess }}</div>

              <div v-for="(rule, idx) in skuRules" :key="rule.skuId || idx" class="sku-rule-card">
                <div class="sku-rule-header">
                  <div class="sku-rule-title">
                    <span class="sku-rule-index">#{{ idx + 1 }}</span>
                    <span class="sku-rule-property" :title="rule.propertyText">{{ rule.propertyText || rule.propertyKey || `SKU: ${rule.skuId}` }}</span>
                  </div>
                  <span class="sku-rule-id">SKU ID: {{ rule.skuId }}</span>
                </div>

                <div class="sku-timing-grid">
                  <div v-for="timing in configTimings" :key="timing.key" class="sku-timing-cell">
                    <div class="sku-timing-header">
                      <label class="checkbox-label">
                        <input type="checkbox" :checked="rule[timing.key].enabled === 1" @change="toggleSkuTiming(rule, timing.key, $event.target.checked)" />
                        {{ timing.label }}
                      </label>
                    </div>
                    <div v-if="rule[timing.key].enabled === 1" class="sku-timing-body">
                      <div class="form-row" style="margin-bottom:6px">
                        <label>模式</label>
                        <select v-model="rule[timing.key].mode" class="input" style="max-width:160px">
                          <option value="text">文本发货</option>
                          <option value="card">卡密发货</option>
                        </select>
                      </div>
                      <div v-if="rule[timing.key].mode === 'text'" class="form-row" style="margin-bottom:6px">
                        <label>关联货源</label>
                        <select v-model="rule[timing.key].sourceId" class="input" style="max-width:240px" :disabled="!sourcesAvailable">
                          <option value="">手写内容</option>
                          <option v-for="source in textSources" :key="source.id" :value="source.id">{{ source.title }}</option>
                        </select>
                      </div>
                      <div v-if="rule[timing.key].mode === 'card'" class="form-row" style="margin-bottom:6px">
                        <label>卡密组</label>
                        <select v-model="rule[timing.key].cardGroupId" class="input" style="max-width:240px" :disabled="!cardGroupsAvailable">
                          <option value="">请选择</option>
                          <option v-for="group in cardGroups" :key="group.id" :value="group.id">
                            {{ group.groupName }}（余 {{ group.remainCount ?? '—' }}）
                            <span v-if="group.skuPropertyKey"> · 专属:{{ group.skuPropertyKey }}</span>
                          </option>
                        </select>
                      </div>
                      <div v-if="rule[timing.key].mode === 'text'" class="form-row" style="margin-bottom:0">
                        <label>发货内容</label>
                        <textarea v-model="rule[timing.key].content" rows="2" placeholder="买家将收到的发货内容"></textarea>
                      </div>
                      <div v-else class="form-row" style="margin-bottom:0">
                        <label>卡密模板</label>
                        <textarea v-model="rule[timing.key].cardTemplate" rows="2" placeholder="例如：您的卡密为：{卡密}"></textarea>
                      </div>
                    </div>
                    <div v-else class="sku-timing-body-disabled">
                      未启用，将回退到商品通用「{{ timing.label }}」配置
                    </div>
                  </div>
                </div>
              </div>

              <div class="sku-config-footer">
                <AppButton type="primary" :loading="skuSaving" :disabled="!isMultiSpecGoods" @click="saveSkuRules">保存 SKU 规则</AppButton>
              </div>
            </div>
          </div>

          <!-- 商品通用配置表单（原有逻辑） -->
          <template v-else>
          <div class="config-modal-hint">
            当前配置时机：<b>{{ currentTimingLabel }}</b>
            <span v-if="isMultiSpecGoods" class="config-modal-hint-extra">
              · 此为<b>商品通用配置</b>，未匹配到 SKU 规则时生效。如需按规格差异化发货，请切到「多规格配置」标签。
            </span>
          </div>

          <div class="form-grid">
            <div class="form-row">
              <label>启用{{ currentTimingLabel }}</label>
              <select v-model.number="configForm.enabled" class="input" style="max-width:200px">
                <option :value="1">启用</option>
                <option :value="0">停用</option>
              </select>
            </div>

            <div class="form-row">
              <label>发货模式</label>
              <select v-model="configForm.mode" class="input" style="max-width:220px">
                <option value="text">文本发货</option>
                <option value="card">卡密发货</option>
              </select>
            </div>

            <div v-if="configForm.mode === 'text'" class="form-row">
              <label>关联货源库</label>
              <div class="toolbar" style="justify-content:flex-start">
                <select v-model="configForm.sourceId" class="input" style="max-width:320px" :disabled="!sourcesAvailable">
                  <option value="">不使用货源库，直接手写内容</option>
                  <option v-for="source in textSources" :key="source.id" :value="source.id">{{ source.title }}</option>
                </select>
                <AppButton @click="goSourceLibrary">管理货源库</AppButton>
              </div>
              <div v-if="configForm.sourceId" class="subtle">
                已关联货源：{{ sourceTitle(configForm.sourceId) }}
              </div>
            </div>

            <div v-if="configForm.mode === 'card'" class="form-row">
              <label>绑定卡密分组</label>
              <select v-model="configForm.cardGroupId" class="input" style="max-width:320px" :disabled="!cardGroupsAvailable">
                <option value="">请选择</option>
                <option v-for="group in cardGroups" :key="group.id" :value="group.id">{{ group.groupName }}（余 {{ group.remainCount ?? '—' }}）</option>
              </select>
            </div>

            <div v-if="configForm.mode === 'card'" class="form-row">
              <label>卡密模板</label>
              <textarea v-model="configForm.cardTemplate" rows="3" placeholder="例如：您的卡密为：{卡密}"></textarea>
            </div>

            <div class="form-row">
              <label>消息头部</label>
              <textarea v-model="configForm.header" rows="2" placeholder="可选，发货正文前的说明"></textarea>
            </div>

            <div class="form-row">
              <div class="content-label-row">
                <label v-if="configForm.mode === 'text'">正文内容</label>
                <label v-else>消息底部</label>
                <button
                  v-if="configForm.mode === 'text'"
                  type="button"
                  class="insert-source-btn"
                  :disabled="!sourcesAvailable"
                  @click="openSourceDrawer('content')"
                >+ 插入货源</button>
                <button
                  v-if="configForm.mode === 'text'"
                  type="button"
                  class="insert-source-btn ghost"
                  @click="insertSegmentPlaceholder"
                >+ 插入 {分段}</button>
              </div>
              <textarea
                v-if="configForm.mode === 'text'"
                ref="contentTextareaRef"
                v-model="configForm.content"
                rows="5"
                :placeholder="configForm.sourceId ? '已引用货源库正文，可继续补充或覆盖。可点击上方「插入货源」将 {货源:ID} 占位符插入到正文，发货时会自动替换为对应货源的最新内容' : '请输入买家将收到的发货内容。可点击上方「插入货源」插入货源占位符'"
              ></textarea>
              <textarea
                v-else
                v-model="configForm.footer"
                rows="2"
                placeholder="可选，卡密内容后的补充说明"
              ></textarea>
            </div>

            <div class="form-row">
              <label>分段发送</label>
              <label class="checkbox-label">
                <input v-model="configForm.segmentSend" type="checkbox" />
                使用 `{分段}` 拆成多条消息发送
              </label>
            </div>

            <div class="form-row">
              <label>失败重试次数</label>
              <input v-model.number="configForm.retryCount" type="number" min="0" max="10" class="input" style="max-width:120px" />
            </div>

            <div class="form-row">
              <label>库存预警阈值</label>
              <input v-model.number="configForm.alertThreshold" type="number" min="0" class="input" style="max-width:120px" />
            </div>

            <div class="form-row">
              <label>库存不足自动停用</label>
              <label class="checkbox-label">
                <input v-model="configForm.autoDisableOnLowStock" type="checkbox" />
                自动停用
              </label>
            </div>
          </div>
        </template>
        </div>

        <div class="config-modal-footer">
          <AppButton @click="closeConfig">取消</AppButton>
          <AppButton v-if="configTiming !== 'skuRules'" type="primary" :loading="configSaving" :disabled="configSaveDisabled" @click="saveConfig">保存配置</AppButton>
          <AppButton v-else type="primary" :loading="skuSaving" :disabled="!isMultiSpecGoods" @click="saveSkuRules">保存 SKU 规则</AppButton>
        </div>
      </div>
    </div>

    <div v-if="sourceDrawer.visible" class="source-drawer-overlay" @click.self="closeSourceDrawer">
      <div class="source-drawer">
        <div class="source-drawer-header">
          <div class="source-drawer-title">选择货源插入</div>
          <button type="button" class="source-drawer-close" aria-label="关闭" @click="closeSourceDrawer">×</button>
        </div>
        <div class="source-drawer-tip">
          点击任意货源将把 <code>&#123;货源:ID&#125;</code> 占位符插入到正文光标位置；发货时会自动替换为对应货源的最新内容（商城货源随商品更新同步）。
        </div>
        <div class="source-drawer-body">
          <div v-if="!sourcesAvailable" class="source-drawer-empty">货源库加载失败，无法插入。</div>
          <div v-else-if="textSources.length === 0" class="source-drawer-empty">暂无货源，请先到货源库添加或购买。</div>
          <template v-else>
            <button
              v-for="source in textSources"
              :key="source.id"
              type="button"
              class="source-drawer-item"
              @click="insertSourceToContent(source)"
            >
              <div class="source-drawer-item-main">
                <div class="source-drawer-item-title">
                  <span class="source-drawer-item-name">{{ source.title || '未命名货源' }}</span>
                  <Badge v-if="source.fromMall" type="purple">商城</Badge>
                  <Badge v-else-if="source.deliveryMode === 'card'" type="blue">卡密</Badge>
                  <Badge v-else>文本</Badge>
                </div>
                <div class="source-drawer-item-meta">
                  <span>ID: {{ source.id }}</span>
                  <span v-if="source.fromMall">货源内容实时同步</span>
                  <span v-else>库存：{{ source.stockLabel || '—' }}</span>
                </div>
              </div>
              <span class="source-drawer-item-insert">插入</span>
            </button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import BaseTable from '../components/BaseTable.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import { confirmAction } from '../utils/confirmAction.js'
import { guardFeatureAction } from '../composables/featureGuard.js'
import { getLiteAccounts } from '../api/accounts.js'
import { getGoods } from '../api/goods.js'
import { getCards } from '../api/cards.js'
import {
  batchDeleteDeliveryRules,
  batchGetGoodsDeliveryConfigs,
  batchSetDeliveryRules,
  getDeliverySources,
  getDeliveryStats,
  getGoodsDeliveryConfig,
  getGoodsSkus,
  getGoodsSkuRules,
  saveGoodsDeliveryConfig,
  saveGoodsSkuRules,
  scanPendingOrders as scanApi
} from '../api/autoDelivery.js'
import { accountName } from '../utils/format.js'
import { recordsOfOrThrow } from '../utils/apiData.js'

const emit = defineEmits(['navigate'])
const accounts = ref([])
const cardGroups = ref([])
const textSources = ref([])
const allGoods = ref([])
const error = ref('')
const success = ref('')
const statsAvailable = ref(false)
const sourcesAvailable = ref(false)
const goodsAvailable = ref(false)
const accountsAvailable = ref(false)
const cardGroupsAvailable = ref(false)
const statsError = ref('')
const sourcesError = ref('')
const dependenciesError = ref('')
const configSaving = ref(false)
const showBatchDialog = ref(false)
const batchLoading = ref(false)
const current = ref(1)
const pageSize = ref(20)

const stats = reactive({
  todaySuccess: null,
  todayFail: null,
  pendingOrders: null,
  lowStockGoods: null,
  enabledGoods: null
})

const query = reactive({
  accountId: '',
  keyword: '',
  deliveryType: '',
  configStatus: '',
  goodsStatus: ''
})

const configTarget = ref(null)
const configTiming = ref('payDelivery')
const configTimings = [
  { key: 'payDelivery', label: '付款后发货' },
  { key: 'confirmDelivery', label: '确认收货后赠送' },
  { key: 'reviewDelivery', label: '好评后赠送' }
]

// 多规格 SKU 配置状态
const skuList = ref([])          // 商品 SKU 列表（从 xianyu_goods_sku 表）
const skuRules = ref([])         // 已保存的 SKU 发货规则
const skuLoading = ref(false)
const skuSaving = ref(false)
const skuError = ref('')
const skuSuccess = ref('')
const isMultiSpecGoods = computed(() => Array.isArray(skuList.value) && skuList.value.length > 0)

const configForm = reactive({
  enabled: 1,
  mode: 'text',
  sourceId: '',
  cardGroupId: '',
  sourceTitle: '',
  cardTemplate: '',
  header: '',
  content: '',
  footer: '',
  segmentSend: false,
  retryCount: 3,
  alertThreshold: 5,
  autoDisableOnLowStock: false
})

const batchForm = reactive({
  action: 'payDelivery',
  enabled: 1,
  mode: '',
  cardGroupId: '',
  sourceId: ''
})

const contentTextareaRef = ref(null)
const sourceDrawer = reactive({
  visible: false,
  target: null
})

const columns = [
  { key: 'goodsInfo', title: '商品信息' },
  { key: 'category', title: '分类' },
  { key: 'account', title: '所属账号' },
  { key: 'payDelivery', title: '付款后发货' },
  { key: 'confirmDelivery', title: '确认收货后赠送' },
  { key: 'reviewDelivery', title: '好评后赠送' },
  { key: 'op', title: '操作' }
]

const currentTimingLabel = computed(() => configTimings.find(item => item.key === configTiming.value)?.label || '')
const hasUnavailableGoods = computed(() => filteredGoods.value.some(goods => goods._configUnavailable))
const configSaveDisabled = computed(() => (
  !goodsAvailable.value
  || !!configTarget.value?.goods?._configUnavailable
  || (configForm.mode === 'card' && !cardGroupsAvailable.value)
))
const batchSubmitDisabled = computed(() => (
  !goodsAvailable.value
  || hasUnavailableGoods.value
  || filteredGoods.value.length === 0
  || (batchForm.mode === 'card' && !cardGroupsAvailable.value)
))

const filteredGoods = computed(() => {
  return allGoods.value.filter(goods => {
    if (query.accountId && String(goods.accountId) !== String(query.accountId)) return false
    if (query.keyword) {
      const keyword = query.keyword.toLowerCase()
      if (!String(goods.title || '').toLowerCase().includes(keyword) && !String(goods.id).includes(keyword)) return false
    }
    if (query.goodsStatus !== '' && String(goods.status) !== String(query.goodsStatus)) return false

    if (goods._configUnavailable && (query.deliveryType || query.configStatus)) return false
    const cfg = goods._config || {}
    const timings = [cfg.payDelivery, cfg.confirmDelivery, cfg.reviewDelivery].filter(Boolean)
    const hasText = timings.some(item => item.mode === 'text')
    const hasCard = timings.some(item => item.mode === 'card')

    if (query.deliveryType === 'text' && !hasText) return false
    if (query.deliveryType === 'card' && !hasCard) return false
    if (query.deliveryType === 'none' && timings.length > 0) return false

    if (query.configStatus === 'configured' && timings.length === 0) return false
    if (query.configStatus === 'unconfigured' && timings.length > 0) return false

    return true
  })
})

const tableRows = computed(() => {
  const start = (current.value - 1) * pageSize.value
  return filteredGoods.value.slice(start, start + pageSize.value).map(goods => ({
    ...goods,
    _config: goods._config || {},
    _account: accounts.value.find(account => String(account.id) === String(goods.accountId))
  }))
})

watch(() => configForm.sourceId, value => {
  const source = textSources.value.find(item => String(item.id) === String(value))
  if (source) {
    configForm.sourceTitle = source.title
    if (!configForm.content || configForm.content === configForm._lastSourceContent) {
      configForm.content = source.content || ''
      configForm._lastSourceContent = source.content || ''
    }
  } else {
    configForm.sourceTitle = ''
  }
})

function goPage(page) {
  current.value = page
}

function sourceTitle(id) {
  return textSources.value.find(item => String(item.id) === String(id))?.title || ''
}

function statValue(value) {
  return value === null || value === undefined ? '—' : value
}

function statusLabel(cfg, unavailable = false) {
  if (unavailable) return '配置不可用'
  if (!cfg) return '未配置'
  if (cfg.mode === 'api') return 'API 模式暂不可用'
  if (Number(cfg.enabled) === 0) return '已停用'
  if (cfg.sourceId) return `货源：${cfg.sourceTitle || sourceTitle(cfg.sourceId) || '已关联'}`
  return cfg.mode === 'card' ? '卡密发货' : '文本发货'
}

function statusClass(cfg, unavailable = false) {
  if (unavailable) return 'status-unavailable'
  if (!cfg) return 'status-none'
  if (cfg.mode === 'api') return 'status-unavailable'
  if (Number(cfg.enabled) === 0) return 'status-disabled'
  return 'status-enabled'
}

function statusDotClass(cfg, unavailable = false) {
  if (unavailable) return 'dot-red'
  if (!cfg) return 'dot-gray'
  if (Number(cfg.enabled) === 0) return 'dot-gray'
  return 'dot-green'
}

async function loadStats() {
  statsAvailable.value = false
  statsError.value = ''
  try {
    const res = await getDeliveryStats()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('发货统计响应格式异常')
    }
    const metricKeys = ['todaySuccess', 'todayFail', 'pendingOrders', 'lowStockGoods', 'enabledGoods']
    if (metricKeys.some(key => typeof data[key] !== 'number' || !Number.isFinite(data[key]) || data[key] < 0)) {
      throw new Error('发货统计响应缺少有效指标')
    }
    Object.assign(stats, {
      todaySuccess: data.todaySuccess,
      todayFail: data.todayFail,
      pendingOrders: data.pendingOrders,
      lowStockGoods: data.lowStockGoods,
      enabledGoods: data.enabledGoods
    })
    statsAvailable.value = true
  } catch (loadError) {
    Object.assign(stats, { todaySuccess: null, todayFail: null, pendingOrders: null, lowStockGoods: null, enabledGoods: null })
    statsError.value = `${loadError?.message || '发货统计加载失败'}，相关指标显示为“—”。`
  }
}

async function loadSources() {
  sourcesAvailable.value = false
  sourcesError.value = ''
  try {
    const res = await getDeliverySources({ current: 1, size: 200 })
    textSources.value = recordsOfOrThrow(res?.data, '货源库响应格式异常')
    sourcesAvailable.value = true
  } catch (loadError) {
    textSources.value = []
    sourcesError.value = `${loadError?.message || '货源库加载失败'}，当前不能选择或变更关联货源。`
  }
}

async function loadAll() {
  error.value = ''
  dependenciesError.value = ''
  accountsAvailable.value = false
  cardGroupsAvailable.value = false
  const dependencyErrors = []
  const [accountResult, cardResult] = await Promise.allSettled([
    getLiteAccounts(),
    getCards({ size: 200 })
  ])
  if (accountResult.status === 'fulfilled') {
    try {
      accounts.value = recordsOfOrThrow(accountResult.value?.data, '账号列表响应格式异常')
      accountsAvailable.value = true
    } catch (loadError) {
      accounts.value = []
      query.accountId = ''
      dependencyErrors.push(loadError?.message || '账号列表加载失败')
    }
  } else {
    accounts.value = []
    query.accountId = ''
    dependencyErrors.push(accountResult.reason?.message || '账号列表加载失败')
  }
  if (cardResult.status === 'fulfilled') {
    try {
      cardGroups.value = recordsOfOrThrow(cardResult.value?.data, '卡密分组响应格式异常')
      cardGroupsAvailable.value = true
    } catch (loadError) {
      cardGroups.value = []
      dependencyErrors.push(loadError?.message || '卡密分组加载失败')
    }
  } else {
    cardGroups.value = []
    dependencyErrors.push(cardResult.reason?.message || '卡密分组加载失败')
  }
  if (dependencyErrors.length) {
    dependenciesError.value = `${dependencyErrors.join('；')}。相关筛选或卡密配置已停用。`
  }
  await Promise.all([loadSources(), loadGoods(), loadStats()])
}

async function loadGoods() {
  goodsAvailable.value = false
  try {
    const params = { size: 200 }
    if (query.accountId) params.accountId = query.accountId
    const res = await getGoods(params)
    current.value = 1
    const list = recordsOfOrThrow(res?.data, '商品列表响应格式异常')

    // 优先用批量接口一次拉取所有商品配置，把 200 个请求压成 1 个；失败时降级到逐个请求。
    let configsById = null
    try {
      const batchRes = await batchGetGoodsDeliveryConfigs(list.map(goods => goods.id))
      const data = batchRes?.data
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        configsById = data
      }
    } catch (batchError) {
      // 批量接口不可用时降级到逐个请求（保持原有兼容性）
      console.warn('[AutoDelivery] 批量读取配置失败，降级到逐个请求', batchError?.message || batchError)
    }

    if (configsById) {
      allGoods.value = list.map(goods => {
        const config = configsById[String(goods.id)]
        if (!config || typeof config !== 'object' || Array.isArray(config)) {
          return { ...goods, _config: {} }
        }
        const validationError = validateGoodsConfig(config)
        if (validationError) {
          return { ...goods, _config: {}, _configUnavailable: true, _configError: validationError }
        }
        return { ...goods, _config: config }
      })
      goodsAvailable.value = true
      return
    }

    // Fallback：逐个请求（仅在批量接口不可用时触发）
    const withConfig = await Promise.all(list.map(async goods => {
      try {
        const configRes = await getGoodsDeliveryConfig(goods.id)
        const config = configRes?.data
        if (!config || typeof config !== 'object' || Array.isArray(config)) {
          throw new Error('商品发货配置响应格式异常')
        }
        const validationError = validateGoodsConfig(config)
        if (validationError) throw new Error(validationError)
        return { ...goods, _config: config }
      } catch (configError) {
        return { ...goods, _config: {}, _configUnavailable: true, _configError: configError?.message || '配置读取失败' }
      }
    }))
    allGoods.value = withConfig
    goodsAvailable.value = true
  } catch (e) {
    allGoods.value = []
    error.value = e.message || '商品加载失败'
  }
}

function validateGoodsConfig(config) {
  for (const timing of ['payDelivery', 'confirmDelivery', 'reviewDelivery']) {
    const timingConfig = config[timing]
    if (timingConfig == null) continue
    const enabled = timingConfig?.enabled
    if (!timingConfig || typeof timingConfig !== 'object' || Array.isArray(timingConfig)
      || ![true, false, 0, 1].includes(enabled)
      || !['text', 'card', 'custom', 'api'].includes(timingConfig.mode)) {
      return `${timing} 发货配置响应格式异常`
    }
  }
  return null
}

function applyFilter() {
  current.value = 1
}

function resetFilter() {
  Object.assign(query, {
    accountId: '',
    keyword: '',
    deliveryType: '',
    configStatus: '',
    goodsStatus: ''
  })
  current.value = 1
}

function fillConfigForm(config = {}) {
  const legacyApiMode = config.mode === 'api'
  Object.assign(configForm, {
    enabled: legacyApiMode ? 0 : (config.enabled !== undefined ? Number(config.enabled) : 1),
    mode: ['text', 'card'].includes(config.mode) ? config.mode : 'text',
    sourceId: config.sourceId || '',
    sourceTitle: config.sourceTitle || '',
    cardGroupId: config.cardGroupId || '',
    cardTemplate: config.cardTemplate || '',
    header: config.header || '',
    content: config.content || '',
    footer: config.footer || '',
    segmentSend: !!config.segmentSend,
    retryCount: config.retryCount ?? 3,
    alertThreshold: config.alertThreshold ?? 5,
    autoDisableOnLowStock: !!config.autoDisableOnLowStock,
    _lastSourceContent: config.content || ''
  })
}

function openConfig(goods, timing) {
  if (!goodsAvailable.value) return
  if (goods?._configUnavailable) {
    error.value = `${goods.title || '该商品'}的自动发货配置读取失败，未确认现有配置前禁止编辑。请刷新后重试。`
    return
  }
  configTarget.value = { goods }
  configTiming.value = timing || 'payDelivery'
  const timingConfig = goods._config?.[configTiming.value] || {}
  if (timingConfig.mode === 'api') {
    error.value = '该规则使用的是已停用的 API 发货模式；保存时请改用文本或卡密发货。'
  }
  fillConfigForm(timingConfig)
  // 异步加载 SKU 列表与已保存的 SKU 规则（不阻塞主配置表单）
  loadGoodsSkuData(goods.id)
}

function openBatchDialog() {
  if (!goodsAvailable.value || hasUnavailableGoods.value || filteredGoods.value.length === 0) return
  showBatchDialog.value = true
}

function switchTiming(timing) {
  configTiming.value = timing
  if (timing === 'skuRules') return  // SKU 配置 tab 不复用主表单
  fillConfigForm(configTarget.value?.goods?._config?.[timing] || {})
}

function closeConfig() {
  configTarget.value = null
  // 清理 SKU 状态
  skuList.value = []
  skuRules.value = []
  skuError.value = ''
  skuSuccess.value = ''
}

// 加载商品 SKU 列表 + 已保存的 SKU 发货规则
async function loadGoodsSkuData(goodsId) {
  skuList.value = []
  skuRules.value = []
  skuError.value = ''
  skuLoading.value = true
  try {
    const [skuRes, rulesRes] = await Promise.all([
      getGoodsSkus(goodsId),
      getGoodsSkuRules(goodsId)
    ])
    const skus = skuRes?.data || []
    const rules = rulesRes?.data || []
    skuList.value = Array.isArray(skus) ? skus : []
    skuRules.value = Array.isArray(rules) ? mergeSkuRules(skus, rules) : []
  } catch (e) {
    // SKU 接口失败不影响主配置流程，仅记录告警
    skuError.value = e?.message || 'SKU 信息加载失败，多规格配置暂不可用'
    skuList.value = []
    skuRules.value = []
  } finally {
    skuLoading.value = false
  }
}

// 将 SKU 列表与已保存的 SKU 规则合并，确保每个 SKU 都有一条可编辑的规则
function mergeSkuRules(skus, savedRules) {
  const ruleMap = new Map()
  for (const rule of savedRules) {
    if (rule && rule.skuId) ruleMap.set(String(rule.skuId), rule)
  }
  return skus.map(sku => {
    const saved = ruleMap.get(String(sku.skuId)) || {}
    return {
      skuId: sku.skuId,
      propertyKey: sku.propertyKey || saved.propertyKey || '',
      propertyText: sku.propertyText || saved.propertyText || '',
      payDelivery: normalizeSkuTimingConfig(saved.payDelivery),
      confirmDelivery: normalizeSkuTimingConfig(saved.confirmDelivery),
      reviewDelivery: normalizeSkuTimingConfig(saved.reviewDelivery)
    }
  })
}

function normalizeSkuTimingConfig(raw) {
  const cfg = raw && typeof raw === 'object' ? raw : {}
  return {
    enabled: cfg.enabled === 1 || cfg.enabled === true ? 1 : 0,
    mode: ['text', 'card'].includes(cfg.mode) ? cfg.mode : 'text',
    sourceId: cfg.sourceId || '',
    sourceTitle: cfg.sourceTitle || '',
    cardGroupId: cfg.cardGroupId || '',
    cardTemplate: cfg.cardTemplate || '',
    header: cfg.header || '',
    content: cfg.content || '',
    footer: cfg.footer || ''
  }
}

// 切换 SKU 单个 timing 的启用状态时，重置为默认值
function toggleSkuTiming(rule, timing, enabled) {
  const cfg = rule[timing]
  cfg.enabled = enabled ? 1 : 0
  if (!enabled) return
  // 启用时若未配置过，给默认值
  if (!cfg.mode) cfg.mode = 'text'
}

// 批量应用：将商品通用配置应用到所有 SKU 的指定 timing
function applyToAllSkus(timing) {
  if (!isMultiSpecGoods.value) return
  const sourceConfig = configTarget.value?.goods?._config?.[timing] || {}
  const template = normalizeSkuTimingConfig(sourceConfig)
  // 启用状态跟随通用配置（通用配置未启用则不勾选，但模板字段仍填充便于快速启用）
  template.enabled = sourceConfig.enabled === 1 || sourceConfig.enabled === true ? 1 : 0
  for (const rule of skuRules.value) {
    rule[timing] = JSON.parse(JSON.stringify(template))
  }
  skuSuccess.value = `已将「${currentTimingLabelFor(timing)}」的通用配置应用到全部 ${skuRules.value.length} 个 SKU`
  setTimeout(() => { skuSuccess.value = '' }, 3000)
}

function currentTimingLabelFor(timing) {
  return configTimings.find(item => item.key === timing)?.label || timing
}

// 保存 SKU 规则
async function saveSkuRules() {
  if (!configTarget.value || !isMultiSpecGoods.value) return
  skuSaving.value = true
  skuError.value = ''
  skuSuccess.value = ''
  try {
    // 仅提交启用了至少一个 timing 的 SKU 规则；未启用的 SKU 不写入（让运行时回退商品通用配置）
    const payload = skuRules.value
      .filter(rule => ['payDelivery', 'confirmDelivery', 'reviewDelivery']
        .some(t => rule[t]?.enabled === 1))
      .map(rule => ({
        skuId: rule.skuId,
        propertyKey: rule.propertyKey,
        propertyText: rule.propertyText,
        payDelivery: cleanSkuTimingForSave(rule.payDelivery),
        confirmDelivery: cleanSkuTimingForSave(rule.confirmDelivery),
        reviewDelivery: cleanSkuTimingForSave(rule.reviewDelivery)
      }))
    await saveGoodsSkuRules(configTarget.value.goods.id, payload)
    skuSuccess.value = `已保存 ${payload.length} 个 SKU 的发货规则`
    await loadGoodsSkuData(configTarget.value.goods.id)
  } catch (e) {
    skuError.value = e?.message || 'SKU 规则保存失败'
  } finally {
    skuSaving.value = false
  }
}

function cleanSkuTimingForSave(cfg) {
  return {
    enabled: cfg.enabled === 1 ? 1 : 0,
    mode: cfg.mode || 'text',
    sourceId: cfg.mode === 'text' && cfg.sourceId ? Number(cfg.sourceId) : null,
    sourceTitle: cfg.mode === 'text' ? (cfg.sourceTitle || '') : '',
    cardGroupId: cfg.mode === 'card' && cfg.cardGroupId ? Number(cfg.cardGroupId) : null,
    cardTemplate: cfg.cardTemplate || '',
    header: cfg.header || '',
    content: cfg.content || '',
    footer: cfg.footer || ''
  }
}

async function saveConfig() {
  if (configSaveDisabled.value) return
  if (!configTarget.value) return
  configSaving.value = true
  error.value = ''
  success.value = ''
  try {
    await saveGoodsDeliveryConfig(configTarget.value.goods.id, {
      timing: configTiming.value,
      enabled: configForm.enabled,
      mode: configForm.mode,
      sourceId: configForm.mode === 'text' && configForm.sourceId ? Number(configForm.sourceId) : null,
      sourceTitle: configForm.mode === 'text' ? configForm.sourceTitle : '',
      cardGroupId: configForm.mode === 'card' && configForm.cardGroupId ? Number(configForm.cardGroupId) : null,
      cardTemplate: configForm.cardTemplate,
      header: configForm.header,
      content: configForm.content,
      footer: configForm.footer,
      segmentSend: configForm.segmentSend,
      retryCount: configForm.retryCount,
      alertThreshold: configForm.alertThreshold,
      autoDisableOnLowStock: configForm.autoDisableOnLowStock
    })
    success.value = '配置已保存'
    await loadGoods()
    closeConfig()
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    configSaving.value = false
  }
}

async function removeConfig(goods) {
  if (!goodsAvailable.value || goods?._configUnavailable) return
  if (!await confirmAction({
    title: '确认禁用该商品自动发货？',
    description: '会将三个发货时机全部停用，但保留已填写内容。',
    dangerous: true,
    confirmText: '禁用'
  })) return

  try {
    for (const timing of ['payDelivery', 'confirmDelivery', 'reviewDelivery']) {
      await saveGoodsDeliveryConfig(goods.id, { timing, enabled: 0, mode: 'text', sourceId: null, sourceTitle: '' })
    }
    success.value = '已禁用该商品发货配置'
    await loadGoods()
  } catch (e) {
    error.value = e.message || '禁用失败'
  }
}

async function submitBatch() {
  if (!await guardFeatureAction()) return
  if (batchSubmitDisabled.value) return
  batchLoading.value = true
  try {
    const goodsIds = filteredGoods.value.map(goods => goods.id)
    await batchSetDeliveryRules({
      goodsIds,
      timing: batchForm.action,
      enabled: batchForm.enabled,
      mode: batchForm.mode || undefined,
      cardGroupId: batchForm.mode === 'card' && batchForm.cardGroupId ? Number(batchForm.cardGroupId) : null,
      sourceId: batchForm.mode === 'text' && batchForm.sourceId ? Number(batchForm.sourceId) : null,
      sourceTitle: batchForm.mode === 'text' ? sourceTitle(batchForm.sourceId) : ''
    })
    success.value = `已批量更新 ${goodsIds.length} 个商品`
    showBatchDialog.value = false
    await loadGoods()
  } catch (e) {
    error.value = e.message || '批量配置失败'
  } finally {
    batchLoading.value = false
  }
}

async function batchDelete() {
  if (!await guardFeatureAction()) return
  if (!goodsAvailable.value || hasUnavailableGoods.value || filteredGoods.value.length === 0) return
  if (!await confirmAction({
    title: '确认批量删除发货配置？',
    description: `将删除当前筛选出的 ${filteredGoods.value.length} 个商品配置。`,
    dangerous: true,
    confirmText: '删除'
  })) return
  try {
    await batchDeleteDeliveryRules({ goodsIds: filteredGoods.value.map(goods => goods.id) })
    success.value = '批量删除完成'
    await loadGoods()
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

async function scanPendingOrders() {
  try {
    const res = await scanApi()
    const data = res?.data
    const fields = ['scanned', 'executed', 'failed']
    if (!data || typeof data !== 'object' || Array.isArray(data)
      || fields.some(key => !Number.isSafeInteger(data[key]) || data[key] < 0)) {
      throw new Error('待发货扫描响应格式异常')
    }
    success.value = data.failed > 0
      ? `扫描完成：创建 ${data.scanned} 个任务，成功 ${data.executed} 个，失败 ${data.failed} 个；请前往发货记录处理失败项。`
      : `扫描完成：创建 ${data.scanned} 个任务，成功发货 ${data.executed} 个。`
  } catch (e) {
    error.value = e.message || '扫描失败'
  }
}

function goSourceLibrary() {
  emit('navigate', 'delivery-source-library')
}

function openSourceDrawer(target) {
  if (!sourcesAvailable.value || textSources.value.length === 0) {
    error.value = '当前货源库不可用，无法插入货源占位符。'
    return
  }
  sourceDrawer.target = target || 'content'
  sourceDrawer.visible = true
}

function closeSourceDrawer() {
  sourceDrawer.visible = false
  sourceDrawer.target = null
}

function insertSegmentPlaceholder() {
  insertAtCursor('{分段}')
}

function insertSourceToContent(source) {
  if (!source?.id) return
  insertAtCursor(`{货源:${source.id}}`)
  closeSourceDrawer()
}

function insertAtCursor(text) {
  const textarea = contentTextareaRef.value
  if (!textarea || typeof text !== 'string' || !text) return
  const start = textarea.selectionStart ?? configForm.content.length
  const end = textarea.selectionEnd ?? configForm.content.length
  const before = (configForm.content || '').slice(0, start)
  const after = (configForm.content || '').slice(end)
  configForm.content = `${before}${text}${after}`
  nextTick(() => {
    const newPosition = start + text.length
    textarea.focus?.()
    try {
      textarea.setSelectionRange?.(newPosition, newPosition)
    } catch (_) {
      // setSelectionRange not available in some envs; ignore.
    }
  })
}

function onHeaderAction(event) {
  if (event.detail === 'delivery-batch') openBatchDialog()
  if (event.detail === 'delivery-refresh') loadAll()
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  loadAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
/* ── 页面容器 ── */
.ad-page {
  width: 100%;
}

/* ── 页面头部 ── */
.ad-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 0 2px;
}
.ad-title {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  color: #15213d;
  letter-spacing: -0.3px;
}
.ad-subtitle {
  margin: 6px 0 0;
  font-size: 14px;
  color: #7a879e;
}
.ad-header-actions {
  display: flex;
  gap: 10px;
}
.ad-header-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border: 1px solid #dbe4f2;
  border-radius: 10px;
  background: #fff;
  color: #526079;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .18s;
}
.ad-header-btn:hover {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f6ff;
}
.ad-header-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 12px rgba(13, 107, 255, .25);
}
.ad-header-btn-primary:hover {
  background: linear-gradient(135deg, #0b5fe6, #2563eb);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(13, 107, 255, .3);
}

/* ── 功能说明横幅 ── */
.ad-banner {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 22px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f2ff 50%, #f5f3ff 100%);
  border: 1px solid #d8e6ff;
  border-radius: 16px;
  margin-bottom: 18px;
}
.ad-banner-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  background: linear-gradient(135deg, #fff, #e8f2ff);
  border-radius: 14px;
  box-shadow: 0 4px 12px rgba(13, 107, 255, .10);
}
.ad-banner-content {
  flex: 1;
  min-width: 0;
}
.ad-banner-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a2742;
  margin-bottom: 4px;
}
.ad-banner-desc {
  margin: 0;
  font-size: 13px;
  color: #5b6b88;
  line-height: 1.6;
}
.ad-banner-stats {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}
.ad-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 14px;
  background: #fff;
  border-radius: 12px;
  min-width: 68px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, .06);
}
.ad-stat-item b {
  font-size: 22px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.ad-stat-item span {
  font-size: 11px;
  color: #8896ab;
  font-weight: 600;
  margin-top: 2px;
}
.ad-stat-green b { color: #16bf78; }
.ad-stat-red b { color: #ef4444; }
.ad-stat-orange b { color: #f59e0b; }
.ad-stat-blue b { color: #0d6bff; }
.ad-stat-indigo b { color: #6366f1; }
.ad-stat-gray b { color: #98a2b3; }

/* ── Toast 提示 ── */
.ad-toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 14px;
  font-size: 13px;
  font-weight: 500;
  animation: ad-toast-in .25s ease;
}
@keyframes ad-toast-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
.ad-toast-icon { font-size: 15px; flex-shrink: 0; }
.ad-toast-success { background: #ecfdf3; color: #067647; border: 1px solid #abefc6; }
.ad-toast-error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.ad-toast-warn { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }

/* ── 布局 ── */
.ad-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
}

/* ── 左侧筛选面板 ── */
.ad-sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ad-filter-card {
  background: #fff;
  border: 1px solid var(--line, #e8edf5);
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, .04);
  overflow: hidden;
}
.ad-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px 10px;
  font-size: 14px;
  font-weight: 700;
  color: #1a2742;
  border-bottom: 1px solid #f0f3f8;
}
.ad-card-header svg {
  color: #0d6bff;
}
.ad-filter-body {
  padding: 14px 16px 16px;
}
.ad-filter-item {
  margin-bottom: 12px;
}
.ad-filter-item:last-of-type {
  margin-bottom: 0;
}
.ad-filter-label {
  display: block;
  font-size: 12px;
  color: #6b7a90;
  margin-bottom: 6px;
  font-weight: 600;
}
.ad-input {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #e2e8f2;
  border-radius: 9px;
  font-size: 13px;
  color: #1a2742;
  background: #fff;
  transition: all .18s;
  box-sizing: border-box;
}
.ad-input:focus {
  outline: none;
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, .10);
}
select.ad-input {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7a90' stroke-width='2.5'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}
.ad-filter-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

/* ── 按钮 ── */
.ad-btn {
  height: 36px;
  padding: 0 16px;
  border: 1px solid #e2e8f2;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .18s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.ad-btn-block {
  width: 100%;
}
.ad-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 3px 10px rgba(13, 107, 255, .22);
}
.ad-btn-primary:hover {
  background: linear-gradient(135deg, #0b5fe6, #2563eb);
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(13, 107, 255, .3);
}
.ad-btn-ghost {
  background: #f8fafc;
  color: #526079;
}
.ad-btn-ghost:hover {
  background: #eef2f7;
  border-color: #c8d4e6;
  color: #1a2742;
}

/* ── 快捷操作按钮 ── */
.ad-quick-actions .ad-filter-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ad-action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: #4a5b75;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  text-align: left;
}
.ad-action-btn svg {
  color: #8896ab;
  transition: color .15s;
}
.ad-action-btn:hover:not(:disabled) {
  background: #f0f6ff;
  color: #0d6bff;
  border-color: #d0e2ff;
}
.ad-action-btn:hover:not(:disabled) svg {
  color: #0d6bff;
}
.ad-action-btn-danger:hover:not(:disabled) {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}
.ad-action-btn-danger:hover:not(:disabled) svg {
  color: #dc2626;
}
.ad-action-btn:disabled {
  opacity: .45;
  cursor: not-allowed;
}

/* ── 主内容区 ── */
.ad-main {
  min-width: 0;
}

/* ── 提示条 ── */
.ad-tip {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #eff6ff, #f5f3ff);
  border: 1px solid #dbeafe;
  border-radius: 12px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #4a5b75;
  line-height: 1.6;
}
.ad-tip-icon {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d6bff;
  color: #fff;
  border-radius: 50%;
  margin-top: 1px;
}
.ad-tip-content b {
  color: #1a2742;
  font-weight: 600;
}

/* ── 表格卡片 ── */
.ad-table-card {
  background: #fff;
  border: 1px solid var(--line, #e8edf5);
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, .04);
  overflow: hidden;
}
.ad-table-header {
  padding: 14px 18px;
  border-bottom: 1px solid #f0f3f8;
}
.ad-table-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ad-table-count {
  font-size: 14px;
  color: #4a5b75;
  font-weight: 600;
}
.ad-table-count b {
  color: #0d6bff;
  font-weight: 800;
  font-size: 16px;
  margin: 0 2px;
}
.ad-table-hint {
  font-size: 12px;
  color: #98a2b3;
  font-weight: 500;
}

/* ── 商品单元格 ── */
.goods-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
}
.goods-thumb {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  object-fit: cover;
  background: linear-gradient(135deg, #f0f4ff, #e8f0ff);
  border: 1px solid #e8edf5;
  flex-shrink: 0;
}
.goods-thumb.placeholder {
  background: linear-gradient(135deg, #f0f4ff, #e8f0ff);
}
.goods-detail {
  min-width: 0;
}
.goods-title {
  font-weight: 600;
  font-size: 13px;
  color: #1a2742;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.goods-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #8896ab;
  margin-top: 3px;
}
.goods-meta .price {
  color: #ef4444;
  font-weight: 700;
}

/* ── 发货状态徽章 ── */
.delivery-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  font-weight: 600;
  transition: all .15s;
}
.delivery-status:hover {
  transform: scale(1.02);
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.dot-green { background: #16bf78; box-shadow: 0 0 0 3px rgba(22, 191, 120, .15); }
.dot-gray { background: #c4cddb; }
.dot-red { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, .15); }
.status-enabled { background: #ecfdf3; color: #067647; }
.status-none { background: #f5f7fb; color: #667085; }
.status-disabled { background: #f5f7fb; color: #98a2b3; }
.status-unavailable { background: #fff1f2; color: #be123c; }

/* ── 操作链接 ── */
.link:disabled { opacity: .4; cursor: not-allowed; }

/* ── 配置弹窗 Tabs ── */
.config-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  background: #f5f7fb;
  border-radius: 12px;
  padding: 4px;
}
.config-tab {
  flex: 1;
  padding: 10px 14px;
  border: none;
  border-radius: 9px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #667085;
  transition: all .18s;
}
.config-tab:hover:not(.active) {
  color: #0d6bff;
  background: rgba(13, 107, 255, .05);
}
.config-tab.active {
  background: #fff;
  color: #0d6bff;
  box-shadow: 0 2px 8px rgba(13, 107, 255, .10);
}

/* ── 弹窗遮罩 ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, .45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: ad-overlay-in .2s ease;
}
@keyframes ad-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.modal-content {
  background: #fff;
  border-radius: 20px;
  padding: 28px;
  max-width: 560px;
  width: 90%;
  box-shadow: 0 28px 80px rgba(15, 23, 42, .22);
  animation: ad-modal-in .25s cubic-bezier(.2, 1, .3, 1);
}
@keyframes ad-modal-in {
  from { opacity: 0; transform: translateY(16px) scale(.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.modal-content h3 {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 800;
  color: #16213e;
}

/* ── 配置弹窗 ── */
.config-modal-content {
  max-width: 700px;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  animation: ad-modal-in .25s cubic-bezier(.16, .84, .44, 1);
}
.config-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 26px 16px;
  border-bottom: 1px solid #f0f3f8;
  background: linear-gradient(135deg, #fafbff, #f5f8ff);
}
.config-modal-heading {
  min-width: 0;
  flex: 1;
}
.config-modal-title {
  font-size: 18px;
  font-weight: 800;
  color: #1a2233;
  line-height: 1.3;
}
.config-modal-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: #667491;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.config-modal-close {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 10px;
  background: #f0f3f8;
  color: #667085;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
}
.config-modal-close:hover {
  background: #e4e9f2;
  color: #1a2233;
  transform: rotate(90deg);
}
.config-modal-tabs {
  margin: 16px 26px 0;
}
.config-modal-body {
  padding: 18px 26px 22px;
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
}
.config-modal-hint {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f0f6ff, #eef2ff);
  border-radius: 12px;
  font-size: 13px;
  color: #1d4ed8;
  border: 1px solid #dbeafe;
  line-height: 1.6;
}
.config-modal-hint b {
  font-weight: 700;
}
.config-modal-hint-extra {
  margin-left: 8px;
  color: #6b7a90;
  font-weight: normal;
}

/* ── SKU 配置面板 ── */
.sku-count-badge {
  display: inline-block;
  margin-left: 6px;
  min-width: 20px;
  height: 20px;
  line-height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
  box-shadow: 0 2px 6px rgba(13, 107, 255, .25);
}
.sku-config-panel {
  padding: 4px 0;
}
.sku-loading, .sku-empty {
  padding: 40px 20px;
  text-align: center;
  color: #8896ab;
  font-size: 13px;
  line-height: 1.8;
  background: linear-gradient(135deg, #f8fafc, #f5f7fb);
  border-radius: 12px;
}
.sku-config-hint {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #fffbeb, #fff7ed);
  border: 1px solid #fde68a;
  border-radius: 12px;
  margin-bottom: 16px;
}
.sku-config-hint-text {
  flex: 1;
  font-size: 13px;
  color: #92400e;
  line-height: 1.7;
}
.sku-config-hint-text b { font-weight: 700; }
.sku-config-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
:deep(.sku-btn-small) {
  padding: 5px 12px !important;
  font-size: 12px !important;
  border-radius: 8px !important;
}
.sku-rule-card {
  border: 1px solid #e8edf5;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fff;
  transition: all .2s;
}
.sku-rule-card:hover {
  box-shadow: 0 4px 16px rgba(31, 53, 94, .08);
  border-color: #d8e2f0;
}
.sku-rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e8edf5;
}
.sku-rule-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sku-rule-index {
  display: inline-block;
  min-width: 28px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  border-radius: 8px;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: #4338ca;
  font-size: 12px;
  font-weight: 700;
}
.sku-rule-property {
  font-size: 14px;
  font-weight: 700;
  color: #1f2937;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sku-rule-id {
  font-size: 11px;
  color: #b0bbd0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  background: #f8fafc;
  padding: 3px 8px;
  border-radius: 6px;
}
.sku-timing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 1100px) {
  .sku-timing-grid { grid-template-columns: 1fr; }
}
.sku-timing-cell {
  border: 1px solid #eef1f6;
  border-radius: 10px;
  padding: 12px;
  background: #fafbfd;
  transition: all .15s;
}
.sku-timing-cell:hover {
  border-color: #d8e2f0;
  background: #fff;
}
.sku-timing-header {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eef1f6;
}
.sku-timing-header .checkbox-label {
  font-weight: 600;
  color: #1f2937;
  font-size: 13px;
}
.sku-timing-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sku-timing-body-disabled {
  font-size: 12px;
  color: #b0bbd0;
  padding: 12px 6px;
  line-height: 1.6;
  text-align: center;
}
.sku-timing-body .form-row label {
  font-size: 12px;
  color: #6b7a90;
  font-weight: 600;
}
.sku-timing-body textarea,
.sku-timing-body .input {
  font-size: 12.5px;
  padding: 8px 10px;
  border-radius: 8px;
}
.sku-config-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  margin-top: 8px;
  border-top: 1px solid #f0f3f8;
}
.config-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 26px;
  border-top: 1px solid #f0f3f8;
  background: linear-gradient(135deg, #fafbff, #f8faff);
}

/* ── 表单 ── */
.form-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-row label {
  font-size: 13px;
  font-weight: 600;
  color: #4a5b75;
}
.form-row textarea {
  width: 100%;
  min-height: 70px;
  padding: 10px 14px;
  border: 1px solid #e2e8f2;
  border-radius: 10px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
  transition: all .18s;
  line-height: 1.6;
}
.form-row textarea:focus {
  outline: none;
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, .10);
}
.form-row .input,
.form-row select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #e2e8f2;
  border-radius: 10px;
  font-size: 13px;
  color: #1a2742;
  transition: all .18s;
}
.form-row .input:focus,
.form-row select:focus {
  outline: none;
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, .10);
}
.content-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.insert-source-btn {
  height: 28px;
  padding: 0 12px;
  border: 1px solid #c7d2fe;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: #4338ca;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  display: inline-flex;
  align-items: center;
}
.insert-source-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: #4f46e5;
  color: #fff;
  transform: translateY(-1px);
}
.insert-source-btn:disabled {
  opacity: .5;
  cursor: not-allowed;
}
.insert-source-btn.ghost {
  background: #fff;
  border-color: #e2e8f2;
  color: #526079;
}
.insert-source-btn.ghost:hover:not(:disabled) {
  background: #f5f7fb;
  border-color: #c8d4e6;
  color: #1a2742;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4a5b75;
  font-weight: 500;
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #0d6bff;
  cursor: pointer;
}
.subtle {
  color: #98a2b3;
  font-size: 12px;
  font-weight: 500;
}

/* ── 货源抽屉 ── */
.source-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, .40);
  backdrop-filter: blur(3px);
  z-index: 1100;
  display: flex;
  justify-content: flex-end;
  animation: ad-overlay-in .18s ease-out;
}
.source-drawer {
  width: 440px;
  max-width: 90vw;
  height: 100%;
  background: #fff;
  box-shadow: -20px 0 60px rgba(15, 23, 42, .18);
  display: flex;
  flex-direction: column;
  animation: ad-drawer-slide .25s cubic-bezier(.16, .84, .44, 1);
}
@keyframes ad-drawer-slide {
  from { transform: translateX(24px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.source-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 22px 16px;
  border-bottom: 1px solid #f0f3f8;
  background: linear-gradient(135deg, #fafbff, #f5f8ff);
}
.source-drawer-title {
  font-size: 17px;
  font-weight: 800;
  color: #1a2233;
}
.source-drawer-close {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 10px;
  background: #f0f3f8;
  color: #667085;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
}
.source-drawer-close:hover {
  background: #e4e9f2;
  color: #1a2233;
  transform: rotate(90deg);
}
.source-drawer-tip {
  padding: 12px 22px;
  font-size: 12px;
  color: #5b6b88;
  background: linear-gradient(135deg, #f0f6ff, #eef2ff);
  border-bottom: 1px solid #f0f3f8;
  line-height: 1.7;
}
.source-drawer-tip code {
  background: #e0e7ff;
  color: #3730a3;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
}
.source-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.source-drawer-empty {
  padding: 48px 20px;
  text-align: center;
  color: #b0bbd0;
  font-size: 13px;
}
.source-drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: all .18s;
}
.source-drawer-item:hover {
  border-color: #6366f1;
  background: linear-gradient(135deg, #f5f7ff, #eef2ff);
  box-shadow: 0 4px 16px rgba(99, 102, 241, .12);
  transform: translateY(-1px);
}
.source-drawer-item-main {
  flex: 1;
  min-width: 0;
}
.source-drawer-item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}
.source-drawer-item-name {
  font-size: 14px;
  font-weight: 700;
  color: #1a2233;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}
.source-drawer-item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #8896ab;
}
.source-drawer-item-insert {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 8px;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: #4338ca;
  font-size: 12px;
  font-weight: 700;
  transition: all .15s;
}
.source-drawer-item:hover .source-drawer-item-insert {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
}

/* ── 响应式 ── */
@media (max-width: 1400px) {
  .ad-layout {
    grid-template-columns: 1fr;
  }
  .ad-sidebar {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 900px) {
  .ad-banner {
    flex-direction: column;
    align-items: flex-start;
  }
  .ad-banner-stats {
    width: 100%;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .ad-sidebar {
    grid-template-columns: 1fr;
  }
  .ad-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
