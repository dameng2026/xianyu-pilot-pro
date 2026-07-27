<template>
  <section class="vip-center-page">
    <div class="vip-shell">
      <div class="vip-main">
        <div class="vip-hero vip-card-surface">
          <div class="vip-hero-copy">
            <div class="vip-badge">VIP会员中心</div>
            <h2>升级会员，解锁更多高效功能</h2>
            <p>让闲鱼运营更智能、更高效、更轻松</p>
            <div class="vip-points">
              <div v-for="item in heroPoints" :key="item.title" class="vip-point">
                <span class="vip-point-icon"><Icon :name="item.icon" /></span>
                <div>
                  <b>{{ item.title }}</b>
                  <small>{{ item.desc }}</small>
                </div>
              </div>
            </div>
          </div>
          <div class="vip-hero-art" aria-hidden="true">
            <div class="vip-glow"></div>
            <div class="vip-card-3d">
              <span>VIP</span>
              <i class="vip-crown">👑</i>
            </div>
            <div class="vip-float float-a"><Icon name="chart" /></div>
            <div class="vip-float float-b"><Icon name="star" /></div>
            <div class="vip-float float-c"><Icon name="gift" /></div>
          </div>
        </div>

        <!-- 会员充值限时活动通知横幅 -->
        <div
          v-if="promotionNotice"
          class="vip-promotion-banner"
          :class="[`pos-${promotionNotice.position}`, `icon-${promotionNotice.icon}`]"
          role="status"
        >
          <div class="vip-promo-banner-icon" aria-hidden="true">
            <span v-if="promotionNotice.icon === 'hot'">🔥</span>
            <span v-else-if="promotionNotice.icon === 'time'">⏰</span>
            <span v-else-if="promotionNotice.icon === 'gift'">🎁</span>
            <span v-else-if="promotionNotice.icon === 'star'">⭐</span>
            <span v-else>📣</span>
          </div>
          <div class="vip-promo-banner-body">
            <strong>{{ promotionNotice.title }}</strong>
            <p v-if="promotionNotice.content">{{ promotionNotice.content }}</p>
            <div class="vip-promo-banner-meta">
              <span v-if="promotionCountdown" class="vip-promo-countdown">⏱ {{ promotionCountdown }}</span>
              <span v-if="promotionEndTimeText" class="vip-promo-endtime">截止：{{ promotionEndTimeText }}</span>
            </div>
          </div>
        </div>

        <EmptyState
          v-if="loading && !displayPlans.length"
          icon="…"
          title="正在加载套餐"
          description="正在读取后台最新套餐与权益配置，请稍候。"
        />
        <EmptyState v-else-if="loadError" variant="error" :title="loadError" description="请稍后重试或检查后台套餐配置">
          <template #actions>
            <button class="vip-btn vip-btn-outline" type="button" :disabled="loading" @click="loadPlans">
              {{ loading ? '正在重试…' : '重试' }}
            </button>
          </template>
        </EmptyState>
        <EmptyState v-else-if="!loading && !displayPlans.length" icon="📭" title="暂无可选套餐" description="后台尚未配置套餐，请联系管理员。" />
        <template v-else>
          <div class="vip-period-switcher">
            <button
              v-for="opt in periodOptions"
              :key="opt.value"
              :class="['vip-period-btn', { active: selectedPeriod === opt.value }]"
              type="button"
              @click="selectedPeriod = opt.value"
            >
              <span class="vip-period-label">{{ opt.label }}</span>
              <small class="vip-period-hint">{{ opt.hint }}</small>
            </button>
          </div>
          <EmptyState v-if="!hasPaidPlans" icon="📭" :title="`暂无${currentPeriodLabel}`" description="该周期暂未配置可购买套餐，请选择其他周期。" />
          <div v-else class="vip-plan-grid" :aria-busy="loading ? 'true' : 'false'">
          <article
            v-for="plan in displayPlans"
            :key="plan.id || plan.planCode"
            class="vip-plan vip-card-surface"
            :class="[plan.cardClass, { recommend: plan.level === 'vip', 'has-promotion': plan.hasActivePrice, 'quota-full': plan.quotaFull }]"
          >
            <div v-if="plan.hasActivePrice && plan.activityTag" class="vip-promo-tag">{{ plan.activityTag }}</div>
            <div v-else-if="plan.ribbon" class="vip-ribbon" :class="{ warm: plan.level === 'svp' }">{{ plan.ribbon }}</div>
            <div class="vip-plan-head">
              <div>
                <strong>{{ plan.planName }}</strong>
                <h3 v-if="plan.hasActivePrice" class="vip-plan-price-active">
                  <span class="vip-price-currency">¥</span>{{ plan.activityPriceYuan }}
                  <small v-if="plan.periodLabel">/{{ plan.periodLabel }}</small>
                </h3>
                <h3 v-else>{{ plan.price }} <small v-if="plan.periodLabel">/{{ plan.periodLabel }}</small></h3>
                <div v-if="plan.hasActivePrice" class="vip-price-original-row">
                  <span class="vip-price-strike">{{ plan.strikethroughPrice }}</span>
                  <span v-if="plan.discountYuan && Number(plan.discountYuan) > 0" class="vip-price-discount">立省 ¥{{ plan.discountYuan }}</span>
                  <span v-else-if="plan.discountRate && Number(plan.discountRate) > 0" class="vip-price-discount">{{ plan.discountRate }}折</span>
                </div>
              </div>
              <div class="vip-plan-ornament" :class="plan.ornament"><Icon :name="plan.level === 'normal' ? 'diamond' : 'crown'" /></div>
            </div>
            <p>{{ plan.summary }}</p>
            <ul v-if="plan.features && plan.features.length">
              <li v-for="item in plan.features" :key="item">{{ item }}</li>
            </ul>

            <!-- 活动名额进度（基于真实数据） -->
            <div v-if="plan.hasActivePrice && plan.quota > 0 && (plan.showQuota || plan.showRemain || plan.showSold)" class="vip-promo-quota">
              <div class="vip-promo-quota-bar">
                <div class="vip-promo-quota-fill" :style="{ width: `${plan.quotaProgress}%` }"></div>
              </div>
              <div class="vip-promo-quota-text">
                <span v-if="plan.showSold">已售 <b>{{ plan.soldCount }}</b> 份</span>
                <span v-if="plan.showQuota">/ 限量 <b>{{ plan.quota }}</b> 份</span>
                <span v-if="plan.showRemain && plan.remainCount >= 0" class="vip-promo-remain">剩余 <b>{{ plan.remainCount }}</b> 份</span>
              </div>
            </div>
            <div v-else-if="plan.hasActivePrice && plan.quota === 0 && plan.showSold" class="vip-promo-quota-static">
              <span>已售 <b>{{ plan.soldCount }}</b> 份 · 活动期间不限量</span>
            </div>

            <!-- 活动倒计时（仅在活动价生效时展示） -->
            <div v-if="plan.hasActivePrice && promotionCountdown" class="vip-promo-card-countdown">
              ⏱ {{ promotionCountdown }}
            </div>

            <button class="vip-btn" :class="plan.buttonClass" type="button" :disabled="plan.level !== 'normal' && !plan.canPurchase" @click="handlePlanClick(plan)">
              {{ plan.level === 'normal' ? '当前套餐' : plan.level === 'unknown' ? '套餐标识无效' : plan.quotaFull ? '名额已售罄' : plan.canPurchase ? (plan.hasActivePrice ? '立即抢购' : '立即升级') : '价格未配置' }}
            </button>
          </article>
        </div>
        </template>

        <div class="vip-compare vip-card-surface">
          <div class="vip-panel-title">
            <div>
              <h3>功能对比</h3>
              <p>数据来源：后台「系统运维 → 功能管理」配置，与个人中心「会员等级功能对比」共用同一份数据源。✓ 表示该等级可用，— 表示该等级不可用。</p>
            </div>
            <button
              type="button"
              class="vip-compare-refresh"
              :disabled="memberComparisonLoading"
              @click="loadMemberComparison"
            >{{ memberComparisonLoading ? '加载中…' : '刷新' }}</button>
          </div>
          <div class="vip-compare-wrap">
            <EmptyState
              v-if="memberComparisonError"
              variant="error"
              title="功能对比数据加载失败"
              :description="memberComparisonError"
            >
              <template #actions>
                <button type="button" class="vip-btn vip-btn-outline" @click="loadMemberComparison">重新加载</button>
              </template>
            </EmptyState>
            <EmptyState
              v-else-if="!memberComparisonLoading && memberCompareData.length === 0"
              variant="default"
              title="暂无功能对比数据"
              description="后台尚未配置功能开关，请前往管理端「系统运维 → 功能管理」初始化默认配置后再查看。"
            />
            <table v-else class="vip-compare-table">
              <thead>
                <tr>
                  <th class="vip-th-feature">功能 / 权益</th>
                  <th class="vip-th-normal">普通会员</th>
                  <th class="vip-th-vip">VIP会员</th>
                  <th class="vip-th-svip">
                    <div class="vip-svip-th-inner">
                      <span class="vip-svip-crown" aria-hidden="true">
                        <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                          <path d="M2 13l2-7 4 3.5 4-3.5 2 7H2z" fill="#d97706"/>
                          <path d="M4 6l4 3.5L12 6l-1 5H5L4 6z" fill="#fbbf24"/>
                        </svg>
                      </span>
                      SVIP会员
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(group, gIdx) in memberCompareData" :key="'g'+gIdx">
                  <tr class="vip-group-row">
                    <td colspan="4">
                      <span class="vip-feature-ico" aria-hidden="true">{{ group.icon }}</span>
                      <span class="vip-group-label">{{ group.category }}</span>
                      <span class="vip-group-count">{{ group.items.length }} 项</span>
                    </td>
                  </tr>
                  <tr v-for="(item, iIdx) in group.items" :key="'i'+gIdx+'-'+iIdx" :class="['vip-feature-row', { 'vip-feature-row-alt': iIdx % 2 === 1 }]">
                    <td class="vip-td-name">{{ item.name }}</td>
                    <td class="vip-td-normal" :class="{ 'vip-mark-on': item.normal === '✓', 'vip-mark-off': item.normal !== '✓' }">
                      <span v-if="item.normal === '✓'" class="vip-check-ico">
                        <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#16a34a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                      </span>
                      <span v-else class="vip-dash">—</span>
                    </td>
                    <td class="vip-td-vip" :class="{ 'vip-mark-on': item.vip === '✓', 'vip-mark-off': item.vip !== '✓' }">
                      <span v-if="item.vip === '✓'" class="vip-check-ico">
                        <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#16a34a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                      </span>
                      <span v-else class="vip-dash">—</span>
                    </td>
                    <td class="vip-td-svip" :class="{ 'vip-mark-on': item.svip === '✓', 'vip-mark-off': item.svip !== '✓' }">
                      <span v-if="item.svip === '✓'" class="vip-check-ico vip-check-gold">
                        <svg viewBox="0 0 16 16" width="18" height="18"><circle cx="8" cy="8" r="7" fill="#fef3c7" stroke="#d97706" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#d97706" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                      </span>
                      <span v-else class="vip-dash">—</span>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <aside class="vip-side">
        <div class="vip-card-box vip-card-surface vip-profile-box">
          <div class="vip-profile-top">
            <h3>会员信息</h3>
            <span class="vip-profile-watermark"><Icon name="crown" /></span>
          </div>
          <div class="vip-profile-main">
            <img class="vip-profile-avatar" :src="avatarUrl" alt="用户头像" @error="handleAvatarError" />
            <div>
              <strong>{{ displayUserName }}</strong>
              <span>{{ currentPlanName }}</span>
            </div>
          </div>
          <div class="vip-profile-stat-grid">
            <div>
              <span>到期时间</span>
              <b>{{ currentPlanPeriod }}</b>
            </div>
            <div>
              <span>当前权益</span>
              <b>{{ currentPlanQuota }}</b>
            </div>
          </div>
          <button class="vip-btn vip-btn-outline" type="button" :disabled="!recommendedUpgradePlan" @click="handlePlanClick(recommendedUpgradePlan)">
            {{ recommendedUpgradePlan ? '升级会员享更多权益' : '暂无可购买套餐' }}
          </button>
        </div>

        <div class="vip-card-box vip-card-surface">
          <div class="vip-panel-title compact">
            <div>
              <h3>会员核心权益</h3>
            </div>
          </div>
          <div class="vip-feature-grid">
            <div v-for="item in coreFeatures" :key="item.title" class="vip-feature-item">
              <span class="vip-feature-icon" :class="item.theme"><Icon :name="item.icon" /></span>
              <b>{{ item.title }}</b>
            </div>
          </div>
        </div>

        <div class="vip-card-box vip-card-surface vip-faq-box">
          <div class="vip-panel-title compact">
            <div>
              <h3>常见问题</h3>
            </div>
            <button type="button" class="faq-more-btn" @click="showFaqNotice">查看说明</button>
          </div>
          <div class="vip-faq-list">
            <details v-for="item in faqs" :key="item.q">
              <summary>{{ item.q }}</summary>
              <p>{{ item.a }}</p>
            </details>
          </div>
        </div>
      </aside>
    </div>
    <PaymentModal :visible="paymentVisible" order-type="vip" :plan="selectedPlan" @close="paymentVisible = false" @paid="handlePaid" />
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import PaymentModal from '../components/PaymentModal.vue'
import EmptyState from '../components/EmptyState.vue'
import { getBillingPlans } from '../api/billing.js'
import { getFeatureSwitchStatus, getFeatureSwitchComparison } from '../api/feature-switch.js'
import { getActivePromotion, previewPromotionPlan } from '../api/promotion.js'
import { globalConfirm } from '../composables/confirmState.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'

