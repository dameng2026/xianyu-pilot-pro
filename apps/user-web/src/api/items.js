import request from '../utils/request.js'

export const listItems = data => request.post('/item/list', data)
// 同步触发接口：Python 端创建后台任务后立即返回，但 DB 检查可能耗时，给 60s 超时
export const refreshItems = data => request.post('/item/refresh', data, { timeout: 60000 })
export const publishItem = data => request.post('/item/publish', data)
export const itemDetail = data => request.post('/item/detail', data)
export const deleteItem = data => request.post('/item/delete', data)
export const offShelfItem = data => request.post('/item/offShelf', data)
export const republishItem = data => request.post('/item/republish', data)
export const toggleAutoRelist = data => request.post('/item/auto-relist/toggle', data)
export const remoteDeleteItem = data => request.post('/item/remoteDelete', data)
export const batchDeleteItems = data => request.post('/item/batch/delete', data)
export const batchRemoteDeleteItems = data => request.post('/item/batch/remoteDelete', data)
export const batchOffShelfItems = data => request.post('/item/batch/offShelf', data)
export const updateItemPrice = data => request.post('/item/updatePrice', data)
export const updateItemStock = data => request.post('/item/updateStock', data)
export const updateAutoDeliveryStatus = data => request.post('/item/updateAutoDeliveryStatus', data)
export const updateAutoConfirmShipment = data => request.post('/item/updateAutoConfirmShipment', data)
export const updateAutoReplyStatus = data => request.post('/item/updateAutoReplyStatus', data)
export const autoDeliveryRecords = data => request.post('/item/autoDeliveryRecords', data)
export const autoReplyRecords = data => request.post('/item/autoReplyRecords', data)
export const getRagAutoReplyConfig = data => request.post('/item/getRagAutoReplyConfig', data)
export const updateRagAutoReplyConfig = data => request.post('/item/updateRagAutoReplyConfig', data)
export const getSkuSpecs = data => request.post('/item/sku-specs', data)
// 进度轮询：每 2s 调用一次，用较短超时避免阻塞下一次轮询
export const getSyncProgress = syncId => request.get(`/item/syncProgress/${syncId}`, { timeout: 15000 })
export const isSyncing = accountId => request.get(`/item/syncing/${accountId}`)

// 同步任务历史：Java 直接查 DB，同步后可能数据量大，给 60s 超时
export const getSyncTasks = params => request.get('/item/syncTasks', { params, timeout: 60000 })

// ---- 自动分类相关 ----
// 自动分类涉及图片下载+CDN上传+MTOP调用，设置较长超时（120s）
export const autoCategory = (accountId, data) => request.post(`/xianyu/accounts/${accountId}/auto-category`, data, { timeout: 120000 })
export const autoCategoryUpload = (accountId, file, title, description) => {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  if (description) form.append('description', description)
  return request.post(`/xianyu/accounts/${accountId}/auto-category/upload`, form, { timeout: 120000 })
}
export const getAutoCategoryConfig = () => request.get('/xianyu/accounts/auto-category/config')
