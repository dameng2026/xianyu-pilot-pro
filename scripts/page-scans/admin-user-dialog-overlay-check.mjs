import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const outputDir = path.join(repoRoot, 'output', 'playwright')
const playwrightEntry = path.join(repoRoot, 'apps', 'crawler-service', 'node_modules', 'playwright', 'index.js')

function parseArgs(argv) {
  return {
    headed: argv.includes('--headed')
  }
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

async function getAdminToken(config) {
  const adminBase = config.smoke.admin_frontend_base.replace(/\/$/, '')
  const login = await requestJson(`${adminBase}/admin-api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config.smoke.admin_credentials)
  })
  if (!login.ok || login.data?.code !== 200 || !login.data?.data?.token) {
    throw new Error(`admin login failed: HTTP ${login.status} ${login.text.slice(0, 200)}`)
  }
  return login.data.data.token
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
  page.on('console', (message) => {
    const type = String(message.type() || '').toLowerCase()
    if (type === 'error') {
      console.error(`[browser:${type}] ${message.text()}`)
    }
  })
  page.on('pageerror', (error) => {
    console.error(`[pageerror] ${error?.message || String(error)}`)
  })

  await page.goto(`${adminBase}/#/admin/user-permission/users`, {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(1500)
  return { context, page }
}

async function findCreatedUserId(adminBase, token, username) {
  const result = await requestJson(
    `${adminBase}/admin-api/admin/users?current=1&size=20&keyword=${encodeURIComponent(username)}&status=`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  const records = result.data?.data?.records || []
  const user = records.find((item) => item?.username === username)
  return user?.id || null
}

async function deleteUser(adminBase, token, id) {
  const result = await requestJson(`${adminBase}/admin-api/admin/modules/users/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  })
  return result.ok && result.data?.code === 200
}

async function collectOverlayState(page) {
  return page.evaluate(() => {
    const overlayNodes = Array.from(document.querySelectorAll('.el-overlay'))
    const visibleOverlayNodes = overlayNodes.filter((node) => {
      const style = window.getComputedStyle(node)
      const rect = node.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || '1') > 0 && rect.width > 0 && rect.height > 0
    })
    const dialogNodes = Array.from(document.querySelectorAll('.el-dialog'))
    const visibleDialogNodes = dialogNodes.filter((node) => {
      const style = window.getComputedStyle(node)
      const rect = node.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    })
    return {
      bodyClassName: document.body.className,
      bodyOverflow: window.getComputedStyle(document.body).overflow,
      overlayCount: overlayNodes.length,
      visibleOverlayCount: visibleOverlayNodes.length,
      dialogCount: dialogNodes.length,
      visibleDialogCount: visibleDialogNodes.length,
      overlayHtml: visibleOverlayNodes.map((node) => node.outerHTML.slice(0, 240))
    }
  })
}

function hasBlockingOverlay(state) {
  return state.visibleOverlayCount > 0
    || state.visibleDialogCount > 0
    || state.bodyClassName.includes('el-popup-parent--hidden')
    || state.bodyOverflow === 'hidden'
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (!fs.existsSync(configPath)) {
    throw new Error(`deploy config not found: ${configPath}`)
  }

  fs.mkdirSync(outputDir, { recursive: true })
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const adminBase = config.smoke.admin_frontend_base.replace(/\/$/, '')
  const adminToken = await getAdminToken(config)
  const playwrightModule = await loadPlaywright()
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium
  if (!chromium) {
    throw new Error('playwright chromium launcher not found')
  }

  const browser = await chromium.launch({ headless: !options.headed })
  const username = `codex_overlay_${Date.now()}`
  const password = 'Codex1234'
  const screenshotPath = path.join(outputDir, `admin-user-dialog-overlay-${Date.now()}.png`)
  let createdUserId = null

  try {
    const { context, page } = await createAdminPage(browser, adminBase, adminToken)
    try {
      await page.getByRole('button', { name: '新增用户' }).click()
      await page.locator('.el-dialog').filter({ hasText: '新增用户' }).waitFor({ state: 'visible', timeout: 10000 })

      await page.getByPlaceholder('请输入登录账号').fill(username)
      await page.getByPlaceholder('请输入密码').fill(password)
      await page.getByPlaceholder('请再次输入密码').fill(password)
      await page.getByPlaceholder('请输入昵称').fill('Codex Overlay Check')

      const createResponsePromise = page.waitForResponse((response) =>
        response.url().includes('/admin-api/admin/modules/users') && response.request().method() === 'POST',
      { timeout: 15000 })

      await page.getByRole('button', { name: '确定' }).click()
      const createResponse = await createResponsePromise
      const createBody = await createResponse.json().catch(() => null)

      await page.waitForTimeout(2000)
      const overlayStateAfterSubmit = await collectOverlayState(page)
      const successToastVisible = await page.locator('.el-message--success').count()
      const dialogNodeCount = await page.locator('.el-dialog').filter({ hasText: '新增用户' }).count()

      createdUserId = createBody?.data?.id || await findCreatedUserId(adminBase, adminToken, username)

      await page.goto(`${adminBase}/#/admin/dashboard/overview`, {
        waitUntil: 'domcontentloaded',
        timeout: 30000
      })
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(1500)
      const overlayStateAfterRouteChange = await collectOverlayState(page)

      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(1500)
      const overlayStateAfterReload = await collectOverlayState(page)

      const failed = hasBlockingOverlay(overlayStateAfterSubmit)
        || hasBlockingOverlay(overlayStateAfterRouteChange)
        || hasBlockingOverlay(overlayStateAfterReload)
      if (failed) {
        await page.screenshot({ path: screenshotPath, fullPage: true })
      }

      const report = {
        ok: !failed,
        username,
        createdUserId,
        createResponseStatus: createResponse.status(),
        createResponseCode: createBody?.code ?? null,
        successToastVisible,
        dialogNodeCount,
        overlayStateAfterSubmit,
        overlayStateAfterRouteChange,
        overlayStateAfterReload,
        screenshotPath: failed ? screenshotPath : null
      }

      process.stdout.write(JSON.stringify(report, null, 2))
    } finally {
      await context.close()
    }
  } finally {
    if (createdUserId) {
      await deleteUser(adminBase, adminToken, createdUserId).catch(() => {})
    }
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error))
  process.exitCode = 1
})
