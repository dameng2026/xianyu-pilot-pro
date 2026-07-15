<template>
  <div class="products-page">
    <div class="products-main">
      <div v-if="notice.text" :class="['global-notice', notice.type]">{{ notice.text }}</div>
      <div v-if="statsError" class="global-notice warn">{{ statsError }}</div>
      <div v-if="accountsLoadError" class="global-notice warn">{{ accountsLoadError }}</div>
      
      <!-- 自动同步状态横幅 -->
      <div v-if="autoSyncState.active" class="global-notice info">
        <strong>正在同步闲鱼商品...</strong>
        <template v-if="autoSyncState.accountTotal > 1">
          <span>（账号 {{ autoSyncState.accountIndex }}/{{ autoSyncState.accountTotal }}：{{ autoSyncState.accountLabel }}）</span>
        </template>
        <span v-if="autoSyncState.progress > 0">进度 {{ autoSyncState.progress }}%</span>
        <span class="muted" style="margin-left:8px">请勿离开当前页面，同步完成后将自动展示最新商品</span>
      </div>
      <div v-else-if="autoSyncState.completed" class="global-notice success">
        <strong>闲鱼商品同步完成！</strong>
        <span style="margin-left:8px">
          共同步 <b>{{ metricText(autoSyncState.summary.total) }}</b> 件商品，
          新增 <b>{{ metricText(autoSyncState.summary.new) }}</b>，
          更新 <b>{{ metricText(autoSyncState.summary.updated) }}</b>
          <template v-if="Number(autoSyncState.summary.offShelf) > 0">
            ，下架 <b>{{ metricText(autoSyncState.summary.offShelf) }}</b>
          </template>
          ，耗时 {{ metricText(autoSyncState.summary.duration) }}秒
        </span>
        <span v-if="autoSyncState.accountTotal > 1" class="muted" style="margin-left:8px">| 共同步 {{ autoSyncState.accountTotal }} 个账号</span>
        <span class="muted" style="margin-left:8px">| 当前仅展示本次同步的最新商品数据</span>
        <button class="link" style="margin-left:8px" @click="showAllProducts">查看全部商品</button>
      </div>
      <div v-else-if="autoSyncState.error" class="global-notice error">
        <strong>自动同步失败：</strong>{{ autoSyncState.error }}
        <button class="link" style="margin-left:8px" @click="syncProducts">重试同步</button>
      </div>

      <div class="grid stat-grid products-stat-grid">
        <StatCard title="商品总数" :value="metricText(goodsStats.total)" :change="statsError ? '状态不可用' : '全部商品'" icon="record" color="green" />
        <StatCard title="在售商品" :value="metricText(goodsStats.onSale)" :change="statsError ? '状态不可用' : '正在售卖'" icon="data" color="green" />
        <StatCard title="下架/草稿" :value="metricText(goodsStats.offShelfOrDraft)" :change="statsError ? '状态不可用' : '未上架'" icon="data" color="orange" />
        <StatCard title="自动发货" :value="metricText(goodsStats.autoDeliveryOn)" :change="statsError ? '状态不可用' : '已开启商品数'" icon="truck" color="purple" />
        <StatCard title="自动回复" :value="metricText(goodsStats.autoReplyAccounts)" :change="statsError ? '状态不可用' : '已开启账号数'" icon="chat" />
        <StatCard title="当前账号" :value="selectedAccountName" change="可切换账号" icon="shield" color="gray" />
      </div>
      <CardPanel class="products-table-card">
        <div class="products-toolbar">
          <div class="toolbar-filter">
            <div class="filter-left">
              <select v-model="query.xianyuAccountId" class="input toolbar-select" :disabled="!accountsAvailable" @change="onAccountChange">
                <option :value="''">全部账号</option>
                <option v-for="a in accounts" :key="a.id" :value="a.id">{{ accountName(a) }}</option>
              </select>
              <div class="tabs products-tabs">
                <button :class="['tab',{active:query.status === ''}]" @click="setStatus('')">全部</button>
                <button :class="['tab',{active:query.status === 0}]" @click="setStatus(0)">在售</button>
                <button :class="['tab',{active:query.status === 1}]" @click="setStatus(1)">下架/草稿</button>
                <button :class="['tab',{active:query.status === 3}]" @click="setStatus(3)">已删除</button>
              </div>
            </div>
            <div class="filter-search">
              <input v-model="query.keyword" class="input products-search-input" placeholder="搜索 商品标题 / 商品ID" @keyup.enter="loadItems">
              <AppButton :loading="loading" @click="loadItems">搜索</AppButton>
              <AppButton :disabled="loading" @click="resetQuery">重置</AppButton>
            </div>
          </div>
          <div class="toolbar-actions">
            <AppButton type="danger" :disabled="!itemsAvailable || selectedKeys.length === 0 || batchDeleting" @click="batchDeleteProducts">
              {{ batchDeleteBtnText }}
            </AppButton>
            <AppButton type="primary" :disabled="!accountsAvailable || syncing || autoSyncState.active" @click="syncProducts">{{ syncing || autoSyncState.active ? (autoSyncState.accountTotal > 1 ? `同步中 ${autoSyncState.accountIndex}/${autoSyncState.accountTotal}...` : '同步中...') : '同步闲鱼商品' }}</AppButton>
          </div>
        </div>
        <div v-if="batchDeleteState.active" class="global-notice warn">
          <strong>正在批量删除商品...</strong>
          <span>{{ batchDeleteState.done }}/{{ batchDeleteState.total }}</span>
          <span v-if="batchDeleteState.current" class="muted" style="margin-left:8px">{{ batchDeleteState.current }}</span>
        </div>
        <div v-else-if="batchDeleteState.result" class="global-notice" :class="batchDeleteState.result.failed.length ? 'warn' : 'success'">
          <strong>批量删除完成：</strong>
          <span>成功 <b>{{ batchDeleteState.result.success }}</b> / 失败 <b>{{ batchDeleteState.result.failed.length }}</b></span>
          <button v-if="batchDeleteState.result.failed.length" class="link" style="margin-left:8px" :title="batchDeleteState.result.failed.map(f => `${f.name}: ${f.reason}`).join('\n')">查看失败详情</button>
          <button v-if="batchDeleteState.result.warnings && batchDeleteState.result.warnings.length" class="link" style="margin-left:8px" :title="batchDeleteState.result.warnings.map(w => `${w.name}: ${w.reason}`).join('\n')">闲鱼下架失败({{ batchDeleteState.result.warnings.length }})</button>
          <button class="link" style="margin-left:8px" @click="batchDeleteState.result = null">关闭</button>
        </div>
        <div class="table-scroll-wrap">
          <EmptyState v-if="listLoadError" variant="error" title="商品列表加载失败" :description="listLoadError">
            <template #actions><AppButton @click="loadItems">重试</AppButton></template>
          </EmptyState>
          <BaseTable
            v-else
            v-model:selected-keys="selectedKeys"
            :columns="cols"
            :rows="products"
            :row-class="rowClass"
            :selectable="true"
            :row-key="rowKeyFn"
            class="products-table"
            @row-click="selectProduct"
          >
            <template #info="{row}"><div class="product-cell"><img v-if="row.coverPic" :src="row.coverPic" class="product-thumb" alt=""><div v-else class="product-thumb product-thumb-placeholder"></div><div class="product-info-text"><strong :title="row.raw?.title || row.name">{{ row.name }}</strong><em>ID：{{ row.xyGoodId }}</em></div></div></template>
            <template #price="{row}"><div class="cell-price">{{ row.price }}</div></template>
            <template #stock="{row}"><div class="cell-center cell-muted">{{ row.stock }}</div></template>
            <template #sku="{row}"><div class="cell-center cell-muted">{{ row.sku }}</div></template>
            <template #status="{row}"><div class="cell-center"><Badge :type="row.statusType">{{ row.status }}</Badge></div></template>
            <template #type="{row}">
              <span v-if="row.type === '未配置'" class="delivery-type-configurable" @click.stop="goToAutoDelivery">
                <Badge type="orange">未配置</Badge>
                <span class="config-hint">去配置</span>
              </span>
              <Badge v-else :type="row.deliveryTypeBadge">{{ row.type }}</Badge>
            </template>
            <template #delivery="{row}"><div class="cell-center"><Badge v-if="row.deliveryOn === null" type="gray">未知</Badge><ToggleSwitch v-else :on="row.deliveryOn" @click.stop="toggleDelivery(row)" /></div></template>
            <template #reply="{row}"><div class="cell-center"><Badge v-if="row.replyOn === null" type="gray">未知</Badge><ToggleSwitch v-else :on="row.replyOn" @click.stop="toggleReply(row)" /></div></template>
            <template #onsale="{row}"><div class="cell-center"><AppButton v-if="row.isLocalDraft" type="primary" @click.stop="publishDraft(row)">发布</AppButton><Badge v-else-if="row.statusCode === null" type="gray">未知</Badge><ToggleSwitch v-else :on="row.statusCode===0" @click.stop="toggleOnShelf(row)" /></div></template>
            <template #op="{row}">
              <div class="op-buttons">
                <button class="link" @click.stop="selectProduct(row)">详情</button>
                <button v-if="!row.isLocalDraft" class="link" :disabled="isItemBusy(row) || syncing || autoSyncState.active" @click.stop="refreshSingle(row)">同步</button>
                <button v-if="row.isLocalDraft" class="link" :disabled="isItemBusy(row)" @click.stop="publishDraft(row)">{{ isItemBusy(row) ? '处理中' : '发布' }}</button>
                <button class="link danger-text" :disabled="isItemBusy(row)" @click.stop="deleteProduct(row)">删除</button>
              </div>
            </template>
            <template #empty>
              <EmptyState v-if="autoSyncState.active" icon="⏳" title="正在同步闲鱼商品" :description="`正在从闲鱼获取商品数据... 进度 ${autoSyncState.progress}%`">
                <template #actions><span class="muted">同步完成后将自动展示最新商品</span></template>
              </EmptyState>
              <EmptyState v-else-if="autoSyncState.completed && products.length === 0" icon="🛍" title="本次同步未获取到商品" description="闲鱼账号中可能没有在售商品，或商品数据尚未完全同步。您可以稍后重试。">
                <template #actions><AppButton type="primary" @click="syncProducts">重新同步</AppButton></template>
              </EmptyState>
              <EmptyState v-else icon="🛍" title="还没有商品数据" description="先选择账号并同步闲鱼商品；如果是第一次使用，请先到闲鱼账号页完成账号绑定。">
                <template #actions><AppButton type="primary" :disabled="!accountsAvailable || syncing || autoSyncState.active" @click="syncProducts">{{ syncing || autoSyncState.active ? '同步中...' : '同步闲鱼商品' }}</AppButton><AppButton @click="emit('navigate','accounts')">添加账号</AppButton></template>
              </EmptyState>
            </template>
          </BaseTable>
        </div>
        <div v-if="!listLoadError" class="pagination products-pagination">
          <div class="pagination-left">
            <span class="page-size-label">每页显示</span>
            <select class="input page-size-select" :value="query.pageSize" @change="onPageSizeChange">
              <option v-for="s in pageSizes" :key="s" :value="s">{{ s }}</option>
            </select>
            <span class="page-size-unit">条</span>
          </div>
          <div class="pagination-right">
            <span class="pagination-total">{{ loading ? '加载中...' : `共 ${totalCount} 条 / ${totalPages} 页` }}</span>
            <button class="page-no" :disabled="query.pageNum <= 1" @click="prevPage">‹</button>
            <template v-for="(p, idx) in pageList" :key="idx">
              <span v-if="p === '...'" class="page-ellipsis">…</span>
              <button v-else :class="['page-no', { active: p === query.pageNum }]" @click="goToPage(p)">{{ p }}</button>
            </template>
            <button class="page-no" :disabled="query.pageNum * query.pageSize >= totalCount" @click="nextPage">›</button>
          </div>
        </div>
      </CardPanel>

      <CardPanel title="同步任务历史" style="margin-top:16px">
        <div class="toolbar compact">
          <select v-model="syncQuery.status" class="input" style="max-width:150px" @change="loadSyncTasks">
            <option value="">全部状态</option>
            <option value="queued">排队中</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
          <AppButton :disabled="syncTasksLoading" @click="loadSyncTasks">刷新任务</AppButton>
          <span class="muted">展示当前账号最近同步记录，服务重启后仍可恢复查看。</span>
        </div>
        <EmptyState v-if="syncTasksError" variant="error" title="同步任务历史加载失败" :description="syncTasksError">
          <template #actions><AppButton @click="loadSyncTasks">重试</AppButton></template>
        </EmptyState>
        <BaseTable v-else :columns="syncCols" :rows="syncTasks">
          <template #status="{row}"><Badge :type="syncStatusType(row.status)">{{ syncStatusText(row.status) }}</Badge></template>
          <template #progress="{row}">{{ syncProgressText(row.progress) }}</template>
          <template #summary="{row}">总 {{ metricText(row.total) }} / 新增 {{ metricText(row.newCount) }} / 更新 {{ metricText(row.updatedCount) }} / 跳过 {{ metricText(row.skippedCount) }}</template>
          <template #error="{row}"><span :title="row.errorMessage">{{ shortText(row.errorMessage || '-', 30) }}</span></template>
        </BaseTable>
        <div v-if="!syncTasksError" class="pagination"><span>{{ syncTasksLoading ? '加载中...' : `共 ${syncTaskTotal} 条任务` }}</span><span class="page-no" @click="prevSyncPage">‹</span><span class="page-no active">{{ syncQuery.current }}</span><span class="page-no" @click="nextSyncPage">›</span></div>
      </CardPanel>
    </div>
    <div v-if="selected" class="right-drawer products-drawer">
      <div class="drawer-header">
        <h3>商品详情</h3>
        <button class="drawer-close" @click="selected = null">×</button>
      </div>
      <template v-if="selected">
        <div class="preview-card" style="height:210px;padding:0;overflow:hidden;border-radius:12px"><img v-if="selected.coverPic" :src="selected.coverPic" style="width:100%;height:100%;object-fit:cover" alt=""><div v-else class="product-thumb" style="width:100%;height:100%;border-radius:0;background:linear-gradient(135deg,#f5f7fb,#dfe9f8)"></div></div>
        <h3 class="drawer-title">{{ selected.name }}</h3>
        <p class="drawer-price"><b style="color:#ef4444;font-size:22px">{{ selected.price }}</b> <Badge :type="selected.statusType">{{ selected.status }}</Badge></p>
        <CardPanel title="商品数据" class="drawer-card">
          <div class="option-line"><span>商品ID</span><b class="drawer-value">{{ selected.xyGoodId }}</b></div>
          <div class="option-line"><span>库存</span><b>{{ selected.stock }}</b></div>
          <div class="option-line"><span>曝光/浏览/想要</span><b>{{ selected.exposureCount }} / {{ selected.viewCount }} / {{ selected.wantCount }}</b></div>
          <div class="option-line"><span>更新时间</span><b>{{ selected.time }}</b></div>
        </CardPanel>
        <div class="grid drawer-metrics">
          <div class="metric-tile"><span>自动发货</span><b :class="{'text-green':selected.deliveryOn === true,'text-gray':selected.deliveryOn !== true}">{{ switchStateText(selected.deliveryOn) }}</b></div>
          <div class="metric-tile"><span>自动回复</span><b :class="{'text-green':selected.replyOn === true,'text-gray':selected.replyOn !== true}">{{ switchStateText(selected.replyOn) }}</b></div>
          <div class="metric-tile"><span>账号</span><b>{{ accountName(accounts.find(a => a.id === Number(selected.xianyuAccountId)) || {}) || '-' }}</b></div>
        </div>
        <div class="grid drawer-actions">
          <AppButton type="primary" @click="loadDetail(selected)">详情</AppButton>
          <AppButton @click="editPrice(selected)">改价</AppButton>
          <AppButton @click="editStock(selected)">库存</AppButton>
          <AppButton v-if="selected.isLocalDraft" type="primary" @click="publishDraft(selected)">发布</AppButton>
          <AppButton v-else type="warn" @click="offShelf(selected.raw)">下架</AppButton>
          <AppButton type="danger" class="full-width" @click="deleteProduct(selected)">删除</AppButton>
        </div>
      </template>
    </div>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import StatCard from '../components/StatCard.vue';import CardPanel from '../components/CardPanel.vue';import BaseTable from '../components/BaseTable.vue';import Badge from '../components/Badge.vue';import ToggleSwitch from '../components/ToggleSwitch.vue';import AppButton from '../components/AppButton.vue';import EmptyState from '../components/EmptyState.vue'
