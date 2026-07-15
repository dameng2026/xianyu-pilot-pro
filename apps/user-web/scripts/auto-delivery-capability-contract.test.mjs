import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'src', 'pages', 'AutoDeliveryPage.vue'),
  'utf8'
)

assert(!source.includes('<option value="api">'), 'API delivery must not be selectable before a secure adapter exists')
assert(source.includes("if (cfg.mode === 'api') return 'API 模式暂不可用'"), 'legacy API rules should show an honest unavailable state')
assert(source.includes("['text', 'card'].includes(config.mode)"), 'editing a legacy rule should migrate it to a supported mode')

console.log('auto-delivery-capability-contract: ok')
