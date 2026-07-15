const CAPABILITY_KEYS = Object.freeze([
  'passwordLogin',
  'emailVerification',
  'selfRegistration',
  'passwordReset',
  'profileVerification',
])

const DEFAULT_UNAVAILABLE_MESSAGE = '认证能力状态无法确认，请联系管理员或部署方。'
const SUPPORTED_VERSION = '1'
const SUPPORTED_MODES = new Set(['production-safe', 'local-development'])

function unavailableCapability(reason) {
  return Object.freeze({ available: false, devOnly: false, reason })
}

export function createFailClosedAuthCapabilities(message = DEFAULT_UNAVAILABLE_MESSAGE) {
  const reason = typeof message === 'string' && message.trim()
    ? message.trim()
    : DEFAULT_UNAVAILABLE_MESSAGE
  return Object.freeze({
    version: 'unknown',
    mode: 'unavailable',
    failClosed: true,
    securityNotice: '未确认服务端能力前，不会开放任何登录或自助验证提交入口。',
    supportMessage: reason,
    ...Object.fromEntries(CAPABILITY_KEYS.map(key => [key, unavailableCapability(reason)])),
  })
}

function parseCapability(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || typeof value.available !== 'boolean'
    || typeof value.devOnly !== 'boolean'
    || typeof value.reason !== 'string'
    || !value.reason.trim()
    || (value.devOnly && !value.available)) {
    throw new Error('认证能力响应格式异常')
  }
  return Object.freeze({
    available: value.available,
    devOnly: value.devOnly,
    reason: value.reason.trim(),
  })
}

export function parseAuthCapabilities(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)
    || payload.version !== SUPPORTED_VERSION
    || typeof payload.mode !== 'string' || !SUPPORTED_MODES.has(payload.mode)
    || payload.failClosed !== true
    || typeof payload.securityNotice !== 'string' || !payload.securityNotice.trim()
    || typeof payload.supportMessage !== 'string' || !payload.supportMessage.trim()) {
    throw new Error('认证能力响应格式异常')
  }

  const parsed = {
    version: payload.version.trim(),
    mode: payload.mode.trim(),
    failClosed: true,
    securityNotice: payload.securityNotice.trim(),
    supportMessage: payload.supportMessage.trim(),
  }
  for (const key of CAPABILITY_KEYS) parsed[key] = parseCapability(payload[key])

  if (parsed.passwordLogin.devOnly
    || (parsed.mode === 'production-safe'
      && CAPABILITY_KEYS.some(key => parsed[key].devOnly))
    || (parsed.mode === 'local-development'
      && CAPABILITY_KEYS.some(key => key !== 'passwordLogin'
        && parsed[key].available && !parsed[key].devOnly))) {
    throw new Error('认证能力响应格式异常')
  }
  return Object.freeze(parsed)
}

export { CAPABILITY_KEYS }
