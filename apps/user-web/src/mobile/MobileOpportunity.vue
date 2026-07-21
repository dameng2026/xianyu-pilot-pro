<template>
  <div class="m-opp">
    <!-- 顶部搜索区 -->
    <div class="m-opp-search-card">
      <div class="m-opp-mode-row">
        <button
          v-for="opt in searchModeOptions"
          :key="opt.value"
          class="m-opp-mode-chip"
          :class="{ active: searchMode === opt.value }"
          @click="searchMode = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="m-opp-search-row">
        <MIcon name="search" :size="18" class="m-opp-search-icon" />
        <input
          v-model="keyword"
          type="text"
          class="m-opp-search-input"
          placeholder="输入商品关键词，例如 iPhone 15、露营车"
          @keyup.enter="doSearch"
        />
        <button v-if="keyword" class="m-opp-search-clear" @click="clearKeyword" aria-label="清空">
          <MIcon name="x" :size="16" />
        </button>
      </div>
      <button
        class="m-opp-search-btn"
        :disabled="searchLoading || !accountAvailable"
        @click="doSearch"
      >
        {{ searchLoading ? '搜索中...' : '开始搜索' }}
      </button>
      <div v-if="!accountAvailable && accountLoaded" class="m-opp-account-warn">
        <MIcon name="warning" :size="14" />
        <span>{{ accountLoadError || '闲鱼账号不可用，请先到「账号管理」添加可用账号' }}</span>
      </div>
      <div v-if="hotTags.length" class="m-opp-hot-tags">
        <span class="m-opp-hot-label">热门：</span>
        <button
          v-for="t in hotTags"
          :key="t"
          class="m-opp-hot-chip"
          @click="clickTag(t)"
        >{{ t }}</button>
        <button class="m-opp-hot-chip m-opp-hot-rotate" @click="rotateTags">换一换</button>
      </div>
    </div>

    <!-- 全局错误提示 -->
    <div v-if="error" class="m-opp-notice m-opp-notice-error">
      <MIcon name="xCircle" :size="16" />
      <span>{{ error }}</span>
    </div>
    <div v-if="saveMessage" class="m-opp-notice m-opp-notice-success">
      <MIcon name="checkCircle" :size="16" />
      <span>{{ saveMessage }}</span>
    </div>

    <!-- 统计信息 -->
    <div v-if="stats" class="m-opp-stats">
      <div class="m-opp-stat">
        <span class="m-opp-stat-label">热度</span>
        <b class="m-opp-stat-value">{{ stats.searchHeat }}</b>
      </div>
      <div class="m-opp-stat">
        <span class="m-opp-stat-label">商品总数</span>
        <b class="m-opp-stat-value">{{ stats.totalCount }}</b>
      </div>
      <div class="m-opp-stat">
        <span class="m-opp-stat-label">想要人数</span>
        <b class="m-opp-stat-value">{{ stats.wantTotal }}</b>
      </div>
      <div class="m-opp-stat">
        <span class="m-opp-stat-label">竞争度</span>
        <b class="m-opp-stat-value">{{ stats.competition }}</b>
      </div>
    </div>

    <!-- 搜索模式提示 -->
    <div v-if="usedSearchMode" class="m-opp-mode-tip">
      实际使用：{{ usedSearchMode === 'fast' ? '快速搜索' : '慢速搜索' }}
    </div>

    <!-- 内容区 -->
    <div v-if="searchLoading" class="m-opp-loading">
      <div class="m-opp-spinner"></div>
      <p>正在搜索商品...</p>
    </div>

    <div v-else-if="!searched" class="m-opp-empty">
      <div class="m-opp-empty-icon">
        <MIcon name="search" :size="48" />
      </div>
      <div class="m-opp-empty-title">开始发掘商机</div>
      <div class="m-opp-empty-desc">输入关键词搜索闲鱼商品，发现潜在商机并 AI 改写</div>
    </div>

    <div v-else-if="!items.length" class="m-opp-empty">
      <div class="m-opp-empty-icon">
        <MIcon name="info" :size="48" />
      </div>
      <div class="m-opp-empty-title">未找到相关商品</div>
      <div class="m-opp-empty-desc">请尝试其他关键词或检查账号状态</div>
    </div>

    <template v-else>
      <div class="m-opp-list-info">
        <span>共 {{ totalItems }} 个商品，第 {{ currentPage }}/{{ totalPages }} 页</span>
        <button class="m-opp-reset-btn" @click="resetView">重置</button>
      </div>

      <div class="m-opp-list">
        <div
          v-for="(item, idx) in items"
          :key="(item.link || item.itemId || '') + idx"
          class="m-opp-card"
          :class="{ active: isSelected(item) }"
          @click="toggleSelect(item)"
        >
          <div class="m-opp-card-checkbox" :class="{ checked: isSelected(item) }">
            <MIcon v-if="isSelected(item)" name="check" :size="14" />
          </div>
          <div class="m-opp-card-cover">
            <img
              v-if="item.image"
              :src="item.image"
              :alt="item.title"
              loading="lazy"
              @error="onImgError"
            />
            <div v-else class="m-opp-card-cover-empty">
              <MIcon name="image" :size="20" />
            </div>
          </div>
          <div class="m-opp-card-info">
            <div class="m-opp-card-title" :title="item.title">{{ item.title }}</div>
            <div class="m-opp-card-price">¥{{ item.price || '—' }}</div>
            <div class="m-opp-card-meta">
              <span v-if="item.seller" class="m-opp-meta-chip">{{ item.seller }}</span>
              <span v-if="item.area" class="m-opp-meta-chip">{{ item.area }}</span>
              <span v-if="item.soldCount" class="m-opp-meta-chip">已售{{ item.soldCount }}</span>
            </div>
            <a
              v-if="item.link"
              :href="item.link"
              target="_blank"
              rel="noopener noreferrer"
              class="m-opp-card-link"
              @click.stop
            >查看链接</a>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="totalItems > pageSize" class="m-opp-pagination">
        <button
          class="m-opp-page-btn"
          :disabled="currentPage <= 1 || searchLoading"
          @click="goToPage(currentPage - 1)"
        >
          <MIcon name="chevronLeft" :size="16" />
          上一页
        </button>
        <span class="m-opp-page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button
          class="m-opp-page-btn"
          :disabled="!hasMore || searchLoading"
          @click="loadMore"
        >
          下一页
          <MIcon name="chevronRight" :size="16" />
        </button>
      </div>
    </template>

    <!-- 底部批量操作栏 -->
    <div v-if="selectedItems.length" class="m-opp-action-bar">
      <div class="m-opp-action-info">
        已选 <b>{{ selectedItems.length }}</b> 项
        <button class="m-opp-action-clear" @click="clearSelection">清空</button>
      </div>
      <button
        class="m-opp-rewrite-btn"
        :disabled="rewriteLoading || !selectedItems.length"
        @click="openRewriteSheet"
      >
        <MIcon name="edit" :size="16" />
        {{ rewriteLoading ? '改写中...' : 'AI 改写' }}
      </button>
    </div>

    <!-- 改写底部弹层 -->
    <div v-if="rewriteSheetVisible" class="m-opp-sheet-mask" @click="closeRewriteSheet"></div>
    <div v-if="rewriteSheetVisible" class="m-opp-sheet">
      <div class="m-opp-sheet-header">
        <span class="m-opp-sheet-title">AI 改写</span>
        <button class="m-opp-sheet-close" @click="closeRewriteSheet" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-opp-sheet-body">
        <!-- 当前改写目标 -->
        <div v-if="rewriteTarget" class="m-opp-rewrite-target">
          <div class="m-opp-rewrite-target-cover">
            <img
              v-if="rewriteTarget.image"
              :src="rewriteTarget.image"
              :alt="rewriteTarget.title"
            />
            <div v-else class="m-opp-card-cover-empty">
              <MIcon name="image" :size="18" />
            </div>
          </div>
          <div class="m-opp-rewrite-target-info">
            <div class="m-opp-rewrite-target-title">{{ rewriteTarget.title }}</div>
            <div class="m-opp-rewrite-target-price">¥{{ rewriteTarget.price || '—' }}</div>
          </div>
        </div>

        <!-- 风格选择 -->
        <div class="m-opp-field">
          <label class="m-opp-field-label">改写风格</label>
          <select v-model="rewriteStyle" class="m-opp-select">
            <option value="friendly">口语化风格</option>
            <option value="concise">简洁风格</option>
            <option value="click">吸引眼球风格</option>
            <option value="custom">自定义风格</option>
          </select>
        </div>
        <div v-if="rewriteStyle === 'custom'" class="m-opp-field">
          <label class="m-opp-field-label">自定义提示词</label>
          <textarea
            v-model="rewriteCustomPrompt"
            class="m-opp-textarea"
            placeholder="请输入你希望的改写要求，例如：请用更加活泼亲切的语气改写，可以适当使用网络流行语。"
          ></textarea>
        </div>

        <!-- AI 状态提示 -->
        <div v-if="aiStatusLoadError" class="m-opp-ai-tip m-opp-ai-tip-warn">
          AI 改写状态获取失败，点击"开始改写"会自动重试。
        </div>
        <div v-else-if="!aiStatusLoading && !aiStatus.rewriteEnabled" class="m-opp-ai-tip m-opp-ai-tip-warn">
          平台暂未开放 AI 改写功能，敬请期待
        </div>

        <!-- 改写结果 -->
        <div v-if="rewriteDraft" class="m-opp-rewrite-result">
          <div class="m-opp-field">
            <label class="m-opp-field-label">
              标题
              <span class="m-opp-char-count">{{ (rewriteDraft.title || '').length }}/30</span>
            </label>
            <input
              :value="rewriteDraft.title"
              maxlength="30"
              class="m-opp-input"
              @input="updateRewriteTitle"
            />
          </div>
          <div class="m-opp-field">
            <label class="m-opp-field-label">正文</label>
            <textarea
              :value="rewriteDraft.description"
              class="m-opp-textarea m-opp-textarea-tall"
              @input="updateRewriteDescription"
            ></textarea>
          </div>
          <div v-if="rewriteDraft.tags && rewriteDraft.tags.length" class="m-opp-rewrite-tags">
            <span class="m-opp-field-label">标签：</span>
            <span class="m-opp-tag">{{ rewriteDraft.tags.join('、') }}</span>
          </div>
          <div v-if="rewriteDraft.safety" class="m-opp-rewrite-safety" :class="{ blocked: rewriteDraft.safety.blocked }">
            <MIcon :name="rewriteDraft.safety.blocked ? 'warning' : 'checkCircle'" :size="14" />
            <span>{{ rewriteDraft.safety.message || '-' }}</span>
          </div>
          <div class="m-opp-rewrite-actions">
            <button class="m-opp-btn m-opp-btn-outline" @click="copyRewriteResult">复制结果</button>
            <button
              class="m-opp-btn m-opp-btn-primary"
              :disabled="rewriteLoading"
              @click="rewriteSelected"
            >{{ rewriteLoading ? '改写中...' : '重新改写' }}</button>
          </div>
        </div>

        <!-- 改写按钮（首次） -->
        <button
          v-else
          class="m-opp-btn m-opp-btn-primary m-opp-btn-block"
          :disabled="rewriteLoading || !shouldEnableRewriteAction"
          @click="handleRewriteAction"
        >
          {{ rewriteLoading ? '改写中...' : '开始改写' }}
        </button>
        <p v-if="!rewriteDraft" class="m-opp-rewrite-tip">
          选择商品后点击 AI 改写，生成可编辑标题和描述。改写前会校验 Token 余额。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import { goofishSearch } from '../api/misc.js'
