import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  createFailClosedAuthCapabilities,
  parseAuthCapabilities,
} from '../src/utils/authCapabilities.js'
import { useAuthCapabilities } from '../src/utils/useAuthCapabilities.js'

const production = parseAuthCapabilities({
  version: '1',
  mode: 'production-safe',
  failClosed: true,
  securityNotice: '生产环境不会接受调试验证码。',
  supportMessage: '请联系管理员。',
  passwordLogin: { available: true, devOnly: false, reason: '密码登录可用' },
  emailVerification: { available: false, devOnly: false, reason: '邮箱SMTP未配置' },
  selfRegistration: { available: false, devOnly: false, reason: '自助注册未开放' },
  passwordReset: { available: false, devOnly: false, reason: '密码找回未开放' },
  profileVerification: { available: false, devOnly: false, reason: '资料验证未开放' },
})

assert.equal(production.passwordLogin.available, true)
assert.equal(production.emailVerification.available, false)
assert.throws(
  () => parseAuthCapabilities({ ...production, profileVerification: undefined }),
  /认证能力响应格式异常/,
)
assert.throws(
  () => parseAuthCapabilities({ ...production, version: '2' }),
  /认证能力响应格式异常/,
)
assert.throws(
  () => parseAuthCapabilities({ ...production, mode: 'future-mode' }),
  /认证能力响应格式异常/,
)
assert.throws(
  () => parseAuthCapabilities({
    ...production,
    emailVerification: { available: true, devOnly: true, reason: '错误地在生产模式开放调试验证码' },
  }),
  /认证能力响应格式异常/,
)
assert.throws(
  () => parseAuthCapabilities({
    ...production,
    mode: 'local-development',
    emailVerification: { available: true, devOnly: false, reason: '未标记为开发专用的调试验证码' },
  }),
  /认证能力响应格式异常/,
)

const unavailable = createFailClosedAuthCapabilities('认证能力状态无法确认，请联系管理员。')
for (const key of ['passwordLogin', 'emailVerification', 'selfRegistration', 'passwordReset', 'profileVerification']) {
  assert.equal(unavailable[key].available, false, `${key} must default to unavailable`)
}
assert.equal(unavailable.failClosed, true)
assert.match(unavailable.supportMessage, /管理员/)

const failedRequest = useAuthCapabilities(async () => {
  throw new Error('upstream connection refused with secret details')
})
await failedRequest.refreshAuthCapabilities()
assert.equal(failedRequest.authCapabilityLoading.value, false)
assert.match(failedRequest.authCapabilityError.value, /无法确认/)
assert.equal(failedRequest.authCapabilities.value.passwordLogin.available, false)
assert.equal(failedRequest.authCapabilities.value.selfRegistration.available, false)
assert.equal(failedRequest.authCapabilityError.value.includes('secret details'), false)

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (...segments) => fs.readFileSync(path.join(root, ...segments), 'utf8')
const authApi = read('src', 'api', 'auth.js')
const loginPage = read('src', 'pages', 'LoginPage.vue')
const registerPage = read('src', 'pages', 'RegisterPage.vue')
const forgotPage = read('src', 'pages', 'ForgotPasswordPage.vue')
const profilePage = read('src', 'pages', 'ProfileCenterPage.vue')

assert.match(authApi, /request\.get\('\/login\/capabilities'\)/)
assert.match(loginPage, /:disabled="!emailLoginCapability\.available"/)
assert.match(loginPage, /emailLoginCapability\.reason/)
assert.match(loginPage, /if \(!activeLoginCapability\.value\.available\) return/)
assert.match(loginPage, /if \(nextTab === 'email' && !emailLoginCapability\.value\.available\) return/)

for (const [name, source, capability] of [
  ['register', registerPage, 'selfRegistrationCapability'],
  ['forgot password', forgotPage, 'passwordResetCapability'],
]) {
  assert.match(source, /v-if="authCapabilityLoading"/, `${name} must wait for the capability truth`)
  assert.match(source, new RegExp(`v-else-if="!${capability}\\.available"`), `${name} must render an unavailable state`)
  assert.match(source, /refreshAuthCapabilities/, `${name} must offer a safe retry`)
  const unavailableIndex = source.indexOf(`v-else-if="!${capability}.available"`)
  const formIndex = source.indexOf('<form')
  assert.ok(unavailableIndex >= 0 && unavailableIndex < formIndex, `${name} must gate its form before rendering it`)
}

assert.match(profilePage, /:disabled="!profileVerificationCapability\.available"/)
assert.match(profilePage, /v-if="!profileVerificationCapability\.available"/)
assert.match(profilePage, /if \(!profileVerificationCapability\.value\.available\) return/)
assert.match(profilePage, /refreshAuthCapabilities\(\)/)
assert.match(profilePage, /if \(authCapabilityLoading\.value\)/)
assert.match(profilePage, /验证码能力状态无法确认/)

console.log('auth-capability-state: ok')
