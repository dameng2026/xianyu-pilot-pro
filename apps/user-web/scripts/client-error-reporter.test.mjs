import assert from 'node:assert/strict'

import { sanitizeClientError } from '../src/utils/errorReporter.js'

const secretJwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.secret-signature'
const event = sanitizeClientError(
  new Error(`Checkout failed for alice@example.com / 13812345678; Bearer ${secretJwt}; password=hunter2`),
  {
    type: 'checkout_failure<script>',
    source: 'C:\\Users\\alice\\project\\CheckoutPage.vue?token=top-secret',
    accessToken: secretJwt,
    arbitraryPayload: { buyerPhone: '13812345678' },
  },
  {
    locationLike: { pathname: '/app', hash: '#/orders?token=top-secret&buyer=alice@example.com' },
    navigatorLike: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 SecretExtension/1.2.3' },
    now: () => new Date('2026-07-11T00:00:00.000Z'),
  },
)

assert.deepEqual(
  Object.keys(event).sort(),
  ['column', 'line', 'message', 'route', 'source', 'stack', 'time', 'type', 'userAgent'].sort(),
  'client error payloads must use an explicit field allowlist',
)

const serialized = JSON.stringify(event)
for (const secret of [secretJwt, 'hunter2', 'alice@example.com', '13812345678', 'top-secret', 'SecretExtension']) {
  assert.equal(serialized.includes(secret), false, `client error telemetry must redact ${secret}`)
}
assert.equal(event.route, '#/orders', 'routes must discard query parameters that may carry PII')
assert.equal(event.userAgent, 'Chrome on Windows', 'the persisted user agent must be coarse and version-free')
assert.match(event.type, /^[a-z0-9:_-]+$/i, 'error types must be normalized to a bounded token')
assert.ok(event.message.length <= 320, 'messages must have a strict length bound')
assert.ok(event.stack.length <= 1200, 'stacks must have a strict length bound')
assert.ok(event.source.length <= 120, 'sources must have a strict length bound')

const fragmentEvent = sanitizeClientError(new Error('failed'), {}, {
  locationLike: { pathname: '/app', hash: '#/orders#buyer-alice@example.com' },
  navigatorLike: { userAgent: '' },
})
assert.equal(fragmentEvent.route, '#/orders', 'secondary URL fragments must not be persisted as route telemetry')

console.log('client-error-reporter: ok')