import { rewriteOpportunity, getOpportunityAiStatus } from '../api/opportunity.js'
import { ensureAiTokenBalance } from '../utils/aiTokenGuard.js'
import { getLiteAccounts, checkAccountAuth } from '../api/accounts.js'
import { accountAuthUsable, pickPreferredAccount, accountLoginHint } from '../utils/accountAuth.js'
import { friendlyError } from '../utils/friendlyError.js'
import { buildOpportunityRewritePayload, getOpportunityItemIdentity, shouldEnableOpportunityRewriteAction } from '../utils/opportunityPageState.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

// ===== 搜索状态 =====
const keyword = ref('')
const error = ref('')
const saveMessage = ref('')
const searchLoading = ref(false)
const searched = ref(false)
const items = ref([])
const searchMode = ref('auto') // fast / slow / auto
const usedSearchMode = ref('')
const currentPage = ref(1)
const totalItems = ref(0)
const hasMore = ref(false)
const searchKeyword = ref('')
const pageSize = 20

const searchModeOptions = [
  { value: 'auto', label: '智能' },
  { value: 'fast', label: '快速' },
  { value: 'slow', label: '慢速' }
]

// ===== 账号状态 =====
const accounts = ref([])
const accountLoaded = ref(false)
const accountAvailable = ref(false)
const accountLoadError = ref('')
const selectedAccountId = ref(null)

