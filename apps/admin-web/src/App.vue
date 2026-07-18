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

  // 检查元素是否由 Vue 组件实例管理（ElDialog/ElDrawer 等通过 Teleport 挂到 body 的 overlay）
  // 这些元素由 Vue 持有引用并管理生命周期，即使内部暂时没有可见内容
  // （例如 dialogVisible=false 时 rendered=false，overlay 内部是注释节点），
  // 也绝不能被外部代码强制 remove，否则后续 v-model=true 时弹窗无法渲染到 DOM。
  function isVueManaged(el: HTMLElement | null): boolean {
    if (!el) return false
    let node: HTMLElement | null = el
    let depth = 0
    while (node && depth < 20) {
      // Vue 3 内部属性：组件挂载后会在 DOM 节点上设置 __vueParentComponent
      if ((node as any).__vueParentComponent) return true
      // Vue 应用根节点
      if ((node as any).__vue_app__) return true
      if (node === document.body) break
      node = node.parentElement
      depth++
    }
    return false
  }

  // Element Plus 通过 Teleport 挂到 body 的 overlay 会带有命名空间前缀的 modal class
  // （el-modal-dialog / el-modal-drawer 等）。这些是 Element Plus 公开样式约定，
  // 出现这些 class 说明 overlay 由 EP 组件管理，不应清理。
  function isElementPlusManagedOverlay(el: HTMLElement): boolean {
    const cls = el.className || ''
    if (typeof cls !== 'string') return false
    return /\bel-modal-(dialog|drawer|messagebox|popover|image|select|cascader|date|time|tooltip)\b/.test(cls)
  }

  function cleanupOrphanMasksDeferred() {
    try {
      const loadingMasks = document.querySelectorAll<HTMLElement>('.el-loading-mask, .art-loading-fix')
      if (loadingMasks.length > 0) {
        loadingMasks.forEach((m) => {
          if (isVueManaged(m)) return
          m.remove()
        })
        document.body.classList.remove('el-loading-parent--hidden', 'el-popup-parent--hidden')
      }

      const overlays = document.querySelectorAll<HTMLElement>('.el-overlay')
      overlays.forEach((el) => {
        // 关键修复：跳过 Vue / Element Plus 管理的 overlay
        const vueManaged = isVueManaged(el)
        const epManaged = isElementPlusManagedOverlay(el)
        if (vueManaged || epManaged) {
          return
        }

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
        modals.forEach((m) => {
          if (isVueManaged(m)) return
          m.remove()
        })
      }
    } catch {}
  }
</script>
