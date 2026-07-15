import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { getAuthIcon } from '../src/components/auth/authContent.js'
import { getMobileIcon, Icons } from '../src/mobile/MobileIcons.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

assert.equal(getAuthIcon('constructor'), getAuthIcon('shield'))
assert.equal(getAuthIcon('<img src=x onerror=alert(1)>'), getAuthIcon('shield'))
assert.equal(getMobileIcon('__proto__'), Icons.help)
assert.equal(getMobileIcon('<svg onload=alert(1)>'), Icons.help)

const guardedSinks = new Set([
  'src/components/auth/AuthIcon.vue',
  'src/mobile/MIcon.vue',
])
const filesToCheck = [
  'src/components/Icon.vue',
  'src/components/auth/AuthShell.vue',
  'src/pages/LoginPage.vue',
  'src/pages/RegisterPage.vue',
  'src/pages/ForgotPasswordPage.vue',
]

for (const relativePath of filesToCheck) {
  const source = await readFile(path.join(root, relativePath), 'utf8')
  assert.doesNotMatch(source, /\bv-html\b/, `${relativePath} must use an allowlisted icon component`)
}

for (const relativePath of guardedSinks) {
  const source = await readFile(path.join(root, relativePath), 'utf8')
  assert.match(source, /\bv-html\b/, `${relativePath} is expected to own the guarded SVG sink`)
  assert.match(source, /Object\.hasOwn|get(?:Auth|Mobile)Icon/, `${relativePath} must resolve through a local allowlist`)
}

console.log('trusted icon contract tests passed')
