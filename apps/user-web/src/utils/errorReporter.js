import request from './request.js'
import { createSessionPrivacyStore, purgeLegacySensitiveData } from './privacySession.js'

const MAX_BUFFER_SIZE = 30
const BUFFER_TTL_MS = 30 * 60 * 1000
const MESSAGE_LIMIT = 320
const STACK_LIMIT = 1200
const SOURCE_LIMIT = 120
const ROUTE_LIMIT = 160
const errorBufferStore = createSessionPrivacyStore('client-error-buffer:v2', { ttlMs: BUFFER_TTL_MS })
let installed = false

function boundedInteger(value) {
  const number = Number(value)
  if (!Number.isInteger(number) || number < 0 || number > 10_000_000) return null
  return number
}

function stripControlCharacters(value) {
  return [...String(value || '')]
    .filter(character => {
      const code = character.charCodeAt(0)
      return code === 9 || code === 10 || code >= 32
    })
    .join('')
}

function redactSensitiveText(value, limit) {
  let text = stripControlCharacters(value).slice(0, Math.max(limit * 4, limit))
  text = text.replace(/\bBearer\s+[^\s,;]+/gi, 'Bearer [redacted]')
  text = text.replace(/\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]+\b/g, '[redacted-token]')
  text = text.replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[redacted-email]')
  text = text.replace(/\b1[3-9]\d{9}\b/g, '[redacted-phone]')
  text = text.replace(
    /\b(password|passwd|pwd|token|access[_-]?token|refresh[_-]?token|authorization|cookie|secret|api[_-]?key|phone|mobile|email)\b\s*[:=]\s*([^\s,;&]+)/gi,
    '$1=[redacted]',
  )
  text = text.replace(/([A-Z]:\\Users\\)[^\\/\s]+/gi, '$1[redacted]')
  text = text.replace(/(\/(?:Users|home)\/)[^/\s]+/g, '$1[redacted]')
  return text.slice(0, limit)
}

function normalizeType(value) {
  const normalized = String(value || 'client_error')
    .trim()
    .replace(/[^a-z0-9:_-]+/gi, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48)
  return normalized || 'client_error'
}

function normalizeSource(value) {
  const withoutQuery = String(value || '').split('?', 1)[0].split('#', 1)[0]
  const basename = withoutQuery.split(/[\\/]/).filter(Boolean).pop() || ''
  return redactSensitiveText(basename, SOURCE_LIMIT)
}

function normalizeRoute(locationLike) {
  const hash = String(locationLike?.hash || '').trim()
  const pathname = String(locationLike?.pathname || '/').trim()
  const withoutQuery = hash.startsWith('#/')
    ? `#${hash.slice(1).split(/[?#]/, 1)[0]}`
    : pathname.split(/[?#]/, 1)[0]
  const safe = stripControlCharacters(withoutQuery)
    .replace(/[^#a-z0-9/_-]+/gi, '-')
    .slice(0, ROUTE_LIMIT)
  return safe || '/'
}

function coarseUserAgent(navigatorLike) {
  const userAgent = String(navigatorLike?.userAgent || '')
  let browser = 'Other browser'
  if (/Edg\//i.test(userAgent)) browser = 'Edge'
  else if (/Firefox\//i.test(userAgent)) browser = 'Firefox'
  else if (/(?:Chrome|CriOS)\//i.test(userAgent)) browser = 'Chrome'
  else if (/Safari\//i.test(userAgent)) browser = 'Safari'

  let platform = 'Other platform'
  if (/Android/i.test(userAgent)) platform = 'Android'
  else if (/(?:iPhone|iPad|iPod)/i.test(userAgent)) platform = 'iOS'
  else if (/Windows/i.test(userAgent)) platform = 'Windows'
  else if (/(?:Macintosh|Mac OS X)/i.test(userAgent)) platform = 'macOS'
  else if (/Linux/i.test(userAgent)) platform = 'Linux'
  return `${browser} on ${platform}`
}

function browserLocation() {
  return typeof location === 'undefined' ? { pathname: '/', hash: '' } : location
}

function browserNavigator() {
  return typeof navigator === 'undefined' ? { userAgent: '' } : navigator
}

export function sanitizeClientError(input, extra = {}, {
  locationLike = browserLocation(),
  navigatorLike = browserNavigator(),
  now = () => new Date(),
} = {}) {
  const error = input?.reason || input?.error || input
  const message = error?.message || String(error || 'Unknown client error')
  const timestamp = now()
  return {
    message: redactSensitiveText(message, MESSAGE_LIMIT),
    stack: redactSensitiveText(error?.stack || '', STACK_LIMIT),
    type: normalizeType(extra?.type || input?.type || 'client_error'),
    source: normalizeSource(extra?.source || input?.filename || ''),
    line: boundedInteger(input?.lineno),
    column: boundedInteger(input?.colno),
    route: normalizeRoute(locationLike),
    userAgent: coarseUserAgent(navigatorLike),
    time: (timestamp instanceof Date ? timestamp : new Date(timestamp)).toISOString(),
  }
}

function readBuffer() {
  const items = errorBufferStore.read()
  return Array.isArray(items) ? items.slice(-MAX_BUFFER_SIZE) : []
}

function writeBuffer(items) {
  errorBufferStore.write((Array.isArray(items) ? items : []).slice(-MAX_BUFFER_SIZE))
}

export function clearClientErrorBuffer() {
  errorBufferStore.remove()
}

export function recordClientError(input, extra = {}) {
  const event = sanitizeClientError(input, extra)
  writeBuffer([...readBuffer(), event])
  if (import.meta.env?.DEV) console.warn('[client-error-buffer]', event)
  return event
}

export async function flushClientErrors() {
  const buffer = readBuffer()
  if (!buffer.length) return { sent: 0 }
  try {
    const res = await request({ url: '/client-errors', method: 'post', data: { events: buffer } })
    const data = res?.data || res || {}
    const accepted = Number(data.accepted || 0)
    const dropped = Number(data.dropped || 0)
    const confirmed = Math.min(buffer.length, Math.max(0, accepted + dropped))
    const latest = readBuffer()
    if (confirmed > 0) writeBuffer(latest.slice(confirmed))
    return { sent: accepted, dropped, pending: Math.max(0, latest.length - confirmed) }
  } catch (error) {
    return { sent: 0, pending: readBuffer().length, error }
  }
}

export function installClientErrorReporter() {
  if (installed || typeof window === 'undefined') return
  purgeLegacySensitiveData()
  installed = true
  window.addEventListener('error', event => recordClientError(event, { type: 'window_error' }))
  window.addEventListener('unhandledrejection', event => recordClientError(event, { type: 'unhandled_rejection' }))
  setTimeout(flushClientErrors, 2000)
  window.addEventListener('xya-auth-expired', clearClientErrorBuffer)
}

export function getBufferedClientErrors() {
  return readBuffer()
}
