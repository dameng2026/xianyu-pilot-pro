<template>
  <div>
    <div class="page-head">
      <div>
        <h1>自动发货</h1>
        <p>按商品配置自动发货时机，支持文本发货、卡密发货，以及引用货源库快速配置。</p>
      </div>
    </div>

    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>
    <div v-if="statsError" class="global-notice warn">{{ statsError }}</div>
    <div v-if="sourcesError" class="global-notice warn">{{ sourcesError }}</div>
    <div v-if="dependenciesError" class="global-notice warn">{{ dependenciesError }}</div>

    <div class="stat-row">
      <StatCard title="今日发货成功" :value="statValue(stats.todaySuccess)" :change="statsAvailable ? '今日' : '状态不可用'" icon="shield" color="green" />
      <StatCard title="今日失败" :value="statValue(stats.todayFail)" :change="statsAvailable ? '今日' : '状态不可用'" icon="warning" color="orange" />
      <StatCard title="待处理订单" :value="statValue(stats.pendingOrders)" :change="statsAvailable ? '待处理' : '状态不可用'" icon="clock" />
      <StatCard title="库存不足" :value="statValue(stats.lowStockGoods)" :change="statsAvailable ? '需关注' : '状态不可用'" icon="warning" color="red" />
      <StatCard title="已启用自动发货" :value="statValue(stats.enabledGoods)" :change="statsAvailable ? '全部商品' : '状态不可用'" icon="product" />
    </div>

    <div class="delivery-body">
      <div class="filter-panel">
        <CardPanel title="筛选条件">
          <div class="filter-section">
            <label class="filter-label">闲鱼账号</label>
            <select v-model="query.accountId" class="input" style="width:100%" :disabled="!accountsAvailable" @change="loadGoods">
              <option value="">全部账号</option>
              <option v-for="account in accounts" :key="account.id" :value="account.id">{{ accountName(account) }}</option>
            </select>
          </div>
          <div class="filter-section">
            <label class="filter-label">搜索商品</label>
            <input v-model="query.keyword" class="input" placeholder="标题 / ID" style="width:100%" @keyup.enter="loadGoods" />
          </div>
          <div class="filter-section">
            <label class="filter-label">发货形式</label>
            <select v-model="query.deliveryType" class="input" style="width:100%">
              <option value="">全部</option>
              <option value="text">文本发货</option>
              <option value="card">卡密发货</option>
              <option value="none">未配置</option>
            </select>
          </div>
          <div class="filter-section">
            <label class="filter-label">配置状态</label>
            <select v-model="query.configStatus" class="input" style="width:100%">
              <option value="">全部</option>
              <option value="configured">已配置</option>
              <option value="unconfigured">未配置</option>
            </select>
          </div>
          <div class="filter-section">
            <label class="filter-label">商品状态</label>
            <select v-model="query.goodsStatus" class="input" style="width:100%">
              <option value="">全部</option>
              <option value="0">在售</option>
              <option value="1">下架</option>
            </select>
          </div>
          <AppButton type="primary" style="width:100%;margin-top:8px" @click="applyFilter">应用筛选</AppButton>
          <AppButton style="width:100%;margin-top:6px" @click="resetFilter">重置筛选</AppButton>
        </CardPanel>

        <CardPanel title="快捷操作" style="margin-top:12px">
          <AppButton type="primary" style="width:100%;margin-bottom:8px" :disabled="!goodsAvailable || hasUnavailableGoods || filteredGoods.length === 0" @click="openBatchDialog">批量设置</AppButton>
          <AppButton style="width:100%;margin-bottom:8px" @click="goSourceLibrary">打开货源库</AppButton>
          <AppButton type="danger" style="width:100%;margin-bottom:8px" :disabled="!goodsAvailable || hasUnavailableGoods || filteredGoods.length === 0" @click="batchDelete">批量删除配置</AppButton>
          <AppButton style="width:100%" @click="scanPendingOrders">扫描待发货订单</AppButton>
        </CardPanel>
      </div>

      <div class="main-content">
        <div class="timing-notice">
          <span class="timing-notice-icon">i</span>
          <span><b>付款后发货</b>会由系统定时扫描自动执行；<b>确认收货后赠送</b>和<b>好评后赠送</b>可在发货记录页手动触发，也可接入后续事件自动化。</span>
        </div>

        <CardPanel>
          <div class="toolbar" style="margin-bottom:12px">
            <span class="table-info">共 <b>{{ filteredGoods.length }}</b> 个商品</span>
            <span style="margin-left:12px" class="subtle">点击状态列可快速进入对应时机配置。</span>
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
        </CardPanel>
      </div>
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
        </div>

        <div class="config-modal-body">
          <div class="config-modal-hint">
            当前配置时机：<b>{{ currentTimingLabel }}</b>
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
        </div>

        <div class="config-modal-footer">
          <AppButton @click="closeConfig">取消</AppButton>
          <AppButton type="primary" :loading="configSaving" :disabled="configSaveDisabled" @click="saveConfig">保存配置</AppButton>
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
import { getLiteAccounts } from '../api/accounts.js'
import { getGoods } from '../api/goods.js'
import { getCards } from '../api/cards.js'
import {
  batchDeleteDeliveryRules,
  batchSetDeliveryRules,
  getDeliverySources,
  getDeliveryStats,
  getGoodsDeliveryConfig,
  saveGoodsDeliveryConfig,
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
    const withConfig = await Promise.all(list.map(async goods => {
      try {
        const configRes = await getGoodsDeliveryConfig(goods.id)
        const config = configRes?.data
        if (!config || typeof config !== 'object' || Array.isArray(config)) {
          throw new Error('商品发货配置响应格式异常')
        }
        for (const timing of ['payDelivery', 'confirmDelivery', 'reviewDelivery']) {
          const timingConfig = config[timing]
          if (timingConfig == null) continue
          const enabled = timingConfig?.enabled
          if (!timingConfig || typeof timingConfig !== 'object' || Array.isArray(timingConfig)
            || ![true, false, 0, 1].includes(enabled)
            || !['text', 'card', 'custom', 'api'].includes(timingConfig.mode)) {
            throw new Error(`${timing} 发货配置响应格式异常`)
          }
        }
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
}

function openBatchDialog() {
  if (!goodsAvailable.value || hasUnavailableGoods.value || filteredGoods.value.length === 0) return
  showBatchDialog.value = true
}

function switchTiming(timing) {
  configTiming.value = timing
  fillConfigForm(configTarget.value?.goods?._config?.[timing] || {})
}

function closeConfig() {
  configTarget.value = null
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
.page-head {
  margin-bottom: 10px;
}

.page-head h1 {
  margin: 0;
  font-size: 30px;
}

.page-head p {
  margin: 10px 0 0;
  color: #667491;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin: 14px 0 18px;
}

.delivery-body {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.filter-section {
  margin-bottom: 10px;
}

.filter-label {
  display: block;
  font-size: 13px;
  color: #526079;
  margin-bottom: 4px;
  font-weight: 500;
}

.table-info {
  font-size: 14px;
  color: #526079;
}

.goods-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
}

.goods-thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  object-fit: cover;
  background: #f0f4ff;
}

.goods-thumb.placeholder {
  background: #f0f4ff;
}

.goods-detail {
  min-width: 0;
}

.goods-title {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.goods-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #667085;
}

.goods-meta .price {
  color: #ef4444;
  font-weight: 600;
}

.delivery-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  font-weight: 500;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-green { background: #16bf78; }
.dot-gray { background: #c4cddb; }
.dot-red { background: #ef4444; }
.status-enabled { background: #ecfdf3; color: #067647; }
.status-none { background: #f5f6fa; color: #667085; }
.status-disabled { background: #f5f6fa; color: #98a2b3; }
.status-unavailable { background: #fff1f2; color: #be123c; }
.link:disabled { opacity: .5; cursor: not-allowed; }

.config-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  background: #f5f6fa;
  border-radius: 10px;
  padding: 3px;
}

.config-tab {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #667085;
  transition: color .15s, background .15s, box-shadow .15s;
}

.config-tab:hover:not(.active) {
  color: #2d5bff;
}

.config-tab.active {
  background: #fff;
  color: #2d5bff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .08);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  border-radius: 20px;
  padding: 28px;
  max-width: 560px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, .2);
}

.config-modal-content {
  max-width: 640px;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  animation: config-modal-in .2s cubic-bezier(.16, .84, .44, 1);
}

@keyframes config-modal-in {
  from { opacity: 0; transform: translateY(16px) scale(.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.config-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #eef1f6;
}

.config-modal-heading {
  min-width: 0;
  flex: 1;
}

.config-modal-title {
  font-size: 17px;
  font-weight: 600;
  color: #1a2233;
  line-height: 1.3;
}

.config-modal-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: #667491;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.config-modal-close {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: #f5f6fa;
  color: #667085;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background .15s, color .15s;
}

.config-modal-close:hover {
  background: #eef1f6;
  color: #1a2233;
}

.config-modal-tabs {
  margin: 16px 24px 0;
  margin-bottom: 0;
}

.config-modal-body {
  padding: 16px 24px 20px;
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
}

.config-modal-hint {
  margin-bottom: 14px;
  padding: 8px 12px;
  background: linear-gradient(90deg, #f0f4ff, #f6f9ff);
  border-radius: 10px;
  font-size: 13px;
  color: #2d5bff;
}

.config-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid #eef1f6;
  background: #fafbfd;
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-row textarea {
  width: 100%;
  min-height: 60px;
  padding: 8px 12px;
  border: 1px solid #dbe1ed;
  border-radius: 10px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.content-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.insert-source-btn {
  height: 26px;
  padding: 0 10px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}

.insert-source-btn:hover:not(:disabled) {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

.insert-source-btn:disabled {
  opacity: .5;
  cursor: not-allowed;
}

.insert-source-btn.ghost {
  background: #fff;
  border-color: #dbe1ed;
  color: #526079;
}

.insert-source-btn.ghost:hover:not(:disabled) {
  background: #f5f6fa;
  border-color: #98a2b3;
  color: #1a2233;
}

.source-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, .35);
  z-index: 1100;
  display: flex;
  justify-content: flex-end;
  animation: source-drawer-fade .18s ease-out;
}

@keyframes source-drawer-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

.source-drawer {
  width: 420px;
  max-width: 90vw;
  height: 100%;
  background: #fff;
  box-shadow: -16px 0 48px rgba(15, 23, 42, .18);
  display: flex;
  flex-direction: column;
  animation: source-drawer-slide .22s cubic-bezier(.16, .84, .44, 1);
}

@keyframes source-drawer-slide {
  from { transform: translateX(16px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.source-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #eef1f6;
}

.source-drawer-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a2233;
}

.source-drawer-close {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: #f5f6fa;
  color: #667085;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background .15s, color .15s;
}

.source-drawer-close:hover {
  background: #eef1f6;
  color: #1a2233;
}

.source-drawer-tip {
  padding: 10px 20px;
  font-size: 12px;
  color: #526079;
  background: linear-gradient(90deg, #f0f4ff, #f6f9ff);
  border-bottom: 1px solid #eef1f6;
  line-height: 1.6;
}

.source-drawer-tip code {
  background: #e0e7ff;
  color: #3730a3;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
}

.source-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-drawer-empty {
  padding: 40px 16px;
  text-align: center;
  color: #98a2b3;
  font-size: 13px;
}

.source-drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: border-color .15s, background .15s, box-shadow .15s;
}

.source-drawer-item:hover {
  border-color: #4f46e5;
  background: #f5f7ff;
  box-shadow: 0 4px 14px rgba(79, 70, 229, .12);
}

.source-drawer-item-main {
  flex: 1;
  min-width: 0;
}

.source-drawer-item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.source-drawer-item-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2233;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.source-drawer-item-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #667085;
}

.source-drawer-item-insert {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 6px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 700;
}

.source-drawer-item:hover .source-drawer-item-insert {
  background: #4f46e5;
  color: #fff;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #526079;
}

.subtle {
  color: #98a2b3;
  font-size: 13px;
}

.timing-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: linear-gradient(90deg, #fff8e6, #fffbf2);
  border: 1px solid #ffd98a;
  border-radius: 12px;
  font-size: 13px;
  color: #6b4f12;
  line-height: 1.6;
}

.timing-notice-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f5a623;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

@media (max-width: 1400px) {
  .stat-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .delivery-body {
    grid-template-columns: 1fr;
  }
}
</style>
