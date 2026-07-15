const MAX_SERVER_MESSAGE_LENGTH = 240
const MAX_REQUEST_ID_LENGTH = 128

const UNSAFE_SERVER_MESSAGE_PATTERNS = [
  /<[^>]*>/,
  /(?:java\.|javax\.|org\.|com\.)[a-z0-9_$.]+(?:exception|error)?/i,
  /\b(?:traceback|stack\s*trace|sqlstate|jdbc)\b/i,
  /\bat\s+[a-z0-9_$.]+\([^)]*:\d+\)/i,
  /\b(?:password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\s*[:=]/i,
  /\b(?:select|insert|update|delete)\s+.+\s+(?:from|into|set)\b/i
]

export function selectSafeServerMessage(serverMessage: unknown, fallbackMessage: string): string {
  if (typeof serverMessage !== 'string') return fallbackMessage

  const withoutControlCharacters = Array.from(serverMessage, character => {
    const codePoint = character.codePointAt(0) ?? 0
    return codePoint <= 31 || codePoint === 127 ? ' ' : character
  }).join('')
  const normalized = withoutControlCharacters.replace(/\s+/g, ' ').trim()
  if (!normalized || normalized.length > MAX_SERVER_MESSAGE_LENGTH) return fallbackMessage
  if (UNSAFE_SERVER_MESSAGE_PATTERNS.some(pattern => pattern.test(normalized))) return fallbackMessage

  return normalized
}

export function normalizeRequestId(requestId: unknown): string | undefined {
  if (typeof requestId !== 'string') return undefined

  const normalized = requestId.trim()
  if (!normalized || normalized.length > MAX_REQUEST_ID_LENGTH) return undefined
  if (!/^[A-Za-z0-9._:-]+$/.test(normalized)) return undefined

  return normalized
}

export function formatHttpErrorDisplay(message: string, requestId?: string): string {
  return requestId ? `${message}（请求 ID：${requestId}）` : message
}

function normalizeAuthorizationToken(value: unknown): string {
  if (typeof value !== 'string') return ''
  return value.trim().replace(/^Bearer\s+/i, '').trim()
}

export function isAuthorizationForCurrentSession(
  requestAuthorization: unknown,
  currentAccessToken: unknown
): boolean {
  const requestToken = normalizeAuthorizationToken(requestAuthorization)
  const currentToken = normalizeAuthorizationToken(currentAccessToken)
  return requestToken.length > 0 && currentToken.length > 0 && requestToken === currentToken
}

const RETRYABLE_GET_STATUSES = new Set([408, 500, 502, 503, 504])

const HTTP_STATUS_MESSAGE_KEYS: Readonly<Record<number, string>> = {
  400: 'httpMsg.badRequest',
  401: 'httpMsg.unauthorized',
  402: 'httpMsg.paymentRequired',
  403: 'httpMsg.forbidden',
  404: 'httpMsg.notFound',
  405: 'httpMsg.methodNotAllowed',
  408: 'httpMsg.requestTimeout',
  409: 'httpMsg.conflict',
  429: 'httpMsg.tooManyRequests',
  500: 'httpMsg.internalServerError',
  502: 'httpMsg.badGateway',
  503: 'httpMsg.serviceUnavailable',
  504: 'httpMsg.gatewayTimeout'
}

export function getHttpStatusMessageKey(statusCode: number): string {
  return HTTP_STATUS_MESSAGE_KEYS[statusCode] ?? 'httpMsg.internalServerError'
}

export function shouldRetryHttpRequest(method: unknown, statusCode: number): boolean {
  return typeof method === 'string'
    && method.toUpperCase() === 'GET'
    && RETRYABLE_GET_STATUSES.has(statusCode)
}