const props = defineProps({
  user: { type: Object, default: () => ({}) }
})

const heroPoints = [
  { icon: 'trend', title: '权益动态配置', desc: '套餐内容以后台实时配置为准' },
  { icon: 'shield', title: '可用状态透明', desc: '缺少价格或支付配置时明确提示' },
  { icon: 'spark', title: '支付结果回查', desc: '订单状态由服务端确认后再生效' }
]

const plans = ref([])
const selectedPeriod = ref('month')
const loadError = ref('')
const loading = ref(true)
const paymentVisible = ref(false)
const selectedPlan = ref(null)
const avatarLoadFailed = ref(false)
let plansRequestId = 0

// 会员充值限时活动
const promotion = ref({})
const promotionLoading = ref(false)
let promotionRequestId = 0
// 服务端时间偏移（毫秒），用于倒计时：localNow - serverNow
let serverClockOffsetMs = 0
const localNowTick = ref(Date.now())
let countdownTimer = null

// 会员功能对比：与个人中心 ProfileCenterPage 共用同一份后台「功能管理」数据源
const memberCompareFeatures = ref([])
const memberComparisonLoading = ref(false)
const memberComparisonError = ref('')

/**
 * 功能分组定义，与后台 admin-web feature-switch/index.vue 的 GROUPS 常量保持一致。
 * 顺序即展示顺序；未匹配 group 的功能归入 "其他"。
 */
