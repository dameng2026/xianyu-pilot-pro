<template>
  <div class="dashboard-page">
    <div class="dashboard-grid">
      <div class="dashboard-main">
        <section class="hero-card">
          <div class="hero-card-tag">首页轮播广告位（后台可配置）</div>
          <div v-if="!navigationLoaded" class="hero-unavailable" role="status">首页内容加载中...</div>
          <div v-else-if="!navigationAvailable" class="hero-unavailable" role="status">
            <strong>首页内容暂时不可用</strong>
            <span>当前无法判断是否已配置轮播内容，请重试加载。</span>
          </div>
          <div v-else-if="!contentAvailable" class="hero-unavailable" role="status">
            <strong>轮播与公告暂时不可用</strong>
            <span>{{ contentMessage }}</span>
          </div>
          <div v-else-if="carouselUnavailable" class="hero-unavailable" role="status">
            <strong>暂未配置轮播内容</strong>
            <span>管理员发布轮播图后会显示在这里。</span>
          </div>
          <div v-else class="hero-viewport">
            <div class="hero-track" :style="{ transform: `translateX(-${currentSlide * 100}%)` }">
              <article
                v-for="(slide, index) in carouselSlides"
                :key="slide.coverId || slide.id || index"
                :class="['hero-slide', { clickable: !!slide.linkUrl }]"
                @click="clickCarousel(slide)"
              >
                <img class="hero-banner" :src="slide.imageUrl" :alt="slide.title || `轮播图 ${index + 1}`" />
              </article>
            </div>
          </div>

          <button v-if="totalSlides" class="hero-arrow hero-arrow-left" type="button" :disabled="totalSlides <= 1" @click="prevSlide">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <button v-if="totalSlides" class="hero-arrow hero-arrow-right" type="button" :disabled="totalSlides <= 1" @click="nextSlide">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>

          <div v-if="totalSlides" class="hero-dots">
            <button
              v-for="(_, index) in totalSlides"
              :key="`dot-${index}`"
              type="button"
              :class="['hero-dot', { active: currentSlide === index }]"
              @click="goToSlide(index)"
            ></button>
          </div>
        </section>

        <div v-if="error" class="global-notice error">
          <span>{{ error }}</span>
          <button class="retry-btn" type="button" :disabled="reloading" @click="reloadData">{{ reloading ? '重试中...' : '重试' }}</button>
        </div>
        <div v-else-if="navigationAvailable && !contentAvailable" class="global-notice warn" role="status">
          <span>{{ contentMessage }}</span>
          <button class="retry-btn" type="button" :disabled="reloading" @click="reloadData">{{ reloading ? '重试中...' : '重试内容' }}</button>
        </div>

        <section v-if="currentAnnouncement" class="announcement-strip">
          <div class="announcement-icon">📣</div>
          <div class="announcement-copy">
            <strong>{{ currentAnnouncement.title }}</strong>
            <span>{{ firstLine }}</span>
          </div>
          <div class="announcement-actions">
            <button class="strip-btn strip-btn-ghost" type="button" @click="openAnnouncementModal">查看详情</button>
            <button class="strip-btn strip-btn-primary" type="button" @click="dismissAnnouncement">我知道了</button>
          </div>
        </section>

        <CardPanel title="快速开始" desc="把最常用的入口放在这里，方便第一次进入系统时快速上手" class="dashboard-section">
          <div class="quick-start-grid">
            <button v-for="item in quickStarts" :key="item.t" type="button" class="quick-card" @click="goFeature(item)">
              <div :class="['circle-ico', item.c]"><Icon :name="item.i" /></div>
              <div class="quick-text">
                <strong>{{ item.t }}</strong>
                <span>{{ item.d }}</span>
              </div>
              <span class="card-arrow">›</span>
            </button>
          </div>
        </CardPanel>

        <CardPanel title="功能特性" desc="常用业务能力模块一览，延续设计稿中的两行卡片结构" class="dashboard-section">
          <div class="feature-grid">
            <button v-for="item in features" :key="item.t" type="button" class="feature-card" @click="goFeature(item)">
              <div :class="['circle-ico', item.c]"><Icon :name="item.i" /></div>
              <div class="feature-text">
                <strong>{{ item.t }}</strong>
                <span>{{ item.d }}</span>
                <em>{{ `点击进入 ${item.targetLabel}` }}</em>
              </div>
              <span class="card-arrow">›</span>
            </button>
          </div>
        </CardPanel>

        <CardPanel title="最近实时事件" class="dashboard-section">
          <div v-if="realtimeEvents.length === 0" class="events-empty">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#b7c5db" stroke-width="1.5">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
            <p>{{ sseStatus === 'connected' ? '暂无实时事件' : (sseStatus === 'connecting' || sseStatus === 'reconnecting' ? '实时事件流连接中...' : '实时事件流暂时不可用') }}</p>
          </div>
          <div v-else class="events-box">
            <div v-for="(event, index) in realtimeEvents" :key="event.id || `rt-${index}`" class="event-row">
              <strong>{{ event.type || '实时事件' }}</strong>
              <span>{{ event.text }}</span>
              <em>{{ event.time || '--:--:--' }}</em>
            </div>
          </div>
        </CardPanel>
      </div>

      <aside class="dashboard-side">
        <CardPanel class="side-panel">
          <template #title>使用指南</template>
          <template #action>
            <button class="side-link" type="button" @click="emit('navigate', 'user-manual')">查看全部 ›</button>
          </template>
          <div class="guide-section">
            <h4>新手入门指南</h4>
            <p>{{ guideLeadText }}</p>
            <ol class="guide-list">
              <li v-for="item in guides" :key="item.title">
                <div class="guide-step-head">
                  <strong>{{ item.title }}</strong>
                  <em :class="['guide-step-status', item.state]">{{ item.stateText }}</em>
                </div>
                <span>{{ item.desc }}</span>
              </li>
            </ol>
            <button class="guide-doc-link" type="button" @click="openGuideDocument">前往阅读文档</button>
            <div class="guide-collapse-list">
              <div v-for="item in guideCollapsibles" :key="item.label" class="guide-collapse-block">
                <button
                  type="button"
                  class="guide-collapse-item"
                  @click="toggleCollapse(item.label)"
                >
                  <span>{{ item.label }}</span>
                  <svg :class="['collapse-chevron', { open: isGuideOpen(item.label) }]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                <div v-if="isGuideOpen(item.label)" class="guide-collapse-panel">
                  <p>{{ item.summary }}</p>
                  <ul class="guide-collapse-points">
                    <li v-for="point in item.points" :key="point">{{ point }}</li>
                  </ul>
                  <button v-if="item.actionText" class="guide-inline-link" type="button" @click="goFeature(item)">
                    {{ item.actionText }} ›
                  </button>
                </div>
              </div>
            </div>
          </div>
        </CardPanel>

        <CardPanel class="side-panel">
          <template #title>最近通知</template>
          <template #action>
            <button class="side-link" type="button" @click="emit('navigate', 'messages')">查看全部 ›</button>
          </template>
          <div v-if="!navigationAvailable" class="side-empty">
            <strong>通知状态暂时不可用</strong>
            <span>当前无法判断是否有新通知，请重试加载首页数据</span>
          </div>
          <div v-else-if="notifications.length === 0" class="side-empty">
            <strong>暂无通知</strong>
            <span>系统消息与业务提醒会展示在这里</span>
          </div>
          <div v-else class="side-list">
            <article v-for="(item, index) in notifications" :key="item.id || `notice-${index}`" class="notice-item">
              <div class="notice-head">
                <strong>{{ item.title }}</strong>
                <span>{{ item.time || '' }}</span>
              </div>
              <div class="notice-meta">
                <i :class="['notice-tag', `notice-tag-${item.typeClass}`]">{{ item.typeLabel }}</i>
                <b :class="['notice-state', { unread: item.isUnread }]">{{ item.isUnread ? '未读' : '已读' }}</b>
              </div>
              <p>{{ item.text }}</p>
            </article>
          </div>
        </CardPanel>

        <CardPanel title="系统状态" class="side-panel">
          <div class="status-list">
            <div v-for="item in systemStatus" :key="item.id || item.label" class="status-row">
              <span><i :class="['status-dot', `status-${item.status}`]"></i>{{ item.label }}</span>
              <strong :class="`status-${item.status}-text`">{{ statusText(item) }}</strong>
            </div>
            <div class="status-footer">
              <strong :class="statusSummaryClass">{{ statusSummaryText }}</strong>
              <span>{{ lastLoaded }}</span>
            </div>
          </div>
        </CardPanel>
      </aside>
    </div>

    <Teleport to="body">
      <div v-if="announcementModalVisible && currentAnnouncement" class="announcement-modal-mask" @click.self="closeAnnouncementModal">
        <section class="announcement-modal">
          <button class="announcement-modal-close" type="button" @click="closeAnnouncementModal">×</button>
          <div class="announcement-modal-icon">📣</div>
          <h3>{{ currentAnnouncement.title }}</h3>
          <p>{{ currentAnnouncement.content || firstLine }}</p>
          <div class="announcement-modal-actions">
            <button class="strip-btn strip-btn-ghost modal-btn" type="button" @click="closeAnnouncementModal">查看详情</button>
            <button class="strip-btn strip-btn-primary modal-btn" type="button" @click="acknowledgeAnnouncement">我知道了</button>
          </div>
        </section>
      </div>
    </Teleport>

    <!-- 惊喜提示：用户不在场时滑块自动求解成功次数（右侧滑入，自动消失，仅好消息） -->
    <Teleport to="body">
      <Transition name="surprise-slide">
        <div v-if="surpriseVisible" class="surprise-toast" role="status" aria-live="polite">
          <div class="surprise-toast-glow"></div>
          <div class="surprise-toast-icon">🛡️</div>
          <div class="surprise-toast-body">
            <div class="surprise-toast-title">在您离开的这段时间</div>
            <div class="surprise-toast-stats">
              滑块求解已自动为您化解
              <span class="surprise-toast-num">{{ surpriseDisplayNum }}</span>
              次验证
            </div>
            <div v-if="surpriseData.accountCount > 0" class="surprise-toast-meta">
              守护 {{ surpriseData.accountCount }} 个账号的在线状态
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import Icon from '../components/Icon.vue'
import { getAnnouncementFirstLine, selectCurrentAnnouncement } from './dashboard/announcement-model.js'
import { shortText, timeText } from '../utils/format.js'
import { getNavigationHome, NAVIGATION_HOME_PERSISTENT_KEY } from '../api/navigation.js'
import { readPersistentCache } from '../utils/persistentCache.js'
import { getSseStatus } from '../utils/sse.js'
import { getCaptchaSilentSummary } from '../api/captcha.js'

