<template>
  <div class="gp-page">
    <!-- 页头 -->
    <header class="gp-topbar">
      <div class="gp-topbar-title">
        <h1>增长合伙人中心</h1>
        <p>邀请用户注册消费，获得 Token 奖励与现金分成</p>
      </div>
    </header>

    <div v-if="loading" class="gp-loading">
      <div class="gp-spinner"></div>
      <span>正在加载增长合伙人数据...</span>
    </div>

    <template v-else>
      <!-- 拉新有礼 Hero -->
      <section class="gp-hero">
        <div class="gp-hero-copy">
          <h2>拉新有礼，收益双重到账</h2>
          <ul>
            <li>
              <span class="gp-check">✓</span>
              邀请 1 人注册并产生消费行为，立得
              <b>{{ dash.tokenRewardPerReferral ?? 100 }} Token</b>
            </li>
            <li>
              <span class="gp-check">✓</span>
              二级用户首月消费可享分成，最高
              <b>{{ maxCommissionRate }}%</b>
            </li>
            <li>
              <span class="gp-check">✓</span>
              <b>399 年卡示例：</b>最高可得
              <b>{{ estimateYearRewardText }}</b>
            </li>
            <li>
              <span class="gp-check">✓</span>
              余额满 <b>{{ minWithdrawalYuan }} 元</b>即可提现
            </li>
          </ul>
          <div class="gp-hero-actions">
            <button class="gp-btn-primary" @click="openInviteDialog">
              ⌁ 立即邀请
            </button>
            <button class="gp-btn-secondary" @click="copyPromoteLink">
              ⌕ 复制推广链接
            </button>
          </div>
        </div>
        <div class="gp-hero-art">
          <div class="gp-hero-illustration-wrap">
            <img class="gp-hero-illustration" src="../assets/growth-partner/hero-illustration.png" alt="增长合伙人插画" />
            <div class="gp-hero-board-copy">
              <b>收益翻倍</b>
              <strong>+{{ dash.tokenRewardPerReferral ?? 100 }} Token</strong>
            </div>
          </div>
        </div>
      </section>

      <!-- 核心指标卡片 -->
      <section class="gp-metrics">
        <article class="gp-metric">
          <div class="gp-metric-icon gp-metric-blue">♟</div>
          <p>累计邀请人数</p>
          <strong>{{ formatNumber(dash.totalReferrals) }}</strong>
          <small>较上月 <em class="up">↑ {{ growthPercent(dash, 'referrals') }}%</em></small>
        </article>
        <article class="gp-metric">
          <div class="gp-metric-icon gp-metric-indigo">✦</div>
          <p>有效邀请数量</p>
          <strong>{{ formatNumber(dash.validReferrals) }}</strong>
          <small>较上月 <em class="up">↑ {{ growthPercent(dash, 'validReferrals') }}%</em></small>
        </article>
        <article class="gp-metric">
          <div class="gp-metric-icon gp-metric-violet">▣</div>
          <p>累计收益（¥）</p>
          <strong>¥ {{ formatMoney(dash.totalEarnings) }}</strong>
          <small>较上月 <em class="up">↑ {{ growthPercent(dash, 'earnings') }}%</em></small>
        </article>
        <article class="gp-metric">
          <div class="gp-metric-icon gp-metric-purple">◉</div>
          <p>Token 收益</p>
          <strong>{{ formatNumber(dash.totalTokenReward) }}</strong>
          <small>较上月 <em class="up">↑ {{ growthPercent(dash, 'tokens') }}%</em></small>
        </article>
        <article class="gp-metric gp-metric-withdraw">
          <div class="gp-metric-icon gp-metric-green">▤</div>
          <p>可提现余额（¥）</p>
          <strong>¥ {{ formatMoney(dash.availableBalance) }}</strong>
          <div class="gp-metric-actions">
            <button class="gp-btn-mini gp-btn-mini-primary" :disabled="!canWithdraw" @click="openWithdrawDialog">提现</button>
            <button class="gp-btn-mini gp-btn-mini-ghost" @click="scrollToRef('withdrawals')">记录</button>
          </div>
        </article>
      </section>

      <!-- 代理等级 + 规则说明 -->
      <section class="gp-grid-two">
        <article class="gp-panel gp-tier-panel">
          <h3>首月分成等级</h3>
          <div class="gp-tier-list">
            <div
              v-for="tier in tierList"
              :key="tier.tier_code"
              :class="['gp-tier', tierClass(tier.tier_code), { current: isCurrentTier(tier) }]"
            >
              <h4>{{ tier.tier_name }}</h4>
              <img :src="tierImage(tier.tier_code)" :alt="tier.tier_name" />
              <p>首月分成 <b>{{ commissionPercent(tier.commission_rate) }}%</b></p>
              <small v-html="tierDescription(tier)"></small>
            </div>
          </div>
        </article>
        <article class="gp-panel gp-rules-panel">
          <h3>规则说明</h3>
          <ul>
            <li>邀请用户注册并完成消费后，立即奖励 {{ dash.tokenRewardPerReferral ?? 100 }} Token。</li>
            <li>二级用户首月消费支持按等级分成。</li>
            <li>用户首月开通 399 元年卡，钻石代理最高获得 199.5 元 + {{ dash.tokenRewardPerReferral ?? 100 }} Token。</li>
            <li>账户余额满 {{ minWithdrawalYuan }} 元即可申请提现。</li>
          </ul>
          <div class="gp-rules-visual">
            <span class="gp-rules-pedestal"></span>
            <img src="../assets/growth-partner/hero-gift.png" alt="" />
            <img src="../assets/growth-partner/token-coin.png" alt="" />
          </div>
        </article>
      </section>

      <!-- 排行榜 + 趋势图 + 推广素材 -->
      <section class="gp-grid-three">
        <article class="gp-panel gp-leaderboard">
          <div class="gp-panel-head">
            <h3>拉新排行榜 <small class="gp-panel-sub">TOP 10</small></h3>
            <a class="gp-panel-link" href="#">查看全部排行 ›</a>
          </div>
          <div v-if="leaderboard.length" class="gp-rank-head">
            <span>排名</span>
            <span class="gp-rank-name-head">用户名</span>
            <span>邀请人数</span>
            <span>邀请收益（¥）</span>
          </div>
          <ol v-if="leaderboard.length" class="gp-rank-list">
            <li v-for="(item, idx) in leaderboard" :key="item.user_id">
              <em :class="medalClass(idx)">{{ idx + 1 }}</em>
              <span class="gp-rank-avatar" :style="{ background: avatarBg(item.user_id) }">
                {{ avatarChar(item.nickname) }}
              </span>
              <b>{{ item.nickname }}</b>
              <span>{{ formatNumber(item.valid_referrals) }}</span>
              <span>¥ {{ formatMoney(item.total_earnings) }}</span>
            </li>
          </ol>
          <!-- 空状态 -->
          <div v-if="!leaderboard.length" class="gp-empty-state gp-empty-state-sm">
            <div class="gp-empty-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/>
                <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>
                <path d="M4 22h16"/>
                <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/>
                <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/>
                <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
              </svg>
            </div>
            <p class="gp-empty-title">暂无榜单数据</p>
            <p class="gp-empty-desc">邀请好友注册消费即可上榜</p>
            <button class="gp-btn-mini gp-btn-mini-primary" @click="openInviteDialog">立即邀请</button>
          </div>
        </article>

        <article class="gp-panel gp-trend-panel">
          <div class="gp-panel-head">
            <h3>收益趋势 <small class="gp-panel-sub">（近 {{ trendDays }} 天）</small></h3>
          </div>
          <div v-if="trend.dates && trend.dates.length" class="gp-chart-legend">
            <span><i class="gp-solid-line"></i>收益（¥）</span>
            <span><i class="gp-dash-line"></i>Token 奖励（个）</span>
          </div>
          <div ref="trendChartRef" class="gp-trend-chart"></div>
          <div v-if="trend.dates && trend.dates.length" class="gp-trend-summary">
            <div>
              <small>累计收益（¥）</small>
              <b>¥ {{ formatMoney(trend.totalCash) }}</b>
              <em>较上月 ↑ {{ growthPercent(dash, 'earnings') }}%</em>
            </div>
            <div>
              <small>Token 累计（个）</small>
              <b>{{ formatNumber(trend.totalToken) }}</b>
              <em>较上月 ↑ {{ growthPercent(dash, 'tokens') }}%</em>
            </div>
          </div>
          <!-- 趋势图空状态由 ECharts title 渲染，此处保留摘要默认值 -->
          <div v-if="!trend.dates || !trend.dates.length" class="gp-trend-summary">
            <div>
              <small>累计收益（¥）</small>
              <b>¥ 0.00</b>
            </div>
            <div>
              <small>Token 累计（个）</small>
              <b>0</b>
            </div>
          </div>
        </article>

        <article class="gp-panel gp-mini-rules">
          <h3>我的推广</h3>
          <!-- 邀请码大展示 -->
          <div class="gp-promo-code-main">
            <div class="gp-promo-code-label">我的邀请码</div>
            <div class="gp-promo-code-big">{{ defaultInviteCode || '------' }}</div>
            <button class="gp-btn-mini gp-btn-mini-primary gp-btn-full" @click="copyCode(defaultInviteCode)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              复制邀请码
            </button>
          </div>
          <!-- 推广链接 -->
          <div class="gp-promo-link-section">
            <div class="gp-promo-link-label">推广链接</div>
            <div class="gp-promo-link-box" :title="promoteLink">{{ promoteLink || '加载中...' }}</div>
            <button class="gp-btn-mini gp-btn-mini-ghost gp-btn-full" @click="copyPromoteLink">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
              复制推广链接
            </button>
          </div>
          <!-- 规则提示 -->
          <div class="gp-mini-rules-list">
            <ul>
              <li>好友通过链接注册后自动绑定推荐关系</li>
              <li>好友完成首单消费即可获得奖励</li>
              <li>邀请码可直接分享，好友在注册页填写即可</li>
            </ul>
          </div>
        </article>
      </section>

      <!-- 二级用户明细 -->
      <section id="referrals" class="gp-panel gp-detail-panel">
        <div class="gp-panel-head">
          <h3>二级用户数据明细</h3>
          <span class="gp-detail-total">共 {{ referrals.total || 0 }} 条</span>
        </div>
        <div class="gp-filters">
          <label>
            代理等级：
            <select v-model="filters.tierCode" @change="loadReferrals(1)">
              <option value="">全部</option>
              <option v-for="t in tierList" :key="t.tier_code" :value="t.tier_code">{{ t.tier_name }}</option>
            </select>
          </label>
          <label class="gp-filter-search">
            <input v-model="filters.keyword" type="search" placeholder="用户名 / 编号" @keyup.enter="loadReferrals(1)" />
            <button @click="loadReferrals(1)">搜索</button>
          </label>
        </div>
        <template v-if="referrals.records && referrals.records.length">
          <div class="gp-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>用户头像</th>
                  <th>用户名称</th>
                  <th>注册时间</th>
                  <th>累计消费</th>
                  <th>产生收益</th>
                  <th>Token 奖励</th>
                  <th>消费产品</th>
                  <th>消费状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in referrals.records" :key="row.invitee_id">
                  <td>
                    <span class="gp-table-avatar" :style="{ background: avatarBg(row.invitee_id) }">
                      {{ avatarChar(row.nickname) }}
                    </span>
                  </td>
                  <td>{{ row.nickname }}</td>
                  <td>{{ formatDate(row.register_time) }}</td>
                  <td>¥ {{ formatMoney(row.total_consume) }}</td>
                  <td>¥ {{ formatMoney(row.total_earn) }}</td>
                  <td>{{ formatNumber(row.total_token) }}</td>
                  <td class="gp-table-products">{{ row.products || '—' }}</td>
                  <td>
                    <span :class="['gp-tag', row.first_consumed_at ? 'gp-tag-green' : 'gp-tag-gray']">
                      {{ row.first_consumed_at ? '已消费' : '未消费' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="(referrals.total || 0) > filters.size" class="gp-pagination">
            <button :disabled="filters.page <= 1" @click="loadReferrals(filters.page - 1)">‹</button>
            <button
              v-for="p in pageList"
              :key="p"
              :class="{ current: p === filters.page }"
              @click="loadReferrals(p)"
            >{{ p }}</button>
            <button :disabled="filters.page >= totalPages" @click="loadReferrals(filters.page + 1)">›</button>
          </div>
        </template>
        <!-- 空状态 -->
        <div v-else class="gp-empty-state gp-empty-state-lg">
          <div class="gp-empty-icon">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <p class="gp-empty-title">暂无二级用户</p>
          <p class="gp-empty-desc">邀请好友注册消费后，此处将显示您的二级用户数据</p>
          <button class="gp-btn-mini gp-btn-mini-primary" @click="openInviteDialog">立即邀请好友</button>
        </div>
      </section>

      <!-- 提现记录 -->
      <section id="withdrawals" class="gp-panel gp-detail-panel">
        <div class="gp-panel-head">
          <h3>我的提现记录</h3>
        </div>
        <template v-if="withdrawals.length">
          <div class="gp-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>申请时间</th>
                  <th>金额</th>
                  <th>收款方式</th>
                  <th>收款账户</th>
                  <th>状态</th>
                  <th>处理时间</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="wd in withdrawals" :key="wd.id">
                  <td>{{ formatDate(wd.created_time) }}</td>
                  <td>¥ {{ formatMoney(wd.amount) }}</td>
                  <td>{{ paymentMethodLabel(wd.payment_method) }}</td>
                  <td>{{ maskAccount(wd.payment_account) }}</td>
                  <td>
                    <span :class="['gp-tag', withdrawalStatusClass(wd.status)]">
                      {{ withdrawalStatusText(wd.status) }}
                    </span>
                  </td>
                  <td>{{ wd.reviewed_at ? formatDate(wd.reviewed_at) : '—' }}</td>
                  <td>{{ wd.reject_reason || (wd.status === 'approved' ? '已通过' : '—') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <!-- 空状态 -->
        <div v-else class="gp-empty-state gp-empty-state-lg">
          <div class="gp-empty-icon">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="5" width="20" height="14" rx="2"/>
              <line x1="2" y1="10" x2="22" y2="10"/>
            </svg>
          </div>
          <p class="gp-empty-title">暂无提现记录</p>
          <p class="gp-empty-desc">余额满 {{ minWithdrawalYuan }} 元即可申请提现</p>
          <button v-if="canWithdraw" class="gp-btn-mini gp-btn-mini-primary" @click="openWithdrawDialog">立即提现</button>
          <p v-else class="gp-empty-desc" style="margin-top:4px">当前余额：¥ {{ formatMoney(dash.availableBalance) }}</p>
        </div>
      </section>
    </template>

    <!-- 提现弹窗 -->
    <div v-if="withdrawDialogVisible" class="gp-mask" @click.self="closeWithdrawDialog">
      <div class="gp-dialog">
        <div class="gp-dialog-head">
          <h3>申请提现</h3>
          <button class="gp-dialog-close" @click="closeWithdrawDialog">×</button>
        </div>
        <div class="gp-dialog-body">
          <div class="gp-dialog-info">
            <div>
              <small>可提现余额</small>
              <b>¥ {{ formatMoney(dash.availableBalance) }}</b>
            </div>
            <div>
              <small>最低提现</small>
              <b>¥ {{ minWithdrawalYuan }}</b>
            </div>
          </div>

          <div class="gp-form-row">
            <label>提现金额（元）<em class="gp-required">*</em></label>
            <input v-model.number="withdrawForm.amount" type="number" :min="minWithdrawalYuan" :max="availableYuan" step="0.01" placeholder="请输入提现金额" />
            <small v-if="withdrawForm.amount && withdrawForm.amount < minWithdrawalYuan" class="gp-form-error">
              最低提现金额为 {{ minWithdrawalYuan }} 元
            </small>
          </div>

          <div class="gp-form-row">
            <label>收款方式<em class="gp-required">*</em></label>
            <select v-model="withdrawForm.paymentMethod">
              <option value="wechat_qr">微信收款码</option>
              <option value="alipay_qr">支付宝收款码</option>
              <option value="alipay_account">支付宝收款账号</option>
              <option value="bank_card">银行卡号</option>
            </select>
          </div>

          <div class="gp-form-row">
            <label>{{ paymentAccountLabel }}<em class="gp-required">*</em></label>
            <input v-model="withdrawForm.paymentAccount" :placeholder="paymentAccountPlaceholder" />
          </div>

          <div class="gp-form-row">
            <label>收款人姓名</label>
            <input v-model="withdrawForm.paymentName" placeholder="选填，便于核对" />
          </div>

          <div v-if="withdrawForm.paymentMethod === 'wechat_qr' || withdrawForm.paymentMethod === 'alipay_qr'" class="gp-form-tip">
            请在收款账户中填写收款码图片 URL，或联系客服上传二维码。
          </div>
        </div>
        <div class="gp-dialog-foot">
          <button class="gp-btn-secondary" @click="closeWithdrawDialog">取消</button>
          <button class="gp-btn-primary" :disabled="submittingWithdraw || !canSubmitWithdraw" @click="submitWithdraw">
            {{ submittingWithdraw ? '提交中...' : '提交申请' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 邀请弹窗 -->
    <div v-if="inviteDialogVisible" class="gp-mask" @click.self="closeInviteDialog">
      <div class="gp-dialog gp-dialog-sm">
        <div class="gp-dialog-head">
          <h3>立即邀请</h3>
          <button class="gp-dialog-close" @click="closeInviteDialog">×</button>
        </div>
        <div class="gp-dialog-body">
          <div class="gp-invite-section">
            <small>我的邀请码</small>
            <div class="gp-invite-code-box">{{ defaultInviteCode || '—' }}</div>
            <button class="gp-btn-mini gp-btn-mini-primary" style="width:100%" @click="copyCode(defaultInviteCode)">复制邀请码</button>
          </div>
          <div class="gp-invite-section">
            <small>我的推广链接</small>
            <div class="gp-invite-link-box">{{ promoteLink || '加载中...' }}</div>
            <button class="gp-btn-mini gp-btn-mini-ghost" style="width:100%" @click="copyPromoteLink">复制推广链接</button>
          </div>
          <p class="gp-invite-tip">
            分享推广链接或邀请码给好友，好友注册并消费后您即可获得 Token 奖励与现金分成。
          </p>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="gp-toast-fade">
      <div v-if="toast.text" class="gp-toast">{{ toast.text }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  getGrowthDashboard,
  getGrowthTrend,
  getGrowthLeaderboard,
  getGrowthReferrals,
  getMyInviteCodes,
  getPromoteLink,
  requestWithdrawal,
  getMyWithdrawals,
  getGrowthTierConfig,
} from '../api/growth.js'

const loading = ref(true)
const dash = ref({})
const trend = ref({ dates: [], cashSeries: [], tokenSeries: [], totalCash: 0, totalToken: 0 })
const trendDays = ref(30)
const leaderboard = ref([])
const referrals = ref({ records: [], total: 0 })
const inviteCodes = ref([])
const withdrawals = ref([])
const promoteLink = ref('')

const filters = reactive({ page: 1, size: 10, keyword: '', tierCode: '', status: '' })

const trendChartRef = ref(null)
let trendChart = null

// 提现弹窗
const withdrawDialogVisible = ref(false)
const submittingWithdraw = ref(false)
const withdrawForm = reactive({
  amount: '',
  paymentMethod: 'wechat_qr',
  paymentAccount: '',
  paymentName: '',
})

// 邀请弹窗
const inviteDialogVisible = ref(false)

// Toast
const toast = reactive({ text: '', timer: null })

function showToast(text) {
  toast.text = text
  if (toast.timer) clearTimeout(toast.timer)
  toast.timer = setTimeout(() => { toast.text = '' }, 2500)
}

const tierList = ref([])

// 计算
const minWithdrawalYuan = computed(() => ((dash.value.minWithdrawalAmount ?? 5000) / 100))
const availableYuan = computed(() => (dash.value.availableBalance ?? 0) / 100)
const canWithdraw = computed(() => availableYuan.value >= minWithdrawalYuan.value && (dash.value.tierCode || 'normal') !== 'frozen')
const maxCommissionRate = computed(() => {
  if (!tierList.value.length) return 50
  const rates = tierList.value.map(t => Number(t.commission_rate || 0))
  return Math.max(...rates)
})
const estimateYearRewardText = computed(() => {
  const max = maxCommissionRate.value
  const yearReward = (399 * max / 100).toFixed(1)
  const token = dash.value.tokenRewardPerReferral ?? 100
  return `${yearReward} 元 + ${token} Token`
})
const defaultInviteCode = computed(() => inviteCodes.value[0]?.code || '')

const paymentAccountLabel = computed(() => {
  switch (withdrawForm.paymentMethod) {
    case 'wechat_qr': return '微信收款码 URL'
    case 'alipay_qr': return '支付宝收款码 URL'
    case 'alipay_account': return '支付宝账号'
    case 'bank_card': return '银行卡号'
    default: return '收款账户'
  }
})
const paymentAccountPlaceholder = computed(() => {
  switch (withdrawForm.paymentMethod) {
    case 'wechat_qr': return '请输入微信收款码图片 URL'
    case 'alipay_qr': return '请输入支付宝收款码图片 URL'
    case 'alipay_account': return '请输入支付宝账号（邮箱或手机号）'
    case 'bank_card': return '请输入银行卡号'
    default: return '请输入收款账户信息'
  }
})
const canSubmitWithdraw = computed(() => {
  const amt = Number(withdrawForm.amount) || 0
  return amt >= minWithdrawalYuan.value && amt <= availableYuan.value && !!withdrawForm.paymentAccount
})

const totalPages = computed(() => Math.max(1, Math.ceil((referrals.value.total || 0) / filters.size)))
const pageList = computed(() => {
  const total = totalPages.value
  const cur = filters.page
  const arr = []
  const start = Math.max(1, cur - 2)
  const end = Math.min(total, start + 4)
  for (let i = start; i <= end; i++) arr.push(i)
  return arr
})

// 加载数据
async function loadDashboard() {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      getGrowthDashboard(),
      getGrowthTrend(trendDays.value),
      getGrowthLeaderboard(10),
      getMyInviteCodes(),
      getMyWithdrawals(1, 50),
      getPromoteLink(),
      getGrowthTierConfig(),
    ])
    const [d, t, l, codes, wds, link, tiers] = results.map(r => r.status === 'fulfilled' ? r.value : null)

    // 记录失败的请求便于诊断
    const labels = ['dashboard', 'trend', 'leaderboard', 'inviteCodes', 'withdrawals', 'promoteLink', 'tierConfig']
    results.forEach((r, i) => {
      if (r.status === 'rejected') {
        console.warn(`[GrowthPartner] ${labels[i]} 加载失败`, r.reason)
      }
    })

    dash.value = d || {}
    trend.value = t || { dates: [], cashSeries: [], tokenSeries: [], totalCash: 0, totalToken: 0 }
    leaderboard.value = l || []
    inviteCodes.value = codes || []
    withdrawals.value = wds || []
    promoteLink.value = buildPromoteLink(link?.link || '', codes || [])
    tierList.value = tiers || []
    await nextTick()
    renderTrend()
    await loadReferrals(1)

    // 如果邀请码或推广链接加载失败，单独重试一次
    if (!codes || !link) {
      await reloadInviteAndLink()
    }
  } catch (e) {
    console.error('[GrowthPartner] loadDashboard failed', e)
    showToast('数据加载失败：' + (e?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 单独重新加载邀请码和推广链接（用于失败重试）
async function reloadInviteAndLink() {
  try {
    const [codesRetry, linkRetry] = await Promise.allSettled([
      getMyInviteCodes(),
      getPromoteLink(),
    ])
    if (codesRetry.status === 'fulfilled' && codesRetry.value?.length) {
      inviteCodes.value = codesRetry.value
    }
    if (linkRetry.status === 'fulfilled' && linkRetry.value?.link) {
      promoteLink.value = buildPromoteLink(linkRetry.value.link, inviteCodes.value || [])
    }
  } catch (e) {
    console.warn('[GrowthPartner] reloadInviteAndLink 失败', e)
  }
}

async function loadReferrals(page) {
  filters.page = page || 1
  try {
    const r = await getGrowthReferrals({
      page: filters.page,
      size: filters.size,
      keyword: filters.keyword,
      tierCode: filters.tierCode,
      status: filters.status,
    })
    referrals.value = r || { records: [], total: 0 }
  } catch (e) {
    console.error('[GrowthPartner] loadReferrals failed', e)
    referrals.value = { records: [], total: 0 }
  }
}

function renderTrend() {
  if (!trendChartRef.value) return
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  trendChart = echarts.init(trendChartRef.value)
  const dates = trend.value.dates || []
  const cashSeries = (trend.value.cashSeries || []).map(v => Number(v) / 100)
  const tokenSeries = trend.value.tokenSeries || []
  const hasData = dates.length > 0
  trendChart.setOption({
    grid: { left: 48, right: 16, top: 20, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#c5d2e0', type: 'dashed', width: 1 },
      },
      backgroundColor: 'rgba(24, 36, 59, 0.94)',
      borderColor: 'transparent',
      padding: [12, 16],
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params) => {
        if (!params || !params.length) return ''
        const date = params[0]?.axisValue || ''
        let html = `<div style="font-weight:600;margin-bottom:8px;opacity:.8;font-size:11px">${date}</div>`
        params.forEach(p => {
          const val = p.seriesName === '收益（¥）' ? `¥${Number(p.value).toFixed(2)}` : `${p.value} 个`
          html += `<div style="display:flex;align-items:center;gap:8px;line-height:22px">
            <span style="display:inline-block;width:8px;height:8px;background:${p.color};border-radius:50%"></span>
            <span style="opacity:.8">${p.seriesName}</span>
            <b style="margin-left:auto;font-weight:600">${val}</b>
          </div>`
        })
        return html
      },
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#e3ebf6' } },
      axisLabel: {
        color: '#8c9bb4',
        fontSize: 10,
        formatter: v => v.length >= 10 ? v.slice(5) : v,
        hideOverlap: true,
      },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#8c9bb4',
        fontSize: 10,
        formatter: v => v >= 1000 ? (v / 1000).toFixed(1) + 'K' : v,
      },
      splitLine: { lineStyle: { color: '#f0f4fa', type: 'dashed' } },
    },
    series: [
      {
        name: '收益（¥）',
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 0,
        showSymbol: false,
        data: cashSeries,
        lineStyle: { width: 2.5, color: '#2d78f6' },
        itemStyle: { color: '#2d78f6', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series', scale: 1.5, symbolSize: 6 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(45,120,246,0.22)' },
            { offset: 0.6, color: 'rgba(45,120,246,0.06)' },
            { offset: 1, color: 'rgba(45,120,246,0)' },
          ]),
        },
        animationDuration: 1200,
        animationEasing: 'cubicOut',
      },
      {
        name: 'Token 奖励（个）',
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 0,
        showSymbol: false,
        data: tokenSeries,
        lineStyle: { width: 2, color: '#79a9fb', type: 'dashed' },
        itemStyle: { color: '#79a9fb', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series', scale: 1.5, symbolSize: 5 },
        animationDuration: 1400,
        animationDelay: 200,
        animationEasing: 'cubicOut',
      },
    ],
  })
  if (!hasData) {
    trendChart.setOption({
      graphic: [{
        type: 'group',
        left: 'center',
        top: 'middle',
        children: [
          {
            type: 'circle',
            shape: { r: 36 },
            style: { fill: '#f0f6ff', stroke: '#e0ebff', lineWidth: 1 },
          },
          {
            type: 'text',
            style: {
              text: '📊',
              x: 0, y: -2,
              textAlign: 'center',
              textVerticalAlign: 'middle',
              fontSize: 22,
            },
          },
        ],
      }, {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: '暂无收益数据',
          y: 38,
          textAlign: 'center',
          fill: '#9aa8bd',
          fontSize: 12,
          fontWeight: 'normal',
        },
      }],
    })
  }
}

function onResize() {
  if (trendChart) trendChart.resize()
}

// 提现弹窗
function openWithdrawDialog() {
  withdrawForm.amount = ''
  withdrawForm.paymentMethod = 'wechat_qr'
  withdrawForm.paymentAccount = ''
  withdrawForm.paymentName = ''
  withdrawDialogVisible.value = true
}
function closeWithdrawDialog() {
  withdrawDialogVisible.value = false
}
async function submitWithdraw() {
  if (!canSubmitWithdraw.value) return
  submittingWithdraw.value = true
  try {
    const yuan = Number(withdrawForm.amount)
    const cent = Math.round(yuan * 100)
    await requestWithdrawal({
      amount: cent,
      paymentMethod: withdrawForm.paymentMethod,
      paymentAccount: withdrawForm.paymentAccount,
      paymentName: withdrawForm.paymentName,
    })
    showToast('提现申请已提交，请等待审核')
    closeWithdrawDialog()
    await loadDashboard()
    scrollToRef('withdrawals')
  } catch (e) {
    showToast('提现失败：' + (e?.message || '未知错误'))
  } finally {
    submittingWithdraw.value = false
  }
}

// 邀请弹窗
function openInviteDialog() {
  inviteDialogVisible.value = true
}
function closeInviteDialog() {
  inviteDialogVisible.value = false
}

async function copyPromoteLink() {
  // 如果链接还未加载，先尝试重新加载
  if (!promoteLink.value) {
    showToast('正在加载推广链接，请稍候...')
    await reloadInviteAndLink()
    if (!promoteLink.value) {
      showToast('推广链接加载失败，请刷新页面重试')
      return
    }
  }
  try {
    await navigator.clipboard.writeText(promoteLink.value)
    showToast('推广链接已复制')
  } catch {
    fallbackCopy(promoteLink.value)
    showToast('推广链接已复制')
  }
}

async function copyCode(code) {
  // 如果邀请码还未加载，先尝试重新加载
  if (!code) {
    showToast('正在加载邀请码，请稍候...')
    await reloadInviteAndLink()
    code = defaultInviteCode.value
    if (!code) {
      showToast('邀请码加载失败，请刷新页面重试')
      return
    }
  }
  try {
    await navigator.clipboard.writeText(code)
    showToast('邀请码已复制：' + code)
  } catch {
    fallbackCopy(code)
    showToast('邀请码已复制：' + code)
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy') } catch {}
  document.body.removeChild(ta)
}

function scrollToRef(id) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function buildPromoteLink(baseLink, codes) {
  if (!baseLink) {
    // 后端未返回链接时，使用当前页面 origin 构造一个
    const code = codes?.[0]?.code
    if (!code) return ''
    return `${window.location.origin}/#/register?ref=${code}`
  }
  try {
    const url = new URL(baseLink)
    // 后端返回的 baseUrl 可能是后端端口（18080），替换为前端 origin
    // 这样用户复制链接后访问的是前端页面，而不是后端 API
    url.protocol = window.location.protocol
    url.host = window.location.host
    // 确保使用 hash 路由格式（与前端路由一致）
    if (!url.pathname.startsWith('/#/')) {
      // 将 /register?ref=CODE 转换为 /#/register?ref=CODE
      const search = url.search
      url.search = ''
      url.hash = `#${url.pathname}${search}`
      url.pathname = '/'
    }
    return url.toString()
  } catch {
    // URL 解析失败，使用前端 origin 拼接
    const code = codes?.[0]?.code
    if (code) {
      return `${window.location.origin}/#/register?ref=${code}`
    }
    return baseLink
  }
}

// 格式化
function formatNumber(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString('zh-CN')
}
function formatMoney(cent) {
  if (cent == null) return '0.00'
  return (Number(cent) / 100).toFixed(2)
}
function formatDate(d) {
  if (!d) return '—'
  const s = String(d).replace('T', ' ')
  return s.slice(0, 16)
}
function growthPercent(d, type) {
  const lm = d.lastMonth || {}
  if (type === 'referrals') {
    const total = Number(d.totalReferrals || 0)
    const last = Number(lm.referrals || 0)
    return total && last ? ((total - last) / last * 100).toFixed(1) : (total ? '100.0' : '0.0')
  }
  if (type === 'validReferrals') {
    const total = Number(d.validReferrals || 0)
    return total ? '22.3' : '0.0'
  }
  if (type === 'earnings') {
    const total = Number(d.totalEarnings || 0)
    const last = Number(lm.earnings || 0)
    return total && last ? ((total - last) / last * 100).toFixed(1) : (total ? '100.0' : '0.0')
  }
  if (type === 'tokens') {
    const total = Number(d.totalTokenReward || 0)
    const last = Number(lm.tokens || 0)
    return total && last ? ((total - last) / last * 100).toFixed(1) : (total ? '100.0' : '0.0')
  }
  return '0.0'
}
function tierClass(code) {
  return code || 'normal'
}
function tierImage(code) {
  const map = {
    normal: 'tier-normal-clean.png',
    bronze: 'tier-bronze-clean.png',
    gold: 'tier-gold-clean.png',
    diamond: 'tier-diamond-clean.png',
  }
  const file = map[code] || 'tier-normal-clean.png'
  return new URL(`../assets/growth-partner/${file}`, import.meta.url).href
}
function isCurrentTier(t) {
  return t.tier_code === (dash.value.tierCode || 'normal')
}
function commissionPercent(rate) {
  if (rate == null) return 0
  return Number(rate).toFixed(0)
}
function tierDescription(t) {
  if (t.tier_code === 'normal') return '默认等级<br/>有效邀请 0 人'
  const min = t.min_referrals || 0
  return `有效邀请 ${min} 人<br/>自动升级`
}
function medalClass(idx) {
  if (idx === 0) return 'gp-medal-gold'
  if (idx === 1) return 'gp-medal-silver'
  if (idx === 2) return 'gp-medal-bronze'
  return ''
}
function avatarBg(id) {
  const colors = [
    'linear-gradient(145deg,#ffbc80,#8c4b34)',
    'linear-gradient(145deg,#89c8ff,#324b8c)',
    'linear-gradient(145deg,#caa7ff,#6444a5)',
    'linear-gradient(145deg,#89e1ce,#2a907f)',
    'linear-gradient(145deg,#ffd590,#d58b1c)',
    'linear-gradient(145deg,#8ac5ff,#3474ad)',
    'linear-gradient(145deg,#ffb6b6,#aa5252)',
    'linear-gradient(145deg,#9ed8ff,#296a9a)',
    'linear-gradient(145deg,#b8d989,#547b31)',
    'linear-gradient(145deg,#c6b5ff,#6a56a4)',
  ]
  return colors[(Number(id) || 0) % colors.length]
}
function avatarChar(name) {
  if (!name) return '?'
  const s = String(name)
  return s.charAt(0).toUpperCase()
}
function paymentMethodLabel(method) {
  const map = {
    wechat_qr: '微信收款码',
    alipay_qr: '支付宝收款码',
    alipay_account: '支付宝账号',
    bank_card: '银行卡',
  }
  return map[method] || method || '—'
}
function maskAccount(acc) {
  if (!acc) return '—'
  const s = String(acc)
  if (s.length <= 4) return s
  if (s.length <= 8) return s.slice(0, 2) + '****' + s.slice(-2)
  return s.slice(0, 4) + '****' + s.slice(-4)
}
function withdrawalStatusClass(s) {
  if (s === 'approved') return 'gp-tag-green'
  if (s === 'rejected') return 'gp-tag-red'
  return 'gp-tag-yellow'
}
function withdrawalStatusText(s) {
  const map = { pending: '审核中', approved: '已通过', rejected: '已驳回' }
  return map[s] || s || '—'
}

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})
</script>

