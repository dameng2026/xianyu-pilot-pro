const SENSITIVE_STORAGE_PREFIX = 'xya:sensitive:'
const LEGACY_SENSITIVE_KEYS = Object.freeze([
  'xya:messages-page-cache:v1',
  'xya:messages-page-accounts:v1',
  'xya_client_error_buffer',
])

function browserStorage(name) {
  if (typeof window === 'undefined') return null
  try {
    return window[name] || null
  } catch {
    return null
  }
}

function decodeJwtPayload(token) {
  const payload = String(token || '').split('.')[1]
  if (!payload) return null
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const binary = globalThis.atob(padded)
    const bytes = Uint8Array.from(binary, character => character.charCodeAt(0))
    const parsed = JSON.parse(new TextDecoder().decode(bytes))
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

function firstIdentityValue(...values) {
  for (const value of values) {
    const normalized = String(value ?? '').trim()
    if (normalized) return normalized
  }
  return ''
}

function hashIdentity(value) {
  const text = String(value || '')
  const seeds = [0x811c9dc5, 0x9e3779b1, 0x85ebca77, 0xc2b2ae3d]
  return seeds.map(seed => {
    let hash = seed >>> 0
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index)
      hash = Math.imul(hash, 0x01000193) >>> 0
      hash ^= hash >>> 13
    }
    return hash.toString(16).padStart(8, '0')
  }).join('')
}

export function createAuthSessionScope(token, username = '') {
  const normalizedToken = String(token || '').trim()
  if (!normalizedToken) return ''
  const claims = decodeJwtPayload(normalizedToken)
  const issuer = firstIdentityValue(claims?.iss)
  const tenant = firstIdentityValue(
    claims?.tenant_id,
    claims?.tenantId,
    claims?.organization_id,
    claims?.organizationId,
    claims?.org_id,
    claims?.orgId,
  )
  const user = firstIdentityValue(
    claims?.sub,
    claims?.user_id,
    claims?.userId,
    claims?.uid,
    claims?.username,
    username,
  )
  const stableIdentity = user
    ? `issuer=${issuer}|tenant=${tenant}|user=${user}`
    : `opaque-token=${normalizedToken}|username=${String(username || '').trim()}`
  return `auth-${hashIdentity(stableIdentity)}`
}

export function getAuthSessionScope() {
  const storage = browserStorage('localStorage')
  if (!storage) return ''
  try {
    return createAuthSessionScope(
      storage.getItem('xianyu_auth_token') || '',
      storage.getItem('xianyu_username') || '',
    )
  } catch {
    return ''
  }
}

function normalizeNamespace(namespace) {
  return String(namespace || '').trim().replace(/[^a-z0-9:_-]/gi, '-').slice(0, 80)
}

export function createSessionPrivacyStore(namespace, {
  storage = browserStorage('sessionStorage'),
  ttlMs = 5 * 60 * 1000,
  getScope = getAuthSessionScope,
  now = Date.now,
} = {}) {
  const safeNamespace = normalizeNamespace(namespace)
  const safeTtl = Math.max(1, Math.min(Number(ttlMs) || 1, 60 * 60 * 1000))

  function details() {
    const scope = String(getScope?.() || '').trim()
    return {
      scope,
      key: scope && safeNamespace ? `${SENSITIVE_STORAGE_PREFIX}${scope}:${safeNamespace}` : '',
    }
  }

  function remove() {
    const { key } = details()
    if (!storage || !key) return
    try { storage.removeItem(key) } catch { /* Storage may be unavailable. */ }
  }

  function read() {
    const { key, scope } = details()
    if (!storage || !key || !scope) return null
    try {
      const raw = storage.getItem(key)
      if (!raw) return null
      const envelope = JSON.parse(raw)
      const expiresAt = Number(envelope?.expiresAt || 0)
      if (envelope?.scope !== scope || !expiresAt || Number(now()) >= expiresAt) {
        storage.removeItem(key)
        return null
      }
      return envelope.value ?? null
    } catch {
      try { storage.removeItem(key) } catch { /* Ignore storage cleanup failure. */ }
      return null
    }
  }

  function write(value) {
    const { key, scope } = details()
    if (!storage || !key || !scope) return false
    const savedAt = Number(now())
    try {
      storage.setItem(key, JSON.stringify({
        version: 1,
        scope,
        savedAt,
        expiresAt: savedAt + safeTtl,
        value,
      }))
      return true
    } catch {
      return false
    }
  }

  return Object.freeze({ read, write, remove })
}

function removeMatchingKeys(storage) {
  if (!storage) return
  try {
    const keys = []
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key?.startsWith(SENSITIVE_STORAGE_PREFIX)) keys.push(key)
    }
    keys.forEach(key => storage.removeItem(key))
    LEGACY_SENSITIVE_KEYS.forEach(key => storage.removeItem(key))
  } catch {
    // Storage may be disabled; clearing auth must still continue.
  }
}

function removeLegacyKeys(storage) {
  if (!storage) return
  try {
    LEGACY_SENSITIVE_KEYS.forEach(key => storage.removeItem(key))
  } catch {
    // Best-effort migration cleanup must never block application startup.
  }
}

export function purgeLegacySensitiveData({
  localStorage = browserStorage('localStorage'),
} = {}) {
  removeLegacyKeys(localStorage)
}

export function clearSensitiveSessionData({
  sessionStorage = browserStorage('sessionStorage'),
  localStorage = browserStorage('localStorage'),
} = {}) {
  removeMatchingKeys(sessionStorage)
  removeMatchingKeys(localStorage)
}
