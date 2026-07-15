import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import { adminRoutes } from '../src/router/modules/admin'
import { systemRoutes } from '../src/router/modules/system'
import { getAdminButtonCapabilities } from '../src/utils/admin-permissions'

type RouteNode = (typeof adminRoutes)[number]

function flattenRoutes(routes: RouteNode[]): RouteNode[] {
  return routes.flatMap(route => [route, ...flattenRoutes((route.children ?? []) as RouteNode[])])
}

const routesByName = new Map(flattenRoutes(adminRoutes).map(route => [String(route.name), route]))

for (const routeName of [
  'AdminUsers',
  'AdminPlans',
  'AdminPaymentConfig',
  'AdminLicenses',
  'AdminXianyuAccounts',
  'AdminModelConfig',
  'AdminAiPricing',
  'AdminImagePromptCategories',
  'AdminNotifyChannels',
  'AdminSmsConfig',
  'AdminEmailConfig',
  'AdminSystemSettings',
  'AdminClientErrors',
  'AdminBackups',
  'AdminFiles',
  'AdminVersions',
  'AdminOpenSourceHome',
  'AdminOpenSourceAnnouncement',
  'AdminOpenSourceAbout',
  'AdminOpenSourceTextAds',
  'AdminOpenSourceAdPlans',
  'AdminOpenSourceAdApplications'
]) {
  assert.deepEqual(
    routesByName.get(routeName)?.meta.roles,
    ['R_SUPER'],
    `${routeName} 包含全局敏感数据或配置，必须仅超级管理员可见`
  )
}

assert.deepEqual(getAdminButtonCapabilities(['view', 'export']), {
  canView: true,
  canExport: true,
  canAdd: false,
  canEdit: false,
  canDelete: false
})
assert.deepEqual(getAdminButtonCapabilities(['view', 'export', 'add', 'edit', 'delete']), {
  canView: true,
  canExport: true,
  canAdd: true,
  canEdit: true,
  canDelete: true
})
assert.deepEqual(
  getAdminButtonCapabilities(['view', 'edit', 'EDIT', '', 'delete', 'unknown']),
  {
    canView: true,
    canExport: false,
    canAdd: false,
    canEdit: true,
    canDelete: true
  },
  '未知、空值和大小写错误的权限码不得扩大权限'
)

const systemRoutesByName = new Map(
  flattenRoutes([systemRoutes as RouteNode]).map(route => [String(route.name), route])
)
for (const routeName of ['User', 'SmsConfig', 'EmailConfig']) {
  assert.deepEqual(
    systemRoutesByName.get(routeName)?.meta.roles,
    ['R_SUPER'],
    `${routeName} 访问 /admin-api/system 敏感端点，必须仅 R_SUPER 可见`
  )
}

for (const routeName of [
  'AdminDashboard',
  'AdminGoods',
  'AdminOrders',
  'AdminMessages',
  'AdminSmartMonitor',
  'AdminAiUsage',
  'AdminNotifyLogs',
  'AdminAuditLogs'
]) {
  const roles = routesByName.get(routeName)?.meta.roles
  assert(roles?.includes('R_ADMIN'), `${routeName} 是运营可读页，R_ADMIN 应保留访问权`)
}

const genericModulePage = fs.readFileSync(
  path.resolve('src/views/admin/module/index.vue'),
  'utf8'
)

for (const capability of ['canAdd', 'canEdit', 'canDelete', 'canExport']) {
  assert(
    genericModulePage.includes(capability),
    `通用模块必须基于 userInfo.buttons 暴露 ${capability} 权限`
  )
}

assert(
  genericModulePage.includes('userStore.info?.buttons'),
  '通用模块按钮权限必须直接来自当前用户 userInfo.buttons'
)

console.log('admin-access-boundary-contract: ok')