const emit = defineEmits(['navigate'])

const carousels = ref([])
const announcements = ref([])
const currentSlide = ref(0)
const error = ref('')
const reloading = ref(false)
const navigationLoaded = ref(false)
const navigationAvailable = ref(false)
const contentAvailable = ref(true)
const contentMessage = ref('轮播与公告暂时无法读取，其他首页数据不受影响')
const carouselImageReadyMap = ref({})
const carouselImagePreloads = new Map()
async function reloadData() {
  reloading.value = true
  try {
    await loadData({ force: true })
  } catch (e) {
    markNavigationUnavailable()
    error.value = `加载失败：${e.message || '网络异常'}，请检查后重试`
  } finally {
    reloading.value = false
  }
}
const notifications = ref([])
const realtimeEvents = ref([])
const sseStatus = ref(getSseStatus())
const lastLoaded = ref('-')
const collapsed = reactive({})
const dismissedAnnouncementIds = ref([])
const announcementModalVisible = ref(false)
let autoTimer = null
const ANNOUNCEMENT_ACK_STORAGE_KEY = 'xya_dashboard_announcement_ack'
const defaultOverview = {
  accountCount: 0,
  goodsCount: 0,
  todayOrderCount: 0,
  messageCount: 0,
  pendingCount: 0
}
const overview = ref({ ...defaultOverview })
const overviewAvailable = ref(false)
const unknownSystemStatus = [
  { id: 'api', label: 'API服务', status: 'unknown' },
  { id: 'ws', label: 'WebSocket服务', status: 'unknown' },
  { id: 'db', label: '数据库服务', status: 'unknown' },
  { id: 'storage', label: '文件存储', status: 'unknown' }
]

const systemStatus = ref(unknownSystemStatus.map(item => ({ ...item })))

const displaySlides = computed(() => {
  return carousels.value
    .filter(item => item?.enabled !== false)
    .sort((a, b) => (a?.sortOrder ?? 0) - (b?.sortOrder ?? 0))
    .flatMap(item => {
      const coverItems = Array.isArray(item.coverItems) && item.coverItems.length
        ? item.coverItems
        : [{
            id: `${item.id || 'legacy'}-0`,
            imageUrl: item.imageUrl || '',
            linkUrl: item.linkUrl || '',
            title: item.title || '',
            description: item.description || '',
            enabled: item.enabled !== false,
            sortOrder: 0
          }]
      return coverItems
        .filter(cover => cover?.enabled !== false && cover?.imageUrl)
        .sort((a, b) => (a?.sortOrder ?? 0) - (b?.sortOrder ?? 0))
        .map((cover, index) => ({
          ...item,
          ...cover,
          coverId: cover.id || `${item.id || 'carousel'}-${index}`,
          title: cover.title || item.title || '',
          description: cover.description || item.description || '',
          imageUrl: cover.imageUrl || item.imageUrl || '',
          linkUrl: safeCarouselLink(cover.linkUrl || item.linkUrl || '')
        }))
    })
})

