import request from '@/utils/http'
import { requirePagePayload } from '@/utils/api-payload'
import { downloadAuthenticatedCsv } from '@/utils/http/download'

export interface OperationLogQuery {
  operationType?: string
  targetType?: string
  targetId?: string | number
  keyword?: string
  current?: number
  size?: number
  limit?: number
}

export interface OperationLogRecord {
  id: number
  tenantId?: number
  userId?: number
  operationType?: string
  operationDesc?: string
  targetType?: string
  targetId?: number
  ipAddress?: string
  createdTime?: string
  updatedTime?: string
}

export interface OperationLogPage {
  records: OperationLogRecord[]
  current: number
  size: number
  total: number
}

export function getOperationLogs(params: OperationLogQuery) {
  return request.get<OperationLogPage>({ url: '/operation-logs', params })
    .then(value => requirePagePayload<OperationLogRecord>(value, '审计日志') as OperationLogPage)
}

export async function exportOperationLogsCsv(params: OperationLogQuery) {
  const baseUrl = import.meta.env.VITE_API_URL || '/admin-api'
  const query = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) query.set(key, String(value))
  })
  await downloadAuthenticatedCsv(
    `${baseUrl}/operation-logs/export?${query.toString()}`,
    `operation-logs-${new Date().toISOString().slice(0, 10)}.csv`
  )
}
