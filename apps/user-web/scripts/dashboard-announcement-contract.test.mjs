import assert from 'node:assert/strict'

import {
  getAnnouncementFirstLine,
  selectCurrentAnnouncement,
} from '../src/pages/dashboard/announcement-model.js'

const items = [
  { id: 1, title: '第一条', content: '第一行\n第二行', enabled: true },
  { id: 2, title: '第二条', content: '备用公告', enabled: true },
]

assert.equal(selectCurrentAnnouncement([], []), null)
assert.equal(selectCurrentAnnouncement(items, [])?.id, 1)
assert.equal(selectCurrentAnnouncement(items, [1])?.id, 2)
assert.equal(selectCurrentAnnouncement(items, [1, 2]), null)
assert.equal(getAnnouncementFirstLine(items[0]), '第一行')
assert.equal(getAnnouncementFirstLine({ title: '空内容' }), '')

console.log('dashboard-announcement-contract: ok')
