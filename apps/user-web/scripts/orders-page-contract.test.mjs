import assert from 'node:assert/strict'

import {
  buildOrdersQuery,
  buildManualDeliveryPayload,
  buildOrderDetailViewModel
} from '../src/utils/orderPageState.js'

const detail = buildOrderDetailViewModel({
  externalOrderId: 'ORDER-55',
  deliveryMethod: 'manual_text',
  deliveryStatus: 'partial',
  quantityRequested: 3,
  quantitySent: 1,
  items: [
    {
      goodsTitle: 'Digital Pack',
      goodsCount: 3,
      specName: 'Version',
      specValue: 'Standard'
    }
  ]
})

assert.equal(detail.deliveryProgressText, '1 / 3')
assert.equal(detail.itemLines[0], 'Digital Pack x3 | Version: Standard')
assert.equal(detail.deliveryBadge, 'orange')
assert.equal(detail.deliveryMethodText, '手动文本发货')

assert.deepEqual(
  buildManualDeliveryPayload({
    deliveryMode: 'text',
    deliveryTiming: 'after_payment',
    deliveryContent: '  download-link  ',
    quantityRequested: '2'
  }),
  {
    deliveryMode: 'text',
    deliveryTiming: 'after_payment',
    deliveryContent: 'download-link',
    quantityRequested: 2
  }
)

assert.deepEqual(
  buildOrdersQuery({
    accountId: '8',
    keyword: 'buyer-a',
    status: '2',
    current: 1,
    size: 20
  }),
  {
    accountId: 8,
    keyword: 'buyer-a',
    status: 2,
    current: 1,
    size: 20
  }
)

assert.deepEqual(
  buildOrdersQuery({
    accountId: '8',
    keyword: '',
    status: '',
    current: 2,
    size: 20
  }),
  {
    accountId: 8,
    current: 2,
    size: 20
  }
)

assert.deepEqual(
  buildOrdersQuery({
    accountId: '8',
    keyword: '',
    status: '',
    current: 2,
    size: 20,
    sync: false
  }),
  {
    accountId: 8,
    current: 2,
    size: 20
  }
)

assert.deepEqual(
  buildOrdersQuery({
    accountId: '8',
    keyword: '',
    status: '',
    current: 2,
    size: 20,
    sync: true
  }),
  {
    accountId: 8,
    current: 2,
    size: 20,
    sync: true
  }
)

console.log('orders-page-contract: ok')
