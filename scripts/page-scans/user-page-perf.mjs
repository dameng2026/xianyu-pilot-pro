import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const outputDir = path.join(repoRoot, 'output', 'playwright')
const playwrightEntry = path.join(repoRoot, 'apps', 'crawler-service', 'node_modules', 'playwright', 'index.js')

const defaultRoutes = [
  'dashboard',
  'data',
  'accounts',
  'products',
  'orders',
  'messages',
  'profile'
]

const routeRootSelectors = {
  dashboard: '.dashboard-page',
  data: '.toolbar',
  accounts: '.grid.wide-right',
  products: '.products-page',
  orders: '.sync-tip',
  messages: '.xya-msg-page',
  profile: '.profile-center'
}

const routeWarmSelectors = {
  dashboard: '.dashboard-page .events-box, .dashboard-page .events-empty',
  data: '.grid.stat-grid',
  accounts: '.grid.wide-right .base-table tbody tr, .grid.wide-right .global-notice',
  products: '.products-page .products-table tbody tr, .products-page .products-table-card .global-notice, .products-page .products-table-card',
  orders: '.sync-tip',
  messages: '.xya-msg-conversation, .xya-msg-empty.big, .xya-msg-chat-head',
  profile: '.profile-center .profile-shell'
}

const ignoredApiPatterns = [
  /\/api\/sse\//i,
  /favicon/i
]