const carouselSlides = computed(() => {
  const activeSlides = displaySlides.value
    .map(slide => ({
      ...slide,
      imageUrl: resolveCarouselImage(slide?.imageUrl)
    }))
    .filter(slide => slide.imageUrl)
  const readySlides = activeSlides.filter(slide => carouselImageReadyMap.value[slide.imageUrl] === true)
  return readySlides
})

const totalSlides = computed(() => carouselSlides.value.length)
const carouselUnavailable = computed(() => navigationLoaded.value && navigationAvailable.value && contentAvailable.value && totalSlides.value === 0)
const currentAnnouncement = computed(() => selectCurrentAnnouncement(announcements.value, dismissedAnnouncementIds.value))
const firstLine = computed(() => getAnnouncementFirstLine(currentAnnouncement.value))

const abnormalStatusCount = computed(() => systemStatus.value.filter(item => item.status === 'down').length)
const unknownStatusCount = computed(() => systemStatus.value.filter(item => item.status === 'unknown').length)
const statusSummaryText = computed(() => {
  if (error.value) return '导航数据加载异常'
  if (abnormalStatusCount.value > 0) return `${abnormalStatusCount.value} 个服务需关注`
  if (unknownStatusCount.value > 0) return '服务状态未提供'
  return '系统运行正常'
})
const statusSummaryClass = computed(() => {
  if (error.value || abnormalStatusCount.value > 0) return 'status-error'
  return unknownStatusCount.value > 0 ? 'status-unknown' : 'status-success'
})
const guideLeadText = computed(() => {
  if (!overviewAvailable.value) return '运营概览暂时不可用，当前不能判断账号、商品或待处理任务状态，请稍后重试。'
  const { accountCount, goodsCount, pendingCount } = overview.value
  if (accountCount === 0) return '首次使用建议先添加店铺账号并完成授权，再继续配置商品与自动化功能。'
  if (goodsCount === 0) return `当前已接入 ${accountCount} 个账号，下一步建议完善商品信息与发布流程。`
  if (pendingCount > 0) return `当前有 ${pendingCount} 个待处理任务，建议优先跟进订单履约和自动化发货配置。`
  return `当前已接入 ${accountCount} 个账号、同步 ${goodsCount} 个商品，可以继续优化工作流和消息处理效率。`
})
const guides = computed(() => {
  if (!overviewAvailable.value) {
    return [
      { title: '连接店铺账号', desc: '账号接入状态暂时不可用。', to: 'accounts', state: 'unknown', stateText: '状态未知' },
      { title: '完善商品与订单配置', desc: '商品与订单概览暂时不可用。', to: 'products', state: 'unknown', stateText: '状态未知' },
      { title: '开启自动化与消息联动', desc: '消息与自动化概览暂时不可用。', to: 'workflow', state: 'unknown', stateText: '状态未知' }
    ]
  }
  const { accountCount, goodsCount, messageCount, pendingCount } = overview.value
  return [
    {
      title: '连接店铺账号',
      desc: accountCount > 0
        ? `已接入 ${accountCount} 个账号，可继续检查授权与在线状态。`
        : '先添加店铺账号并完成授权，后续商品、订单与消息功能才会正常联动。',
      to: 'accounts',
      state: accountCount > 0 ? 'done' : 'todo',
      stateText: accountCount > 0 ? '已完成' : '待开始'
    },
    {
      title: '完善商品与订单配置',
      desc: goodsCount > 0
        ? pendingCount > 0
          ? `当前已同步 ${goodsCount} 个商品，另有 ${pendingCount} 个待处理任务需要跟进。`
          : `当前已同步 ${goodsCount} 个商品，可继续检查发布、库存与订单流程。`
        : '建议优先进入商品管理完善商品信息，再联动订单与自动发货配置。',
      to: goodsCount > 0 ? 'orders' : 'products',
      state: goodsCount > 0 ? (pendingCount > 0 ? 'progress' : 'done') : 'todo',
      stateText: goodsCount > 0 ? (pendingCount > 0 ? '处理中' : '已完成') : '待开始'
    },
    {
      title: '开启自动化与消息联动',
      desc: messageCount > 0
        ? `已有 ${messageCount} 条会话数据，可继续配置自动回复、工作流和数据统计。`
        : '进入工作流、自动发货或数据面板，逐步建立自动化处理链路。',
      to: messageCount > 0 ? 'messages' : 'workflow',
      state: messageCount > 0 || pendingCount > 0 ? 'progress' : 'suggest',
      stateText: messageCount > 0 || pendingCount > 0 ? '进行中' : '建议体验'
    }
  ]
})
const guideCollapsibles = computed(() => {
  if (!overviewAvailable.value) {
    return [{
      label: '数据状态说明',
      summary: '当前没有取得运营概览，不能根据零值判断业务尚未开始。',
      points: ['请先重试加载首页数据。', '若持续失败，请检查后端服务和账号授权状态。'],
      actionText: '查看系统设置',
      to: 'settings-about'
    }]
  }
  const { accountCount, goodsCount, todayOrderCount, pendingCount } = overview.value
  return [
    {
      label: '功能使用教程',
      summary: '建议按“账号接入 → 商品管理 → 自动化配置”的顺序完成配置，上手速度会更快。',
      points: [
        accountCount > 0
          ? `账号中心当前已接入 ${accountCount} 个账号，可继续检查在线状态与授权有效期。`
          : '先进入“账号管理”添加店铺账号，完成授权后再继续后续业务操作。',
        goodsCount > 0
          ? `商品中心当前已有 ${goodsCount} 个商品，可继续编辑详情、上下架与同步信息。`
          : '进入“商品管理”发布或同步商品，准备后续订单、卡密和自动化流程。',
        '最后进入“自动化发货”或“工作流”，为重复业务建立稳定规则。'
      ],
      actionText: accountCount > 0 ? '继续管理账号' : '立即添加账号',
      to: 'accounts'
    },
    {
      label: '最佳实践案例',
      summary: '推荐把导航面板作为每天登录后的第一站，先处理提醒，再进入具体模块。',
      points: [
        pendingCount > 0
          ? `当前有 ${pendingCount} 个待处理任务，建议优先进入订单或自动发货模块。`
          : '先查看最近实时事件和最近通知，确认系统是否有新订单、消息或异常提醒。',
        todayOrderCount > 0
          ? `今日已产生 ${todayOrderCount} 笔订单，建议同步跟进履约状态与发货进度。`
          : '若今日订单较少，可优先完善商品资料、自动回复和工作流规则。',
        '完成日常检查后，再到数据面板观察成交、消息和服务表现。'
      ],
      actionText: '进入工作流',
      to: 'workflow'
    },
    {
      label: '常见问题解答',
      summary: '如果模块没有数据或入口不可用，通常可以先检查以下几个基础项。',
      points: [
        accountCount > 0
          ? '账号已接入但业务数据为空时，先检查店铺授权是否失效或连接是否中断。'
          : '尚未接入账号时，部分商品、订单与消息模块不会展示实时数据。',
        notifications.value.length > 0
          ? '最近通知中已有系统消息，可优先查看提醒内容定位异常来源。'
          : '如果最近通知为空，说明近期没有新的系统消息或业务提醒。',
        error.value
          ? '当前检测到导航数据加载异常，建议稍后刷新页面或检查后端服务状态。'
          : unknownStatusCount.value > 0
            ? '当前未取得服务健康状态，不能据此判断系统是否正常，请稍后重试。'
            : '系统状态正常时，可继续检查网络、SSE 连接或各模块筛选条件。'
      ],
      actionText: '查看系统设置',
      to: 'settings-about'
    }
  ]
})