// ===== 多选状态 =====
const selectedItems = ref([])

// ===== AI 改写状态 =====
const rewriteLoading = ref(false)
const rewriteDraft = ref(null)
const rewriteStyle = ref('friendly')
const rewriteCustomPrompt = ref('')
const rewriteTarget = ref(null)
const rewriteSheetVisible = ref(false)
let rewriteRequestVersion = 0

const DEFAULT_AI_STATUS = { configured: null, rewriteEnabled: null, imageConfigured: null }
const aiStatus = ref({ ...DEFAULT_AI_STATUS })
const aiStatusLoading = ref(false)
const aiStatusLoadError = ref('')

// ===== 热门关键词 =====
const tagPools = [
  ['iPhone 17 Pro Max', '小米17', '华为Mate 80', 'Switch 2', '开放式耳机', 'AI录音笔', '大疆运动相机', '苹果快充套装'],
  ['LABUBU', '谷子吧唧', '骑行装备', '露营折叠车', '扫地机器人', '宠物烘干箱', '婴儿推车', '电动滑板车'],
  ['机械键盘套件', '电竞显示器', '筋膜枪', '咖啡机', '投影仪', '二手相机', '户外电源', '猫砂盆']
]
const tagIndex = ref(0)
const hotTags = ref([...tagPools[0]])

// ===== 计算属性 =====
const totalPages = computed(() => {
  const total = totalItems.value || items.value.length
  return Math.max(1, Math.ceil(total / pageSize))
})

