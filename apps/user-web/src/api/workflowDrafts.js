import request from '../utils/request.js'
import { pageParams } from '../utils/apiData.js'

/**
 * 工作流商品草稿箱 API
 *
 * 后端路由（Java AutomationProxyController 透传到 Python workflow.py）：
 *   GET    /workflow/drafts                         列表（分页 + 过滤）
 *   GET    /workflow/drafts/stats                   汇总统计
 *   GET    /workflow/drafts/{draftId}               草稿详情
 *   POST   /workflow/drafts/{draftId}/retry-publish 单条重试发布
 *   POST   /workflow/drafts/batch-retry-publish     批量重试发布
 *   DELETE /workflow/drafts/{draftId}               删除草稿
 *
 * 列表参数：{ page, pageSize, status, workflowId, keyword, startDate, endDate }
 * 状态取值：all / draft / publishing / published / failed
 */

export const listWorkflowDrafts = params => request.get('/workflow/drafts', { params: pageParams(params) })

export const getWorkflowDraftStats = () => request.get('/workflow/drafts/stats')

export const getWorkflowDraft = draftId => request.get(`/workflow/drafts/${draftId}`)

export const retryPublishDraft = draftId => request.post(`/workflow/drafts/${draftId}/retry-publish`, {})

export const batchRetryPublishDrafts = ids => request.post('/workflow/drafts/batch-retry-publish', {
  ids: Array.isArray(ids) ? ids : []
})

export const deleteWorkflowDraft = draftId => request.delete(`/workflow/drafts/${draftId}`)
