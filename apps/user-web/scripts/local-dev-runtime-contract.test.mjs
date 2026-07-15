import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(scriptDir, '..', '..', '..')
const launcher = fs.readFileSync(path.join(projectRoot, 'dev-start.ps1'), 'utf8')

assert.match(launcher, /function\s+Import-DotEnv/)
assert.match(launcher, /Set-Item\s+-Path\s+"Env:\$key"/)
for (const key of ['ADMIN_JWT_SECRET', 'COOKIE_CRYPTO_SECRET', 'INTERNAL_API_TOKEN']) {
  assert.match(launcher, new RegExp(key), `dev-start.ps1 must export ${key} to every local service`)
}

console.log('local-dev-runtime-contract: ok')
