import request from '@/utils/http'
import { requireRecordPayload } from '@/utils/api-payload'

export interface SmsConfigData {
  provider: string
  apiUrl: string
  accessKeyId: string
  accessKeySecret: string
  accessKeySecretConfigured?: boolean
  clearAccessKeySecret?: boolean
  signName: string
  templateCode: string
  templateParam: string
  codeLength: number
  validSeconds: number
  sendInterval: number
  dailyLimit: number
}

export interface EmailConfigData {
  provider: string
  smtpHost: string
  smtpPort: number
  encryption: string
  fromEmail: string
  fromName: string
  username: string
  password: string
  passwordConfigured?: boolean
  clearPassword?: boolean
  subject: string
  template: string
  codeLength: number
  validSeconds: number
  sendInterval: number
  dailyLimit: number
}

export function fetchGetSmsConfig() {
  return request.get<SmsConfigData>({
    url: '/system/sms-config',
    skipDedupe: true,
    showErrorMessage: false
  }).then(value => requireRecordPayload<Record<string, any>>(value, '短信配置') as SmsConfigData)
}

export function fetchSaveSmsConfig(data: SmsConfigData) {
  return request.post<void>({ url: '/system/sms-config', data, showErrorMessage: false })
}

export function fetchGetEmailConfig() {
  return request.get<EmailConfigData>({
    url: '/system/email-config',
    skipDedupe: true,
    showErrorMessage: false
  }).then(value => requireRecordPayload<Record<string, any>>(value, '邮件配置') as EmailConfigData)
}

export function fetchSaveEmailConfig(data: EmailConfigData) {
  return request.post<void>({ url: '/system/email-config', data, showErrorMessage: false })
}

export function fetchTestEmail(email: string) {
  return request.post<void>({
    url: '/system/email-config/test',
    data: { email },
    showErrorMessage: false
  })
}