import { confirmAction } from '../utils/confirmAction.js'
import { globalConfirm } from '../composables/confirmState.js'
import { getLiteAccounts } from '../api/accounts.js'
import { getBusinessSettings } from '../api/businessSettings.js'
import { updateProductAutoReplyScope } from '../api/autoReplyScope.js'
import { deleteGoodsLocal, getGoodsDetail, getGoods, getGoodsStats, updateGoods } from '../api/goods.js'
import { refreshItems, getSyncProgress, getSyncTasks, publishItem, offShelfItem, updateItemPrice, remoteDeleteItem } from '../api/items.js'
import { accountName, formatMoney, formatNumber, shortText } from '../utils/format.js'
import { recordsOfOrThrow } from '../utils/apiData.js'

const emit = defineEmits(['navigate'])
const accounts = ref([])
const accountsAvailable = ref(false)
const accountsLoadError = ref('')
const items = ref([])
const totalCount = ref(0)
const goodsStats = ref({ total: null, onSale: null, offShelfOrDraft: null, autoDeliveryOn: null, autoReplyAccounts: null })
const statsError = ref('')
const listLoadError = ref('')
const itemsAvailable = ref(false)
const loading = ref(false)
const syncing = ref(false)
const busyItemId = ref(null)
// 批量选择：使用商品记录的本地 id（raw.id）作为 key，翻页/筛选时清空，避免误删不可见行
const selectedKeys = ref([])
const batchDeleting = ref(false)
const batchDeleteState = reactive({
  active: false,
  done: 0,
  total: 0,
  current: '',
  result: null // { success: number, failed: [{name, reason}] }
})
const rowKeyFn = (row) => row?.raw?.id
const batchDeleteBtnText = computed(() => {
  if (batchDeleting.value) {
    return `删除中 ${batchDeleteState.done}/${batchDeleteState.total}`
  }
  return selectedKeys.value.length ? `批量删除(${selectedKeys.value.length})` : '批量删除'
})
const syncTask = ref({ id: '', status: '', progress: 0 })
const syncTasks = ref([])
const syncTaskTotal = ref(0)
const syncTasksLoading = ref(false)
const syncTasksError = ref('')
const syncQuery = reactive({ status: '', current: 1, size: 5 })
const notice = ref({ type: '', text: '' })
const selected = ref(null)
const query = reactive({ xianyuAccountId: '', status: '', keyword: '', pageNum: 1, pageSize: 50 })
// 每页条数可选项，默认 50
const pageSizes = [50, 100, 200, 300, 500, 1000]
const cols=[{key:'info',title:'商品信息'},{key:'price',title:'价格'},{key:'stock',title:'库存'},{key:'sku',title:'SKU'},{key:'status',title:'状态'},{key:'type',title:'发货类型'},{key:'delivery',title:'自动发货'},{key:'reply',title:'自动回复'},{key:'onsale',title:'在售'},{key:'time',title:'更新时间'},{key:'op',title:'操作'}]
const syncCols=[{key:'createdTime',title:'创建时间'},{key:'status',title:'状态'},{key:'progress',title:'进度'},{key:'summary',title:'统计'},{key:'durationSeconds',title:'耗时(s)'},{key:'error',title:'错误'}]
let syncPollCanceled = false
const statusMap = { 0: '在售', 1: '下架/草稿', 2: '已售出', 3: '已删除' }
const autoSyncState = reactive({
  active: false,
  completed: false,
  error: '',
  progress: 0,
  summary: emptySyncSummary(),
  // 多账号顺序同步时的进度信息
  accountIndex: 0,
  accountTotal: 0,
  accountLabel: '',
  failedAccounts: []
})

