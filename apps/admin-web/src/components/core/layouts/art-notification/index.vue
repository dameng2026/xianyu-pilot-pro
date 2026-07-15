<!-- 通知组件 -->
<template>
  <div
    class="art-notification-panel art-card-sm !shadow-xl"
    :style="{
      transform: show ? 'scaleY(1)' : 'scaleY(0.9)',
      opacity: show ? 1 : 0
    }"
    v-show="visible"
    @click.stop
  >
    <div class="flex-cb px-3.5 mt-3.5">
      <span class="text-base font-medium text-g-800">{{ $t('notice.title') }}</span>
      <span
        class="text-xs text-g-800 px-1.5 py-1 c-p select-none rounded hover:bg-g-200"
        @click="markAllRead"
      >
        {{ $t('notice.btnRead') }}
      </span>
    </div>

    <ul class="box-border flex items-end w-full h-12.5 px-3.5 border-b-d">
      <li
        v-for="(item, index) in barList"
        :key="index"
        class="h-12 leading-12 mr-5 overflow-hidden text-[13px] text-g-700 c-p select-none"
        :class="{ 'bar-active': barActiveIndex === index }"
        @click="changeBar(index)"
      >
        {{ item.name }} ({{ item.num }})
      </li>
    </ul>

    <div class="w-full h-[calc(100%-95px)]">
      <div class="h-[calc(100%-60px)] overflow-y-scroll scrollbar-thin">
        <!-- 通知 -->
        <ul v-show="barActiveIndex === 0">
          <li
            v-for="(item, index) in noticeList"
            :key="index"
            class="box-border flex-c px-3.5 py-3.5 c-p last:border-b-0 hover:bg-g-200/60"
            :class="{ 'opacity-60': item.read }"
          >
            <div
              class="size-9 leading-9 text-center rounded-lg flex-cc"
              :class="[getNoticeStyle(item.type).iconClass]"
            >
              <ArtSvgIcon class="text-lg !bg-transparent" :icon="getNoticeStyle(item.type).icon" />
            </div>
            <div class="w-[calc(100%-45px)] ml-3.5 relative">
              <h4 class="text-sm font-normal leading-5.5 text-g-900">
                <span v-if="!item.read" class="inline-block size-1.5 rounded-full bg-red-500 mr-1.5 align-middle" />
                {{ item.title }}
              </h4>
              <p class="mt-1.5 text-xs text-g-500">{{ item.time }}</p>
            </div>
          </li>
        </ul>

        <!-- 消息 -->
        <ul v-show="barActiveIndex === 1">
          <li
            v-for="(item, index) in msgList"
            :key="index"
            class="box-border flex-c px-3.5 py-3.5 c-p last:border-b-0 hover:bg-g-200/60"
          >
            <div
              class="size-9 leading-9 text-center rounded-lg flex-cc"
              :class="item.success ? 'bg-success/12 text-success' : 'bg-danger/12 text-danger'"
            >
              <ArtSvgIcon
                class="text-lg !bg-transparent"
                :icon="item.success ? 'ri:check-double-line' : 'ri:error-warning-line'"
              />
            </div>
            <div class="w-[calc(100%-45px)] ml-3.5">
              <h4 class="text-xs font-normal leading-5.5 text-g-900">{{ item.title }}</h4>
              <p class="mt-1.5 text-xs text-g-500">{{ item.time }}</p>
            </div>
          </li>
        </ul>

        <!-- 待办 -->
        <ul v-show="barActiveIndex === 2">
          <li
            v-for="(item, index) in pendingList"
            :key="index"
            class="box-border px-5 py-3.5 last:border-b-0"
          >
            <h4>{{ item.title }}</h4>
            <p class="text-xs text-g-500">{{ item.time }}</p>
          </li>
        </ul>

        <!-- 空状态 -->
        <div
          v-show="currentTabIsEmpty"
          class="relative top-25 h-full text-g-500 text-center !bg-transparent"
        >
          <ArtSvgIcon icon="system-uicons:inbox" class="text-5xl" />
          <p class="mt-3.5 text-xs !bg-transparent"
            >{{ $t('notice.text[0]') }}{{ barList[barActiveIndex].name }}</p
          >
        </div>
      </div>

      <div class="relative box-border w-full px-3.5">
        <ElButton class="w-full mt-3" @click="handleViewAll" v-ripple>
          {{ $t('notice.viewAll') }}
        </ElButton>
      </div>
    </div>

    <div class="h-25"></div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch, onMounted } from 'vue'
  import type { ComputedRef } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { ElMessage } from 'element-plus'
  import { getRecentEvents, getPendingTasks, getReadNotificationIds, markAllNotificationsRead } from '@/api/admin'
  import { getNotificationDeliveryLogs } from '@/api/notification-logs'

  defineOptions({ name: 'ArtNotification' })

  interface NoticeItem {
    /** 事件 ID（用于已读状态持久化） */
    id?: number | string
    /** 标题 */
    title: string
    /** 时间 */
    time: string
    /** 类型 */
    type: NoticeType
    /** 是否已读 */
    read?: boolean
  }

  interface MessageItem {
    /** 标题 */
    title: string
    /** 时间 */
    time: string
    /** 是否成功 */
    success: boolean
  }

  interface PendingItem {
    /** 标题 */
    title: string
    /** 时间 */
    time: string
  }

  interface BarItem {
    /** 名称 */
    name: ComputedRef<string>
    /** 数量 */
    num: number
  }

  interface NoticeStyle {
    /** 图标 */
    icon: string
    /** icon 样式 */
    iconClass: string
  }

  type NoticeType = 'email' | 'message' | 'collection' | 'user' | 'notice'

  const { t } = useI18n()
  const router = useRouter()

  const props = defineProps<{
    value: boolean
  }>()

  const emit = defineEmits<{
    'update:value': [value: boolean]
  }>()

  const show = ref(false)
  const visible = ref(false)
  const barActiveIndex = ref(0)
  const loading = ref(false)

  const noticeList = ref<NoticeItem[]>([])
  const msgList = ref<MessageItem[]>([])
  const pendingList = ref<PendingItem[]>([])

  // 样式管理
  const useNotificationStyles = () => {
    const noticeStyleMap: Record<NoticeType, NoticeStyle> = {
      email: {
        icon: 'ri:mail-line',
        iconClass: 'bg-warning/12 text-warning'
      },
      message: {
        icon: 'ri:volume-down-line',
        iconClass: 'bg-success/12 text-success'
      },
      collection: {
        icon: 'ri:heart-3-line',
        iconClass: 'bg-danger/12 text-danger'
      },
      user: {
        icon: 'ri:user-line',
        iconClass: 'bg-info/12 text-info'
      },
      notice: {
        icon: 'ri:notification-3-line',
        iconClass: 'bg-theme/12 text-theme'
      }
    }

    const getNoticeStyle = (type: NoticeType): NoticeStyle => {
      const defaultStyle: NoticeStyle = {
        icon: 'ri:notification-3-line',
        iconClass: 'bg-theme/12 text-theme'
      }

      return noticeStyleMap[type] || defaultStyle
    }

    return {
      getNoticeStyle
    }
  }

  // 动画管理
  const useNotificationAnimation = () => {
    const showNotice = (open: boolean) => {
      if (open) {
        visible.value = true
        setTimeout(() => {
          show.value = true
        }, 5)
      } else {
        show.value = false
        setTimeout(() => {
          visible.value = false
        }, 350)
      }
    }

    return {
      showNotice
    }
  }

  // 标签页管理
  const useTabManagement = () => {
    const changeBar = (index: number) => {
      barActiveIndex.value = index
    }

    // 检查当前标签页是否为空
    const currentTabIsEmpty = computed(() => {
      const tabDataMap = [noticeList.value, msgList.value, pendingList.value]

      const currentData = tabDataMap[barActiveIndex.value]
      return currentData && currentData.length === 0
    })

    const handleViewAll = () => {
      const routeMap: Record<number, string> = {
        0: '/admin/risk-notify/notify-logs',
        1: '/admin/risk-notify/notify-logs',
        2: '/admin/dashboard/overview'
      }
      const target = routeMap[barActiveIndex.value]
      if (target) {
        emit('update:value', false)
        router.push(target)
        return
      }
      emit('update:value', false)
    }

    return {
      changeBar,
      currentTabIsEmpty,
      handleViewAll
    }
  }

  // 标签栏数据
  const barList = computed<BarItem[]>(() => [
    {
      name: computed(() => t('notice.bar[0]')),
      num: noticeList.value.length
    },
    {
      name: computed(() => t('notice.bar[1]')),
      num: msgList.value.length
    },
    {
      name: computed(() => t('notice.bar[2]')),
      num: pendingList.value.length
    }
  ])

  const { getNoticeStyle } = useNotificationStyles()
  const { showNotice } = useNotificationAnimation()
  const { changeBar, currentTabIsEmpty, handleViewAll } = useTabManagement()

  // 加载真实数据：最近后台操作事件
  async function loadNoticeList() {
    try {
      const [list, readIds] = await Promise.all([
        getRecentEvents(),
        getReadNotificationIds().catch(() => [])
      ])
      const events = Array.isArray(list) ? list : []
      const readSet = new Set((readIds || []).map(id => Number(id)))
      noticeList.value = events.slice(0, 20).map((e: any) => {
        const module = String(e?.module || '系统')
        const action = String(e?.action || '操作')
        const targetId = e?.targetId ? ` #${e.targetId}` : ''
        const resultText = String(e?.result || '') === '成功' ? '成功' : '失败'
        const id = e?.id
        return {
          id,
          title: `${module} · ${action}${targetId}（${resultText}）`,
          time: String(e?.time || ''),
          type: inferNoticeType(module),
          read: id != null && readSet.has(Number(id))
        } as NoticeItem
      })
    } catch {
      noticeList.value = []
    }
  }

  function inferNoticeType(module: string): NoticeType {
    const m = String(module || '').toLowerCase()
    if (m.includes('user') || m.includes('用户')) return 'user'
    if (m.includes('mail') || m.includes('邮件') || m.includes('email')) return 'email'
    if (m.includes('message') || m.includes('消息') || m.includes('notify') || m.includes('通知')) return 'message'
    if (m.includes('risk') || m.includes('风控') || m.includes('alert') || m.includes('告警')) return 'collection'
    return 'notice'
  }

  // 加载真实数据：最近通知发送记录
  async function loadMsgList() {
    try {
      const res = await getNotificationDeliveryLogs({ current: 1, size: 20 })
      const records = res?.records || []
      msgList.value = records.map((r) => {
        const channel = r.channelName || r.channelKey || '通知渠道'
        const event = r.eventType || '事件'
        const statusText = r.success ? '发送成功' : '发送失败'
        const msgSnippet = r.message ? `：${String(r.message).slice(0, 40)}` : ''
        return {
          title: `[${channel}] ${event} ${statusText}${msgSnippet}`,
          time: String(r.createdTime || ''),
          success: !!r.success
        } as MessageItem
      })
    } catch {
      msgList.value = []
    }
  }

  // 待办数据：聚合失败工作流、风控账号、通知失败、卡密低库存
  async function loadPendingList() {
    try {
      const list = await getPendingTasks()
      pendingList.value = (list || []).map(t => ({
        title: t.title,
        time: String(t.time || ''),
        type: 'notice'
      }))
    } catch {
      pendingList.value = []
    }
  }

  // 全部标为已读（持久化到 sys_notification_read 表）
  async function markAllRead() {
    try {
      const ids = noticeList.value
        .filter(n => n.id != null && !n.read)
        .map(n => n.id as number | string)
      if (ids.length === 0) {
        ElMessage.success('已全部标为已读')
        return
      }
      await markAllNotificationsRead(ids, 'recent_event')
      noticeList.value.forEach(n => { if (n.id != null) n.read = true })
      ElMessage.success('已全部标为已读')
    } catch {
      ElMessage.error('标记已读失败')
    }
  }

  async function loadAll() {
    if (loading.value) return
    loading.value = true
    try {
      await Promise.all([loadNoticeList(), loadMsgList(), Promise.resolve(loadPendingList())])
    } finally {
      loading.value = false
    }
  }

  // 监听属性变化
  watch(
    () => props.value,
    (newValue) => {
      showNotice(newValue)
      // 面板首次展开时刷新数据
      if (newValue) loadAll()
    }
  )

  onMounted(() => {
    // 静默预加载一次，让红点计数更准确
    loadAll().catch(() => {})
  })
</script>

<style scoped>
  @reference '@styles/core/tailwind.css';

  .art-notification-panel {
    @apply absolute 
    top-14.5 
    right-5 
    w-90 
    h-125 
    overflow-hidden 
    transition-all 
    duration-300
    origin-top 
    will-change-[top,left] 
    max-[640px]:top-[65px]
    max-[640px]:right-0
    max-[640px]:w-full 
    max-[640px]:h-[80vh];
  }

  .bar-active {
    color: var(--theme-color) !important;
    border-bottom: 2px solid var(--theme-color);
  }

  .scrollbar-thin::-webkit-scrollbar {
    width: 5px !important;
  }

  .dark .scrollbar-thin::-webkit-scrollbar-track {
    background-color: var(--default-box-color);
  }

  .dark .scrollbar-thin::-webkit-scrollbar-thumb {
    background-color: #222 !important;
  }
</style>
