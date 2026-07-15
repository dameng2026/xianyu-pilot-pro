import assert from 'node:assert/strict'

import {
  buildDeliveryRecordDetailViewModel,
  buildScheduleRedeliveryPayload,
  canScheduleRedelivery
} from '../src/utils/deliveryRecordsPageState.js'

const detail = buildDeliveryRecordDetailViewModel({
  status: 3,
  deliveryStatus: 'failed',
  quantityRequested: 3,
  quantitySent: 1,
  deliveryContent: 'download-link',
  platformSyncTime: '2026-07-03T10:00:00'
})

assert.equal(detail.deliveryProgressText, '1 / 3')
assert.equal(detail.deliveryBadge, 'red')
assert.equal(detail.platformSyncTimeText, '2026-07-03 10:00:00')
assert.equal(canScheduleRedelivery({ status: 3, deliveryStatus: 'failed' }), true)
assert.equal(canScheduleRedelivery({ status: 2, deliveryStatus: 'success' }), false)

assert.deepEqual(
  buildScheduleRedeliveryPayload({ cronExpression: ' 0 0/15 * * * ? ' }),
  { cronExpression: '0 0/15 * * * ?' }
)

console.log('delivery-records-contract: ok')
