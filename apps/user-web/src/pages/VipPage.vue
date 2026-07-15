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
          <div v-else class="vip-plan-grid" :aria-busy="loading ? 'true' : 'false'">
          <article
            v-for="plan in displayPlans"
            :key="plan.planCode"
            class="vip-plan vip-card-surface"
            :class="[plan.cardClass, { recommend: plan.level === 'vip' }]"
          >
            <div v-if="plan.ribbon" class="vip-ribbon" :class="{ warm: plan.level === 'svp' }">{{ plan.ribbon }}</div>
            <div class="vip-plan-head">
              <div>
                <strong>{{ plan.planName }}</strong>
                <h3>{{ plan.price }} <small v-if="plan.durationLabel">/{{ plan.durationLabel }}</small></h3>
              </div>
              <div class="vip-plan-ornament" :class="plan.ornament"><Icon :name="plan.level === 'normal' ? 'diamond' : 'crown'" /></div>
            </div>
            <p>{{ plan.summary }}</p>
            <ul>
              <li v-for="item in plan.features" :key="item">{{ item }}</li>
            </ul>
            <button class="vip-btn" :class="plan.buttonClass" type="button" :disabled="plan.level !== 'normal' && !plan.canPurchase" @click="handlePlanClick(plan)">
              {{ plan.level === 'normal' ? '当前套餐' : plan.level === 'unknown' ? '套餐标识无效' : plan.canPurchase ? '立即升级' : '价格未配置' }}
            </button>
          </article>
        </div>

        <div class="vip-compare vip-card-surface">
          <div class="vip-panel-title">
            <div>
              <h3>功能对比</h3>
              <p>不同会员等级的核心功能差异一目了然</p>
            </div>
          </div>
          <div class="vip-compare-wrap">
            <table>
              <thead>
                <tr>
                  <th>功能特性</th>
                  <th>普通用户</th>
                  <th>VIP用户</th>
                  <th>SVIP用户</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in compareRows" :key="row.name">
                  <td>{{ row.name }}</td>
                  <td>{{ row.free }}</td>
                  <td>{{ row.vip }}</td>
                  <td>{{ row.svip }}</td>
                </tr>
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
import { computed, onMounted, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import PaymentModal from '../components/PaymentModal.vue'
import EmptyState from '../components/EmptyState.vue'
import { getBillingPlans } from '../api/billing.js'
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
const loadError = ref('')
const loading = ref(true)
const paymentVisible = ref(false)
const selectedPlan = ref(null)
const avatarLoadFailed = ref(false)
let plansRequestId = 0

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
  if (code === 'svip') return 'svp'
  if (code === 'svp' || code === 'vip') return code
  if (code === 'normal') return 'normal'
  return 'unknown'
}

