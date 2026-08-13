// 一级分类配置（含图标）
export const navCategories = [
  {
    key: 'overview',
    title: '概览',
    icon: 'overview',
    items: [
      { key: 'dashboard', label: '导航面板', icon: 'dashboard' },
      { key: 'data', label: '数据面板', icon: 'data' }
    ]
  },
  {
    key: 'account',
    title: '账号',
    icon: 'account',
    items: [
      { key: 'accounts', label: '闲鱼账号', icon: 'users' },
      { key: 'orders', label: '订单管理', icon: 'record' },
      { key: 'refunds', label: '退款管理', icon: 'refund' },
      { key: 'refund-cancel', label: '退款关单', icon: 'refund' },
      { key: 'rates', label: '评价管理', icon: 'circle' },
      { key: 'fish-shop-data', label: '鱼小铺数据分析', icon: 'data' },
      { key: 'fish-shop-browse', label: '流量分布', icon: 'data' }
    ]
  },
  {
    key: 'product',
    title: '商品',
    icon: 'product',
    items: [
      { key: 'products', label: '商品管理', icon: 'product' },
      { key: 'product-publish', label: '商品发布', icon: 'publish' },
      { key: 'opportunities', label: '商机发掘', icon: 'opportunity' },
      { key: 'goods-data', label: '商品数据分析', icon: 'data' }
    ]
  },
  {
    key: 'message',
    title: '消息',
    icon: 'message',
    items: [
      { key: 'messages', label: '在线消息', icon: 'chat' },
      { key: 'auto-reply', label: '自动回复', icon: 'reply' },
      { key: 'auto-reply-rules', label: '回复规则', icon: 'rule' },
      { key: 'message-filters', label: '消息过滤', icon: 'filter' },
      { key: 'default-reply', label: '默认回复', icon: 'reply' },
      { key: 'settings-ai-cs', label: 'AI客服配置', icon: 'ai' },
      { key: 'settings-kb', label: '客服知识库', icon: 'library' }
    ]
  },
  {
    key: 'delivery',
    title: '自动发货',
    icon: 'delivery',
    items: [
      { key: 'auto-delivery', label: '自动发货', icon: 'truck' },
      { key: 'delivery-block-rules', label: '发货拦截规则', icon: 'shield' },
      { key: 'delivery-source-library', label: '货源库', icon: 'library' },
      { key: 'card-warehouse', label: '卡密仓库', icon: 'key' },
      { key: 'blacklist', label: '买家黑名单', icon: 'block' },
      { key: 'delivery-statement', label: '发货声明', icon: 'document' },
      { key: 'delivery-records', label: '发货记录', icon: 'record' }
    ]
  },
  {
    key: 'distribution',
    title: '分销管理',
    icon: 'distribution',
    items: [
      { key: 'delivery-mall', label: '货源商城', icon: 'crown' },
      { key: 'supply-center', label: '供货中心', icon: 'distribution' },
      { key: 'platform-connect', label: '平台对接', icon: 'link', maintenance: true }
    ]
  },
  {
    key: 'workflow',
    title: '工作流',
    icon: 'workflow',
    items: [
      { key: 'workflow', label: '工作流', icon: 'workflow' },
      { key: 'workflow-tasks', label: '工作流任务', icon: 'task' },
      { key: 'workflow-drafts', label: '商品草稿箱', icon: 'draft' },
      { key: 'workflow-image-records', label: '图片生成记录', icon: 'image' }
    ]
  },
  {
    key: 'marketing',
    title: '营销增长',
    icon: 'marketing',
    items: [
      { key: 'growth-partner', label: '增长合伙人', icon: 'users' },
      { key: 'invite-poster', label: '邀请海报', icon: 'image', maintenance: true }
    ]
  },
  {
    key: 'system',
    title: '系统',
    icon: 'system',
    items: [
      { key: 'scheduled-tasks', label: '定时任务', icon: 'clock' },
      { key: 'settings-notify', label: '通知设置', icon: 'bell' },
      { key: 'slider-solve-records', label: '滑块求解', icon: 'scan' },
      { key: 'api-slider-solve', label: 'API滑块求解', icon: 'key' },
      { key: 'logs', label: '操作日志', icon: 'log' },
      { key: 'feedback', label: '反馈建议', icon: 'help' },
      { key: 'settings-about', label: '关于我们', icon: 'aboutStatus' }
    ]
  }
]

// 数据同步板块仅在本地开发环境显示（VITE_SHOW_DATA_SYNC=true）
const showDataSync = import.meta.env.VITE_SHOW_DATA_SYNC === 'true'
if (showDataSync) {
  const systemCat = navCategories.find(c => c.key === 'system')
  if (systemCat) {
    systemCat.items.push({ key: 'settings-sync', label: '数据同步' })
  }
}

// 为了兼容旧代码，保留 navGroups 导出（平铺结构）
export const navGroups = navCategories.map(cat => ({
  title: cat.title,
  items: cat.items.map(item => ({ ...item, icon: cat.icon }))
}))

