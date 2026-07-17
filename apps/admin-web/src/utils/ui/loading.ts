/**
 * 全局 Loading 加载管理模块
 *
 * 提供统一的全屏加载动画管理
 *
 * ## 主要功能
 *
 * - 全屏 Loading 显示和隐藏
 * - 自动适配明暗主题背景色
 * - 自定义 SVG 加载动画
 * - 单例模式防止重复创建
 * - 锁定页面交互
 * - DOM 级强制清理，防止遮罩残留
 *
 * @module utils/ui/loading
 */
import { ElLoading } from 'element-plus'
import { fourDotsSpinnerSvg } from '@/assets/svg/loading'

const LOADING_CUSTOM_CLASS = 'art-loading-fix'

const getLoadingBackground = (): string => {
  const isDark = document.documentElement.classList.contains('dark')
  return isDark ? 'rgba(7, 7, 7, 0.85)' : '#fff'
}

const DEFAULT_LOADING_CONFIG = {
  lock: true,
  background: '#fff',
  svg: fourDotsSpinnerSvg,
  svgViewBox: '0 0 40 40',
  customClass: LOADING_CUSTOM_CLASS
} as const

interface LoadingInstance {
  close: () => void
}

let loadingInstance: LoadingInstance | null = null

function forceCleanupLoadingDom(): void {
  try {
    const customMasks = document.querySelectorAll<HTMLElement>(`.${LOADING_CUSTOM_CLASS}`)
    customMasks.forEach((mask) => mask.remove())

    document.body.querySelectorAll<HTMLElement>('.el-loading-mask').forEach((mask) => {
      const style = getComputedStyle(mask)
      if (style.position === 'fixed' && mask.parentElement === document.body) {
        mask.remove()
      }
    })

    document.body.classList.remove('el-loading-parent--hidden')
    document.body.classList.remove('el-popup-parent--hidden')
    document.body.style.overflow = ''
  } catch {}
}

export const loadingService = {
  showLoading(): () => void {
    if (!loadingInstance) {
      const config = {
        ...DEFAULT_LOADING_CONFIG,
        background: getLoadingBackground()
      }
      try {
        loadingInstance = ElLoading.service(config)
      } catch {
        forceCleanupLoadingDom()
        try {
          loadingInstance = ElLoading.service(config)
        } catch {
          loadingInstance = null
        }
      }
    }
    return () => this.hideLoading()
  },

  hideLoading(): void {
    if (loadingInstance) {
      try {
        loadingInstance.close()
      } catch {
        // close may throw if already closed; fall through to DOM cleanup
      }
      loadingInstance = null
    }
    forceCleanupLoadingDom()
  }
}
