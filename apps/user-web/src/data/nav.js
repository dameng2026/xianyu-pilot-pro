export const navGroups = [
  { title: '概览', items: [
    { key: 'dashboard', label: '导航面板', icon: 'dashboard' },
    { key: 'data', label: '数据面板', icon: 'data' }
  ]},
  { title: '账号与商品', items: [
    { key: 'accounts', label: '闲鱼账号', icon: 'account' },
    { key: 'connections', label: '连接管理', icon: 'link' },
    { key: 'products', label: '商品管理', icon: 'product' },
    { key: 'orders', label: '订单管理', icon: 'record' },
    { key: 'product-publish', label: '发布商品', icon: 'publish', child: true },
    { key: 'opportunities', label: '商机发掘', icon: 'opportunity' }
  ]},
  { title: '消息', items: [
    { key: 'messages', label: '在线消息', icon: 'chat' }
  ]},
  { title: '自动化', items: [
    { key: 'workflow', label: '工作流', icon: 'workflow' },
    { key: 'workflow-tasks', label: '工作流任务', icon: 'task' },
    { key: 'auto-delivery', label: '自动发货', icon: 'truck' },
    { key: 'delivery-source-library', label: '货源库', icon: 'document', child: true },
    { key: 'delivery-statement', label: '发货声明', icon: 'document', child: true },
    { key: 'delivery-mall', label: '货源商城', icon: 'product', child: true },
    { key: 'card-warehouse', label: '卡密仓库', icon: 'key' },
    { key: 'delivery-records', label: '发货记录', icon: 'record' },
    { key: 'scheduled-tasks', label: '定时任务', icon: 'clock' },
    { key: 'auto-reply', label: '自动回复', icon: 'reply' }
  ]},
  { title: '系统', items: [
    { key: 'logs', label: '操作日志', icon: 'log' },
    { key: 'slider-solve-records', label: '滑块求解', icon: 'log' },
    { key: 'feedback', label: '反馈建议', icon: 'reply' },
    { key: 'settings-notify', label: '通知设置', icon: 'bell' },
    { key: 'settings-ai-cs', label: '系统设置', icon: 'settings' }
  ]}
]

// 数据同步板块仅在本地开发环境显示（VITE_SHOW_DATA_SYNC=true）
// 商业版（线上生产）不设置此变量，数据同步 tab 不会出现在设置页
const showDataSync = import.meta.env.VITE_SHOW_DATA_SYNC === 'true'

export const settingsTabs = [
  { key: 'settings-ai-cs', label: 'AI客服配置', icon: 'message' },
  { key: 'settings-product', label: '商品操作', icon: 'product' },
  ...(showDataSync ? [{ key: 'settings-sync', label: '数据同步', icon: 'data' }] : []),
  { key: 'settings-about', label: '关于', icon: 'help' }
]

export const pageTitles = {
  dashboard: ['导航面板', '系统导航中心，帮助你快速进入常用功能'],
  data: ['数据面板', '实时查看运营数据、发货情况与业务趋势'],
  accounts: ['闲鱼账号', '管理账号状态、登录情况与连接健康度'],
  connections: ['连接管理', '统一查看账号连接、WebSocket 与 Cookie 状态'],
  products: ['商品管理', '管理商品信息、同步状态、自动发货与自动回复配置'],
  orders: ['订单管理', '集中查看订单状态、买家信息、发货情况与异常提醒'],
  'product-publish': ['发布商品', '创建并发布闲鱼商品'],
  opportunities: ['商机发掘', '发现高潜力商品与经营机会'],
  messages: ['在线消息', '集中处理买家咨询与消息会话'],
  'message-center': ['在线消息', '集中处理买家咨询与消息会话'],
  workflow: ['工作流', '设计并运行自动化业务流程'],
  'workflow-tasks': ['工作流任务', '查看工作流任务执行状态与结果'],
  'card-warehouse': ['卡密仓库', '管理卡密库存、分组与使用记录'],
  'auto-delivery': ['自动发货', '按商品配置自动发货规则、时机与发送方式'],
  'delivery-source-library': ['货源库', '统一管理文本货源，支持 AI 推荐适配商品并批量配置'],
  'delivery-statement': ['发货声明', '管理发货声明文案与生效范围'],
  'delivery-mall': ['货源商城', '海量优质虚拟商品资源，自动发货，即买即用'],
  'delivery-templates': ['模板管理', '管理可复用的发货模板与变量'],
  'delivery-records': ['发货记录', '追踪自动发货、异常与补发情况'],
  'scheduled-tasks': ['定时任务', '查看和维护定时任务执行计划'],
  'auto-reply': ['', ''],
  logs: ['操作日志', '查看系统操作与关键行为记录'],
  'slider-solve-records': ['滑块求解', '查看滑块自动求解的触发场景、处理结果与验证状态'],
  feedback: ['反馈建议', '提交产品建议、Bug 反馈与功能诉求'],
  'settings-ai-cs': ['系统设置 / AI客服配置', '管理 AI 客服相关配置'],
  'settings-product': ['系统设置 / 商品操作', '管理商品相关系统级配置'],
  'settings-sync': ['系统设置 / 数据同步', '将本地配置一键同步到线上服务器'],
  'settings-notify': ['', ''],
  'settings-about': ['系统设置 / 关于', '查看版本信息与服务支持'],
  vip: ['VIP会员中心', '查看会员能力与套餐信息'],
  profile: ['个人中心', '管理账号资料、安全设置与余额信息'],
  'user-manual': ['使用手册', '深入浅出地讲解闲鱼助手全部功能与最佳实践，帮助新用户快速上手']
}
