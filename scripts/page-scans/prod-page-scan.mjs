import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const outputDir = path.join(repoRoot, 'output', 'playwright')
const playwrightEntry = path.join(repoRoot, 'apps', 'crawler-service', 'node_modules', 'playwright', 'index.js')

const adminRoutes = [
  '/admin/dashboard/overview',
  '/admin/user-permission/users',
  '/admin/billing/plans',
  '/admin/billing/payment-config',
  '/admin/billing/licenses',
  '/admin/xianyu-business/accounts',
  '/admin/xianyu-business/goods',
  '/admin/xianyu-business/orders',
  '/admin/xianyu-business/messages',
  '/admin/xianyu-business/delivery',
  '/admin/xianyu-business/auto-reply',
  '/admin/xianyu-business/kami',
  '/admin/ai/model-config',
  '/admin/ai/pricing',
  '/admin/ai/monitor',
  '/admin/ai/usage',
  '/admin/ai/token',
  '/admin/ai/image-prompt-categories',
  '/admin/ai/rag',
  '/admin/ai/sensitive-words',
  '/admin/data-stats/hot-goods',
  '/admin/risk-notify/channels',
  '/admin/risk-notify/notify-logs',
  '/admin/risk-notify/risk-events',
  '/admin/risk-notify/alerts',
  '/admin/ops/settings',
  '/admin/ops/audit-logs',
  '/admin/ops/client-errors',
  '/admin/ops/runtime',
  '/admin/ops/backups',
  '/admin/ops/files',
  '/admin/ops/versions',
  '/admin/content/carousel',
  '/admin/content/announcement',
  '/admin/content/feedback',
  '/system/user-center'
]

const userRoutes = [
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
  'card-warehouse',
  'auto-delivery',
  'delivery-source-library',
  'delivery-statement',
  'delivery-templates',
  'delivery-records',
  'scheduled-tasks',
  'auto-reply',
  'logs',
  'feedback',
  'settings-notify',
  'settings-ai-cs',
  'settings-about',
  'vip',
  'profile'
]

const ignoredConsolePatterns = [
  /favicon/i,
  /DevTools/i,
  /ResizeObserver loop limit exceeded/i,
  /GitHub/i,
  /QQ群/i
]

const ignoredRequestPatterns = [
  /\/api\/sse\/subscribe/i,
  /favicon/i
]

function parseArgs(argv) {
  const options = {
    scope: 'all',
    limit: 0,
    waitMs: 4500,
    headed: false
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--scope' && argv[index + 1]) {
      options.scope = argv[index + 1]
      index += 1
      continue
    }
    if (arg === '--limit' && argv[index + 1]) {
      options.limit = Number(argv[index + 1]) || 0
      index += 1
      continue
    }
    if (arg === '--wait-ms' && argv[index + 1]) {
      options.waitMs = Number(argv[index + 1]) || options.waitMs
      index += 1
      continue
    }
    if (arg === '--headed') {
      options.headed = true
    }
  }

  return options
}

async function loadPlaywright() {
  if (!fs.existsSync(playwrightEntry)) {
    throw new Error(`playwright entry not found: ${playwrightEntry}`)
  }
  return import(pathToFileURL(playwrightEntry).href)
}

async function requestJson(url, { method = 'GET', headers = {}, body } = {}) {
  const response = await fetch(url, {
    method,
    headers: {
      Accept: 'application/json, text/plain, */*',
      ...headers
    },
    body
  })
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  return {
    ok: response.ok,
    status: response.status,
    text,
    data
  }
}