const stats = computed(() => {
  if (!items.value.length) return null
  const total = Number(totalItems.value || items.value.length)
  const local = items.value
  const wantValues = local.map(item => numberLike(item.wantCount)).filter(v => v !== null)
  const soldValues = local.map(item => numberLike(item.soldCount)).filter(v => v !== null)
  const want = wantValues.reduce((sum, v) => sum + v, 0)
  const sold = soldValues.reduce((sum, v) => sum + v, 0)
  const sellerCount = new Set(local.map(item => item.seller).filter(Boolean)).size
  const prices = local.map(item => numberLike(item.price)).filter(n => n !== null && n > 0)
  const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : 0
  const cheapCount = avgPrice ? prices.filter(p => p <= avgPrice * 0.85).length : 0
  const heatScore = want + sold * 2 + total
  const competitionScore = sellerCount + Math.min(total, 50) + Math.max(0, prices.length - cheapCount)
  const heatAvailable = wantValues.length === local.length && soldValues.length === local.length
  const competitionAvailable = local.every(item => String(item.seller || '').trim()) && prices.length === local.length
  return {
    searchHeat: heatAvailable ? (heatScore > 120 ? '高' : heatScore > 40 ? '中' : '低') : '数据不足',
    totalCount: total,
    wantTotal: wantValues.length === local.length ? formatNum(want) : '—',
    competition: competitionAvailable ? (competitionScore > 65 ? '激烈' : competitionScore > 28 ? '中等' : '较低') : '数据不足'
  }
})

const currentAccountId = computed(() => {
  const currentAccount = accounts.value.find(account => String(account?.id ?? '') === String(selectedAccountId.value ?? '')) || null
  if (currentAccount && accountAuthUsable(currentAccount)) {
    return selectedAccountId.value
  }
  return pickPreferredAccount(accounts.value, selectedAccountId.value)?.id || null
})

const shouldEnableRewriteAction = computed(() => shouldEnableOpportunityRewriteAction({
  rewriteLoading: rewriteLoading.value,
  aiStatusLoading: aiStatusLoading.value
}))

// ===== 工具函数 =====
function numberLike(value) {
  if (value === null || value === undefined || value === '') return null
  const raw = String(value ?? '').replace(/[¥￥,人想要已售\s]/g, '')
  const n = Number(raw)
  return Number.isFinite(n) && n >= 0 ? n : null
}

function formatNum(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function extractOpportunityItems(data, errorMessage = '商品搜索响应格式异常') {
  const list = Array.isArray(data)
    ? data
    : Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data?.list)
        ? data.list
        : Array.isArray(data?.data)
          ? data.data
          : null
  if (!Array.isArray(list)) throw new Error(errorMessage)
  return list
}

function opportunitySearchResultOf(response, errorMessage = '商品搜索响应格式异常') {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(errorMessage)
  const itemsList = extractOpportunityItems(data, errorMessage)
  const total = Number(data.total)
  if (!Number.isFinite(total) || total < 0 || typeof data.hasMore !== 'boolean') throw new Error(errorMessage)
  return { data, items: itemsList, total }
}

function normalizeOpportunityItem(item) {
  return {
    title: item.title || item.name || '无标题商品',
    price: item.price || item.soldPrice || item.currentPrice || '',
    image: item.imageUrl || item.image || item.picUrl || item.coverPic || item.mainImageUrl || '',
    link: item.pcUrl || item.itemUrl || item.link || item.url || '',
    itemId: item.itemId || item.externalGoodsId || '',
    description: item.description || item.desc || '',
    seller: item.seller || item.userNick || '',
    area: item.area || item.location || '',
    soldCount: item.soldCount ?? null,
    wantCount: item.wantCount ?? item.want ?? item.wantNum ?? null,
    status: item.status ?? item.itemStatus ?? null
  }
}

function onImgError(e) {
  if (e?.target) {
    e.target.style.display = 'none'
  }
}

// ===== 账号加载 =====
async function loadAccounts() {
  accountLoaded.value = false
  accountAvailable.value = false
  accountLoadError.value = ''
  accounts.value = []
  try {
    const res = await getLiteAccounts({ size: 200 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    const preferredAccount = pickPreferredAccount(accounts.value, selectedAccountId.value)
    if (preferredAccount && !selectedAccountId.value) {
      selectedAccountId.value = preferredAccount.id
    }
    if (!selectedAccountId.value && accounts.value.length) {
      selectedAccountId.value = accounts.value[0].id
    }
    accountAvailable.value = true
    return true
  } catch (e) {
    selectedAccountId.value = null
    accountLoadError.value = e?.message || '账号列表加载失败'
    return false
  } finally {
    accountLoaded.value = true
  }
}

async function refreshAccountAuthStatus(accountId) {
  if (!accountId) return null
  try {
    const res = await checkAccountAuth(accountId)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.usable !== 'boolean') {
      throw new Error('账号鉴权状态响应格式异常')
    }
    const account = accounts.value.find(item => item.id === accountId)
    if (account) {
      account.cookieStatus = data.cookieStatus
      account.authUsable = data.usable
      account.loginStatusCode = data.loginStatusCode
      account.loginStatusMessage = data.loginStatusMessage
      account.loginCheckTime = data.checkedAt
    }
    return data
  } catch (_e) {
    return null
  }
}

async function ensureLoggedXianyuAccount() {
  if (!accountLoaded.value) {
    const maxWait = 6000
    const start = Date.now()
    while (!accountLoaded.value && Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 150))
    }
    if (!accountLoaded.value) {
      error.value = '闲鱼账号状态加载中，请稍后再试'
      return false
    }
  }
  if (!accountAvailable.value) {
    error.value = accountLoadError.value || '闲鱼账号状态加载失败，请重试后再搜索'
    return false
  }
  if (!accounts.value.length) {
    error.value = '商机发掘需要先登录闲鱼账号。请先到「账号管理」扫码添加账号后再使用。'
    return false
  }
  const preferred = pickPreferredAccount(accounts.value, selectedAccountId.value)
  if (!preferred) {
    error.value = '未选择有效的闲鱼账号，请到「账号管理」扫码登录后再使用'
    return false
  }
  const authStatus = await refreshAccountAuthStatus(preferred.id)
  if (!authStatus) {
    if (!accountAuthUsable(preferred)) {
      error.value = '无法确认闲鱼账号登录状态，请检查网络后重试'
      return false
    }
    return true
  }
  const refreshed = accounts.value.find(item => item.id === preferred.id)
  if (refreshed && !accountAuthUsable(refreshed)) {
    const accountLabel = refreshed.nickname || refreshed.displayName || refreshed.externalUid || ('账号' + refreshed.id)
    error.value = `账号「${accountLabel}」Cookie 已失效（${accountLoginHint(refreshed)}），请到「账号管理」重新登录后再使用`
    return false
  }
  return true
}

