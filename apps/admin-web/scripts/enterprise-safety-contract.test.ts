import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import {
  ApiPayloadError,
  requireAffectedCount,
  requireListPayload,
  requirePagePayload,
  requireRecordPayload
} from '../src/utils/api-payload'
import { formatSensitivePayload, redactSensitiveText } from '../src/utils/sensitive-display'
import { resolveInternalRedirect } from '../src/utils/safe-redirect'
import { isAllowedCsvContentType } from '../src/utils/http/download-policy'
import { createLockVerifier, verifyLockPassword } from '../src/utils/lock-verifier'
import { clearApplicationStorage, clearLegacyPersistentAuth } from '../src/utils/auth-storage'
import { isTrustedSvgSource, MAX_SVG_BYTES, svgByteLength } from '../src/utils/sanitizeSvg'

assert.deepEqual(requireListPayload([{ id: 1 }], '列表'), [{ id: 1 }])
assert.deepEqual(requireRecordPayload({ ok: true }, '对象'), { ok: true })
assert.deepEqual(requireAffectedCount({ count: '0' }, '批量操作'), { count: 0 })
assert.throws(() => requireAffectedCount({ count: -1 }, '批量操作'), ApiPayloadError)
assert.deepEqual(requirePagePayload({ records: [{ id: 1 }], total: '1', current: 1, size: 20 }, '分页'), {
  records: [{ id: 1 }],
  total: 1,
  current: 1,
  size: 20
})
for (const invalid of [null, {}, { records: [], total: -1 }, { records: {}, total: 0 }]) {
  assert.throws(() => requirePagePayload(invalid, '分页'), ApiPayloadError)
}

const redacted = formatSensitivePayload(JSON.stringify({
  authorization: 'Bearer prod-token',
  nested: { apiKey: 'key-123', safe: 'visible' },
  url: 'https://example.test/callback?access_token=token-123&ok=1'
}))
assert(!redacted.includes('prod-token'))
assert(!redacted.includes('key-123'))
assert(!redacted.includes('token-123'))
assert(redacted.includes('visible'))
assert(!redactSensitiveText('Authorization=secret-value').includes('secret-value'))

assert.equal(isAllowedCsvContentType('text/csv; charset=utf-8'), true)
assert.equal(isAllowedCsvContentType('application/octet-stream'), true)
assert.equal(isAllowedCsvContentType('application/json'), false)
assert.equal(isAllowedCsvContentType('text/html'), false)

const lockVerifier = await createLockVerifier('correct horse battery staple')
assert(lockVerifier.startsWith('v1$210000$'))
assert(!lockVerifier.includes('correct horse battery staple'))
assert.equal(await verifyLockPassword('correct horse battery staple', lockVerifier), true)
assert.equal(await verifyLockPassword('wrong password', lockVerifier), false)
assert.equal(await verifyLockPassword('correct horse battery staple', 'invalid'), false)

const legacyStorage = (() => {
  const values = new Map<string, string>([
    ['user', '{"accessToken":"legacy"}'],
    ['sys-v0.0.0-userStore', '{"accessToken":"legacy"}'],
    ['sys-v0.0.0-settingStore', '{"theme":"dark"}']
  ])
  return {
    get length() { return values.size },
    key: (index: number) => Array.from(values.keys())[index] ?? null,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
    values
  }
})()
assert.equal(clearLegacyPersistentAuth(legacyStorage as unknown as Storage), 2)
assert.equal(legacyStorage.values.has('sys-v0.0.0-settingStore'), true)

const sessionValues = new Map<string, string>([
  ['user', 'session-token'],
  ['iframeRoutes', '[]'],
  ['unrelated', 'keep']
])
const sessionStorageMock = {
  get length() { return sessionValues.size },
  key: (index: number) => Array.from(sessionValues.keys())[index] ?? null,
  getItem: (key: string) => sessionValues.get(key) ?? null,
  setItem: (key: string, value: string) => sessionValues.set(key, value),
  removeItem: (key: string) => sessionValues.delete(key),
  clear: () => sessionValues.clear()
}
clearApplicationStorage(
  legacyStorage as unknown as Storage,
  sessionStorageMock as unknown as Storage
)
assert.equal(legacyStorage.values.has('sys-v0.0.0-settingStore'), false)
assert.equal(sessionValues.has('user'), false)
assert.equal(sessionValues.has('unrelated'), true)

