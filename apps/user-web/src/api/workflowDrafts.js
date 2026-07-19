import request from '../utils/request.js'
import { pageParams } from '../utils/apiData.js'

/**
 * 工作流商品草稿箱 API
 *
 * 后端路由（Java AutomationProxyController 透传到 Python workflow.py）：
 *   GET    /workflow/drafts                         列表（分页 + 过滤）
 *   GET    /workflow/drafts/stats                   汇总统计
 *   GET    /workflow/drafts/{draftId}               草稿详情
 *   POST   /workflow/drafts/{draftId}/retry-publish 单条重试发布（可选 accountId 指定账号）
 *   POST   /workflow/drafts/batch-retry-publish     批量重试发布（可选 accountId 指定账号）
 *   DELETE /workflow/drafts/{draftId}               删除草稿
 *
 * 列表参数：{ page, pageSize, status, workflowId, keyword, startDate, endDate }
 * 状态取值：all / draft / publishing / published / failed
 *
 * 重试发布 accountId 参数：
 *   - 传入时使用该账号发布（用于"选择账号后重新发布"）
 *   - 不传时回退到草稿原 account_id
 */

export const listWorkflowDrafts = params => request.get('/workflow/drafts', { params: pageParams(params) })

export const getWorkflowDraftStats = () => request.get('/workflow/drafts/stats')

export const getWorkflowDraft = draftId => request.get(`/workflow/drafts/${draftId}`)

/**
 * 重试发布单个草稿
 * @param {number} draftId 草稿 ID
 * @param {number} [accountId] 可选，指定重新发布使用的账号 ID
 */
export const retryPublishDraft = (draftId, accountId) => {
  const payload = {}
  if (accountId !== undefined && accountId !== null && accountId !== '') {
    payload.accountId = accountId
  }
  return request.post(`/workflow/drafts/${draftId}/retry-publish`, payload)
}

/**
 * 批量重试发布
 * @param {number[]} ids 草稿 ID 数组
 * @param {number} [accountId] 可选，指定重新发布使用的账号 ID（所有草稿统一使用此账号）
 */
export const batchRetryPublishDrafts = (ids, accountId) => {
  const payload = { ids: Array.isArray(ids) ? ids : [] }
  if (accountId !== undefined && accountId !== null && accountId !== '') {
    payload.accountId = accountId
  }
  return request.post('/workflow/drafts/batch-retry-publish', payload)
}

export const deleteWorkflowDraft = draftId => request.delete(`/workflow/drafts/${draftId}`)
