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
  /** 发送方式：smtp 或 tencent_ses */
  provider: string
  // SMTP 字段（保留，用于 SMTP 模式）
  /** SMTP 服务商（仅前端用于自动填充默认值，不保存到后端） */
  smtpProvider?: string
  smtpHost: string
  smtpPort: number
  encryption: string
  fromEmail: string
  fromName: string
  username: string
  password: string
  passwordConfigured?: boolean
  clearPassword?: boolean
  // 腾讯云 SES 字段
  tencentSecretId?: string
  /** 后端返回的脱敏值（保留前 4 位 + ****） */
  tencentSecretIdMasked?: string
  tencentSecretKey?: string
  tencentSecretKeyConfigured?: boolean
  clearTencentSecretKey?: boolean
  tencentRegion?: string
  tencentFromEmailAddress?: string
  tencentTemplateId?: number
  /** 后端返回的 SES 配置完整性标记 */
  tencentConfigured?: boolean
  // 验证码业务字段
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

export function fetchTestEmail(email: string, provider?: string) {
  return request.post<void>({
    url: '/system/email-config/test',
    data: { email, provider },
    showErrorMessage: false
  })
}
