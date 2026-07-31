import request from '../utils/request'

// 供货商品管理
export function createSupplyProduct(data) {
  return request({ url: '/supply/products', method: 'post', data }).then(res => res?.data)
}

export function getSupplyProducts(params) {
  return request({ url: '/supply/products', method: 'get', params }).then(res => res?.data)
}

export function getSupplyProductDetail(id) {
  return request({ url: `/supply/products/${id}`, method: 'get' }).then(res => res?.data)
}

export function updateSupplyProduct(id, data) {
  return request({ url: `/supply/products/${id}`, method: 'put', data }).then(res => res?.data)
}

export function onlineSupplyProduct(id) {
  return request({ url: `/supply/products/${id}/online`, method: 'post' }).then(res => res?.data)
}

export function offlineSupplyProduct(id) {
  return request({ url: `/supply/products/${id}/offline`, method: 'post' }).then(res => res?.data)
}

export function deleteSupplyProduct(id) {
  return request({ url: `/supply/products/${id}`, method: 'delete' }).then(res => res?.data)
}

export function getSupplyProductStats(id) {
  return request({ url: `/supply/products/${id}/stats`, method: 'get' }).then(res => res?.data)
}

// 供货中心首页
export function getSupplyDashboard() {
  return request({ url: '/supply/dashboard', method: 'get' }).then(res => res?.data)
}

export function getSupplySalesTrend() {
  return request({ url: '/supply/sales/trend', method: 'get' }).then(res => res?.data)
}

// 货源商城（买家）
export function getSupplyShopProducts(params) {
  return request({ url: '/supply-shop/products', method: 'get', params }).then(res => res?.data)
}

export function getSupplyShopProductDetail(source, id) {
  return request({ url: `/supply-shop/products/${source}/${id}`, method: 'get' }).then(res => res?.data)
}

export function getCustomerServiceWechat() {
  return request({ url: '/supply-shop/customer-service', method: 'get' }).then(res => res?.data)
}
