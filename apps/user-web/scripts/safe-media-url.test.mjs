import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { openTrustedMediaUrl, resolveTrustedMediaUrl } from '../src/utils/safeMediaUrl.js'

const context = { origin: 'https://app.example.com' }

assert.equal(resolveTrustedMediaUrl('https://img.alicdn.com/demo.jpg', context), 'https://img.alicdn.com/demo.jpg')
assert.equal(resolveTrustedMediaUrl('//gw.alicdn.com/demo.webp', context), 'https://gw.alicdn.com/demo.webp')
assert.equal(resolveTrustedMediaUrl('/uploads/chat/demo.png', context), '/uploads/chat/demo.png')
assert.equal(resolveTrustedMediaUrl('/api/media/demo.png', context), '/api/media/demo.png')
assert.equal(resolveTrustedMediaUrl('/imgextra/demo.png', context), 'https://img.alicdn.com/imgextra/demo.png')
assert.equal(resolveTrustedMediaUrl('data:image/png;base64,iVBORw0KGgo=', context), 'data:image/png;base64,iVBORw0KGgo=')

for (const unsafe of [
  'javascript:alert(1)',
  'http://img.alicdn.com/demo.jpg',
  'https://img.alicdn.com.evil.example/demo.jpg',
  'https://evil.example/tracker.png',
  '//evil.example/tracker.png',
  'blob:https://app.example.com/secret',
  'data:image/svg+xml,<svg onload=alert(1)>',
  'data:text/html,<script>alert(1)</script>',
  'https://user:password@img.alicdn.com/demo.jpg',
]) {
  assert.equal(resolveTrustedMediaUrl(unsafe, context), '', `unsafe media URL must be rejected: ${unsafe}`)
}

const openedWindow = { opener: { unsafe: true } }
const calls = []
const windowLike = {
  location: { origin: context.origin },
  open(...args) {
    calls.push(args)
    return openedWindow
  },
}

assert.equal(openTrustedMediaUrl('https://img.alicdn.com/demo.jpg', { windowLike }), true)
assert.deepEqual(calls, [['https://img.alicdn.com/demo.jpg', '_blank', 'noopener,noreferrer']])
assert.equal(openedWindow.opener, null, 'the preview window must not retain a reference to the application')
assert.equal(openTrustedMediaUrl('javascript:alert(1)', { windowLike }), false)
assert.equal(calls.length, 1, 'blocked URLs must never reach window.open')

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const mobileMessages = fs.readFileSync(path.join(root, 'src', 'mobile', 'MobileMessages.vue'), 'utf8')
const desktopMessages = fs.readFileSync(path.join(root, 'src', 'pages', 'MessagesPage.vue'), 'utf8')
assert.match(mobileMessages, /const imageUrl = resolveTrustedMediaUrl\(/, 'mobile message images must be normalized before reaching img.src')
assert.match(mobileMessages, /openTrustedMediaUrl\(url\)/, 'mobile image previews must use the isolated safe opener')
assert.doesNotMatch(mobileMessages, /window\.open\(/, 'mobile messages must never open an unvalidated URL directly')
assert.match(desktopMessages, /return resolveTrustedMediaUrl\(value\)/, 'desktop message images must share the trusted media policy')

console.log('safe-media-url: ok')
