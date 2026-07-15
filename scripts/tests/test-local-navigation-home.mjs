import assert from 'node:assert/strict'

const baseUrl = process.env.LOCAL_API_BASE_URL || 'http://localhost:18080'
const username = String(process.env.TEST_USER_USERNAME || '').trim()
const password = String(process.env.TEST_USER_PASSWORD || '')

assert.ok(username, 'TEST_USER_USERNAME is required')
assert.ok(password, 'TEST_USER_PASSWORD is required')

const loginResponse = await fetch(`${baseUrl}/api/login/login`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ username, password })
})
assert.equal(loginResponse.status, 200, `login HTTP status: ${loginResponse.status}`)

const login = await loginResponse.json()
assert.equal(login.code, 200, `login business code: ${login.code}`)
const token = login.data?.token
assert.ok(token, 'login response must include a token')

const response = await fetch(`${baseUrl}/api/navigation/home?limit=5`, {
  headers: { authorization: `Bearer ${token}` }
})
assert.equal(response.status, 200, `navigation HTTP status: ${response.status}`)

const payload = await response.json()
assert.equal(payload.code, 200, `navigation business code: ${payload.code}; msg=${payload.msg || ''}`)
assert.ok(payload.data && typeof payload.data === 'object', 'navigation response must include data')

console.log('local-navigation-home: ok')
