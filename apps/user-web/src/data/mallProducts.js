// 货源商城静态模拟数据（仅用于 UI 展示，不涉及接口请求）
// 每个商品的 coverFrom/coverTo 用于生成不同风格的渐变封面占位组件

export const textProducts = [
  {
    id: 't1',
    title: 'ChatGPT 提示词大全',
    intro: '2000+高质量提示词，覆盖工作、学习、生活等多个场景',
    price: '¥ 9.90',
    boughtCount: '1,689',
    publishTime: '07-15 12:20',
    tag: '热门推荐',
    category: '软件工具',
    coverFrom: '#5b8cff',
    coverTo: '#a06bff'
  },
  {
    id: 't2',
    title: '短视频运营实操手册',
    intro: '从0到1打造短视频账号，包含选题、拍摄、剪辑和运营流程',
    price: '¥ 14.90',
    boughtCount: '1,256',
    publishTime: '07-14 21:45',
    tag: '最新上架',
    category: '运营营销',
    coverFrom: '#ff7a59',
    coverTo: '#ff9f22'
  },
  {
    id: 't3',
    title: '小红书运营攻略大全',
    intro: '涵盖账号搭建、内容规划、涨粉、变现和品牌合作技巧',
    price: '¥ 12.90',
    boughtCount: '987',
    publishTime: '07-14 10:10',
    tag: '优质内容',
    category: '运营营销',
    coverFrom: '#ff4d6d',
    coverTo: '#ff7a9c'
  },
  {
    id: 't4',
    title: 'Python入门到精通教程',
    intro: '零基础学习Python，包含完整代码示例和实战项目',
    price: '¥ 39.90',
    boughtCount: '1,432',
    publishTime: '07-13 09:30',
    tag: '精品课程',
    category: '编程开发',
    coverFrom: '#16bf78',
    coverTo: '#0ea5a0'
  },
  {
    id: 't5',
    title: '电商运营资料大全',
    intro: '淘宝、拼多多、抖音电商等平台运营资料合集',
    price: '¥ 29.90',
    boughtCount: '1,875',
    publishTime: '07-13 16:40',
    tag: '精品',
    category: '运营营销',
    coverFrom: '#0d6bff',
    coverTo: '#11b5d8'
  },
  {
    id: 't6',
    title: 'Excel函数大全',
    intro: '常用Excel函数讲解，配合实战案例，提高办公效率',
    price: '¥ 8.90',
    boughtCount: '1,103',
    publishTime: '07-12 20:15',
    tag: '优质内容',
    category: '办公软件',
    coverFrom: '#16a34a',
    coverTo: '#65b535'
  },
  {
    id: 't7',
    title: '大学生职业规划指南',
    intro: '职业定位、简历制作、面试技巧等全方位指导',
    price: '¥ 16.90',
    boughtCount: '765',
    publishTime: '07-12 14:25',
    tag: '热门推荐',
    category: '考试学习',
    coverFrom: '#8b5cf6',
    coverTo: '#c084fc'
  },
  {
    id: 't8',
    title: 'AI人工智能入门与实战',
    intro: '从基础到实战，掌握AI核心技术与常见应用思路',
    price: '¥ 49.90',
    boughtCount: '1,214',
    publishTime: '07-11 19:15',
    tag: '精品课程',
    category: '编程开发',
    coverFrom: '#1f2a6b',
    coverTo: '#3b82f6'
  }
]

export const cardProducts = [
  {
    id: 'c1',
    title: '视频会员月卡',
    intro: '主流视频平台月度会员兑换码，到账即用',
    price: '¥ 19.90',
    stock: 326,
    publishTime: '07-15 09:00',
    tag: '卡密',
    category: '卡密商品',
    coverFrom: '#ff5b61',
    coverTo: '#ff9f22'
  },
  {
    id: 'c2',
    title: '云存储兑换卡',
    intro: '主流网盘大容量存储空间兑换卡，自动发货',
    price: '¥ 12.90',
    stock: 128,
    publishTime: '07-14 15:30',
    tag: '卡密',
    category: '卡密商品',
    coverFrom: '#0d6bff',
    coverTo: '#5b8cff'
  },
  {
    id: 'c3',
    title: '软件激活卡',
    intro: '正版软件激活码，购买后自动发送卡密',
    price: '¥ 29.90',
    stock: 35,
    publishTime: '07-13 11:20',
    tag: '卡密',
    category: '卡密商品',
    coverFrom: '#16bf78',
    coverTo: '#0ea5a0'
  },
  {
    id: 'c4',
    title: '素材网站兑换码',
    intro: '设计素材网站会员兑换码，海量素材免费下载',
    price: '¥ 9.90',
    stock: 8,
    publishTime: '07-12 16:50',
    tag: '卡密',
    category: '卡密商品',
    coverFrom: '#8b5cf6',
    coverTo: '#c084fc'
  }
]

export const mallCategories = [
  '全部',
  '软件工具',
  '教程资料',
  '运营营销',
  '设计素材',
  '编程开发',
  '考试学习',
  '其他'
]

export const mallAnnouncements = [
  { date: '07-16', text: '新增100+优质文本商品', badge: 'NEW' },
  { date: '07-15', text: '卡密商品库存同步优化完成', badge: '' },
  { date: '07-14', text: '系统维护公告（已完成）', badge: 'HOT' },
  { date: '07-13', text: '部分商品价格调整通知', badge: '' },
  { date: '07-10', text: '新增多种支付方式', badge: 'NEW' }
]

export const mallGuides = [
  { icon: 'product', title: '如何购买商品', desc: '选择商品后点击立即购买即可下单' },
  { icon: 'truck', title: '自动发货流程', desc: '付款后系统自动发货，秒级到账' },
  { icon: 'help', title: '商品使用帮助', desc: '查看商品详情页内的使用说明' },
  { icon: 'warning', title: '问题反馈与投诉', desc: '遇到问题可提交工单或投诉' }
]