// 页面标题映射
export const pageTitles = {
  dashboard: ['导航面板', '系统导航中心，帮助你快速进入常用功能'],
  data: ['数据面板', '实时查看运营数据、发货情况与业务趋势'],
  accounts: ['闲鱼账号', '管理账号状态、登录情况与连接健康度'],
  products: ['商品管理', '管理商品信息、同步状态、自动发货与自动回复配置'],
  orders: ['订单管理', '集中查看订单状态、买家信息、发货情况与异常提醒'],
  refunds: ['退款管理', '查看与处理鱼小铺账号的买家退款申请（仅鱼小铺账号可用）'],
  'refund-cancel': ['退款关单', '同步到退款订单时，按账号调用外部注销接口关闭订单/回收卡密'],
  rates: ['评价管理', '集中查看买家评价并对未评价订单进行卖家评价（仅鱼小铺账号可用）'],
  'product-publish': ['商品发布', '创建并发布闲鱼商品'],
  'goods-data': ['商品数据分析', '查看商品曝光/订单趋势，筛选低效商品并一键重发或删除'],
  opportunities: ['商机发掘', '发现高潜力商品与经营机会'],
  'fish-shop-data': ['鱼小铺数据分析', '查看鱼小铺账号的成交、曝光、浏览、访问等官方数据（仅鱼小铺账号）'],
  'fish-shop-browse': ['流量分布', '查看流量来源、商品、时间与地域分布（仅鱼小铺账号）'],
  messages: ['在线消息', '集中处理买家咨询与消息会话'],
  'message-center': ['在线消息', '集中处理买家咨询与消息会话'],
  'auto-reply': ['自动回复', '配置买家消息自动回复规则'],
  'auto-reply-rules': ['回复规则', '管理关键词/AI 自动回复规则与命中策略'],
  'message-filters': ['消息过滤', '按关键词屏蔽骚扰消息：跳过自动回复或消息通知'],
  'default-reply': ['默认回复', '未命中关键词且 AI 关闭时，按账号兜底回复买家'],
  workflow: ['工作流', '设计并运行自动化业务流程'],
  'workflow-tasks': ['工作流任务', '查看工作流任务执行状态与结果'],
  'workflow-drafts': ['商品草稿箱', '工作流生成的商品草稿与发布记录'],
  'workflow-image-records': ['图片生成记录', '所有生图模型调用产生的图片历史'],
  'card-warehouse': ['卡密仓库', '管理卡密库存、分组与使用记录'],
  'blacklist': ['买家黑名单', '拉黑买家后自动发货直接拦截，不发送卡密/内容'],
  'auto-delivery': ['自动发货', '按商品配置自动发货规则、时机与发送方式'],
  'delivery-block-rules': ['发货拦截规则', '买家已有订单/未确认收货时自动拦截发货'],
  'delivery-source-library': ['货源库', '统一管理文本货源，支持 AI 推荐适配商品并批量配置'],
  'delivery-statement': ['发货声明', '管理发货声明文案与生效范围'],
  'delivery-mall': ['货源商城', '海量优质虚拟商品资源，自动发货，即买即用'],
  'delivery-records': ['发货记录', '追踪自动发货、异常与补发情况'],
  'scheduled-tasks': ['定时任务', '查看和维护定时任务执行计划'],
  'settings-notify': ['通知设置', '配置消息通知方式与提醒规则'],
  'settings-ai-cs': ['AI客服配置', '管理自动回复买家的 AI 客服配置（人设、工作时段、转人工策略等）'],
  'settings-kb': ['客服知识库', '管理客服知识库分类与对话内容'],
  'settings-sync': ['数据同步', '将本地配置一键同步到线上服务器'],
  'settings-about': ['关于我们', '查看版本信息与服务支持'],
  'slider-solve-records': ['滑块求解', '查看滑块自动求解的触发场景、处理结果与验证状态'],
  'api-slider-solve': ['API滑块求解', '开放滑块求解能力，对接外部系统，独立记录 API 求解与 Token 消费情况'],
  logs: ['操作日志', '查看系统操作与关键行为记录'],
  feedback: ['反馈建议', '提交产品建议、Bug 反馈与功能诉求'],
  'supply-center': ['供货中心', '管理你的供货商品、查看收入与审核状态'],
  'supply-center-products': ['我的货源', '管理已上传的货源商品'],
  'supply-center-products-new': ['上传货源', '提交新的货源商品到平台'],
  'supply-center-products-edit': ['编辑货源', '修改货源商品信息'],
  'platform-connect': ['平台对接', '该功能正在维护升级中，敬请期待'],
  'growth-partner': ['增长合伙人', '邀请用户、收益概览、代理功能与数据分析全掌握'],
  'invite-poster': ['邀请海报', '该功能正在维护升级中，敬请期待'],
  vip: ['VIP会员中心', '查看会员能力与套餐信息'],
  profile: ['个人中心', '管理账号资料、安全设置与余额信息']
}
