import request from '../utils/request'
import { pageParams } from '../utils/apiData.js'

export function getGoods(params = {}) {
  const p = pageParams(params)
  if (p.xianyuAccountId && !p.accountId) p.accountId = p.xianyuAccountId
  return request({ url: '/goods', method: 'get', params: p })
}

export function getGoodsStats(params = {}) {
  const p = { ...params }
  if (p.xianyuAccountId && !p.accountId) p.accountId = p.xianyuAccountId
  return request({ url: '/goods/stats', method: 'get', params: p })
}

export function createGoods(data) {
  return request({ url: '/goods', method: 'post', data })
}

/**
 * 本地商品记录暂存键：商品已发布到闲鱼但本地保存失败时，暂存到 localStorage，
 * 进入商品管理页面时自动补建本地记录。
 */
const LS_PENDING_LOCAL_GOODS = 'xianyu_pending_local_goods'

/**
 * 判断错误是否可重试（503 服务不可用、网络错误、超时）
 */
function isRetryableError(err) {
  const code = err?.code
  const msg = (err?.message || err?.msg || '').toString()
  // 503 DataAccessException / 网络错误 / 超时
  if (code === 503 || code === 'ECONNABORTED' || code === 'ERR_NETWORK') return true
  if (/503|service unavailable|数据服务暂时不可用|timeout|超时|network|网络/i.test(msg)) return true
  return false
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

/**
 * 带重试的 createGoods：对 503/网络错误自动重试 3 次（间隔 1s/2s/4s）。
 * 重试仍失败时，将商品信息暂存到 localStorage，等进入商品管理页面时自动补建。
 *
 * @param {object} data - createGoods 入参（含 externalGoodsId、accountId 等）
 * @param {object} [opts] - { maxRetries=3, onRetry }
 * @returns {Promise<void>} 成功时 resolve，最终失败时 reject（调用方应捕获并提示用户）
 */
export async function createGoodsWithRetry(data, opts = {}) {
  const maxRetries = opts.maxRetries ?? 3
  const delays = [1000, 2000, 4000]
  let lastErr
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await createGoods(data)
    } catch (err) {
      lastErr = err
      if (attempt === maxRetries || !isRetryableError(err)) {
        throw err
      }
      if (typeof opts.onRetry === 'function') {
        try { opts.onRetry(attempt + 1, maxRetries, err) } catch { /* ignore */ }
      }
      await sleep(delays[attempt] || delays[delays.length - 1])
    }
  }
  throw lastErr
}

/**
 * 将发布成功但本地保存失败的商品信息暂存到 localStorage。
 * 进入商品管理页面时会调用 flushPendingLocalGoods 自动补建。
 * @param {object} data - createGoods 入参
 */
export function stashPendingLocalGoods(data) {
  try {
    const list = JSON.parse(localStorage.getItem(LS_PENDING_LOCAL_GOODS) || '[]')
    // 去重：同账号同 externalGoodsId 只保留最新一条
    const filtered = list.filter(g =>
      !(Number(g.accountId) === Number(data.accountId)
        && String(g.externalGoodsId) === String(data.externalGoodsId)))
    filtered.push({ ...data, stashedAt: Date.now() })
    // 最多暂存 50 条，避免无限增长
    const trimmed = filtered.slice(-50)
    localStorage.setItem(LS_PENDING_LOCAL_GOODS, JSON.stringify(trimmed))
  } catch { /* localStorage 不可用时忽略 */ }
}

/**
 * 取出并清空所有暂存的待补建本地商品记录。
 * @returns {Array<object>} 待补建的商品列表
 */
export function consumePendingLocalGoods() {
  try {
    const list = JSON.parse(localStorage.getItem(LS_PENDING_LOCAL_GOODS) || '[]')
    if (list.length === 0) return []
    localStorage.removeItem(LS_PENDING_LOCAL_GOODS)
    return list
  } catch {
    return []
  }
}

/**
 * 查询当前是否有待补建的本地商品记录（不消费）。
 * @returns {number} 待补建数量
 */
export function peekPendingLocalGoodsCount() {
  try {
    const list = JSON.parse(localStorage.getItem(LS_PENDING_LOCAL_GOODS) || '[]')
    return Array.isArray(list) ? list.length : 0
  } catch {
    return 0
  }
}

export function getGoodsDetail(id, params) {
  return request({ url: `/goods/${id}`, method: 'get', params })
}

export function updateGoods(id, data) {
  return request({ url: `/goods/${id}`, method: 'put', data })
}

export function deleteGoods(id) {
  return deleteGoodsLocal(id)
}

export function deleteGoodsLocal(id) {
  return request({ url: `/goods/${id}/local`, method: 'delete' })
}

export function deleteGoodsRemote(id, data = {}) {
  return request({ url: `/goods/${id}/remote`, method: 'delete', data })
}

/**
 * 更新售整自动上架开关（Java 直接修改本地 DB，速度快）。
 * 与 /item/auto-relist/toggle（Python 链路）互补，前端默认走此接口。
 * @param {number} id 商品主键 ID（xianyu_goods.id，非 external_goods_id）
 * @param {boolean} enabled 是否开启
 */
export function updateGoodsAutoRelist(id, enabled) {
  return request({ url: `/goods/${id}/auto-relist`, method: 'put', data: { enabled } })
}
