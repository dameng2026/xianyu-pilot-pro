/**
 * goofish-search.js
 * 纯前端闲鱼/Goofish 商品关键词搜索工具。
 *
 * 工作原理：
 * 1. 通过 Vite 代理（开发环境）或 Nginx 反向代理（生产环境）绕过 CORS
 * 2. 请求 Goofish 搜索页面 HTML
 * 3. 从页面内嵌数据中提取商品信息
 * 4. 标准化、去重后返回
 *
 * 注意：本模块仅提取公开页面中可见的数据，不绕过任何安全措施。
 *       如果页面要求登录/验证码，将返回相应错误。
 */

// ---- 搜索 URL 模板 ----
const SEARCH_URL_TEMPLATE = '/goofish-proxy/search?q='

// ---- 错误码映射 ----
const HTTP_ERROR_MAP = {
  403: 'Goofish 拒绝了本次请求（403 禁止访问），可能是因为检测到非正常浏览器访问。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。',
  429: '请求过于频繁（429），请稍后再试。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。',
  503: 'Goofish 服务暂时不可用（503），请稍后再试。',
}

// ---- 商品字段候选名（大小写不敏感） ----
const TITLE_KEYS = ['title', 'name', 'itemtitle', 'idletitle', 'productname', 'goodsname']
const PRICE_KEYS = ['price', 'reserveprice', 'reserve_price', 'soldprice', 'currentprice', 'saleprice', 'amount']
const IMAGE_KEYS = ['image', 'picurl', 'pic_url', 'cover', 'mainpic', 'imgurl', 'img', 'thumb', 'thumbnail', 'imageurl']
const URL_KEYS = ['itemurl', 'url', 'detailurl', 'link', 'href', 'shareurl']
const ID_KEYS = ['itemid', 'item_id', 'id', 'auctionid', 'productid', 'goodsid']

// ---- 阻断关键词（检测页面是否需要登录/验证） ----
const BLOCK_KEYWORDS = ['登录', '验证码', '安全验证', '访问过于频繁', '请稍后再试', '人机验证', '滑块验证']

// ---- 图片 URL 黑名单（过滤占位图/默认图） ----
const IMAGE_BLACKLIST = ['default', 'placeholder', 'no-image', 'no_pic', 'blank']

/**
 * 输入验证
 */
function validateKeyword(keyword) {
  const trimmed = (keyword || '').trim()

  if (!trimmed) {
    return { valid: false, error: '请输入搜索关键词' }
  }

  // 检测 URL
  if (/^https?:\/\//i.test(trimmed)) {
    return { valid: false, error: '请输入商品关键词，不要输入链接' }
  }

  // 长度检查
  if (trimmed.length < 1) {
    return { valid: false, error: '请输入搜索关键词' }
  }
  if (trimmed.length > 50) {
    return { valid: false, error: '关键词长度不能超过 50 个字符' }
  }

  return { valid: true, keyword: trimmed }
}

/**
 * 构建搜索 URL
 */
function buildSearchUrl(keyword) {
  return SEARCH_URL_TEMPLATE + encodeURIComponent(keyword)
}

/**
 * 判断是否为对象
 */
function isObject(val) {
  return val !== null && typeof val === 'object' && !Array.isArray(val)
}

/**
 * 从对象中按候选字段名提取值（不区分大小写）
 */
function pickByKeys(obj, keyList) {
  if (!isObject(obj)) return undefined
  const lowerKeys = Object.keys(obj).map(k => k.toLowerCase())
  for (const candidate of keyList) {
    const idx = lowerKeys.indexOf(candidate.toLowerCase())
    if (idx !== -1) {
      const val = obj[Object.keys(obj)[idx]]
      if (val !== null && val !== undefined) return val
    }
  }
  return undefined
}

/**
 * 递归遍历 JSON，提取疑似商品对象。
 * 只要对象同时满足以下条件即视为商品：
 * - 存在 title 字段（字符串）
 * - 且存在 price/imageUrl/itemUrl/itemId 中至少一个
 */
