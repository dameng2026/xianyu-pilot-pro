import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

const accountsPage = fs.readFileSync(path.join(root, 'src', 'pages', 'AccountsPage.vue'), 'utf8')
const publishPage = fs.readFileSync(path.join(root, 'src', 'pages', 'ProductPublishPage.vue'), 'utf8')
const opportunityPage = fs.readFileSync(path.join(root, 'src', 'pages', 'OpportunityPage.vue'), 'utf8')
const accountAuthUtils = fs.readFileSync(path.join(root, 'src', 'utils', 'accountAuth.js'), 'utf8')

// ===========================================================================
// Bug 场景：用户 cookie 已失效、WS 也已终止，但闲鱼账号页面仍显示"正常"，
// 发布商品/搜索商品时才被动发现问题。
// 根因：前端进入页面 / 关键操作前未主动调用 /xianyu/accounts/:id/check-auth
// 实时探活，仅依赖 DB 中的 cookie_status 缓存。
// ===========================================================================

// 1) AccountsPage 进入页面时必须主动校验 cookie 状态
//    要求 onMounted 钩子中除了 loadAccounts 还要触发实时校验
assert(
  accountsPage.includes('refreshAccountAuthOnPageEnter') ||
  accountsPage.includes('refreshVisibleAccountsAuthOnPageEnter') ||
  accountsPage.includes('checkAuthOnPageEnter'),
  'AccountsPage onMounted must actively call check-auth to revalidate cookie status, not just rely on DB cache'
)

// 2) ProductPublishPage 在发布前必须校验选中账号 cookie 状态
//    要求 validate() 或 submit() 前调用 checkAccountAuth 校验
assert(
  publishPage.includes('ensureSelectedAccountCookieValid') ||
  publishPage.includes('refreshSelectedAccountAuth') ||
  publishPage.includes('checkAccountAuth('),
  'ProductPublishPage must call checkAccountAuth on the selected account before publish'
)

// 3) OpportunityPage 搜索前必须无条件主动校验 cookie 状态
//    要求 ensureLoggedXianyuAccount() 在缓存显示可用时也主动 refreshAccountAuthStatus
assert(
  opportunityPage.includes('ensurePreferredAccountCookieFresh') ||
  opportunityPage.includes('refreshAccountAuthStatus(preferred.id)') ||
  opportunityPage.includes('await refreshAccountAuthStatus'),
  'OpportunityPage ensureLoggedXianyuAccount must actively refresh cookie status even when cache shows usable'
)

// 4) accountAuth.js 必须暴露一个工具函数：根据实时校验结果判断 cookie 是否失效
assert(
  accountAuthUtils.includes('isAccountCookieExpired') ||
  accountAuthUtils.includes('accountCookieExpired') ||
  accountAuthUtils.includes('cookieStatus === 0') ||
  accountAuthUtils.includes('cookieStatus === 2'),
  'accountAuth utils must expose a way to detect expired cookie status for UI gating'
)

console.log('cookie-revalidation-contract: ok')
