import request from '../utils/request'

// 平台学习 KB（只读）
export function listLearnedKb(params) {
  return request({ url: '/ai-cs/kb/learned', method: 'get', params })
}

export function getLearnedKbDetail(id) {
  return request({ url: `/ai-cs/kb/learned/${id}`, method: 'get' })
}

// V1.47: 获取某条 Q&A 关联的原始对话消息
export function getLearnedKbConversation(id) {
  return request({ url: `/ai-cs/kb/learned/${id}/conversation`, method: 'get' })
}

// V1.47: 分类列表（附带用户启用状态）
export function listKbCategories() {
  return request({ url: '/ai-cs/kb/categories', method: 'get' })
}

// V1.47: 按分类 code 列出该分类下所有 Q&A
export function listLearnedKbByCategory(code, params) {
  return request({ url: `/ai-cs/kb/categories/${code}/learned`, method: 'get', params })
}

// V1.47: 一键启用某个分类下的所有 Q&A
export function bindCategory(code) {
  return request({ url: `/ai-cs/kb/categories/${code}/bind`, method: 'post' })
}

// V1.47: 一键取消启用某个分类下的所有 Q&A
export function unbindCategory(code) {
  return request({ url: `/ai-cs/kb/categories/${code}/bind`, method: 'delete' })
}

// V1.49: 一级大类（三级分类）
// 按一级分类 code 列出其下所有二级分类的所有 Q&A
export function listLearnedKbByParentCategory(code, params) {
  return request({ url: `/ai-cs/kb/parent-categories/${code}/learned`, method: 'get', params })
}

// V1.49: 一键启用某个一级分类下所有二级分类的所有 Q&A（按大类启用）
export function bindParentCategory(code) {
  return request({ url: `/ai-cs/kb/parent-categories/${code}/bind`, method: 'post' })
}

// V1.49: 一键取消启用某个一级分类下所有二级分类的所有 Q&A
export function unbindParentCategory(code) {
  return request({ url: `/ai-cs/kb/parent-categories/${code}/bind`, method: 'delete' })
}

// 用户私有 KB
export function listUserKb() {
  return request({ url: '/ai-cs/kb/user-kb', method: 'get' })
}

export function createUserKb(data) {
  return request({ url: '/ai-cs/kb/user-kb', method: 'post', data })
}

export function updateUserKb(id, data) {
  return request({ url: `/ai-cs/kb/user-kb/${id}`, method: 'put', data })
}

export function deleteUserKb(id) {
  return request({ url: `/ai-cs/kb/user-kb/${id}`, method: 'delete' })
}

// ===== 新建知识库弹窗 - 三种模式扩展 =====

/**
 * 文件上传模式：上传文件 → AI 提取 Q&A 数组（不写库）。
 * 支持 .md .txt .csv .xlsx .pptx .docx .pdf（最大 10MB）。
 * @param {File} file 文件对象
 * @param {string} [fileType='auto'] 文件类型：auto(自动检测) / chat_records / product_docs / company_docs / general
 * @returns Promise<{ entries: Array<{title,content,category,tags,source_summary}>, totalCount, fileName, fileType, contentCategory, rawLength }>
 */
export function extractQaFromFile(file, fileType = 'auto') {
  const formData = new FormData()
  formData.append('file', file)
  // 透传文件类型，让后端选择专用提取 prompt
  if (fileType) {
    formData.append('fileType', fileType)
  }
  return request({
    url: '/ai-cs/kb/user-kb/extract-from-file',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  })
}

/**
 * 会话聊天提取模式：根据 sids 拉取消息 → AI 提取 Q&A。
 * @param {Object} payload { accountId, sids:[string], conversations:[{sid,conversationId,peerUserName,goodsTitle,peerUserId}] }
 * @returns Promise<{ entries, totalCount, selectedCount, processedCount, totalMessages }>
 */
export function extractQaFromConversations(payload) {
  return request({
    url: '/ai-cs/kb/user-kb/extract-from-conversations',
    method: 'post',
    data: payload,
    timeout: 180000
  })
}

/**
 * AI 智能推荐高价值会话：传入会话列表，AI 返回推荐会话 + 推荐理由 + 价值评分。
 * @param {Object} payload { accountId, conversations:[{sid,conversationId,peerUserName,goodsTitle,lastMessage,messageCount,peerUserId}] }
 * @returns Promise<{ recommendations: Array<{sid,conversationId,reason,estimatedValue,peerUserName,goodsTitle,messageCount,peerUserId}>, totalScanned, recommendedCount }>
 */
export function recommendConversations(payload) {
  return request({
    url: '/ai-cs/kb/user-kb/recommend-conversations',
    method: 'post',
    data: payload,
    timeout: 180000
  })
}

/**
 * 批量创建用户私有 KB（文件上传/会话提取模式确认保存）。
 * @param {Object} payload { entries:[{title,content,category,tags}], defaultCategory, defaultTags }
 * @returns Promise<{ createdIds:number[], count:number, skipped:number }>
 */
export function batchCreateUserKb(payload) {
  return request({
    url: '/ai-cs/kb/user-kb/batch',
    method: 'post',
    data: payload
  })
}

// 绑定关系（单条 Q&A 级别，向后兼容）
export function listBindings() {
  return request({ url: '/ai-cs/kb/bindings', method: 'get' })
}

export function bindKbs(items) {
  return request({ url: '/ai-cs/kb/bindings', method: 'post', data: { items } })
}

export function unbindKb(kbType, kbId) {
  return request({
    url: '/ai-cs/kb/bindings',
    method: 'delete',
    params: { kbType, kbId }
  })
}

// 反馈（复用既有 feedback API）
export { submitFeedback } from './feedback'
