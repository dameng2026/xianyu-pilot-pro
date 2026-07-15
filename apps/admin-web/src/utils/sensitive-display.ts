const MASK = '[已隐藏]'
const MAX_DISPLAY_LENGTH = 20_000
const MAX_DEPTH = 12

const SENSITIVE_KEY = /^(?:authorization|proxy-authorization|cookie|set-cookie|password|passwd|secret|clientsecret|privatekey|apikey|api_key|accesskeysecret|accesstoken|access_token|refreshtoken|refresh_token|idtoken|sessionid|session_id|credential|webhooksecret|signingsecret)$/i

function redactString(value: string): string {
  return value
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, `Bearer ${MASK}`)
    .replace(
      /((?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie|session[_-]?id)\s*[=:]\s*)([^\s&,;]+)/gi,
      `$1${MASK}`
    )
    .replace(
      /([?&](?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie|session[_-]?id)=)[^&#]*/gi,
      `$1${encodeURIComponent(MASK)}`
    )
}

function redactValue(value: unknown, depth: number, seen: WeakSet<object>): unknown {
  if (typeof value === 'string') return redactString(value)
  if (value === null || typeof value !== 'object') return value
  if (depth >= MAX_DEPTH) return '[内容层级过深，已截断]'
  if (seen.has(value)) return '[循环引用]'

  seen.add(value)
  if (Array.isArray(value)) {
    return value.map(item => redactValue(item, depth + 1, seen))
  }

  const result: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    result[key] = SENSITIVE_KEY.test(key)
      ? MASK
      : redactValue(item, depth + 1, seen)
  }
  return result
}

export function redactSensitiveText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  return redactString(String(value))
}

export function formatSensitivePayload(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'

  let parsed: unknown = value
  if (typeof value === 'string') {
    try {
      parsed = JSON.parse(value)
    } catch {
      return truncate(redactString(value))
    }
  }

  const redacted = redactValue(parsed, 0, new WeakSet())
  const formatted = typeof redacted === 'string'
    ? redacted
    : JSON.stringify(redacted, null, 2)
  return truncate(formatted)
}

function truncate(value: string): string {
  if (value.length <= MAX_DISPLAY_LENGTH) return value
  return `${value.slice(0, MAX_DISPLAY_LENGTH)}\n[内容过长，已截断]`
}
