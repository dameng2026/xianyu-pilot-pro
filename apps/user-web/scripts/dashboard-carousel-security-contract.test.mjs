import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'src', 'pages', 'DashboardPage.vue'),
  'utf8'
)

assert(source.includes('safeCarouselLink'), 'carousel navigation should validate destinations in the browser')
assert(source.includes("'noopener,noreferrer'"), 'carousel links should isolate window.opener')
assert(!source.includes("window.open(item.linkUrl, '_blank')"), 'raw carousel URLs must never be opened')
assert(source.includes("parsed.protocol !== 'http:' && parsed.protocol !== 'https:'"), 'carousel links should allow only HTTP/HTTPS protocols')

console.log('dashboard-carousel-security-contract: ok')