function todayStamp() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function readAnnouncementAckMap() {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(ANNOUNCEMENT_ACK_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function rememberAnnouncementAcknowledged(announcement = currentAnnouncement.value) {
  if (typeof window === 'undefined' || !announcement?.id) return
  const ackMap = readAnnouncementAckMap()
  ackMap[String(announcement.id)] = todayStamp()
  window.localStorage.setItem(ANNOUNCEMENT_ACK_STORAGE_KEY, JSON.stringify(ackMap))
}

function hasAcknowledgedAnnouncementToday(announcement = currentAnnouncement.value) {
  if (!announcement?.id) return false
  const ackMap = readAnnouncementAckMap()
  return ackMap[String(announcement.id)] === todayStamp()
}

function syncAnnouncementModalVisibility() {
  announcementModalVisible.value = !!currentAnnouncement.value && !hasAcknowledgedAnnouncementToday(currentAnnouncement.value)
}

function resolveCarouselImage(imageUrl) {
  const value = String(imageUrl || '').trim()
  if (!value) return ''
  if (/^(https?:)?\/\//.test(value) || value.startsWith('/')) return value
  return `/${value.replace(/^\/+/, '')}`
}

function setCarouselImageReady(imageUrl, ready) {
  if (!imageUrl) return
  carouselImageReadyMap.value = {
    ...carouselImageReadyMap.value,
    [imageUrl]: ready
  }
}

function preloadCarouselImage(imageUrl) {
  if (!imageUrl || typeof Image === 'undefined') return
  if (carouselImageReadyMap.value[imageUrl] === true || carouselImagePreloads.has(imageUrl)) return

  const img = new Image()
  const finalize = (ready) => {
    carouselImagePreloads.delete(imageUrl)
    setCarouselImageReady(imageUrl, ready)
  }

  carouselImagePreloads.set(imageUrl, img)
  img.onload = () => finalize(true)
  img.onerror = () => finalize(false)
  img.src = imageUrl

  if (img.complete && img.naturalWidth > 0) {
    finalize(true)
  }
}

function nextSlide() {
  if (totalSlides.value <= 1) return
  currentSlide.value = (currentSlide.value + 1) % totalSlides.value
  restartAuto()
}

function prevSlide() {
  if (totalSlides.value <= 1) return
  currentSlide.value = (currentSlide.value - 1 + totalSlides.value) % totalSlides.value
  restartAuto()
}

function goToSlide(index) {
  if (index < 0 || index >= totalSlides.value) return
  currentSlide.value = index
  restartAuto()
}

function restartAuto() {
  if (autoTimer) clearInterval(autoTimer)
  if (totalSlides.value <= 1) return
  autoTimer = setInterval(() => {
    currentSlide.value = (currentSlide.value + 1) % totalSlides.value
  }, 5000)
}

function toArrayOrThrow(data, label) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    if (Array.isArray(data.records)) return data.records
    if (Array.isArray(data.list)) return data.list
  }
  throw new Error(`${label}响应格式异常`)
}

function normalizeOverviewOrThrow(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('运营概览响应格式异常')
  }
  const result = {}
  for (const key of Object.keys(defaultOverview)) {
    const value = data[key]
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
      throw new Error('运营概览响应格式异常')
    }
    result[key] = value
  }
  return result
}

function markNavigationUnavailable() {
  navigationAvailable.value = false
  navigationLoaded.value = true
  contentAvailable.value = false
  contentMessage.value = '当前无法读取首页数据，请稍后重试'
  overviewAvailable.value = false
  overview.value = { ...defaultOverview }
  carousels.value = []
  announcements.value = []
  notifications.value = []
  systemStatus.value = unknownSystemStatus.map(item => ({ ...item }))
  lastLoaded.value = '-'
  restartAuto()
}

function formatNoticeTime(value) {
  const text = timeText(value)
  if (!text || text === '-') return ''
  const normalized = String(text).replace('T', ' ')
  if (!normalized.includes(' ')) return normalized
  const [date, clock = ''] = normalized.split(' ')
  return `${date.slice(5)} ${clock.slice(0, 5)}`
}

function formatEventTime(value) {
  const text = timeText(value)
  if (!text || text === '-') return '--:--:--'
  const normalized = String(text).replace('T', ' ')
  return normalized.includes(' ') ? normalized.split(' ').pop().slice(0, 8) : normalized.slice(-8)
}

function mapNoticeType(type) {
  switch (String(type || '').toLowerCase()) {
    case 'system':
      return { label: '系统', className: 'system' }
    case 'warning':
      return { label: '预警', className: 'warning' }
    case 'info':
      return { label: '通知', className: 'info' }
    default:
      return { label: '消息', className: 'info' }
  }
}

function normalizeNotification(item, index) {
  const type = mapNoticeType(item?.type)
  return {
    id: item?.id || `notice-${index}`,
    title: item?.title || type.label,
    text: shortText(item?.content || item?.message || '-', 72),
    time: formatNoticeTime(item?.createdTime || item?.time || item?.createdAt),
    typeLabel: type.label,
    typeClass: type.className,
    isUnread: Number(item?.status ?? 0) === 0
  }
}

function normalizeSystemStatus(item, index) {
  const rawStatus = item?.status
  const numericStatus = Number(rawStatus)
  const hasStatus = rawStatus !== null && rawStatus !== undefined && rawStatus !== ''
  const status = hasStatus && (rawStatus === 'ok' || rawStatus === 'healthy' || numericStatus === 1)
    ? 'ok'
    : hasStatus && (rawStatus === 'down' || rawStatus === 'unhealthy' || numericStatus === 0)
      ? 'down'
      : 'unknown'
  return {
    id: item?.id || `status-${index}`,
    label: item?.nodeName || unknownSystemStatus[index]?.label || `服务节点 ${index + 1}`,
    status
  }
}