const products = computed(() => items.value.map(w => {
  const item = w.item || w
  const statusCode = item.status === null || item.status === undefined || item.status === '' ? null : Number(item.status)
  const category = item.category || ''
  const externalId = item.externalGoodsId || item.xyGoodId || ''
  const isLocalDraft = category === '商机发掘' || String(externalId).startsWith('opp:') || !externalId
  return {
    raw: item,
    wrapper: w,
    name: shortText(item.title || '未命名商品', 34),
    xyGoodId: externalId || `local:${item.id}`,
    category,
    isLocalDraft,
    xianyuAccountId: item.accountId || item.xianyuAccountId,
    coverPic: item.imageUrl || item.mainImageUrl || item.coverPic,
    price: formatMoney(item.soldPrice ?? item.price),
    stock: item.stock ?? item.quantity ?? '-',
    sku: item.skuCount ?? '-',
    statusCode: Number.isFinite(statusCode) ? statusCode : null,
    status: isLocalDraft ? '草稿/待发布' : (Number.isFinite(statusCode) ? (statusMap[statusCode] || String(statusCode)) : '状态未知'),
    statusType: isLocalDraft ? 'orange' : (statusCode === 0 ? 'green' : statusCode === 3 ? 'red' : Number.isFinite(statusCode) ? 'orange' : 'gray'),
    type: w.autoDeliveryType === 0
      ? '卡密'
      : w.autoDeliveryType === 1
        ? '文本'
        : w.autoDeliveryType === 2
          ? '自定义'
          : w.autoDeliveryType == null
            ? '配置状态未知'
            : '未知类型',
    deliveryTypeBadge: w.autoDeliveryType === 0 ? 'purple' : w.autoDeliveryType === 2 ? 'blue' : w.autoDeliveryType === 1 ? 'green' : 'gray',
    deliveryOn: normalizeSwitchState(w.xianyuAutoDeliveryOn),
    replyOn: normalizeSwitchState(w.xianyuAutoReplyOn),
    time: item.updatedTime || item.createdTime || '-',
    exposureCount: formatNumber(item.exposureCount),
    viewCount: formatNumber(item.viewCount),
    wantCount: formatNumber(item.wantCount)
  }
}))
const selectedAccountName = computed(() => {
  if (!query.xianyuAccountId) return accountsAvailable.value ? '全部账号' : '账号状态未知'
  const account = accounts.value.find(a => a.id === Number(query.xianyuAccountId))
  return account ? accountName(account) : '账号状态未知'
})
// AI 客服主开关缓存：null 表示未查询过，避免每次切换商品开关都请求后端
const aiCsEnabledCache = ref(null)

async function checkAiCsEnabled() {
  if (aiCsEnabledCache.value !== null) return aiCsEnabledCache.value
  try {
    const res = await getBusinessSettings('ai-customer-service')
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.enabled !== 'boolean') {
      throw new Error('AI 客服主开关响应格式异常')
    }
    aiCsEnabledCache.value = data.enabled
    return aiCsEnabledCache.value
  } catch (e) {
    console.warn('[ProductsPage] 检查AI客服主开关失败', e)
    return null
  }
}

function normalizeSwitchState(value) {
  if (value === true || Number(value) === 1) return true
  if (value === false || value === 0 || value === '0') return false
  return null
}

function switchStateText(value) {
  if (value === true) return '已开启'
  if (value === false) return '已关闭'
  return '状态未知'
}

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function emptySyncSummary() {
  return { total: null, new: null, updated: null, offShelf: null, duration: null }
}

function syncProgressText(value) {
  const progress = Number(value)
  return Number.isFinite(progress) ? `${progress}%` : '—'
}

async function promptEnableAiCs() {
  const ok = await confirmAction({
    title: '尚未开启 AI 自动回复主开关',
    description: '请先前往「AI 客服配置」页面开启 24 小时全天在线的 AI 自动回复，开启后即可为商品启用自动回复。',
    confirmText: '前往配置'
  })
  if (ok) emit('navigate', 'settings-ai-cs')
}
function showNotice(type, text) { notice.value = { type, text } }
function clearNotice() { notice.value = { type: '', text: '' } }
function setStatus(status){ query.status = status; query.pageNum = 1; selectedKeys.value = []; loadItems() }
function resetQuery(){ query.status=''; query.keyword=''; query.pageNum=1; selectedKeys.value = []; loadItems() }
function onAccountChange(){
  query.pageNum = 1
  selectedKeys.value = []
  syncQuery.current = 1
  loadSyncTasks()
  loadGoodsStats()
  // 切换账号时重新检查自动同步条件
  autoTriggerSync()
}

