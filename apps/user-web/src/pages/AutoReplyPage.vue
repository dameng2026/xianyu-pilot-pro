<template>
  <div class="auto-reply-shell">
    <div v-if="loadErrorItems.length" class="global-notice error auto-reply-error-summary" role="alert">
      <strong>{{ loadErrorItems.length > 1 ? '部分自动回复数据暂时不可用' : `${loadErrorItems[0].label}不可用` }}</strong>
      <p>
        {{ loadErrorItems.length > 1
          ? `${loadErrorItems.length} 项数据加载失败，相关修改操作已安全禁用。`
          : loadErrorItems[0].message }}
      </p>
      <details v-if="loadErrorItems.length > 1">
        <summary>查看失败项目</summary>
        <ul>
          <li v-for="item in loadErrorItems" :key="item.label">{{ item.label }}：{{ item.message }}</li>
        </ul>
      </details>
    </div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <section class="auto-reply-hero">
      <div class="auto-reply-hero-head">
        <div class="auto-reply-hero-copy">
          <span class="auto-reply-hero-pill">Auto Reply Console</span>
          <h1>自动回复</h1>
          <p>
            把账号范围、商品范围和 AI 客服摘要收拢到一个主工作台里，让“选哪里生效”和“为什么生效”在同一
            屏完成理解。
          </p>
        </div>

        <div class="auto-reply-hero-actions">
          <button type="button" class="auto-reply-action-button" :disabled="isRefreshing" @click="refreshCurrentScope">
            <span class="auto-reply-button-dot"></span>
            {{ isRefreshing ? '同步中...' : '同步当前范围' }}
          </button>
          <button type="button" class="auto-reply-action-button primary" @click="goToAiCsSettings">
            <span class="auto-reply-button-dot"></span>
            前往 AI 客服配置
          </button>
        </div>
      </div>

      <div class="auto-reply-hero-main">
        <span class="auto-reply-hero-kicker">运行概览</span>
        <h2>集中查看并管理自动回复生效范围</h2>
        <p>
          左侧选择账号与商品，右侧查看当前作用域、启用状态和 AI 配置摘要；只有状态完整加载后才允许修改。
        </p>

        <div class="auto-reply-hero-pill-row">
          <span v-for="pill in heroPills" :key="pill">{{ pill }}</span>
        </div>

        <div class="auto-reply-hero-metrics">
          <article
            v-for="card in heroMetricCards"
            :key="card.label"
            class="auto-reply-hero-metric"
          >
            <b>{{ card.value }}</b>
            <span>{{ card.detail }}</span>
          </article>
        </div>
      </div>

      <aside class="auto-reply-hero-side">
        <div class="auto-reply-hero-side-top">
          <div>
            <h3>当前作用域</h3>
            <strong>{{ selectedAccountSummary.title }}</strong>
          </div>

          <label class="auto-reply-switch auto-reply-switch-large">
            <input type="checkbox" :checked="currentScopeEnabled === true" :disabled="!scopeWritable" @change="toggleCurrentScope" />
            <span class="auto-reply-slider"></span>
          </label>
        </div>

        <span class="auto-reply-side-pill">启用自动回复</span>

        <div class="auto-reply-side-note">
          <strong>本页负责范围与主开关联动</strong>
          <p>
            AI 客服的话术、知识库与聊天规则仍在「AI 客服配置」统一维护，这里会同步处理真正影响是否回消息的启用链路。
          </p>
        </div>

        <div class="auto-reply-side-list">
          <div class="auto-reply-side-item">
            <div>
              <b>作用层级</b>
              <strong>全局 → 账号 → 商品</strong>
            </div>
            <span class="auto-reply-status-chip blue">可继承</span>
          </div>

          <div class="auto-reply-side-item">
            <div>
              <b>批量选择</b>
              <strong>{{ selectedProductSummary.title }}</strong>
            </div>
            <span class="auto-reply-status-chip green">{{ selectedProductSummary.tag }}</span>
          </div>

          <div class="auto-reply-side-item">
            <div>
              <b>风险提醒</b>
              <strong>{{ riskSummaryText }}</strong>
            </div>
            <span class="auto-reply-status-chip amber">{{ riskSummaryTag }}</span>
          </div>
        </div>
      </aside>
    </section>

    <section class="auto-reply-workspace">
      <div class="auto-reply-left-column">
        <section class="auto-reply-panel auto-reply-account-panel">
          <div class="auto-reply-panel-head">
            <div>
              <h3>账号范围</h3>
              <p>先决定这次操作面向哪些账号，再继续细化到商品。</p>
            </div>
            <span class="auto-reply-tiny-chip">{{ accountsAvailable ? `${accountCards.length - 1} 个账号` : '账号状态未知' }}</span>
          </div>

          <div class="auto-reply-panel-body auto-reply-account-list">
            <button
              v-for="card in accountCards"
              :key="card.key"
              type="button"
              class="auto-reply-account-item"
              :class="{ active: card.active }"
              :disabled="!accountsAvailable"
              @click="selectAccount(card.id)"
            >
              <div class="auto-reply-account-row">
                <div class="auto-reply-account-main">
                  <span class="auto-reply-account-badge" :class="{ 'is-all': card.isAll, 'has-avatar': !!card.avatarUrl }">
                    <svg v-if="card.isAll" class="auto-reply-account-icon" viewBox="0 0 24 24" aria-hidden="true">
                      <circle cx="9" cy="8" r="3.2" />
                      <path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5" stroke-linecap="round" stroke-linejoin="round" />
                      <circle cx="16.5" cy="9" r="2.6" />
                      <path d="M14 18.5c0-2.4 1.8-4 4-4s4 1.6 4 4" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <img v-else-if="card.avatarUrl" :src="card.avatarUrl" alt="" class="auto-reply-account-avatar" @error="onAvatarError(card)" />
                    <template v-else>{{ card.badge }}</template>
                  </span>
                  <div>
                    <strong>{{ card.name }}</strong>
                    <span>{{ card.description }}</span>
                  </div>
                </div>
                <span class="auto-reply-status-pill" :class="card.statusTone">{{ card.status }}</span>
              </div>

              <div v-if="card.showMetrics" class="auto-reply-account-stats">
                <div v-for="metric in card.metrics" :key="metric.label" class="auto-reply-mini-stat">
                  <b>{{ metric.value }}</b>
                  <span>{{ metric.label }}</span>
                </div>
              </div>
            </button>
          </div>
        </section>

        <section class="auto-reply-panel auto-reply-product-panel">
          <div class="auto-reply-panel-head">
            <div>
              <h3>商品范围</h3>
              <p>搜索、筛选并批量选择商品，决定哪些咨询会进入自动回复。</p>
            </div>
            <span class="auto-reply-tiny-chip">{{ productsAvailable ? `${products.length} 个商品` : '商品状态未知' }}</span>
          </div>

          <div class="auto-reply-product-toolbar">
            <div class="auto-reply-search-row">
              <label class="auto-reply-search">
                <span class="auto-reply-search-icon"></span>
                <input v-model="productSearch" type="text" :disabled="!productsAvailable" placeholder="搜索商品标题、关键词或店铺标签" />
              </label>

              <button
                type="button"
                class="auto-reply-action-button primary"
                :disabled="!scopeWritable || batchUpdating || !products.length"
                @click="batchEnableAllProducts"
              >
                {{ batchUpdating ? '处理中...' : '一键全部开启' }}
              </button>
            </div>

            <div class="auto-reply-filter-row">
              <button
                v-for="option in productFilterOptions"
                :key="option.value"
                type="button"
                class="auto-reply-filter-chip"
                :class="{ active: productFilter === option.value }"
                :disabled="!productsAvailable || !scopeAvailable"
                @click="productFilter = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <div v-if="productsLoading" class="auto-reply-loading">商品加载中...</div>
          <div v-else-if="!productsAvailable" class="auto-reply-empty">商品范围加载失败，当前状态不可判断，请点击“同步当前范围”重试。</div>
          <div v-else-if="!filteredProducts.length" class="auto-reply-empty">当前筛选条件下暂无商品</div>
          <div v-else class="auto-reply-product-list">
            <button
              v-for="product in pagedFilteredProducts"
              :key="product.id"
              type="button"
              class="auto-reply-product-item"
              :class="{ selected: selectedProductIds.includes(product.id) }"
              @click="toggleProductSelect(product.id)"
            >
              <div class="auto-reply-product-top">
                <span class="auto-reply-checkbox" :class="{ checked: selectedProductIds.includes(product.id) }"></span>
                <div class="auto-reply-product-body">
                  <strong :title="product.title">{{ shortText(product.title, 36) }}</strong>
                  <div class="auto-reply-product-meta">
                    <span class="auto-reply-meta-badge" :class="productPrimaryStatus(product).tone">
                      {{ productPrimaryStatus(product).label }}
                    </span>
                    <span v-if="productSecondaryStatus(product)" class="auto-reply-meta-badge" :class="productSecondaryStatus(product).tone">
                      {{ productSecondaryStatus(product).label }}
                    </span>
                    <span class="auto-reply-meta-badge gray">
                      {{ accountLabelForProduct(product) }}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          </div>

          <div v-if="filteredProducts.length > productVisibleLimit" class="auto-reply-load-more">
            <button type="button" class="ghost" @click="productVisibleLimit += 50">显示更多（剩余 {{ filteredProducts.length - productVisibleLimit }} 条）</button>
          </div>

          <div v-if="selectedProductIds.length" class="auto-reply-selection-bar">
            <div>
              <strong>{{ selectedProductSummary.title }}</strong>
              <span>{{ selectedProductSummary.description }}</span>
            </div>

            <div class="auto-reply-selection-actions">
              <button
                type="button"
                class="ghost"
                :disabled="!scopeWritable || batchUpdating"
                @click.stop="batchUpdateProducts(false)"
              >
                批量关闭
              </button>
              <button
                type="button"
                class="fill"
                :disabled="!scopeWritable || batchUpdating"
                @click.stop="batchUpdateProducts(true)"
              >
                批量开启
              </button>
            </div>
          </div>
        </section>
      </div>

      <div class="auto-reply-right-column">
        <section class="auto-reply-panel auto-reply-strategy-panel">
          <div class="auto-reply-panel-head">
            <div>
              <h3>自动回复策略</h3>
              <p>聚焦当前作用域的启用状态、继承关系和生效摘要，用户不需要在左右信息块之间来回跳读。</p>
            </div>
            <span class="auto-reply-tiny-chip">当前生效</span>
          </div>

          <div class="auto-reply-panel-body auto-reply-strategy-body">
            <div class="auto-reply-strategy-top">
              <div class="auto-reply-strategy-copy">
                <h4>{{ strategyHeadline }}</h4>
                <p>{{ strategyDescription }}</p>

                <div class="auto-reply-insight-row">
                  <span class="auto-reply-insight-chip">{{ currentScopeBadge }}</span>
                  <span class="auto-reply-insight-chip">{{ selectedProductBadge }}</span>
                  <span class="auto-reply-insight-chip">{{ knowledgeBaseBadge }}</span>
                </div>
              </div>

              <div class="auto-reply-toggle-box">
                <b>总开关</b>
                <label class="auto-reply-switch">
                  <input type="checkbox" :checked="currentScopeEnabled === true" :disabled="!scopeWritable" @change="toggleCurrentScope" />
                  <span class="auto-reply-slider"></span>
                </label>
                <strong>{{ currentScopeEnabled === true ? '启用中' : currentScopeEnabled === false ? '未启用' : '状态未知' }}</strong>
              </div>
            </div>

            <div class="auto-reply-metric-grid">
              <article
                v-for="card in scopeOverviewCards"
                :key="card.label"
                class="auto-reply-metric-card"
              >
                <b :class="card.tone">{{ card.label }}</b>
                <strong>{{ card.value }}</strong>
                <span>{{ card.detail }}</span>
              </article>
            </div>
          </div>
        </section>

        <div class="auto-reply-detail-grid">
          <section class="auto-reply-panel auto-reply-summary-panel">
            <div class="auto-reply-panel-head">
              <div>
                <h3>AI 客服配置摘要</h3>
                <p>保持只读摘要，不在这里直接改 Prompt，保证内容配置入口单一。</p>
              </div>
              <span class="auto-reply-tiny-chip">只读预览</span>
            </div>

            <div v-if="aiSummaryAvailable" class="auto-reply-panel-body auto-reply-summary-body">
              <div class="auto-reply-summary-block">
                <label>系统提示词</label>
                <p>{{ shortText(aiCsSummary.systemPrompt || '未配置系统提示词', 180) }}</p>
              </div>

              <div class="auto-reply-summary-block">
                <label>欢迎语</label>
                <p>{{ shortText(aiCsSummary.welcomeMessage || '未配置欢迎语', 140) }}</p>
              </div>

              <div class="auto-reply-summary-block">
                <label>知识库</label>
                <p>{{ aiKnowledgeBaseSummary }}</p>
              </div>

              <div class="auto-reply-summary-block">
                <label>聊天规则</label>
                <p>{{ aiChatRuleSummary }}</p>
              </div>
            </div>
            <div v-else class="auto-reply-loading">{{ aiSummaryError || 'AI 客服摘要加载中...' }}</div>

            <div class="auto-reply-summary-footer">
              <button type="button" class="auto-reply-action-button primary full" @click="goToAiCsSettings">
                <span class="auto-reply-button-dot"></span>
                前往 AI 客服配置修改
              </button>
            </div>
          </section>

          <div class="auto-reply-side-stack">
            <section class="auto-reply-panel auto-reply-logic-panel">
              <div class="auto-reply-panel-head">
                <div>
                  <h3>生效逻辑</h3>
                  <p>把层级关系讲清楚，减少“为什么这个商品没生效”的疑问。</p>
                </div>
              </div>

              <div class="auto-reply-panel-body auto-reply-logic-body">
                <div
                  v-for="step in logicSteps"
                  :key="step.step"
                  class="auto-reply-logic-step"
                  :data-step="step.step"
                >
                  <strong>{{ step.title }}</strong>
                  <span>{{ step.detail }}</span>
                </div>
              </div>
            </section>

            <section class="auto-reply-panel auto-reply-impact-panel">
              <div class="auto-reply-panel-head">
                <div>
                  <h3>当前影响面</h3>
                  <p>用运营语言说明这次切换具体会波及什么。</p>
                </div>
              </div>

              <div class="auto-reply-panel-body auto-reply-impact-body">
                <div
                  v-for="row in impactRows"
                  :key="row.label"
                  class="auto-reply-impact-row"
                >
                  <div>
                    <strong>{{ row.label }}</strong>
                    <span>{{ row.detail }}</span>
                  </div>
                  <div class="auto-reply-impact-value">{{ row.value }}</div>
                </div>

                <div class="auto-reply-impact-note">
                  <strong>操作说明</strong>
                  修改仅在后端明确返回成功后更新本页状态；任一关键配置加载失败时，写操作会保持禁用。
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getAutoReplyScopeProducts, getAutoReplyScopeStatus, updateProductAutoReplyScope, updateAccountAutoReplyScope, batchUpdateAutoReplyScope } from '../api/autoReplyScope.js'
import { getBusinessSettings, saveBusinessSettings } from '../api/businessSettings.js'
import { accountName, shortText } from '../utils/format.js'
import { confirmAction } from '../utils/confirmAction.js'
import { useDebouncedRef } from '../composables/useDebouncedRef.js'
import { friendlyError } from '../utils/friendlyError.js'