assert.equal(resolveInternalRedirect('/admin/dashboard?tab=1#main', '/fallback'), '/admin/dashboard?tab=1#main')
for (const unsafe of ['https://evil.test', '//evil.test/path', '/\\evil.test', 'javascript:alert(1)', '\n/admin']) {
  assert.equal(resolveInternalRedirect(unsafe, '/fallback'), '/fallback')
}

const viteSource = fs.readFileSync(path.resolve('vite.config.ts'), 'utf8')
assert(viteSource.includes('drop_console'), '生产构建必须移除可能包含业务数据或令牌的 console 输出')
assert(viteSource.includes('drop_debugger'), '生产构建必须移除 debugger')
assert.match(
  viteSource,
  /['"]\/uploads['"]\s*:\s*\{[\s\S]*?target:\s*['"]http:\/\/localhost:18080['"]/,
  '本地私有媒体必须通过 core-api 鉴权边界'
)
assert.doesNotMatch(
  viteSource,
  /['"]\/uploads['"]\s*:\s*\{[\s\S]*?target:\s*['"]http:\/\/localhost:12401['"]/,
  '本地开发不得绕过 core-api 直接读取 Python 上传目录'
)

const packageMetadata = JSON.parse(fs.readFileSync(path.resolve('package.json'), 'utf8')) as {
  name?: string
  version?: string
}
const packageLockMetadata = JSON.parse(fs.readFileSync(path.resolve('package-lock.json'), 'utf8')) as {
  name?: string
  version?: string
  packages?: Record<string, { name?: string; version?: string }>
}
assert.equal(packageMetadata.name, 'xianyu-assistant-admin-web')
assert.equal(packageMetadata.version, '1.0.0')
assert.equal((packageMetadata as { private?: boolean }).private, true)
assert.equal(packageLockMetadata.name, packageMetadata.name)
assert.equal(packageLockMetadata.version, packageMetadata.version)
assert.equal(packageLockMetadata.packages?.['']?.name, packageMetadata.name)
assert.equal(packageLockMetadata.packages?.['']?.version, packageMetadata.version)

const entryHtmlSource = fs.readFileSync(path.resolve('index.html'), 'utf8')
const developmentConsoleSource = fs.readFileSync(path.resolve('src/utils/sys/console.ts'), 'utf8')
for (const source of [entryHtmlSource, developmentConsoleSource]) {
  assert(!source.includes('Art Design Pro'), '活跃后台入口不得冒用上游模板产品标识')
  assert(!source.includes('Daymychen/art-design-pro'), '活跃后台入口不得将用户引导到上游模板支持渠道')
}
assert(entryHtmlSource.includes('<title>闲鱼助手管理后台</title>'))

const headerFeatureSource = fs.readFileSync(path.resolve('src/config/modules/headerBar.ts'), 'utf8')
assert.match(headerFeatureSource, /fastEnter:\s*{\s*enabled:\s*true/)
assert.match(headerFeatureSource, /chat:\s*{\s*enabled:\s*false/)
assert.match(headerFeatureSource, /language:\s*{\s*enabled:\s*false/)

const globalComponentRegistrySource = fs.readFileSync(
  path.resolve('src/config/modules/component.ts'),
  'utf8'
)
assert(!globalComponentRegistrySource.includes('art-chat-window'), '禁用的演示聊天不得进入生产依赖图')
assert(!globalComponentRegistrySource.includes('art-fireworks-effect'), '禁用的烟花特效不得进入生产依赖图')

const fastEnterSource = fs.readFileSync(path.resolve('src/config/modules/fastEnter.ts'), 'utf8')
const fastEnterComponentSource = fs.readFileSync(
  path.resolve('src/components/core/layouts/art-fast-enter/index.vue'),
  'utf8'
)
const adminRouteSource = fs.readFileSync(path.resolve('src/router/modules/admin.ts'), 'utf8')
assert(!fastEnterSource.includes('WEB_LINKS'), '生产快捷入口不得链接上游模板站点')
for (const routeName of [
  'AdminDashboard',
  'AdminOrders',
  'AdminMessages',
  'AdminAiUsage',
  'AdminNotifyLogs',
  'AdminAuditLogs',
  'UserCenter',
  'AdminGoods',
  'AdminAutoReply',
  'AdminSmartMonitor'
]) {
  assert(fastEnterSource.includes(`routeName: '${routeName}'`), `快捷入口应包含 ${routeName}`)
  assert(adminRouteSource.includes(`name: '${routeName}'`), `快捷入口 ${routeName} 必须对应真实路由`)
}
for (const removedDemoRoute of ['Console', 'Analysis', 'Fireworks', 'Chat', 'Pricing']) {
  assert(!fastEnterSource.includes(`routeName: '${removedDemoRoute}'`))
}
assert(fastEnterComponentSource.includes('router.hasRoute(routeName)'), '快捷入口必须在跳转前验证路由')
assert(fastEnterComponentSource.includes('该功能暂不可用'), '无效快捷入口必须显示可理解的状态')
assert(fastEnterComponentSource.includes('trigger="click"'), '快捷入口必须支持键盘触发的点击语义')
assert(fastEnterComponentSource.includes('isNavigationFailure(failure)'), '路由守卫拒绝跳转时必须显示失败状态')
assert(fastEnterComponentSource.includes('router.currentRoute.value.name !== routeName'), '路由被重定向时不得误报打开成功')
assert(fastEnterComponentSource.includes('if (navigating.value) return'), '快捷入口必须阻止并发重复导航')
assert(!fastEnterComponentSource.includes('window.open('), '生产快捷入口不得打开未审计的外部窗口')
assert.match(fastEnterComponentSource, /<button\s+v-for="application in enabledApplications"/, '快捷应用必须使用原生按钮')
assert.match(fastEnterComponentSource, /<li\s+v-for="quickLink in enabledQuickLinks"[\s\S]*?<button/, '快捷链接必须使用原生按钮')
assert(fastEnterComponentSource.includes(':aria-label="`${application.name}：${application.description}`"'))
assert(fastEnterComponentSource.includes(':aria-label="`打开${quickLink.name}`"'))

const headerComponentSource = fs.readFileSync(
  path.resolve('src/components/core/layouts/art-header-bar/index.vue'),
  'utf8'
)
assert(!headerComponentSource.includes('absolute top-2 right-2 size-1.5 !bg-danger'), '不得用固定红点伪造未读通知')
assert(!headerComponentSource.includes("mittBus.emit('openChat')"), '未实现聊天不得保留可触发生产入口')
assert(!headerComponentSource.includes('shouldShowChat'))
assert.match(headerComponentSource, /icon="ri:notification-2-line"[\s\S]{0,180}:label=/)
assert.match(headerComponentSource, /icon="ri:function-line"\s+label="打开快捷入口"/)
assert.match(headerComponentSource, /<button[\s\S]{0,180}aria-label="打开全局搜索"/)

const iconButtonSource = fs.readFileSync(
  path.resolve('src/components/core/widget/art-icon-button/index.vue'),
  'utf8'
)
assert.match(iconButtonSource, /<button\s/)
assert(iconButtonSource.includes('type="button"'), '图标按钮不得意外提交表单')
assert(iconButtonSource.includes(':aria-label="label"'), '图标按钮必须暴露可读名称')
assert(!iconButtonSource.includes('<div\n    class="size-8.5'), '图标按钮不得退化为 click-only div')

const excelExportSource = fs.readFileSync(
  path.resolve('src/components/core/forms/art-excel-export/index.vue'),
  'utf8'
)
assert(!excelExportSource.includes("creator || 'Art Design Pro'"), '导出文件作者不得使用上游模板名')
assert(excelExportSource.includes("creator || '闲鱼助手管理后台'"))

const notificationLogSource = fs.readFileSync(
  path.resolve('src/views/admin/ops/notification-logs/index.vue'),
  'utf8'
)
assert(notificationLogSource.includes('formatSensitivePayload'), '通知请求体和响应体必须在展示前脱敏')

const loginSource = fs.readFileSync(path.resolve('src/views/auth/login/index.vue'), 'utf8')
assert(loginSource.includes('resolveInternalRedirect'), '登录后的 redirect 必须限制为站内路径')
assert(!loginSource.includes('rememberPassword'), '界面不得声称记住密码却实际长期保存访问令牌')
assert(loginSource.includes('autocomplete="username"'))
assert(loginSource.includes('autocomplete="current-password"'))
assert(loginSource.includes('dragVerify.value?.reset?.()'), '登录失败时不得因验证组件已卸载而再次抛错')

const authApiSource = fs.readFileSync(path.resolve('src/api/auth.ts'), 'utf8')
const appShellSource = fs.readFileSync(path.resolve('src/App.vue'), 'utf8')
assert(authApiSource.includes("url: '/media/session'"), '管理端必须初始化受限媒体会话')
assert(loginSource.includes('await createAdminMediaSession()'), '登录完成前必须确认私有媒体会话')
assert(appShellSource.includes('10 * 60 * 1000'), '长会话必须在媒体 Cookie 到期前刷新')
assert(authApiSource.includes('let mediaSessionRequest:'), '并发媒体会话初始化必须复用同一请求')
assert.match(authApiSource, /url: '\/media\/session',[\s\S]*?showErrorMessage: false/)
assert.match(authApiSource, /url: '\/auth\/login',[\s\S]*?showErrorMessage: false/)
assert(appShellSource.includes("[userStore.accessToken, userStore.isLogin] as const"))
assert(appShellSource.includes('if (userStore.accessToken && userStore.isLogin)'))
assert(appShellSource.includes('60 * 1000'), '媒体会话暂时失败应保持壳可用并定时恢复')

const userStoreSource = fs.readFileSync(path.resolve('src/store/modules/user.ts'), 'utf8')
assert(userStoreSource.includes('storage: sessionStorage'), '管理端认证状态不得长期持久化到 localStorage')
assert(authApiSource.includes("fetch('/admin-api/auth/logout'"), '退出登录必须调用服务端权威撤销接口')
assert(authApiSource.includes('keepalive: true'), '退出请求必须在页面跳转期间保持发送能力')
assert(userStoreSource.includes('revokeAdminSession(mediaToken)'), '清除本地令牌前必须发起服务端会话撤销')
assert(userStoreSource.includes('服务端会话撤销未确认'), '网络失败必须向管理员说明服务端撤销状态未知')
assert(userStoreSource.includes("currentRoute.path.startsWith('/auth/')"), '认证页退出不得把认证页自身写入 redirect')

const dragVerifySource = fs.readFileSync(
  path.resolve('src/components/core/forms/art-drag-verify/index.vue'),
  'utf8'
)
assert.match(dragVerifySource, /<button[\s\S]*?class="dv_handler/)
assert(dragVerifySource.includes('@keydown.enter.prevent="completeWithKeyboard"'))
assert(dragVerifySource.includes('@keydown.space.prevent="completeWithKeyboard"'))
assert(dragVerifySource.includes(':aria-pressed="value"'))
assert.equal(
  (dragVerifySource.match(/document\.addEventListener\('touchstart'/g) ?? []).length,
  1,
  '拖拽验证不得重复注册全局触摸监听'
)

const authTopBarSource = fs.readFileSync(
  path.resolve('src/components/core/views/login/AuthTopBar.vue'),
  'utf8'
)
assert.match(authTopBarSource, /<button[\s\S]*?aria-label="选择主题色"/)
assert(authTopBarSource.includes("'切换到浅色模式'"))
assert(authTopBarSource.includes('.color-picker-expandable:focus-within .color-dots'))

const exceptionViewSource = fs.readFileSync(
  path.resolve('src/components/core/views/exception/ArtException.vue'),
  'utf8'
)
const staticRouteSource = fs.readFileSync(path.resolve('src/router/routes/staticRoutes.ts'), 'utf8')
assert(exceptionViewSource.includes('<h1'), '异常页必须有可读的页面标题')
assert(staticRouteSource.includes("path: '/404'"), '404 必须有可直接回归的显式路由')
assert(staticRouteSource.includes("name: 'Exception404CatchAll'"))

const httpErrorSource = fs.readFileSync(path.resolve('src/utils/http/error.ts'), 'utf8')
assert(httpErrorSource.includes("console.error('[HTTP Error]', error.toSafeLogData())"))
assert(!httpErrorSource.includes("console.error('[HTTP Error]', error.toLogData())"))

const httpClientSource = fs.readFileSync(path.resolve('src/utils/http/index.ts'), 'utf8')
assert(!httpClientSource.includes('Math.random()'), '请求跟踪 ID 不得使用可预测伪随机数')
assert(httpClientSource.includes('cryptoApi?.randomUUID') || httpClientSource.includes('cryptoApi?.getRandomValues'))

const iconComponentSource = fs.readFileSync(
  path.resolve('src/components/core/base/art-svg-icon/index.vue'),
  'utf8'
)
const iconLoaderSource = fs.readFileSync(path.resolve('src/utils/ui/iconify-loader.ts'), 'utf8')
const mainSource = fs.readFileSync(path.resolve('src/main.ts'), 'utf8')
const iconBundle = JSON.parse(
  fs.readFileSync(path.resolve('src/assets/generated/iconify-bundle.json'), 'utf8')
) as Array<{ prefix: string; icons: Record<string, unknown> }>
assert(iconComponentSource.includes("from '@iconify/vue/offline'"), '图标组件不得启用 Iconify 公网加载器')
assert(iconLoaderSource.includes("from '@iconify/vue/offline'"))
assert(mainSource.includes("import '@utils/ui/iconify-loader.ts'"))
assert(iconBundle.length >= 1 && iconBundle.every(collection => Object.keys(collection.icons).length > 0))

const routeModulesSource = fs.readFileSync(path.resolve('src/router/modules/index.ts'), 'utf8')
assert.equal(
  routeModulesSource.includes("from './article'")
    || routeModulesSource.includes("from './dashboard'")
    || routeModulesSource.includes("from './examples'")
    || routeModulesSource.includes("from './safeguard'")
    || routeModulesSource.includes("from './template'")
    || routeModulesSource.includes("from './widgets'"),
  false,
  '演示、随机指标和未接真实 API 的路由不得进入生产菜单'
)
assert(routeModulesSource.includes('export const routeModules: AppRouteRecord[] = adminRoutes'))

const componentLoaderSource = fs.readFileSync(path.resolve('src/router/core/ComponentLoader.ts'), 'utf8')
for (const forbiddenViewRoot of ['article', 'dashboard', 'examples', 'safeguard', 'template', 'widgets']) {
  assert(
    !componentLoaderSource.includes(`../../views/${forbiddenViewRoot}/**/*.vue`),
    `${forbiddenViewRoot} 演示页面不得被生产动态路由加载器打包或开放`
  )
}

const lockScreenSource = fs.readFileSync(
  path.resolve('src/components/core/layouts/art-screen-lock/index.vue'),
  'utf8'
)
assert(lockScreenSource.includes('createLockVerifier'))
assert(lockScreenSource.includes('enableIntrusiveBrowserBlocking = false'))
assert(!lockScreenSource.includes('CryptoJS.AES'))
assert(!lockScreenSource.includes('VITE_LOCK_ENCRYPT_KEY'))

const themeSvgSource = fs.readFileSync(
  path.resolve('src/components/core/theme/theme-svg/index.vue'),
  'utf8'
)
const svgSanitizerSource = fs.readFileSync(path.resolve('src/utils/sanitizeSvg.ts'), 'utf8')
assert(themeSvgSource.includes('isTrustedSvgSource(source)'), '主题 SVG 必须先拒绝非本地来源')
assert(themeSvgSource.includes('sanitizeSvg(applyThemeToSvg(content, themeColor))'), '主题 SVG 注入 DOM 前必须净化')
assert(themeSvgSource.includes('onCleanup(() => controller.abort())'), '主题 SVG 切换资源时必须中止旧请求')
assert(themeSvgSource.includes('if (signal.aborted) return'), '旧 SVG 响应不得覆盖新资源')
assert(themeSvgSource.includes('response.body?.getReader()'), '主题 SVG 必须在流式读取期间限制响应体积')
assert(svgSanitizerSource.includes("typeof DOMParser === 'undefined'"), '无解析器时 SVG 净化必须 fail-closed')
for (const blockedVector of ["name.startsWith('on')", 'xlink:href', '@import', 'javascript:']) {
  assert(svgSanitizerSource.includes(blockedVector), `SVG 净化必须覆盖 ${blockedVector}`)
}
assert(svgSanitizerSource.includes("root.namespaceURI !== SVG_NAMESPACE"), 'SVG 根节点必须使用 SVG 命名空间')
assert(svgSanitizerSource.includes('ALLOWED_STYLE_PROPERTIES'), '内联样式必须限制到绘图属性白名单')
assert(svgSanitizerSource.includes('(?:doctype|entity)'), 'SVG 必须拒绝 DTD 与实体声明')

const svgBase = 'https://admin.example.test/app/'
assert.equal(isTrustedSvgSource('/assets/illustration.svg', svgBase), true)
assert.equal(isTrustedSvgSource('https://admin.example.test/assets/illustration.svg', svgBase), true)
assert.equal(isTrustedSvgSource('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%2F%3E', svgBase), true)
for (const unsafeSource of [
  'https://evil.example.test/illustration.svg',
  '//evil.example.test/illustration.svg',
  'javascript:alert(1)',
  'https://user:password@admin.example.test/illustration.svg'
]) {
  assert.equal(isTrustedSvgSource(unsafeSource, svgBase), false, `必须拒绝不可信 SVG 来源：${unsafeSource}`)
}
assert.equal(isTrustedSvgSource(`data:image/svg+xml,${'a'.repeat(MAX_SVG_BYTES)}`, svgBase), false)
assert.equal(svgByteLength('企业级'), 9)

console.log('enterprise-safety-contract: ok')