async function loadAccountsData() {
  accountsAvailable.value = false
  accountsLoadError.value = ''
  try {
    const res = await getLiteAccounts()
    accounts.value = recordsOfOrThrow(res?.data, '账号列表响应格式异常')
    accountsAvailable.value = true
  } catch (loadError) {
    accounts.value = []
    query.xianyuAccountId = ''
    accountsLoadError.value = `${loadError?.message || '账号列表加载失败'}；账号筛选和商品同步已停用。`
    throw loadError
  }
}
async function loadItems(options = {}) {
  loading.value = true
  listLoadError.value = ''
  itemsAvailable.value = false
  try {
    const params = { pageNum: query.pageNum, pageSize: query.pageSize, keyword: query.keyword || undefined }
    if (query.xianyuAccountId) params.xianyuAccountId = Number(query.xianyuAccountId)
    if (query.status !== '') params.status = query.status
    // 支持排除特定状态，例如同步完成后排除已删除(status=3)商品
    if (options.excludeStatus !== undefined) params.excludeStatus = options.excludeStatus
    const res = await getGoods(params)
    const data = res?.data
    if (!data || (typeof data !== 'object' && !Array.isArray(data))) throw new Error('商品列表响应格式异常，请稍后重试')
    const records = Array.isArray(data)
      ? data
      : data.records || data.itemsWithConfig || data.items || data.list || data.rows
    if (!Array.isArray(records)) throw new Error('商品列表响应格式异常，请稍后重试')
    items.value = records
    const rawTotal = Array.isArray(data) ? records.length : data.total ?? data.totalCount
    const parsedTotal = Number(rawTotal)
    if (!Number.isFinite(parsedTotal) || parsedTotal < records.length) throw new Error('商品总数响应格式异常，请稍后重试')
    totalCount.value = parsedTotal
    selected.value = products.value[0] || null
    itemsAvailable.value = true
  } catch (e) {
    items.value = []
    totalCount.value = 0
    selected.value = null
    listLoadError.value = e.message || '商品列表加载失败'
  }
  finally { loading.value = false }
}
// 加载商品全局统计（不受分页、关键词、状态筛选影响，仅按账号过滤）
async function loadGoodsStats() {
  statsError.value = ''
  try {
    const params = {}
    if (query.xianyuAccountId) params.accountId = Number(query.xianyuAccountId)
    const res = await getGoodsStats(params)
    const data = res?.data
    const metricKeys = ['total', 'onSale', 'offShelfOrDraft', 'autoDeliveryOn', 'autoReplyAccounts']
    if (!data || typeof data !== 'object' || Array.isArray(data)
      || metricKeys.some(key => typeof data[key] !== 'number' || !Number.isFinite(data[key]) || data[key] < 0)) {
      throw new Error('商品统计响应不完整')
    }
    goodsStats.value = {
      total: data.total,
      onSale: data.onSale,
      offShelfOrDraft: data.offShelfOrDraft,
      autoDeliveryOn: data.autoDeliveryOn,
      autoReplyAccounts: data.autoReplyAccounts
    }
  } catch (e) {
    goodsStats.value = { total: null, onSale: null, offShelfOrDraft: null, autoDeliveryOn: null, autoReplyAccounts: null }
    statsError.value = `${e?.message || '商品统计加载失败'}，相关指标显示为“—”。`
  }
}
async function loadSyncTasks() {
  syncTasksError.value = ''
  if (!query.xianyuAccountId) { syncTasks.value = []; syncTaskTotal.value = 0; return }
  syncTasksLoading.value = true
  try {
    const res = await getSyncTasks({ accountId: Number(query.xianyuAccountId), status: syncQuery.status || undefined, current: syncQuery.current, size: syncQuery.size })
    const page = res?.data
    if (!page || typeof page !== 'object' || Array.isArray(page)) throw new Error('同步任务响应格式异常')
    if (!Array.isArray(page.records)) throw new Error('同步任务响应格式异常')
    syncTasks.value = page.records
    const parsedTotal = Number(page.total ?? page.records.length)
    if (!Number.isFinite(parsedTotal) || parsedTotal < 0) throw new Error('同步任务总数响应格式异常')
    syncTaskTotal.value = parsedTotal
  } catch (e) {
    syncTasks.value = []
    syncTaskTotal.value = 0
    syncTasksError.value = e.message || '同步任务历史加载失败'
  } finally { syncTasksLoading.value = false }
}
function syncStatusText(status) { return ({ queued: '排队中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消' })[status] || status || '状态未知' }
function syncStatusType(status) { return status === 'completed' ? 'green' : status === 'failed' ? 'red' : status === 'running' ? 'orange' : 'gray' }
function prevSyncPage(){ if(syncQuery.current > 1){ syncQuery.current--; loadSyncTasks() } }
function nextSyncPage(){ if(syncQuery.current * syncQuery.size < syncTaskTotal.value){ syncQuery.current++; loadSyncTasks() } }
async function init(){
  try {
    await loadAccountsData()
  } catch {
    // 账号错误由专用不可用态展示；商品列表和统计仍可独立加载。
  }
  await loadSyncTasks()
  await autoTriggerSync()
}
function showAllProducts() {
  // 用户点击"查看全部商品"时清除仅展示同步结果的限制，加载全部商品
  autoSyncState.completed = false
  loadItems()
}
function selectProduct(row){ selected.value = row }
const rowClass = (row) => selected.value && selected.value.xyGoodId === row.xyGoodId ? 'row-selected' : ''
function itemBusyKey(row){ return row?.raw?.id || row?.id || row?.xyGoodId }
function isItemBusy(row){ return busyItemId.value && busyItemId.value === itemBusyKey(row) }
async function withItemBusy(row, task){ const key = itemBusyKey(row); if (busyItemId.value) return; busyItemId.value = key; try { return await task() } finally { busyItemId.value = null } }
function prevPage(){ if(query.pageNum > 1){ query.pageNum--; selectedKeys.value = []; loadItems() } }
function nextPage(){ if(query.pageNum * query.pageSize < totalCount.value){ query.pageNum++; selectedKeys.value = []; loadItems() } }
function goToPage(n){
  const total = Math.max(1, Math.ceil(totalCount.value / query.pageSize))
  if (n < 1 || n > total || n === query.pageNum) return
  query.pageNum = n
  selectedKeys.value = []
  loadItems()
}
// 总页数
const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / query.pageSize)))
// 可点击的页码列表（含省略号）：总是显示首尾页，当前页前后各显示 2 页
const pageList = computed(() => {
  const total = totalPages.value
  const current = query.pageNum
  const list = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) list.push(i)
    return list
  }
  list.push(1)
  let start = Math.max(2, current - 2)
  let end = Math.min(total - 1, current + 2)
  if (start > 2) list.push('...')
  for (let i = start; i <= end; i++) list.push(i)
  if (end < total - 1) list.push('...')
  list.push(total)
  return list
})
// 切换每页条数：重置到第 1 页并清空选择
function changePageSize() {
  query.pageNum = 1
  selectedKeys.value = []
  loadItems()
}
// select change 事件：转成数字再调用 changePageSize
function onPageSizeChange(e) {
  query.pageSize = Number(e.target.value)
  changePageSize()
}
async function refreshSingle(row) {
  const accountId = row.xianyuAccountId || Number(query.xianyuAccountId)
  if (!accountId) return showNotice('warn', '请先选择账号')
  const ok = await confirmAction({ title:'确认同步该账号全部商品？', description:'当前版本会同步该账号的全部闲鱼商品，不是仅刷新单个商品。同步期间请避免重复点击。' })
  if (!ok) return
  // 复用 syncProducts 的完整同步+进度展示逻辑，确保三个同步入口行为一致
  return syncProducts(false, accountId)
}
function toggleDelivery(_row) { showNotice('info', '自动发货开关请到“自动发货”模块配置规则') }
async function toggleReply(row) {
  if (typeof isItemBusy === 'function' && isItemBusy(row)) return
  const nextEnabled = !row.replyOn
  if (nextEnabled) {
    const enabled = await checkAiCsEnabled()
    if (enabled === null) {
      showNotice('error', '无法确认 AI 客服主开关状态，请检查网络后重试；当前不会修改商品自动回复配置。')
      return
    }
    if (!enabled) {
      await promptEnableAiCs()
      return
    }
  }
  try {
    const itemId = row.raw?.id ?? row.id
    await updateProductAutoReplyScope(itemId, nextEnabled)
    row.replyOn = nextEnabled
    if (row.raw) row.raw.auto_reply_enabled = nextEnabled ? 1 : 0
    showNotice('success', `已${nextEnabled ? '开启' : '关闭'}商品"${row.name}"的自动回复`)
    aiCsEnabledCache.value = null  // 刷新缓存
    loadGoodsStats()
  } catch (e) {
    showNotice('error', e.message || '切换自动回复失败')
    aiCsEnabledCache.value = null
  }
}
async function toggleOnShelf(row) {
  if (row.isLocalDraft) return publishDraft(row)
  if (row.statusCode === 0) return offShelf(row.raw)
  showNotice('warn', '重新上架需要重新发布商品，即将跳转到发布商品页')
  setTimeout(() => emit('navigate', 'product-publish'), 1200)
}
async function offShelf(item) {
  if(!item?.externalGoodsId) return showNotice('warn', '本地草稿尚未发布到闲鱼，不能执行远端下架')
  if(!await confirmAction({title:'确认下架该商品？',description:'该操作会影响闲鱼线上状态。请确认商品不需要继续售卖。'})) return
  return withItemBusy({ raw: item }, async () => {
  try {
    await offShelfItem({ xianyuAccountId: item.accountId || query.xianyuAccountId, xyGoodsId: item.externalGoodsId })
    await updateGoods(item.id, { accountId: item.accountId || Number(query.xianyuAccountId), title: item.title, status: 1 })
    showNotice('success', '下架成功')
    await loadItems()
    loadGoodsStats()
  } catch(e){ showNotice('error', e.message || '下架失败') }
  })
}
function priceNumber(row) {
  const raw = String(row.raw?.price ?? row.price ?? '0').replace(/[¥￥,]/g, '').trim()
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : 0
}
function parseDraftMeta(item) {
  const text = item?.detailInfo || item?.detail_info || ''
  if (!text || typeof text !== 'string') return {}
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function normalizePublishResult(res) {
  const outer = res?.data !== undefined ? res.data : res
  const data = outer?.data !== undefined ? outer.data : outer
  const code = Number(outer?.code ?? 200)
  if (Number.isFinite(code) && code !== 200 && code !== 0) {
    throw new Error(outer?.msg || outer?.message || '发布失败')
  }
  const nestedCode = data && typeof data === 'object' && data.code !== undefined ? Number(data.code) : 200
  if (Number.isFinite(nestedCode) && nestedCode !== 200 && nestedCode !== 0) {
    throw new Error(data.msg || data.message || '发布失败')
  }
  const payload = data && data.data !== undefined ? data.data : data
  const itemId = payload?.itemId || payload?.item_id || payload?.xyGoodsId || payload?.id || ''
  if (!itemId || String(itemId).startsWith('opp:')) {
    throw new Error(payload?.message || '发布接口未返回有效闲鱼商品ID，本地状态不会改为在售')
  }
  return { ...payload, itemId }
}

async function publishDraft(row) {
  const item = row.raw || row
  if (!item?.id) return
  if (!query.xianyuAccountId && !item.accountId) return showNotice('warn', '请先选择发布账号')
  const image = item.imageUrl || item.coverPic || row.coverPic
  if (!image) return showNotice('warn', '发布前至少需要一张商品图片，请先补充图片')
  const price = priceNumber(row)
  if (!price) return showNotice('warn', '发布前需要设置有效价格')
  const meta = parseDraftMeta(item)
  const location = meta.location || item.location
  if (!location || !location.poiName) {
    return showNotice('warn', '发布前需要完整的省、市、区地址。请在商机发掘或发布商品页完成地址选择后重试。')
  }
  if (!await confirmAction({title:`确认发布「${row.name}」？`,description:'发布前请确认标题、描述、图片、价格和位置真实有效。'})) return
  return withItemBusy(row, async () => {
  let publishedItemId = ''
  try {
    const res = await publishItem({
      xianyuAccountId: Number(item.accountId || query.xianyuAccountId),
      title: String(item.title || row.name).slice(0, 30),
      description: item.description || item.title || row.name,
      imageUrls: [image],
      price,
      stock: Number(item.quantity || item.stock || 1) || 1,
      category: item.category && item.category !== '商机发掘' ? item.category : undefined,
      location,
    })
    const data = normalizePublishResult(res)
    publishedItemId = String(data.itemId)
    await updateGoods(item.id, {
      accountId: item.accountId || Number(query.xianyuAccountId),
      title: item.title,
      externalGoodsId: data.itemId,
      detailUrl: data.itemUrl || item.detailUrl,
      status: 0,
      category: item.category === '商机发掘' ? '已发布' : item.category,
    })
    showNotice('success', '发布成功，已同步本地商品状态')
    await loadItems()
    loadGoodsStats()
  } catch(e) {
    if (publishedItemId) {
      localStorage.setItem(LS_PENDING_SYNC, 'true')
      showNotice('error', `商品已发布到闲鱼（ID：${publishedItemId}），但本地状态保存失败：${e.message || '服务异常'}。请勿重复发布，先执行商品同步。`)
    } else {
      showNotice('error', e.message || '发布失败，本地商品仍保持草稿状态')
    }
  }
  })
}

/**
 * 统一删除商品：
 * - 本地草稿：直接删除本地记录
 * - 已发布到闲鱼的商品：先调用闲鱼 API 下架商品，再从本地数据库删除该商品记录
 */
async function deleteProduct(row) {
  const item = row.raw || row
  if (!item?.id) return
  const isLocalDraft = row.isLocalDraft

  const confirmDesc = isLocalDraft
    ? '该商品为本地草稿，删除后将从本地数据库移除。'
    : '删除后，商品会从闲鱼下架，同时本地数据库中该商品会被删除。该操作不可逆！'
  const confirmOptions = isLocalDraft
    ? { title: '确认删除该商品？', description: confirmDesc }
    : { title: '确认删除该商品？', description: confirmDesc, dangerous: true, confirmText: 'DELETE' }
  if (!await confirmAction(confirmOptions)) return

  return withItemBusy(row, async () => {
    try {
      if (!isLocalDraft) {
        // 已发布到闲鱼：先调用闲鱼删除 API 下架商品
        const accountId = item.accountId || Number(query.xianyuAccountId)
        if (!accountId) return showNotice('warn', '请先选择账号')
        const xyGoodsId = item.externalGoodsId
        if (!xyGoodsId) return showNotice('warn', '缺少闲鱼商品ID')
        try {
          await remoteDeleteItem({ xianyuAccountId: accountId, xyGoodsId })
        } catch (e) {
          // 闲鱼下架失败：本地记录保留，便于用户重试或排查
          return showNotice('error', e.message || '闲鱼下架失败，本地商品保留')
        }
      }
      // 删除本地数据库中的商品记录
      try {
        await deleteGoodsLocal(item.id)
        showNotice('success', isLocalDraft ? '本地商品记录已删除' : '商品已从闲鱼下架，并删除本地记录')
        await loadItems()
        loadGoodsStats()
      } catch (e) {
        showNotice('error', e.message || '本地记录删除失败')
      }
    } catch (e) { showNotice('error', e.message || '删除失败') }
  })
}

/**
 * 批量删除商品：顺序逐个发起删除请求，复用现有单删端点。
 * - 本地草稿：直接 deleteGoodsLocal(item.id)
 * - 已发布商品：先 remoteDeleteItem(闲鱼API) 再 deleteGoodsLocal
 * 单个失败不影响后续，最终汇总成功/失败。
 */
async function batchDeleteProducts() {
  if (!selectedKeys.value.length || batchDeleting.value) return
  // 找出选中行（基于 raw.id）
  const selectedRows = products.value.filter(p => selectedKeys.value.includes(p.raw?.id))
  if (!selectedRows.length) {
    showNotice('warn', '未找到选中的商品（可能已切换页面）')
    selectedKeys.value = []
    return
  }

  const draftCount = selectedRows.filter(r => r.isLocalDraft).length
  const publishedCount = selectedRows.length - draftCount

  const desc = publishedCount > 0
    ? `选中 ${selectedRows.length} 件商品（已发布到闲鱼 ${publishedCount} 件，本地草稿 ${draftCount} 件）。已发布商品会先从闲鱼下架删除，再删除本地记录。该操作不可逆！`
    : `选中 ${selectedRows.length} 件本地草稿商品，删除后将从本地数据库移除。`
  const confirmOptions = publishedCount > 0
    ? { title: '确认批量删除选中商品？', description: desc, dangerous: true, confirmText: 'DELETE' }
    : { title: '确认批量删除选中商品？', description: desc }
  if (!await confirmAction(confirmOptions)) return

  batchDeleting.value = true
  batchDeleteState.active = true
  batchDeleteState.done = 0
  batchDeleteState.total = selectedRows.length
  batchDeleteState.current = ''
  batchDeleteState.result = null

  const failed = []
  const warnings = []  // 闲鱼下架失败但本地删除成功的商品
  let success = 0

  for (const row of selectedRows) {
    const item = row.raw || row
    batchDeleteState.current = shortText(item.title || row.name, 20)
    let remoteFailedReason = null
    try {
      if (!row.isLocalDraft) {
        // 已发布：先调闲鱼删除 API
        const accountId = item.accountId || row.xianyuAccountId
        const xyGoodsId = item.externalGoodsId
        if (accountId && xyGoodsId) {
          try {
            await remoteDeleteItem({ xianyuAccountId: accountId, xyGoodsId })
          } catch (e) {
            // 闲鱼删除失败：记录原因，但仍继续删除本地记录
            remoteFailedReason = e.message || '闲鱼下架失败'
          }
        } else {
          remoteFailedReason = '缺少账号或闲鱼商品ID'
        }
      }
      // 删除本地数据库记录
      try {
        await deleteGoodsLocal(item.id)
        success++
        if (remoteFailedReason) {
          warnings.push({ name: row.name, reason: remoteFailedReason })
        }
      } catch (e) {
        const reason = remoteFailedReason
          ? `${remoteFailedReason}；本地删除失败：${e.message || '未知错误'}`
          : (e.message || '本地删除失败')
        failed.push({ name: row.name, reason })
      }
    } catch (e) {
      failed.push({ name: row.name, reason: e.message || '删除失败' })
    }
    batchDeleteState.done++
  }

  batchDeleteState.active = false
  batchDeleteState.current = ''
  batchDeleteState.result = { success, failed, warnings }
  batchDeleting.value = false
  selectedKeys.value = []

  if (failed.length === 0) {
    const warnNote = warnings.length ? `（其中 ${warnings.length} 件闲鱼下架失败，已仅删除本地记录）` : ''
    showNotice('success', `批量删除完成，共删除 ${success} 件商品${warnNote}`)
  } else {
    showNotice('warn', `批量删除完成：成功 ${success} / 失败 ${failed.length}，悬停"查看失败详情"查看`)
  }
  await loadItems()
  loadGoodsStats()
}
function normalizePriceInput(value) {
  const raw = String(value || '').replace('¥', '').trim()
  if (!/^\d+(\.\d{1,2})?$/.test(raw)) return ''
  const num = Number(raw)
  if (!Number.isFinite(num) || num <= 0 || num > 9999999) return ''
  return raw
}
async function editPrice(row) {
  const input = await globalConfirm.prompt('请输入新价格，最多两位小数', '', String(row.price).replace('¥',''))
  if (input === false || input === null) return
  const price = normalizePriceInput(input)
  const accountId = row.xianyuAccountId || Number(query.xianyuAccountId)
  if (!accountId) return showNotice('warn', '请先选择账号')
  const xyGoodsId = row.xyGoodId
  if (!xyGoodsId || String(xyGoodsId).startsWith('local:')) return showNotice('warn', '本地草稿不能远程改价')
  return withItemBusy(row, async () => {
    try {
      await updateItemPrice({ xianyuAccountId: accountId, xyGoodsId, price })
      showNotice('success', '商品改价成功')
      await loadItems()
    } catch (e) { showNotice('error', e.message || '改价失败') }
  })
}
async function editStock(row) {
  const raw = await globalConfirm.prompt('请输入库存数量，必须为0或正整数', '', String(row.stock))
  if (raw === false || raw === null) return
  const normalized = String(raw).trim()
  if (!/^\d+$/.test(normalized) || Number(normalized) > 999999) return showNotice('warn', '库存必须为0到999999之间的整数')
  try { await updateGoods(row.raw.id, { stock: normalized, quantity: Number(normalized) }); showNotice('success', '库存更新成功'); await loadItems() } catch(e){ showNotice('error', e.message || '库存更新失败') }
}
async function loadDetail(row) {
  try {
    const res = await getGoodsDetail(row.raw?.id || row.id)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) {
      throw new Error('商品详情响应格式异常')
    }
    selected.value = { ...row, raw: res.data }
  } catch(e) {
    showNotice('error', e.message || '详情加载失败')
  }
}
function onHeader(e){ if(e.detail === 'sync-products') syncProducts() }

