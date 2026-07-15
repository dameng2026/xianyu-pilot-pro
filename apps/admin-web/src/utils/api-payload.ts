export class ApiPayloadError extends Error {
  constructor(label: string) {
    super(`${label}响应格式异常，请稍后重试`)
    this.name = 'ApiPayloadError'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readNonNegativeInteger(value: unknown): number | null {
  if (typeof value === 'string' && /^\d+$/.test(value)) {
    value = Number(value)
  }

  return typeof value === 'number'
    && Number.isSafeInteger(value)
    && value >= 0
    ? value
    : null
}

export function requireRecordPayload<T extends Record<string, unknown>>(
  value: unknown,
  label: string
): T {
  if (!isRecord(value)) {
    throw new ApiPayloadError(label)
  }
  return value as T
}

export function requireListPayload<T>(value: unknown, label: string): T[] {
  if (!Array.isArray(value)) {
    throw new ApiPayloadError(label)
  }
  return value as T[]
}

export interface ValidatedPagePayload<T> {
  records: T[]
  total: number
  current?: number
  size?: number
}

export function requirePagePayload<T>(value: unknown, label: string): ValidatedPagePayload<T> {
  const page = requireRecordPayload<Record<string, unknown>>(value, label)
  const total = readNonNegativeInteger(page.total)

  if (!Array.isArray(page.records) || total === null || total < page.records.length) {
    throw new ApiPayloadError(label)
  }

  const current = page.current === undefined ? undefined : readNonNegativeInteger(page.current)
  const size = page.size === undefined ? undefined : readNonNegativeInteger(page.size)
  if (current === null || size === null) {
    throw new ApiPayloadError(label)
  }

  return {
    records: page.records as T[],
    total,
    ...(current === undefined ? {} : { current }),
    ...(size === undefined ? {} : { size })
  }
}

export function requireAffectedCount(value: unknown, label: string): { count: number } {
  const payload = requireRecordPayload<Record<string, unknown>>(value, label)
  const count = readNonNegativeInteger(payload.count)
  if (count === null) {
    throw new ApiPayloadError(label)
  }
  return { count }
}
