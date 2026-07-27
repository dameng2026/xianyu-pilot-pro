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
