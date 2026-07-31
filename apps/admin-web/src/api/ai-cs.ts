import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

// ===== AI 客服后台管理 API =====
// 对接后端 AdminAiCsController，前缀 /admin-api/ai-cs/*（baseURL 已由 http 工具注入）

// ----- 类型定义 -----

export interface AiCsStats {
  totalSessions?: number
  activeSessions?: number
  todaySessions?: number
  totalMessages?: number
  todayMessages?: number
  totalChargeTokens?: number
  todayChargeTokens?: number
  casualCount?: number
  knowledgeCount?: number
  toolCallCount?: number
  [key: string]: any
}

export interface AiCsSessionQuery {
  current?: number
  size?: number
  userId?: number | string | null
  status?: string | null
}

export interface AiCsSessionRow {
  id: number
  sessionId?: number | string
  sessionToken?: string
  userId?: number
  username?: string
  tenantId?: number
  status?: string
  messageCount?: number
  casualCount?: number
  lastActiveTime?: string
  createdTime?: string
  [key: string]: any
}

export interface AiCsMessageQuery {
  current?: number
  size?: number
  sessionId?: number | string | null
  userId?: number | string | null
  role?: string | null
}

export interface AiCsMessageRow {
  id: number
  sessionId?: number
  userId?: number
  username?: string
  role?: string
  content?: string
  tokensCharged?: number
  isCasual?: number | boolean
  toolCalls?: string | any
  createdTime?: string
  [key: string]: any
}

export interface AiCsToolCallQuery {
  current?: number
  size?: number
  sessionId?: number | string | null
  status?: string | null
}

export interface AiCsToolCallRow {
  id: number
  sessionId?: number
  userId?: number
  toolName?: string
  status?: string
  arguments?: string
  result?: string
  createdTime?: string
  [key: string]: any
}

export interface AiCsBillingConfig {
  enabled?: number | boolean
  perMessageTokens?: number
  maxContextMessages?: number
  casualThreshold?: number
  casualReminderText?: string
  dailyFreeQuota?: number
  [key: string]: any
}

export interface AiCsKnowledgeCategory {
  key: string
  label: string
  /** 父分类 ID（一级分类为 null） */
  parent_id?: number | null
  /** 该分类下的知识库条目数 */
  entry_count?: number
  /** 子分类列表（用于三级分类树形结构） */
  children?: AiCsKnowledgeCategory[]
}

export interface AiCsKnowledgeQuery {
  current?: number
  size?: number
  category?: string | null
  keyword?: string | null
  enabled?: string | null
}

export interface AiCsKnowledgeRow {
  id: number
  tenantId?: number | null
  category?: string
  title?: string
  content?: string
  keywords?: string
  priority?: number
  enabled?: number | boolean
  sortOrder?: number
  createdTime?: string
  updatedTime?: string
  [key: string]: any
}

export interface AiCsKnowledgeForm {
  id?: number | string | null
  category?: string
  title?: string
  content?: string
  keywords?: string
  priority?: number
  enabled?: number | boolean | string
  sortOrder?: number
}

// ----- API 函数 -----

export function getAiCsStats() {
  return request.get<any>({ url: '/ai-cs/stats' })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'AI 客服统计') as AiCsStats)
}

export function pageAiCsSessions(params: AiCsSessionQuery = {}) {
  return request.get<any>({ url: '/ai-cs/sessions/page', params })
    .then(value => requirePagePayload<AiCsSessionRow>(value, '会话审计'))
}

export function pageAiCsMessages(params: AiCsMessageQuery = {}) {
  return request.get<any>({ url: '/ai-cs/messages/page', params })
    .then(value => requirePagePayload<AiCsMessageRow>(value, '消息审计'))
}

// 获取指定会话的全部消息（按时间正序，完整内容）。
// 供后台"对话气泡视图"使用：一次性加载完整对话流，不分页。
export function listSessionAiCsMessages(sessionId: number | string) {
  return request.get<any>({ url: `/ai-cs/messages/session/${sessionId}` })
    .then(value => {
      // 后端返回 Result<List<Map>>，http 拦截器通常已解包 data 字段
      if (Array.isArray(value)) return value as AiCsMessageRow[]
      if (value && Array.isArray((value as any).data)) return (value as any).data as AiCsMessageRow[]
      return [] as AiCsMessageRow[]
    })
}

export function pageAiCsToolCalls(params: AiCsToolCallQuery = {}) {
  return request.get<any>({ url: '/ai-cs/tool-calls/page', params })
    .then(value => requirePagePayload<AiCsToolCallRow>(value, '工具调用审计'))
}

export function getAiCsBillingConfig() {
  return request.get<any>({ url: '/ai-cs/billing-config' })
    .then(value => requireRecordPayload<Record<string, any>>(value, '计费配置') as AiCsBillingConfig)
}

export function saveAiCsBillingConfig(data: AiCsBillingConfig) {
  return request.put<any>({ url: '/ai-cs/billing-config', data })
}

export function getAiCsKnowledgeCategories() {
  return request.get<any>({ url: '/ai-cs/knowledge/categories' })
    .then(value => {
      if (Array.isArray(value)) return value as AiCsKnowledgeCategory[]
      if (value && Array.isArray((value as any).data)) return (value as any).data as AiCsKnowledgeCategory[]
      return []
    })
}

export function pageAiCsKnowledge(params: AiCsKnowledgeQuery = {}) {
  return request.get<any>({ url: '/ai-cs/knowledge/page', params })
    .then(value => requirePagePayload<AiCsKnowledgeRow>(value, '知识库'))
}

export function saveAiCsKnowledge(data: AiCsKnowledgeForm) {
  return request.post<any>({ url: '/ai-cs/knowledge', data })
}

export function getAiCsKnowledgeDetail(id: number | string) {
  return request.get<any>({ url: `/ai-cs/knowledge/${id}` })
    .then(value => requireRecordPayload<Record<string, any>>(value, '知识库详情') as AiCsKnowledgeRow)
}

export function deleteAiCsKnowledge(id: number | string) {
  return request.del<any>({ url: `/ai-cs/knowledge/${id}` })
}

export function rebuildAiCsKnowledgeIndex() {
  return request.post<any>({ url: '/ai-cs/knowledge/rebuild', data: {} })
}
