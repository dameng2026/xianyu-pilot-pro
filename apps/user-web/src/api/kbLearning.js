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