function extractItemsFromJson(obj, results, maxDepth, maxItems) {
  if (maxDepth <= 0) return
  if (results.length >= maxItems) return
  if (!isObject(obj)) return

  const keys = Object.keys(obj)
  const lowerKeys = keys.map(k => k.toLowerCase())
  const hasTitle = lowerKeys.some(k => TITLE_KEYS.includes(k))
  const titleVal = hasTitle ? pickByKeys(obj, TITLE_KEYS) : undefined
  const hasValidTitle = typeof titleVal === 'string' && titleVal.trim().length > 0
  const hasAux =
    lowerKeys.some(k => PRICE_KEYS.includes(k)) ||
    lowerKeys.some(k => IMAGE_KEYS.includes(k)) ||
    lowerKeys.some(k => URL_KEYS.includes(k)) ||
    lowerKeys.some(k => ID_KEYS.includes(k))

  if (hasValidTitle && hasAux) {
    const price = pickByKeys(obj, PRICE_KEYS)
    const rawImage = pickByKeys(obj, IMAGE_KEYS)
    const rawUrl = pickByKeys(obj, URL_KEYS)
    const itemId = pickByKeys(obj, ID_KEYS)

    results.push({
      title: String(titleVal).trim().substring(0, 200),
      price: price != null ? formatPrice(price) : '',
      image: normalizeImageUrl(rawImage),
      link: normalizeItemUrl(rawUrl),
      itemId: itemId != null ? String(itemId) : '',
      description: '',
    })
  }

  // 递归遍历子属性
  for (const val of Object.values(obj)) {
    if (results.length >= maxItems) return
    if (isObject(val)) {
      extractItemsFromJson(val, results, maxDepth - 1, maxItems)
    } else if (Array.isArray(val)) {
      for (const elem of val) {
        if (results.length >= maxItems) return
        if (isObject(elem)) {
          extractItemsFromJson(elem, results, maxDepth - 1, maxItems)
        }
      }
    }
  }
}

/**
 * 格式化价格
 */
function formatPrice(val) {
  if (typeof val === 'number') {
    // 大于 1000000 的可能是以"分"为单位的，需要除以 100
    if (val > 1000000) val = val / 100
    return val.toFixed(2)
  }
  // 处理数组类型价格（如 [{"text":"¥","type":"sign"},{"text":"28","type":"integer"},{"text":"88","type":"decimal"}]）
  if (Array.isArray(val)) {
    let sign = ''
    let integer = ''
    let decimal = ''
    for (const item of val) {
      if (!item || typeof item !== 'object') continue
      const text = String(item.text || '')
      const typ = item.type || ''
      if (typ === 'sign') sign = text
      else if (typ === 'integer') integer = text
      else if (typ === 'decimal') decimal = text
    }
    if (integer) {
      return decimal ? `${sign}${integer}.${decimal}` : `${sign}${integer}`
    }
    // 回退：拼接所有 text
    return val.map(item => (item && typeof item === 'object' ? String(item.text || '') : '')).join('')
  }
  const str = String(val).trim()
  // 纯数字字符串
  if (/^\d+$/.test(str)) {
    const num = parseInt(str, 10)
    if (num > 1000000) return (num / 100).toFixed(2)
    return num.toFixed(2)
  }
  // 已有的价格格式
  return str
}

/**
 * 规范化图片 URL：过滤占位图，补全协议
 */
function normalizeImageUrl(val) {
  if (val == null) return ''
  let url = String(val).trim()
  if (!url) return ''

  // 过滤黑名单
  const lower = url.toLowerCase()
  for (const black of IMAGE_BLACKLIST) {
    if (lower.includes(black)) return ''
  }

  // 补全协议
  if (url.startsWith('//')) {
    url = 'https:' + url
  }
  return url
}

/**
 * 规范化商品链接
 */