const FEATURE_COMPARISON_GROUPS = [
  { key: 'overview', label: '概览', icon: '📊' },
  { key: 'account', label: '账号与商品', icon: '📦' },
  { key: 'message', label: '消息与商机', icon: '💬' },
  { key: 'automation', label: '自动化', icon: '⚙️' },
  { key: 'system', label: '系统设置', icon: '🛠️' },
  { key: 'hidden', label: '会员', icon: '👑' },
  { key: 'misc', label: '其他', icon: '📂' }
]

const displayUserName = computed(() => props.user?.name || props.user?.username || props.user?.displayName || '当前用户')
const defaultAvatarUrl = '/xya/chat_ui_assets/chat_ui_assets_023.png'
const trustedAvatarUrl = computed(() => resolveTrustedMediaUrl(props.user?.avatar || props.user?.avatarUrl || ''))
const avatarUrl = computed(() => avatarLoadFailed.value ? defaultAvatarUrl : (trustedAvatarUrl.value || defaultAvatarUrl))

watch(trustedAvatarUrl, () => {
  avatarLoadFailed.value = false
})

function handleAvatarError() {
  avatarLoadFailed.value = true
}

const normalizeLevel = plan => {
  const code = String(plan?.level || plan?.planCode || '').trim().toLowerCase()
  if (code.startsWith('svip') || code.startsWith('svp')) return 'svp'
  if (code.startsWith('vip')) return 'vip'
  if (code.startsWith('normal') || code === 'free') return 'normal'
  return 'unknown'
}

const PERIOD_LABELS = { month: '月', quarter: '季', year: '年' }
const periodOptions = [
  { value: 'month', label: '月套餐', hint: '灵活开通' },
  { value: 'quarter', label: '季套餐', hint: '更划算' },
  { value: 'year', label: '年套餐', hint: '最优惠' }
]

const PLAN_DEFAULT_SUMMARY = {
  normal: '基础运营功能全套开放，适合个人闲鱼卖家',
  vip: '在普通会员基础上，解锁商机发掘与货源商城',
  svp: '在 VIP 基础上，解锁工作流自动化与图片生成能力',
  unknown: '具体权益与限制以后台套餐配置为准'
}

const displayPlans = computed(() => {
  // 当前活动套餐映射：key = planId:periodType
  const promotionPlans = promotion.value?.plans || []
  const promotionMap = new Map()
  for (const ap of promotionPlans) {
    const key = `${ap.planId}:${ap.periodType}`
    promotionMap.set(key, ap)
  }
  return plans.value
    .map(raw => {
      const level = normalizeLevel(raw)
      // 所有套餐都显示，按 selectedPeriod 取对应周期价格
      const period = selectedPeriod.value
      const periodLabel = PERIOD_LABELS[period] || ''
      const durationLabel = raw.durationText && raw.durationText !== '永久' ? raw.durationText : ''
      const planName = raw.planName || (level === 'svp' ? 'SVP 用户' : level === 'vip' ? 'VIP 用户' : level === 'normal' ? '普通用户' : '套餐名称未配置')
      // 根据选中周期取对应价格（priceMonth / priceQuarter / priceYear 为格式化字符串；*Cent 为分值）
      const priceField = `price${period.charAt(0).toUpperCase()}${period.slice(1)}`
      const priceCentField = `price${period.charAt(0).toUpperCase()}${period.slice(1)}Cent`
      const priceCent = Number(raw[priceCentField] ?? 0)
      const priceDisplay = raw[priceField]
      const hasPrice = priceDisplay !== null && priceDisplay !== undefined && String(priceDisplay).trim() !== '' && String(priceDisplay).trim() !== '免费' && priceCent > 0
      const canPurchase = ['vip', 'svp'].includes(level) && hasPrice && Number.isFinite(priceCent) && priceCent > 0
      // 前台套餐介绍严格使用后台 featuresText 按行拆分后的数组；为空则不展示任何 li
      const features = Array.isArray(raw.features) ? raw.features : []
      // 注入活动信息：仅当活动状态为 ongoing 且套餐配置存在时生效
      const promotionInfo = promotionMap.get(`${raw.id}:${period}`) || null
      const promotionActive = promotionInfo && promotion.value?.status === 'ongoing'
      // 活动价（分→元）：仅当活动价>0 且 ≤ 原价时才展示为活动价
      const activityPriceCent = promotionInfo ? Number(promotionInfo.activityPriceCent) : 0
      const activityPriceYuan = promotionInfo ? promotionInfo.activityPriceYuan : ''
      const originalPriceYuan = promotionInfo ? promotionInfo.originalPriceYuan : ''
      const discountYuan = promotionInfo ? promotionInfo.discountYuan : ''
      const discountRate = promotionInfo ? promotionInfo.discountRate : ''
      const hasActivePrice = promotionActive
        && activityPriceCent > 0
        && activityPriceCent <= priceCent
        && String(activityPriceYuan || '').trim() !== ''
      // 名额信息（基于真实数据）
      const quota = promotionInfo ? Number(promotionInfo.quota) : 0
      const soldCount = promotionInfo ? Number(promotionInfo.soldCount) : 0
      const remainCount = promotionInfo ? Number(promotionInfo.remainCount) : -1
      const showSold = promotionInfo ? promotionInfo.showSoldCount : false
      const showQuota = promotionInfo ? promotionInfo.showQuota : false
      const showRemain = promotionInfo ? promotionInfo.showRemain : false
      const activityTag = promotionInfo ? promotionInfo.activityTag : ''
      // 名额进度条数据
      const quotaProgress = quota > 0 ? Math.min(100, Math.round((soldCount / quota) * 100)) : 0
      const quotaFull = quota > 0 && remainCount <= 0
      // 实际展示价：活动价优先，否则原价
      const displayPrice = level === 'normal'
        ? '免费'
        : (hasActivePrice ? `¥${activityPriceYuan}` : (hasPrice ? String(priceDisplay) : '价格未配置'))
      const strikethroughPrice = hasActivePrice && originalPriceYuan ? `¥${originalPriceYuan}` : ''
      return {
        ...raw,
        level,
        planName,
        // 普通用户套餐在后台无论配置为免费还是带价，前台统一展示为「免费」
        price: displayPrice,
        canPurchase: canPurchase && !quotaFull,
        durationLabel,
        periodLabel,
        periodType: period,
        summary: raw.summary || raw.description || PLAN_DEFAULT_SUMMARY[level] || '具体权益与限制以后台套餐配置为准',
        features,
        cardClass: level === 'svp' ? 'svip' : level,
        ornament: level === 'svp' ? 'warm' : level === 'vip' ? 'blue' : 'muted',
        buttonClass: level === 'svp' ? 'vip-btn-warm' : level === 'vip' ? 'vip-btn-primary' : 'vip-btn-ghost',
        ribbon: raw.ribbon || (raw.recommended === true ? '推荐' : (level === 'vip' ? '推荐' : '')),
        // 活动相关字段
        promotionInfo,
        hasActivePrice,
        activityPriceYuan,
        originalPriceYuan,
        discountYuan,
        discountRate,
        strikethroughPrice,
        quota,
        soldCount,
        remainCount,
        showSold,
        showQuota,
        showRemain,
        activityTag,
        quotaProgress,
        quotaFull
      }
    })
})

