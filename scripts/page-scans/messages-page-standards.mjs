import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const outputDir = path.join(repoRoot, 'output', 'playwright')
const playwrightEntry = path.join(repoRoot, 'apps', 'crawler-service', 'node_modules', 'playwright', 'index.js')
const CACHE_KEY = 'xya:messages-page-cache:v1'

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
      ...headers,
    },
    body,
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
    data,
    text,
  }
}

function unwrapResultObject(payload) {
  if (!payload || typeof payload !== 'object') return payload
  return Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload
}

function normalizeSid(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const withoutPrefix = raw.startsWith('sid:') ? raw.slice(4) : raw
  return withoutPrefix.endsWith('@goofish') ? withoutPrefix.slice(0, -8) : withoutPrefix
}

function normalizePeerUserId(value) {
  const raw = String(value || '').trim()
  if (!raw || raw.startsWith('sid:')) return ''
  return raw.endsWith('@goofish') ? raw.slice(0, -8) : raw
}

function getConversationKey(accountId, conversation) {
  const sid = normalizeSid(conversation?.sid || conversation?.sId || conversation?.sessionId || conversation?.conversationId || conversation?.cid || '')
  if (sid) return `${accountId}:sid:${sid}`
  const peerUserId = normalizePeerUserId(
    conversation?.peerUserId ||
    conversation?.peerExternalUid ||
    conversation?.externalBuyerId ||
    conversation?.senderUserId ||
    conversation?.receiverUserId ||
    ''
  )
  return peerUserId ? `${accountId}:peer:${peerUserId}` : ''
}

async function loginUser(config) {
  const userBase = config.smoke.user_frontend_base.replace(/\/$/, '')
  const response = await requestJson(`${userBase}/api/login/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config.smoke.user_credentials),
  })
  const token = response.data?.data?.token || ''
  if (!response.ok || response.data?.code !== 200 || !token) {
    throw new Error(`user login failed: status=${response.status} body=${response.text.slice(0, 200)}`)
  }
  return { userBase, token }
}

async function fetchAccounts(userBase, token) {
  const response = await requestJson(`${userBase}/api/xianyu/accounts?current=1&size=50`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const payload = unwrapResultObject(response.data)
  const records = Array.isArray(payload)
    ? payload
    : (payload?.records || payload?.accounts || payload?.list || payload?.rows || [])
  return records.map((item) => ({
    id: Number(item?.id || 0),
    label: item?.accountNote || item?.nickname || item?.displayName || item?.externalUid || item?.unb || `账号${item?.id || ''}`,
  })).filter((item) => item.id > 0)
}

async function fetchAllConversations(userBase, token, accountId) {
  const seen = new Map()
  let cursor = null
  let loops = 0
  for (;;) {
    loops += 1
    if (loops > 50) break
    const query = new URLSearchParams({
      xianyuAccountId: String(accountId),
      pageSize: '20',
    })
    if (cursor !== null && cursor !== '') {
      query.set('cursor', String(cursor))
    }
    const response = await requestJson(`${userBase}/api/msg/online/conversations?${query.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const payload = unwrapResultObject(response.data) || {}
    const list = Array.isArray(payload)
      ? payload
      : (payload?.conversations || payload?.records || payload?.list || [])
    list.forEach((item) => {
      const key = getConversationKey(accountId, item)
      if (key) {
        seen.set(key, item)
      }
    })
    const nextCursor = Array.isArray(payload) ? null : (payload?.nextCursor ?? null)
    const hasMore = Array.isArray(payload) ? false : Boolean(payload?.hasMore)
    if (!hasMore || nextCursor === null || nextCursor === '') {
      break
    }
    cursor = nextCursor
  }
  return {
    count: seen.size,
    keys: Array.from(seen.keys()),
  }
}

async function createUserPage(browser, userBase, username, token) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true })
  await context.addInitScript(({ tokenValue, usernameValue }) => {
    localStorage.setItem('xianyu_auth_token', tokenValue)
    localStorage.setItem('xianyu_username', usernameValue)
  }, { tokenValue: token, usernameValue: username })
  const page = await context.newPage()
  await page.goto(`${userBase}/#/dashboard`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  return { context, page }
}

async function waitForConversationSurface(page, timeout = 45000) {
  await page.waitForFunction(() => {
    const visibleConversations = Array.from(document.querySelectorAll('.xya-msg-conversation'))
      .filter((node) => node instanceof HTMLElement && node.offsetParent !== null)
    const emptyState = document.querySelector('.xya-msg-empty')
    return visibleConversations.length > 0 || Boolean(emptyState)
  }, null, { timeout })
}

async function waitForConversationVisible(page, timeout = 45000) {
  await page.waitForFunction(() => {
    return Array.from(document.querySelectorAll('.xya-msg-conversation'))
      .some((node) => node instanceof HTMLElement && node.offsetParent !== null)
  }, null, { timeout })
}