// localStorage 键名常量
const LS_LAST_SYNC_TIME = 'xianyu_last_sync_time'
const LS_PENDING_SYNC = 'xianyu_pending_sync'
// 同步冷却期：3 小时（毫秒）
const SYNC_COOLDOWN_MS = 3 * 60 * 60 * 1000

async function autoTriggerSync() {
  // 自动触发同步：进入页面或切换账号时调用，不阻止用户操作
  if (!query.xianyuAccountId) {
    // 没有选中账号时正常加载已有数据
    loadItems()
    loadGoodsStats()
    return
  }

  // 检查是否有待同步标记（用户在其他页面发布了商品）
  const hasPendingSync = localStorage.getItem(LS_PENDING_SYNC) === 'true'

  if (!hasPendingSync) {
    // 检查冷却期：3 小时内同步过则跳过
    const lastSyncTime = localStorage.getItem(LS_LAST_SYNC_TIME)
    if (lastSyncTime) {
      const elapsed = Date.now() - Number(lastSyncTime)
      if (elapsed < SYNC_COOLDOWN_MS) {
        // 冷却期内：直接加载已有商品数据，不触发自动同步
        loadItems()
        loadGoodsStats()
        return
      }
    }
  }

  // 清除待同步标记
  localStorage.removeItem(LS_PENDING_SYNC)

  // 重置自动同步状态
  autoSyncState.active = true
  autoSyncState.completed = false
  autoSyncState.error = ''
  autoSyncState.progress = 0
  autoSyncState.summary = emptySyncSummary()
  // 清空原有商品数据，避免展示历史数据
  items.value = []
  totalCount.value = 0
  await syncProducts(true)
}

