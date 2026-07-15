import { containsAsciiControlCharacter } from './text-security'

export function resolveInternalRedirect(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback
  if (containsAsciiControlCharacter(value)) return fallback

  const candidate = value.trim()
  if (
    !candidate.startsWith('/')
    || candidate.startsWith('//')
    || candidate.startsWith('/\\')
  ) {
    return fallback
  }

  try {
    const parsed = new URL(candidate, 'https://admin.invalid')
    if (parsed.origin !== 'https://admin.invalid') return fallback
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return fallback
  }
}