function parseArgs(argv) {
  const options = {
    routes: [...defaultRoutes],
    thresholdMs: 3000,
    waitIdleMs: 900,
    headed: false,
    baseUrl: ''
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--routes' && argv[index + 1]) {
      options.routes = argv[index + 1]
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
      index += 1
      continue
    }
    if (arg === '--threshold-ms' && argv[index + 1]) {
      options.thresholdMs = Number(argv[index + 1]) || options.thresholdMs
      index += 1
      continue
    }
    if (arg === '--wait-idle-ms' && argv[index + 1]) {
      options.waitIdleMs = Number(argv[index + 1]) || options.waitIdleMs
      index += 1
      continue
    }
    if (arg === '--headed') {
      options.headed = true
      continue
    }
    if (arg === '--base-url' && argv[index + 1]) {
      options.baseUrl = String(argv[index + 1]).trim()
      index += 1
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

function isTrackedApi(url) {
  const text = String(url || '')
  if (!/\/api\//i.test(text)) return false
  return !ignoredApiPatterns.some(pattern => pattern.test(text))
}

function sanitizeRoute(route) {
  return String(route)
    .replace(/^#?\//, '')
    .replace(/[\\/:*?"<>|#]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '') || 'root'
}

function roundMs(value) {
  return Math.round(Number(value) || 0)
}

function summarizeApiRequests(requests = [], limit = 8) {
  return [...requests]
    .sort((left, right) => right.durationMs - left.durationMs)
    .slice(0, limit)
    .map(item => ({
      method: item.method,
      status: item.status,
      durationMs: roundMs(item.durationMs),
      url: item.url
    }))
}

function createNetworkTracker(page) {
  let sequence = 0
  let activeCount = 0
  const inflight = new Map()
  const records = []

  const begin = (request) => {
    const url = request.url()
    if (!isTrackedApi(url)) return
    const startedAt = Date.now()
    const key = `${startedAt}-${sequence += 1}-${request.method()}-${url}`
    inflight.set(request, {
      key,
      method: request.method(),
      url,
      startedAt
    })
    activeCount += 1
  }

  const finish = async (request, failed = false) => {
    const item = inflight.get(request)
    if (!item) return
    inflight.delete(request)
    activeCount = Math.max(0, activeCount - 1)

    let status = failed ? 0 : null
    try {
      const response = await request.response()
      if (response) status = response.status()
    } catch {
      // Ignore missing responses for failed/aborted requests.
    }

    records.push({
      ...item,
      status,
      failed,
      finishedAt: Date.now(),
      durationMs: Date.now() - item.startedAt
    })
  }

  page.on('request', begin)
  page.on('requestfinished', request => {
    finish(request).catch(() => {})
  })
  page.on('requestfailed', request => {
    finish(request, true).catch(() => {})
  })

  return {
    getActiveCount() {
      return activeCount
    },
    snapshot(startedAt, finishedAt) {
      return records.filter(item => item.startedAt >= startedAt && item.finishedAt <= finishedAt)
    }
  }
}

async function collectPageState(page) {
  return page.evaluate(() => ({
    href: location.href,
    title: document.title,
    loadingVisible: Boolean(document.querySelector('.page-loading, .boot-screen')),
    errorVisible: Boolean(document.querySelector('.page-load-error, .global-notice.error')),
    bodySample: (document.body?.innerText || '').trim().slice(0, 200)
  }))
}

async function waitForRouteSettled(page, tracker, waitIdleMs, timeoutMs = 30000) {
  const startedAt = Date.now()
  let idleSince = Date.now()

  while ((Date.now() - startedAt) < timeoutMs) {
    const state = await collectPageState(page)
    const activeRequests = tracker.getActiveCount()
    const busy = state.loadingVisible || activeRequests > 0

    if (busy) {
      idleSince = Date.now()
    } else if ((Date.now() - idleSince) >= waitIdleMs) {
      return state
    }

    await page.waitForTimeout(120)
  }

  return collectPageState(page)
}

async function waitForRouteVisible(page, route) {
  const rootSelector = routeRootSelectors[route]
  if (rootSelector) {
    await page.waitForSelector(rootSelector, {
      state: 'visible',
      timeout: 30000
    }).catch(() => {})
  }

  const warmSelector = routeWarmSelectors[route]
  if (warmSelector) {
    await page.waitForSelector(warmSelector, {
      state: 'attached',
      timeout: 15000
    }).catch(() => {})
  }
}

async function login(baseUrl, credentials) {
  const result = await requestJson(`${baseUrl}/api/login/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials)
  })

  if (!result.ok || result.data?.code !== 200 || !result.data?.data?.token) {
    throw new Error(`user login failed: http=${result.status} code=${result.data?.code ?? 'unknown'}`)
  }

  return {
    token: result.data.data.token,
    username: result.data.data.username || credentials.username
  }
}

async function scanRoute(page, tracker, baseUrl, route, waitIdleMs, thresholdMs) {
  const startedAt = Date.now()
  await page.goto(`${baseUrl}/#/${route}`, {
    waitUntil: 'domcontentloaded',
    timeout: 45000
  })
  await waitForRouteVisible(page, route)
  const pageState = await waitForRouteSettled(page, tracker, waitIdleMs)
  const finishedAt = Date.now()
  const routeDurationMs = finishedAt - startedAt
  const apiRequests = tracker.snapshot(startedAt, finishedAt)
  const slowApis = summarizeApiRequests(apiRequests)
  const slow = routeDurationMs > thresholdMs
  const hasError = Boolean(pageState.errorVisible)

  return {
    route,
    routeDurationMs: roundMs(routeDurationMs),
    thresholdMs,
    slow,
    hasError,
    pageState,
    apiRequestCount: apiRequests.length,
    slowApis
  }
}

async function main() {
  if (!fs.existsSync(configPath)) {
    throw new Error(`deploy config not found: ${configPath}`)
  }

  fs.mkdirSync(outputDir, { recursive: true })

  const options = parseArgs(process.argv.slice(2))
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const userBase = (options.baseUrl || config.smoke.user_frontend_base).replace(/\/$/, '')
  const auth = await login(userBase, config.smoke.user_credentials)
  const playwrightModule = await loadPlaywright()
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium
  if (!chromium) {
    throw new Error('playwright chromium launcher not found')
  }

  const browser = await chromium.launch({ headless: !options.headed })
  const results = []

  try {
    for (const route of options.routes) {
      const context = await browser.newContext({ ignoreHTTPSErrors: true })
      await context.addInitScript(({ tokenValue, usernameValue }) => {
        localStorage.setItem('xianyu_auth_token', tokenValue)
        localStorage.setItem('xianyu_username', usernameValue)
      }, { tokenValue: auth.token, usernameValue: auth.username })

      const page = await context.newPage()
      const tracker = createNetworkTracker(page)

      try {
        const result = await scanRoute(page, tracker, userBase, route, options.waitIdleMs, options.thresholdMs)

        if (result.slow || result.hasError) {
          const screenshotPath = path.join(outputDir, `user-perf-${sanitizeRoute(route)}.png`)
          await page.screenshot({ path: screenshotPath, fullPage: true })
          result.screenshotPath = screenshotPath
        }

        results.push(result)
        process.stdout.write(JSON.stringify({
          route: result.route,
          routeDurationMs: result.routeDurationMs,
          apiRequestCount: result.apiRequestCount,
          slow: result.slow,
          hasError: result.hasError,
          slowestApi: result.slowApis[0] || null
        }) + '\n')
      } finally {
        await context.close()
      }
    }
  } finally {
    await browser.close()
  }

  const report = {
    scannedAt: new Date().toISOString(),
    baseUrl: userBase,
    thresholdMs: options.thresholdMs,
    waitIdleMs: options.waitIdleMs,
    routes: options.routes,
    results
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const reportPath = path.join(outputDir, `user-page-perf-${stamp}.json`)
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8')

  const slowRoutes = results.filter(item => item.slow || item.hasError)
  const summary = {
    reportPath,
    routeCount: results.length,
    slowRouteCount: slowRoutes.length,
    slowRoutes: slowRoutes.map(item => ({
      route: item.route,
      routeDurationMs: item.routeDurationMs,
      hasError: item.hasError,
      slowestApi: item.slowApis[0] || null
    }))
  }

  process.stdout.write(JSON.stringify(summary, null, 2))

  if (slowRoutes.length > 0) {
    process.exitCode = 1
  }
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error))
  process.exitCode = 1
})
