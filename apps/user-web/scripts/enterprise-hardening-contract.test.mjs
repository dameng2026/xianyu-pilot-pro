import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import './auth-capability-state.test.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(scriptDir, '..')

function read(...segments) {
  return fs.readFileSync(path.join(root, ...segments), 'utf8')
}

const packageMetadata = JSON.parse(read('package.json'))
const packageLockMetadata = JSON.parse(read('package-lock.json'))
assert.equal(packageMetadata.name, 'xianyu-assistant-user-web')
assert.equal(packageMetadata.version, '1.0.0')
assert.equal(packageLockMetadata.name, packageMetadata.name)
assert.equal(packageLockMetadata.version, packageMetadata.version)
assert.equal(packageLockMetadata.packages?.['']?.name, packageMetadata.name)
assert.equal(packageLockMetadata.packages?.['']?.version, packageMetadata.version)

function readVueSources(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const target = path.join(directory, entry.name)
    if (entry.isDirectory()) return readVueSources(target)
    return entry.name.endsWith('.vue') ? [fs.readFileSync(target, 'utf8')] : []
  })
}

const globalStyles = read('src', 'styles.css')
const authStyles = read('src', 'auth-pages.css')
const configNav = read('src', 'components', 'ConfigNav.vue')
const productPublishPage = read('src', 'pages', 'ProductPublishPage.vue')
const messagesPage = read('src', 'pages', 'MessagesPage.vue')
const aiCsSettings = read('src', 'pages', 'settings', 'AiCsSettings.vue')
const loginPage = read('src', 'pages', 'LoginPage.vue')
const authShell = read('src', 'components', 'auth', 'AuthShell.vue')
const authContent = read('src', 'components', 'auth', 'authContent.js')
const aboutSettings = read('src', 'pages', 'settings', 'AboutSettings.vue')
const registerPage = read('src', 'pages', 'RegisterPage.vue')
const forgotPasswordPage = read('src', 'pages', 'ForgotPasswordPage.vue')
const aiChatApi = read('src', 'api', 'aiChat.js')
const viteConfig = read('vite.config.js')
const requestClient = read('src', 'utils', 'request.js')
const appSource = read('src', 'App.vue')
const authApiSource = read('src', 'api', 'auth.js')
const imageUploadPolicySource = read('src', 'utils', 'imageUploadPolicy.js')