const emit = defineEmits(['navigate'])

const accounts = ref([])
const brokenAvatarIds = ref(new Set())
const selectedAccountId = ref('')
const selectedProductIds = ref([])
const products = ref([])
const allProductsCache = ref([])
const productsLoading = ref(false)
const productSearch = ref('')
const debouncedProductSearch = useDebouncedRef(productSearch, 300)
const productFilter = ref('all')
const accountScopeStatus = ref({})
const globalEnabled = ref(null)
const aiCsSummary = ref(null)
const accountsAvailable = ref(false)
const scopeAvailable = ref(false)
const productsAvailable = ref(false)
const aiSummaryAvailable = ref(false)
const accountsError = ref('')
const scopeError = ref('')
const productsError = ref('')
const aiSummaryError = ref('')
const batchUpdating = ref(false)
const isRefreshing = ref(false)
const error = ref('')
const success = ref('')
const loadErrorItems = computed(() => [
  { label: '自动回复服务', message: error.value },
  { label: '账号范围', message: accountsError.value },
  { label: '自动回复作用域', message: scopeError.value },
  { label: '商品范围', message: productsError.value },
  { label: 'AI 客服摘要', message: aiSummaryError.value }
].filter((item) => String(item.message || '').trim()))
const scopeWritable = computed(() => accountsAvailable.value && scopeAvailable.value && productsAvailable.value && aiSummaryAvailable.value)

const productFilterOptions = [
  { value: 'all', label: '全部' },
  { value: 'enabled', label: '已开启' },
  { value: 'disabled', label: '未开启' },
  { value: 'inherited', label: '继承账号级' }
]