function sanitizeRoute(route) {
  return String(route)
    .replace(/^#?\//, '')
    .replace(/[\\/:*?"<>|#]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '') || 'root'
}

function createCaptureBucket() {
  return {
    pageErrors: [],
    consoleMessages: [],
    requestFailures: [],
    responseFailures: []
  }
}

function attachCapture(page) {
  const state = { current: createCaptureBucket() }

  page.on('pageerror', (error) => {
    state.current.pageErrors.push(error?.message || String(error))
  })

  page.on('console', (message) => {
    const type = String(message.type() || '').toLowerCase()
    const text = String(message.text() || '')
    state.current.consoleMessages.push({ type, text })
  })

  page.on('requestfailed', (request) => {
    state.current.requestFailures.push({
      method: request.method(),
      url: request.url(),
      errorText: request.failure()?.errorText || 'unknown'
    })
  })

  page.on('response', (response) => {
    const status = response.status()
    if (status < 400) return
    state.current.responseFailures.push({
      method: response.request().method(),
      url: response.url(),
      status
    })
  })

  return {
    reset() {
      state.current = createCaptureBucket()
    },
    read() {
      return state.current
    }
  }
}

function filterConsoleMessages(messages = []) {
  return messages.filter((message) => {
    if (!['error', 'warning'].includes(String(message.type || '').toLowerCase())) return false
    return !ignoredConsolePatterns.some((pattern) => pattern.test(String(message.text || '')))
  })
}

function filterRequestFailures(failures = []) {
  return failures.filter((failure) => {
    const url = String(failure.url || '')
    const errorText = String(failure.errorText || '')
    if (/ERR_ABORTED|NS_BINDING_ABORTED/i.test(errorText)) {
      return false
    }
    return !ignoredRequestPatterns.some((pattern) => pattern.test(url))
  })
}

function filterResponseFailures(failures = []) {
  return failures.filter((failure) => {
    const url = String(failure.url || '')
    return !ignoredRequestPatterns.some((pattern) => pattern.test(url))
  })
}

async function collectPageState(page, route, kind) {
  return page.evaluate(({ expectedRoute, pageKind }) => {
    const selectors = [
      '.global-notice.error',
      '.global-notice.warn',
      '.page-load-error',
      '.el-message--error',
      '.el-notification--error .el-notification__content',
      '.el-alert--error',
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
    const alertTexts = Array.from(new Set(texts)).filter((text) =>
      /失败|错误|异常|繁忙|超时|不可用|未授权|加载|404|500|error/i.test(text)
    )
    const loginHint = pageKind === 'admin' ? '/auth/login' : '#/login'
    return {
      expectedRoute,
      href: location.href,
      title: document.title,
      heading: (document.querySelector('h1, h2, h3')?.textContent || '').trim(),
      bodyTextSample: (document.body?.innerText || '').trim().slice(0, 300),
      bootVisible: !!document.querySelector('.boot-screen'),
      loadErrorVisible: !!document.querySelector('.page-load-error'),
      alertTexts,
      onLoginPage: location.href.includes(loginHint)
    }
  }, { expectedRoute: route, pageKind: kind })
}

function routeHasIssue(result) {
  return result.pageState.onLoginPage
    || result.pageState.bootVisible
    || result.pageState.loadErrorVisible
    || result.pageState.alertTexts.length > 0
    || result.pageErrors.length > 0
    || result.consoleMessages.length > 0
    || result.requestFailures.length > 0
    || result.responseFailures.length > 0
}

async function waitForRouteSettled(page, waitMs) {
  await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {})
  await page.waitForTimeout(waitMs)
  await page.waitForFunction(() => !document.querySelector('.boot-screen'), { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(400)
}

async function runRouteScan(page, capture, url, route, kind, waitMs) {
  capture.reset()
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await waitForRouteSettled(page, waitMs)

  const pageState = await collectPageState(page, route, kind)
  const captured = capture.read()

  return {
    route,
    kind,
    url,
    pageState,
    pageErrors: captured.pageErrors,
    consoleMessages: filterConsoleMessages(captured.consoleMessages),
    requestFailures: filterRequestFailures(captured.requestFailures),
    responseFailures: filterResponseFailures(captured.responseFailures)
  }
}

async function runApiChecks(config) {
  const checks = []
  const chinaBase = config.smoke.china_backend_base.replace(/\/$/, '')
  const userBase = config.smoke.user_frontend_base.replace(/\/$/, '')
  const adminBase = config.smoke.admin_frontend_base.replace(/\/$/, '')

  const userHealth = await requestJson(`${chinaBase}/api/health`)
  checks.push({ name: 'china-user-health', status: userHealth.status, ok: userHealth.ok })

  const adminHealth = await requestJson(`${chinaBase}/admin-api/health`)
  checks.push({ name: 'china-admin-health', status: adminHealth.status, ok: adminHealth.ok })

  const userLogin = await requestJson(`${userBase}/api/login/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config.smoke.user_credentials)
  })
  checks.push({
    name: 'user-login',
    status: userLogin.status,
    ok: userLogin.ok && userLogin.data?.code === 200
  })

  const adminLogin = await requestJson(`${adminBase}/admin-api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config.smoke.admin_credentials)
  })
  checks.push({
    name: 'admin-login',
    status: adminLogin.status,
    ok: adminLogin.ok && adminLogin.data?.code === 200
  })

  const adminToken = adminLogin.data?.data?.token || ''
  if (adminToken) {
    const billingSummary = await requestJson(`${adminBase}/admin-api/ai-billing/summary`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    })
    checks.push({
      name: 'admin-billing-summary',
      status: billingSummary.status,
      ok: billingSummary.ok && billingSummary.data?.code === 200
    })

    const modelPrices = await requestJson(`${adminBase}/admin-api/ai-billing/model-prices/page?current=1&size=20`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    })
    checks.push({
      name: 'admin-billing-model-prices',
      status: modelPrices.status,
      ok: modelPrices.ok && modelPrices.data?.code === 200
    })
  }

  const userToken = userLogin.data?.data?.token || ''
  if (userToken) {
    const accountList = await requestJson(`${userBase}/api/xianyu/accounts?page=1&pageSize=20`, {
      headers: { Authorization: `Bearer ${userToken}` }
    })
    const accountRecords = accountList.data?.data?.records || []
    checks.push({
      name: 'user-account-list',
      status: accountList.status,
      ok: accountList.ok && accountList.data?.code === 200 && Array.isArray(accountRecords)
    })

    const firstAccountId = accountRecords[0]?.id
    if (firstAccountId) {
      const onlineConversations = await requestJson(`${userBase}/api/msg/online/conversations?xianyuAccountId=${firstAccountId}&pageSize=5`, {
        headers: { Authorization: `Bearer ${userToken}` }
      })
      checks.push({
        name: 'user-online-conversations',
        status: onlineConversations.status,
        ok: onlineConversations.ok && onlineConversations.data?.code === 200
      })
    }
  }

  return { checks, adminToken, userToken }
}

async function createAdminPage(browser, adminBase, token) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true })
  await context.addInitScript(({ tokenValue }) => {
    localStorage.setItem('sys-version', '0.0.0')
    localStorage.setItem('sys-v0.0.0-user', JSON.stringify({
      language: 'zh',
      isLogin: true,
      isLock: false,
      lockPassword: '',
      info: {},
      searchHistory: [],
      accessToken: tokenValue,
      refreshToken: ''
    }))
  }, { tokenValue: token })

  const page = await context.newPage()
  const capture = attachCapture(page)
  await page.goto(`${adminBase}/#/admin/dashboard/overview`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await waitForRouteSettled(page, 5000)
  return { context, page, capture }
}

