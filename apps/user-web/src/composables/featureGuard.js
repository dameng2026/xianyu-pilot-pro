import { reactive, readonly, computed } from 'vue'
import { globalConfirm } from './confirmState.js'

// 全局限制模式状态
// 两种"可进入但不可操作"的模式：
//   1. browseMode（等级不足，reason=level）：用户等级不够，可浏览但不可写
//   2. previewMode（管理员预览限制，limitMode=preview）：管理员主动设置为预览模式，可查看但不可执行业务操作
// 两者互斥：同一时间只允许一种模式生效（由 App.vue 路由守卫切换页面时控制）
const state = reactive({
  // 浏览模式信息：{ featureKey, requiredLevel, reasonText }
  // 为 null 表示当前页面不在浏览模式
  browseMode: null,
  // 预览模式信息：{ featureKey, reasonText }
  // 为 null 表示当前页面不在预览模式
  previewMode: null
})

// 防止并发弹窗（限制模式下多个写请求同时被拦截时，只弹一次）
let noticeInFlight = false

/**
 * 设置浏览模式（由 App.vue 路由守卫在 reason === 'level' 时调用）
 * 设置时会清除 previewMode（两者互斥）
 * @param {Object} blockInfo - { featureKey, requiredLevel, reasonText }
 */
export function setBrowseMode(blockInfo) {
  state.previewMode = null
  state.browseMode = blockInfo ? { ...blockInfo } : null
}

/**
 * 清除浏览模式（由 App.vue 路由守卫在离开浏览模式页面时调用）
 */
export function clearBrowseMode() {
  state.browseMode = null
}

/**
 * 获取当前浏览模式信息（供 request.js 等非组件环境使用）
 * @returns {Object|null}
 */
export function getBrowseMode() {
  return state.browseMode
}

/**
 * 是否处于浏览模式（等级不足，可浏览不可用功能）
 * @returns {boolean}
 */
export function isInBrowseMode() {
  return state.browseMode !== null
}

/**
 * 设置预览模式（由 App.vue 路由守卫在 limitMode === 'preview' 时调用）
 * 设置时会清除 browseMode（两者互斥）
 * @param {Object} previewInfo - { featureKey, reasonText }
 */
export function setPreviewMode(previewInfo) {
  state.browseMode = null
  state.previewMode = previewInfo ? { ...previewInfo } : null
}

/**
 * 清除预览模式（由 App.vue 路由守卫在离开预览模式页面时调用）
 */
export function clearPreviewMode() {
  state.previewMode = null
}

/**
 * 获取当前预览模式信息（供 request.js 等非组件环境使用）
 * @returns {Object|null}
 */
export function getPreviewMode() {
  return state.previewMode
}

/**
 * 是否处于预览模式（管理员限制，可查看不可操作）
 * @returns {boolean}
 */
export function isInPreviewMode() {
  return state.previewMode !== null
}

/**
 * 清除所有限制模式（供 App.vue 路由守卫在放行进入页面时调用）
 */
export function clearAllLimitModes() {
  state.browseMode = null
  state.previewMode = null
}

/**
 * 弹窗提示等级不足（浏览模式下被拦截时调用）
 * 通过事件通知 App.vue 跳转会员中心，避免直接耦合 navigate 函数。
 * @param {Object} blockInfo - { requiredLevel, reasonText }
 */
async function showLevelBlockedNotice(blockInfo) {
  if (!blockInfo || noticeInFlight) return
  noticeInFlight = true
  try {
    const level = blockInfo.requiredLevel || ''
    const levelLabel = level === 'svp' ? 'SVP'
      : level === 'svip' ? 'SVIP'
      : level === 'vip' ? 'VIP'
      : (level || 'VIP')
    const reasonText = blockInfo.reasonText || `该功能需要 ${levelLabel} 等级才能使用`
    const confirmed = await globalConfirm.confirm(
      '等级不足',
      `${reasonText}\n\n是否前往会员中心升级？`,
      '立即升级'
    )
    if (confirmed) {
      // 通过事件通知 App.vue 跳转会员中心
      window.dispatchEvent(new CustomEvent('xya-navigate', { detail: 'vip' }))
    }
  } finally {
    noticeInFlight = false
  }
}

/**
 * 弹窗提示预览模式限制（预览模式下被拦截时调用）
 * @param {Object} previewInfo - { reasonText }
 */
async function showPreviewBlockedNotice(previewInfo) {
  if (!previewInfo || noticeInFlight) return
  noticeInFlight = true
  try {
    const reasonText = previewInfo.reasonText || '该功能当前为预览模式，可查看内容但不可执行业务操作'
    await globalConfirm.alert('预览模式', reasonText)
  } finally {
    noticeInFlight = false
  }
}

/**
 * 功能操作守卫：在核心业务按钮点击 / 纯前端交互前调用。
 * - 浏览模式（等级不足）：弹窗提示等级不足，返回 false
 * - 预览模式（管理员限制）：弹窗提示预览模式限制，返回 false
 * - 正常模式：返回 true
 *
 * 用法：
 *   async function handlePublish() {
 *     if (!await guardFeatureAction()) return
 *     // ... 执行发布逻辑
 *   }
 *
 * @returns {Promise<boolean>}
 */
export async function guardFeatureAction() {
  if (state.browseMode) {
    await showLevelBlockedNotice(state.browseMode)
    return false
  }
  if (state.previewMode) {
    await showPreviewBlockedNotice(state.previewMode)
    return false
  }
  return true
}

/**
 * 通知用户等级不足（供 request.js 等非组件环境调用）。
 * 内部有防并发机制，多次调用只弹一次窗。
 * 返回 Promise，弹窗关闭后 resolve。
 *
 * @returns {Promise<void>}
 */
export async function notifyLevelBlocked() {
  if (!state.browseMode || noticeInFlight) return
  await showLevelBlockedNotice(state.browseMode)
}

/**
 * 通知用户预览模式限制（供 request.js 等非组件环境调用）。
 * 内部有防并发机制，多次调用只弹一次窗。
 * 返回 Promise，弹窗关闭后 resolve。
 *
 * @returns {Promise<void>}
 */
export async function notifyPreviewBlocked() {
  if (!state.previewMode || noticeInFlight) return
  await showPreviewBlockedNotice(state.previewMode)
}

/**
 * useFeatureGuard composable（供 Vue 组件使用）
 * 返回响应式状态与 guardAction 方法。
 */
export function useFeatureGuard() {
  return {
    // 当前是否处于浏览模式（响应式）
    isBrowseMode: computed(() => state.browseMode !== null),
    // 浏览模式信息（只读）
    browseMode: readonly(computed(() => state.browseMode)),
    // 当前是否处于预览模式（响应式）
    isPreviewMode: computed(() => state.previewMode !== null),
    // 预览模式信息（只读）
    previewMode: readonly(computed(() => state.previewMode)),
    // 当前是否处于任何限制模式（浏览或预览）
    isLimited: computed(() => state.browseMode !== null || state.previewMode !== null),
    // 功能操作守卫
    guardAction: guardFeatureAction
  }
}
