import assert from 'node:assert/strict'
import fs from 'node:fs'

import { buildUnifiedCarouselConfig, buildCarouselSavePlan } from '../src/views/admin/carousel/page-model'

const unified = buildUnifiedCarouselConfig([
  {
    id: 11,
    title: '首页轮播',
    description: '主轮播',
    imageUrl: '/banner-a.png',
    linkUrl: 'https://a.example.com',
    sourceType: 'upload',
    sortOrder: 2,
    enabled: true,
    coverItems: [
      {
        id: 'cover-a2',
        title: '第二张',
        description: '第二张图',
        imageUrl: '/banner-a2.png',
        linkUrl: 'https://a2.example.com',
        sourceType: 'upload',
        sortOrder: 1,
        enabled: true
      }
    ]
  },
  {
    id: 10,
    title: '旧轮播位',
    description: '历史数据',
    imageUrl: '/banner-b.png',
    linkUrl: 'https://b.example.com',
    sourceType: 'upload',
    sortOrder: 0,
    enabled: true,
    coverItems: [
      {
        id: 'cover-b1',
        title: '第一张',
        description: '第一张图',
        imageUrl: '/banner-b1.png',
        linkUrl: 'https://b1.example.com',
        sourceType: 'upload',
        sortOrder: 0,
        enabled: true
      }
    ]
  }
])

assert.equal(unified.id, 10)
assert.equal(unified.legacyItemCount, 2)
assert.deepEqual(
  unified.coverItems.map(item => item.id),
  ['cover-b1', 'cover-a2']
)

const savePlan = buildCarouselSavePlan(unified)

assert.equal(savePlan.payload.imageUrl, '/banner-b1.png')
assert.equal(savePlan.payload.linkUrl, 'https://b1.example.com')
assert.equal(savePlan.payload.coverItems?.length, 2)

const openSourceApi = fs.readFileSync(
  new URL('../src/api/open-source-content.ts', import.meta.url),
  'utf8'
)
const openSourceAbout = fs.readFileSync(
  new URL('../src/views/admin/open-source/about/index.vue', import.meta.url),
  'utf8'
)
const commercialCarousel = fs.readFileSync(
  new URL('../src/views/admin/carousel/index.vue', import.meta.url),
  'utf8'
)
const openSourceCarousel = fs.readFileSync(
  new URL('../src/views/admin/open-source/home/index.vue', import.meta.url),
  'utf8'
)
assert.match(openSourceApi, /\/open-source-admin\/media\/upload/)
assert.match(openSourceApi, /\/open-source-admin\/media\/import-from-url/)
assert.match(openSourceAbout, /uploadOpenSourceContentImage/)
assert.match(openSourceAbout, /importOpenSourceContentImageFromUrl/)
assert.doesNotMatch(openSourceAbout, /uploadCarouselImage/)
for (const uploadPage of [commercialCarousel, openSourceCarousel, openSourceAbout]) {
  assert.match(uploadPage, /image\/png/)
  assert.match(uploadPage, /image\/jpeg/)
  assert.doesNotMatch(uploadPage, /image\/webp/)
}

console.log('content-config-contract: ok')
