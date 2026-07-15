const BLOCKED_TAGS = new Set([
  'script', 'iframe', 'object', 'embed', 'link', 'meta', 'base', 'form', 'input', 'button', 'textarea', 'select', 'option'
])

const URL_ATTRS = new Set(['href', 'src', 'xlink:href'])
const SAFE_URL_PATTERN = /^(https?:|mailto:|tel:|data:image\/(png|gif|jpeg|jpg|webp);base64,|\/|#)/i

export function sanitizeHtml(raw: string | null | undefined): string {
  const html = String(raw || '')
  if (typeof window === 'undefined' || typeof window.DOMParser === 'undefined') {
    return html.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
  }

  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html')

  doc.body.querySelectorAll('*').forEach((el) => {
    const tagName = el.tagName.toLowerCase()
    if (BLOCKED_TAGS.has(tagName)) {
      el.remove()
      return
    }

    Array.from(el.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase()
      const value = attr.value.trim()

      if (name.startsWith('on')) {
        el.removeAttribute(attr.name)
        return
      }

      if (URL_ATTRS.has(name) && value && !SAFE_URL_PATTERN.test(value)) {
        el.removeAttribute(attr.name)
        return
      }

      if (name === 'style' && /expression\s*\(|javascript:/i.test(value)) {
        el.removeAttribute(attr.name)
      }
    })

    if (tagName === 'a') {
      el.setAttribute('rel', 'noopener noreferrer')
    }
  })

  return doc.body.firstElementChild?.innerHTML || ''
}
