import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const appRoot = path.resolve(__dirname, '..')
const repoRoot = path.resolve(appRoot, '..', '..')
const apiSource = fs.readFileSync(path.join(appRoot, 'src', 'api', 'qrlogin.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(appRoot, 'src', 'pages', 'AccountsPage.vue'), 'utf8')
const controllerSource = fs.readFileSync(
  path.join(repoRoot, 'apps', 'core-api', 'src', 'main', 'java', 'com', 'xianyu', 'admin', 'controller', 'UserQrLoginController.java'),
  'utf8'
)

assert(!apiSource.includes('/qrlogin/cookies'), 'browser API must not expose QR session cookies')
assert(!apiSource.includes('getQrLoginCookies'), 'browser API must not define a raw-cookie helper')
assert(!pageSource.includes('getQrLoginCookies'), 'AccountsPage must rely on persisted account status, not raw cookies')
assert(!controllerSource.includes('@GetMapping("/cookies/'), 'core API must not return QR cookies to the browser')
assert(controllerSource.includes('/api/internal/qrlogin/cookies/'), 'rescan may retrieve credentials only over the internal service boundary')

console.log('qr-cookie-boundary-contract: ok')