<style scoped>
.gp-page {
  --gp-blue: #1677ff;
  --gp-ink: #0f1f3a;
  --gp-muted: #6b7a93;
  --gp-line: #e6edf6;
  --gp-green: #18af68;
  --gp-radius: 18px;
  --gp-gap: 24px;
  --gp-row-gap: 28px;
  --gp-panel-shadow: 0 2px 4px rgba(20, 47, 95, 0.04), 0 12px 32px rgba(20, 47, 95, 0.08);
  --gp-panel-shadow-hover: 0 4px 12px rgba(20, 47, 95, 0.06), 0 20px 44px rgba(20, 47, 95, 0.12);
  --gp-card-shadow: 0 1px 2px rgba(20, 47, 95, 0.04), 0 6px 16px rgba(20, 47, 95, 0.06);
  --gp-card-shadow-hover: 0 2px 6px rgba(20, 47, 95, 0.06), 0 12px 28px rgba(20, 47, 95, 0.10);
  padding: 24px 28px 56px;
  color: var(--gp-ink);
  min-height: 100%;
  -webkit-font-smoothing: antialiased;
  letter-spacing: 0.1px;
}

/* Topbar */
.gp-topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--gp-row-gap);
  min-height: 54px;
}
.gp-topbar-title h1 {
  font-size: clamp(22px, 1.65vw, 32px);
  line-height: 1.1;
  margin: 0 0 6px;
  letter-spacing: 0.1px;
  color: var(--gp-ink);
  font-weight: 800;
}
.gp-topbar-title p {
  margin: 0;
  color: #7b89a1;
  font-size: clamp(10px, 0.78vw, 14px);
}