function accountScopeOverride(accountId) {
  const key = String(accountId ?? '')
  if (!key) return undefined
  if (!Object.prototype.hasOwnProperty.call(accountScopeStatus.value || {}, key)) return undefined
  return accountScopeStatus.value[key]
}

function accountScopeConfigured(accountId) {
  return accountScopeOverride(accountId) !== undefined
}

function resolveAccountEffective(accountId) {
  if (!scopeAvailable.value || typeof globalEnabled.value !== 'boolean') return null
  if (!globalEnabled.value) return false
  const override = accountScopeOverride(accountId)
  if (override === undefined) return true
  return override === true
}

function computeProductEffective(product) {
  if (!product || !scopeAvailable.value || typeof globalEnabled.value !== 'boolean') return null
  if (!globalEnabled.value) return false
  if (product.auto_reply_enabled === 1) return true
  if (product.auto_reply_enabled === 0) return false
  return resolveAccountEffective(product.accountId)
}

const knowledgeBaseCount = computed(() => {
  if (!aiSummaryAvailable.value) return null
  const data = aiCsSummary.value || {}
  const list = Array.isArray(data.knowledgeBases) ? data.knowledgeBases : []
  if (list.length) return list.length
  return data.knowledgeBase ? 1 : 0
})

const chatRuleCount = computed(() => {
  if (!aiSummaryAvailable.value) return null
  const data = aiCsSummary.value || {}
  const list = Array.isArray(data.chatRules) ? data.chatRules : []
  return list.length
})

const visibleProducts = computed(() => {
  const query = debouncedProductSearch.value.trim().toLowerCase()
  return products.value.filter((product) => {
    const matchesSearch = !query || (product.title || '').toLowerCase().includes(query)
    if (!matchesSearch) return false

    if (productFilter.value === 'enabled') return resolveProductEffective(product) === true
    if (productFilter.value === 'disabled') return resolveProductEffective(product) === false
    if (productFilter.value === 'inherited') return product.auto_reply_enabled == null && accountScopeOverride(product.accountId) === true
    return true
  })
})

const filteredProducts = computed(() => visibleProducts.value)
// 商品列表分页显示：默认只渲染前 50 条，避免多账号场景下一次性渲染过多 DOM 导致卡顿
const productVisibleLimit = ref(50)
const pagedFilteredProducts = computed(() => filteredProducts.value.slice(0, productVisibleLimit.value))

const enabledProductCount = computed(() => productsAvailable.value && scopeAvailable.value ? products.value.filter(product => resolveProductEffective(product) === true).length : null)
const inheritedProductCount = computed(() => productsAvailable.value && scopeAvailable.value ? products.value.filter((product) => product.auto_reply_enabled == null && accountScopeOverride(product.accountId) === true).length : null)
const selectedProducts = computed(() => products.value.filter((product) => selectedProductIds.value.includes(product.id)))
const selectedEnabledCount = computed(() => scopeAvailable.value ? selectedProducts.value.filter(product => resolveProductEffective(product) === true).length : null)
const selectedDisabledCount = computed(() => selectedEnabledCount.value === null ? null : Math.max(selectedProducts.value.length - selectedEnabledCount.value, 0))
const selectedAccount = computed(() => accounts.value.find((account) => account.id === selectedAccountId.value) || null)

const aiKnowledgeBaseSummary = computed(() => {
  if (!aiSummaryAvailable.value) return '知识库摘要不可用，无法判断是否已配置。'
  if (knowledgeBaseCount.value > 1) return `已配置 ${knowledgeBaseCount.value} 份知识库，具体内容请前往 AI 客服配置查看。`
  if (knowledgeBaseCount.value === 1) return '已配置 1 份知识库，具体内容请前往 AI 客服配置查看。'
  return '暂未配置知识库，建议先补充商品说明和售后 FAQ，避免回复内容过于空泛。'
})

const aiChatRuleSummary = computed(() => {
  if (!aiSummaryAvailable.value) return '聊天规则摘要不可用，无法判断是否已配置。'
  if (chatRuleCount.value > 0) return `已配置 ${chatRuleCount.value} 条聊天规则，具体内容请前往 AI 客服配置查看。`
  return '当前未返回聊天规则配置。'
})

const selectedAccountSummary = computed(() => {
  if (selectedProductIds.value.length === 1) {
    const product = selectedProducts.value[0]
    return {
      title: `${shortText(product?.title || '商品', 16)}\n单品范围`,
      description: '当前只针对单个商品查看自动回复状态。',
      badge: '商品级'
    }
  }

  if (selectedProductIds.value.length > 1) {
    return {
      title: `${selectedProductIds.value.length} 个商品\n批量范围`,
      description: '当前准备批量修改多个商品的自动回复状态。',
      badge: '批量操作'
    }
  }

  if (selectedAccount.value) {
    return {
      title: `${accountName(selectedAccount.value)}\n账号范围`,
      description: '当前正在查看单个账号下的商品覆盖情况。',
      badge: '账号级'
    }
  }

  return {
    title: '全部账号\n全局范围',
    description: '当前正在汇总查看全部账号的自动回复覆盖情况。',
    badge: '全局'
  }
})

const selectedProductSummary = computed(() => {
  if (!selectedProductIds.value.length) {
    return {
      title: '暂无商品选中',
      description: '先在左侧商品列表里选择一个或多个商品，右侧会同步显示影响范围。',
      tag: '待选择'
    }
  }

  if (selectedProductIds.value.length === 1) {
    const product = selectedProducts.value[0]
    return {
      title: `已选中 1 个商品`,
      description: `当前聚焦商品「${shortText(product?.title || '', 24)}」的自动回复状态。`,
      tag: resolveProductEffective(product) === true ? '生效中' : resolveProductEffective(product) === false ? '待调整' : '状态未知'
    }
  }

  return {
    title: `已选中 ${selectedProductIds.value.length} 个商品`,
    description: selectedEnabledCount.value === null ? '当前自动回复状态不可用，已禁用批量操作。' : `批量操作将影响 ${selectedEnabledCount.value} 个已开启商品和 ${selectedDisabledCount.value} 个待调整商品。`,
    tag: '待操作'
  }
})

const scopeOverviewCards = computed(() => [
  {
    label: '生效范围',
    value: enabledProductCount.value === null ? '—' : `${enabledProductCount.value} 个`,
    detail: '已覆盖的商品数量，帮助用户立刻判断这次操作影响面。',
    tone: 'blue'
  },
  {
    label: '继承账号级',
    value: inheritedProductCount.value === null ? '—' : `${inheritedProductCount.value} 个`,
    detail: '仍处于“跟随账号配置”的商品，适合提醒继续精细化管理。',
    tone: 'green'
  },
  {
    label: '待完善',
    value: pendingConfigCount.value === null ? '—' : `${pendingConfigCount.value} 项`,
    detail: '根据知识库与聊天规则情况给出轻量风险提醒。',
    tone: 'amber'
  }
])

const heroMetricCards = computed(() => [
  {
    label: '已开启自动回复',
    value: enabledProductCount.value ?? '—',
    detail: '已开启自动回复的商品，适合突出当前运营覆盖面。'
  },
  {
    label: '自动回复生效账号',
    value: accountEnabledCount.value === null ? '—' : `${accountEnabledCount.value}/${accounts.value.length}`,
    detail: '根据当前返回的全局与账号作用域配置计算。'
  },
  {
    label: '自动回复商品覆盖率',
    value: coverageRate.value === null ? '—' : `${coverageRate.value}%`,
    detail: '根据当前返回的商品作用域配置计算，不代表消息送达率。'
  }
])

const heroPills = computed(() => [
  scopeAvailable.value ? (globalEnabled.value ? '全局主开关已开启' : '全局主开关未开启') : '自动回复状态未知',
  accountsAvailable.value ? `${accounts.value.length} 个账号已接入` : '账号范围状态未知',
  productsAvailable.value ? `${products.value.length} 个商品支持自动回复` : '商品范围状态未知',
  `当前命中范围：${selectedAccountSummary.value.badge}`
])

const strategyHeadline = computed(() => {
  if (selectedProductIds.value.length > 1) return `${selectedProductIds.value.length} 个商品 · 批量调整自动回复`
  if (selectedProductIds.value.length === 1) return `${shortText(selectedProducts.value[0]?.title || '当前商品', 18)} · 自动回复详情`
  if (selectedAccount.value) return `${accountName(selectedAccount.value)} · 账号自动回复配置`
  return scopeAvailable.value ? '全部账号 · 自动回复配置' : '全部账号 · 自动回复状态未知'
})

