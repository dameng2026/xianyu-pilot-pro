import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const outputDir = path.join(repoRoot, 'output', 'playwright')
const playwrightEntry = path.join(repoRoot, 'apps', 'crawler-service', 'node_modules', 'playwright', 'index.js')

const ignoredConsolePatterns = [
  /favicon/i,
  /DevTools/i,
  /ResizeObserver loop limit exceeded/i
]

const ignoredRequestPatterns = [
  /\/api\/sse\/subscribe/i,
  /favicon/i
]

function ensureOutputDir() {
  fs.mkdirSync(outputDir, { recursive: true })
}

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
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
    if (/ERR_ABORTED|NS_BINDING_ABORTED/i.test(errorText)) return false
    return !ignoredRequestPatterns.some((pattern) => pattern.test(url))
  })
}

function filterResponseFailures(failures = []) {
  return failures.filter((failure) => {
    const url = String(failure.url || '')
    return !ignoredRequestPatterns.some((pattern) => pattern.test(url))
  })
}

function summarizeApiResult(result) {
  const outer = result?.json || null
  const outerCode = outer?.code
  let businessCode = outerCode
  let message = outer?.msg || outer?.message || ''
  let data = outer?.data

  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'code')) {
    businessCode = data.code
    message = data.msg || data.message || message
    data = Object.prototype.hasOwnProperty.call(data, 'data') ? data.data : data
  }

  const ok = result?.status === 200 && (
    businessCode === 200 ||
    businessCode === 0 ||
    outer?.ok === true ||
    data?.ok === true
  )

  return {
    httpStatus: result?.status ?? 0,
    outerCode: outerCode ?? null,
    businessCode: businessCode ?? null,
    message,
    data,
    ok
  }
}