// ===== 搜索 =====
async function doSearch() {
  searchLoading.value = true
  try {
    if (!(await ensureLoggedXianyuAccount())) return
    const q = keyword.value.trim()
    if (!q) {
      error.value = '请输入搜索关键词'
      return
    }
    if (/^https?:\/\//i.test(q)) {
      error.value = '请输入商品关键词，不要输入链接'
      return
    }
    if (q.length > 50) {
      error.value = '关键词长度不能超过 50 个字符'
      return
    }
    error.value = ''
    items.value = []
    searched.value = false
    selectedItems.value = []
    currentPage.value = 1
    totalItems.value = 0
    hasMore.value = false
    searchKeyword.value = q

    const res = await goofishSearch(q, 1, pageSize, currentAccountId.value, searchMode.value)
    const { data, items: list, total } = opportunitySearchResultOf(res)
    items.value = list.map(normalizeOpportunityItem)
    totalItems.value = total
    hasMore.value = data.hasMore
    usedSearchMode.value = typeof data.searchMode === 'string' ? data.searchMode : ''
    searched.value = true

    if (!items.value.length) {
      if (typeof data.warning === 'string' && data.warning.trim()) {
        error.value = data.warning.trim()
      } else if (typeof data.fastFallbackReason === 'string' && data.fastFallbackReason.trim()) {
        error.value = data.fastFallbackReason.trim()
      } else {
        error.value = '未搜索到商品，请更换关键词或稍后重试'
      }
    }
  } catch (e) {
    error.value = friendlyError(e, '商品搜索失败，请稍后重试')
    items.value = []
    if (e && (e.code === 409 || /Cookie.*失效|登录状态.*失效|_m_h5_tk/.test(String(e.message || '')))) {
      try {
        const preferred = pickPreferredAccount(accounts.value, selectedAccountId.value)
        if (preferred && preferred.id) {
          await refreshAccountAuthStatus(preferred.id)
        }
      } catch (_e) {}
    }
  } finally {
    searchLoading.value = false
  }
}

async function goToPage(page) {
  if (!searchKeyword.value || searchLoading.value) return
  searchLoading.value = true
  error.value = ''
  selectedItems.value = []
  try {
    const res = await goofishSearch(searchKeyword.value, page, pageSize, currentAccountId.value, searchMode.value)
    const { data, items: list, total } = opportunitySearchResultOf(res, '商品翻页响应格式异常')
    items.value = list.map(normalizeOpportunityItem)
    totalItems.value = total
    hasMore.value = data.hasMore
    usedSearchMode.value = typeof data.searchMode === 'string' ? data.searchMode : ''
    currentPage.value = page
  } catch (e) {
    error.value = friendlyError(e, '翻页加载失败，请稍后重试')
  } finally {
    searchLoading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value) return
  await goToPage(currentPage.value + 1)
}

function resetView() {
  keyword.value = ''
  items.value = []
  selectedItems.value = []
  searched.value = false
  error.value = ''
  saveMessage.value = ''
  currentPage.value = 1
  totalItems.value = 0
  hasMore.value = false
  usedSearchMode.value = ''
  searchKeyword.value = ''
  rewriteDraft.value = null
  rewriteTarget.value = null
  rewriteSheetVisible.value = false
}

function clearKeyword() {
  keyword.value = ''
}

function rotateTags() {
  tagIndex.value = (tagIndex.value + 1) % tagPools.length
  hotTags.value = [...tagPools[tagIndex.value]]
}

function clickTag(t) {
  keyword.value = t
  doSearch()
}

// ===== 多选 =====
function isSelected(item) {
  const id = getOpportunityItemIdentity(item)
  return selectedItems.value.some(s => getOpportunityItemIdentity(s) === id)
}

function toggleSelect(item) {
  const id = getOpportunityItemIdentity(item)
  const idx = selectedItems.value.findIndex(s => getOpportunityItemIdentity(s) === id)
  if (idx >= 0) {
    selectedItems.value.splice(idx, 1)
  } else {
    selectedItems.value.push(item)
  }
}