function statusText(item) {
  if (item?.status === 'ok') return '正常'
  if (item?.status === 'down') return '异常'
  return '未知'
}

function pushRealtimeEvent(eventItem) {
  if (!eventItem?.text) return
  const current = realtimeEvents.value.filter(item => item?.id !== eventItem.id)
  realtimeEvents.value = [eventItem, ...current].slice(0, 5)
}

async function loadData(options = {}) {
  error.value = ''
  const cached = await getNavigationHome({ force: options.force === true, limit: 5 })
  // withPersistentCache 返回 { data: <axios响应>, stale, fromCache }
  // axios 响应结构为 { code, msg, data: <业务数据> }
  const homeRes = cached?.data ?? cached
  const homeData = homeRes?.data
  applyHomeData(homeData)
}

// 将首页数据应用到响应式状态，供 loadData 和同步缓存复用
function applyHomeData(homeData) {
  if (!homeData || typeof homeData !== 'object' || Array.isArray(homeData)) {
    throw new Error('首页导航响应格式异常')
  }
  const nextCarousels = toArrayOrThrow(homeData.carousels, '轮播内容')
  const nextAnnouncements = toArrayOrThrow(homeData.announcements, '公告内容')
  const nextOverview = normalizeOverviewOrThrow(homeData.overview)
  const nextNotifications = toArrayOrThrow(homeData.notifications, '最近通知')
  const nextSystemStatus = toArrayOrThrow(homeData.systemStatus, '系统状态')
  const nextContentAvailable = homeData.contentAvailable !== false
  const nextContentMessage = typeof homeData.contentMessage === 'string' && homeData.contentMessage.trim()
    ? homeData.contentMessage.trim()
    : '轮播与公告暂时无法读取，其他首页数据不受影响'

  carousels.value = nextCarousels
  announcements.value = nextAnnouncements
  contentAvailable.value = nextContentAvailable
  contentMessage.value = nextContentMessage
  overviewAvailable.value = true
  overview.value = nextOverview

  notifications.value = nextNotifications
    .slice(0, 5)
    .map((item, index) => normalizeNotification(item, index))

  const list = nextSystemStatus.map((item, index) => normalizeSystemStatus(item, index))
  systemStatus.value = list.length ? list : unknownSystemStatus.map(item => ({ ...item }))
  syncAnnouncementModalVisibility()
  lastLoaded.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  navigationAvailable.value = true
  navigationLoaded.value = true
  if (currentSlide.value >= totalSlides.value) currentSlide.value = 0
  restartAuto()
}

// 同步从持久化缓存恢复首页数据，避免进入页面时闪现"加载中"
function applyHomeDataFromCacheIfAvailable() {
  const cached = readPersistentCache(NAVIGATION_HOME_PERSISTENT_KEY)
  if (!cached || !cached.value) return false
  try {
    const homeRes = cached.value
    const homeData = homeRes?.data
    if (!homeData || typeof homeData !== 'object' || Array.isArray(homeData)) return false
    applyHomeData(homeData)
    return true
  } catch {
    return false
  }
}

function clickCarousel(item) {
  const safeLink = safeCarouselLink(item?.linkUrl)
  if (!safeLink) return
  const opened = window.open(safeLink, '_blank', 'noopener,noreferrer')
  if (opened) opened.opener = null
}

function safeCarouselLink(value) {
  const link = String(value || '').trim()
  if (!link || link.includes('\\') || Array.from(link).some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)) return ''
  if ((link.startsWith('/') && !link.startsWith('//')) || link.startsWith('#/')) return link
  try {
    const parsed = new URL(link)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return ''
    return parsed.href
  } catch {
    return ''
  }
}

async function openAnnouncementModal() {
  const ann = currentAnnouncement.value
  if (!ann) return
  announcementModalVisible.value = true
}

function dismissAnnouncement() {
  rememberAnnouncementAcknowledged()
  if (!currentAnnouncement.value?.id) return
  if (!dismissedAnnouncementIds.value.includes(currentAnnouncement.value.id)) {
    dismissedAnnouncementIds.value.push(currentAnnouncement.value.id)
  }
  announcementModalVisible.value = false
}

function closeAnnouncementModal() {
  announcementModalVisible.value = false
}

function acknowledgeAnnouncement() {
  rememberAnnouncementAcknowledged()
  announcementModalVisible.value = false
}

