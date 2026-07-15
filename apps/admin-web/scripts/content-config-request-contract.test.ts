import assert from 'node:assert/strict'

import { buildFreshContentListRequest } from '../src/api/content-config'

assert.deepEqual(buildFreshContentListRequest('/admin/carousel/list'), {
  url: '/admin/carousel/list',
  cacheTtl: 0,
  skipDedupe: true,
})

assert.deepEqual(buildFreshContentListRequest('/admin/announcement/list'), {
  url: '/admin/announcement/list',
  cacheTtl: 0,
  skipDedupe: true,
})

console.log('content-config-request-contract: ok')
