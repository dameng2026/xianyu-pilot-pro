const LEGACY_AUTH_KEYS = [
  /^user$/,
  /^sys-v.+-(?:user|userStore)$/
]

export function clearLegacyPersistentAuth(storage: Storage = localStorage): number {
  let removed = 0
  const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index))
    .filter((key): key is string => Boolean(key))
  for (const key of keys) {
    if (LEGACY_AUTH_KEYS.some(pattern => pattern.test(key))) {
      storage.removeItem(key)
      removed += 1
    }
  }
  return removed
}

function storageKeys(storage: Storage): string[] {
  return Array.from({ length: storage.length }, (_, index) => storage.key(index))
    .filter((key): key is string => Boolean(key))
}

export function clearApplicationStorage(
  persistentStorage: Storage = localStorage,
  sessionStorageArea: Storage = sessionStorage
): void {
  for (const key of storageKeys(persistentStorage)) {
    if (key.startsWith('sys-') || key === 'user') persistentStorage.removeItem(key)
  }
  for (const key of storageKeys(sessionStorageArea)) {
    if (key.startsWith('sys-') || key === 'user' || key === 'iframeRoutes') {
      sessionStorageArea.removeItem(key)
    }
  }
}
