import request from '@/utils/http'

// 审核工作台
export function getPendingAuditList(params: { page: number; size: number; moduleKey?: string }) {
  return request.get({ url: '/supply/audit/pending', params })
}

export function approveAudit(id: number, reason?: string) {
  return request.post({ url: `/supply/audit/${id}/approve`, data: { reason: reason || '' } })
}

export function rejectAudit(id: number, reason: string) {
  return request.post({ url: `/supply/audit/${id}/reject`, data: { reason } })
}

export function getAuditHistory(params: { page: number; size: number; moduleKey?: string; status?: string }) {
  return request.get({ url: '/supply/audit/history', params })
}

// 权重调整
export function updateProductWeight(data: { source: string; id: number; weight: number }) {
  return request.put({ url: '/supply/weight', data })
}

// 供货商城商品列表（用于权重调整页面，走 user-web 的 supply-shop 接口）
// baseURL 已是 /admin-api，这里用 baseURL 覆盖为空，直接访问 /api 前缀的接口
export function getSupplyShopProductsForWeight(params: { page?: number; size?: number; keyword?: string }) {
  return request.get({ url: '/api/supply-shop/products', baseURL: '', params })
}