async function syncProducts(isAuto = false, overrideAccountId = null){
  if (syncing.value) return
  if (!overrideAccountId && !accountsAvailable.value) {
    showNotice('error', accountsLoadError.value || '账号状态不可用，当前无法同步商品')
    return
  }
  const accountId = overrideAccountId || query.xianyuAccountId
  // 未选账号（全部账号）：
  //   - 自动触发（isAuto=true）：进页面/切账号自动同步，不跑全账号（太重），仅加载已有数据
  //   - 手动点击按钮：顺序同步所有账号
  if(!accountId) {
    if (isAuto) {
      loadItems()
      return
    }
    return syncAllAccounts()
  }
  // 已选账号：单账号同步
  clearNotice()
  syncing.value = true
  syncPollCanceled = false
  // 统一使用 autoSyncState 横幅展示进度，避免 showNotice 频繁替换导致的闪烁
  autoSyncState.active = true
  autoSyncState.completed = false
  autoSyncState.error = ''
  autoSyncState.progress = 0
  autoSyncState.summary = emptySyncSummary()
  autoSyncState.accountIndex = 0
  autoSyncState.accountTotal = 0
  autoSyncState.accountLabel = ''
  autoSyncState.failedAccounts = []
  try {
    const res = await refreshItems({ xianyuAccountId: Number(accountId) })
    const syncId = res.data?.syncId || res.data?.sync_id
    if (syncId) {
      syncTask.value = { id: syncId, status: 'running', progress: 0 }
      // manageLifecycle=true：单账号同步由 pollSyncProgress 管理 active/completed/error
      await pollSyncProgress(syncId, true)
    } else {
      autoSyncState.active = false
      autoSyncState.completed = false
      autoSyncState.error = '同步请求已受理，但服务未返回任务标识，当前无法确认执行状态。请查看任务历史或重试。'
      showNotice('warn', autoSyncState.error)
    }
  } catch(e) {
    autoSyncState.active = false
    autoSyncState.error = e.message || '同步请求失败'
    showNotice('error', e.message || '同步请求失败')
  }
  finally {
    if (!syncPollCanceled) {
      // 同步完成后重置到第1页
      query.pageNum = 1
      // 同步完成后加载商品列表，用 try/catch 防止超时错误冒泡为未处理异常
      try {
        await loadItems({ excludeStatus: 3 })
        // 前端二次过滤：确保已删除(status=3)的商品不展示
        items.value = items.value.filter(item => Number(item.status ?? 1) !== 3)
      } catch(e) {
        console.warn('[ProductsPage] 同步后加载商品列表失败', e)
      }
      try {
        await loadSyncTasks()
      } catch(e) {
        console.warn('[ProductsPage] 同步后加载任务历史失败', e)
      }
      loadGoodsStats()
    }
    syncing.value = false
  }
}

