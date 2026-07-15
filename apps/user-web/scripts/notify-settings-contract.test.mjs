import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const sourcePath = path.join(root, 'src', 'pages', 'settings', 'NotifySettings.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

for (const expected of [
  'notify-settings-shell',
  'notify-hero',
  'notify-summary-grid',
  'notify-health-card',
  'notify-channel-list',
  'notify-config-card',
  'notify-rules-card',
  'notify-logs-card',
  'notify-preview-phone',
  'Notification Control Center',
  'copyWebhookUrl',
  'renderChannelDescription',
  'settingsAvailable',
  'deliveryLogsLoadError',
  'notificationsLoadError',
  '暂无真实投递记录',
  '仅展示接口返回的真实通知'
]) {
  assert(source.includes(expected), `NotifySettings should include: ${expected}`)
}

for (const forbidden of [
  'TARGET_OVERVIEW',
  'FALLBACK_LOGS',
  'FALLBACK_PREVIEW',
  '较昨日 ↑',
  '最近一次测试发送成功，响应耗时 1.2 秒'
]) {
  assert(!source.includes(forbidden), `NotifySettings must not fabricate operational state: ${forbidden}`)
}

console.log('notify-settings-contract: ok')
