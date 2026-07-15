import assert from 'node:assert/strict'

import { friendlyError } from '../src/utils/friendlyError.js'
import { httpErrorMessage } from '../src/utils/httpErrorMessage.js'

assert.equal(httpErrorMessage(502, 'Bad Gateway'), '服务暂时不可用，请稍后重试')
assert.equal(httpErrorMessage(503, { message: 'Service Unavailable' }), '服务暂时不可用，请稍后重试')
assert.equal(httpErrorMessage(503, { msg: '短信服务暂不可用，请联系部署方' }), '短信服务暂不可用，请联系部署方')
assert.equal(httpErrorMessage(401, null), '登录状态无效，请重新登录')
assert.equal(httpErrorMessage(429, null), '操作过于频繁，请稍后再试')
assert.equal(
  friendlyError({ message: 'Request failed with status code 502', requestId: 'web-test-1' }, '验证码发送失败'),
  '服务暂时不可用，请稍后重试（错误编号：web-test-1）',
)
assert.equal(
  friendlyError({ message: 'java.lang.IllegalStateException', requestId: 'web-test-2' }, '操作失败'),
  '操作失败（错误编号：web-test-2）',
)

console.log('http-error-message: ok')
