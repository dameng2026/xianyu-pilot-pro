const responseCache = new Map()
const inflightCache = new Map()

function stableSerialize(value) {
  if (value === null || value === undefined) return String(value)
  if (Array.isArray(value)) {
    return `[${value.map(item => stableSerialize(item)).join(',')}]`
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableSerialize(item)}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function cloneValue(value) {
  if (value === null || value === undefined || typeof value !== 'object') {
    return value
  }
  try {
    if (typeof structuredClone === 'function') {
      return structuredClone(value)
    }
  } catch {
    // Fall through to JSON clone.
  }
  try {
    return JSON.parse(JSON.stringify(value))
  } catch {
    return value
  }
}

function normalizeMatcher(matcher) {
  if (typeof matcher === 'function') return matcher
  const text = String(matcher || '')
  return key => key.includes(text)
}

export function withRequestCache({ keyParts, ttlMs = 0, force = false, request }) {
  if (force || ttlMs <= 0) {
    return Promise.resolve().then(request)
  }

  const key = stableSerialize(keyParts)
  const now = Date.now()
  const cached = responseCache.get(key)
  if (cached && cached.expiresAt > now) {
    return Promise.resolve(cloneValue(cached.value))
  }
  if (cached) {
    responseCache.delete(key)
  }

  const inflight = inflightCache.get(key)
  if (inflight) {
    return inflight.then(value => cloneValue(value))
  }

  const pending = Promise.resolve()
    .then(request)
    .then(value => {
      responseCache.set(key, {
        value: cloneValue(value),
        expiresAt: Date.now() + ttlMs,
      })
      return value
    })
    .finally(() => {
      inflightCache.delete(key)
    })

  inflightCache.set(key, pending)
  return pending.then(value => cloneValue(value))
}

export function invalidateRequestCache(matcher) {
  const matches = normalizeMatcher(matcher)
  for (const key of responseCache.keys()) {
    if (matches(key)) {
      responseCache.delete(key)
    }
  }
  for (const key of inflightCache.keys()) {
    if (matches(key)) {
      inflightCache.delete(key)
    }
  }
}
