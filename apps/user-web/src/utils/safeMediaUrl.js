const MAX_DATA_IMAGE_LENGTH = 2 * 1024 * 1024
const TRUSTED_MEDIA_HOSTS = Object.freeze([
  'alicdn.com',
  'tbcdn.cn',
  'taobaocdn.com',
  'xianyu.com',
  'goofish.com',
  'taobao.com',
  'tmall.com',
  'aliyun.com',
  'alibaba.com',
  '1688.com',
  'alibaba-inc.com',
  'mmecdn.com',
  'layui.com',
  'qlogo.cn',
  'qq.com',
  'weixin.qq.com',
  'wx.qlogo.cn',
])
const SAME_ORIGIN_MEDIA_PREFIXES = Object.freeze([
  '/api/',
  '/uploads/',
  '/xya/',
  '/assets/',
])
const ALICDN_MEDIA_PREFIXES = Object.freeze([
  '/bao/uploaded/',
  '/imgextra/',
  '/tfscom/',
])

function activeOrigin() {
  if (typeof window === 'undefined') return 'https://invalid.local'
  return window.location?.origin || 'https://invalid.local'
}

function activeWindow() {
  return typeof window === 'undefined' ? null : window
}

function isTrustedHostname(hostname, trustedHosts) {
  const normalized = String(hostname || '').toLowerCase().replace(/\.$/, '')
  return trustedHosts.some(host => normalized === host || normalized.endsWith(`.${host}`))
}

function isAllowedSameOriginPath(pathname) {
  return SAME_ORIGIN_MEDIA_PREFIXES.some(prefix => pathname.startsWith(prefix))
}

function safeDataImage(value) {
  if (value.length > MAX_DATA_IMAGE_LENGTH) return ''
  return /^data:image\/(?:avif|gif|jpeg|png|webp);base64,[a-z0-9+/=]+$/i.test(value) ? value : ''
}

function relativeUrl(parsed) {
  return `${parsed.pathname}${parsed.search}${parsed.hash}`
}

export function resolveTrustedMediaUrl(value, {
  origin = activeOrigin(),
  trustedHosts = TRUSTED_MEDIA_HOSTS,
} = {}) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (raw.toLowerCase().startsWith('data:')) return safeDataImage(raw)

  let originUrl
  try {
    originUrl = new URL(origin)
  } catch {
    return ''
  }

  if (raw.startsWith('/') && !raw.startsWith('//')) {
    let parsed
    try {
      parsed = new URL(raw, originUrl)
    } catch {
      return ''
    }
    if (parsed.origin !== originUrl.origin || parsed.username || parsed.password) return ''
    if (isAllowedSameOriginPath(parsed.pathname)) return relativeUrl(parsed)
    if (ALICDN_MEDIA_PREFIXES.some(prefix => parsed.pathname.startsWith(prefix))) {
      return `https://img.alicdn.com${relativeUrl(parsed)}`
    }
    return ''
  }

  const candidate = raw.startsWith('//') ? `https:${raw}` : raw
  let parsed
  try {
    parsed = new URL(candidate)
  } catch {
    return ''
  }
  // 允许 http 和 https（部分头像CDN可能仍使用http）
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return ''
  if (parsed.username || parsed.password) return ''
  if (parsed.port && parsed.port !== '443' && parsed.port !== '80') return ''

  if (parsed.origin === originUrl.origin && isAllowedSameOriginPath(parsed.pathname)) {
    return parsed.href
  }

  const hosts = (Array.isArray(trustedHosts) ? trustedHosts : [])
    .map(host => String(host || '').trim().toLowerCase())
    .filter(Boolean)
  return isTrustedHostname(parsed.hostname, hosts) ? parsed.href : ''
}

/**
 * 将本地用户图片 URL 转换为缩略图 URL（{原图}_thumb.jpg）。
 *
 * <p>仅转换 /uploads/images/ 下的用户图片；缩略图由后端懒生成并落盘，
 * 旧图首次访问时自动生成，不会裂图。动图（gif）与原图保持一致。</p>
 */