async function gotoHash(page, userBase, hash) {
  await page.goto(`${userBase}/#/${hash}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(2500)
}

async function waitForResponseJson(page, matcher, action, timeout = 30000) {
  const [response] = await Promise.all([
    page.waitForResponse((resp) => {
      try {
        return matcher(resp)
      } catch {
        return false
      }
    }, { timeout }),
    action()
  ])
  let text = ''
  let readError = ''
  try {
    text = await response.text()
  } catch (error) {
    readError = error?.message || String(error || '')
  }
  let json = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  return {
    url: response.url(),
    status: response.status(),
    text,
    readError,
    json
  }
}

async function waitForEnabledLocator(page, selector, timeout = 60000) {
  const locator = page.locator(selector).first()
  await locator.waitFor({ state: 'visible', timeout })
  await page.waitForFunction((targetSelector) => {
    return Array.from(document.querySelectorAll(targetSelector)).some((node) => {
      if (!(node instanceof HTMLElement)) return false
      return node.offsetParent !== null && !node.hasAttribute('disabled')
    })
  }, selector, { timeout })
  return locator
}

async function createUserPage(browser, userBase, username, token) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true })
  await context.addInitScript(({ tokenValue, usernameValue }) => {
    localStorage.setItem('xianyu_auth_token', tokenValue)
    localStorage.setItem('xianyu_username', usernameValue)
  }, { tokenValue: token, usernameValue: username })

  const page = await context.newPage()
  const capture = attachCapture(page)
  await gotoHash(page, userBase, 'dashboard')
  return { context, page, capture }
}

async function saveScreenshot(page, name) {
  const filePath = path.join(outputDir, `${name}-${stamp()}.png`)
  await page.screenshot({ path: filePath, fullPage: true })
  return filePath
}

async function verifyAiCs(page, capture, userBase) {
  capture.reset()
  await gotoHash(page, userBase, 'settings-ai-cs')
  const generateReplyButton = page.getByRole('button', { name: '生成回复' })
  await generateReplyButton.waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForFunction(() => {
    const button = Array.from(document.querySelectorAll('button')).find((node) => {
      return node instanceof HTMLElement && node.offsetParent !== null && /生成回复/.test(node.textContent || '')
    })
    return !!button && !button.hasAttribute('disabled')
  }, { timeout: 60000 })

  const response = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/business-settings/ai-customer-service/test') && resp.request().method() === 'POST',
    async () => {
      await generateReplyButton.click()
    },
    120000
  )

  await page.waitForTimeout(2000)
  const bubbleText = await page.locator('.aics-bubble').last().textContent().catch(() => '')
  const screenshot = await saveScreenshot(page, 'ai-cs-regression')
  const api = summarizeApiResult(response)
  const captureState = capture.read()

  return {
    ok: api.ok && /.+/.test(String(bubbleText || '').trim()),
    api,
    bubbleText: String(bubbleText || '').trim(),
    screenshot,
    pageErrors: captureState.pageErrors,
    consoleErrors: filterConsoleMessages(captureState.consoleMessages),
    requestFailures: filterRequestFailures(captureState.requestFailures),
    responseFailures: filterResponseFailures(captureState.responseFailures)
  }
}

async function verifyOpportunity(page, capture, userBase) {
  capture.reset()
  await gotoHash(page, userBase, 'opportunities')

  const keywordInput = page.locator('input[placeholder*="输入商品关键词"]').first()
  const searchButton = page.locator('.toolbar').first().locator('button.app-btn').first()
  await keywordInput.waitFor({ state: 'visible', timeout: 30000 })
  await keywordInput.fill('Mathtype')

  const searchResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/goofish/search') && resp.request().method() === 'GET',
    async () => {
      await searchButton.click()
    },
    120000
  )

  await page.locator('.op-product').first().waitFor({ state: 'visible', timeout: 30000 })

  const visibleStep = page.locator('.step-panel:visible')
  await visibleStep.locator('.step-footer .app-btn.primary').click()
  await page.waitForTimeout(1000)
  const rewriteButton = await waitForEnabledLocator(page, '.step-panel:visible .rewrite-style-row .app-btn', 60000)

  const rewriteResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/opportunity/rewrite') && resp.request().method() === 'POST',
    async () => {
      await rewriteButton.click()
    },
    180000
  )

  await page.waitForTimeout(2000)
  await page.locator('.step-panel:visible .step-footer .app-btn.primary').click()
  await page.waitForTimeout(1000)
  const imageButton = await waitForEnabledLocator(page, '.step-panel:visible .image-gen-actions .app-btn.primary', 60000)

  const imageResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/opportunity/generate-images') && resp.request().method() === 'POST',
    async () => {
      await imageButton.click()
    },
    330000
  )

  await page.waitForTimeout(3000)
  const generatedImageCount = await page.locator('.generated-grid img').count().catch(() => 0)
  const history = await page.evaluate(async () => {
    const token = localStorage.getItem('xianyu_auth_token') || ''
    const resp = await fetch('/api/opportunity/image-history?limit=5', {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    const text = await resp.text()
    try {
      return { status: resp.status, json: JSON.parse(text) }
    } catch {
      return { status: resp.status, json: null, text }
    }
  })
  const screenshot = await saveScreenshot(page, 'opportunity-regression')
  const captureState = capture.read()
  const searchApi = summarizeApiResult(searchResponse)
  const rewriteApi = summarizeApiResult(rewriteResponse)
  const imageApi = summarizeApiResult(imageResponse)
  if (!imageApi.ok && generatedImageCount > 0 && history?.status === 200) {
    imageApi.ok = true
    imageApi.message = imageApi.message || imageResponse.readError || 'response body unavailable'
  }

  return {
    ok: searchApi.ok &&
      rewriteApi.ok &&
      imageApi.ok &&
      generatedImageCount > 0,
    search: searchApi,
    rewrite: rewriteApi,
    image: imageApi,
    generatedImageCount,
    history,
    screenshot,
    pageErrors: captureState.pageErrors,
    consoleErrors: filterConsoleMessages(captureState.consoleMessages),
    requestFailures: filterRequestFailures(captureState.requestFailures),
    responseFailures: filterResponseFailures(captureState.responseFailures)
  }
}

async function verifyWorkflow(page, capture, userBase) {
  capture.reset()
  await gotoHash(page, userBase, 'workflow')
  const firstWorkflow = page.locator('.workflow-list-item').first()
  const firstNode = page.locator('.workflow-node').first()
  if (await firstWorkflow.isVisible().catch(() => false)) {
    await firstWorkflow.click()
  }
  const hasExistingNodes = await firstNode.isVisible({ timeout: 5000 }).catch(() => false)
  if (!hasExistingNodes) {
    await page.locator('.workflow-list-panel .full').click()
  }
  await firstNode.waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForTimeout(3000)

  const fetchNode = page.locator('.workflow-node').nth(1)
  await fetchNode.click()
  const extractInput = page.locator('textarea[placeholder*="直接粘贴"]').first()
  await extractInput.fill('夏季连衣裙, 通勤衬衫, 轻奢女包, 二手手机，帮我提取适合闲鱼商机搜索的关键词。')
  const extractResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/workflow/ai/extract-keywords') && resp.request().method() === 'POST',
    async () => {
      await page.getByRole('button', { name: /AI 提取关键词/ }).click()
    },
    120000
  )
  await page.waitForTimeout(1500)

  const polishNode = page.locator('.workflow-node').nth(3)
  await polishNode.click()
  const styleSelect = page.locator('.form-row').filter({ hasText: '润色风格' }).locator('select').first()
  if (await styleSelect.isVisible().catch(() => false)) {
    await styleSelect.selectOption({ index: 1 })
  }
  const polishResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/workflow/ai/rewrite') && resp.request().method() === 'POST',
    async () => {
      await page.getByRole('button', { name: '测试改写' }).click()
    },
    120000
  )
  await page.waitForTimeout(1500)
  const polishPreview = await page.locator('.preview-box').nth(1).textContent().catch(() => '')

  const imageNode = page.locator('.workflow-node').nth(4)
  await imageNode.click()
  const imageResponse = await waitForResponseJson(
    page,
    (resp) => resp.url().includes('/api/workflow/ai/generate-images') && resp.request().method() === 'POST',
    async () => {
      await page.getByRole('button', { name: '测试生图' }).click()
    },
    180000
  )

  await page.waitForTimeout(2000)
  const screenshot = await saveScreenshot(page, 'workflow-regression')
  const captureState = capture.read()

  return {
    ok: summarizeApiResult(extractResponse).ok &&
      summarizeApiResult(polishResponse).ok &&
      summarizeApiResult(imageResponse).ok &&
      /.+/.test(String(polishPreview || '').trim()),
    extract: summarizeApiResult(extractResponse),
    polish: summarizeApiResult(polishResponse),
    polishPreview: String(polishPreview || '').trim(),
    image: summarizeApiResult(imageResponse),
    screenshot,
    pageErrors: captureState.pageErrors,
    consoleErrors: filterConsoleMessages(captureState.consoleMessages),
    requestFailures: filterRequestFailures(captureState.requestFailures),
    responseFailures: filterResponseFailures(captureState.responseFailures)
  }
}

async function main() {
  ensureOutputDir()
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const userBase = config.smoke.user_frontend_base.replace(/\/$/, '')
  const userLogin = await requestJson(`${userBase}/api/login/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config.smoke.user_credentials)
  })
  if (!userLogin.ok || userLogin.data?.code !== 200 || !userLogin.data?.data?.token) {
    throw new Error(`user login failed: HTTP ${userLogin.status}`)
  }

  const playwrightModule = await loadPlaywright()
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium
  if (!chromium) throw new Error('playwright chromium launcher not found')

  const browser = await chromium.launch({ headless: true })
  try {
    const { context, page, capture } = await createUserPage(
      browser,
      userBase,
      config.smoke.user_credentials.username,
      userLogin.data.data.token
    )
    try {
      const aiCs = await verifyAiCs(page, capture, userBase)
      const opportunity = await verifyOpportunity(page, capture, userBase)
      const workflow = await verifyWorkflow(page, capture, userBase)
      const result = {
        checkedAt: new Date().toISOString(),
        aiCs,
        opportunity,
        workflow,
        overallOk: aiCs.ok && opportunity.ok && workflow.ok
      }
      const resultPath = path.join(outputDir, `ai-flow-regression-${stamp()}.json`)
      fs.writeFileSync(resultPath, JSON.stringify(result, null, 2), 'utf8')
      console.log(JSON.stringify({ resultPath, overallOk: result.overallOk, aiCs: aiCs.ok, opportunity: opportunity.ok, workflow: workflow.ok }, null, 2))
    } finally {
      await context.close()
    }
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error))
  process.exitCode = 1
})
