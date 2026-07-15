async page => {
  const baseUrl = 'http://154.9.254.86:81'
  const routes = [
    'dashboard',
    'data',
    'accounts',
    'connections',
    'products',
    'orders',
    'product-publish',
    'opportunities',
    'messages',
    'workflow',
    'workflow-tasks',
    'auto-delivery',
    'delivery-source-library',
    'delivery-statement',
    'delivery-templates',
    'card-warehouse',
    'delivery-records',
    'scheduled-tasks',
    'auto-reply',
    'logs',
    'feedback',
    'settings-notify',
    'settings-ai-cs',
    'settings-product',
    'settings-about',
    'vip',
    'profile'
  ]

  const issues = []
  let currentRoute = 'login'

  const ignoredConsolePatterns = [
    /favicon/i,
    /DevTools/i,
    /ResizeObserver loop limit exceeded/i
  ]
  const ignoredRequestPatterns = [
    /\/api\/sse\/subscribe/i
  ]

  function shouldIgnore(patterns, text) {
    return patterns.some((pattern) => pattern.test(text))
  }

  function record(type, detail) {
    issues.push({
      route: currentRoute,
      type,
      detail
    })
  }

  page.removeAllListeners('pageerror')
  page.removeAllListeners('console')
  page.removeAllListeners('requestfailed')
  page.removeAllListeners('response')

  page.on('pageerror', error => {
    record('pageerror', error?.message || String(error))
  })

  page.on('console', message => {
    const text = message.text() || ''
    if (!['error', 'warning'].includes(message.type())) return
    if (shouldIgnore(ignoredConsolePatterns, text)) return
    record(`console:${message.type()}`, text)
  })

  page.on('requestfailed', request => {
    const url = request.url()
    if (shouldIgnore(ignoredRequestPatterns, url)) return
    record('requestfailed', `${request.method()} ${url} :: ${request.failure()?.errorText || 'unknown'}`)
  })

  page.on('response', response => {
    const status = response.status()
    if (status < 400) return
    const url = response.url()
    if (/\/api\/sse\/subscribe/i.test(url)) return
    if (status === 404 && /favicon/i.test(url)) return
    record('response', `${status} ${response.request().method()} ${url}`)
  })

  async function collectDomErrors() {
    return page.evaluate(() => {
      const selectors = [
        '.global-notice.error',
        '.page-load-error',
        '.form-error',
        '.input-error',
        '[role="alert"]'
      ]
      const texts = []
      for (const selector of selectors) {
        for (const node of document.querySelectorAll(selector)) {
          const text = (node.textContent || '').trim()
          if (text) texts.push(text)
        }
      }
      return Array.from(new Set(texts)).filter(text => {
        return /失败|错误|异常|繁忙|超时|无权限|不可用|加载中\.\.\./.test(text)
      })
    })
  }

  async function waitForPageSettled() {
    await page.waitForTimeout(1800)
    await page.waitForFunction(() => !document.querySelector('.boot-screen'), { timeout: 15000 }).catch(() => {})
  }

  currentRoute = 'login'
  await page.goto(`${baseUrl}/#/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill('slfasd')
  await page.locator('input[autocomplete="current-password"]').fill('slfasd123')
  await page.locator('button.auth-submit').click()
  await page.waitForFunction(() => location.hash && location.hash !== '#/login', { timeout: 15000 })
  await waitForPageSettled()

  for (const route of routes) {
    currentRoute = route
    await page.goto(`${baseUrl}/#/${route}`, { waitUntil: 'domcontentloaded' })
    await waitForPageSettled()

    const domErrors = await collectDomErrors()
    for (const text of domErrors) {
      record('dom', text)
    }
  }

  return {
    scannedRoutes: routes.length,
    issueCount: issues.length,
    issues
  }
}