assert.match(viteConfig, /minify:\s*'oxc'/)
assert.match(viteConfig, /dropConsole:\s*true/)
assert.match(viteConfig, /dropDebugger:\s*true/)
assert.match(viteConfig, /sourcemap:\s*false/)
assert.match(viteConfig, /process\.env\.VITE_BUILD_DATE/)
assert.doesNotMatch(viteConfig, /new Date\(\)\.toISOString\(\)/)
assert.doesNotMatch(requestClient, /Math\.random\(\)/, '请求跟踪 ID 不得使用可预测伪随机数')
assert.match(requestClient, /cryptoApi\?\.randomUUID|cryptoApi\?\.getRandomValues/)
assert.match(authApiSource, /request\.post\('\/media\/session'/)
assert.match(authApiSource, /request\.post\('\/login\/logout'/)
assert.doesNotMatch(authApiSource, /clearMediaSession|request\.delete\('\/media\/session'/,
  '权威登出响应应原子撤销 JWT 并清理 HttpOnly 媒体 Cookie，避免双请求竞态')
assert.match(appSource, /await initializeMediaSession\(\)[\s\S]*startSse\(\)/)
assert.match(appSource, /10 \* 60 \* 1000/)
assert.match(appSource, /catch \(e\) \{[\s\S]*clearMediaSessionTimer\(\)[\s\S]*clearAuth\(\)[\s\S]*location\.hash = '#\/login'[\s\S]*authNotice\.value = e\?\.message/)
assert.match(appSource, /logout_session_revocation/)
assert.match(appSource, /服务端会话撤销未确认/)
assert.match(appSource, /class="mobile-home-button"/)
assert.match(appSource, /next !== previous\) authNotice\.value = ''/)
assert.match(imageUploadPolicySource, /5 \* 1024 \* 1024/)
for (const pageSource of [productPublishPage, messagesPage, read('src', 'pages', 'OpportunityPage.vue')]) {
  assert.match(pageSource, /imageUploadValidationMessage\(file\)/)
}
assert.doesNotMatch(productPublishPage, /10 \* 1024 \* 1024|大小超过 10MB/)
assert.doesNotMatch(requestClient, /console\.(?:log|warn|error)\([^\n]*res\.msg/, '业务错误消息不得写入浏览器控制台')

assert.doesNotMatch(
  globalStyles,
  /(^|\n)\s*\.config-(?:nav|link)\b|(^|\n)\s*\.settings-layout\b/m,
  'settings navigation layout must be owned by scoped settings styles, without obsolete global overrides',
)
assert.match(configNav, /grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/)
assert.match(configNav, /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/)
assert.match(configNav, /grid-template-columns:\s*minmax\(0,\s*1fr\)/)
assert.match(authStyles, /overflow-x:\s*hidden/)
assert.match(authStyles, /overflow-y:\s*auto/)
assert.match(authStyles, /@media \(max-width:\s*1160px\)[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
assert.match(authStyles, /@media \(max-width:\s*600px\)[\s\S]*\.auth-showcase\s*\{\s*display:\s*none/)
assert.match(authStyles, /\.auth-submit:disabled\s*\{[\s\S]*cursor:\s*not-allowed/)

for (const [source, gateName, obsoleteWarning] of [
  [productPublishPage, 'categoryRefreshGate', '[refreshCategoriesInBackground]'],
  [messagesPage, 'aiSettingsGate', '[MSG] loadAiCsSetting failed:'],
]) {
  assert.match(source, new RegExp(`const ${gateName} = createRequestGate\\(\\)`))
  assert.match(source, new RegExp(`${gateName}\\.isCurrent\\(`))
  assert.match(source, new RegExp(`${gateName}\\.dispose\\(\\)`))
  assert.equal(source.includes(obsoleteWarning), false, 'disposed background requests must not leak warnings into the next page')
}

assert.match(aiCsSettings, /v-else-if="loadError"[^>]*role="alert"/)
assert.match(aiCsSettings, /@click="load">重新加载<\/button>/)
assert.match(aiCsSettings, /Promise\.allSettled\(/)
assert.match(aiCsSettings, /const loadGate = createRequestGate\(\)/)
assert.match(aiCsSettings, /loadGate\.dispose\(\)/)
assert.match(aiCsSettings, /accept="\.md,\.txt,\.pptx,\.xlsx,\.csv"/)
assert.doesNotMatch(aiCsSettings, /\['\.md', '\.txt', '\.ppt',/)
assert.doesNotMatch(aiCsSettings, /\.xlsx,\.xls/)

const allVueSource = readVueSources(path.join(root, 'src')).join('\n')
assert.doesNotMatch(allVueSource, /[\uE000-\uF8FF\uFFFD]/, 'user-facing Vue files must not contain replacement or private-use mojibake characters')
assert.doesNotMatch(
  allVueSource,
  /鍙戦€佷腑|鍔犺浇|娑堟伅|浼氳瘽|璐﹀彿|鏆傛棤|杈撳叆|鑷姩|鍥炲|涔板|澶嶆潅|璁板綍|鍥剧墖|鏄ㄥぉ|澶╁墠|绉诲姩绔|瑙嗗浘/,
  'user-facing Vue files must not contain known mojibake fragments',
)

assert.match(loginPage, /const agreed = ref\(false\)/)
assert.match(loginPage, /const isPhoneValid = computed\(/)
assert.match(loginPage, /:disabled="!smsLoginCapability\.available \|\| !isPhoneValid \|\| smsSending \|\| smsCountdown > 0"/)
assert.match(loginPage, /function switchTab\(nextTab\)/)
assert.doesNotMatch(loginPage, /@click="tab\s*=/, 'login method changes must clear stale errors through switchTab')
for (const provider of ['微信登录（暂未开放）', 'QQ登录（暂未开放）']) {
  assert.equal(loginPage.includes(`<span>${provider}</span>`), true)
}
assert.equal((loginPage.match(/<button[^>]*class="auth-social-btn"[^>]* disabled aria-disabled="true"/g) || []).length, 2)
assert.match(loginPage, /id="login-sms-help"/)
assert.match(loginPage, /aria-describedby="login-sms-help"/)

for (const unsupportedClaim of ['50万+', '1000万+', '99.9%', '粤ICP备2023012456号-2']) {
  assert.equal(`${authContent}\n${authShell}`.includes(unsupportedClaim), false, `remove unsupported claim: ${unsupportedClaim}`)
}
assert.match(authShell, /v-if="legalConfig\.icpLicense"/)
assert.match(authShell, /协议链接未配置/)
assert.doesNotMatch(authContent, /document\.write\(/)
assert.match(authContent, /getLegalDocumentUrl\(/)

for (const fakeEndpointOrClaim of [
  'https://github.com/',
  'support@xianyu.local',
  'feedback@xianyu.local',
  '7×12 小时在线响应',
  '服务运行中',
  '首个正式版本发布',
  '全功能发布',
  '当前已是最新版本',
]) {
  assert.equal(aboutSettings.includes(fakeEndpointOrClaim), false, `AboutSettings must not present unverified state: ${fakeEndpointOrClaim}`)
}
assert.doesNotMatch(aboutSettings, /document\.write\(/)
assert.match(aboutSettings, /getLegalDocumentUrl\(/)
assert.match(aboutSettings, /协议链接尚未配置/)

assert.match(registerPage, /const legalDocumentsAvailable = hasRequiredLegalDocuments\(/)
assert.match(registerPage, /用户协议或隐私政策链接未配置，当前无法完成注册/)
assert.match(registerPage, /:disabled="loading \|\| !selfRegistrationCapability\.available \|\| !legalDocumentsAvailable"/)
assert.match(registerPage, /v-if="authSupportMessage"/)
assert.match(registerPage, /support !== authUnavailableMessage\.value/)
assert.doesNotMatch(registerPage, /\/\^1\\\\d/, 'registration phone validation must match digits, not a literal backslash')
assert.doesNotMatch(registerPage, /\(\?=\.\*\\\\d\)/, 'registration password validation must match digits, not a literal backslash')

assert.match(forgotPasswordPage, /const phoneValid = computed\(/)
assert.match(forgotPasswordPage, /:disabled="!smsLoginCapability\.available \|\| !phoneValid \|\| countdown > 0 \|\| sendingCode"/)
assert.doesNotMatch(forgotPasswordPage, /\\\\d/, 'password recovery validators must not match literal backslash-d sequences')
assert.equal((forgotPasswordPage.match(/<button[^>]*class="auth-social-btn"[^>]*disabled/g) || []).length, 2)
assert.match(forgotPasswordPage, /v-if="authSupportMessage"/)
assert.match(forgotPasswordPage, /support !== authUnavailableMessage\.value/)
assert.match(globalStyles, /@media \(max-width:\s*900px\)[\s\S]*\.app-shell \.sidebar\s*\{\s*display:\s*none/)
assert.match(globalStyles, /\.mobile-home-button\s*\{[\s\S]*display:\s*inline-flex/)
const notifySettingsSource = read('src', 'pages', 'settings', 'NotifySettings.vue')
assert.match(notifySettingsSource, /<fieldset[\s\S]*:disabled="!settingsAvailable"/)
assert.match(notifySettingsSource, /:aria-pressed="!!event\.enabled"/)
assert.match(notifySettingsSource, /:aria-pressed="!!event\.app"/)
assert.match(aiChatApi, /new Error\('AI 请求超时，请稍后重试', \{ cause: e \}\)/)

console.log('enterprise-hardening-contract: ok')