function onSse(event) {
  const detail = event.detail || {}
  pushRealtimeEvent({
    id: detail.id ? `sse-${detail.id}` : `sse-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type: detail.title || detail.name || formatRealtimeType(detail.type || detail.event),
    text: shortText(detail.message || detail.content || detail.description || JSON.stringify(detail), 80),
    time: formatEventTime(detail.createdTime || detail.time || detail.timestamp || Date.now())
  })
}

function onSseStatus(event) {
  sseStatus.value = String(event?.detail || 'disconnected')
}

function toggleCollapse(label) {
  const next = !isGuideOpen(label)
  guideCollapsibles.value.forEach(item => {
    collapsed[item.label] = false
  })
  collapsed[label] = next
}

function isGuideOpen(label) {
  const value = collapsed[label]
  if (value === undefined) return label === guideCollapsibles.value[0]?.label
  return value
}

function formatRealtimeType(type) {
  switch (String(type || '').toLowerCase()) {
    case 'order':
      return '订单事件'
    case 'message':
      return '消息事件'
    case 'warning':
      return '预警事件'
    case 'workflow':
      return '工作流事件'
    case 'delivery':
      return '发货事件'
    case 'system':
      return '系统事件'
    default:
      return '实时事件'
  }
}

function openAiCs() {
  // 派发全局事件，由 App.vue 监听并打开 AI 客服"小梦"面板
  window.dispatchEvent(new CustomEvent('xya-open-ai-cs'))
}

const quickStarts = [
  { t: '添加账号', d: '添加店铺账号，开始管理您的店铺', i: 'users', c: 'blue-bg', to: 'accounts' },
  { t: 'WebSocket连接', d: '建立实时连接，接收消息和数据', i: 'data', c: 'purple-bg', to: 'accounts' },
  { t: '商品管理', d: '发布管理商品，优化商品信息', i: 'product', c: 'green-bg', to: 'products' },
  { t: '自动化发货', d: '设置发货规则，自动处理订单', i: 'truck', c: 'orange-bg', to: 'auto-delivery' }
]

const features = [
  { t: '多账号管理', d: '多账号分组管理，权限精细控制', i: 'users', c: 'purple-bg', to: 'accounts', targetLabel: '管理账号' },
  { t: '商品同步', d: '批量同步商品，自动上架提升成交效率', i: 'product', c: 'green-bg', to: 'products', targetLabel: '商品管理' },
  { t: '订单管理', d: '实时同步订单，自动处理订单状态', i: 'order', c: 'blue-bg', to: 'orders', targetLabel: '订单管理' },
  { t: '自动发货', d: '自动处理发货流程，提高发货效率', i: 'truck', c: 'orange-bg', to: 'auto-delivery', targetLabel: '自动化' },
  { t: '商机发掘', d: '发掘潜在商机，挖掘优质客户', i: 'opportunity', c: 'purple-bg', to: 'opportunities', targetLabel: '商机发现' },
  { t: '工作流', d: '自定义业务流程，自动化处理任务', i: 'workflow', c: 'cyan-bg', to: 'workflow', targetLabel: '工作流' },
  { t: '卡密仓库', d: '管理卡密资源，安全存储和使用', i: 'key', c: 'orange-bg', to: 'card-warehouse', targetLabel: '卡密仓库' },
  { t: '数据统计', d: '多维度数据分析，助力决策优化', i: 'data', c: 'blue-bg', to: 'data', targetLabel: '数据面板' }
]

function goFeature(item) {
  if (item?.to) emit('navigate', item.to)
}

watch(displaySlides, (slides) => {
  const urls = slides
    .map(slide => resolveCarouselImage(slide?.imageUrl))
    .filter(Boolean)

  const nextReadyMap = {}
  for (const imageUrl of urls) {
    nextReadyMap[imageUrl] = carouselImageReadyMap.value[imageUrl] === true
  }
  carouselImageReadyMap.value = nextReadyMap

  for (const imageUrl of urls) {
    preloadCarouselImage(imageUrl)
  }
}, { immediate: true })

// ============================================================
// 惊喜提示：用户不在场时滑块自动求解成功次数
// ============================================================
// - localStorage 记录上次访问首页的时间，作为 since 查询
// - sessionStorage 防止同一浏览会话内刷新重复弹窗
// - 仅查询自动触发场景（ws_connect/cookie_keepalive/token_refresh）的成功次数
// - 弹窗从右侧滑入，5 秒后自动滑出，全程无需用户操作
const LAST_VISIT_KEY = 'xya_home_last_visit'
const SURPRISE_SESSION_KEY = 'xya_captcha_surprise_shown'
const SURPRISE_DISPLAY_MS = 5000
const SURPRISE_MIN_INTERVAL_MS = 3 * 60 * 1000 // 距上次访问 < 3 分钟不弹（刷新页面）

const surpriseVisible = ref(false)
const surpriseDisplayNum = ref(0)
const surpriseData = reactive({ success: 0, accountCount: 0, lastSolveTime: '' })
let surpriseHideTimer = null
let surpriseCountRaf = 0

function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3) }

function animateSurpriseNum(target) {
  if (!window.requestAnimationFrame) { surpriseDisplayNum.value = target; return }
  cancelAnimationFrame(surpriseCountRaf)
  const start = performance.now()
  const duration = 1200
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration)
    surpriseDisplayNum.value = Math.round(easeOutCubic(t) * target)
    if (t < 1) surpriseCountRaf = requestAnimationFrame(step)
  }
  surpriseCountRaf = requestAnimationFrame(step)
}

function hideSurprise() {
  surpriseVisible.value = false
  if (surpriseHideTimer) { clearTimeout(surpriseHideTimer); surpriseHideTimer = null }
}

/**
 * 进入首页时加载"用户不在场时"自动求解成功摘要。
 * 仅展示好消息（成功次数），不涉及失败/总数。
 * 弹窗从右侧滑入，5 秒后自动滑出。
 */
async function loadSurprise() {
  const now = Date.now()
  // 本次 session 已展示过则跳过（防止刷新重复弹）
  if (sessionStorage.getItem(SURPRISE_SESSION_KEY)) return

  const lastVisitStr = localStorage.getItem(LAST_VISIT_KEY)
  let lastVisit = null
  if (lastVisitStr) {
    const t = Date.parse(lastVisitStr)
    if (!isNaN(t)) lastVisit = t
  }

  // 首次访问或距上次访问 < 3 分钟，不弹（刷新场景）
  if (!lastVisit || now - lastVisit < SURPRISE_MIN_INTERVAL_MS) {
    localStorage.setItem(LAST_VISIT_KEY, new Date(now).toISOString())
    return
  }

  try {
    const res = await getCaptchaSilentSummary({ since: new Date(lastVisit).toISOString() })
    const data = res?.data || res || {}
    const success = Number(data.success) || 0
    if (success <= 0) return // 无新成功记录，不弹

    // 标记本次 session 已展示
    sessionStorage.setItem(SURPRISE_SESSION_KEY, '1')
    surpriseData.success = success
    surpriseData.accountCount = Number(data.accountCount) || 0
    surpriseData.lastSolveTime = data.lastSolveTime || ''

    // 同时往"最近通知"板块插入一条好消息
    notifications.value.unshift({
      id: `captcha-surprise-${now}`,
      title: '滑块自动守护',
      typeLabel: '系统',
      typeClass: 'success',
      isUnread: true,
      time: '刚刚',
      text: `您不在场时已自动为您解决 ${success} 次滑块验证，账号在线状态持续守护中。`
    })

    // 显示弹窗 + 数字递增动画
    surpriseVisible.value = true
    requestAnimationFrame(() => animateSurpriseNum(success))

    // 5 秒后自动消失
    surpriseHideTimer = setTimeout(hideSurprise, SURPRISE_DISPLAY_MS)
  } catch (e) {
    // 静默失败，不打扰用户
  } finally {
    // 无论是否弹出，都更新访问时间
    localStorage.setItem(LAST_VISIT_KEY, new Date(now).toISOString())
  }
}

onMounted(() => {
  window.addEventListener('xya-sse-event', onSse)
  window.addEventListener('xya-sse-status', onSseStatus)
  // 同步从缓存恢复首页数据，有缓存时立即渲染轮播图/广告，无闪烁
  const hasCache = applyHomeDataFromCacheIfAvailable()
  // 后台异步刷新（命中新鲜期则不发请求；命中过期期则后台静默刷新）
  loadData().catch((loadError) => {
    // 仅在无缓存兜底时才展示错误，避免覆盖已渲染的缓存内容
    if (!hasCache) {
      error.value = `加载失败：${loadError?.message || '网络异常'}，请检查后重试`
      markNavigationUnavailable()
    }
  })
  // 加载惊喜提示（异步，不阻塞首页渲染）
  loadSurprise()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-sse-event', onSse)
  window.removeEventListener('xya-sse-status', onSseStatus)
  carouselImagePreloads.forEach((img) => {
    img.onload = null
    img.onerror = null
  })
  carouselImagePreloads.clear()
  if (autoTimer) clearInterval(autoTimer)
  if (surpriseHideTimer) clearTimeout(surpriseHideTimer)
  if (surpriseCountRaf) cancelAnimationFrame(surpriseCountRaf)
})
</script>

<style scoped>
.dashboard-page {
  max-width: 100%;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 316px;
  gap: 20px;
  align-items: start;
}

.dashboard-main {
  min-width: 0;
}

.dashboard-side {
  position: sticky;
  top: 88px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-section {
  margin-top: 18px;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 16px 40px rgba(32, 68, 132, 0.05);
}

.hero-card {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid rgba(190, 211, 247, 0.9);
  background: linear-gradient(180deg, #eff6ff 0%, #f7fbff 100%);
  box-shadow: 0 18px 48px rgba(41, 88, 171, 0.1);
  padding: 14px;
}

.hero-card::before {
  display: none;
}

.hero-card-tag {
  position: absolute;
  left: 24px;
  top: 16px;
  z-index: 5;
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #50617c;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(91, 119, 170, 0.12);
  backdrop-filter: blur(6px);
}

.hero-viewport {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  aspect-ratio: 2048 / 646;
}

.hero-unavailable {
  aspect-ratio: 2048 / 646;
  border-radius: 18px;
  border: 1px dashed #cdd9eb;
  background: linear-gradient(135deg, #f8fbff, #eef4fd);
  color: #66758d;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
}

.hero-unavailable strong {
  color: #33435d;
  font-size: 16px;
}

.hero-track {
  display: flex;
  height: 100%;
  transition: transform 0.55s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.hero-slide {
  min-width: 100%;
  position: relative;
  margin: 0;
  cursor: default;
}

.hero-slide.clickable {
  cursor: pointer;
}

.hero-banner {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  object-position: center;
}

.hero-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.96);
  color: #33435d;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12px 28px rgba(61, 95, 152, 0.14);
  z-index: 4;
}

.hero-arrow:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hero-arrow-left {
  left: 28px;
}

.hero-arrow-right {
  right: 28px;
}

.hero-dots {
  position: absolute;
  bottom: 26px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  z-index: 4;
}

.hero-dot {
  width: 8px;
  height: 8px;
  border: 0;
  border-radius: 999px;
  padding: 0;
  background: rgba(112, 143, 197, 0.32);
}

.hero-dot.active {
  width: 24px;
  background: #1c73ff;
}

.announcement-strip {
  margin-top: 20px;
  min-height: 86px;
  border-radius: 16px;
  border: 1px solid #f4d4a4;
  background: linear-gradient(90deg, #fff8ec 0%, #fffdf8 100%);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 20px;
  box-shadow: 0 10px 28px rgba(255, 176, 48, 0.06);
}

.announcement-icon {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: linear-gradient(135deg, #fff1cf 0%, #ffe7b6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.announcement-copy {
  flex: 1;
  min-width: 0;
}

.announcement-copy strong {
  display: block;
  color: #8c5a06;
  font-size: 15px;
}

.announcement-copy span {
  display: block;
  margin-top: 6px;
  color: #9c7221;
  font-size: 13px;
  line-height: 1.7;
  max-width: 760px;
}

.announcement-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.strip-btn {
  height: 38px;
  padding: 0 18px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 800;
  border: 1px solid transparent;
}

.strip-btn-ghost {
  background: #fff;
  color: #8b6116;
  border-color: #f0d2a1;
}

.strip-btn-primary {
  background: linear-gradient(90deg, #ff982a 0%, #ffb03a 100%);
  color: #fff;
}

.quick-start-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.quick-card,
.feature-card {
  min-height: 96px;
  border: 1px solid #edf2fb;
  border-radius: 18px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 16px;
  text-align: left;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.quick-card:hover,
.feature-card:hover {
  transform: translateY(-1px);
  border-color: #c9dcff;
  box-shadow: 0 14px 30px rgba(37, 106, 214, 0.08);
}

.quick-text,
.feature-text {
  min-width: 0;
  flex: 1;
}

.quick-text strong,
.feature-text strong {
  display: block;
  color: #16233d;
  font-size: 15px;
}

.quick-text span,
.feature-text span {
  display: block;
  margin-top: 4px;
  color: #7a8aa5;
  font-size: 12px;
  line-height: 1.65;
}

.feature-text em {
  display: block;
  margin-top: 6px;
  color: #0d6bff;
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
}

.quick-card .circle-ico,
.feature-card .circle-ico {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  font-size: 20px;
}

.card-arrow {
  color: #bdc9db;
  font-size: 20px;
  font-weight: 700;
}

.events-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 94px;
  color: #8ba0bf;
}

.events-empty p {
  margin: 0;
}

.events-box {
  border: 1px solid #eef3fb;
  border-radius: 14px;
  overflow: hidden;
}

.event-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) 120px;
  gap: 10px;
  align-items: center;
  min-height: 56px;
  padding: 0 18px;
  font-size: 13px;
}

.event-row + .event-row {
  border-top: 1px solid #f1f5fa;
}

.event-row strong {
  color: #314666;
}

.event-row span {
  color: #6e7f9b;
}

.event-row em {
  color: #9aa7bb;
  font-style: normal;
  text-align: right;
}

.side-panel {
  border-radius: 18px;
  padding: 20px 18px;
  box-shadow: 0 16px 40px rgba(32, 68, 132, 0.06);
}

.side-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: #2f74f6;
  font-size: 12px;
  font-weight: 700;
}

.guide-section h4 {
  margin: 0;
  color: #192742;
  font-size: 15px;
}

.guide-section p {
  margin: 10px 0 0;
  color: #6d7f9d;
  font-size: 13px;
  line-height: 1.75;
}

.guide-list {
  margin: 12px 0 0;
  padding: 0 0 0 18px;
  color: #536682;
}

.guide-list li + li {
  margin-top: 8px;
}

.guide-step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.guide-list strong {
  display: block;
  color: #1d2d4b;
}

.guide-list span {
  display: block;
  margin-top: 4px;
  color: #6d7f9d;
}

.guide-step-status {
  flex: 0 0 auto;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-style: normal;
  font-size: 11px;
  font-weight: 800;
}

.guide-step-status.done {
  background: #e9f8f1;
  color: #179866;
}

.guide-step-status.progress {
  background: #fff4e5;
  color: #d97706;
}

.guide-step-status.todo,
.guide-step-status.suggest {
  background: #edf4ff;
  color: #2767e7;
}

.guide-doc-link {
  margin-top: 12px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #0d6bff;
  font-size: 13px;
  font-weight: 800;
}

.guide-collapse-list {
  margin-top: 12px;
  border-top: 1px solid #eef2f8;
}

.guide-collapse-block + .guide-collapse-block {
  border-top: 1px solid #eef2f8;
}

.guide-collapse-item {
  width: 100%;
  min-height: 44px;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #2c3d59;
  font-size: 13px;
  font-weight: 700;
}

.collapse-chevron {
  color: #98a7bc;
  transition: transform .18s ease;
}

.collapse-chevron.open {
  transform: rotate(180deg);
}

.guide-collapse-panel {
  padding: 0 0 14px;
}

.guide-collapse-panel p {
  margin: 0;
  color: #6d7f9d;
  font-size: 12px;
  line-height: 1.8;
}

.guide-collapse-points {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #5b6d88;
  font-size: 12px;
  line-height: 1.75;
}

.guide-collapse-points li + li {
  margin-top: 6px;
}

.guide-inline-link {
  margin-top: 10px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #0d6bff;
  font-size: 12px;
  font-weight: 800;
}

.side-empty {
  padding: 12px 0;
  color: #93a2b7;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.side-empty strong {
  color: #445874;
}

.side-empty span {
  line-height: 1.7;
}

.side-list {
  display: flex;
  flex-direction: column;
}

.notice-item + .notice-item {
  border-top: 1px solid #eef2f8;
}

.notice-item {
  padding: 12px 0;
}

.notice-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.notice-head strong {
  color: #1c2a44;
  font-size: 13px;
}

.notice-head span {
  color: #99a8bd;
  font-size: 11px;
}

.notice-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.notice-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.notice-tag-system {
  background: #edf4ff;
  color: #2767e7;
}

.notice-tag-warning {
  background: #fff4e5;
  color: #d97706;
}

.notice-tag-info {
  background: #f3f6fb;
  color: #60718c;
}

.notice-state {
  color: #97a6bb;
  font-size: 11px;
  font-weight: 800;
}

.notice-state.unread {
  color: #f97316;
}

.notice-item p {
  margin: 6px 0 0;
  color: #6e809b;
  font-size: 12px;
  line-height: 1.7;
}

.status-list {
  display: flex;
  flex-direction: column;
}

.status-row {
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eef2f8;
}

.status-row span {
  color: #41516b;
  display: flex;
  align-items: center;
}

.status-row strong {
  color: #16a26d;
}

.status-row .status-ok-text {
  color: #16a26d;
}

.status-row .status-down-text {
  color: #ef4444;
}

.status-row .status-unknown-text {
  color: #8a97aa;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #19b16f;
  display: inline-block;
  margin-right: 8px;
}

.status-dot.status-down {
  background: #ef4444;
}

.status-dot.status-unknown {
  background: #a7b1c0;
}

.status-footer {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #93a2b7;
}

.status-success {
  color: #17a36b;
}

.status-error {
  color: #ef4444;
}

.status-unknown {
  color: #8a97aa;
}

.announcement-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1002;
  background: rgba(18, 31, 52, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.announcement-modal {
  position: relative;
  width: min(100%, 420px);
  min-height: 304px;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 28px 80px rgba(35, 61, 109, 0.22);
  padding: 34px 28px 24px;
  text-align: center;
}

.announcement-modal-close {
  position: absolute;
  right: 18px;
  top: 16px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #657892;
  font-size: 22px;
}

.announcement-modal-icon {
  width: 74px;
  height: 74px;
  margin: 4px auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #edf5ff 0%, #dcebff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
}

.announcement-modal h3 {
  margin: 0;
  color: #17315c;
  font-size: 20px;
}

.announcement-modal p {
  margin: 18px 0 0;
  color: #5f7089;
  font-size: 14px;
  line-height: 1.9;
  white-space: pre-wrap;
}

.announcement-modal-actions {
  margin-top: 22px;
  display: flex;
  justify-content: center;
  gap: 12px;
}

.modal-btn {
  min-width: 130px;
}

/* 中等屏幕宽度下功能特性 4 列卡片文字过窄导致溢出，降到 3 列保证可读 */
@media (max-width: 1640px) {
  .feature-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1500px) {
  .quick-start-grid,
  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-side {
    position: static;
  }
}

@media (max-width: 900px) {
  .hero-viewport {
    aspect-ratio: 4 / 3;
  }

  .quick-start-grid,
  .feature-grid {
    grid-template-columns: 1fr;
  }

  .event-row {
    grid-template-columns: 1fr;
    padding: 14px 18px;
  }

  .event-row em {
    text-align: left;
  }

  .announcement-strip {
    flex-wrap: wrap;
    padding: 16px;
  }
}
</style>

<!-- 惊喜弹窗样式（非 scoped，因为弹窗通过 Teleport 挂载到 body） -->
<style>
.surprise-toast {
  position: fixed;
  top: 100px;
  right: 28px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 320px;
  max-width: 380px;
  padding: 20px 24px;
  border-radius: 18px;
  color: #fff;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
  box-shadow:
    0 16px 48px -12px rgba(139, 92, 246, 0.55),
    0 4px 16px rgba(99, 102, 241, 0.3);
  overflow: hidden;
}

.surprise-toast-glow {
  position: absolute;
  top: -50%;
  right: -10%;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.18), transparent 70%);
  pointer-events: none;
}

.surprise-toast-icon {
  position: relative;
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  animation: surprise-icon-bounce 1.8s ease-in-out infinite;
}

@keyframes surprise-icon-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.surprise-toast-body {
  position: relative;
  flex: 1;
  min-width: 0;
}

.surprise-toast-title {
  font-size: 13px;
  opacity: 0.9;
  margin-bottom: 2px;
  letter-spacing: 0.3px;
}

.surprise-toast-stats {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.4;
  margin-bottom: 4px;
}

.surprise-toast-num {
  display: inline-block;
  font-size: 36px;
  font-weight: 800;
  margin: 0 4px;
  vertical-align: -5px;
  line-height: 1;
  background: linear-gradient(180deg, #ffffff 0%, #fef3c7 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 2px 8px rgba(255, 255, 255, 0.5));
  font-variant-numeric: tabular-nums;
}

.surprise-toast-meta {
  font-size: 12px;
  opacity: 0.82;
}

/* 右侧滑入/滑出动画 */
.surprise-slide-enter-active {
  transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.4s ease;
}

.surprise-slide-leave-active {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.6, 1), opacity 0.3s ease;
}

.surprise-slide-enter-from {
  transform: translateX(120%);
  opacity: 0;
}

.surprise-slide-leave-to {
  transform: translateX(120%);
  opacity: 0;
}

@media (max-width: 768px) {
  .surprise-toast {
    top: auto;
    bottom: 24px;
    right: 16px;
    left: 16px;
    max-width: none;
    min-width: 0;
    padding: 16px 18px;
    gap: 12px;
  }
  .surprise-toast-icon {
    width: 42px;
    height: 42px;
    font-size: 22px;
  }
  .surprise-toast-stats {
    font-size: 14px;
  }
  .surprise-toast-num {
    font-size: 28px;
  }
}
</style>
