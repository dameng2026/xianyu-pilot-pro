import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { globalConfirm } from '../src/composables/confirmState.js'

const first = globalConfirm.confirm('第一项', '必须先处理', '继续执行', true)
const second = globalConfirm.alert('第二项', '随后展示')

assert.equal(globalConfirm.state.visible, true)
assert.equal(globalConfirm.state.title, '第一项')
assert.equal(globalConfirm.state.confirmText, '继续执行')
assert.equal(globalConfirm.state.dangerous, true)
globalConfirm.doConfirm()
assert.equal(await first, true)

await new Promise(resolve => queueMicrotask(resolve))
assert.equal(globalConfirm.state.visible, true)
assert.equal(globalConfirm.state.title, '第二项')
assert.equal(globalConfirm.state.confirmText, '')
assert.equal(globalConfirm.state.dangerous, false)
globalConfirm.cancel()
assert.equal(await second, false)
assert.equal(globalConfirm.state.visible, false)

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const modal = fs.readFileSync(path.join(root, 'src', 'components', 'ConfirmModal.vue'), 'utf8')
const vipPage = fs.readFileSync(path.join(root, 'src', 'pages', 'VipPage.vue'), 'utf8')
assert.match(modal, /role="dialog"/)
assert.match(modal, /aria-modal="true"/)
assert.match(modal, /aria-labelledby="global-confirm-title"/)
assert.match(modal, /event\.key === 'Escape'/)
assert.match(modal, /event\.key !== 'Tab'/)
assert.match(modal, /state\.confirmText \|\| '确认'/, 'custom confirmation labels must reach the rendered button')
assert.match(modal, /state\.dangerous[\s\S]*cancelRef/, 'dangerous actions must initially focus a safe dismissal control')
assert.match(modal, /returnFocusTarget/, 'the dialog must restore focus after the complete queue closes')
assert.match(modal, /event\.isComposing/, 'IME composition Enter events must not submit a prompt')
assert.match(modal, /:aria-label="state\.placeholder \|\| state\.title"/, 'prompt inputs need an accessible name')
assert.match(vipPage, /resolveTrustedMediaUrl\(props\.user\?\.avatar/, 'VIP avatars must use the shared trusted-media policy')
assert.match(vipPage, /requestId !== plansRequestId/, 'stale plan responses must not replace the newest request')
assert.match(vipPage, /&& hasPrice &&/, 'plans without a display price must remain unavailable')
assert.match(vipPage, /正在加载套餐/, 'the initial plan request must expose a truthful loading state')
assert.match(vipPage, /const loading = ref\(true\)/, 'the first render must not flash an empty-plan state before loading begins')

console.log('confirm-state: ok')
