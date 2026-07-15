import request from '@/utils/http'
import { requireListPayload, requirePagePayload } from '@/utils/api-payload'

export interface PaymentConfigRecord {
  id?: number
  channelType: 'wechat' | 'alipay'
  providerType: 'official' | 'yipay'
  configName?: string
  merchantId?: string
  appId?: string
  privateKey?: string
  publicKey?: string
  apiKey?: string
  notifyUrl?: string
  gatewayUrl?: string
  enabled?: number | boolean
  sandbox?: number | boolean
  remark?: string
}

export function fetchPaymentConfigs() {
  return request.get<PaymentConfigRecord[]>({ url: '/payment/configs' })
    .then(value => requireListPayload<PaymentConfigRecord>(value, '支付通道配置'))
}

export function savePaymentConfig(data: PaymentConfigRecord) {
  return request.post<PaymentConfigRecord>({ url: '/payment/configs', data, showSuccessMessage: true })
}

export function fetchPaymentOrders(params: any) {
  return request.get<any>({ url: '/payment/orders/page', params })
    .then(value => requirePagePayload<any>(value, '支付订单'))
}

export function fetchTokenRechargePlans(params: any) {
  return request.get<any>({ url: '/payment/token-plans/page', params })
    .then(value => requirePagePayload<any>(value, '充值套餐'))
}

export function saveTokenRechargePlan(data: any) {
  return request.post<any>({ url: '/payment/token-plans', data, showSuccessMessage: true })
}

export function deleteTokenRechargePlan(id: number) {
  return request.del<void>({ url: `/payment/token-plans/${id}`, showSuccessMessage: true })
}