const strategyDescription = computed(() => {
  if (selectedProductIds.value.length > 1) {
    return '当前已选中的商品会一起应用开关状态。商品级关闭会覆盖账号级开启，开启后会立刻进入自动回复处理链路。'
  }
  if (selectedProductIds.value.length === 1) {
    return '单个商品可以单独覆盖账号级默认状态，适合对重点商品、特殊服务商品做更精细的控制。'
  }
  if (selectedAccount.value) {
    return '打开后，该账号下未单独关闭的商品都会进入 AI 客服处理链路。商品级覆盖依然优先于账号级。'
  }
  return '打开后，当前选中范围内的咨询将直接进入 AI 客服处理链路。商品级关闭会覆盖账号级开启，账号级开启会覆盖全局默认状态。'
})

const currentScopeBadge = computed(() => {
  if (selectedProductIds.value.length === 1) return '当前作用域：单个商品'
  if (selectedProductIds.value.length > 1) return `当前作用域：${selectedProductIds.value.length} 个商品`
  if (selectedAccount.value) return `当前作用域：${accountName(selectedAccount.value)}`
  return '当前作用域：全部账号（全局）'
})

const selectedProductBadge = computed(() => {
  if (!selectedProductIds.value.length) return '批量选中：未选择商品'
  return `批量选中：${selectedProductIds.value.length} 个商品`
})

const knowledgeBaseBadge = computed(() => knowledgeBaseCount.value === null ? '知识库：状态未知' : `知识库：${knowledgeBaseCount.value} 份已绑定`)

const pendingConfigCount = computed(() => {
  if (!accountsAvailable.value || !aiSummaryAvailable.value) return null
  if (!accounts.value.length) return 0
  if (!knowledgeBaseCount.value && !chatRuleCount.value) return 1
  if (!knowledgeBaseCount.value || !chatRuleCount.value) return 1
  return 0
})

const riskSummaryText = computed(() => {
  if (pendingConfigCount.value === null) return '配置状态暂不可用'
  if (pendingConfigCount.value > 0) return `${pendingConfigCount.value} 项配置待完善`
  return '知识库与规则配置已齐全'
})

const riskSummaryTag = computed(() => pendingConfigCount.value === null ? '状态未知' : (pendingConfigCount.value > 0 ? '建议补齐' : '已完善'))

const coverageRate = computed(() => {
  if (!productsAvailable.value || !scopeAvailable.value) return null
  if (!products.value.length) return 0
  return Math.round((enabledProductCount.value / products.value.length) * 100)
})

const accountEnabledCount = computed(() => {
  if (!accountsAvailable.value || !scopeAvailable.value) return null
  return accounts.value.filter((account) => resolveAccountEffective(account.id) === true).length
})

const logicSteps = [
  {
    step: '1',
    title: '全局主开关',
    detail: '决定系统是否具备自动回复能力。这里可以联动开关，详细话术和知识库仍在 AI 客服配置页维护。'
  },
  {
    step: '2',
    title: '账号级范围',
    detail: '用于批量决定某个店铺下的默认回复状态，适合先做中层策略。'
  },
  {
    step: '3',
    title: '商品级覆盖',
    detail: '当单个商品需要单独开关时，以商品状态覆盖账号级和全局状态。'
  }
]

const impactRows = computed(() => [
  {
    label: '本次批量选择',
    detail: '将同步修改当前选中商品的商品级状态。',
    value: productsAvailable.value ? selectedProductIds.value.length : '—'
  },
  {
    label: '账户默认继承',
    detail: '仍有商品跟随账号级策略，适合后续继续细分。',
    value: inheritedProductCount.value ?? '—'
  },
  {
    label: '全局覆盖比例',
    detail: '当前自动回复已覆盖当前范围内的商品占比。',
    value: coverageRate.value === null ? '—' : `${coverageRate.value}%`
  }
])

const accountCards = computed(() => {
  const cards = [
    {
      key: 'all',
      id: '',
      isAll: true,
      avatarUrl: '',
      active: selectedAccountId.value === '',
      badge: 'ALL',
      name: '全部账号',
      description: '汇总查看所有账号的自动回复覆盖情况',
      status: scopeAvailable.value ? (globalEnabled.value ? '全局开启' : '全局关闭') : '自动回复状态未知',
      statusTone: scopeAvailable.value ? (globalEnabled.value ? 'green' : 'gray') : 'amber',
      showMetrics: true,
      metrics: buildAccountMetrics(allProductsCache.value)
    }
  ]

  for (const account of accounts.value) {
    const accountProducts = scopedProductsForAccount(account.id)
    const enabledCount = scopeAvailable.value && productsAvailable.value ? accountProducts.filter(product => resolveProductEffective(product) === true).length : null
    const inheritedCount = accountProducts.filter((product) => product.auto_reply_enabled == null && accountScopeOverride(product.accountId) === true).length
    const avatarUrl = brokenAvatarIds.value.has(account.id) ? '' : (account?.avatarUrl || '')

    const totalCount = accountProducts.length
    let statusText = '自动回复状态未知'
    let statusTone = 'amber'
    if (enabledCount !== null && totalCount === 0) {
      statusText = '暂无商品'
      statusTone = 'gray'
    } else if (enabledCount !== null && totalCount > 0 && enabledCount === totalCount) {
      statusText = '全部开启'
      statusTone = 'green'
    } else if (enabledCount !== null && enabledCount > 0) {
      statusText = '部分开启'
      statusTone = 'amber'
    } else if (enabledCount === 0) {
      statusText = '全部关闭'
      statusTone = 'gray'
    }

    cards.push({
      key: account.id,
      id: account.id,
      isAll: false,
      avatarUrl,
      active: selectedAccountId.value === account.id,
      badge: accountBadge(account),
      name: accountName(account),
      description: enabledCount === null ? '商品自动回复状态暂不可用' : `${accountProducts.length} 个商品 · ${enabledCount} 个已开启 · ${inheritedCount} 个继承账号级`,
      status: statusText,
      statusTone,
      showMetrics: selectedAccountId.value === account.id,
      metrics: buildAccountMetrics(accountProducts)
    })
  }

  return cards
})

function onAvatarError(card) {
  if (!card?.id) return
  const next = new Set(brokenAvatarIds.value)
  next.add(card.id)
  brokenAvatarIds.value = next
}

function buildAccountMetrics(source) {
  const list = Array.isArray(source) ? source : []
  if (!productsAvailable.value || !scopeAvailable.value) {
    return [
      { label: '商品总数', value: '—' },
      { label: '已开启', value: '—' },
      { label: '账号覆盖', value: '—' }
    ]
  }
  return [
    { label: '商品总数', value: list.length },
    { label: '已开启', value: list.filter(product => resolveProductEffective(product) === true).length },
    { label: '账号覆盖', value: list.length ? new Set(list.map((product) => product.accountId)).size : 0 }
  ]
}

function accountBadge(account) {
  const text = accountName(account)
  return text
    .replace(/[^\p{L}\p{N}]/gu, '')
    .slice(0, 2)
    .toUpperCase() || 'AC'
}

function scopedProductsForAccount(accountId) {
  if (!allProductsCache.value.length) {
    return accountId === selectedAccountId.value ? products.value : []
  }
  return allProductsCache.value.filter((product) => product.accountId === accountId)
}

function resolveProductEffective(product) {
  if (!product || !scopeAvailable.value) return null
  if (typeof product.effective_enabled === 'boolean') return product.effective_enabled
  return computeProductEffective(product)
}

function productPrimaryStatus(product) {
  if (product.auto_reply_enabled === 1) return { label: '已开启', tone: 'green' }
  if (product.auto_reply_enabled === 0) return { label: '已关闭', tone: 'gray' }
  if (accountScopeOverride(product.accountId) === true) return { label: '继承账号级', tone: 'blue' }
  if (globalEnabled.value && !accountScopeConfigured(product.accountId)) return { label: '继承全局', tone: 'blue' }
  if (!scopeAvailable.value) return { label: '状态未知', tone: 'amber' }
  return { label: '未开启', tone: 'gray' }
}

function productSecondaryStatus(product) {
  const effective = resolveProductEffective(product)
  if (effective === null) return { label: '生效状态未知', tone: 'amber' }
  if (effective === true) return { label: '生效中', tone: 'blue' }
  if (product.auto_reply_enabled === 0) return { label: '待确认', tone: 'amber' }
  return null
}

function accountLabelForProduct(product) {
  const account = accounts.value.find((item) => item.id === product.accountId)
  return account ? accountName(account) : '未绑定账号'
}

function applyProductState(itemIds, enabled) {
  for (const source of [products.value, allProductsCache.value]) {
    source.forEach((product) => {
      if (itemIds.includes(product.id)) {
        product.auto_reply_enabled = enabled ? 1 : 0
        product.effective_enabled = globalEnabled.value && enabled
      }
    })
  }
}

