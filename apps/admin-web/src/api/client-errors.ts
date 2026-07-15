import request from '@/utils/http'
import { requirePagePayload } from '@/utils/api-payload'

export interface ClientErrorQuery {
  current?: number
  size?: number
  keyword?: string
  type?: string
}

export interface ClientErrorRecord {
  id: number
  tenantId?: number
  userId?: number
  errorType?: string
  message?: string
  source?: string
  route?: string
  userAgent?: string
  ipAddress?: string
  createdTime?: string
}

export interface ClientErrorPage {
  records: ClientErrorRecord[]
  current: number
  size: number
  total: number
}

export function getClientErrors(params: ClientErrorQuery) {
  return request.get<ClientErrorPage>({ url: '/client-errors/page', params })
    .then(value => requirePagePayload<ClientErrorRecord>(value, '前端错误日志') as ClientErrorPage)
}