async function measureFirstConversationTime(page, action) {
  const startedAt = Date.now()
  const waitForVisible = waitForConversationVisible(page).then(() => Date.now() - startedAt).catch(() => null)
  await action()
  return waitForVisible
}

async function getConversationCount(page) {
  return page.evaluate(() => {
    return Array.from(document.querySelectorAll('.xya-msg-conversation'))
      .filter((node) => node instanceof HTMLElement && node.offsetParent !== null)
      .length
  })
}

async function getVisibleAccountOptions(page) {
  return page.evaluate(() => {
    const select = document.querySelector('select.xya-msg-select')
    if (!(select instanceof HTMLSelectElement)) return []
    return Array.from(select.options)
      .map((option) => ({
        value: String(option.value || ''),
        label: String(option.textContent || '').trim(),
      }))
      .filter((item) => item.value)
  })
}

async function loadAllConversationsInSidebar(page) {
  let previousCount = -1
  let stableRounds = 0
  for (let index = 0; index < 40; index += 1) {
    await page.locator('.xya-msg-conversation-list').evaluate((element) => {
      element.scrollTop = element.scrollHeight
    }).catch(() => {})
    await page.waitForTimeout(700)
    const count = await getConversationCount(page)
    const noMoreText = await page.locator('.xya-msg-more-wrap .xya-msg-more-tip').last().textContent().catch(() => '')
    if (count === previousCount) {
      stableRounds += 1
    } else {
      stableRounds = 0
    }
    if (String(noMoreText || '').includes('暂无更多会话') && stableRounds >= 1) {
      return { count, noMoreText: String(noMoreText || '').trim(), loops: index + 1 }
    }
    previousCount = count
  }
  return {
    count: await getConversationCount(page),
    noMoreText: String(await page.locator('.xya-msg-more-wrap .xya-msg-more-tip').last().textContent().catch(() => '') || '').trim(),
    loops: 40,
  }
}

async function sampleConversationCounts(page, durationMs = 4000, intervalMs = 500) {
  const samples = []
  const startedAt = Date.now()
  while (Date.now() - startedAt < durationMs) {
    samples.push(await getConversationCount(page))
    await page.waitForTimeout(intervalMs)
  }
  return samples
}

async function switchAccount(page, accountId) {
  const firstVisibleMs = await measureFirstConversationTime(page, async () => {
    await page.locator('select.xya-msg-select').selectOption(String(accountId))
  })
  await waitForConversationSurface(page)
  await page.waitForTimeout(2200)
  const loadResult = await loadAllConversationsInSidebar(page)
  const samples = await sampleConversationCounts(page)
  return {
    firstVisibleMs,
    uiCount: loadResult.count,
    noMoreText: loadResult.noMoreText,
    stabilitySamples: samples,
    uniqueCounts: Array.from(new Set(samples)),
  }
}