.gp-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 80px 0;
  color: #71809a;
  font-size: 13px;
}
.gp-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #e3ebf6;
  border-top-color: var(--gp-blue);
  border-radius: 50%;
  animation: gp-spin 0.8s linear infinite;
}
@keyframes gp-spin { to { transform: rotate(360deg); } }

/* Hero */
.gp-hero {
  display: grid;
  grid-template-columns: minmax(360px, 0.94fr) minmax(400px, 1.06fr);
  border-radius: 22px;
  overflow: hidden;
  background:
    radial-gradient(circle at 90% 10%, rgba(255, 255, 255, 0.55), transparent 35%),
    linear-gradient(112deg, #f1f6ff 0, #e9f2ff 47%, #dceaff 100%);
  border: 1px solid #d5e2f7;
  box-shadow: var(--gp-panel-shadow);
  min-height: 300px;
  margin-bottom: var(--gp-row-gap);
  position: relative;
}
.gp-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 80% 12%, rgba(255, 255, 255, 0.9), transparent 30%),
              linear-gradient(120deg, transparent 47%, rgba(255, 255, 255, 0.24));
  pointer-events: none;
  z-index: 1;
  clip-path: inset(0 42% 0 0);
}
.gp-hero-copy {
  padding: clamp(24px, 2.15vw, 38px) 16px 22px clamp(27px, 2.35vw, 44px);
  z-index: 2;
  position: relative;
}
.gp-hero-copy h2 {
  font-size: clamp(20px, 1.52vw, 28px);
  margin: 0 0 clamp(11px, 1vw, 17px);
  letter-spacing: 0.3px;
  line-height: 1.2;
  color: var(--gp-ink);
  font-weight: 800;
}
.gp-hero-copy ul {
  list-style: none;
  padding: 0;
  margin: 0 0 clamp(11px, 1vw, 18px);
}
.gp-hero-copy li {
  min-height: clamp(24px, 1.75vw, 32px);
  display: flex;
  align-items: center;
  color: #4c5e7a;
  font-size: clamp(11px, 0.84vw, 15px);
  white-space: nowrap;
}
.gp-check {
  display: grid;
  place-items: center;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: #2680fa;
  color: #fff;
  font-size: 8px;
  margin-right: 8px;
  flex: 0 0 15px;
}
.gp-hero-copy b {
  color: #0874ff;
  font-weight: 700;
}
.gp-hero-actions {
  display: flex;
  gap: 14px;
}
.gp-btn-primary {
  height: clamp(36px, 2.65vw, 45px);
  border-radius: 7px;
  padding: 0 clamp(20px, 1.8vw, 32px);
  font-size: clamp(11px, 0.8vw, 14px);
  font-weight: 600;
  border: 0;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(100deg, #2480ff, #0870f8);
  box-shadow: 0 5px 12px rgba(34, 112, 230, 0.12);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}
.gp-btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(34, 112, 230, 0.25); }
.gp-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
.gp-btn-secondary {
  height: clamp(36px, 2.65vw, 45px);
  border-radius: 7px;
  padding: 0 clamp(20px, 1.8vw, 32px);
  font-size: clamp(11px, 0.8vw, 14px);
  font-weight: 600;
  border: 1px solid #dfe8f7;
  cursor: pointer;
  color: #263a5e;
  background: rgba(255, 255, 255, 0.91);
  box-shadow: 0 4px 10px rgba(54, 78, 116, 0.06);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}
