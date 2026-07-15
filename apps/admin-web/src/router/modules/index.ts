import { AppRouteRecord } from '@/types/router'
import { adminRoutes } from './admin'

/**
 * 后台管理端路由。
 * 基于 Art Design Pro 的布局、权限、标签页与菜单系统，只替换业务菜单。
 */
export const routeModules: AppRouteRecord[] = adminRoutes