async function createUserPage(browser, userBase, username, token) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true })
  await context.addInitScript(({ tokenValue, usernameValue }) => {
    localStorage.setItem('xianyu_auth_token', tokenValue)
    localStorage.setItem('xianyu_username', usernameValue)
  }, { tokenValue: token, usernameValue: username })

  const page = await context.newPage()
  const capture = attachCapture(page)
  await page.goto(`${userBase}/#/dashboard`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await waitForRouteSettled(page, 5000)
  return { context, page, capture }
}

async function scanAdminRoutes(browser, config, options, adminToken) {
  const adminBase = config.smoke.admin_frontend_base.replace(/\/$/, '')
  const routesToScan = options.limit > 0 ? adminRoutes.slice(0, options.limit) : adminRoutes
  const { context, page, capture } = await createAdminPage(browser, adminBase, adminToken)

  try {
    const results = []
    for (const route of routesToScan) {
      const result = await runRouteScan(page, capture, `${adminBase}/#${route}`, route, 'admin', options.waitMs)
      if (routeHasIssue(result)) {
        const screenshotPath = path.join(outputDir, `admin-${sanitizeRoute(route)}.png`)
        await page.screenshot({ path: screenshotPath, fullPage: true })
        result.failureScreenshot = screenshotPath
      }
      results.push(result)
    }
    return results
  } finally {
    await context.close()
  }
}

