import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const upgradeSource = readFileSync(resolve(root, 'src/utils/sys/upgrade.ts'), 'utf8')
const changelogSource = readFileSync(resolve(root, 'src/views/change/log/index.vue'), 'utf8')
const releaseSource = readFileSync(resolve(root, 'src/config/release-notes.ts'), 'utf8')
const packageJson = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')) as {
  version?: string
}

assert.doesNotMatch(upgradeSource, /@\/mock|DEBUG-UPGRADE|dangerouslyUseHTMLString:\s*true/)
assert.doesNotMatch(upgradeSource, /<p\b|<\/p>/i)
assert.doesNotMatch(changelogSource, /@\/mock/)
assert.match(upgradeSource, /dangerouslyUseHTMLString:\s*false/)
assert.match(releaseSource, new RegExp(`version:\\s*['"]v${packageJson.version}['"]`))
assert.match(releaseSource, /生产上线仍须通过生产就绪清单/)

console.log('release-metadata-contract: ok')
