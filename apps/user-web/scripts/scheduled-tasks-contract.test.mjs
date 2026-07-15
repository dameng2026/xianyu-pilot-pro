import assert from 'node:assert/strict'

import {
  normalizeScheduledTaskPayload,
  normalizeScheduledTaskTypes
} from '../src/utils/scheduledTaskState.js'

assert.deepEqual(
  normalizeScheduledTaskTypes(['sync_goods', 'sync_orders', 'sync_delivery_status', 'redelivery']),
  [
    { value: 'sync_goods', label: '同步商品' },
    { value: 'sync_orders', label: '同步订单' },
    { value: 'sync_delivery_status', label: '同步发货状态' },
    { value: 'redelivery', label: '安排重新发货' }
  ]
)

assert.deepEqual(
  normalizeScheduledTaskPayload({
    taskName: 'Sync sold orders',
    taskType: 'Sync_Orders',
    cronExpression: ' 0 0/30 * * * ? ',
    configJson: '{"accountId":8}',
    accountId: '8',
    enabled: true
  }),
  {
    taskName: 'Sync sold orders',
    taskType: 'sync_orders',
    cronExpression: '0 0/30 * * * ?',
    configJson: '{"accountId":8}',
    accountId: 8,
    enabled: 1
  }
)

console.log('scheduled-tasks-contract: ok')
