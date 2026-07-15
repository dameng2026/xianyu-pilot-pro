const MAX_SVG_BYTES = 256 * 1024
const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
const XLINK_NAMESPACE = 'http://www.w3.org/1999/xlink'

const ALLOWED_TAGS = new Set([
  'svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon',
  'defs', 'clipPath', 'mask', 'linearGradient', 'radialGradient', 'stop', 'pattern',
  'filter', 'feBlend', 'feColorMatrix', 'feComposite', 'feFlood', 'feGaussianBlur',
  'feOffset', 'title', 'desc', 'use'
].map(tag => tag.toLowerCase()))

const ALLOWED_ATTRIBUTES = new Set([
  'xmlns', 'viewbox', 'width', 'height', 'fill', 'fill-opacity', 'fill-rule', 'stroke',
  'stroke-width', 'stroke-opacity', 'stroke-linecap', 'stroke-linejoin', 'clip-rule',
  'd', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'points',
  'transform', 'opacity', 'offset', 'stop-color', 'stop-opacity', 'gradientunits',
  'gradienttransform', 'spreadmethod', 'mask', 'maskunits', 'maskcontentunits',
  'clippathunits', 'filter', 'filterunits', 'primitiveunits', 'in', 'in2', 'result',
  'stddeviation', 'dx', 'dy', 'values', 'type', 'operator', 'k1', 'k2', 'k3', 'k4',
  'id', 'href', 'xlink:href', 'xmlns:xlink', 'preserveaspectratio', 'style', 'role',
  'aria-label'
])

const SAFE_FRAGMENT_REFERENCE = /^(?:#[A-Za-z_][\w:.-]*|url\(#[A-Za-z_][\w:.-]*\))$/
const SAFE_STYLE_VALUE = /^[-#(),.%\w\s]+$/i
const ALLOWED_STYLE_PROPERTIES = new Set([
  'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity',
  'stroke-linecap', 'stroke-linejoin', 'opacity', 'stop-color', 'stop-opacity',
  'mask-type'
])

function isSafeStyle(value: string): boolean {
  const declarations = value.split(';').map(part => part.trim()).filter(Boolean)
  if (declarations.length === 0) return false

  return declarations.every(declaration => {
    const separator = declaration.indexOf(':')
    if (separator <= 0) return false

    const property = declaration.slice(0, separator).trim().toLowerCase()
    const propertyValue = declaration.slice(separator + 1).trim()
    if (!ALLOWED_STYLE_PROPERTIES.has(property) || !SAFE_STYLE_VALUE.test(propertyValue)) {
      return false
    }
    if (/@import|expression|javascript:|data:|https?:|\\/i.test(propertyValue)) return false
    return !/url\s*\(/i.test(propertyValue) || SAFE_FRAGMENT_REFERENCE.test(propertyValue)
  })
}

export function svgByteLength(value: string): number {
  const content = String(value || '')
  if (typeof TextEncoder === 'undefined') return content.length * 3
  return new TextEncoder().encode(content).byteLength
}

export function isTrustedSvgSource(raw: string, baseUrl = globalThis.location?.href): boolean {
  const value = String(raw || '').trim()
  if (!value || value.length > MAX_SVG_BYTES) return false
  if (/^data:image\/svg\+xml(?:;charset=[\w-]+)?(?:;base64)?,/i.test(value)) return true
  if (!baseUrl) return false

  try {
    const base = new URL(baseUrl)
    const candidate = new URL(value, base)
    return (candidate.protocol === 'https:' || candidate.protocol === 'http:')
      && candidate.origin === base.origin
      && !candidate.username
      && !candidate.password
  } catch {
    return false
  }
}

export function sanitizeSvg(raw: string): string {
  const content = String(raw || '')
  if (
    !content
    || svgByteLength(content) > MAX_SVG_BYTES
    || /<!\s*(?:doctype|entity)\b/i.test(content)
    || typeof DOMParser === 'undefined'
  ) return ''

  const document = new DOMParser().parseFromString(content, 'image/svg+xml')
  if (document.querySelector('parsererror')) return ''
  const root = document.documentElement
  if (root.localName.toLowerCase() !== 'svg' || root.namespaceURI !== SVG_NAMESPACE) return ''

  for (const element of [...root.querySelectorAll('*')]) {
    if (element.namespaceURI !== SVG_NAMESPACE || !ALLOWED_TAGS.has(element.localName.toLowerCase())) {
      element.remove()
      continue
    }
  }

  for (const element of [root, ...root.querySelectorAll('*')]) {
    for (const attribute of [...element.attributes]) {
      const name = attribute.name.toLowerCase()
      const value = attribute.value.trim()
      if (name.startsWith('on') || !ALLOWED_ATTRIBUTES.has(name)) {
        element.removeAttribute(attribute.name)
        continue
      }
      if (name === 'xmlns' && (element !== root || value !== SVG_NAMESPACE)) {
        element.removeAttribute(attribute.name)
        continue
      }
      if (name === 'xmlns:xlink' && (element !== root || value !== XLINK_NAMESPACE)) {
        element.removeAttribute(attribute.name)
        continue
      }
      if ((name === 'href' || name === 'xlink:href') && !/^#[A-Za-z_][\w:.-]*$/.test(value)) {
        element.removeAttribute(attribute.name)
        continue
      }
      if ((name === 'mask' || name === 'filter') && !SAFE_FRAGMENT_REFERENCE.test(value)) {
        element.removeAttribute(attribute.name)
        continue
      }
      if (name === 'style') {
        if (!isSafeStyle(value)) element.removeAttribute(attribute.name)
        continue
      }
      if (/url\s*\(/i.test(value) && !SAFE_FRAGMENT_REFERENCE.test(value)) {
        element.removeAttribute(attribute.name)
      }
    }
  }

  return new XMLSerializer().serializeToString(root)
}

export { MAX_SVG_BYTES, SVG_NAMESPACE }
