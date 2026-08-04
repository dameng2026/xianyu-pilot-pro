/**
 * API 接口类型定义模块
 *
 * 提供所有后端接口的类型定义
 *
 * ## 主要功能
 *
 * - 通用类型（分页参数、响应结构等）
 * - 认证类型（登录、用户信息等）
 * - 系统管理类型（用户、角色等）
 * - 全局命名空间声明
 *
 * ## 使用场景
 *
 * - API 请求参数类型约束
 * - API 响应数据类型定义
 * - 接口文档类型同步
 *
 * ## 注意事项
 *
 * - 在 .vue 文件使用需要在 eslint.config.mjs 中配置 globals: { Api: 'readonly' }
 * - 使用全局命名空间，无需导入即可使用
 *
 * ## 使用方式
 *
 * ```typescript
 * const params: Api.Auth.LoginParams = { userName: 'admin', password: '123456' }
 * const response: Api.Auth.UserInfo = await fetchUserInfo()
 * ```
 *
 * @module types/api/api
 * @author Art Design Pro Team
 */

declare namespace Api {
  /** 通用类型 */
  namespace Common {
    /** 分页参数 */
    interface PaginationParams {
      /** 当前页码 */
      current: number
      /** 每页条数 */
      size: number
      /** 总条数 */
      total: number
    }

    /** 通用搜索参数 */
    type CommonSearchParams = Pick<PaginationParams, 'current' | 'size'>

    /** 分页响应基础结构 */
    interface PaginatedResponse<T = any> {
      records: T[]
      current: number
      size: number
      total: number
    }

    /** 启用状态 */
    type EnableStatus = '1' | '2'
  }

  /** 认证类型 */
  namespace Auth {
    /** 登录参数 */
    interface LoginParams {
      userName: string
      password: string
    }

    /** 登录响应 */
    interface LoginResponse {
      token: string
      refreshToken?: string
    }

    /** 用户信息 */
    interface UserInfo {
      buttons: string[]
      roles: string[]
      userId: number
      userName: string
      email: string
      avatar?: string
    }
  }

  /** 系统管理类型 */
  namespace SystemManage {
    /** 用户列表 */
    type UserList = Api.Common.PaginatedResponse<UserListItem>

    /** sys_user 表对应的用户列表项 */
    interface UserListItem {
      id: number
      username: string
      /** 示例表格兼容字段：旧版 demo 使用 userName。 */
      userName?: string
      nickname: string
      tenantName: string
      tenantId?: number
      planName?: string
      userLevel?: string          // "normal" | "vip-single" | "vip" | "svp"
      userLevelName?: string      // "普通用户" | "VIP（单店版）" | "VIP" | "SVP"
      tokenBalance?: number
      xianyuAccountCount?: number | string
      status: string           // "正常" | "禁用"
      lastLoginTime: string
      createdTime: string
      phone?: string
      email?: string
      /** 示例表格兼容字段：旧版 demo 使用 userGender。 */
      userGender?: string
      avatar?: string
      userType?: number
      lastLoginIp?: string
      updatedTime?: string
      roles?: UserRoleItem[]
      roleIds?: number[]
    }

    /** 用户角色项 */
    interface UserRoleItem {
      id: number
      roleName: string
      roleCode: string
      description: string
    }

    /** 用户搜索参数 */
    type UserSearchParams = Partial<
      {
        username: string
        /** 示例表格兼容字段：旧版 demo 使用 userName。 */
        userName: string
        nickname: string
        /** 示例表格兼容字段：旧版 demo 使用 nickName。 */
        nickName: string
        phone: string
        /** 示例表格兼容字段：旧版 demo 使用 userPhone。 */
        userPhone: string
        email: string
        /** 示例表格兼容字段：旧版 demo 使用 userEmail。 */
        userEmail: string
        /** 示例表格兼容字段：旧版 demo 使用 userGender。 */
        userGender: string
        userType: string
        status: string
        tenantId: string
      } & Api.Common.CommonSearchParams
    >

    /** 用户表单数据 */
    interface UserFormData {
      id?: number
      tenantId: number
      username: string
      password?: string
      nickname: string
      phone: string
      email: string
      avatar: string
      userType: number
      status: number
      roleIds: number[]
    }

    /** 角色列表 */
    type RoleList = Api.Common.PaginatedResponse<RoleListItem>

    /** 角色列表项 */
    interface RoleListItem {
      roleId: number
      roleName: string
      roleCode: string
      description: string
      enabled: boolean
      createTime: string
    }

    /** 角色搜索参数 */
    type RoleSearchParams = Partial<
      Pick<RoleListItem, 'roleId' | 'roleName' | 'roleCode' | 'description' | 'enabled'> &
        Api.Common.CommonSearchParams & {
          startTime: string | null
          endTime: string | null
        }
    >
  }
}
