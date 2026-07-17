<template>
  <ElConfigProvider
    size="default"
    :locale="locales[language]"
    :z-index="3000"
    :card="{
      shadow: 'never'
    }"
  >
    <RouterView></RouterView>
  </ElConfigProvider>
</template>

<script setup lang="ts">
  import { useUserStore } from './store/modules/user'
  import zh from 'element-plus/es/locale/lang/zh-cn'
  import en from 'element-plus/es/locale/lang/en'
  import { systemUpgrade } from './utils/sys'
  import { toggleTransition } from './utils/ui/animation'
  import { checkStorageCompatibility } from './utils/storage'
  import { initializeTheme } from './hooks/core/useTheme'
  import { createAdminMediaSession } from './api/auth'

  const userStore = useUserStore()
  const { language } = storeToRefs(userStore)

  const locales = {
    zh: zh,
    en: en
  }

  let mediaSessionTimer: ReturnType<typeof setTimeout> | null = null
  let mediaSessionWarningShown = false

  const clearMediaSessionTimer = () => {
    if (mediaSessionTimer) clearTimeout(mediaSessionTimer)
    mediaSessionTimer = null
  }

  const refreshMediaSession = async () => {
    clearMediaSessionTimer()
    if (!userStore.accessToken || !userStore.isLogin) return
    try {
      await createAdminMediaSession()
      mediaSessionWarningShown = false
      mediaSessionTimer = setTimeout(refreshMediaSession, 10 * 60 * 1000)
    } catch {
      if (!mediaSessionWarningShown) {
        mediaSessionWarningShown = true
        ElMessage.warning('私有媒体会话暂不可用，头像和私有图片预览可能无法显示')
      }
      // Keep the shell usable and retry quietly while the media boundary recovers.
      mediaSessionTimer = setTimeout(refreshMediaSession, 60 * 1000)
    }
  }

  watch(
    () => [userStore.accessToken, userStore.isLogin] as const,
    ([token, isLogin]) => {
      clearMediaSessionTimer()
      if (!token || !isLogin) {
        mediaSessionWarningShown = false
        return
      }
      // A fresh login has already established the cookie synchronously. Schedule
      // the next renewal instead of racing the login request with a duplicate POST.
      mediaSessionTimer = setTimeout(refreshMediaSession, 10 * 60 * 1000)
    },
    { flush: 'post' }
  )

  // A restored tab may have a token in sessionStorage but no surviving cookie.
  // Re-establish the path-scoped media session before the user opens private media.
  if (userStore.accessToken && userStore.isLogin) {
    void refreshMediaSession()
  }

  onBeforeMount(() => {
    toggleTransition(true)
    initializeTheme()
    forceCleanupOrphanMasks()
  })

  onMounted(() => {
    checkStorageCompatibility()
    toggleTransition(false)
    systemUpgrade()
    startMaskGuard()
  })

  onBeforeUnmount(() => {
    clearMediaSessionTimer()
    stopMaskGuard()
  })

  function forceCleanupOrphanMasks() {
    try {
      document.querySelectorAll<HTMLElement>('.el-loading-mask, .art-loading-fix').forEach((el) => el.remove())
      document.body.classList.remove(
        'el-loading-parent--hidden',
        'el-popup-parent--hidden'
      )
      document.body.style.overflow = ''
    } catch {}
  }

  let maskObserver: MutationObserver | null = null
  let maskCleanupTimer: ReturnType<typeof setTimeout> | null = null
  let startupSafetyInterval: ReturnType<typeof setInterval> | null = null

  function startMaskGuard() {
    forceCleanupOrphanMasks()

    if (maskObserver) return
    maskObserver = new MutationObserver(() => {
      if (maskCleanupTimer) return
      maskCleanupTimer = setTimeout(() => {
        maskCleanupTimer = null
        cleanupOrphanMasksDeferred()
      }, 500)
    })
    maskObserver.observe(document.body, { childList: true, subtree: false })

    startupSafetyInterval = setInterval(() => {
      cleanupOrphanMasksDeferred()
    }, 1000)
    setTimeout(() => {
      if (startupSafetyInterval) {
        clearInterval(startupSafetyInterval)
        startupSafetyInterval = null
      }
      cleanupOrphanMasksDeferred()
    }, 10000)
  }

  function stopMaskGuard() {
    if (maskObserver) {
      maskObserver.disconnect()
      maskObserver = null
    }
    if (maskCleanupTimer) {
      clearTimeout(maskCleanupTimer)
      maskCleanupTimer = null
    }
    if (startupSafetyInterval) {
      clearInterval(startupSafetyInterval)
      startupSafetyInterval = null
    }
  }

  function cleanupOrphanMasksDeferred() {
    try {
      const loadingMasks = document.querySelectorAll<HTMLElement>('.el-loading-mask, .art-loading-fix')
      if (loadingMasks.length > 0) {
        loadingMasks.forEach((m) => m.remove())
        document.body.classList.remove('el-loading-parent--hidden', 'el-popup-parent--hidden')
      }

      const overlays = document.querySelectorAll<HTMLElement>('.el-overlay')
      overlays.forEach((el) => {
        const hasVisibleContent = el.querySelector(
          '.el-dialog, .el-message-box, .el-drawer, .el-message, .el-notification'
        )
        if (!hasVisibleContent) {
          el.remove()
        }
      })

      const modals = document.querySelectorAll<HTMLElement>('.v-modal')
      const hasLegitModal = document.querySelector('.el-overlay .el-dialog, .el-overlay .el-message-box, .el-overlay .el-drawer')
      if (!hasLegitModal && modals.length > 0) {
        modals.forEach((m) => m.remove())
      }
    } catch {}
  }
</script>
