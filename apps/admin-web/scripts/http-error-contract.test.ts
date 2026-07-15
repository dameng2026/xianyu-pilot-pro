import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import {
  formatHttpErrorDisplay,
  getHttpStatusMessageKey,
  isAuthorizationForCurrentSession,
  normalizeRequestId,
  selectSafeServerMessage,
  shouldRetryHttpRequest
} from '../src/utils/http/error-policy'

assert.equal(selectSafeServerMessage('余额不足，请先充值', '支付失败'), '余额不足，请先充值')
assert.equal(selectSafeServerMessage('  参数冲突\n请刷新后重试  ', '请求失败'), '参数冲突 请刷新后重试')
assert.equal(
  selectSafeServerMessage('<script>alert(1)</script>', '服务器异常'),
  '服务器异常',
  '服务端返回标记语言时不得直接展示'
)
assert.equal(
  selectSafeServerMessage('java.lang.IllegalStateException at com.example.Secret', '服务器异常'),
  '服务器异常',
  '堆栈和内部类名不得暴露给用户'
)
assert.equal(
  selectSafeServerMessage('database password=prod-secret', '服务器异常'),
  '服务器异常',
  '可能含密钥的服务端信息必须回退为安全提示'
)

assert.equal(normalizeRequestId(' req-20260710_A.42 '), 'req-20260710_A.42')
assert.equal(normalizeRequestId('<img onerror=alert(1)>'), undefined)
assert.equal(formatHttpErrorDisplay('无权操作', 'req-42'), '无权操作（请求 ID：req-42）')
assert.equal(formatHttpErrorDisplay('无权操作', undefined), '无权操作')
assert.equal(shouldRetryHttpRequest('GET', 503), true)
assert.equal(shouldRetryHttpRequest('get', 502), true)
assert.equal(shouldRetryHttpRequest('GET', 400), false)
assert.equal(shouldRetryHttpRequest('POST', 503), false)
assert.equal(shouldRetryHttpRequest('PUT', 500), false)
assert.equal(shouldRetryHttpRequest('DELETE', 503), false)
assert.equal(isAuthorizationForCurrentSession('Bearer current-token', 'current-token'), true)
assert.equal(isAuthorizationForCurrentSession('old-token', 'current-token'), false)
assert.equal(isAuthorizationForCurrentSession(undefined, 'current-token'), false)
assert.equal(isAuthorizationForCurrentSession('Bearer current-token', ''), false)

assert.deepEqual(
  [400, 401, 402, 403, 404, 409, 429, 500, 502, 503].map(getHttpStatusMessageKey),
  [
    'httpMsg.badRequest',
    'httpMsg.unauthorized',
    'httpMsg.paymentRequired',
    'httpMsg.forbidden',
    'httpMsg.notFound',
    'httpMsg.conflict',
    'httpMsg.tooManyRequests',
    'httpMsg.internalServerError',
    'httpMsg.badGateway',
    'httpMsg.serviceUnavailable'
  ]
)

const httpSource = fs.readFileSync(path.resolve('src/utils/http/index.ts'), 'utf8')
assert(
  httpSource.includes("method === 'GET'"),
  '自动重试必须限于 GET，禁止重试 POST/PUT/DELETE 导致重复写入'
)
assert(
  httpSource.includes("error.config?.url") && httpSource.includes('isLoginRequest'),
  '登录请求 401 必须与登录后会话失效分开处理'
)
assert(
  httpSource.includes("!response.data || typeof response.data !== 'object'"),
  '非标准成功响应必须失败关闭，不得伪造成功或泄漏原始异常'
)

console.log('http-error-contract: ok')
