import request from '../utils/request.js'

export const uploadImage = (accountId, file) => {
  const form = new FormData()
  form.append('accountId', String(accountId))
  form.append('file', file)
  return request.post('/image/upload', form)
}
export const uploadImageFromUrl = data => request.post('/image/uploadFromUrl', data)
export const detectCaptcha = data => request.post('/captcha/detect', data)
export const latestCaptchaDebugImageUrl = () => '/api/captcha/debug-image/latest'
export const listMedia = data => request.post('/media/list', data || {})
export const deleteMedia = data => request.post('/media/delete', data)
export const notificationLogs = data => request.post('/notification/logs', data || {})
export const latestNotifications = data => request.post('/notification/latest', data || {})
export const testNotification = data => request.post('/notification/test', data || {})
export const queryOperationLogs = data => request.post('/operationLog/list', data || {})
export const deleteOldOperationLogs = data => request.post('/operationLog/deleteOld', data || {})
export const runtimeLog = data => request.post('/operationLog/runtime', data || {})
export const runtimeLogFiles = data => request.post('/operationLog/runtime/files', data || {})
export const clearRuntimeLog = data => request.post('/operationLog/runtime/clear', data || {})
export const exportOrdersUrl = query => `/api/excel/export/orders?${new URLSearchParams(query || {})}`
export const kamiTemplateUrl = () => '/api/excel/template/kami'
export const backupDbUrl = () => '/api/backup/export-db'
export const restoreDb = file => {
  const form = new FormData()
  form.append('file', file)
  return request.post('/backup/restore-db', form)
}
export const goodsSkuList = data => request.post('/goods-sku/list', data || {})
export const goodsSkuDetail = data => request.post('/goods-sku/detail', data || {})
export const businessSearch = q => request.get('/business-opportunity/search', { params: { q } })
export const businessShop = url => request.get('/business-opportunity/shop', { params: { url } })
export const collectBusinessShop = data => request.post('/business-opportunity/collect-shop', data)

// ---- 本地地址字典（省市区三级联动）----
// 一次性加载全国省→市→区树形结构，前端本地做分级筛选。
export const addressDictTree = () => request.get('/address-dict/tree')

// ---- 闲鱼商品关键词搜索（Java 网关 -> Python MTOP）----
// 支持分页: q=关键词&page=1&pageSize=20
// 可选 accountId 指定使用哪个闲鱼账号的 Cookie/_m_h5_tk
// mode: fast=快速搜索(直调MTOP，~1秒) | slow=慢速搜索(浏览器，~2-3秒) | auto=自动降级(默认)
// 返回: { code, data: { items, total, page, pageSize, hasMore, searchMode } }
export const goofishSearch = (q, page = 1, pageSize = 20, accountId = undefined, mode = 'auto') =>
  request.get('/goofish/search', {
    params: { q, page, pageSize, mode, ...(accountId ? { accountId } : {}) },
    // 超时 180 秒：慢速搜索可能触发 Baxia 风控，由 crawler-service 委托 Python patchright 求解滑块，
    // 整个过程（Node Playwright 检测 + Python patchright 启动 + 滑块求解 + MTOP 拦截）
    // 实测需要 120-150 秒。180 秒余量避免把真实 cookie 失效/风控状态吞成"请求超时"。
    // 各层超时已对齐：前端 axios=180s，Java 网关→Python=180s，Python→crawler=180s。
    timeout: 180000,
  })

// ---- 爬虫服务（异步抓取）----
// 提交闲鱼店铺链接，返回 jobId
export const importGoofishStore = url => request.post('/crawler/import/goofish', { url })
// 查询爬取任务状态
export const getCrawlJobStatus = jobId => request.get(`/crawler/crawl-jobs/${jobId}`)
// 获取已抓取的店铺商品列表
export const getGoofishStoreItems = userId => request.get(`/crawler/goofish/stores/${userId}/items`)