function clearSelection() {
  selectedItems.value = []
}

// ===== AI 改写 =====
async function refreshAiStatus() {
  if (aiStatusLoading.value) return
  aiStatusLoading.value = true
  aiStatusLoadError.value = ''
  aiStatus.value = { ...DEFAULT_AI_STATUS }
  try {
    const res = await getOpportunityAiStatus()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)
      || typeof data.configured !== 'boolean'
      || typeof data.rewriteEnabled !== 'boolean'
      || typeof data.imageConfigured !== 'boolean') {
      throw new Error('AI 功能状态响应格式异常')
    }
    aiStatus.value = { ...DEFAULT_AI_STATUS, ...data }
  } catch (e) {
    aiStatusLoadError.value = friendlyError(e, 'AI 改写状态获取失败，请稍后重试')
  } finally {
    aiStatusLoading.value = false
  }
}

function openRewriteSheet() {
  if (!selectedItems.value.length) {
    error.value = '请先选择商品'
    return
  }
  rewriteTarget.value = selectedItems.value[selectedItems.value.length - 1]
  rewriteDraft.value = null
  rewriteSheetVisible.value = true
  error.value = ''
  saveMessage.value = ''
  if (aiStatus.value.rewriteEnabled === null && !aiStatusLoadError.value) {
    refreshAiStatus()
  }
}

function closeRewriteSheet() {
  rewriteSheetVisible.value = false
}

async function handleRewriteAction() {
  if (aiStatusLoadError.value || !aiStatus.value.rewriteEnabled) {
    await refreshAiStatus()
  }
  if (!aiStatus.value.rewriteEnabled) {
    error.value = aiStatusLoadError.value || '平台暂未开放 AI 改写功能，敬请期待'
    return
  }
  await rewriteSelected()
}

async function rewriteSelected() {
  if (!rewriteTarget.value) {
    error.value = '请先选择商品'
    return
  }
  const requestVersion = ++rewriteRequestVersion
  const sourceItemKey = getOpportunityItemIdentity(rewriteTarget.value)
  const payload = buildOpportunityRewritePayload({
    selectedItem: rewriteTarget.value,
    rewriteDraft: rewriteDraft.value,
    keyword: searchKeyword.value || keyword.value,
    style: rewriteStyle.value,
    customPrompt: rewriteCustomPrompt.value
  })
  rewriteLoading.value = true
  error.value = ''
  try {
    // 强制规则：调用通用模型前必须先校验 Token 余额
    if (!(await ensureAiTokenBalance({ sceneName: '商机改写' }))) return

    const res = await rewriteOpportunity(payload)
    const data = res?.data
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(rewriteTarget.value)) return
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('AI 改写响应格式异常，请重试')
    }
    if (typeof data.ok !== 'boolean') throw new Error('AI 改写响应缺少成功状态')
    if (data.ok === false || data.error) {
      error.value = data.error || data.message || 'AI改写失败'
      return
    }
    if (!data.rewrite || typeof data.rewrite !== 'object' || Array.isArray(data.rewrite)
      || typeof data.rewrite.title !== 'string' || !data.rewrite.title.trim()
      || typeof data.rewrite.description !== 'string' || !data.rewrite.description.trim()) {
      error.value = data.message || 'AI改写失败，请重试'
      return
    }
    if (!Number.isFinite(Number(data.draftId)) || Number(data.draftId) <= 0 || data.saved !== true) {
      throw new Error('AI 改写结果未确认保存，原文已保留')
    }
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(rewriteTarget.value)) return

    const draft = { ...data.rewrite, draftId: data.draftId }
    if (draft.title && draft.title.length > 30) {
      draft.title = draft.title.slice(0, 30)
    }
    // 与 PC 端一致：标题 + "。" + 正文
    if (draft.title && draft.description) {
      draft.description = draft.title + '。' + draft.description
    }
    rewriteDraft.value = draft
    saveMessage.value = 'AI 改写完成，可在下方编辑后复制使用'
  } catch (e) {
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(rewriteTarget.value)) return
    error.value = friendlyError(e, 'AI改写失败')
  } finally {
    if (requestVersion === rewriteRequestVersion) {
      rewriteLoading.value = false
    }
  }
}

function updateRewriteTitle(e) {
  if (!rewriteDraft.value) return
  rewriteDraft.value.title = e.target.value.slice(0, 30)
}

function updateRewriteDescription(e) {
  if (!rewriteDraft.value) return
  rewriteDraft.value.description = e.target.value
}

async function copyRewriteResult() {
  if (!rewriteDraft.value) return
  const text = `${rewriteDraft.value.title || ''}\n\n${rewriteDraft.value.description || ''}`.trim()
  try {
    await navigator.clipboard.writeText(text)
    saveMessage.value = '改写结果已复制到剪贴板'
  } catch (_e) {
    saveMessage.value = '请手动复制结果'
  }
}

onMounted(async () => {
  await Promise.all([loadAccounts(), refreshAiStatus()])
})
</script>