function syncEffectiveState() {
  for (const source of [products.value, allProductsCache.value]) {
    source.forEach((product) => {
      product.effective_enabled = computeProductEffective(product)
    })
  }
}

async function loadAccounts() {
  accountsAvailable.value = false
  accountsError.value = ''
  accounts.value = []
  try {
    const response = await getLiteAccounts()
    const data = response?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    accountsAvailable.value = true
    return true
  } catch (requestError) {
    accountsError.value = friendlyError(requestError, '账号列表加载失败')
    return false
  }
}

async function loadScopeStatus() {
  scopeAvailable.value = false
  scopeError.value = ''
  globalEnabled.value = null
  accountScopeStatus.value = {}
  try {
    const response = await getAutoReplyScopeStatus()
    const data = response?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('自动回复作用域响应格式异常')
    const enabled = data.global_enabled ?? data.globalEnabled
    if (typeof enabled !== 'boolean') throw new Error('自动回复作用域响应缺少主开关状态')
    const scopes = data.account_scopes ?? data.accountScopes ?? {}
    if (!scopes || typeof scopes !== 'object' || Array.isArray(scopes)
      || Object.values(scopes).some(value => typeof value !== 'boolean')) {
      throw new Error('自动回复账号作用域响应格式异常')
    }
    globalEnabled.value = enabled
    accountScopeStatus.value = scopes
    scopeAvailable.value = true
    syncEffectiveState()
    return true
  } catch (requestError) {
    scopeError.value = friendlyError(requestError, '自动回复作用域加载失败')
    return false
  }
}

async function loadAiCsSummary() {
  aiSummaryAvailable.value = false
  aiSummaryError.value = ''
  aiCsSummary.value = null
  try {
    const response = await getBusinessSettings('ai-customer-service')
    const data = response?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.enabled !== 'boolean') {
      throw new Error('AI 客服摘要响应格式异常')
    }
    aiCsSummary.value = data
    aiSummaryAvailable.value = true
    return true
  } catch (requestError) {
    aiSummaryError.value = friendlyError(requestError, 'AI 客服摘要加载失败')
    return false
  }
}

async function saveAiCsEnabled(enabled) {
  if (!aiSummaryAvailable.value || !aiCsSummary.value || typeof aiCsSummary.value !== 'object') {
    throw new Error('AI 客服配置不可用，已阻止覆盖保存')
  }
  const baseConfig = { ...aiCsSummary.value }

  const nextConfig = { ...baseConfig, enabled }
  await saveBusinessSettings('ai-customer-service', nextConfig)
  aiCsSummary.value = nextConfig
  aiSummaryAvailable.value = true
  globalEnabled.value = enabled
  scopeAvailable.value = true
  syncEffectiveState()
}

async function ensureGlobalEnabledBeforeScopeEnable() {
  if (!scopeWritable.value || typeof globalEnabled.value !== 'boolean') throw new Error('自动回复状态不可用，无法安全修改作用域')
  if (globalEnabled.value) return false

  const confirmed = await confirmAction({
    title: '同步开启 AI 客服主开关',
    description: '当前 AI 客服主开关仍处于关闭状态。继续后会先开启主开关，再应用这次商品或账号范围设置，自动回复才会真正生效。',
    confirmText: '开启并继续'
  })
  if (!confirmed) return null

  await saveAiCsEnabled(true)
  return true
}

async function loadAllProductsCache({ replaceVisible = false } = {}) {
  const response = await getAutoReplyScopeProducts()
  const data = response?.data
  const items = Array.isArray(data) ? data : data?.items || data?.records || data?.list
  if (!Array.isArray(items)) throw new Error('自动回复商品列表响应格式异常')
  allProductsCache.value = items
  if (replaceVisible) products.value = items
}

async function loadProducts() {
  productsLoading.value = true
  productsAvailable.value = false
  productsError.value = ''
  selectedProductIds.value = []
  products.value = []

  try {
    if (selectedAccountId.value === '') {
      await loadAllProductsCache({ replaceVisible: true })
    } else {
      const response = await getAutoReplyScopeProducts(selectedAccountId.value)
      const data = response?.data
      const items = Array.isArray(data) ? data : data?.items || data?.records || data?.list
      if (!Array.isArray(items)) throw new Error('自动回复商品列表响应格式异常')
      products.value = items
      if (!allProductsCache.value.length) {
        allProductsCache.value = products.value.map((product) => ({ ...product }))
      }
    }
    productsAvailable.value = true
    return true
  } catch (requestError) {
    productsError.value = friendlyError(requestError, '商品范围加载失败')
    return false
  } finally {
    productsLoading.value = false
  }
}

function selectAccount(accountId) {
  if (!accountsAvailable.value) return
  selectedAccountId.value = accountId
  selectedProductIds.value = []
  loadProducts()
}

function toggleProductSelect(productId) {
  if (!productsAvailable.value) return
  const index = selectedProductIds.value.indexOf(productId)
  if (index >= 0) selectedProductIds.value.splice(index, 1)
  else selectedProductIds.value.push(productId)
}

const currentScopeEnabled = computed(() => {
  if (!scopeAvailable.value || !productsAvailable.value || typeof globalEnabled.value !== 'boolean') return null
  if (selectedProductIds.value.length > 0) {
    const states = selectedProducts.value.map(resolveProductEffective)
    if (!states.length || states.some(state => state === null)) return null
    return states.every(state => state === true)
  }

  if (selectedAccount.value) return resolveAccountEffective(selectedAccount.value.id)
  return globalEnabled.value
})

async function refreshCurrentScope() {
  isRefreshing.value = true

  try {
    await Promise.allSettled([
      loadAccounts(),
      loadScopeStatus(),
      loadAiCsSummary(),
      loadProducts()
    ])
  } finally {
    isRefreshing.value = false
  }
}