/**
 * 顺序同步所有账号：账号1完成后再同步账号2，避免并发调用闲鱼API触发风控。
 * 汇总各账号结果，单账号失败不影响后续账号。
 */
async function syncAllAccounts() {
  const accountList = accounts.value
  if (!accountsAvailable.value) {
    showNotice('error', accountsLoadError.value || '账号状态不可用，当前无法同步商品')
    return
  }
  if (!accountList || !accountList.length) {
    showNotice('warn', '没有可同步的账号')
    return
  }
  if (syncing.value) return
  clearNotice()
  syncing.value = true
  syncPollCanceled = false

  autoSyncState.active = true
  autoSyncState.completed = false
  autoSyncState.error = ''
  autoSyncState.progress = 0
  autoSyncState.summary = emptySyncSummary()
  autoSyncState.accountIndex = 0
  autoSyncState.accountTotal = accountList.length
  autoSyncState.accountLabel = ''
  autoSyncState.failedAccounts = []
  // 清空原数据避免与同步过程混淆
  items.value = []
  totalCount.value = 0

  const totalSummary = { total: 0, new: 0, updated: 0, offShelf: 0, duration: 0 }
  let successfulAccounts = 0

  try {
    for (let i = 0; i < accountList.length; i++) {
      if (syncPollCanceled) break
      const acc = accountList[i]
      const label = accountName(acc) || `账号 ${acc.id}`
      autoSyncState.accountIndex = i + 1
      autoSyncState.accountLabel = label
      // 不重置 progress 为 0，保留上一账号进度作为起点，避免进度回退闪烁
      try {
        const res = await refreshItems({ xianyuAccountId: Number(acc.id) })
        const syncId = res.data?.syncId || res.data?.sync_id
        if (syncId) {
          syncTask.value = { id: syncId, status: 'running', progress: 0 }
          // manageLifecycle=false：仅更新进度，由 syncAllAccounts 管理 active/completed/error
          const summary = await pollSyncProgress(syncId, false)
          if (summary) {
            successfulAccounts++
            totalSummary.total += summary.total
            totalSummary.new += summary.new
            totalSummary.updated += summary.updated
            totalSummary.offShelf += summary.offShelf
            totalSummary.duration += summary.duration
          }
        } else {
          autoSyncState.failedAccounts.push({ label, reason: '未返回 syncId' })
        }
      } catch (e) {
        autoSyncState.failedAccounts.push({ label, reason: e.message || '同步失败' })
      }
    }

    autoSyncState.active = false
    autoSyncState.completed = autoSyncState.failedAccounts.length === 0 && successfulAccounts === accountList.length
    autoSyncState.progress = autoSyncState.completed ? 100 : autoSyncState.progress
    autoSyncState.summary = successfulAccounts > 0 ? totalSummary : emptySyncSummary()
    if (autoSyncState.failedAccounts.length > 0) {
      autoSyncState.error = `${autoSyncState.failedAccounts.length} 个账号同步失败，${successfulAccounts} 个成功：${autoSyncState.failedAccounts.map(f => `${f.label}（${f.reason}）`).join('、')}`
    }
    if (autoSyncState.completed) {
      localStorage.setItem(LS_LAST_SYNC_TIME, String(Date.now()))
      localStorage.removeItem(LS_PENDING_SYNC)
    }
  } finally {
    if (!syncPollCanceled) {
      query.pageNum = 1
      // 用 try/catch 防止超时错误冒泡为未处理异常
      try {
        await loadItems({ excludeStatus: 3 })
        items.value = items.value.filter(item => Number(item.status ?? 1) !== 3)
      } catch(e) {
        console.warn('[ProductsPage] 全账号同步后加载商品列表失败', e)
      }
      try {
        await loadSyncTasks()
      } catch(e) {
        console.warn('[ProductsPage] 全账号同步后加载任务历史失败', e)
      }
      loadGoodsStats()
    }
    syncing.value = false
  }
}

async function pollSyncProgress(syncId, manageLifecycle = true) {
  let retries = 0
  let consecutiveQueryFailures = 0
  const maxRetries = 120
  while (retries < maxRetries && !syncPollCanceled) {
    await new Promise(r => setTimeout(r, 2000))
    if (syncPollCanceled) return null
    retries++
    let res
    try {
      res = await getSyncProgress(syncId)
      consecutiveQueryFailures = 0
    } catch(e) {
      consecutiveQueryFailures++
      console.warn('[ProductsPage] 同步进度查询失败', e)
      if (consecutiveQueryFailures >= 3) {
        throw new Error(`同步状态连续查询失败：${e?.message || '服务不可用'}`, { cause: e })
      }
      continue
    }

    const progress = res?.data
    if (!progress || typeof progress !== 'object' || Array.isArray(progress)) {
      throw new Error('同步进度响应格式异常')
    }
    const status = progress.status
    const knownStatuses = ['queued', 'running', 'completed', 'failed', 'cancelled', 'not_found']
    if (!knownStatuses.includes(status)) throw new Error('同步进度缺少有效任务状态')
    const pct = Number(progress.progress)
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) throw new Error('同步进度数值异常')
    syncTask.value = { id: syncId, status, progress: pct }
    if (!manageLifecycle && autoSyncState.accountTotal > 1) {
      autoSyncState.progress = Math.round((((autoSyncState.accountIndex - 1) * 100) + pct) / autoSyncState.accountTotal)
    } else {
      autoSyncState.progress = pct
    }

    if (status === 'completed') {
      const fields = {
        total: progress.total,
        new: progress.new,
        updated: progress.updated,
        offShelf: progress.off_shelf,
        duration: progress.duration_seconds
      }
      const summary = Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, Number(value)]))
      if (Object.values(summary).some(value => !Number.isFinite(value) || value < 0)) {
        throw new Error('同步完成结果缺少有效统计')
      }
      if (manageLifecycle) {
        localStorage.setItem(LS_LAST_SYNC_TIME, String(Date.now()))
        localStorage.removeItem(LS_PENDING_SYNC)
        autoSyncState.active = false
        autoSyncState.completed = true
        autoSyncState.progress = 100
        autoSyncState.summary = summary
      }
      return summary
    }
    if (status === 'failed') {
      throw new Error(progress.error || '同步任务执行失败')
    }
    if (status === 'cancelled') {
      throw new Error(progress.error || '同步任务已取消')
    }
    if (status === 'not_found') {
      throw new Error('同步任务不存在或已过期')
    }
  }
  if (syncPollCanceled) return null
  throw new Error('同步状态查询超时，请刷新页面查看任务历史')
}
// 跳转到自动发货配置页面
const goToAutoDelivery = () => {
  emit('navigate', 'auto-delivery')
}
onMounted(()=>{ window.addEventListener('xya-header-action', onHeader); init() })
onBeforeUnmount(()=>{ syncPollCanceled = true; window.removeEventListener('xya-header-action', onHeader) })
</script>
<style scoped>
.products-page {
  display: flex;
  gap: 16px;
  width: 100%;
  min-width: 0;
  /* 视口确定高度：让 .products-main 成为内部滚动容器，drawer 作为 flex 兄弟自然常驻可见。
     偏移 = main padding-top(22) + PageHeader(62) + main padding-bottom(20) = 104px */
  max-height: calc(100vh - 104px);
  min-height: 360px;
}
.products-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding-right: 4px;
}
.products-stat-grid {
  margin-bottom: 16px;
}
.products-table-card {
  min-width: 0;
}
.products-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 14px;
  flex-wrap: wrap;
}
.toolbar-filter {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}
.filter-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.toolbar-select {
  width: 140px;
  flex-shrink: 0;
}
.filter-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 280px;
}
.products-search-input {
  flex: 1;
  min-width: 0;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.tabs.products-tabs {
  margin: 0;
  border-bottom: none;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: #f1f5fb;
  border-radius: 9px;
  padding: 3px;
}
.tabs.products-tabs .tab {
  border: none;
  border-radius: 7px;
  padding: 6px 14px;
  height: auto;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  background: transparent;
  transition: all 0.15s;
  white-space: nowrap;
}
.tabs.products-tabs .tab:hover {
  color: #1e40af;
  background: rgba(255,255,255,0.6);
}
.tabs.products-tabs .tab.active {
  color: #1d4ed8;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  font-weight: 600;
}

.table-scroll-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: 10px;
}
.products-table {
  min-width: 1064px;
  table-layout: fixed;
}
.products-table :deep(th),
.products-table :deep(td) {
  white-space: nowrap;
}
.products-table :deep(th) {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
  background: #f8fafc;
}
.products-table :deep(th:nth-child(1)) { width: 44px; text-align: center; } /* 选择列 */
.products-table :deep(th:nth-child(2)) { width: 280px; text-align: left; }   /* 商品信息 */
.products-table :deep(th:nth-child(3)) { width: 80px; text-align: right; }    /* 价格 */
.products-table :deep(th:nth-child(4)) { width: 60px; text-align: center; }
.products-table :deep(th:nth-child(5)) { width: 60px; text-align: center; }
.products-table :deep(th:nth-child(6)) { width: 90px; text-align: center; }
.products-table :deep(th:nth-child(7)) { width: 110px; text-align: center; }
.products-table :deep(th:nth-child(8)) { width: 78px; text-align: center; }
.products-table :deep(th:nth-child(9)) { width: 78px; text-align: center; }
.products-table :deep(th:nth-child(10)) { width: 78px; text-align: center; }
.products-table :deep(th:nth-child(11)) { width: 140px; text-align: center; }
.products-table :deep(th:nth-child(12)) { width: 160px; text-align: center; }

