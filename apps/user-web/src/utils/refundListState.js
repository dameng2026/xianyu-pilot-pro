/**
 * 退款列表筛选状态保存/恢复（需求第三节：返回列表时恢复筛选与页码）。
 *
 * 用途：从退款列表"查看详情"进入退款详情页，返回时恢复：
 * - 账号筛选（selectedAccountId）
 * - 退款分类（category）
 * - 页码（page）/ 每页条数（pageSize）
 * - 滚动位置（scrollTop）
 *
 * 实现策略：使用 sessionStorage 短时保存（关闭标签页自动清理），
 * 避免长期保留陈旧状态；同时提供 in-memory 兜底，防止 sessionStorage 不可用。
 *
 * 不保存：完整列表数据（仍走后端缓存）、敏感字段。
 */

const STORAGE_KEY = 'xya_refund_list_state_v1'
const MAX_SCROLL = Number.MAX_SAFE_INTEGER

// 内存兜底（sessionStorage 不可用时使用）
let memoryState = null

function getStorage() {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) return null
    return window.sessionStorage
  } catch {
    return null
  }
}

/**
 * 保存退款列表筛选状态。
 *
 * @param {Object} state
 * @param {string} state.selectedAccountId  选中的账号ID（'' 表示全部账号）
 * @param {string} state.category           退款分类（all/unshipped/shipped/return/freight）
 * @param {number} state.page               当前页码
 * @param {number} state.pageSize           每页条数
 * @param {number} [state.scrollTop]        列表滚动位置（用于恢复视图）
 * @param {string} [state.savedAt]          保存时间（ISO 字符串）
 */
export function saveRefundListState(state = {}) {
  const data = {
    selectedAccountId: typeof state.selectedAccountId === 'string' ? state.selectedAccountId : '',
    category: typeof state.category === 'string' ? state.category : 'all',
    page: Number.isFinite(state.page) && state.page > 0 ? Math.floor(state.page) : 1,
    pageSize: Number.isFinite(state.pageSize) && state.pageSize > 0 ? Math.floor(state.pageSize) : 20,
    scrollTop: Number.isFinite(state.scrollTop) && state.scrollTop >= 0
      ? Math.min(Math.floor(state.scrollTop), MAX_SCROLL)
      : 0,
    savedAt: new Date().toISOString(),
  }
  memoryState = data
  const storage = getStorage()
  if (storage) {
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {
      // 配额超限或被禁用：仅使用内存兜底
    }
  }
}

/**
 * 读取并清除退款列表筛选状态。
 *
 * 调用后立即从 storage 中清除，避免重复恢复旧状态。
 * 同时返回内存兜底副本，确保即使 storage 不可用也能恢复。
 *
 * @returns {Object|null} 保存的状态，或 null（无可用状态）
 */
export function consumeRefundListState() {
  let data = null
  const storage = getStorage()
  if (storage) {
    try {
      const raw = storage.getItem(STORAGE_KEY)
      if (raw) {
        data = JSON.parse(raw)
        storage.removeItem(STORAGE_KEY)
      }
    } catch {
      // 解析失败：忽略并继续使用内存兜底
    }
  }
  if (!data) {
    data = memoryState
  }
  // 无论从 storage 还是 memory 读取，都同步清除内存兜底，
  // 避免"save 同时写入 storage+memory"后第二次 consume 拿到旧内存副本。
  memoryState = null
  if (!data || typeof data !== 'object') return null
  // 基础校验：至少包含 selectedAccountId 字段
  if (typeof data.selectedAccountId !== 'string') return null
  return {
    selectedAccountId: data.selectedAccountId,
    category: typeof data.category === 'string' ? data.category : 'all',
    page: Number.isFinite(data.page) && data.page > 0 ? Math.floor(data.page) : 1,
    pageSize: Number.isFinite(data.pageSize) && data.pageSize > 0 ? Math.floor(data.pageSize) : 20,
    scrollTop: Number.isFinite(data.scrollTop) && data.scrollTop >= 0 ? Math.floor(data.scrollTop) : 0,
    savedAt: typeof data.savedAt === 'string' ? data.savedAt : null,
  }
}

/**
 * 仅查看保存的状态（不消费）。
 * 用于详情页判断"是否有可返回的列表状态"。
 */
export function peekRefundListState() {
  const storage = getStorage()
  if (storage) {
    try {
      const raw = storage.getItem(STORAGE_KEY)
      if (raw) return JSON.parse(raw)
    } catch {
      // ignore
    }
  }
  return memoryState
}

/**
 * 清除保存的状态（如用户主动离开详情页时调用）。
 */
export function clearRefundListState() {
  memoryState = null
  const storage = getStorage()
  if (storage) {
    try {
      storage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }
}