const hasPaidPlans = computed(() => displayPlans.value.some(p => p.level !== 'normal'))
const currentPeriodLabel = computed(() => {
  const opt = periodOptions.find(o => o.value === selectedPeriod.value)
  return opt ? opt.label : ''
})

const recommendedUpgradePlan = computed(() => {
  return displayPlans.value.find(plan => plan.recommended === true && plan.canPurchase)
    || displayPlans.value.find(plan => plan.level === 'vip' && plan.canPurchase)
    || displayPlans.value.find(plan => plan.canPurchase)
    || null
})

const currentPlanName = computed(() => {
  const rawCurrentCode = props.user?.activePlan?.planCode || props.user?.planCode
  if (!rawCurrentCode && !props.user?.activePlan?.planName) return '权益状态未提供'
  const currentCode = String(rawCurrentCode || '').trim().toLowerCase()
  const currentLevel = normalizeLevel({ planCode: currentCode })
  const current = displayPlans.value.find(plan => String(plan.planCode || '').trim().toLowerCase() === currentCode || plan.level === currentLevel)
  return current?.planName || props.user?.activePlan?.planName || '套餐信息未匹配'
})

const currentPlanPeriod = computed(() => {
  const endTime = props.user?.activePlan?.endTime || props.user?.expireTime || props.user?.planExpireTime
  if (!endTime) return '以后台权益为准'
  const date = new Date(endTime)
  if (Number.isNaN(date.getTime())) return '以后台权益为准'
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
})

// 当前权益描述：不再展示账号数/商品数等数量限制，改为展示套餐功能特性摘要
const currentPlanQuota = computed(() => {
  const rawCurrentCode = props.user?.activePlan?.planCode || props.user?.planCode
  if (!rawCurrentCode) return '额度状态未提供'
  const currentCode = String(rawCurrentCode).trim().toLowerCase()
  const currentLevel = normalizeLevel({ planCode: currentCode })
  const current = displayPlans.value.find(plan => String(plan.planCode || '').trim().toLowerCase() === currentCode || plan.level === currentLevel)
  if (!current) return '以套餐配置为准'
  const featureCount = Array.isArray(current.features) ? current.features.length : 0
  if (featureCount > 0) return `${featureCount} 项权益`
  return '以套餐配置为准'
})

/** 按分组聚合后的对比数据，用于表格渲染（与 ProfileCenterPage 一致） */
const memberCompareData = computed(() => {
  const features = memberCompareFeatures.value
  if (!Array.isArray(features) || features.length === 0) return []
  const buckets = new Map()
  for (const g of FEATURE_COMPARISON_GROUPS) buckets.set(g.key, [])
  for (const f of features) {
    const g = String(f?.group || 'misc')
    if (!buckets.has(g)) buckets.set(g, [])
    buckets.get(g).push(f)
  }
  const result = []
  for (const g of FEATURE_COMPARISON_GROUPS) {
    const items = buckets.get(g.key) || []
    if (items.length === 0) continue
    result.push({
      category: g.label,
      icon: g.icon,
      items: items.map(f => ({
        key: f.key,
        name: f.title || f.key,
        normal: boolToMark(f.normal),
        vip: boolToMark(f.vip),
        svip: boolToMark(f.svp)
      }))
    })
  }
  return result
})

function boolToMark(value) {
  return value === true || value === 'true' || value === 1 || value === '1' ? '✓' : '—'
}

const coreFeatures = [
  { icon: 'paper-plane', title: '发布商品', theme: 'blue' },
  { icon: 'gift', title: '商机挖掘', theme: 'purple' },
  { icon: 'headset', title: '智能客服', theme: 'orange' },
  { icon: 'book', title: '知识库配置', theme: 'green' },
  { icon: 'workflow', title: '自动化工作流', theme: 'pink' },
  { icon: 'chart', title: '高效运营', theme: 'indigo' }
]

const faqs = [
  { q: 'VIP 与普通用户有什么区别？', a: '权益由后台「功能管理」统一控制，前台 VIP 会员中心与个人中心展示同一份功能对比数据。' },
  { q: '如何升级会员？', a: '点击"立即升级"后，系统会展示后台当前启用的支付方式；未配置价格或支付渠道时会明确提示不可用。' },
  { q: '会员是否按账号独立生效？', a: '会员状态按当前登录用户生效；具体可用功能以后台「功能管理」配置为准。' },
  { q: '功能对比数据从哪里来？', a: '来自后台「系统运维 → 功能管理」配置，与个人中心「会员等级功能对比」共用同一份数据源。' }
]

async function loadPlans() {
  const requestId = ++plansRequestId
  loading.value = true
  loadError.value = ''
  try {
    const data = await getBillingPlans()
    if (!Array.isArray(data)) throw new Error('套餐列表响应格式异常')
    if (requestId !== plansRequestId) return
    plans.value = data
  } catch (e) {
    if (requestId !== plansRequestId) return
    plans.value = []
    loadError.value = e?.message || '套餐加载失败'
  } finally {
    if (requestId === plansRequestId) loading.value = false
  }
}

async function loadPromotion() {
  const requestId = ++promotionRequestId
  promotionLoading.value = true
  try {
    const data = await getActivePromotion()
    if (requestId !== promotionRequestId) return
    // 计算服务端时间偏移
    const serverNow = data?.serverNow ? new Date(data.serverNow).getTime() : Date.now()
    serverClockOffsetMs = Date.now() - serverNow
    promotion.value = data || {}
  } catch (e) {
    if (requestId !== promotionRequestId) return
    // 活动查询失败时降级为无活动，套餐仍展示原价
    promotion.value = {}
  } finally {
    if (requestId === promotionRequestId) promotionLoading.value = false
  }
}

async function loadMemberComparison() {
  memberComparisonLoading.value = true
  memberComparisonError.value = ''
  try {
    const list = await getFeatureSwitchComparison()
    memberCompareFeatures.value = Array.isArray(list) ? list : []
    return true
  } catch (error) {
    memberCompareFeatures.value = []
    memberComparisonError.value = error?.message || '功能对比数据加载失败'
    return false
  } finally {
    memberComparisonLoading.value = false
  }
}

