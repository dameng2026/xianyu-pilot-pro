import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  getPublishAddressMissingFields,
  isPublishAddressComplete,
  normalizePublishAddress,
} from '../src/utils/publishAddress.js'

const legacyPoi = normalizePublishAddress({
  name: '虹桥天地',
  pname: '上海市',
  cityname: '上海市',
  adname: '闵行区',
  adcode: '310112',
  location: '121.3,31.2',
  id: 'legacy-poi',
})
assert.equal(isPublishAddressComplete(legacyPoi), true)

const manualLegacy = normalizePublishAddress({ addressText: '旧手填地址' })
assert.equal(manualLegacy.poiName, '旧手填地址')
assert.deepEqual(getPublishAddressMissingFields(manualLegacy), ['prov', 'city', 'area', 'divisionId', 'gps', 'poiId'])

const [product, opportunity, workflow] = await Promise.all([
  readFile(new URL('../src/pages/ProductPublishPage.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/pages/OpportunityPage.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/pages/WorkflowPage.vue', import.meta.url), 'utf8'),
])

for (const page of [product, opportunity, workflow]) {
  assert.match(page, /PublishAddressCascader/)
}
assert.match(product, /isPublishAddressComplete\(selectedAddress\.value\)/)
assert.match(opportunity, /isPublishAddressComplete\(location\)/)
assert.match(workflow, /请先在发布节点中选择完整的省、市、区/)

const retiredProvider = ['a', 'map'].join('')
for (const page of [opportunity, workflow]) {
  assert.equal(page.toLowerCase().includes(retiredProvider), false)
}

console.log('publish-address-contract: ok')
