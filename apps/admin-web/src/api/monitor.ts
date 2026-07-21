import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

export interface MonitorQuery {
  days?: number
  current?: number
  size?: number
  scene?: string
  keyword?: string
  status?: string
  userId?: number | string
}

export interface MonitorRequestUiOptions {
  showErrorMessage?: boolean
}

export function getAiMonitor(params: MonitorQuery = {}, options: MonitorRequestUiOptions = {}) {
  return request.get<any>({ url: '/monitor/ai', params, showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'AI 监控'))
}

export function getAiUsagePage(params: MonitorQuery = {}) {
  return request.get<any>({ url: '/monitor/ai/usage', params })
    .then(value => requirePagePayload<any>(value, 'AI 调用日志'))
}

export function getAiTokenStats(params: { days?: number } = {}, options: MonitorRequestUiOptions = {}) {
  return request.get<any>({ url: '/monitor/ai/token-stats', params, showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'AI Token 统计'))
}

export function getAiCostStats(params: { days?: number; groupBy?: string } = {}, options: MonitorRequestUiOptions = {}) {
  return request.get<any>({ url: '/monitor/ai/cost-stats', params, showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'AI 成本统计'))
}

export function getAiUserStats(params: {
  current?: number
  size?: number
  days?: number
  keyword?: string
  sortBy?: string
  sortOrder?: string
} = {}) {
  return request.get<any>({ url: '/monitor/ai/user-stats', params })
    .then(value => requirePagePayload<any>(value, 'AI 用户统计'))
}

export function getAutoReplyMonitor(params: MonitorQuery = {}, options: MonitorRequestUiOptions = {}) {
  return request.get<any>({ url: '/monitor/auto-reply', params, showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, '自动回复监控'))
}

export function getWorkflowMonitor(params: MonitorQuery = {}, options: MonitorRequestUiOptions = {}) {
  return request.get<any>({ url: '/monitor/workflow', params, showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, '工作流监控'))
}
