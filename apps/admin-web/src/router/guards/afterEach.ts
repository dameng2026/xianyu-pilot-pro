import { nextTick } from 'vue'
import { useSettingStore } from '@/store/modules/setting'
import { Router } from 'vue-router'
import NProgress from 'nprogress'
import { useCommon } from '@/hooks/core/useCommon'
import { loadingService } from '@/utils/ui'
import { getPendingLoading, resetPendingLoading } from './beforeEach'

function forceCleanupStuckMasks() {
  try {
    document
      .querySelectorAll<HTMLElement>('.el-loading-mask, .art-loading-fix')
      .forEach((mask) => mask.remove())

    const hasVisibleOverlay = document.querySelector(
      '.el-overlay .el-dialog:not([style*="display: none"]), ' +
      '.el-overlay .el-message-box, ' +
      '.el-overlay .el-drawer'
    )
    if (!hasVisibleOverlay) {
      document.querySelectorAll<HTMLElement>('.v-modal').forEach((m) => m.remove())
      document
        .querySelectorAll<HTMLElement>('.el-overlay')
        .forEach((o) => {
          if (
            !o.querySelector('.el-dialog, .el-message-box, .el-drawer, .el-message, .el-notification')
          ) {
            o.remove()
          }
        })
    }

    document.body.classList.remove('el-loading-parent--hidden', 'el-popup-parent--hidden')
    document.body.style.overflow = ''
  } catch {
    // ignore cleanup errors
  }
}

export function setupAfterEachGuard(router: Router) {
  const { scrollToTop } = useCommon()

  router.afterEach(() => {
    scrollToTop()

    const settingStore = useSettingStore()
    if (settingStore.showNprogress) {
      NProgress.done()
      setTimeout(() => {
        NProgress.remove()
      }, 100)
    }

    if (getPendingLoading()) {
      nextTick(() => {
        loadingService.hideLoading()
        resetPendingLoading()
        setTimeout(forceCleanupStuckMasks, 100)
      })
    } else {
      nextTick(() => {
        setTimeout(forceCleanupStuckMasks, 100)
      })
    }
  })
}
