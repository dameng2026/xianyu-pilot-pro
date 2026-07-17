import request from '../utils/request.js'

// 商城商品
export function getMallProducts(params) {
  return request({ url: '/mall/products', method: 'get', params }).then(res => res?.data)
}
export function getMallCategories() {
  return request({ url: '/mall/categories', method: 'get' }).then(res => res?.data)
}
export function getMallProductDetail(id) {
  return request({ url: `/mall/products/${id}`, method: 'get' }).then(res => res?.data)
}
export function purchaseMallProduct(data) {
  return request({ url: '/mall/purchase', method: 'post', data }).then(res => res?.data)
}
export function getMallFaqs() {
  return request({ url: '/mall/faqs', method: 'get' }).then(res => res?.data)
}

// 商城客服配置（公开接口）
export function getMallServiceConfig() {
  return request({ url: '/system/config', method: 'get' }).then(res => res?.data)
}
