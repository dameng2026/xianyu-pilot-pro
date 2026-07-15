import assert from 'node:assert/strict'

import { createRequestGate } from '../src/utils/requestLifecycle.js'

const gate = createRequestGate()
const first = gate.begin()
const second = gate.begin()

assert.equal(gate.isCurrent(first), false, 'a newer request must invalidate an older response')
assert.equal(gate.isCurrent(second), true, 'the latest response may update the active view')

gate.dispose()
assert.equal(gate.isCurrent(second), false, 'disposed views must ignore every pending response')

console.log('request-lifecycle: ok')
