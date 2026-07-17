import request from '@/utils/http'
import { AppRouteRecord } from '@/types/router'
import {
  requireAffectedCount,
  requireListPayload,
  requirePagePayload,
  requireRecordPayload
} from '@/utils/api-payload'
import { downloadAuthenticatedCsv } from '@/utils/http/download'

// ==================== 菜单管理 API ====================

// 获取菜单列表（后端模式使用；前端模式下由 asyncRoutes 直接提供）
// 缓存 10 分钟，菜单数据低频变更
export function fetchGetMenuList() {
  return request.get<AppRouteRecord[]>({
    url: '/admin/menus',
    cacheTtl: 10 * 60 * 1000
  }).then(value => requireListPayload<AppRouteRecord>(value, '菜单列表'))
}

// 保存菜单（新增/更新）
export function fetchSaveMenu(data: Record<string, any>) {
  return request.post<AppRouteRecord>({
    url: '/admin/menus',
    data
  })
}

// 更新菜单
export function fetchUpdateMenu(id: number, data: Record<string, any>) {
  return request.put<AppRouteRecord>({
    url: `/admin/menus/${id}`,
    data
  })
}

// 删除菜单
export function fetchDeleteMenu(id: number) {
  return request.del({
    url: `/admin/menus/${id}`
  })
}

// ==================== 用户管理 API（使用 AdminModuleController） ====================

// 获取用户分页列表（从 sys_user 表）
export function fetchGetUserList(params: Api.SystemManage.UserSearchParams & { current?: number; size?: number }) {
  return request.get<Api.SystemManage.UserList>({
    url: '/admin/users',
    params: {
      current: params.current || 1,
      size: params.size || 20,
      keyword: params.username || '',
      status: params.status || ''
    }
  }).then(value => requirePagePayload<Api.SystemManage.UserListItem>(value, '用户列表') as Api.SystemManage.UserList)
}

// 获取租户列表（用于用户编辑弹窗的下拉选择器）
export function fetchGetTenantList(keyword?: string) {
  return request.get<{ id: number; name: string }[]>({
    url: '/admin/tenants',
    params: keyword ? { keyword } : {},
    cacheTtl: 60 * 1000
  }).then(value => requireListPayload<{ id: number; name: string }>(value, '租户列表'))
}

// 获取用户详情
export function fetchGetUserDetail(id: number) {
  return request.get<Api.SystemManage.UserListItem>({
    url: `/admin/modules/users/${id}`
  }).then(value => requireRecordPayload<Record<string, any>>(value, '用户详情') as Api.SystemManage.UserListItem)
}

// 创建用户
export function fetchCreateUser(data: Api.SystemManage.UserFormData) {
  return request.post<Api.SystemManage.UserListItem>({
    url: '/admin/modules/users',
    data
  })
}

// 更新用户
export function fetchUpdateUser(id: number, data: Partial<Api.SystemManage.UserFormData>) {
  return request.put<Api.SystemManage.UserListItem>({
    url: `/admin/modules/users/${id}`,
    data
  })
}

// ==================== 系统配置 API ====================

// 获取系统配置（缓存 5 分钟）
export function fetchGetSystemConfig() {
  return request.get<any>({
    url: '/system/config',
    cacheTtl: 5 * 60 * 1000
  }).then(value => requireRecordPayload<Record<string, any>>(value, '系统配置'))
}

// 保存系统配置
export function fetchSaveSystemConfig(data: Record<string, any>) {
  return request.post<any>({
    url: '/system/config',
    data
  })
}

// 上传LOGO
export function fetchUploadLogo(formData: FormData) {
  return request.post<any>({
    url: '/system/config/upload-logo',
    data: formData
  })
}

// 删除用户（软删除）
export function fetchDeleteUser(id: number) {
  return request.del({
    url: `/admin/modules/users/${id}`
  })
}

// 批量删除用户
export function fetchBatchDeleteUser(ids: number[]) {
  return request.post<{ count: number }>({
    url: '/admin/modules/users/batch-delete',
    data: { ids }
  }).then(value => requireAffectedCount(value, '批量删除用户'))
}

// 更新用户状态
export function fetchUpdateUserStatus(id: number, status: number) {
  return request.put({
    url: `/admin/modules/users/${id}/status`,
    data: { status: status === 1 ? '正常' : '禁用' }
  })
}

// 批量更新用户状态
export function fetchBatchUpdateUserStatus(ids: number[], status: number) {
  return request.post<{ count: number }>({
    url: '/admin/modules/users/batch-status',
    data: { ids, status: status === 1 ? '正常' : '禁用' }
  }).then(value => requireAffectedCount(value, '批量更新用户状态'))
}

// 重置用户密码
export function fetchResetUserPassword(id: number, newPassword: string) {
  return request.post({
    url: `/system/user/${id}/reset-password`,
    data: { newPassword }
  })
}

// 管理员代登：为指定前台用户签发登录 token（用于辅助调试）
// 返回 { token, username, userId, tenantId, nickname }
export function fetchUserLoginToken(id: number) {
  return request.post<{
    token: string
    username: string
    userId: number
    tenantId: number
    nickname?: string
  }>({
    url: `/system/user/${id}/login-token`
  })
}

// 导出用户列表为 CSV（按当前搜索条件导出，最多 5000 条；phone/email 已在后端脱敏）
// 使用原生 fetch 绕过封装的响应拦截器（拦截器会解包 res.data.data，对 blob 响应不适用）
export async function exportUsersCsv(keyword: string, status: string) {
  const baseUrl = import.meta.env.VITE_API_URL || '/admin-api'
  const query = new URLSearchParams()
  if (keyword) query.set('keyword', keyword)
  if (status) query.set('status', status)
  await downloadAuthenticatedCsv(
    `${baseUrl}/admin/modules/users/export?${query.toString()}`,
    `users-${new Date().toISOString().slice(0, 10)}.csv`
  )
}
