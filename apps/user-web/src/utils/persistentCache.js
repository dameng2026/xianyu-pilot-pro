/**
 * 持久化缓存工具 - 基于 localStorage 的 stale-while-revalidate 缓存
 *
 * 用途：让页面进入时立即从本地缓存渲染，同时在后台异步刷新数据，
 * 避免每次进入页面都等待几秒钟的网络请求。
 *
 * 缓存策略：
 * - freshMs：缓存新鲜期，此期间直接返回缓存，不发请求
 * - staleMs：缓存可过期使用期，此期间先返回缓存（标记 stale），后台异步刷新
 * - 超过 staleMs：缓存失效，必须等待网络请求
 */

const STORAGE_PREFIX = 'xya_cache:'

function isStorageAvailable(storage) {
  try {
    const testKey = '__xya_cache_test__'
    storage.setItem(testKey, '1')
    storage.removeItem(testKey)
    return true
  } catch {
    return false
  }
}

const localStorageAvailable = typeof window !== 'undefined' && isStorageAvailable(window.localStorage)

function buildKey(namespace) {
  return STORAGE_PREFIX + namespace
}

/**
 * 读取持久化缓存
 * @param {string} namespace 缓存命名空间
 * @returns {{ value: any, savedAt: number } | null}
 */
export function readPersistentCache(namespace) {
  if (!localStorageAvailable) return null
  try {
    const raw = window.localStorage.getItem(buildKey(namespace))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed.savedAt !== 'number') return null
    return parsed
  } catch {
    return null
  }
}

/**
 * 写入持久化缓存
 * @param {string} namespace 缓存命名空间
 * @param {any} value 缓存值
 */
export function writePersistentCache(namespace, value) {
  if (!localStorageAvailable) return
  try {
    const payload = JSON.stringify({ value, savedAt: Date.now() })
    window.localStorage.setItem(buildKey(namespace), payload)
  } catch {
    // 配额不足或序列化失败时静默忽略
  }
}

/**
 * 清除指定命名空间的持久化缓存
 * @param {string} namespace 缓存命名空间
 */
export function clearPersistentCache(namespace) {
  if (!localStorageAvailable) return
  try {
    window.localStorage.removeItem(buildKey(namespace))
  } catch {
    // 忽略
  }
}

/**
 * stale-while-revalidate 模式的持久化缓存请求
 *
 * @param {Object} options
 * @param {string} options.namespace 缓存命名空间（需唯一）
 * @param {Function} options.request 返回 Promise 的请求函数
 * @param {number} [options.freshMs=60000] 缓存新鲜期（毫秒），此期间不发请求
 * @param {number} [options.staleMs=300000] 缓存可过期使用期（毫秒），此期间先返回缓存再后台刷新
 * @returns {Promise<{ data: any, stale: boolean, fromCache: boolean }>}
 */
export function withPersistentCache({
  namespace,
  request,
  freshMs = 60_000,
  staleMs = 300_000,
}) {
  const now = Date.now()
  const cached = readPersistentCache(namespace)

  // 情况1：缓存仍在新鲜期，直接返回缓存
  if (cached && (now - cached.savedAt) < freshMs) {
    return Promise.resolve({
      data: cached.value,
      stale: false,
      fromCache: true,
    })
  }

  // 情况2：缓存已过期但在可使用期，先返回缓存（标记 stale），后台刷新
  if (cached && (now - cached.savedAt) < staleMs) {
    // 后台刷新，不阻塞当前渲染
    request()
      .then((value) => {
        writePersistentCache(namespace, value)
      })
      .catch(() => {
        // 后台刷新失败时保留旧缓存，下次再试
      })
    return Promise.resolve({
      data: cached.value,
      stale: true,
      fromCache: true,
    })
  }

  // 情况3：无缓存或缓存已失效，必须等待网络请求
  return Promise.resolve()
    .then(request)
    .then((value) => {
      writePersistentCache(namespace, value)
      return { data: value, stale: false, fromCache: false }
    })
}