async function toggleCurrentScope() {
  if (!scopeWritable.value || currentScopeEnabled.value === null) {
    error.value = '自动回复状态不可用，已阻止修改；请先同步当前范围。'
    return
  }
  const nextEnabled = !currentScopeEnabled.value

  try {
    let globalJustEnabled = false
    if (nextEnabled && (selectedProductIds.value.length > 0 || selectedAccount.value)) {
      const ensured = await ensureGlobalEnabledBeforeScopeEnable()
      if (ensured == null) return
      globalJustEnabled = ensured
    }

    if (selectedProductIds.value.length === 1) {
      const productId = selectedProductIds.value[0]
      await updateProductAutoReplyScope(productId, nextEnabled)
      applyProductState([productId], nextEnabled)
      success.value = `已${nextEnabled ? '开启' : '关闭'}商品自动回复${globalJustEnabled ? '，并同步开启 AI 客服主开关' : ''}`
    } else if (selectedProductIds.value.length > 1) {
      await batchUpdateAutoReplyScope({ itemIds: selectedProductIds.value, enabled: nextEnabled })
      applyProductState(selectedProductIds.value, nextEnabled)
      success.value = `已${nextEnabled ? '开启' : '关闭'} ${selectedProductIds.value.length} 个商品${globalJustEnabled ? '，并同步开启 AI 客服主开关' : ''}`
    } else if (selectedAccount.value) {
      await updateAccountAutoReplyScope(selectedAccount.value.id, nextEnabled)
      accountScopeStatus.value[selectedAccount.value.id] = nextEnabled
      syncEffectiveState()
      success.value = `已${nextEnabled ? '开启' : '关闭'}该账号的自动回复${globalJustEnabled ? '，并同步开启 AI 客服主开关' : ''}`
      await loadProducts()
      await loadAllProductsCache({ replaceVisible: false })
    } else {
      await saveAiCsEnabled(nextEnabled)
      success.value = `已${nextEnabled ? '开启' : '关闭'} AI 客服主开关`
      await loadProducts()
      await loadAllProductsCache({ replaceVisible: false })
    }

    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (requestError) {
    error.value = `切换失败：${friendlyError(requestError, '网络错误')}`
    setTimeout(() => {
      if (error.value) error.value = ''
    }, 6000)
  }
}

async function batchUpdateProducts(enabled) {
  if (!scopeWritable.value || !selectedProductIds.value.length) return

  batchUpdating.value = true
  try {
    let globalJustEnabled = false
    if (enabled) {
      const ensured = await ensureGlobalEnabledBeforeScopeEnable()
      if (ensured == null) return
      globalJustEnabled = ensured
    }

    await batchUpdateAutoReplyScope({ itemIds: selectedProductIds.value, enabled })
    applyProductState(selectedProductIds.value, enabled)
    success.value = `已${enabled ? '开启' : '关闭'} ${selectedProductIds.value.length} 个商品${globalJustEnabled ? '，并同步开启 AI 客服主开关' : ''}`
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (requestError) {
    error.value = `批量操作失败：${friendlyError(requestError)}`
    setTimeout(() => { if (error.value) error.value = '' }, 6000)
  } finally {
    batchUpdating.value = false
  }
}

async function batchEnableAllProducts() {
  if (!scopeWritable.value || !products.value.length) return

  const confirmed = await confirmAction({
    title: '一键全部开启',
    description: `将为当前列表的 ${products.value.length} 个商品全部开启自动回复，确认？`,
    confirmText: '确认开启'
  })
  if (!confirmed) return

  batchUpdating.value = true
  try {
    const ensured = await ensureGlobalEnabledBeforeScopeEnable()
    if (ensured == null) return

    const itemIds = products.value.map((product) => product.id)
    await batchUpdateAutoReplyScope({ itemIds, enabled: true })
    applyProductState(itemIds, true)
    success.value = `已为 ${itemIds.length} 个商品开启自动回复${ensured ? '，并同步开启 AI 客服主开关' : ''}`
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (requestError) {
    error.value = `一键开启失败：${friendlyError(requestError)}`
    setTimeout(() => { if (error.value) error.value = '' }, 6000)
  } finally {
    batchUpdating.value = false
  }
}

function goToAiCsSettings() {
  emit('navigate', 'settings-ai-cs')
}

onMounted(async () => {
  await loadAccounts()
  await Promise.all([
    loadScopeStatus(),
    loadAiCsSummary(),
    loadProducts()
  ])
})
</script>

<style scoped>
.auto-reply-shell {
  display: grid;
  gap: 18px;
}

.auto-reply-error-summary {
  display: grid;
  gap: 6px;
}

.auto-reply-error-summary strong,
.auto-reply-error-summary p {
  margin: 0;
}

.auto-reply-error-summary p {
  font-weight: 600;
  line-height: 1.55;
}

.auto-reply-error-summary details {
  font-size: 12px;
  font-weight: 600;
}

.auto-reply-error-summary summary {
  width: fit-content;
  cursor: pointer;
}

.auto-reply-error-summary ul {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
  padding-left: 18px;
  font-weight: 500;
  line-height: 1.45;
}

.auto-reply-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 392px;
  gap: 18px;
}

.auto-reply-hero-head {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.auto-reply-hero-copy {
  min-width: 0;
}

.auto-reply-hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(47, 107, 255, 0.08);
  color: #3a63c6;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.auto-reply-hero-pill::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f6bff, #59b3ff);
}

.auto-reply-hero-copy h1 {
  margin: 10px 0;
  font-size: 44px;
  line-height: 1;
  letter-spacing: -0.04em;
  color: #16315d;
}

.auto-reply-hero-copy p {
  max-width: 820px;
  margin: 0;
  color: #667b9f;
  font-size: 16px;
  line-height: 1.8;
}

.auto-reply-hero-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.auto-reply-action-button {
  min-height: 42px;
  border: 1px solid #dbe6f6;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #436289;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(42, 72, 130, 0.08);
}

.auto-reply-action-button.primary {
  border-color: transparent;
  color: #fff;
  background: linear-gradient(135deg, #2f6bff, #489cff);
  box-shadow: 0 16px 30px rgba(47, 107, 255, 0.24);
}

.auto-reply-action-button.full {
  width: 100%;
  justify-content: center;
}

.auto-reply-action-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.auto-reply-button-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.82;
}

.auto-reply-hero-main,
.auto-reply-hero-side,
.auto-reply-panel {
  border: 1px solid #e4ebf7;
  border-radius: 28px;
  overflow: hidden;
}

.auto-reply-hero-main {
  position: relative;
  padding: 26px 28px;
  background:
    radial-gradient(circle at 85% 20%, rgba(120, 195, 255, 0.28), transparent 18%),
    radial-gradient(circle at 70% 110%, rgba(20, 184, 166, 0.18), transparent 24%),
    linear-gradient(135deg, #173b74 0%, #2457b8 48%, #4d98ff 100%);
  color: #fff;
  box-shadow: 0 24px 42px rgba(32, 76, 177, 0.22);
}

.auto-reply-hero-main::before {
  content: '';
  position: absolute;
  width: 320px;
  height: 320px;
  right: -120px;
  top: -120px;
  border-radius: 48px;
  background: rgba(255, 255, 255, 0.08);
  transform: rotate(18deg);
}

.auto-reply-hero-main::after {
  content: '';
  position: absolute;
  width: 220px;
  height: 220px;
  right: 120px;
  bottom: -110px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.16);
}

.auto-reply-hero-kicker {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.auto-reply-hero-kicker::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7debd7;
  box-shadow: 0 0 0 4px rgba(125, 235, 215, 0.18);
}

.auto-reply-hero-main h2,
.auto-reply-hero-main p,
.auto-reply-hero-pill-row,
.auto-reply-hero-metrics {
  position: relative;
  z-index: 1;
}

.auto-reply-hero-main h2 {
  max-width: 760px;
  margin: 16px 0 14px;
  font-size: 34px;
  line-height: 1.15;
  letter-spacing: -0.04em;
}

.auto-reply-hero-main p {
  max-width: 780px;
  margin: 0 0 18px;
  color: rgba(255, 255, 255, 0.84);
  font-size: 15px;
  line-height: 1.8;
}

.auto-reply-hero-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 22px;
}

.auto-reply-hero-pill-row span {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 13px;
  font-weight: 700;
}

.auto-reply-hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  max-width: 760px;
}

.auto-reply-hero-metric {
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(6px);
}

.auto-reply-hero-metric b {
  display: block;
  margin-bottom: 6px;
  font-size: 26px;
  letter-spacing: -0.03em;
}

.auto-reply-hero-metric span {
  display: block;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.82);
}

.auto-reply-hero-side {
  padding: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.94));
  box-shadow: 0 18px 42px rgba(36, 67, 128, 0.1);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.auto-reply-hero-side-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.auto-reply-hero-side-top h3 {
  margin: 0 0 8px;
  color: #6d83a7;
  font-size: 14px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.auto-reply-hero-side-top strong {
  white-space: pre-line;
  display: block;
  font-size: 30px;
  line-height: 1.06;
  letter-spacing: -0.04em;
  color: #16335f;
}

.auto-reply-side-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  width: fit-content;
  padding: 0 12px;
  border-radius: 999px;
  background: #edf4ff;
  color: #2f6bff;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-side-pill::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f6bff, #59b3ff);
}

.auto-reply-side-note {
  padding: 16px;
  border-radius: 20px;
  border: 1px solid #e5edf8;
  background: linear-gradient(135deg, #f7faff, #eef5ff);
}

.auto-reply-side-note strong {
  display: block;
  margin-bottom: 6px;
  color: #16335f;
  font-size: 14px;
}

.auto-reply-side-note p {
  margin: 0;
  color: #6c82a5;
  font-size: 13px;
  line-height: 1.72;
}

.auto-reply-side-list {
  display: grid;
  gap: 12px;
}

.auto-reply-side-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid #e8eef8;
  background: #fbfdff;
}

.auto-reply-side-item b {
  display: block;
  margin-bottom: 4px;
  color: #6e82a5;
  font-size: 13px;
}

.auto-reply-side-item strong {
  display: block;
  color: #17345f;
  font-size: 18px;
  letter-spacing: -0.02em;
}

.auto-reply-status-chip,
.auto-reply-status-pill,
.auto-reply-meta-badge,
.auto-reply-tiny-chip,
.auto-reply-insight-chip {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  white-space: nowrap;
}

