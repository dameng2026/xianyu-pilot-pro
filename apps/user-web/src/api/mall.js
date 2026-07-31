import request from '../utils/request.js'

// 商城商品（改为 UNION 查询：平台自营 + 供货商品，列表数据含 source 字段）
export function getMallProducts(params) {
  return request({ url: '/supply-shop/products', method: 'get', params }).then(res => res?.data)
}
export function getMallCategories() {
  return request({ url: '/mall/categories', method: 'get' }).then(res => res?.data)
}
// 商品详情：兼容旧调用 getMallProductDetail(id) 默认 source='mall'，
// 也支持 getMallProductDetail(source, id) 按来源查询
export function getMallProductDetail(source, id) {
  const src = arguments.length === 1 ? 'mall' : source
  const targetId = arguments.length === 1 ? source : id
  return request({ url: `/supply-shop/products/${src}/${targetId}`, method: 'get' }).then(res => res?.data)
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