export function toThumbUrl(value) {
  const raw = String(value || '').trim()
  if (!raw || !raw.startsWith('/uploads/images/')) return raw
  return raw.replace(/\.(jpg|jpeg|png|webp)$/i, '_thumb.jpg')
}

export function resolveAvatarUrl(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  
  // 清理脏数据：处理 {avatar=http://...} 或 avatar=http://... 格式
  let cleaned = raw
  // 移除 { } 包裹
  cleaned = cleaned.replace(/^\{?\s*(?:avatar|avatarUrl|headImg|profilePic)\s*=\s*/i, '')
  cleaned = cleaned.replace(/\s*\}?$/, '')
  // 移除多余引号
  cleaned = cleaned.replace(/^["']|["']$/g, '')
  
  if (!cleaned) return ''
  if (cleaned.toLowerCase().startsWith('data:')) return safeDataImage(cleaned)
  
  // 处理 // 开头的协议相对URL
  const candidate = cleaned.startsWith('//') ? `https:${cleaned}` : cleaned
  
  try {
    const parsed = new URL(candidate)
    // 头像允许 http/https
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return ''
    if (parsed.username || parsed.password) return ''
    
    // 检查是否是可信域名（扩展列表，包含更多头像CDN）
    const avatarHosts = [
      ...TRUSTED_MEDIA_HOSTS,
      'img.alicdn.com',
      'gw.alicdn.com',
      'gtms.alicdn.com',
      'x.i2.taobao.com',
      'wwc.alicdn.com',
      'cbu01.alicdn.com',
      'sc01.alicdn.com',
      'sc02.alicdn.com',
      'img01.taobaocdn.com',
      'img02.taobaocdn.com',
      'img03.taobaocdn.com',
      'img04.taobaocdn.com',
      'avatar.xianyu.com',
      'pic.xianyu.com',
    ]
    
    const hostname = parsed.hostname.toLowerCase()
    const isTrusted = avatarHosts.some(host => 
      hostname === host || hostname.endsWith(`.${host}`)
    )
    
    // 如果是可信域名，直接返回
    if (isTrusted) return parsed.href
    
    // 对于其他域名，如果看起来像图片URL（路径包含图片扩展名或常见图片路径），也允许
    const path = parsed.pathname.toLowerCase()
    const isImagePath = /\.(jpg|jpeg|png|gif|webp|bmp|svg)(\?|$)/i.test(path) ||
                       path.includes('/avatar/') ||
                       path.includes('/head/') ||
                       path.includes('/profile/') ||
                       path.includes('avatar') ||
                       path.includes('headimg')
    
    if (isImagePath) return parsed.href

    // 不在可信域名白名单且不像图片路径的 URL，返回空字符串
    // 强制调用方使用默认头像，避免隐私追踪像素、CDN 泄露等风险
    return ''
  } catch {
    // 如果是相对路径，尝试补全为https
    if (cleaned.startsWith('/')) {
      try {
        return new URL(cleaned, 'https://img.alicdn.com').href
      } catch {
        return ''
      }
    }
    return ''
  }
}

export function openTrustedMediaUrl(value, {
  windowLike = activeWindow(),
  trustedHosts = TRUSTED_MEDIA_HOSTS,
} = {}) {
  if (!windowLike?.open) return false
  const safeUrl = resolveTrustedMediaUrl(value, {
    origin: windowLike.location?.origin || activeOrigin(),
    trustedHosts,
  })
  if (!safeUrl) return false
  try {
    const opened = windowLike.open(safeUrl, '_blank', 'noopener,noreferrer')
    if (!opened) return false
    try { opened.opener = null } catch { /* noopener already isolates the window. */ }
    return true
  } catch {
    return false
  }
}