<style scoped>
.m-opp {
  padding: 12px 12px 100px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100%;
  box-sizing: border-box;
}

/* 搜索卡片 */
.m-opp-search-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 2px 12px rgba(31, 53, 94, 0.05);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-opp-mode-row {
  display: flex;
  gap: 6px;
  background: #f5f7fb;
  border-radius: 10px;
  padding: 3px;
}
.m-opp-mode-chip {
  flex: 1;
  border: none;
  background: transparent;
  color: #5a6a85;
  font-size: 13px;
  font-weight: 600;
  padding: 7px 0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.m-opp-mode-chip.active {
  background: white;
  color: #0d6bff;
  box-shadow: 0 1px 4px rgba(13, 107, 255, 0.12);
}
.m-opp-search-row {
  display: flex;
  align-items: center;
  background: #f5f7fb;
  border-radius: 10px;
  padding: 0 12px;
  height: 44px;
  gap: 8px;
  border: 1px solid transparent;
}
.m-opp-search-row:focus-within {
  border-color: #0d6bff;
  background: white;
}
.m-opp-search-icon {
  color: #94a3b8;
  flex-shrink: 0;
}
.m-opp-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: #15213d;
  min-width: 0;
}
.m-opp-search-input::placeholder {
  color: #94a3b8;
}
.m-opp-search-clear {
  border: none;
  background: none;
  color: #94a3b8;
  padding: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-opp-search-btn {
  height: 44px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-opp-search-btn:disabled {
  background: #c0c8d6;
  box-shadow: none;
  cursor: not-allowed;
}
.m-opp-search-btn:active:not(:disabled) {
  transform: scale(0.98);
}
.m-opp-account-warn {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #ef4444;
  font-size: 12px;
  background: #fef2f2;
  padding: 8px 10px;
  border-radius: 8px;
}
.m-opp-hot-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.m-opp-hot-label {
  font-size: 12px;
  color: #8a96aa;
  font-weight: 600;
}
.m-opp-hot-chip {
  border: none;
  background: #eef4ff;
  color: #0d6bff;
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
}
.m-opp-hot-chip:active {
  background: #dbeafe;
}
.m-opp-hot-rotate {
  background: #f5f7fb;
  color: #5a6a85;
}

/* 全局通知 */
.m-opp-notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.5;
}
.m-opp-notice-error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.m-opp-notice-success {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

/* 统计信息 */
.m-opp-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.m-opp-stat {
  background: white;
  border-radius: 10px;
  padding: 10px 6px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(31, 53, 94, 0.04);
}
.m-opp-stat-label {
  display: block;
  font-size: 11px;
  color: #8a96aa;
  margin-bottom: 4px;
}
.m-opp-stat-value {
  font-size: 15px;
  color: #15213d;
  font-weight: 700;
}

.m-opp-mode-tip {
  font-size: 12px;
  color: #0d6bff;
  background: #eef4ff;
  padding: 6px 10px;
  border-radius: 8px;
  text-align: center;
  font-weight: 600;
}

/* 加载与空状态 */
.m-opp-loading {
  text-align: center;
  padding: 60px 0;
  color: #8a96aa;
}
.m-opp-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #eef3fa;
  border-top-color: #0d6bff;
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: m-opp-spin 0.7s linear infinite;
}
@keyframes m-opp-spin {
  to { transform: rotate(360deg); }
}
.m-opp-empty {
  text-align: center;
  padding: 60px 20px;
}
.m-opp-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #f5f7fb;
  color: #c0c8d6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.m-opp-empty-title {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 6px;
}
.m-opp-empty-desc {
  font-size: 13px;
  color: #8a96aa;
  line-height: 1.6;
}

/* 列表 */
.m-opp-list-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #8a96aa;
  padding: 4px 4px 0;
}
.m-opp-reset-btn {
  border: 1px solid #e0e6ed;
  background: white;
  color: #5a6a85;
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.m-opp-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-opp-card {
  display: flex;
  align-items: stretch;
  gap: 10px;
  background: white;
  border-radius: 12px;
  padding: 10px;
  box-shadow: 0 1px 6px rgba(31, 53, 94, 0.04);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}
.m-opp-card.active {
  border-color: #0d6bff;
  background: #f7fbff;
}
.m-opp-card-checkbox {
  width: 22px;
  height: 22px;
  border: 2px solid #d8dee9;
  border-radius: 6px;
  flex-shrink: 0;
  margin-top: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  color: white;
  transition: all 0.15s;
}
.m-opp-card-checkbox.checked {
  background: #0d6bff;
  border-color: #0d6bff;
}
.m-opp-card-cover {
  width: 84px;
  height: 84px;
  border-radius: 10px;
  background: #f5f7fb;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c8d6;
}
.m-opp-card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-opp-card-cover-empty {
  color: #c0c8d6;
}
.m-opp-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-opp-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.m-opp-card-price {
  font-size: 16px;
  font-weight: 800;
  color: #ef4444;
}
.m-opp-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.m-opp-meta-chip {
  font-size: 11px;
  color: #5a6a85;
  background: #f5f7fb;
  padding: 2px 6px;
  border-radius: 4px;
}
.m-opp-card-link {
  font-size: 11px;
  color: #0d6bff;
  text-decoration: none;
  margin-top: 2px;
  align-self: flex-start;
}

/* 分页 */
.m-opp-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 0;
}
.m-opp-page-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #e0e6ed;
  background: white;
  color: #15213d;
  font-size: 13px;
  padding: 7px 14px;
  border-radius: 8px;
  cursor: pointer;
}
.m-opp-page-btn:disabled {
  color: #c0c8d6;
  background: #f5f7fb;
  cursor: not-allowed;
}
.m-opp-page-info {
  font-size: 13px;
  color: #5a6a85;
  min-width: 70px;
  text-align: center;
}