.auto-reply-status-chip {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-status-chip.green,
.auto-reply-status-pill.green,
.auto-reply-meta-badge.green {
  background: #ecfdf3;
  color: #159c61;
}

.auto-reply-status-chip.blue,
.auto-reply-status-pill.blue,
.auto-reply-meta-badge.blue {
  background: #edf4ff;
  color: #2f6bff;
}

.auto-reply-status-chip.amber,
.auto-reply-meta-badge.amber {
  background: #fff6df;
  color: #d97706;
}

.auto-reply-status-chip.gray,
.auto-reply-status-pill.gray,
.auto-reply-meta-badge.gray {
  background: #f2f5f9;
  color: #7588a3;
}

.auto-reply-workspace {
  display: grid;
  grid-template-columns: 356px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.auto-reply-left-column,
.auto-reply-right-column,
.auto-reply-side-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.auto-reply-panel {
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 42px rgba(36, 67, 128, 0.1);
}

.auto-reply-panel-head {
  padding: 20px 22px 16px;
  border-bottom: 1px solid #edf2fb;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.auto-reply-panel-head h3 {
  margin: 0 0 8px;
  font-size: 22px;
  letter-spacing: -0.02em;
  color: #18345f;
}

.auto-reply-panel-head p {
  margin: 0;
  color: #7d8fab;
  font-size: 13px;
  line-height: 1.7;
}

.auto-reply-tiny-chip {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(47, 107, 255, 0.08);
  color: #3d66cb;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-panel-body {
  padding: 18px;
}

.auto-reply-account-list,
.auto-reply-product-list,
.auto-reply-summary-body,
.auto-reply-logic-body,
.auto-reply-impact-body {
  display: grid;
  gap: 12px;
}

.auto-reply-account-list {
  max-height: 540px;
  overflow: auto;
}

.auto-reply-account-item,
.auto-reply-product-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e8eef8;
  background: #fbfdff;
  padding: 0;
}

.auto-reply-account-item {
  padding: 16px;
  border-radius: 20px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.auto-reply-account-item.active,
.auto-reply-product-item.selected {
  border-color: rgba(47, 107, 255, 0.28);
  background: linear-gradient(135deg, rgba(47, 107, 255, 0.12), rgba(12, 192, 223, 0.08));
  box-shadow: 0 14px 26px rgba(47, 107, 255, 0.12);
}

.auto-reply-account-row,
.auto-reply-account-main {
  display: flex;
  align-items: center;
}

.auto-reply-account-row {
  justify-content: space-between;
  gap: 10px;
}

.auto-reply-account-main {
  gap: 12px;
  min-width: 0;
}

.auto-reply-account-badge {
  width: 42px;
  height: 42px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  flex: none;
  color: #2f6bff;
  font-size: 13px;
  font-weight: 900;
  background: linear-gradient(135deg, rgba(47, 107, 255, 0.12), rgba(90, 174, 255, 0.14));
  overflow: hidden;
}

.auto-reply-account-badge.is-all {
  background: linear-gradient(135deg, #2f6bff 0%, #5aaeff 60%, #7debd7 100%);
  color: #fff;
  box-shadow: 0 8px 18px rgba(47, 107, 255, 0.28);
}

.auto-reply-account-icon {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.auto-reply-account-badge.has-avatar {
  background: linear-gradient(135deg, rgba(47, 107, 255, 0.18), rgba(125, 235, 215, 0.18));
  padding: 0;
}

.auto-reply-account-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 15px;
  display: block;
}

.auto-reply-account-main strong {
  display: block;
  margin-bottom: 4px;
  color: #17345f;
  font-size: 15px;
}

.auto-reply-account-main span {
  display: block;
  color: #7d8fab;
  font-size: 12px;
}

.auto-reply-status-pill {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-account-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.auto-reply-mini-stat {
  min-width: 92px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid #e9eff9;
}

.auto-reply-mini-stat b {
  display: block;
  margin-bottom: 4px;
  color: #18345f;
  font-size: 17px;
  letter-spacing: -0.02em;
}

.auto-reply-mini-stat span {
  display: block;
  color: #7f90ab;
  font-size: 11px;
}

.auto-reply-product-toolbar {
  padding: 0 18px 14px;
  display: grid;
  gap: 12px;
}

.auto-reply-search-row,
.auto-reply-filter-row,
.auto-reply-selection-actions,
.auto-reply-strategy-top {
  display: flex;
  gap: 10px;
}

.auto-reply-search-row {
  align-items: center;
}

.auto-reply-search {
  flex: 1;
  min-height: 44px;
  border: 1px solid #d9e4f4;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff, #f7faff);
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.auto-reply-search input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: #7084a7;
  font-size: 13px;
  font-weight: 600;
}

.auto-reply-search-icon {
  width: 14px;
  height: 14px;
  border: 2px solid #9ab0ce;
  border-radius: 50%;
  position: relative;
  flex: none;
}

.auto-reply-search-icon::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 2px;
  right: -4px;
  bottom: -1px;
  background: #9ab0ce;
  transform: rotate(40deg);
  border-radius: 999px;
}

.auto-reply-filter-row {
  flex-wrap: wrap;
}

.auto-reply-filter-chip {
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid #dbe6f6;
  border-radius: 999px;
  background: #fff;
  color: #7387a5;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-filter-chip.active {
  background: #edf4ff;
  border-color: #cfe0ff;
  color: #2f6bff;
}

.auto-reply-loading,
.auto-reply-empty {
  padding: 24px 18px;
  color: #8294af;
  text-align: center;
  font-size: 13px;
}

.auto-reply-product-list {
  padding: 0 18px 18px;
  max-height: 680px;
  overflow: auto;
}

.auto-reply-load-more {
  padding: 8px 18px 16px;
  text-align: center;
}
.auto-reply-load-more .ghost {
  padding: 6px 16px;
  border: 1px dashed #c4cbd6;
  background: transparent;
  border-radius: 8px;
  color: #5b6b86;
  cursor: pointer;
  font-size: 12px;
  transition: all .2s;
}
.auto-reply-load-more .ghost:hover { border-color: var(--blue, #2563eb); color: var(--blue, #2563eb) }

.auto-reply-product-item {
  display: block;
  border-radius: 18px;
  padding: 14px;
}

.auto-reply-product-top {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.auto-reply-checkbox {
  width: 18px;
  height: 18px;
  border: 1.6px solid #b6c6dd;
  border-radius: 6px;
  margin-top: 2px;
  flex: none;
  background: #fff;
}

.auto-reply-checkbox.checked {
  position: relative;
  border-color: transparent;
  background: linear-gradient(135deg, #2f6bff, #5aaeff);
}

.auto-reply-checkbox.checked::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 2px;
  width: 5px;
  height: 9px;
  border-right: 2px solid #fff;
  border-bottom: 2px solid #fff;
  transform: rotate(40deg);
}

.auto-reply-product-body {
  min-width: 0;
  flex: 1;
}

.auto-reply-product-body strong {
  display: block;
  margin-bottom: 8px;
  color: #17345f;
  font-size: 14px;
  line-height: 1.55;
}

.auto-reply-product-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.auto-reply-meta-badge {
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
}

.auto-reply-selection-bar {
  margin: 0 18px 18px;
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, #173b74, #306fff);
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  box-shadow: 0 18px 30px rgba(32, 76, 177, 0.2);
}

.auto-reply-selection-bar strong {
  display: block;
  margin-bottom: 4px;
  font-size: 14px;
}

.auto-reply-selection-bar span {
  display: block;
  color: rgba(255, 255, 255, 0.84);
  font-size: 12px;
  line-height: 1.7;
}

.auto-reply-selection-actions .ghost,
.auto-reply-selection-actions .fill {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-selection-actions .ghost {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

.auto-reply-selection-actions .fill {
  border: 0;
  background: #fff;
  color: #245ad5;
}

.auto-reply-selection-actions button:disabled {
  opacity: 0.65;
}

.auto-reply-strategy-body,
.auto-reply-summary-body {
  gap: 16px;
}

.auto-reply-strategy-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 92px;
  align-items: start;
}

.auto-reply-strategy-copy h4 {
  margin: 0 0 10px;
  color: #18345f;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.auto-reply-strategy-copy p {
  margin: 0 0 16px;
  color: #6f83a5;
  font-size: 14px;
  line-height: 1.8;
}

.auto-reply-insight-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.auto-reply-insight-chip {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #e5edf8;
  background: #f7fbff;
  color: #57729e;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-toggle-box {
  padding: 14px;
  border-radius: 20px;
  border: 1px solid #dfebff;
  background: linear-gradient(135deg, #edf4ff, #f8fbff);
  display: grid;
  place-items: center;
  gap: 8px;
  text-align: center;
}

.auto-reply-toggle-box b {
  color: #6e83a6;
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.auto-reply-toggle-box strong {
  color: #17345f;
  font-size: 14px;
}

.auto-reply-switch {
  position: relative;
  width: 42px;
  height: 24px;
  display: inline-block;
  flex: none;
}

.auto-reply-switch-large {
  width: 56px;
  height: 30px;
}

.auto-reply-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.auto-reply-slider {
  position: absolute;
  inset: 0;
  cursor: pointer;
  border-radius: 999px;
  background: #cbd5e1;
  transition: 0.2s;
}

.auto-reply-slider::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 8px 16px rgba(26, 76, 166, 0.18);
  transition: 0.2s;
}

.auto-reply-switch-large .auto-reply-slider::before {
  width: 24px;
  height: 24px;
}

.auto-reply-switch input:checked + .auto-reply-slider {
  background: linear-gradient(90deg, #2f6bff, #54a6ff);
}

.auto-reply-switch input:checked + .auto-reply-slider::before {
  transform: translateX(18px);
}

.auto-reply-switch-large input:checked + .auto-reply-slider::before {
  transform: translateX(26px);
}

.auto-reply-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.auto-reply-metric-card {
  min-height: 116px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #e7eef8;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  box-shadow: 0 10px 24px rgba(42, 72, 130, 0.08);
}

.auto-reply-metric-card b {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  margin-bottom: 16px;
  font-size: 12px;
  font-weight: 800;
}

.auto-reply-metric-card b.blue {
  background: #edf4ff;
  color: #2f6bff;
}

.auto-reply-metric-card b.green {
  background: #ecfdf3;
  color: #159c61;
}

.auto-reply-metric-card b.amber {
  background: #fff6df;
  color: #d97706;
}

.auto-reply-metric-card strong {
  display: block;
  margin-bottom: 8px;
  color: #17325d;
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.auto-reply-metric-card span {
  display: block;
  color: #6f83a5;
  font-size: 13px;
  line-height: 1.6;
}

.auto-reply-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: start;
}

.auto-reply-summary-block {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #e7eef8;
  background: linear-gradient(180deg, #ffffff, #f9fbff);
}

.auto-reply-summary-block label {
  display: block;
  margin-bottom: 8px;
  color: #7187aa;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.auto-reply-summary-block p {
  margin: 0;
  color: #29476f;
  font-size: 14px;
  line-height: 1.8;
}

.auto-reply-summary-footer {
  padding: 0 18px 18px;
}

.auto-reply-logic-step {
  position: relative;
  padding: 14px 14px 14px 52px;
  border-radius: 18px;
  border: 1px solid #e7eef8;
  background: linear-gradient(180deg, #ffffff, #f9fbff);
}

.auto-reply-logic-step::before {
  content: attr(data-step);
  position: absolute;
  left: 14px;
  top: 14px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2f6bff, #5aaeff);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
  box-shadow: 0 10px 18px rgba(47, 107, 255, 0.2);
}

.auto-reply-logic-step strong {
  display: block;
  margin-bottom: 6px;
  color: #17345f;
  font-size: 14px;
}

.auto-reply-logic-step span,
.auto-reply-impact-row span,
.auto-reply-impact-note {
  color: #7286a7;
  font-size: 12px;
  line-height: 1.7;
}

.auto-reply-impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid #e7eef8;
  background: linear-gradient(180deg, #ffffff, #f9fbff);
}

.auto-reply-impact-row strong {
  display: block;
  margin-bottom: 4px;
  color: #17345f;
  font-size: 14px;
}

.auto-reply-impact-value {
  flex: none;
  color: #17345f;
  font-size: 24px;
  font-weight: 900;
  letter-spacing: -0.04em;
}

.auto-reply-impact-note {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(20, 184, 166, 0.14);
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.08), rgba(47, 107, 255, 0.06));
  color: #2a5b79;
}

.auto-reply-impact-note strong {
  display: block;
  margin-bottom: 6px;
  color: #17345f;
  font-size: 14px;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
}

@media (max-width: 1800px) {
  .auto-reply-detail-grid {
    grid-template-columns: 1fr;
  }

  .auto-reply-side-stack {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 1480px) {
  .auto-reply-hero,
  .auto-reply-workspace {
    grid-template-columns: 1fr;
  }

  .auto-reply-strategy-top,
  .auto-reply-metric-grid,
  .auto-reply-hero-metrics {
    grid-template-columns: 1fr;
  }

  .auto-reply-side-stack {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1120px) {
  .auto-reply-hero-head,
  .auto-reply-search-row,
  .auto-reply-selection-bar,
  .auto-reply-hero-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .auto-reply-selection-actions {
    width: 100%;
  }

  .auto-reply-selection-actions .ghost,
  .auto-reply-selection-actions .fill {
    justify-content: center;
    flex: 1;
  }
}

@media (max-width: 560px) {
  .auto-reply-shell,
  .auto-reply-hero,
  .auto-reply-left-column,
  .auto-reply-right-column,
  .auto-reply-side-stack {
    gap: 12px;
  }

  .auto-reply-error-summary {
    gap: 4px;
    padding: 12px 14px;
    border-radius: 14px;
    font-size: 13px;
  }

  .auto-reply-error-summary p {
    font-size: 12px;
    line-height: 1.5;
  }

  .auto-reply-hero-head {
    gap: 12px;
  }

  .auto-reply-hero-pill {
    min-height: 28px;
    padding: 0 10px;
    font-size: 10px;
  }

  .auto-reply-hero-copy h1 {
    margin: 8px 0;
    font-size: 28px;
    line-height: 1.1;
  }

  .auto-reply-hero-copy p {
    font-size: 13px;
    line-height: 1.65;
  }

  .auto-reply-hero-main,
  .auto-reply-hero-side,
  .auto-reply-panel {
    border-radius: 20px;
  }

  .auto-reply-hero-main {
    padding: 18px;
  }

  .auto-reply-hero-kicker {
    min-height: 28px;
    padding: 0 10px;
    font-size: 11px;
  }

  .auto-reply-hero-main h2 {
    margin: 10px 0 8px;
    font-size: 24px;
    line-height: 1.2;
    letter-spacing: -0.03em;
  }

  .auto-reply-hero-main p {
    margin-bottom: 12px;
    font-size: 13px;
    line-height: 1.65;
  }

  .auto-reply-hero-pill-row {
    gap: 6px;
    margin-bottom: 14px;
  }

  .auto-reply-hero-pill-row span {
    min-height: 28px;
    padding: 0 10px;
    font-size: 11px;
  }

  .auto-reply-hero-metrics,
  .auto-reply-metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .auto-reply-hero-metric {
    min-width: 0;
    padding: 10px 8px;
    border-radius: 14px;
  }

  .auto-reply-hero-metric b {
    margin-bottom: 3px;
    font-size: 20px;
    line-height: 1.1;
  }

  .auto-reply-hero-metric span {
    font-size: 11px;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  .auto-reply-hero-side {
    gap: 12px;
    padding: 16px;
  }

  .auto-reply-hero-side-top h3 {
    margin-bottom: 5px;
    font-size: 12px;
  }

  .auto-reply-hero-side-top strong {
    font-size: 22px;
    line-height: 1.16;
    overflow-wrap: anywhere;
  }

  .auto-reply-side-pill {
    min-height: 28px;
    padding: 0 10px;
    font-size: 11px;
  }

  .auto-reply-side-note {
    padding: 12px;
    border-radius: 16px;
  }

  .auto-reply-side-note strong {
    margin-bottom: 4px;
    font-size: 13px;
  }

  .auto-reply-side-note p {
    font-size: 12px;
    line-height: 1.6;
  }

  .auto-reply-side-list {
    gap: 8px;
  }

  .auto-reply-side-item {
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 14px;
  }

  .auto-reply-side-item b {
    margin-bottom: 2px;
    font-size: 11px;
  }

  .auto-reply-side-item strong {
    font-size: 15px;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }

  .auto-reply-status-chip {
    min-height: 24px;
    padding: 0 8px;
    font-size: 11px;
  }

  .auto-reply-metric-card {
    min-width: 0;
    min-height: 0;
    padding: 10px;
    border-radius: 14px;
  }

  .auto-reply-metric-card b {
    min-height: 24px;
    max-width: 100%;
    margin-bottom: 8px;
    padding: 0 8px;
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .auto-reply-metric-card strong {
    margin-bottom: 4px;
    font-size: 20px;
    line-height: 1.1;
  }

  .auto-reply-metric-card span {
    font-size: 11px;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }
}

@media (max-width: 340px) {
  .auto-reply-hero-copy h1 {
    font-size: 26px;
  }

  .auto-reply-hero-main,
  .auto-reply-hero-side {
    padding: 14px;
  }

  .auto-reply-hero-main h2 {
    font-size: 22px;
  }

  .auto-reply-hero-metrics,
  .auto-reply-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px;
  }

  .auto-reply-hero-metric,
  .auto-reply-metric-card {
    padding: 8px;
  }

  .auto-reply-hero-metric:last-child,
  .auto-reply-metric-card:last-child {
    grid-column: 1 / -1;
  }

  .auto-reply-hero-metric:last-child {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .auto-reply-hero-metric:last-child b {
    flex: none;
    margin-bottom: 0;
  }

  .auto-reply-metric-card:last-child {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .auto-reply-metric-card:last-child b,
  .auto-reply-metric-card:last-child strong {
    flex: none;
    margin-bottom: 0;
  }

  .auto-reply-metric-card:last-child span {
    min-width: 0;
  }
}
</style>
