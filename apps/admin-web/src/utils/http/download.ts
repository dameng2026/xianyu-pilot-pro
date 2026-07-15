import { useUserStore } from '@/store/modules/user'
import { ApiStatus } from './status'
import { createHttpError } from './error'
import { normalizeRequestId, selectSafeServerMessage } from './error-policy'
import { isAllowedCsvContentType } from './download-policy'
import { containsAsciiControlCharacter } from '../text-security'

const MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
const FORBIDDEN_FILE_NAME_CHARACTERS = new Set(['\\', '/', ':', '*', '?', '"', '<', '>', '|'])

function sanitizeFileName(fileName: string): string {
  const sanitized = Array.from(fileName, (character) => (
    FORBIDDEN_FILE_NAME_CHARACTERS.has(character) || containsAsciiControlCharacter(character)
      ? '-'
      : character
  )).join('').slice(0, 180)
  return sanitized || 'export.csv'
}

export async function downloadAuthenticatedCsv(url: string, fileName: string): Promise<void> {
  const token = useUserStore().accessToken
  const response = await fetch(url, {
    credentials: import.meta.env.VITE_WITH_CREDENTIALS === 'true' ? 'include' : 'same-origin',
    headers: {
      Accept: 'text/csv, application/csv, application/octet-stream;q=0.8',
      ...(token
        ? { Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}` }
        : {})
    }
  })
  const requestId = normalizeRequestId(response.headers.get('x-request-id'))

  if (!response.ok) {
    throw createHttpError('导出请求失败', response.status, {
      url,
      method: 'GET',
      requestId
    })
  }

  const contentType = response.headers.get('content-type')
  if (!isAllowedCsvContentType(contentType)) {
    if (String(contentType || '').toLowerCase().includes('application/json')) {
      const body = await response.json().catch(() => null) as { code?: unknown; msg?: unknown } | null
      if (body?.code !== ApiStatus.success) {
        throw createHttpError(
          selectSafeServerMessage(body?.msg, '导出服务返回了错误响应'),
          Number.isInteger(body?.code) ? Number(body?.code) : ApiStatus.badGateway,
          { url, method: 'GET', requestId }
        )
      }
    }
    throw createHttpError('导出服务未返回 CSV 文件', ApiStatus.badGateway, {
      url,
      method: 'GET',
      requestId
    })
  }

  const declaredLength = Number(response.headers.get('content-length') || 0)
  if (Number.isFinite(declaredLength) && declaredLength > MAX_DOWNLOAD_BYTES) {
    throw createHttpError('导出文件过大，请缩小筛选范围', ApiStatus.error, {
      url,
      method: 'GET',
      requestId
    })
  }

  const blob = await response.blob()
  if (blob.size <= 0 || blob.size > MAX_DOWNLOAD_BYTES) {
    throw createHttpError(
      blob.size <= 0 ? '导出文件为空' : '导出文件过大，请缩小筛选范围',
      ApiStatus.error,
      { url, method: 'GET', requestId }
    )
  }

  const objectUrl = URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = sanitizeFileName(fileName)
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}