/* 底部操作栏 */
.m-opp-action-bar {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(12px + env(safe-area-inset-bottom));
  background: white;
  border-radius: 14px;
  box-shadow: 0 4px 24px rgba(31, 53, 94, 0.12);
  padding: 10px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  z-index: 90;
}
.m-opp-action-info {
  font-size: 13px;
  color: #5a6a85;
  display: flex;
  align-items: center;
  gap: 6px;
}
.m-opp-action-info b {
  color: #0d6bff;
  font-size: 15px;
}
.m-opp-action-clear {
  border: none;
  background: #f5f7fb;
  color: #5a6a85;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  margin-left: 4px;
}
.m-opp-rewrite-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 14px;
  font-weight: 700;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}
.m-opp-rewrite-btn:disabled {
  background: #c0c8d6;
  box-shadow: none;
  cursor: not-allowed;
}

/* 改写底部弹层 */
.m-opp-sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 25, 50, 0.45);
  z-index: 200;
  animation: m-opp-fade-in 0.2s ease;
}
@keyframes m-opp-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.m-opp-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 88vh;
  background: white;
  border-radius: 18px 18px 0 0;
  z-index: 201;
  display: flex;
  flex-direction: column;
  animation: m-opp-slide-up 0.25s ease;
  padding-bottom: env(safe-area-inset-bottom);
}
@keyframes m-opp-slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.m-opp-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 10px;
  border-bottom: 1px solid #f0f4fa;
}
.m-opp-sheet-title {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-opp-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f5f7fb;
  color: #5a6a85;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.m-opp-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.m-opp-rewrite-target {
  display: flex;
  gap: 10px;
  align-items: center;
  background: #f7fbff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 10px;
}
.m-opp-rewrite-target-cover {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  background: #f5f7fb;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-opp-rewrite-target-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-opp-rewrite-target-info {
  flex: 1;
  min-width: 0;
}
.m-opp-rewrite-target-title {
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.m-opp-rewrite-target-price {
  font-size: 14px;
  font-weight: 800;
  color: #ef4444;
  margin-top: 4px;
}

.m-opp-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.m-opp-field-label {
  font-size: 13px;
  font-weight: 600;
  color: #1f2a44;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-opp-char-count {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 400;
}
.m-opp-select,
.m-opp-input {
  height: 42px;
  border: 1px solid #e0e6ed;
  border-radius: 10px;
  background: white;
  padding: 0 12px;
  font-size: 14px;
  color: #15213d;
  outline: none;
}
.m-opp-select:focus,
.m-opp-input:focus {
  border-color: #0d6bff;
}
.m-opp-textarea {
  border: 1px solid #e0e6ed;
  border-radius: 10px;
  background: white;
  padding: 10px 12px;
  font-size: 14px;
  color: #15213d;
  outline: none;
  min-height: 80px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
}
.m-opp-textarea:focus {
  border-color: #0d6bff;
}
.m-opp-textarea-tall {
  min-height: 140px;
}

.m-opp-ai-tip {
  font-size: 13px;
  padding: 10px 12px;
  border-radius: 10px;
  line-height: 1.5;
}
.m-opp-ai-tip-warn {
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fde68a;
}

.m-opp-rewrite-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #f7fbff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 12px;
}
.m-opp-rewrite-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: #5a6a85;
}
.m-opp-tag {
  background: white;
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
  color: #15213d;
}
.m-opp-rewrite-safety {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 8px;
  background: #ecfdf5;
  color: #059669;
}
.m-opp-rewrite-safety.blocked {
  background: #fef2f2;
  color: #dc2626;
}
.m-opp-rewrite-actions {
  display: flex;
  gap: 8px;
}
.m-opp-btn {
  flex: 1;
  height: 42px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.m-opp-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-opp-btn-primary:disabled {
  background: #c0c8d6;
  box-shadow: none;
  cursor: not-allowed;
}
.m-opp-btn-outline {
  background: white;
  color: #0d6bff;
  border: 1px solid #0d6bff;
}
.m-opp-btn-block {
  width: 100%;
}
.m-opp-rewrite-tip {
  font-size: 12px;
  color: #8a96aa;
  line-height: 1.6;
  text-align: center;
  margin: 0;
}

@media (max-width: 360px) {
  .m-opp-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  .m-opp-card-cover {
    width: 72px;
    height: 72px;
  }
}
</style>
