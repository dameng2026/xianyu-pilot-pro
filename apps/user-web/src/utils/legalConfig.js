function normalizeDocumentUrl(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.startsWith('/') && !text.startsWith('//')) return text

  try {
    const url = new URL(text)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : ''
  } catch {
    return ''
  }
}

export function resolveLegalConfig(env = {}) {
  return {
    termsUrl: normalizeDocumentUrl(env.VITE_TERMS_URL),
    privacyUrl: normalizeDocumentUrl(env.VITE_PRIVACY_URL),
    icpLicense: String(env.VITE_ICP_LICENSE || '').trim(),
  }
}

export const LEGAL_CONFIG = resolveLegalConfig(import.meta.env || {})

export function getLegalDocumentUrl(type, config = LEGAL_CONFIG) {
  return type === 'privacy' ? config.privacyUrl : type === 'terms' ? config.termsUrl : ''
}

export function hasRequiredLegalDocuments(config = LEGAL_CONFIG) {
  return Boolean(config.termsUrl && config.privacyUrl)
}