async function scanUserRoutes(browser, config, options, userToken) {
  const userBase = config.smoke.user_frontend_base.replace(/\/$/, '')
  const routesToScan = options.limit > 0 ? userRoutes.slice(0, options.limit) : userRoutes
  const { context, page, capture } = await createUserPage(
    browser,
    userBase,
    config.smoke.user_credentials.username,
    userToken
  )

  try {
    const results = []
    for (const route of routesToScan) {
      const result = await runRouteScan(page, capture, `${userBase}/#/${route}`, route, 'user', options.waitMs)
      if (routeHasIssue(result)) {
        const screenshotPath = path.join(outputDir, `user-${sanitizeRoute(route)}.png`)
        await page.screenshot({ path: screenshotPath, fullPage: true })
        result.failureScreenshot = screenshotPath
      }
      results.push(result)
    }
    return results
  } finally {
    await context.close()
  }
}

function summarizeIssues(results = []) {
  return results
    .filter((item) => routeHasIssue(item))
    .map((item) => ({
      route: item.route,
      kind: item.kind,
      href: item.pageState.href,
      alertTexts: item.pageState.alertTexts,
      pageErrors: item.pageErrors,
      consoleMessages: item.consoleMessages,
      requestFailures: item.requestFailures,
      responseFailures: item.responseFailures,
      failureScreenshot: item.failureScreenshot || null
    }))
}

async function main() {
  if (!fs.existsSync(configPath)) {
    throw new Error(`deploy config not found: ${configPath}`)
  }
  fs.mkdirSync(outputDir, { recursive: true })

  const options = parseArgs(process.argv.slice(2))
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const playwrightModule = await loadPlaywright()
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium
  if (!chromium) {
    throw new Error('playwright chromium launcher not found')
  }
  const apiChecks = await runApiChecks(config)
  const browser = await chromium.launch({ headless: !options.headed })

  const result = {
    scannedAt: new Date().toISOString(),
    scope: options.scope,
    apiChecks: apiChecks.checks,
    admin: null,
    user: null,
    issues: []
  }

  try {
    if ((options.scope === 'all' || options.scope === 'admin') && apiChecks.adminToken) {
      result.admin = await scanAdminRoutes(browser, config, options, apiChecks.adminToken)
    }
    if ((options.scope === 'all' || options.scope === 'user') && apiChecks.userToken) {
      result.user = await scanUserRoutes(browser, config, options, apiChecks.userToken)
    }
  } finally {
    await browser.close()
  }

  result.issues = [
    ...summarizeIssues(result.admin || []),
    ...summarizeIssues(result.user || [])
  ]

  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const reportPath = path.join(outputDir, `prod-page-scan-${stamp}.json`)
  fs.writeFileSync(reportPath, JSON.stringify(result, null, 2), 'utf8')

  process.stdout.write(JSON.stringify({
    reportPath,
    apiChecksPassed: result.apiChecks.every((item) => item.ok),
    apiCheckCount: result.apiChecks.length,
    adminRouteCount: result.admin?.length || 0,
    userRouteCount: result.user?.length || 0,
    issueCount: result.issues.length
  }, null, 2))
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error))
  process.exitCode = 1
})
