import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const sourcePath = path.join(root, 'src', 'pages', 'AccountsPage.vue')
const source = fs.readFileSync(sourcePath, 'utf8')
const apiSourcePath = path.join(root, 'src', 'api', 'accounts.js')
const apiSource = fs.readFileSync(apiSourcePath, 'utf8')

for (const expectedExport of [
  'export function getAccountAutoRateConfig',
  'export function saveAccountAutoRateConfig',
  'export function getAccountFaceVerifications',
  'export function markAccountFaceVerificationRead',
  'export function getAccountStrategyConfig',
  'export function saveAccountStrategyConfig',
  'export function getAccountLoginCredential',
  'export function saveAccountLoginCredential',
]) {
  assert(apiSource.includes(expectedExport), `accounts api should export: ${expectedExport}`)
}

for (const expected of [
  '人脸验证',
  '自动评价',
  '消息等待',
  '定时补发货',
  '自动回复',
  '自动发货',
  '连接管理',
  '在线消息',
  '统一配置',
  "modal==='faceVerify'",
  "modal==='autoRate'",
  "modal==='accountStrategy'",
  'openFaceVerificationModal',
  'openAutoRateModal',
  'openAccountStrategyModal',
  "modal==='loginCredential'",
  'openLoginCredentialModal',
  'saveAccountLoginCredential',
  'accountLoginCredentialForm.loginUsername',
  'accountStrategyForm.autoPolish',
  'saveAutoRateConfig',
  'markFaceVerificationRead',
  'saveAccountStrategyConfig',
]) {
  assert(source.includes(expected), `AccountsPage should include: ${expected}`)
}

for (const unexpected of [
  '鑷姩鍥炲',
  '鑷姩鍙戣揣',
  '杩炴帴绠＄悊',
  '鍦ㄧ嚎娑堟伅',
]) {
  assert(!source.includes(unexpected), `AccountsPage should not include mojibake text: ${unexpected}`)
}

console.log('accounts-page-contract: ok')