function normalizeItemUrl(val) {
  if (val == null) return ''
  let url = String(val).trim()
  if (!url) return ''

  // 相对路径补全
  if (url.startsWith('/')) {
    url = 'https://www.goofish.com' + url
  } else if (!url.startsWith('http') && !url.startsWith('//')) {
    return '' // 非法 URL
  }

  if (url.startsWith('//')) {
    url = 'https:' + url
  }

  return url
}

/**
 * 去重：按 link > itemId > title+price 优先级
 */
function deduplicate(items) {
  const seen = new Set()
  return items.filter(item => {
    let key
    if (item.link) {
      key = `url:${item.link}`
    } else if (item.itemId) {
      key = `id:${item.itemId}`
    } else {
      key = `combo:${item.title}|${item.price}`
    }
    if (key.length < 5) return false // 过滤过于模糊的 key
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/**
 * 检查 HTML 文本是否包含阻断关键词
 */
function checkBlocked(bodyText) {
  for (const kw of BLOCK_KEYWORDS) {
    if (bodyText.includes(kw)) {
      return kw
    }
  }
  return null
}

/**
 * 从 HTML 文本中提取所有 <script> 标签内的 JSON 数据
 * 优先匹配常见的状态注入模式
 */
function extractScriptJson(html) {
  const results = []

  // 模式 1: window.__xxx__ = {...} 或 __NUXT__={...} 等
  const statePatterns = [
    /window\.__(?:INITIAL|PRELOADED|DATA|STATE)__\s*=\s*({[\s\S]*?});/gi,
    /__NUXT__\s*=\s*({[\s\S]*?});/gi,
    /window\.__NUXT__\s*=\s*({[\s\S]*?});/gi,
    /window\.__NEXT_DATA__\s*=\s*({[\s\S]*?});/gi,
    /__NEXT_DATA__\s*=\s*({[\s\S]*?});/gi,
  ]

  for (const pattern of statePatterns) {
    let match
    while ((match = pattern.exec(html)) !== null) {
      try {
        const json = JSON.parse(match[1])
        results.push(json)
      } catch { /* JSON 解析失败，继续下一个 */ }
    }
  }

  // 模式 2: <script type="application/json"> 或 <script type="application/ld+json">
  const jsonScriptRegex = /<script[^>]*type="(?:application\/json|application\/ld\+json)"[^>]*>([\s\S]*?)<\/script>/gi
  let match
  while ((match = jsonScriptRegex.exec(html)) !== null) {
    try {
      const json = JSON.parse(match[1])
      results.push(json)
    } catch { /* JSON 解析失败 */ }
  }

  // 模式 3: <script id="__NEXT_DATA__" 或类似
  const nextDataRegex = /<script[^>]*id="__(?:NEXT|NUXT)_DATA__"[^>]*>([\s\S]*?)<\/script>/gi
  while ((match = nextDataRegex.exec(html)) !== null) {
    try {
      const json = JSON.parse(match[1])
      results.push(json)
    } catch { /* JSON 解析失败 */ }
  }

  return results
}

/**
 * 从 HTML DOM 中提取商品信息（兜底解析）
 * 查找包含商品特征的元素
 */
function extractFromHtml(htmlText) {
  const items = []

  // 寻找 href 包含 /item/ 或 /goods/ 的链接
  const itemLinkRegex = /<a[^>]*href="(\/[^"]*(?:item|goods|detail)\/[^"]*)"[^>]*>([\s\S]*?)<\/a>/gi
  let match
  while ((match = itemLinkRegex.exec(htmlText)) !== null && items.length < 50) {
    const href = match[1]
    const innerHtml = match[2]

    // 提取 img src
    const imgMatch = innerHtml.match(/<img[^>]*src="([^"]*)"[^>]*>/i)
    const imageUrl = imgMatch ? normalizeImageUrl(imgMatch[1]) : ''

    // 提取文字标题（去掉 HTML 标签）
    const title = innerHtml.replace(/<[^>]*>/g, '').trim().substring(0, 200)

    if (title && title.length >= 2) {
      items.push({
        title,
        price: '',
        image: imageUrl,
        link: normalizeItemUrl(href),
        itemId: extractItemIdFromUrl(href),
        description: '',
      })
    }
  }

  return items
}

function extractItemIdFromUrl(url) {
  const m = url.match(/[?&]id=(\d+)/) || url.match(/\/(\d+)$/)
  return m ? m[1] : ''
}

/**
 * 主体搜索函数
 * @param {string} keyword - 用户输入关键词
 * @returns {Promise<{ok: boolean, items?: Array, error?: string, total?: number}>}
 */
export async function searchGoofish(keyword) {
  // 1. 输入验证
  const validation = validateKeyword(keyword)
  if (!validation.valid) {
    return { ok: false, error: validation.error }
  }

  const url = buildSearchUrl(validation.keyword)
  console.log('[GoofishSearch] 搜索 URL:', url)

  let response
  try {
    // 2. 发起请求（通过 Vite 代理，设置较宽松的超时）
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 25000)

    response = await fetch(url, {
      headers: {
        'Accept': 'text/html,application/json,*/*',
        'User-Agent': navigator.userAgent,
      },
      signal: controller.signal,
    })
    clearTimeout(timeoutId)
  } catch (err) {
    if (err.name === 'AbortError') {
      return {
        ok: false,
        error: '搜索请求超时，请检查网络连接或稍后重试。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。'
      }
    }
    // CORS 或其他网络错误
    if (err.message && (err.message.includes('Failed to fetch') || err.message.includes('NetworkError'))) {
      return {
        ok: false,
        error: '网络请求失败，可能是 CORS 限制或网络不可达。请确保开发环境已配置代理。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。'
      }
    }
    return { ok: false, error: err.message || '未知网络错误' }
  }

  // 3. 处理 HTTP 错误状态
  if (!response.ok) {
    const mappedError = HTTP_ERROR_MAP[response.status]
    if (mappedError) {
      return { ok: false, error: mappedError }
    }
    return {
      ok: false,
      error: `请求失败（HTTP ${response.status}）。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。`
    }
  }

  // 4. 获取响应文本
  let html
  try {
    html = await response.text()
  } catch {
    return { ok: false, error: '无法读取响应数据。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。' }
  }

  if (!html || html.length < 100) {
    return { ok: false, error: 'Goofish 返回了空响应，可能触发了安全验证。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。' }
  }

  // 5. 检查阻断关键词
  const blocked = checkBlocked(html)
  if (blocked) {
    return {
      ok: false,
      error: `Goofish 页面检测到「${blocked}」提示，当前无法获取公开数据。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。`
    }
  }

  // 6. 尝试提取内嵌 JSON 数据
  const jsonDataList = extractScriptJson(html)
  console.log('[GoofishSearch] 提取到 JSON 数据块:', jsonDataList.length)

  const rawItems = []

  // 从 JSON 数据中提取商品
  for (const data of jsonDataList) {
    if (rawItems.length >= 50) break
    extractItemsFromJson(data, rawItems, 15, 50)
  }

  // 7. 如果 JSON 未提取到商品，使用 DOM 兜底
  if (rawItems.length === 0) {
    console.log('[GoofishSearch] JSON 未提取到商品，尝试 DOM 解析')
    const domItems = extractFromHtml(html)
    rawItems.push(...domItems)
  }

  // 8. 去重
  const uniqueItems = deduplicate(rawItems)

  // 限制最多 50 条
  const finalItems = uniqueItems.slice(0, 50)

  console.log(`[GoofishSearch] 完成: 关键词="${keyword}", 原始=${rawItems.length}, 去重后=${uniqueItems.length}, 最终=${finalItems.length}`)

  if (finalItems.length === 0) {
    return {
      ok: true,
      items: [],
      total: 0,
      message: '未找到相关商品，请尝试其他关键词。本功能仅展示当前接口可返回的公开商品数据，不承诺抓取所有商品。'
    }
  }

  return {
    ok: true,
    items: finalItems,
    total: finalItems.length,
  }
}
