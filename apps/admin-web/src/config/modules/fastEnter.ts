/**
 * 管理后台快捷入口。
 *
 * 只公布已注册、对日常运营角色可用的站内路由，避免展示模板演示页、
 * 外部支持站或尚未接入的功能。
 */
import type { FastEnterConfig } from '@/types/config'

const fastEnterConfig: FastEnterConfig = {
  minWidth: 1200,
  applications: [
    {
      name: '运营概览',
      description: '查看系统状态与核心指标',
      icon: 'ri:dashboard-line',
      iconColor: '#377dff',
      enabled: true,
      order: 1,
      routeName: 'AdminDashboard'
    },
    {
      name: '订单监管',
      description: '查询与跟踪业务订单',
      icon: 'ri:shopping-bag-3-line',
      iconColor: '#ff3b30',
      enabled: true,
      order: 2,
      routeName: 'AdminOrders'
    },
    {
      name: '消息监管',
      description: '排查消息收发与处理状态',
      icon: 'ri:message-3-line',
      iconColor: '#13b8a6',
      enabled: true,
      order: 3,
      routeName: 'AdminMessages'
    },
    {
      name: 'AI 调用日志',
      description: '核查模型调用、费用与错误',
      icon: 'ri:line-chart-line',
      iconColor: '#7a7fff',
      enabled: true,
      order: 4,
      routeName: 'AdminAiUsage'
    },
    {
      name: '通知记录',
      description: '查看通知发送结果与失败原因',
      icon: 'ri:notification-3-line',
      iconColor: '#ffb100',
      enabled: true,
      order: 5,
      routeName: 'AdminNotifyLogs'
    },
    {
      name: '审计日志',
      description: '追溯管理员操作与安全事件',
      icon: 'ri:shield-check-line',
      iconColor: '#ff6b6b',
      enabled: true,
      order: 6,
      routeName: 'AdminAuditLogs'
    }
  ],
  quickLinks: [
    {
      name: '个人中心',
      enabled: true,
      order: 1,
      routeName: 'UserCenter'
    },
    {
      name: '商品监管',
      enabled: true,
      order: 2,
      routeName: 'AdminGoods'
    },
    {
      name: '自动回复监管',
      enabled: true,
      order: 3,
      routeName: 'AdminAutoReply'
    },
    {
      name: '智能运营监控',
      enabled: true,
      order: 4,
      routeName: 'AdminSmartMonitor'
    }
  ]
}

export default Object.freeze(fastEnterConfig)