const displayPlans = computed(() => {
  return plans.value.map(raw => {
    const level = normalizeLevel(raw)
    const durationLabel = raw.durationText && raw.durationText !== '永久' ? raw.durationText : ''
    const planName = raw.planName || (level === 'svp' ? 'SVP 用户' : level === 'vip' ? 'VIP 用户' : level === 'normal' ? '普通用户' : '套餐名称未配置')
    const priceCent = Number(raw.priceCent)
    const hasPrice = raw.price !== null && raw.price !== undefined && String(raw.price).trim() !== ''
    const canPurchase = ['vip', 'svp'].includes(level) && hasPrice && Number.isFinite(priceCent) && priceCent > 0
    return {
      ...raw,
      level,
      planName,
      price: hasPrice ? String(raw.price) : '价格未配置',
      canPurchase,
      durationLabel,
      summary: raw.summary || raw.description || '具体权益与限制以后台套餐配置为准',
      features: Array.isArray(raw.features) ? raw.features : [],
      cardClass: level === 'svp' ? 'svip' : level,
      ornament: level === 'svp' ? 'warm' : level === 'vip' ? 'blue' : 'muted',
      buttonClass: level === 'svp' ? 'vip-btn-warm' : level === 'vip' ? 'vip-btn-primary' : 'vip-btn-ghost',
      ribbon: raw.ribbon || (raw.recommended === true ? '推荐' : '')
    }
  })
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

const currentPlanQuota = computed(() => {
  const rawCurrentCode = props.user?.activePlan?.planCode || props.user?.planCode
  if (!rawCurrentCode) return '额度状态未提供'
  const currentCode = String(rawCurrentCode).trim().toLowerCase()
  const currentLevel = normalizeLevel({ planCode: currentCode })
  const current = displayPlans.value.find(plan => String(plan.planCode || '').trim().toLowerCase() === currentCode || plan.level === currentLevel)
  if (!current) return '以套餐配置为准'
  const accountQuota = current.maxAccounts ?? current.maxXianyuAccounts
  const goodsQuota = current.maxGoodsCount
  if (accountQuota === null || accountQuota === undefined || goodsQuota === null || goodsQuota === undefined) return '额度未提供'
  return `${accountQuota}账号 / ${goodsQuota}商品`
})

const compareRows = computed(() => {
  const byLevel = Object.fromEntries(displayPlans.value.map(plan => [plan.level, plan]))
  const featureValue = (level, key, fallback = '—') => {
    const plan = byLevel[level]
    if (!plan) return fallback
    if (key === 'accounts') {
      const value = plan.maxAccounts ?? plan.maxXianyuAccounts
      return value === null || value === undefined ? '未配置' : `${value}个`
    }
    if (key === 'goods') return plan.maxGoodsCount === null || plan.maxGoodsCount === undefined ? '未配置' : `${plan.maxGoodsCount}个`
    if (key === 'ai') {
      const value = plan.aiQuota ?? plan.maxAiReplyPerDay
      return value === null || value === undefined ? '未配置' : `${value}次/日`
    }
    if (key === 'autoDelivery') return plan.enableAutoDelivery === true ? '✓' : plan.enableAutoDelivery === false ? '—' : '未配置'
    if (key === 'workflow') return plan.enableWorkflowValue === true ? '✓' : plan.enableWorkflowValue === false ? '—' : '未配置'
    return fallback
  }
  return [
    { name: '可绑定闲鱼账号', free: featureValue('normal', 'accounts'), vip: featureValue('vip', 'accounts'), svip: featureValue('svp', 'accounts') },
    { name: '可管理商品数', free: featureValue('normal', 'goods'), vip: featureValue('vip', 'goods'), svip: featureValue('svp', 'goods') },
    { name: 'AI 回复额度', free: featureValue('normal', 'ai'), vip: featureValue('vip', 'ai'), svip: featureValue('svp', 'ai') },
    { name: '自动发货', free: featureValue('normal', 'autoDelivery'), vip: featureValue('vip', 'autoDelivery'), svip: featureValue('svp', 'autoDelivery') },
    { name: '自动化发布工作流', free: featureValue('normal', 'workflow'), vip: featureValue('vip', 'workflow'), svip: featureValue('svp', 'workflow') }
  ]
})

const coreFeatures = [
  { icon: 'paper-plane', title: '发布商品', theme: 'blue' },
  { icon: 'gift', title: '商机挖掘', theme: 'purple' },
  { icon: 'headset', title: '智能客服', theme: 'orange' },
  { icon: 'book', title: '知识库配置', theme: 'green' },
  { icon: 'workflow', title: '自动化工作流', theme: 'pink' },
  { icon: 'chart', title: '高效运营', theme: 'indigo' }
]

const faqs = [
  { q: 'VIP 与普通用户有什么区别？', a: '权益由后台套餐管理动态控制，前台不再维护一份静态套餐。' },
  { q: '如何升级会员？', a: '点击“立即升级”后，系统会展示后台当前启用的支付方式；未配置价格或支付渠道时会明确提示不可用。' },
  { q: '会员是否按账号独立生效？', a: '会员状态按当前登录用户生效；账号数量等限制以后台返回的套餐权益为准。' },
  { q: '套餐价格从哪里来？', a: '来自 billing_plan 表，与后台套餐管理保持一致。' }
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

async function handlePlanClick(plan) {
  if (!plan || plan.level === 'normal' || !plan.canPurchase) return
  await globalConfirm.alert('暂未开放', '会员升级功能暂未开放，敬请期待。')
}

async function handlePaid() {
  paymentVisible.value = false
  await loadPlans()
}

async function showFaqNotice() {
  await globalConfirm.alert(
    '会员说明',
    '套餐价格、权益和可用支付方式均以当前后台配置为准。若页面提示不可用，请联系“关于”页所列支持渠道。'
  )
}

onMounted(loadPlans)
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
  padding-left: 18px;
  color: #526079;
  line-height: 1.45;
  font-size: 13px;
}

.vip-plan li::before {
  content: '•';
  position: absolute;
  left: 0;
  top: -1px;
  color: #2f66ff;
  font-size: 18px;
  line-height: 1;
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

.vip-compare-wrap {
  overflow: auto;
}

.vip-compare-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.vip-compare-wrap th,
.vip-compare-wrap td {
  padding: 12px 10px;
  border-bottom: 1px solid #edf2fb;
  text-align: center;
  white-space: nowrap;
}

.vip-compare-wrap th:first-child,
.vip-compare-wrap td:first-child {
  text-align: left;
}

.vip-compare-wrap thead th {
  font-size: 12px;
  color: #66748d;
  font-weight: 800;
  background: #fbfcff;
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
}
</style>