.products-table :deep(td:nth-child(1)) { text-align: center; } /* 选择列 */
.products-table :deep(td:nth-child(2)) { text-align: left; }
.products-table :deep(td:nth-child(3)) { text-align: right; }
.products-table :deep(td:nth-child(4)),
.products-table :deep(td:nth-child(5)),
.products-table :deep(td:nth-child(6)),
.products-table :deep(td:nth-child(7)),
.products-table :deep(td:nth-child(8)),
.products-table :deep(td:nth-child(9)),
.products-table :deep(td:nth-child(10)),
.products-table :deep(td:nth-child(11)) { text-align: center; }
.products-table :deep(td:nth-child(12)) { text-align: center; }

.products-table :deep(tbody tr) { cursor: pointer; }
.products-table :deep(tbody tr.row-selected) { background: #eef5ff; box-shadow: inset 3px 0 0 #2563eb; }
.products-table :deep(tbody tr.row-selected:hover) { background: #e0edff; }
.products-table :deep(tbody tr:hover td) { background: #f5f9ff; }

.cell-center {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
.cell-price {
  font-weight: 600;
  color: #ef4444;
  font-size: 14px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.cell-muted {
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.op-buttons {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  justify-content: center;
}
.op-buttons .link {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 13px;
  transition: background 0.15s;
}
.op-buttons .link:hover {
  background: #eef2ff;
}
.op-buttons .link.danger-text:hover {
  background: #fef2f2;
}
.op-buttons .link:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  overflow: hidden;
}
.product-thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: linear-gradient(135deg, #f5f7fb, #dfe9f8);
  border: 1px solid #eef2f7;
}
.product-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}
.product-info-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
.product-info-text strong {
  font-size: 13.5px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 210px;
  line-height: 1.4;
}
.product-info-text em {
  font-size: 12px;
  color: #94a3b8;
  font-style: normal;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delivery-type-configurable {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
  transition: background 0.15s;
  white-space: nowrap;
}
.delivery-type-configurable:hover {
  background: rgba(255, 125, 0, 0.1);
}
.delivery-type-configurable .config-hint {
  font-size: 12px;
  color: #f59e0b;
  font-weight: 500;
  white-space: nowrap;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  font-size: 13px;
  color: #64748b;
  flex-wrap: wrap;
}
.products-pagination .pagination-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.page-size-label {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}
.page-size-select {
  width: 88px;
  height: 32px;
  padding: 0 8px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  color: #1e293b;
  cursor: pointer;
}
.page-size-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.page-size-unit {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}
.products-pagination .pagination-right {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.pagination-total {
  font-size: 13px;
  color: #64748b;
  margin-right: 8px;
  white-space: nowrap;
}
.page-no {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
  user-select: none;
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #475569;
}
.page-no:hover:not(:disabled) {
  background: #eef2ff;
  color: #2563eb;
  border-color: #c7d6f5;
}
.page-no.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.page-no:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  background: #f8fafc;
}
.page-ellipsis {
  min-width: 24px;
  text-align: center;
  color: #94a3b8;
  user-select: none;
}

@media (max-width: 768px) {
  .products-pagination {
    justify-content: center;
  }
}

.products-drawer {
  /* 高度跟随内容：align-self: flex-start 取消默认 stretch，底部贴合内容而非页面底部 */
  align-self: flex-start;
  /* 宽度由内容自适应，不固定 */
  width: fit-content;
  min-width: 300px;
  max-width: 380px;
  flex-shrink: 0;
  /* 常驻可见：.products-main 内部滚动（非 body 滚动），drawer 作为 flex 兄弟自然固定在右侧；
     内容过多时 drawer 内部滚动，不超出 .products-page 高度 */
  max-height: 100%;
  overflow-y: auto;
  background: #fff;
  border: 1px solid var(--line, #e5eaf2);
  border-radius: 14px;
  box-shadow: var(--shadow, 0 1px 3px rgba(0,0,0,0.04));
  padding: 16px;
}
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.drawer-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.drawer-close {
  width: 30px;
  height: 30px;
  border: none;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 18px;
  cursor: pointer;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.drawer-close:hover {
  background: #e2e8f0;
  color: #1e293b;
}
.preview-card {
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 12px;
  border: 1px solid #eef2f7;
}
.drawer-title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.5;
}
.drawer-price {
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.drawer-card {
  margin-bottom: 12px;
}
.drawer-metrics {
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}
.metric-tile {
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 8px;
  text-align: center;
  border: 1px solid #eef2f7;
}
.metric-tile span {
  font-size: 12px;
  color: #94a3b8;
  display: block;
}
.metric-tile b {
  font-size: 13px;
  margin-top: 4px;
  display: block;
  color: #1e293b;
}
.metric-tile b.text-green { color: #10b981; }
.metric-tile b.text-gray { color: #94a3b8; }
.drawer-actions {
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.drawer-actions :deep(button) {
  width: 100%;
}

.global-notice {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.products-table :deep(.badge.purple) {
  background: #f4efff;
  color: #7c3aed;
}

@media (max-width: 1280px) {
  .products-stat-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 1200px) {
  .products-drawer {
    min-width: 280px;
    max-width: 320px;
  }
}
@media (max-width: 1100px) {
  .toolbar-filter {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .filter-left {
    flex-wrap: wrap;
  }
  .filter-search {
    min-width: 0;
  }
}
@media (max-width: 900px) {
  .products-page {
    flex-direction: column;
    /* 移动端堆叠布局：取消视口高度限制，恢复内容高度 + body 滚动 */
    max-height: none;
    min-height: 0;
  }
  .products-drawer {
    /* 移动端：恢复全宽自适应，不限制高度 */
    width: 100%;
    min-width: 0;
    max-width: none;
    max-height: none;
  }
  .products-stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
