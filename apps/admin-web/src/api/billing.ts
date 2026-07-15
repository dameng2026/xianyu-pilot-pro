import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

export interface ModelPriceQuery {
  current?: number
  size?: number
  keyword?: string
  modelType?: string
  enabled?: string
}

export interface ModelPriceForm {
  id?: number | string
  moduleKey?: string
  providerName?: string
  modelName?: string
  modelType?: string
  billingMode?: string
  inputPricePer1k?: number | string
  outputPricePer1k?: number | string
  cachedInputPricePer1k?: number | string
  perCallPrice?: number | string
  specPriceJson?: string
  tokenExchangeRate?: number | string
  minChargeToken?: number | string
  billingUnit?: string
  costPerImage?: number | string
  tokensPerImage?: number | string
  costPerCall?: number | string
  tokensPerCall?: number | string
  enabled?: number | string
  remark?: string
}

export interface ModelPriceRow extends ModelPriceForm {
  id: number
  tenantId?: number | null
  enabledText?: string
  billingUnitText?: string
  inputPriceText?: string
  outputPriceText?: string
  cachedInputPriceText?: string
  perCallPriceText?: string
  costPerImageText?: string
  tokensPerImageText?: string
  costPerCallText?: string
  tokensPerCallText?: string
  profitText?: string
  profitYuan?: string | null
  createdTime?: string
  updatedTime?: string
}

export interface BillingSummary {
  todayChargeTokens?: number
  todayCostCent?: number
  todayCachedTokens?: number
  totalCachedTokens?: number
  enabledModels?: number
  lowBalanceUsers?: number
}

export function getModelPricesPage(params: ModelPriceQuery = {}) {
  return request.get<any>({ url: '/ai-billing/model-prices/page', params })
    .then(value => requirePagePayload<ModelPriceRow>(value, '模型价格'))
}

export function saveModelPrice(data: ModelPriceForm) {
  return request.post<any>({ url: '/ai-billing/model-prices', data })
}

export function deleteModelPrice(id: number) {
  return request.del<any>({ url: `/ai-billing/model-prices/${id}` })
}

export function getBillingSummary() {
  return request.get<BillingSummary>({ url: '/ai-billing/summary' })
    .then(value => requireRecordPayload<Record<string, any>>(value, '计费汇总') as BillingSummary)
}