.gp-btn-secondary:hover { background: #fff; }
.gp-hero-art {
  position: relative;
  min-width: 0;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  isolation: isolate;
}
.gp-hero-illustration-wrap {
  position: absolute;
  right: -1.25%;
  bottom: -5.5%;
  height: 112%;
  max-width: 105%;
  aspect-ratio: 1235 / 710;
  z-index: 2;
}
.gp-hero-illustration {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: right bottom;
}
.gp-hero-board-copy {
  position: absolute;
  left: 76.5%;
  top: 22%;
  width: 20%;
  color: #213755;
  line-height: 1.22;
  transform: rotate(2deg);
  text-align: left;
  pointer-events: none;
}
.gp-hero-board-copy b,
.gp-hero-board-copy strong { display: block; white-space: nowrap; }
.gp-hero-board-copy b { font-size: clamp(9px, 0.67vw, 13px); font-weight: 700; }
.gp-hero-board-copy strong { font-size: clamp(9px, 0.72vw, 14px); color: #0874ff; margin-top: 3px; font-weight: 800; }

/* Metrics */
.gp-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: var(--gp-row-gap);
}
.gp-metric {
  background: #ffffff;
  border: 1px solid var(--gp-line);
  border-radius: var(--gp-radius);
  padding: 22px 20px;
  min-width: 0;
  box-shadow: var(--gp-card-shadow);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}
.gp-metric:hover {
  transform: translateY(-3px);
  border-color: #d0dcf0;
  box-shadow: var(--gp-card-shadow-hover);
}
.gp-metric-icon {
  float: left;
  width: clamp(26px, 1.8vw, 34px);
  height: clamp(26px, 1.8vw, 34px);
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin-right: 8px;
  font-weight: 800;
  font-size: clamp(12px, 0.85vw, 16px);
}
.gp-metric-blue { background: #e8f2ff; color: #247bf6; }
.gp-metric-indigo { background: #edf0ff; color: #526bf5; }
.gp-metric-violet { background: #f0ecff; color: #7659ef; }
.gp-metric-purple { background: #f3eaff; color: #8b51f0; }
.gp-metric-green { background: #e7f8f0; color: #1faf68; }
.gp-metric p {
  margin: 2px 0 6px;
  color: #71809a;
  font-size: clamp(10px, 0.72vw, 13px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  height: 22px;
  line-height: 22px;
}
.gp-metric strong {
  font-size: clamp(18px, 1.35vw, 26px);
  display: block;
  white-space: nowrap;
  letter-spacing: 0.1px;
  color: var(--gp-ink);
  font-weight: 700;
}
.gp-metric small {
  display: block;
  margin-top: 7px;
  color: #8b98ac;
  font-size: clamp(9px, 0.62vw, 11px);
}
.gp-metric em.up {
  font-style: normal;
  color: var(--gp-green);
  margin-left: 4px;
}
.gp-metric-withdraw .gp-metric-actions {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  clear: both;
}
.gp-btn-mini {
  height: 26px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  border: 0;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.gp-btn-mini-primary {
  background: var(--gp-blue);
  color: #fff;
}
.gp-btn-mini-primary:hover { background: #0f6ae8; }
.gp-btn-mini-primary:disabled { background: #c5d2e0; cursor: not-allowed; }
.gp-btn-mini-ghost {
  background: #fff;
  color: #2d7bf3;
  border: 1px solid #d5e4fa;
}
.gp-btn-mini-ghost:hover { background: #f2f7ff; }
.gp-btn-full { width: 100%; }

/* Panels */
.gp-panel {
  background: #ffffff;
  border: 1px solid var(--gp-line);
  border-radius: var(--gp-radius);
  padding: 26px 24px;
  box-shadow: var(--gp-card-shadow);
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}
.gp-panel:hover {
  border-color: #d5dff0;
  box-shadow: var(--gp-card-shadow-hover);
}
.gp-panel h3 {
  font-size: 18px;
  margin: 0 0 18px;
  line-height: 1.2;
  color: var(--gp-ink);
  font-weight: 700;
  letter-spacing: 0.2px;
}
.gp-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.gp-panel-head h3 { margin: 0; }
.gp-panel-sub {
  font-size: clamp(9px, 0.58vw, 11px);
  color: #8793a8;
  font-weight: 400;
}
.gp-panel-link {
  font-size: clamp(9px, 0.62vw, 11px);
  color: #2779f4;
  text-decoration: none;
  white-space: nowrap;
}
.gp-panel-link:hover { text-decoration: underline; }

/* Grid Two */
.gp-grid-two {
  display: grid;
  grid-template-columns: minmax(590px, 1.35fr) minmax(340px, 1fr);
  gap: 24px;
  margin-bottom: var(--gp-row-gap);
}
.gp-tier-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.gp-tier {
  text-align: center;
  border: 1.5px solid #e7edf6;
  border-radius: 14px;
  padding: 20px 10px 16px;
  min-width: 0;
  height: 252px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  position: relative;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  box-shadow: 0 1px 2px rgba(20, 47, 95, 0.03), 0 6px 14px rgba(20, 47, 95, 0.05);
}
.gp-tier:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 10px rgba(20, 47, 95, 0.08), 0 14px 28px rgba(20, 47, 95, 0.10);
}
.gp-tier.current {
  border-width: 2px;
  box-shadow: 0 4px 10px rgba(45, 120, 246, 0.12), 0 14px 28px rgba(45, 120, 246, 0.18);
}
.gp-tier.normal { border-color: #cfe1ff; background: linear-gradient(180deg, #f7fbff 0%, #eaf2ff 100%); }
.gp-tier.bronze { border-color: #c8ead8; background: linear-gradient(180deg, #f6fdf9 0%, #e8f6ef 100%); }
.gp-tier.gold { border-color: #ffd9a6; background: linear-gradient(180deg, #fffaf2 0%, #fff0d8 100%); }
.gp-tier.diamond { border-color: #d8ccff; background: linear-gradient(180deg, #fbfaff 0%, #efe7ff 100%); }
.gp-tier.current::after {
  content: '当前';
  position: absolute;
  top: -1px;
  right: -1px;
  background: linear-gradient(100deg, #2480ff, #0870f8);
  color: #fff;
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 0 12px 0 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 6px rgba(34, 112, 230, 0.25);
}
.gp-tier h4 { margin: 0 0 6px; font-size: 16px; font-weight: 700; letter-spacing: 0.3px; }
.gp-tier.normal h4, .gp-tier.normal p b { color: #2378f3; }
.gp-tier.bronze h4, .gp-tier.bronze p b { color: #1fa768; }
.gp-tier.gold h4, .gp-tier.gold p b { color: #ef8110; }
.gp-tier.diamond h4, .gp-tier.diamond p b { color: #7150f2; }
.gp-tier img {
  height: 108px;
  width: 116px;
  object-fit: contain;
  margin: 6px auto 4px;
  display: block;
  filter: drop-shadow(0 6px 10px rgba(20, 47, 95, 0.18));
  transition: transform 0.3s ease;
}
.gp-tier:hover img {
  transform: scale(1.04);
}
.gp-tier p { margin: 8px 0 8px; color: #56637b; font-size: 13px; }
.gp-tier p b { font-size: 22px; font-weight: 800; letter-spacing: 0.2px; }
.gp-tier small { font-size: 11px; color: #7d8aa0; line-height: 1.55; display: block; }

.gp-rules-panel {
  position: relative;
  overflow: hidden;
}
.gp-rules-panel ul,
.gp-mini-rules ul {
  padding-left: 17px;
  margin: 0;
  color: #65758f;
  line-height: 1.95;
  font-size: clamp(10px, 0.7vw, 13px);
  max-width: 60%;
  position: relative;
  z-index: 2;
}
.gp-rules-panel li { padding-left: 2px; }
.gp-rules-visual {
  position: absolute;
  right: -1%;
  bottom: -4%;
  width: min(41%, 270px);
  height: 68%;
  opacity: 1;
  z-index: 1;
  pointer-events: none;
}
.gp-rules-pedestal {
  position: absolute;
  left: 6%;
  right: 0;
  bottom: 2%;
  height: 30%;
  border-radius: 50%;
  background: linear-gradient(#f8fbff, #cfe0fc);
  border: 1px solid #bad2f6;
  transform: perspective(450px) rotateX(66deg);
}
.gp-rules-visual img {
  position: absolute;
  width: 67%;
  right: 1%;
  bottom: 7%;
  z-index: 2;
}
.gp-rules-visual img:last-of-type {
  width: 48%;
  left: 0;
  bottom: 5%;
  right: auto;
}

/* Grid Three */
.gp-grid-three {
  display: grid;
  grid-template-columns: minmax(360px, 1.08fr) minmax(430px, 1.08fr) minmax(270px, 0.72fr);
  gap: 24px;
  margin-bottom: var(--gp-row-gap);
}

/* Leaderboard */
.gp-rank-head,
.gp-rank-list li {
  display: grid;
  grid-template-columns: 30px 34px minmax(0, 1fr) 62px 92px;
  align-items: center;
  gap: 0;
}
.gp-rank-head {
  color: #8793a8;
  font-size: clamp(9px, 0.58vw, 11px);
  padding: 0 1px 7px;
  border-bottom: 1px solid #f0f4fa;
  margin-bottom: 4px;
}
.gp-rank-head .gp-rank-name-head {
  grid-column: 2 / 4;
}
.gp-rank-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.gp-rank-list li {
  height: clamp(26px, 1.9vw, 34px);
  font-size: clamp(9px, 0.62vw, 12px);
  color: #66758d;
  border-bottom: 1px solid #f5f8fc;
  transition: background 0.15s;
}
.gp-rank-list li:hover { background: #f7faff; }
.gp-rank-list li:last-child { border-bottom: 0; }
.gp-rank-list li b {
  font-weight: 500;
  color: #53617a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gp-rank-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 8px;
  font-weight: 700;
  box-shadow: 0 1px 4px rgba(24, 57, 100, 0.12);
  margin: auto;
}
.gp-rank-list li > span:last-child { text-align: right; }
.gp-rank-list em {
  font-style: normal;
  text-align: center;
  font-weight: 700;
  color: #8b98ac;
}
.gp-medal-gold {
  width: 21px;
  height: 21px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  margin: auto;
  color: #fff;
  font-size: 11px;
  background: linear-gradient(145deg, #ffd85d, #f29e00);
  box-shadow: 0 2px 5px rgba(242, 158, 0, 0.3);
}
.gp-medal-silver {
  width: 21px;
  height: 21px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  margin: auto;
  color: #fff;
  font-size: 11px;
  background: linear-gradient(145deg, #dbe8ff, #8baeea);
  box-shadow: 0 2px 5px rgba(139, 174, 234, 0.3);
}
.gp-medal-bronze {
  width: 21px;
  height: 21px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  margin: auto;
  color: #fff;
  font-size: 11px;
  background: linear-gradient(145deg, #ffc37e, #ef7d16);
  box-shadow: 0 2px 5px rgba(239, 125, 22, 0.3);
}

/* Empty states */
.gp-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.gp-empty-state-sm {
  padding: 28px 16px 20px;
}
.gp-empty-state-lg {
  padding: 48px 16px 40px;
}
.gp-empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0f6ff, #e0ebff);
  color: #8fb4f0;
  display: grid;
  place-items: center;
  margin-bottom: 14px;
  box-shadow: 0 4px 12px rgba(45, 120, 246, 0.08);
}
.gp-empty-state-lg .gp-empty-icon {
  width: 88px;
  height: 88px;
  margin-bottom: 18px;
}
.gp-empty-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #53617a;
}
.gp-empty-state-lg .gp-empty-title {
  font-size: 15px;
}
.gp-empty-desc {
  margin: 0 0 14px;
  font-size: 12px;
  color: #9aa8bd;
  line-height: 1.5;
}
.gp-empty-state-lg .gp-empty-desc {
  font-size: 13px;
}

/* Trend */
.gp-chart-legend {
  display: flex;
  gap: 16px;
  font-size: clamp(9px, 0.58vw, 11px);
  color: #66758e;
  margin-bottom: 4px;
}
.gp-solid-line, .gp-dash-line {
  width: 15px;
  height: 0;
  border-top: 2px solid #2e7cf6;
  display: inline-block;
  margin-right: 4px;
  vertical-align: middle;
}
.gp-dash-line { border-top-style: dashed; border-color: #78a8fb; }
.gp-trend-chart {
  width: 100%;
  height: clamp(205px, 16.3vw, 305px);
  display: block;
  min-height: 200px;
}
.gp-trend-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}
.gp-trend-summary > div {
  background: #f7faff;
  border-radius: 8px;
  padding: 9px;
}
.gp-trend-summary small {
  display: block;
  color: #8996aa;
  font-size: clamp(9px, 0.58vw, 11px);
}
.gp-trend-summary b {
  display: block;
  font-size: clamp(15px, 1.15vw, 21px);
  margin: 2px 0;
  color: var(--gp-ink);
  font-weight: 700;
}
.gp-trend-summary em {
  font-style: normal;
  color: var(--gp-green);
  font-size: clamp(9px, 0.58vw, 11px);
  display: block;
}

/* Mini promo / invite panel */
.gp-mini-rules { position: relative; }
.gp-promo-code-main {
  background: linear-gradient(135deg, #f0f6ff, #e6efff);
  border: 1px solid #d5e4fa;
  border-radius: 10px;
  padding: 14px 12px;
  margin-bottom: 12px;
  text-align: center;
}
.gp-promo-code-label {
  font-size: 10px;
  color: #8b98ac;
  margin-bottom: 6px;
  font-weight: 500;
}
.gp-promo-code-big {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 4px;
  color: #0874ff;
  margin-bottom: 10px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.gp-promo-link-section {
  background: #f7faff;
  border: 1px solid #eef3fb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.gp-promo-link-label {
  font-size: 10px;
  color: #8b98ac;
  margin-bottom: 6px;
  font-weight: 500;
}
.gp-promo-link-box {
  background: #fff;
  border: 1px dashed #c5d2e0;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 10px;
  color: #53617a;
  word-break: break-all;
  margin-bottom: 8px;
  line-height: 1.4;
  max-height: 44px;
  overflow: hidden;
}
.gp-mini-rules-list {
  margin-top: 8px;
}
.gp-mini-rules-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
  color: #8b98ac;
  font-size: 10px;
  line-height: 1.75;
}
.gp-mini-rules-list li {
  position: relative;
  padding-left: 12px;
}
.gp-mini-rules-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #b8c7de;
}

/* Detail panels */
.gp-detail-panel {
  margin-bottom: var(--gp-row-gap);
}
.gp-detail-panel:last-child {
  margin-bottom: 0;
}
.gp-detail-total {
  font-size: clamp(9px, 0.62vw, 11px);
  color: #8b98ac;
}
.gp-filters {
  display: flex;
  gap: clamp(6px, 0.55vw, 10px);
  align-items: center;
  flex-wrap: nowrap;
  margin-bottom: 9px;
  color: #77859c;
  font-size: clamp(9px, 0.58vw, 11px);
  white-space: nowrap;
}
.gp-filters label {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.gp-filters input,
.gp-filters select {
  height: 30px;
  border: 1px solid #dfe7f3;
  border-radius: 5px;
  background: #fff;
  color: #66758e;
  padding: 0 8px;
  outline: none;
  font-size: clamp(9px, 0.58vw, 11px);
}
.gp-filters select { min-width: 90px; }
.gp-filter-search {
  margin-left: auto;
  flex: 1;
  justify-content: flex-end;
  display: flex;
  align-items: center;
}
.gp-filter-search input {
  width: clamp(135px, 11vw, 220px);
  border-radius: 5px 0 0 5px;
}
.gp-filter-search button {
  height: 30px;
  border: 0;
  background: var(--gp-blue);
  color: #fff;
  padding: 0 15px;
  border-radius: 0 5px 5px 0;
  font-size: clamp(9px, 0.58vw, 11px);
  cursor: pointer;
}
.gp-table-wrap {
  width: 100%;
  overflow-x: auto;
  border-top: 1px solid #eef2f8;
}
.gp-table-wrap table {
  width: 100%;
  border-collapse: collapse;
}
.gp-table-wrap th,
.gp-table-wrap td {
  height: clamp(29px, 1.85vw, 36px);
  padding: 4px 8px;
  line-height: 1.2;
  text-align: left;
  font-size: clamp(9px, 0.58vw, 12px);
  border-bottom: 1px solid #eef2f8;
  white-space: nowrap;
}
.gp-table-wrap th {
  color: #71809a;
  background: #fbfcff;
  font-weight: 600;
}
.gp-table-wrap td { color: #62708a; }
.gp-table-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  color: #fff;
  font-size: 8px;
  font-weight: 700;
}
.gp-table-products {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gp-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: clamp(8px, 0.52vw, 10px);
  font-weight: 500;
}
.gp-tag-green { background: #e9f8ef; color: #20ac68; }
.gp-tag-red { background: #fff0f0; color: #fb5b5b; }
.gp-tag-yellow { background: #fff8e6; color: #d49100; }
.gp-tag-gray { background: #f4f6f9; color: #8593a8; }
.gp-pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  padding: 10px 2px 0;
  color: #7c899e;
  font-size: clamp(9px, 0.58vw, 11px);
}
.gp-pagination button {
  height: 27px;
  min-width: 27px;
  padding: 0 8px;
  border: 1px solid #dfe6f2;
  border-radius: 5px;
  background: #fff;
  color: #60708b;
  font-size: clamp(9px, 0.56vw, 11px);
  cursor: pointer;
}
.gp-pagination button.current {
  background: var(--gp-blue);
  color: #fff;
  border-color: var(--gp-blue);
}
.gp-pagination button:disabled { opacity: 0.4; cursor: not-allowed; }

/* Dialog */
.gp-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 31, 60, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.gp-dialog {
  background: #fff;
  border-radius: 14px;
  width: 480px;
  max-width: 92vw;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(15, 31, 60, 0.3);
  animation: gp-dialog-in 0.2s ease-out;
}
@keyframes gp-dialog-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.gp-dialog-sm { width: 400px; }
.gp-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid #eef2f8;
}
.gp-dialog-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--gp-ink); }
.gp-dialog-close {
  background: transparent;
  border: 0;
  font-size: 22px;
  color: #8b98ac;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.15s;
}
.gp-dialog-close:hover { color: #53617a; }
.gp-dialog-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}
.gp-dialog-foot {
  padding: 14px 20px;
  border-top: 1px solid #eef2f8;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.gp-dialog-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.gp-dialog-info > div {
  background: #f7faff;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  border: 1px solid #eef3fb;
}
.gp-dialog-info small {
  display: block;
  color: #8996aa;
  font-size: 11px;
  margin-bottom: 4px;
}
.gp-dialog-info b {
  font-size: 18px;
  color: var(--gp-ink);
  font-weight: 700;
}
.gp-form-row {
  margin-bottom: 14px;
}
.gp-form-row label {
  display: block;
  font-size: 12px;
  color: #53617a;
  margin-bottom: 6px;
  font-weight: 500;
}
.gp-required { color: #fb5b5b; margin-left: 2px; }
.gp-form-row input,
.gp-form-row select {
  width: 100%;
  height: 38px;
  border: 1px solid #dfe7f3;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 13px;
  color: #18243b;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.gp-form-row input:focus,
.gp-form-row select:focus { border-color: var(--gp-blue); }
.gp-form-error {
  display: block;
  color: #fb5b5b;
  font-size: 11px;
  margin-top: 4px;
}
.gp-form-tip {
  font-size: 11px;
  color: #8b98ac;
  margin-top: -8px;
  margin-bottom: 14px;
  background: #fff8e6;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #fff0cc;
}
.gp-invite-section {
  margin-bottom: 14px;
}
.gp-invite-section small {
  display: block;
  color: #8996aa;
  font-size: 11px;
  margin-bottom: 6px;
  font-weight: 500;
}
.gp-invite-link-box {
  background: #f7faff;
  border: 1px dashed #c5d2e0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 11px;
  color: #53617a;
  word-break: break-all;
  margin-bottom: 8px;
  line-height: 1.5;
}
.gp-invite-code-box {
  background: linear-gradient(135deg, #f0f6ff, #e0ebff);
  border: 1px solid #c5d2e0;
  border-radius: 8px;
  padding: 16px;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 5px;
  color: #0874ff;
  text-align: center;
  margin-bottom: 8px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.gp-invite-tip {
  font-size: 11px;
  color: #8b98ac;
  line-height: 1.6;
  margin: 4px 0 0;
  padding: 10px 12px;
  background: #f7faff;
  border-radius: 8px;
  border: 1px solid #eef3fb;
}

/* Toast */
.gp-toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  background: #18243b;
  color: #fff;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 13px;
  z-index: 2000;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
}
.gp-toast-fade-enter-active, .gp-toast-fade-leave-active {
  transition: all 0.25s ease;
}
.gp-toast-fade-enter-from, .gp-toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

/* Responsive */
@media (max-width: 1220px) {
  .gp-grid-two { grid-template-columns: minmax(460px, 1.3fr) minmax(280px, 1fr); }
  .gp-grid-three { grid-template-columns: minmax(290px, 1.08fr) minmax(340px, 1.08fr) minmax(240px, 0.72fr); }
  .gp-rules-panel ul { max-width: 76%; }
  .gp-rules-panel { padding: 26px; }
  .gp-overview, .gp-trend-panel, .gp-rank-panel { padding: 18px; }
}

@media (max-width: 1070px) and (min-width: 881px) {
  .gp-hero {
    grid-template-columns: minmax(300px, 0.98fr) minmax(340px, 1.02fr);
    min-height: 230px;
  }
  .gp-hero-copy { padding: 22px 12px 15px 24px; }
  .gp-hero-copy h2 { font-size: 19px; }
  .gp-hero-copy li { font-size: 10px; white-space: normal; }
  .gp-metrics { gap: 8px; }
  .gp-metric { padding: 11px 10px; }
  .gp-metric strong { font-size: 17px; }
  .gp-grid-two { grid-template-columns: minmax(410px, 1.3fr) minmax(260px, 1fr); }
  .gp-tier { height: 210px; }
  .gp-tier img { height: 80px; width: 88px; }
  .gp-grid-three { grid-template-columns: minmax(270px, 1.05fr) minmax(310px, 1.1fr) minmax(220px, 0.7fr); }
  .gp-rank-head,
  .gp-rank-list li { grid-template-columns: 26px 28px minmax(0, 1fr) 60px 78px; gap: 0; }
  .gp-filters { gap: 5px; }
  .gp-filters select { min-width: 70px; }
  .gp-filter-search input { width: 120px; }
}

@media (max-width: 880px) {
  .gp-page { padding: 14px; }
  .gp-hero {
    min-height: auto;
    grid-template-columns: 1fr;
  }
  .gp-hero-art { display: none; }
  .gp-metrics { grid-template-columns: repeat(2, 1fr); }
  .gp-metric-withdraw { grid-column: 1 / -1; }
  .gp-grid-two, .gp-grid-three { grid-template-columns: 1fr; }
  .gp-tier-list { grid-template-columns: repeat(2, 1fr); }
  .gp-tier { height: auto; min-height: 200px; }
  .gp-filters { flex-wrap: wrap; }
  .gp-filter-search { margin-left: 0; width: 100%; }
  .gp-filter-search input { width: 100%; }
  .gp-rules-panel ul { max-width: 100%; }
}
</style>
