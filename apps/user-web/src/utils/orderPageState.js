import { dateTime } from './apiData.js'

const ORDER_STATUS_META = {
  0: { text: '待付款', badge: 'orange' },
  1: { text: '已付款', badge: 'blue' },
  2: { text: '待发货', badge: 'orange' },
  3: { text: '已发货', badge: 'green' },
  4: { text: '已完成', badge: 'green' },
  5: { text: '已关闭', badge: 'red' }
}

const DELIVERY_STATUS_META = {
  pending: { text: '待处理', badge: 'orange' },
  running: { text: '执行中', badge: 'blue' },
  partial: { text: '部分完成', badge: 'orange' },
  success: { text: '已完成', badge: 'green' },
  failed: { text: '失败', badge: 'red' }
}

const DELIVERY_METHOD_TEXT = {
  manual_text: '手动文本发货',
  manual_card: '手动卡密发货',
  auto_text: '自动文本发货',
  auto_card: '自动卡密发货'
}

function orderStatusMeta(value) {
  return ORDER_STATUS_META[Number(value)] || { text: String(value ?? '-'), badge: 'gray' }
}

function deliveryStatusMeta(value) {
  if (!value) return { text: '-', badge: 'gray' }
  return DELIVERY_STATUS_META[String(value).toLowerCase()] || { text: String(value), badge: 'gray' }
}

function buildSpecText(item) {
  if (item?.specSummary) return item.specSummary
  const parts = [item?.specName, item?.specValue].filter(Boolean)
  return parts.length === 2 ? `${parts[0]}: ${parts[1]}` : parts[0] || ''
}

function buildItemLine(item) {
  const title = item?.goodsTitle || '-'
  const count = Math.max(Number(item?.goodsCount) || 1, 1)
  const specText = buildSpecText(item)
  return `${title} x${count}${specText ? ` | ${specText}` : ''}`
}

function quantityText(order) {
  const sent = Number(order?.quantitySent ?? 0) || 0
  const requested = Number(order?.quantityRequested ?? order?.quantityTotal ?? 0) || 0
  return `${sent} / ${requested}`
}

function normalizeItemSummary(order) {
  if (order?.itemSummary) return order.itemSummary
  const items = Array.isArray(order?.items) ? order.items : []
  if (!items.length) return '查看详情'
  return items.slice(0, 2).map(buildItemLine).join(' / ')
}

export function buildOrderRowViewModel(order) {
  const orderMeta = orderStatusMeta(order?.orderStatus)
  const deliveryMeta = deliveryStatusMeta(order?.deliveryStatus)
  const quantityTotal = Number(order?.quantityTotal ?? 0) || 0
  return {
    ...order,
    createTimeText: dateTime(order?.createTime),
    payTimeText: dateTime(order?.payTime),
    shipTimeText: dateTime(order?.shipTime),
    platformSyncTimeText: dateTime(order?.platformSyncTime),
    itemSummary: normalizeItemSummary(order),
    quantityTotalText: quantityTotal > 0 ? String(quantityTotal) : '-',
    orderStatusText: orderMeta.text,
    orderStatusBadge: orderMeta.badge,
    deliveryStatusText: deliveryMeta.text,
    deliveryBadge: deliveryMeta.badge,
    deliveryProgressText: quantityText(order)
  }
}

function boolLabel(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return '是'
  if (value === false || value === 0 || value === '0' || value === 'false') return '否'
  return '-'
}

function boolBadge(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return 'green'
  if (value === false || value === 0 || value === '0' || value === 'false') return 'gray'
  return 'gray'
}

export function buildOrderDetailViewModel(order) {
  const row = buildOrderRowViewModel(order)
  const items = Array.isArray(order?.items) ? order.items : []
  return {
    ...row,
    itemLines: items.map(buildItemLine),
    deliveryMethodText: DELIVERY_METHOD_TEXT[order?.deliveryMethod] || (order?.deliveryMethod || '-'),
    deliveryFailReasonText: order?.deliveryFailReason || '-',
    itemId: order?.itemId || (items.length > 0 ? items[0]?.externalGoodsId : null) || '-',
    isBargain: order?.isBargain,
    isBargainText: boolLabel(order?.isBargain),
    isBargainBadge: boolBadge(order?.isBargain),
    isRated: order?.isRated,
    isRatedText: boolLabel(order?.isRated),
    isRatedBadge: boolBadge(order?.isRated),
    isRedFlower: order?.isRedFlower,
    isRedFlowerText: boolLabel(order?.isRedFlower),
    isRedFlowerBadge: boolBadge(order?.isRedFlower),
  }
}

export function buildManualDeliveryPayload(form) {
  const payload = {
    deliveryTiming: String(form?.deliveryTiming || 'after_payment').trim() || 'after_payment',
    quantityRequested: Math.max(Number(form?.quantityRequested) || 1, 1)
  }
  // 货源库发货：传 sourceId，由后端根据货源推断 deliveryMode 与 deliveryContent
  const sourceId = Number(form?.sourceId)
  if (Number.isFinite(sourceId) && sourceId > 0) {
    payload.sourceId = sourceId
    return payload
  }
  // 自定义发货：传 deliveryMode + deliveryContent
  payload.deliveryMode = String(form?.deliveryMode || 'text').trim() || 'text'
  payload.deliveryContent = String(form?.deliveryContent || '').trim()
  return payload
}

export function buildOrdersQuery(query) {
  const accountId = String(query?.accountId || '').trim()
  const status = String(query?.status ?? '').trim()
  const current = Number(query?.current || 1) || 1
  const shouldSync = query?.sync === true
  const sortField = String(query?.sortField || '').trim()
  const sortOrder = String(query?.sortOrder || '').trim().toLowerCase()
  const payload = {
    accountId: accountId ? Number(accountId) : undefined,
    keyword: query?.keyword || undefined,
    status: status === '' ? undefined : Number(status),
    current,
    size: Number(query?.size || 20) || 20,
    // 排序参数：sortField 必须在白名单内后端才会生效，否则后端使用默认排序
    sortField: sortField || undefined,
    sortOrder: sortOrder === 'asc' || sortOrder === 'desc' ? sortOrder : undefined
  }
  if (accountId && shouldSync) {
    payload.sync = true
  }
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined))
}