async function collectMetrics(page) {
  return page.evaluate((cacheKey) => {
    const fullTimePattern = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
    const visibleConversationRows = Array.from(document.querySelectorAll('.xya-msg-conversation'))
      .filter((node) => node instanceof HTMLElement && node.offsetParent !== null)
    const conversationTimes = visibleConversationRows
      .map((node) => node.querySelector('.xya-msg-conversation-top span')?.textContent?.trim() || '')
      .filter(Boolean)
    const messageTimes = Array.from(document.querySelectorAll('.xya-msg-bubble-meta span:first-child'))
      .map((node) => node.textContent?.trim() || '')
      .filter(Boolean)
    const parseTime = (value) => {
      const normalized = value.includes(' ') ? value.replace(' ', 'T') : value
      const parsed = Date.parse(normalized)
      return Number.isFinite(parsed) ? parsed : 0
    }
    const parsedMessageTimes = messageTimes.map(parseTime).filter(Boolean)
    const messageOrderValid = parsedMessageTimes.every((value, index) => index === 0 || value >= parsedMessageTimes[index - 1])
    const bubbleImages = Array.from(document.querySelectorAll('.xya-msg-image')).map((node) => {
      const rect = node.getBoundingClientRect()
      return {
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        naturalWidth: Number(node.naturalWidth || 0),
        naturalHeight: Number(node.naturalHeight || 0),
      }
    })
    const productImage = document.querySelector('.xya-msg-product-cover')
    const selectedAvatar = document.querySelector('.xya-msg-chat-head .avatar-image')
    const chatPanel = document.querySelector('.xya-msg-chat-panel')
    const chatStream = document.querySelector('.xya-msg-chat-stream')
    const conversationList = document.querySelector('.xya-msg-conversation-list')
    const statusBanner = document.querySelector('.xya-msg-card-status')
    return {
      pageHasVerticalScroll: document.documentElement.scrollHeight > window.innerHeight + 4,
      pageHeight: Math.round(window.innerHeight),
      layoutHeights: {
        list: conversationList ? Math.round(conversationList.getBoundingClientRect().height) : 0,
        chat: chatPanel ? Math.round(chatPanel.getBoundingClientRect().height) : 0,
        stream: chatStream ? Math.round(chatStream.getBoundingClientRect().height) : 0,
      },
      overflow: {
        list: conversationList ? getComputedStyle(conversationList).overflowY : '',
        chat: chatPanel ? getComputedStyle(chatPanel).overflowY : '',
        stream: chatStream ? getComputedStyle(chatStream).overflowY : '',
      },
      conversationTimes: conversationTimes.slice(0, 8),
      allConversationTimesFull: conversationTimes.every((value) => fullTimePattern.test(value)),
      messageTimes: messageTimes.slice(0, 10),
      allMessageTimesFull: messageTimes.every((value) => fullTimePattern.test(value)),
      messageOrderValid,
      aiListBadges: document.querySelectorAll('.xya-msg-ai-tag').length,
      aiMessageBadges: document.querySelectorAll('.xya-msg-bubble-label').length,
      imageCount: bubbleImages.length,
      imageAdaptiveOk: bubbleImages.every((item) => item.width <= 420 && item.height <= 340),
      bubbleImages,
      productImageLoaded: Boolean(productImage?.complete && productImage?.naturalWidth > 0),
      goodsIdText: document.querySelector('.xya-msg-product-info span')?.textContent?.trim() || '',
      avatarImageCount: document.querySelectorAll('.avatar-image').length,
      selectedAvatarLoaded: Boolean(selectedAvatar?.complete && selectedAvatar?.naturalWidth > 0),
      tokenStatusText: statusBanner?.textContent?.trim() || '',
      cachePresent: Boolean(localStorage.getItem(cacheKey)),
      cacheSize: (localStorage.getItem(cacheKey) || '').length,
      noMoreText: document.querySelector('.xya-msg-more-wrap .xya-msg-more-tip:last-child')?.textContent?.trim() || '',
    }
  }, CACHE_KEY)
}

async function run() {
  ensureOutputDir()
  if (!fs.existsSync(configPath)) {
    throw new Error(`deploy config not found: ${configPath}`)
  }
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const { userBase, token } = await loginUser(config)
  const accounts = await fetchAccounts(userBase, token)
  const playwrightModule = await loadPlaywright()
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium
  if (!chromium) {
    throw new Error('playwright chromium launcher not found')
  }

  const browser = await chromium.launch({ headless: true })
  try {
    const { context, page } = await createUserPage(
      browser,
      userBase,
      config.smoke.user_credentials.username,
      token
    )

    try {
      const coldOpenFirstVisibleMs = await measureFirstConversationTime(page, async () => {
        await page.goto(`${userBase}/#/messages`, { waitUntil: 'domcontentloaded', timeout: 60000 })
      })
      await waitForConversationSurface(page)
      await page.waitForTimeout(1800)
      const warmReloadFirstVisibleMs = await measureFirstConversationTime(page, async () => {
        await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
      })
      await waitForConversationSurface(page)
      await page.waitForTimeout(1800)

      const visibleOptions = await getVisibleAccountOptions(page)
      const optionPool = visibleOptions.length ? visibleOptions : accounts.map((item) => ({ value: String(item.id), label: item.label }))
      const accountChecks = []
      for (const option of optionPool) {
        const accountId = Number(option.value || 0)
        if (!accountId) continue
        const apiConversations = await fetchAllConversations(userBase, token, accountId)
        const uiCheck = await switchAccount(page, accountId)
        const metrics = await collectMetrics(page)
        accountChecks.push({
          accountId,
          label: option.label,
          apiCount: apiConversations.count,
          uiCount: uiCheck.uiCount,
          countsMatch: apiConversations.count === uiCheck.uiCount,
          firstVisibleMs: uiCheck.firstVisibleMs,
          noMoreText: uiCheck.noMoreText,
          stabilitySamples: uiCheck.stabilitySamples,
          uniqueCounts: uiCheck.uniqueCounts,
          metrics,
        })
      }

      const finalMetrics = await collectMetrics(page)
      const screenshotPath = path.join(outputDir, `messages-page-standards-${stamp()}.png`)
      const resultPath = path.join(outputDir, `messages-page-standards-${stamp()}.json`)
      await page.screenshot({ path: screenshotPath, fullPage: true })

      const result = {
        checkedAt: new Date().toISOString(),
        coldOpenFirstVisibleMs,
        warmReloadFirstVisibleMs,
        accountChecks,
        finalMetrics,
        screenshot: screenshotPath,
      }
      fs.writeFileSync(resultPath, JSON.stringify(result, null, 2))
      console.log(JSON.stringify({ resultPath, screenshotPath, result }, null, 2))
    } finally {
      await context.close()
    }
  } finally {
    await browser.close()
  }
}

run().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
