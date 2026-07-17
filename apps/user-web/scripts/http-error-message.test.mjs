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

// 图片上传技术性错误应转为友好提示，仅保留一个错误编号（不再重复显示请求编号 + 错误编号）
assert.equal(
  friendlyError({ message: '图片上传返回了无法解析的响应（请求编号：web-img-1）（错误编号：web-img-1）', requestId: 'web-img-1' }, '发布失败'),
  '图片上传失败，请稍后重试或更换图片（错误编号：web-img-1）',
)
assert.equal(
  friendlyError({ message: '图片上传失败，闲鱼服务返回了无法识别的内容，请稍后重试或更换图片（请求编号：web-img-2）', requestId: 'web-img-2' }, '发布失败'),
  '图片上传失败，请稍后重试或更换图片（错误编号：web-img-2）',
)
assert.equal(
  friendlyError({ message: '图片上传失败，未能获取闲鱼图片地址，请稍后重试或更换图片（请求编号：web-img-3）', requestId: 'web-img-3' }, '发布失败'),
  '图片上传失败，请稍后重试或更换图片（错误编号：web-img-3）',
)
// 后端消息已包含"请求编号："时，friendlyError 替换为新消息后只附加一次"错误编号："，避免编号重复
assert.equal(
  friendlyError({ message: '闲鱼登录已失效，请到「账号管理」重新登录后再发布（请求编号：web-img-4）', requestId: 'web-img-4' }),
  '登录已失效，请重新扫码或更新 Cookie（错误编号：web-img-4）',
)
// 后端消息已含编号且 friendlyError 原样保留时，不再附加"错误编号："，避免编号重复
assert.equal(
  friendlyError({ message: '商品已发布到闲鱼，但本地保存失败（请求编号：web-img-5）', requestId: 'web-img-5' }),
  '商品已发布到闲鱼，但本地保存失败（请求编号：web-img-5）',
)

console.log('http-error-message: ok')
