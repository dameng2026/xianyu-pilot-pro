import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

for (const [channel, relativePath, configuredFlag] of [
  ['短信', 'src/views/system/sms-config/index.vue', 'accessKeySecretConfigured'],
  ['邮件', 'src/views/system/email-config/index.vue', 'passwordConfigured']
] as const) {
  const source = fs.readFileSync(path.resolve(relativePath), 'utf8')

  assert(source.includes('<AdminDataState'), `${channel}配置必须区分加载失败与真实空值`)
  assert(source.includes("configState !== 'ready'"), `${channel}配置读取失败时必须禁用保存`)
  assert(source.includes('发送器未接入'), `${channel}页面必须显示真实发送能力不可用`)
  assert(source.includes('无真实记录'), `${channel}页面不得伪造或暗示存在发送记录`)
  assert(source.includes(configuredFlag), `${channel}密钥已配置时必须允许留空保留`)
  assert(source.includes('Object.assign(form, response)'), `${channel}配置必须使用 request 已解包的直接响应`)
  assert(source.includes('配置草稿已保存'), `${channel}保存文案不得暗示发送能力已生效`)
  assert(!source.includes('res.data'), `${channel}配置不得对已解包响应再读取 data`)
  assert(!source.includes('/records'), `${channel}页面不得请求不存在的 records 接口`)
  assert(!source.includes('/test'), `${channel}发送器未接入时不得发起测试请求`)
  assert(!source.includes('发送成功'), `${channel}页面不得保留可能的假成功文案`)
}

const apiSource = fs.readFileSync(path.resolve('src/api/notification-config.ts'), 'utf8')
assert(!apiSource.includes('/test'), '前端 API 层不应暴露尚未实现的测试发送能力')

console.log('notification-config-state-contract: ok')