// 服务端当前时间（毫秒）
const serverNowMs = computed(() => localNowTick.value - serverClockOffsetMs)

// 活动是否有效（前台展示）
const hasActivePromotion = computed(() => {
  const p = promotion.value
  return !!p && (p.status === 'ongoing' || p.status === 'pending') && Array.isArray(p.plans) && p.plans.length > 0
})

// 活动通知（仅当 visible=true 且非空时展示）
const promotionNotice = computed(() => {
  const p = promotion.value
  if (!p || !hasActivePromotion.value) return null
  const notice = p.notice || {}
  if (!notice.visible) return null
  if (!notice.title && !notice.content) return null
  return {
    title: notice.title || p.activityName || '会员限时优惠',
    content: notice.content || '',
    position: notice.position || 'top',
    icon: notice.icon || 'hot'
  }
})

// 活动倒计时文案
const promotionCountdown = computed(() => {
  const p = promotion.value
  if (!p || p.status !== 'ongoing') return ''
  if (Number(p.isLongTerm) === 1) return '长期活动'
  const endTime = p.endTime ? new Date(p.endTime).getTime() : 0
  if (!endTime) return ''
  const diff = endTime - serverNowMs.value
  if (diff <= 0) return '已结束'
  const days = Math.floor(diff / 86400000)
  const hours = Math.floor((diff % 86400000) / 3600000)
  const minutes = Math.floor((diff % 3600000) / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  if (days > 0) return `剩 ${days} 天 ${hours} 时 ${minutes} 分`
  if (hours > 0) return `剩 ${hours} 时 ${minutes} 分 ${seconds} 秒`
  if (minutes > 0) return `剩 ${minutes} 分 ${seconds} 秒`
  return `剩 ${seconds} 秒`
})

// 活动结束时间展示文案
const promotionEndTimeText = computed(() => {
  const p = promotion.value
  if (!p) return ''
  if (Number(p.isLongTerm) === 1) return '长期活动'
  const endTime = p.endTime
  if (!endTime) return ''
  const d = new Date(endTime)
  if (Number.isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  const hh = `${d.getHours()}`.padStart(2, '0')
  const mm = `${d.getMinutes()}`.padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
})

// 不可用原因映射
function mapUnavailableReason(reason) {
  switch (reason) {
    case 'no_activity': return '当前套餐未参与活动'
    case 'activity_not_started': return '活动尚未开始'
    case 'activity_ended': return '活动已结束'
    case 'activity_closed': return '活动已关闭'
    case 'quota_full': return '活动名额已用完'
    case 'plan_offline': return '套餐已下架'
    case 'price_invalid': return '活动价格异常，请刷新页面后重试'
    default: return '活动不可用，请刷新页面后重试'
  }
}

async function handlePlanClick(plan) {
  if (!plan || plan.level === 'normal' || !plan.canPurchase) return
  // 检查"升级会员"功能开关：开启则弹出充值弹窗，关闭则提示暂未开放
  try {
    const status = await getFeatureSwitchStatus()
    if (status?.accessible?.['member-upgrade'] !== true) {
      await globalConfirm.alert('暂未开放', '会员升级功能暂未开放，敬请期待。')
      return
    }
  } catch (e) {
    // 查询失败时降级为提示暂未开放
    await globalConfirm.alert('暂未开放', '会员升级功能暂未开放，敬请期待。')
    return
  }
  // 如果套餐有活动价，调用服务端 preview 进行二次确认
  if (plan.hasActivePrice && plan.promotionInfo) {
    try {
      const preview = await previewPromotionPlan(plan.id, plan.periodType)
      if (!preview.available) {
        // 活动已不可用：刷新活动状态后提示用户
        loadPromotion()
        const reason = mapUnavailableReason(preview.reason)
        await globalConfirm.alert('活动已变化', `${reason}，请按当前页面价格重新下单。`)
        return
      }
      // 校验价格/名额是否变化
      const previewFinalYuan = String(preview.finalPriceYuan || '')
      const localFinalYuan = String(plan.activityPriceYuan || '')
      const previewRemain = Number(preview.remainCount)
      const localRemain = Number(plan.remainCount)
      let changedMessage = ''
      if (previewFinalYuan && previewFinalYuan !== localFinalYuan) {
        changedMessage = `活动价格已变化：原显示 ¥${localFinalYuan}，当前服务端最终价 ¥${previewFinalYuan}`
      } else if (plan.quota > 0 && previewRemain !== localRemain) {
        changedMessage = `活动剩余名额已变化：原显示 ${localRemain} 份，当前剩余 ${previewRemain} 份`
      }
      if (changedMessage) {
        // 价格或名额变化：必须让用户明确确认，不能静默修改
        const confirmed = await globalConfirm.confirm('活动信息已变化', `${changedMessage}\n是否按服务端最新价格 ¥${previewFinalYuan} 继续下单？`)
        if (!confirmed) {
          loadPromotion()
          return
        }
        // 注入服务端最新数据后开窗
        selectedPlan.value = {
          ...plan,
          activityPriceYuan: previewFinalYuan,
          activityPriceCent: Number(preview.finalPriceCent || plan.promotionInfo.activityPriceCent),
          originalPriceYuan: preview.originalPriceYuan || plan.originalPriceYuan,
          originalPriceCent: Number(preview.originalPriceCent || plan.promotionInfo.originalPriceCent),
          remainCount: previewRemain,
          ruleVersion: Number(preview.ruleVersion || plan.promotionInfo.ruleVersion),
          promotionSnapshot: {
            activityId: preview.activityId || promotion.value?.id,
            activityPlanId: preview.activityPlanId || plan.promotionInfo.activityPlanId,
            activityName: preview.activityName || promotion.value?.activityName,
            finalPriceYuan: previewFinalYuan,
            finalPriceCent: Number(preview.finalPriceCent || 0),
            originalPriceYuan: preview.originalPriceYuan || '',
            originalPriceCent: Number(preview.originalPriceCent || 0),
            ruleVersion: Number(preview.ruleVersion || 0),
            endTime: preview.endTime || promotion.value?.endTime
          }
        }
        paymentVisible.value = true
        return
      }
      // 价格/名额未变化，正常下单：注入服务端 preview 数据作为快照
      selectedPlan.value = {
        ...plan,
        promotionSnapshot: {
          activityId: preview.activityId || promotion.value?.id,
          activityPlanId: preview.activityPlanId || plan.promotionInfo.activityPlanId,
          activityName: preview.activityName || promotion.value?.activityName,
          finalPriceYuan: previewFinalYuan,
          finalPriceCent: Number(preview.finalPriceCent || 0),
          originalPriceYuan: preview.originalPriceYuan || '',
          originalPriceCent: Number(preview.originalPriceCent || 0),
          ruleVersion: Number(preview.ruleVersion || 0),
          endTime: preview.endTime || promotion.value?.endTime
        }
      }
      paymentVisible.value = true
      return
    } catch (e) {
      // preview 调用失败：阻塞下单，避免用户按过期价格支付
      await globalConfirm.alert('无法确认活动价格', e?.message || '活动价格校验失败，请刷新页面后重试。')
      return
    }
  }
  // 非活动套餐：原流程
  selectedPlan.value = plan
  paymentVisible.value = true
}

async function handlePaid() {
  paymentVisible.value = false
  await Promise.all([loadPlans(), loadPromotion()])
}

async function showFaqNotice() {
  await globalConfirm.alert(
    '会员说明',
    '套餐价格、权益和可用支付方式均以当前后台配置为准。若页面提示不可用，请联系"关于"页所列支持渠道。'
  )
}

onMounted(() => {
  loadPlans()
  loadPromotion()
  loadMemberComparison()
  // 倒计时定时器：每秒刷新一次
  countdownTimer = setInterval(() => {
    localNowTick.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = null
})
</script>

<style scoped>
/* ========================================
   VIP 会员中心 - 全部样式隔离，不影响其他页面
   ======================================== */

/* ----- 基础卡片表面 ----- */
.vip-card-surface {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  box-shadow: var(--shadow);
  border: 1px solid rgba(231, 237, 247, 0.92);
}

/* ----- 页面容器 ----- */
.vip-center-page {
  padding-top: 2px;
}

.vip-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 306px;
  gap: 18px;
  align-items: start;
}

.vip-main {
  display: grid;
  gap: 16px;
  min-width: 0;
}

/* ----- Hero 头部区域 ----- */
.vip-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 10px;
  padding: 18px 18px 16px;
  overflow: hidden;
}

.vip-hero-copy {
  padding: 12px 8px 6px 4px;
}

.vip-badge {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: #edf4ff;
  color: #2e5fe7;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.vip-hero-copy h2 {
  margin: 14px 0 8px;
  font-size: 26px;
  line-height: 1.18;
  color: #18233d;
}

.vip-hero-copy p {
  margin: 0;
  color: #6f7e97;
  font-size: 14px;
  line-height: 1.6;
}

.vip-points {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 20px;
}

.vip-point {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 10px 10px 12px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f9fbff 0%, #f4f8ff 100%);
  border: 1px solid #e8eef8;
}

.vip-point-icon {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  box-shadow: 0 8px 18px rgba(20, 80, 180, 0.08);
}

.vip-point b {
  display: block;
  font-size: 13px;
  line-height: 1.25;
}

.vip-point small {
  display: block;
  margin-top: 4px;
  color: #7a879b;
  line-height: 1.4;
}

/* ----- Hero 右侧插画 ----- */
.vip-hero-art {
  position: relative;
  min-height: 230px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 25% 20%, rgba(74, 134, 255, 0.2), transparent 35%),
    radial-gradient(circle at 78% 20%, rgba(241, 154, 38, 0.12), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
  overflow: hidden;
  border: 1px solid #e8eef8;
}

.vip-glow {
  position: absolute;
  inset: 18px 30px 22px;
  border-radius: 30px;
  background: radial-gradient(circle at 50% 50%, rgba(13, 107, 255, 0.15), transparent 60%);
}

.vip-card-3d {
  position: absolute;
  right: 54px;
  top: 44px;
  width: 172px;
  height: 118px;
  border-radius: 22px;
  background: linear-gradient(160deg, #4a8aff 0%, #2f66ff 55%, #1d3fd0 100%);
  box-shadow: 0 24px 36px rgba(32, 80, 180, 0.22);
  transform: rotate(-12deg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.vip-card-3d span {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-shadow: 0 6px 12px rgba(0, 0, 0, 0.18);
}

.vip-crown {
  position: absolute;
  top: -16px;
  right: 18px;
  font-size: 42px;
  filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.14));
}

.vip-float {
  position: absolute;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 16px 28px rgba(35, 73, 142, 0.12);
  color: var(--primary);
}

.float-a {
  left: 28px;
  top: 24px;
}

.float-b {
  left: 60px;
  bottom: 26px;
  color: var(--purple);
}

.float-c {
  right: 28px;
  bottom: 34px;
  color: var(--orange);
}

/* ----- 周期切换器 ----- */
.vip-period-switcher {
  display: flex;
  gap: 10px;
  padding: 4px 0 14px;
  flex-wrap: wrap;
}

.vip-period-btn {
  flex: 1 1 0;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 18px;
  border-radius: 16px;
  border: 1.5px solid #e3eaf5;
  background: #fff;
  cursor: pointer;
  transition: all 0.22s ease;
  position: relative;
  overflow: hidden;
}

.vip-period-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(47, 102, 255, 0.08), rgba(74, 138, 255, 0.04));
  opacity: 0;
  transition: opacity 0.22s ease;
  pointer-events: none;
}

.vip-period-btn:hover {
  border-color: #c3d4f0;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(35, 73, 142, 0.08);
}

.vip-period-btn.active {
  border-color: #2f66ff;
  background: linear-gradient(135deg, #f4f8ff, #fff);
  box-shadow: 0 10px 22px rgba(47, 102, 255, 0.18);
}

.vip-period-btn.active::before {
  opacity: 1;
}

.vip-period-label {
  position: relative;
  font-size: 15px;
  font-weight: 800;
  color: #18233d;
  letter-spacing: 0.02em;
}

.vip-period-btn.active .vip-period-label {
  color: #2f66ff;
}

.vip-period-hint {
  position: relative;
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
}

.vip-period-btn.active .vip-period-hint {
  color: #5b7bbf;
}

/* ----- 套餐卡片网格 ----- */
.vip-plan-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.vip-plan {
  position: relative;
  padding: 18px 18px 16px;
  overflow: hidden;
  /* 让三个套餐卡片等高，并使按钮底部对齐 */
  display: flex;
  flex-direction: column;
}

/* 按钮被推到卡片底部，保证三个卡片的按钮处于同一水平线 */
.vip-plan > .vip-btn {
  margin-top: auto;
}

.vip-plan.free {
  background: linear-gradient(180deg, #fff 0%, #f9fbff 100%);
}

.vip-plan.vip {
  background: linear-gradient(180deg, #fff 0%, #f8fbff 100%);
}

.vip-plan.svip {
  background: linear-gradient(180deg, #fff 0%, #fffaf2 100%);
}

.vip-plan-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.vip-plan-head strong {
  display: block;
  font-size: 18px;
  line-height: 1.2;
}

.vip-plan-head h3 {
  margin: 10px 0 0;
  font-size: 28px;
  line-height: 1;
  color: #18233d;
}

.vip-plan-head h3 small {
  font-size: 12px;
  color: #77839a;
  font-weight: 600;
}

.vip-plan > p {
  margin: 12px 0 0;
  color: #6f7e97;
  line-height: 1.55;
  font-size: 13px;
}

.vip-plan-ornament {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f6f9ff;
  color: #9fb1d0;
}

.vip-plan-ornament.blue {
  background: #edf4ff;
  color: #2f66ff;
}

.vip-plan-ornament.warm {
  background: #fff3df;
  color: #f59e0b;
}

.vip-plan-ornament.muted {
  background: #f7f9fd;
  color: #bcc7da;
}

.vip-plan ul {
  padding: 0;
  margin: 14px 0 16px;
  list-style: none;
  display: grid;
  gap: 10px;
}

.vip-plan li {
  position: relative;
  padding-left: 22px;
  color: #526079;
  line-height: 1.5;
  font-size: 13px;
}

.vip-plan li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M4 8l2.5 2.5L12 5' stroke='%232f66ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>") center/contain no-repeat;
  box-shadow: 0 0 0 1px #e8eef8 inset;
}

/* 不同等级套餐的权益项颜色差异化 */
.vip-plan.free li::before {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M4 8l2.5 2.5L12 5' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>");
}

.vip-plan.vip li::before {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M4 8l2.5 2.5L12 5' stroke='%232f66ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>");
}

.vip-plan.svip li::before {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M4 8l2.5 2.5L12 5' stroke='%23d97706' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/></svg>");
}

.vip-plan.svip li {
  color: #5b4226;
}

.vip-ribbon {
  position: absolute;
  right: 0;
  top: 0;
  padding: 7px 16px;
  border-radius: 0 18px 0 14px;
  background: linear-gradient(90deg, #2f66ff, #4a8aff);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(47, 102, 255, 0.2);
}

.vip-ribbon.warm {
  background: linear-gradient(90deg, #f59e0b, #ffb647);
}

/* ----- 按钮 ----- */
.vip-btn {
  width: 100%;
  height: 42px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-weight: 800;
  font-size: 14px;
  cursor: pointer;
}

.vip-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}

.vip-btn-ghost {
  background: #fff;
  border-color: #d8e3f2;
  color: #485c7d;
}

.vip-btn-primary {
  background: linear-gradient(90deg, #2f66ff, #4a8aff);
  color: #fff;
}

.vip-btn-warm {
  background: linear-gradient(90deg, #f59e0b, #ffb647);
  color: #fff;
}

.vip-btn-outline {
  background: #fff;
  border-color: #2f66ff;
  color: #2f66ff;
}

/* ----- 功能对比表 ----- */
.vip-compare {
  padding: 18px;
}

.vip-panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.vip-panel-title h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.25;
}

.vip-panel-title p {
  margin: 6px 0 0;
  color: #6f7e97;
  font-size: 12px;
  line-height: 1.6;
}

.vip-compare-refresh {
  flex-shrink: 0;
  height: 30px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #d8e3f2;
  background: #fff;
  color: #2f66ff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
}

.vip-compare-refresh:hover:not(:disabled) {
  background: #edf4ff;
  border-color: #2f66ff;
}

.vip-compare-refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.vip-compare-wrap {
  overflow: auto;
  border-radius: 12px;
  border: 1px solid #edf2fb;
  background: #fff;
}

.vip-compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.vip-compare-table th,
.vip-compare-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #edf2fb;
  text-align: center;
  white-space: nowrap;
}

.vip-compare-table th:first-child,
.vip-compare-table td:first-child {
  text-align: left;
}

.vip-compare-table thead th {
  font-size: 12px;
  color: #66748d;
  font-weight: 800;
  background: linear-gradient(180deg, #fbfcff 0%, #f4f8ff 100%);
  border-bottom: 1px solid #d8e3f2;
  position: sticky;
  top: 0;
  z-index: 1;
}

.vip-th-feature {
  min-width: 160px;
}

.vip-th-normal,
.vip-th-vip,
.vip-th-svip {
  min-width: 100px;
}

.vip-th-vip {
  color: #2f66ff;
}

.vip-th-svip {
  color: #d97706;
}

.vip-svip-th-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
}

.vip-svip-crown {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 分组行 */
.vip-group-row td {
  background: linear-gradient(90deg, #f4f8ff 0%, #fbfcff 100%);
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 800;
  color: #2f3e5f;
  border-bottom: 1px solid #e2e9f5;
}

.vip-feature-ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  font-size: 14px;
}

.vip-group-label {
  margin-right: 8px;
}

.vip-group-count {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  color: #6f7e97;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid #e8eef8;
}

/* 功能行 */
.vip-feature-row {
  transition: background 0.15s ease;
}

.vip-feature-row:hover {
  background: #f9fbff;
}

.vip-feature-row-alt {
  background: #fafcff;
}

.vip-td-name {
  color: #253450;
  font-weight: 600;
}

/* 标记样式 */
.vip-mark-on {
  background: rgba(22, 163, 74, 0.04);
}

.vip-mark-off {
  background: rgba(148, 163, 184, 0.04);
  opacity: 0.7;
}

.vip-check-ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.vip-check-gold {
  filter: drop-shadow(0 2px 4px rgba(217, 119, 6, 0.18));
}

.vip-dash {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 700;
}

/* ----- 右侧栏 ----- */
.vip-side {
  display: grid;
  gap: 14px;
  position: sticky;
  top: 92px;
}

.vip-card-box {
  padding: 16px;
}

/* 会员信息卡片 */
.vip-profile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.vip-profile-top h3 {
  margin: 0;
  font-size: 16px;
}

.vip-profile-watermark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: #edf4ff;
  color: #9ab1da;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vip-profile-main {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.vip-profile-avatar {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 10px 22px rgba(31, 53, 94, 0.12);
}

.vip-profile-main strong {
  display: block;
  font-size: 16px;
  line-height: 1.2;
}

.vip-profile-main span {
  display: inline-flex;
  margin-top: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #edf4ff;
  color: #2f66ff;
  font-size: 12px;
  font-weight: 700;
}

.vip-profile-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.vip-profile-stat-grid div {
  padding: 12px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #edf2fb;
}

.vip-profile-stat-grid span {
  display: block;
  color: #74839b;
  font-size: 12px;
}

.vip-profile-stat-grid b {
  display: block;
  margin-top: 8px;
  font-size: 15px;
  color: #16233d;
}

/* 核心权益网格 */
.vip-feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.vip-feature-item {
  padding: 12px;
  border-radius: 14px;
  background: #f9fbff;
  border: 1px solid #edf2fb;
  display: grid;
  justify-items: start;
  gap: 10px;
}

.vip-feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  box-shadow: 0 10px 20px rgba(31, 53, 94, 0.08);
}

.vip-feature-icon.blue   { color: #2f66ff; }
.vip-feature-icon.purple { color: #8b5cf6; }
.vip-feature-icon.orange { color: #ff9f22; }
.vip-feature-icon.green  { color: #16bf78; }
.vip-feature-icon.pink   { color: #f43f5e; }
.vip-feature-icon.indigo { color: #4f46e5; }

.vip-feature-item b {
  font-size: 13px;
  line-height: 1.35;
  color: #253450;
}

/* 常见问题 */
.vip-faq-box a {
  color: #2f66ff;
  font-size: 12px;
  font-weight: 700;
}

.faq-more-btn {
  border: 0;
  background: transparent;
  color: #2f66ff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.vip-faq-list {
  display: grid;
  gap: 10px;
}

.vip-faq-list details {
  border: 1px solid #edf2fb;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}

.vip-faq-list summary {
  list-style: none;
  cursor: pointer;
  padding: 13px 14px;
  font-weight: 700;
  color: #23324d;
  position: relative;
}

.vip-faq-list summary::-webkit-details-marker {
  display: none;
}

.vip-faq-list summary::after {
  content: '+';
  position: absolute;
  right: 14px;
  top: 12px;
  color: #91a3bf;
  font-size: 18px;
}

.vip-faq-list details[open] summary::after {
  content: '—';
}

.vip-faq-list p {
  margin: 0;
  padding: 0 14px 14px;
  color: #6f7e97;
  line-height: 1.7;
  font-size: 13px;
}

/* ========================================
   响应式适配
   ======================================== */

/* 平板 (768px - 1023px) */
@media (max-width: 1023px) {
  .vip-shell {
    grid-template-columns: 1fr;
  }

  .vip-side {
    position: static;
  }
}

/* 移动端 (320px - 767px) */
@media (max-width: 767px) {
  .vip-hero,
  .vip-plan-grid,
  .vip-points,
  .vip-feature-grid,
  .vip-profile-stat-grid {
    grid-template-columns: 1fr;
  }

  .vip-hero {
    padding: 16px;
  }

  .vip-hero-copy h2 {
    font-size: 22px;
  }

  .vip-hero-art {
    min-height: 210px;
  }

  .vip-card-3d {
    right: 22px;
    top: 42px;
    transform: rotate(-10deg) scale(0.9);
  }

  .vip-plan-head h3 {
    font-size: 24px;
  }

  /* 移动端周期切换器：三按钮等宽排布，紧凑显示 */
  .vip-period-switcher {
    gap: 8px;
    padding: 2px 0 12px;
  }

  .vip-period-btn {
    min-width: 0;
    padding: 12px 6px;
    gap: 2px;
  }

  .vip-period-label {
    font-size: 14px;
  }

  .vip-period-hint {
    font-size: 11px;
  }
}

/* Keep the comparison table scrollable instead of allowing its nowrap cells
   to enlarge the single-column mobile grid beyond the viewport. */
@media (max-width: 900px) {
  .vip-main {
    grid-template-columns: minmax(0, 1fr);
  }

  .vip-main > .vip-card-surface,
  .vip-compare {
    min-width: 0;
    max-width: 100%;
  }

  .vip-compare-wrap {
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .vip-compare-wrap table {
    width: max-content;
    min-width: 560px;
  }

  /* 移动端功能对比表头粘性定位调整 */
  .vip-compare-table thead th {
    position: static;
  }
}

/* 超小屏适配：套餐卡片堆叠 + 功能对比紧凑显示 */
@media (max-width: 480px) {
  .vip-compare {
    padding: 14px;
  }

  .vip-compare-table th,
  .vip-compare-table td {
    padding: 10px 8px;
    font-size: 12px;
  }

  .vip-group-row td {
    padding: 8px 10px;
    font-size: 11px;
  }

  .vip-panel-title {
    flex-direction: column;
    gap: 10px;
  }

  .vip-compare-refresh {
    align-self: flex-start;
  }
}

/* ========================================
   会员充值限时活动 - 样式
   ======================================== */

/* ----- 活动通知横幅 ----- */
.vip-promotion-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fff5e6 0%, #ffe9c7 100%);
  border: 1.5px solid #ffd591;
  box-shadow: 0 10px 24px rgba(245, 158, 11, 0.12);
  position: relative;
  overflow: hidden;
}

.vip-promotion-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 8% 20%, rgba(255, 255, 255, 0.4), transparent 30%);
  pointer-events: none;
}

.vip-promo-banner-icon {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #fff, #fff7ed);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 6px 14px rgba(245, 158, 11, 0.18);
}

.vip-promo-banner-body {
  flex: 1;
  min-width: 0;
}

.vip-promo-banner-body strong {
  display: block;
  font-size: 15px;
  font-weight: 800;
  color: #b45309;
  line-height: 1.3;
}

.vip-promo-banner-body p {
  margin: 4px 0 8px;
  font-size: 13px;
  line-height: 1.55;
  color: #92400e;
}

.vip-promo-banner-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.vip-promo-countdown {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #b45309;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.vip-promo-endtime {
  font-size: 12px;
  color: #92400e;
  font-weight: 600;
}

/* ----- 活动套餐卡片样式 ----- */
.vip-plan.has-promotion {
  border: 1.5px solid #ffd591;
  background: linear-gradient(180deg, #fffaf2 0%, #fff5e6 100%);
  box-shadow: 0 12px 28px rgba(245, 158, 11, 0.14);
}

.vip-plan.has-promotion.recommend {
  border-color: #f59e0b;
  box-shadow: 0 14px 32px rgba(245, 158, 11, 0.2);
}

.vip-plan.quota-full {
  opacity: 0.78;
}

.vip-promo-tag {
  position: absolute;
  right: 0;
  top: 0;
  padding: 7px 16px;
  border-radius: 0 18px 0 14px;
  background: linear-gradient(90deg, #f59e0b, #ffb647);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(245, 158, 11, 0.22);
}

.vip-plan-price-active {
  margin: 10px 0 0;
  font-size: 32px;
  line-height: 1;
  color: #d97706;
  font-weight: 800;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.vip-price-currency {
  font-size: 18px;
  font-weight: 700;
  color: #d97706;
}

.vip-plan-price-active small {
  font-size: 12px;
  color: #92400e;
  font-weight: 600;
}

.vip-price-original-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.vip-price-strike {
  font-size: 13px;
  color: #94a3b8;
  text-decoration: line-through;
  text-decoration-color: #cbd5e1;
}

.vip-price-discount {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
  font-weight: 700;
}

/* 名额进度条 */
.vip-promo-quota {
  margin-top: 14px;
  display: grid;
  gap: 6px;
}

.vip-promo-quota-bar {
  height: 8px;
  border-radius: 999px;
  background: #fde9c8;
  overflow: hidden;
}

.vip-promo-quota-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f59e0b, #ffb647);
  transition: width 0.3s ease;
}

.vip-promo-quota-text {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #92400e;
  font-weight: 600;
}

.vip-promo-quota-text b {
  color: #b45309;
  font-weight: 800;
  margin: 0 2px;
}

.vip-promo-remain {
  margin-left: auto;
}

.vip-promo-remain b {
  color: #d97706;
}

.vip-promo-quota-static {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px dashed #ffd591;
  font-size: 12px;
  color: #92400e;
  font-weight: 600;
}

.vip-promo-quota-static b {
  color: #b45309;
  font-weight: 800;
  margin: 0 2px;
}

.vip-promo-card-countdown {
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: max-content;
}

/* 移动端活动样式适配 */
@media (max-width: 900px) {
  .vip-promotion-banner {
    padding: 12px 14px;
    gap: 10px;
  }

  .vip-promo-banner-icon {
    width: 38px;
    height: 38px;
    font-size: 18px;
  }

  .vip-promo-banner-body strong {
    font-size: 14px;
  }

  .vip-promo-banner-body p {
    font-size: 12px;
  }

  .vip-plan-price-active {
    font-size: 28px;
  }

  .vip-price-currency {
    font-size: 16px;
  }
}

@media (max-width: 480px) {
  .vip-promo-banner-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .vip-promo-quota-text {
    font-size: 11px;
  }

  .vip-promo-quota-static {
    font-size: 11px;
  }
}
</style>
