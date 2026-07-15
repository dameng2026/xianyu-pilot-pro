const ALLOWED_CSV_MEDIA_TYPES = new Set([
  'text/csv',
  'application/csv',
  'application/octet-stream',
  'application/vnd.ms-excel'
])

export function isAllowedCsvContentType(contentType: string | null): boolean {
  const mediaType = String(contentType || '').split(';', 1)[0].trim().toLowerCase()
  return ALLOWED_CSV_MEDIA_TYPES.has(mediaType)
}
