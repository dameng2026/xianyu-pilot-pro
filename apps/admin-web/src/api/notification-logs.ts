import request from '@/utils/http'
import { requirePagePayload } from '@/utils/api-payload'

export interface NotificationDeliveryLogQuery {
  current?: number
  size?: number
  keyword?: string
  success?: string | number
  channelKey?: string
}

export interface NotificationDeliveryLogRecord {
  id: number
  tenantId?: number
  userId?: number
  channelKey?: string
  channelName?: string
  eventType?: string
  success?: number | boolean
  statusCode?: number
  costMs?: number
  message?: string
  requestBody?: string
  responseBody?: string
  retryCount?: number
  createdTime?: string
}

export interface NotificationDeliveryLogPage {
  records: NotificationDeliveryLogRecord[]
  current: number
  size: number
  total: number
}

export function getNotificationDeliveryLogs(params: NotificationDeliveryLogQuery) {
  return request.get<NotificationDeliveryLogPage>({ url: '/notifications/delivery-logs', params })
    .then(value => requirePagePayload<NotificationDeliveryLogRecord>(value, '通知发送记录') as NotificationDeliveryLogPage)
}
