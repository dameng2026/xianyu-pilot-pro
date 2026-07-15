import { AppRouteRecord } from '@/types/router'

const moduleComponent = '/admin/module'
const SUPER_ONLY = ['R_SUPER']
const ADMIN_OPERATORS = ['R_SUPER', 'R_ADMIN']

export const adminRoutes: AppRouteRecord[] = [
  {
    name: 'AdminDashboardRoot',
    path: '/admin/dashboard',
    component: '/index/index',
    meta: { title: '后台首页', icon: 'ri:dashboard-3-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'overview', name: 'AdminDashboard', component: moduleComponent, meta: { title: '运营概览', icon: 'ri:dashboard-line', fixedTab: true, moduleKey: 'dashboard', roles: ADMIN_OPERATORS } as any }
    ]
  },
  {
    name: 'AdminUserPermission',
    path: '/admin/user-permission',
    component: '/index/index',
    meta: { title: '用户与权限', icon: 'ri:user-settings-line', roles: SUPER_ONLY },
    children: [
      { path: 'users', name: 'AdminUsers', component: '/system/user', meta: { title: '用户管理', icon: 'ri:user-line', roles: SUPER_ONLY } as any }
    ]
  },
  {
    name: 'AdminBilling',
    path: '/admin/billing',
    component: '/index/index',
    meta: { title: '套餐与授权', icon: 'ri:vip-crown-line', roles: SUPER_ONLY },
    children: [
      { path: 'plans', name: 'AdminPlans', component: moduleComponent, meta: { title: '套餐管理', icon: 'ri:price-tag-3-line', moduleKey: 'plans', roles: SUPER_ONLY } as any },
      { path: 'payment-config', name: 'AdminPaymentConfig', component: '/admin/payment-config/index', meta: { title: '支付配置', icon: 'ri:bank-card-line', roles: SUPER_ONLY } as any },
      { path: 'licenses', name: 'AdminLicenses', component: moduleComponent, meta: { title: '授权码管理', icon: 'ri:key-2-line', moduleKey: 'licenses', roles: SUPER_ONLY } as any }
    ]
  },
  {
    name: 'AdminXianyuBusiness',
    path: '/admin/xianyu-business',
    component: '/index/index',
    meta: { title: '闲鱼业务监管', icon: 'ri:store-2-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'accounts', name: 'AdminXianyuAccounts', component: moduleComponent, meta: { title: '闲鱼账号', icon: 'ri:account-circle-line', moduleKey: 'xianyu-accounts', roles: SUPER_ONLY } as any },
      { path: 'goods', name: 'AdminGoods', component: moduleComponent, meta: { title: '商品监管', icon: 'ri:archive-line', moduleKey: 'goods', roles: ADMIN_OPERATORS } as any },
      { path: 'orders', name: 'AdminOrders', component: moduleComponent, meta: { title: '订单监管', icon: 'ri:shopping-bag-3-line', moduleKey: 'orders', roles: ADMIN_OPERATORS } as any },
      { path: 'messages', name: 'AdminMessages', component: moduleComponent, meta: { title: '消息监管', icon: 'ri:message-3-line', moduleKey: 'messages', roles: ADMIN_OPERATORS } as any },
      { path: 'delivery', name: 'AdminDelivery', component: moduleComponent, meta: { title: '自动发货监管', icon: 'ri:truck-line', moduleKey: 'delivery', roles: ADMIN_OPERATORS } as any },
      { path: 'auto-reply', name: 'AdminAutoReply', component: moduleComponent, meta: { title: '自动回复监管', icon: 'ri:robot-2-line', moduleKey: 'auto-reply', roles: ADMIN_OPERATORS } as any },
      { path: 'kami', name: 'AdminKami', component: moduleComponent, meta: { title: '卡密监管', icon: 'ri:coupon-3-line', moduleKey: 'kami', roles: ADMIN_OPERATORS } as any }
    ]
  },
  {
    name: 'AdminAI',
    path: '/admin/ai',
    component: '/index/index',
    meta: { title: 'AI 管理', icon: 'ri:brain-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'model-config', name: 'AdminModelConfig', component: '/admin/model-config/index', meta: { title: '模型配置', icon: 'ri:cloud-line', roles: SUPER_ONLY } as any },
      { path: 'pricing', name: 'AdminAiPricing', component: '/admin/ai-pricing/index', meta: { title: '费用设置', icon: 'ri:money-cny-circle-line', roles: SUPER_ONLY } as any },
      { path: 'monitor', name: 'AdminSmartMonitor', component: '/admin/monitor/index', meta: { title: '智能运营监控', icon: 'ri:pulse-line', roles: ADMIN_OPERATORS } as any },
      { path: 'usage', name: 'AdminAiUsage', component: '/admin/ai-usage/index', meta: { title: 'AI 调用日志', icon: 'ri:line-chart-line', roles: ADMIN_OPERATORS } as any },
      { path: 'token', name: 'AdminAiToken', component: '/admin/ai-token/index', meta: { title: 'Token 用量', icon: 'ri:token-swap-line', roles: ADMIN_OPERATORS } as any },
      { path: 'image-prompt-categories', name: 'AdminImagePromptCategories', component: moduleComponent, meta: { title: '生图类目提示词', icon: 'ri:image-2-line', moduleKey: 'model-config-image-prompts', roles: SUPER_ONLY } as any },
      { path: 'rag', name: 'AdminRag', component: moduleComponent, meta: { title: 'RAG 知识库', icon: 'ri:book-open-line', moduleKey: 'rag', roles: ADMIN_OPERATORS } as any },
      { path: 'sensitive-words', name: 'AdminSensitiveWords', component: moduleComponent, meta: { title: '敏感词策略', icon: 'ri:forbid-line', moduleKey: 'sensitive-words', roles: ADMIN_OPERATORS } as any }
    ]
  },
  {
    name: 'AdminDataStats',
    path: '/admin/data-stats',
    component: '/index/index',
    meta: { title: '数据统计', icon: 'ri:bar-chart-2-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'hot-goods', name: 'AdminHotGoods', component: moduleComponent, meta: { title: '热销商品统计', icon: 'ri:fire-line', moduleKey: 'hot-goods', roles: ADMIN_OPERATORS } as any }
    ]
  },
  {
    name: 'AdminRiskNotify',
    path: '/admin/risk-notify',
    component: '/index/index',
    meta: { title: '通知与风控', icon: 'ri:alarm-warning-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'channels', name: 'AdminNotifyChannels', component: moduleComponent, meta: { title: '通知渠道', icon: 'ri:notification-3-line', moduleKey: 'notify-channels', roles: SUPER_ONLY } as any },
      { path: 'sms-config', name: 'AdminSmsConfig', component: '/system/sms-config', meta: { title: '短信配置草稿', icon: 'ri:message-3-line', roles: SUPER_ONLY } as any },
      { path: 'email-config', name: 'AdminEmailConfig', component: '/system/email-config', meta: { title: '邮件配置草稿', icon: 'ri:mail-line', roles: SUPER_ONLY } as any },
      { path: 'notify-logs', name: 'AdminNotifyLogs', component: '/admin/ops/notification-logs/index', meta: { title: '通知发送记录', icon: 'ri:file-list-line', roles: ADMIN_OPERATORS } as any },
      { path: 'risk-events', name: 'AdminRiskEvents', component: moduleComponent, meta: { title: '风控事件', icon: 'ri:alert-line', moduleKey: 'risk-events', roles: ADMIN_OPERATORS } as any },
      { path: 'alerts', name: 'AdminAlerts', component: moduleComponent, meta: { title: '异常告警', icon: 'ri:error-warning-line', moduleKey: 'alerts', roles: ADMIN_OPERATORS } as any }
    ]
  },
  {
    name: 'AdminOps',
    path: '/admin/ops',
    component: '/index/index',
    meta: { title: '系统运维', icon: 'ri:settings-4-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'settings', name: 'AdminSystemSettings', component: '/admin/ops/settings/index', meta: { title: '系统配置', icon: 'ri:settings-line', roles: SUPER_ONLY } as any },
      { path: 'audit-logs', name: 'AdminAuditLogs', component: '/admin/ops/audit-logs/index', meta: { title: '操作审计日志', icon: 'ri:shield-check-line', roles: ADMIN_OPERATORS } as any },
      { path: 'client-errors', name: 'AdminClientErrors', component: '/admin/ops/client-errors/index', meta: { title: '前端错误日志', icon: 'ri:bug-line', roles: SUPER_ONLY } as any },
      { path: 'runtime', name: 'AdminRuntime', component: moduleComponent, meta: { title: '运行日志', icon: 'ri:terminal-box-line', moduleKey: 'runtime', roles: ADMIN_OPERATORS } as any },
      { path: 'backups', name: 'AdminBackups', component: moduleComponent, meta: { title: '数据备份', icon: 'ri:database-2-line', moduleKey: 'backups', roles: SUPER_ONLY } as any },
      { path: 'files', name: 'AdminFiles', component: moduleComponent, meta: { title: '文件管理', icon: 'ri:folder-line', moduleKey: 'files', roles: SUPER_ONLY } as any },
      { path: 'versions', name: 'AdminVersions', component: moduleComponent, meta: { title: '版本管理', icon: 'ri:git-commit-line', moduleKey: 'versions', roles: SUPER_ONLY } as any }
    ]
  },
  {
    name: 'AdminContent',
    path: '/admin/content',
    component: '/index/index',
    meta: { title: '内容管理', icon: 'ri:file-list-3-line', roles: ADMIN_OPERATORS },
    children: [
      { path: 'carousel', name: 'AdminCarousel', component: '/admin/carousel/index', meta: { title: '轮播图配置', icon: 'ri:image-line', roles: ADMIN_OPERATORS } as any },
      { path: 'announcement', name: 'AdminAnnouncement', component: '/admin/announcement/index', meta: { title: '公告配置', icon: 'ri:notification-line', roles: ADMIN_OPERATORS } as any },
      { path: 'feedback', name: 'AdminFeedback', component: '/admin/feedback/index', meta: { title: '用户反馈', icon: 'ri:feedback-line', roles: ADMIN_OPERATORS } as any },
      { path: 'open-source-home', name: 'AdminOpenSourceHome', component: '/admin/open-source/home/index', meta: { title: '开源版首页轮播', icon: 'ri:gallery-line', roles: SUPER_ONLY } as any },
      { path: 'open-source-announcement', name: 'AdminOpenSourceAnnouncement', component: '/admin/open-source/announcement/index', meta: { title: '开源版首页公告', icon: 'ri:notification-badge-line', roles: SUPER_ONLY } as any },
      { path: 'open-source-about', name: 'AdminOpenSourceAbout', component: '/admin/open-source/about/index', meta: { title: '开源版关于页', icon: 'ri:information-line', roles: SUPER_ONLY } as any },
      { path: 'open-source-text-ads', name: 'AdminOpenSourceTextAds', component: '/admin/open-source/ads-text/index', meta: { title: '开源版文字广告', icon: 'ri:advertisement-line', roles: SUPER_ONLY } as any },
      { path: 'open-source-ad-plans', name: 'AdminOpenSourceAdPlans', component: '/admin/open-source/ads-plans/index', meta: { title: '开源版广告套餐', icon: 'ri:price-tag-3-line', roles: SUPER_ONLY } as any },
      { path: 'open-source-ad-applications', name: 'AdminOpenSourceAdApplications', component: '/admin/open-source/ads-applications/index', meta: { title: '开源版广告申请', icon: 'ri:file-list-2-line', roles: SUPER_ONLY } as any }
    ]
  },
  {
    name: 'System',
    path: '/system',
    component: '/index/index',
    meta: { title: '个人中心', icon: 'ri:user-3-line', roles: ['R_SUPER', 'R_ADMIN', 'R_USER'], isHide: true },
    children: [
      {
        path: 'user-center',
        name: 'UserCenter',
        component: '/system/user-center',
        meta: {
          title: '个人中心',
          icon: 'ri:user-line',
          isHide: true,
          keepAlive: true,
          isHideTab: false
        }
      }
    ]
  }
]
