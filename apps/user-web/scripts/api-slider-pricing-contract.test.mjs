import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (...segments) => fs.readFileSync(path.join(root, ...segments), 'utf8')

const overview = read('src', 'components', 'api-slider', 'ApiOverviewCards.vue')
const config = read('src', 'components', 'api-slider', 'ApiConfigCard.vue')
const mobile = read('src', 'mobile', 'MobileApiSliderSolve.vue')
const page = read('src', 'pages', 'ApiSliderSolvePage.vue')
const docs = read('src', 'components', 'api-slider', 'ApiDocsCard.vue')

for (const source of [overview, config, mobile]) {
  assert.doesNotMatch(source, /\?\?\s*5\s*Token/)
  assert.doesNotMatch(source, /\?\?\s*0\.05/)
  assert.match(source, /不可用/)
}

assert.doesNotMatch(page, /完整密钥仅生成一次/)
assert.match(docs, /动态价格|以页面显示价格为准|实际价格以接口返回为准/)
assert.doesNotMatch(docs, /tokenCharged["']?\s*:\s*5/)
assert.doesNotMatch(docs, /扣费\s*5\s*Token/)

console.log('api-slider-pricing-contract: ok')
