-- V1.46__deepen_ai_cs_knowledge_base.sql
-- 深度扩展 AI 客服"小梦"知识库：基于前台 user-web 全功能分析，为每个分类补充极其详细的条目
-- 覆盖：完整操作步骤、API 路径、参数限制、字段说明、常见错误、业务规则
-- 全部使用 INSERT ... WHERE NOT EXISTS 模式，幂等可重入
-- 注：core-api 不使用 Flyway 框架，本文件为文档性质；实际执行由 SchemaCompatibilityRunner 在启动时调用
-- 重要：content 字段均不含 ASCII 分号（使用中文标点），可安全按 ; 分割

-- ============================================================
-- 1. system_usage 系统使用总览（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'system_usage', '路由系统与页面访问方式',
'项目采用自定义路由系统（非 Vue Router），路由键通过 #/key 形式写入地址栏：
- 桌面端：App.vue 的 pageMap 维护路由键到异步组件的映射
- 移动端：MobileLite.vue 使用 activeTab（5 个底部 tab）+ subPage 二级路由模型
- 路由键示例：#/dashboard、#/orders、#/account-detail/123

静态路由（无需登录）：
- #/login 登录页（支持密码/邮箱验证码登录）
- #/register 注册页
- #/forgot-password 忘记密码页
- #/auto-login?token=xxx 管理员代登入口（token 一次性使用后立即清除）

动态路由（需登录）共 35+ 项，按功能分组：
- 概览：dashboard（导航面板）、data（数据面板）
- 账号与商品：accounts（闲鱼账号）、products（商品管理）、product-publish（发布商品）、orders（订单管理）、refunds（退款管理）、rates（评价管理）、opportunities（商机发掘）
- 消息：messages（在线消息）
- 自动化：workflow（工作流）、workflow-tasks（工作流任务）、workflow-drafts（商品草稿箱）、workflow-image-records（图片生成记录）、auto-delivery（自动发货）、delivery-source-library（货源库）、delivery-statement（发货声明）、delivery-mall（货源商城）、delivery-templates（模板管理）、delivery-records（发货记录）、card-warehouse（卡密仓库）、scheduled-tasks（定时任务）、auto-reply（自动回复）
- 系统：logs（操作日志）、slider-solve-records（滑块求解）、api-slider-solve（API滑块求解）、feedback（反馈建议）、settings-notify（通知设置）、settings-ai-cs（AI客服配置）、settings-kb（客服知识库）、settings-product（商品操作）、settings-about（关于）
- 个人：profile（个人中心）、vip（VIP会员中心）、user-manual（使用手册）

鉴权机制：JWT Token 存于 localStorage，请求自动注入 Authorization: Bearer 头。401 时清除 token 并跳转登录页（SSE 接口除外）',
'system_usage,router,route,路由,page,页面,导航,地址栏,hash,登录', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='system_usage' AND title='路由系统与页面访问方式');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'system_usage', '功能开关与等级拦截',
'功能开关（feature-switch）拦截机制：
- 进入页面前 App.vue.checkFeatureSwitch(pageKey) 调用 GET /feature-switches/status
- 被拦截时弹窗提示，不跳转占位页
- 拦截原因：
  * reason=maintenance：功能维护中
  * reason=level：等级不足，引导升级到 VIP/SVP
  * reason=disabled：功能暂未开放

跳过检查的页面：login、register、forgot-password、feature-unavailable、dashboard

缓存策略：
- 30 秒前端缓存
- 登录/登出/套餐变更后调用 invalidateFeatureSwitchCache() 强制刷新
- 功能对比表 GET /feature-switches/comparison 缓存 60 秒

会员等级功能对比：
- 普通用户：基础功能
- VIP：解锁更多高效功能
- SVP：最高等级，享受所有权益
- 数据来源：后台「系统运维 → 功能管理」配置',
'system_usage,feature,switch,开关,拦截,等级,vip,svp,升级', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='system_usage' AND title='功能开关与等级拦截');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'system_usage', 'SSE 实时通道与维护模式',
'SSE 业务事件通道：
- 连接 URL：/sse/events
- 工具：utils/sse.js
- 事件分发：通过 xya-sse-event 全局事件推送
- 推送事件类型：订单、发货、AI 回复、账号状态等实时事件

AI 客服流式聊天（特殊）：
- 使用 fetch 直连 /api/ai-cs/chat（不走 axios）
- 事件类型：
  * delta：增量内容
  * tool_call：工具调用请求
  * tool_result：工具执行结果
  * insufficient_balance：余额不足
  * context_exceeded：上下文超限
  * casual_remind：闲聊提醒
  * done：流结束（含 tokensCharged）
  * error：错误

维护模式横幅：
- MaintenanceBanner.vue 每 60 秒轮询 GET /api/maintenance/status
- enabled=true 时在所有页面顶部显示横幅
- Redis 不可达时降级为 enabled=false（不锁死前台）
- 维护状态存储：Redis key xianyu:maintenance:enabled / message / until',
'system_usage,sse,实时,事件,maintenance,维护,横幅,banner,redis', 96, 1, 16, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='system_usage' AND title='SSE 实时通道与维护模式');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'system_usage', '移动端与桌面端切换',
'移动端生效条件：
- App.vue 的 shouldUseMobileLite 计算属性为 true
- 触发条件：屏幕宽度 ≤ 768px 且未强制桌面模式
- 可通过 localStorage.xya_mobile_desktop_override 强制桌面模式

移动端底部 Tab（5 个）：
1. home（首页）：MobileHome.vue
2. products（商品）：MobileProducts.vue
3. product-publish（发布，中间凸起按钮）：MobileProductPublish.vue
4. orders（订单）：MobileOrders.vue
5. profile（我的）：MobileProfile.vue

移动端子页（subPage）：
- data / data-detail：数据看板 / 数据详情
- products / product-detail / product-publish：商品管理 / 详情 / 发布
- opportunity：商机发掘
- accounts / account-detail：账号管理 / 详情
- messages / chat-detail / notifications：在线消息 / 聊天详情 / 消息中心
- auto-delivery / auto-delivery-config：自动发货 / 配置
- delivery-source-library / delivery-records：货源库 / 发货记录
- order-detail：订单详情
- profile-security / profile-ledger / profile-recharge：安全 / Token流水 / 充值
- api-slider-solve：API滑块求解

全局导航栏组件位置：
- MobileLite.vue：承载顶部导航 m-topbar、底部导航 m-tabbar、左侧抽屉 m-drawer
- nav.js：导航数据源（navGroups、settingsTabs、settingsKeys、bottomTabs）
- MobileIcons.js：SVG 图标库

注意：顶部/底部导航栏为全局组件，不得因单页设计图差异而更改',
'system_usage,mobile,移动端,桌面,切换,tab,bottom,drawer,抽屉', 96, 1, 17, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='system_usage' AND title='移动端与桌面端切换');

-- ============================================================
-- 2. xianyu_account 闲鱼账号管理（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'xianyu_account', '添加账号三种方式与操作步骤',
'方式 A：扫码登录（推荐）
操作步骤：
1. 账号管理页点击"添加账号"或对已有账号点"重新扫码"
2. 弹出二维码弹窗，点击"生成二维码"按钮 → POST /qrlogin/generate
3. 系统返回 sessionId 与 qrUrl，前端渲染二维码
4. 用户使用闲鱼 App 扫码并确认登录
5. 前端轮询 POST /qrlogin/status/{sessionId} 等待登录结果
6. 登录成功：新增模式自动添加账号并刷新资料；重扫模式将新 Cookie 回写到当前账号

接口：
- 生成二维码：POST /qrlogin/generate
- 查询状态：POST /qrlogin/status/{sessionId}
- 清理会话：POST /qrlogin/cleanup

方式 B：Cookie 手动导入
操作步骤：
1. 账号管理页选择"手动添加账号"
2. 填写账号备注（可选，最多 50 字符，有 0/50 计数提示）
3. 粘贴 Cookie 字符串（必填，从浏览器 F12 → Application → Cookies 中复制）
4. 前端实时解析 Cookie 并展示预览：unb（身份标识，必填）、_m_h5_tk（签名 Token）、user_id
5. 解析失败或缺少 unb 时禁用"添加"按钮
6. 提交 → POST /xianyu/accounts/manual-cookie

字段限制：
- 账号备注：最长 50 字符
- Cookie：必填，必须包含 unb 字段，建议包含 _m_h5_tk

方式 C：更新已有账号 Cookie
操作步骤：
1. 账号详情或列表点"更新 Cookie"
2. 粘贴新 Cookie，前端做身份校验（防串号）：检测新 Cookie 的 unb 与原账号 unb 是否一致，不一致显示警告
3. 保存 → POST /xianyu/accounts/{id}/cookie，后端自动提取 unb、_m_h5_tk 等字段并重置 Cookie 状态为正常',
'xianyu_account,add,添加,扫码,cookie,手动,导入,qrlogin,unb', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='xianyu_account' AND title='添加账号三种方式与操作步骤');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'xianyu_account', '账号状态字段含义与异常处理',
'账号状态字段：

1. 在线状态（WS 状态）
- 含义：WebSocket 连接状态
- 取值：在线 / 离线 / 状态未知
- 异常处理：离线可点击"连接 WS"重新建立

2. Cookie 状态
- 取值：0=失效（需重新扫码）/ 1=正常 / 2=即将过期
- 异常处理：失效时必须重新扫码或更新 Cookie，滑块求解无法恢复

3. WS Token 获取失败
- 含义：在线消息页遇到滑块自动求解失败
- 处理：可在账号页"重试求解"后重连 WS

4. 滑块求解失败
- 含义：系统已尝试自动拖动但未通过
- 处理：点击"重试求解"，多次失败建议手动完成验证

5. 触发人机验证
- 含义：闲鱼平台要求滑块验证
- 处理：系统自动尝试求解，持续失败建议在闲鱼 APP 中验证

6. 服务暂时不可用
- 含义：crawler-service 繁忙或不可达
- 处理：稍后重试，持续失败联系管理员

7. 账号不活跃/已禁用
- 含义：超过 3 天未操作或被禁用
- 处理：手动连接账号或联系管理员启用

列表搜索支持：昵称/UID/备注
状态筛选支持：全部/正常/需验证/Cookie异常/WS在线',
'xianyu_account,status,cookie,ws,滑块,验证,异常,失效,在线', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='xianyu_account' AND title='账号状态字段含义与异常处理');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'xianyu_account', '账号管理操作清单与接口',
'账号管理操作：

1. 启用/禁用 WS
- 入口：列表"连接/断开 WS"
- 接口：POST /websocket/checkLogin 等
- 说明：控制在线消息接收

2. 删除账号
- 入口：列表"删除"
- 接口：DELETE /xianyu/accounts/{id}
- 说明：二次确认后删除

3. 刷新资料
- 入口：列表"刷新资料"
- 接口：POST /xianyu/accounts/{id}/refresh-profile
- 说明：拉取闲鱼主页资料（粉丝、已售、评价等）

4. 重新扫码
- 入口：列表"重新扫码"
- 接口：POST /qrlogin/generate
- 说明：走扫码登录流程获取新 Cookie

5. 重试求解
- 入口：滑块横幅"重试求解"
- 接口：crawler-service 求解
- 限制：每分钟最多 1 次主动求解，失败后"重试求解"不受冷却限制

6. 一键擦亮
- 入口：列表"一键擦亮"
- 接口：POST /item/polish
- 超时：10 秒
- 进度查询：GET /item/polishProgress/{taskId}

7. 检查鉴权
- 入口：详情页
- 接口：POST /xianyu/accounts/{id}/check-auth
- 说明：校验账号登录态

8. 自动评价
- 入口：详情页"自动评价"
- 接口：GET/PUT /xianyu/accounts/{id}/auto-rate
- 评价方式：固定文本 / 外部 API
- 外部 API 超时：默认 3600 秒

注意事项：
- Cookie 字段 unb 必须存在，是身份标识
- Cookie 编辑时会做身份校验，防止串号
- 单账号手动求解冷却：每分钟最多 1 次
- 账号超过 3 天未操作会自动暂停滑块求解',
'xianyu_account,操作,接口,删除,刷新,擦亮,求解,评价,check-auth', 96, 1, 16, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='xianyu_account' AND title='账号管理操作清单与接口');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'xianyu_account', '账号 API 完整清单',
'账号管理 API：

查询类：
- GET /xianyu/accounts（分页列表，query: current/size/keyword/status）
- GET /xianyu/accounts/lite（轻量列表）
- GET /xianyu/accounts/{id}（详情）
- GET /xianyu/accounts/summary（汇总统计）
- GET /xianyu/accounts/{id}/auto-rate（自动评价配置）
- GET /xianyu/accounts/{id}/strategy-config（策略配置）
- GET /xianyu/accounts/{id}/login-credential（登录凭证）
- GET /xianyu/accounts/face-verifications（人脸验证列表）

创建/更新类：
- POST /xianyu/accounts（创建账号）
- POST /xianyu/accounts/manual-cookie（Cookie 创建）
- PUT /xianyu/accounts/{id}（更新账号）
- POST /xianyu/accounts/{id}/cookie（更新 Cookie）
- POST /xianyu/accounts/{id}/refresh-profile（刷新资料）
- POST /xianyu/accounts/{id}/check-auth（校验鉴权）
- PUT /xianyu/accounts/{id}/auto-rate（保存自动评价配置）
- PUT /xianyu/accounts/{id}/strategy-config（保存策略配置）
- PUT /xianyu/accounts/{id}/login-credential（保存登录凭证）

删除类：
- DELETE /xianyu/accounts/{id}（删除账号）

人脸验证：
- POST /xianyu/accounts/face-verifications/{id}/read（标记已读）

商品擦亮：
- POST /item/polish（触发擦亮，body: {xianyuAccountId}）
- GET /item/polishProgress/{taskId}（查询进度）

Cookie 保活：
- POST /websocket/refreshCookie（body: {accountId}）
- POST /websocket/checkLogin（检查登录状态）

扫码登录：
- POST /qrlogin/generate（生成二维码）
- POST /qrlogin/status/{sessionId}（查询状态）
- POST /qrlogin/cleanup（清理会话）',
'xianyu_account,api,接口,清单,query,create,update,delete', 96, 1, 17, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='xianyu_account' AND title='账号 API 完整清单');

-- ============================================================
-- 3. product_publish 商品发布与管理（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'product_publish', '商品发布完整字段与限制',
'发布商品页面字段（ProductPublishPage.vue）：

宝贝基础信息：
- 闲鱼账号：必选，从已登录账号下拉选择
- 宝贝标题：最长 30 字符（maxlength=30，实时计数 0/30）
- 宝贝描述：无明确上限，文本域 4 行
- 宝贝图片：最多 10 张，支持 JPEG/PNG/GIF/WebP，单张 ≤ 5MB
- 图片 URL 导入：支持 http/https，可粘贴 URL 导入封面图

商品分类：
- 三级级联选择（一级 → 二级 → 三级）
- 支持搜索分类（最多展示 20 条结果）
- 收藏分类、最近使用分类快捷选择
- 上传封面图后自动检测分类（AI 视觉识别）
- 支持"AI 自动选择"按钮（需 AI 分类状态 configured 为 true）

商品位置：
- 省市区三级联动地址选择器（PublishAddressCascader）

价格与规格：
- 售价（元）：min=0，step=0.01，多规格开启时禁用
- 库存：数字，多规格开启时禁用
- 多规格：最多 2 个规格类型，仅鱼小铺账号可用

多规格商品（MultiSpecEditor）：
- 仅鱼小铺账号可开启
- 最多 2 个规格类型
- 自动生成 SKU 笛卡尔积（价格、库存按 SKU 维度填写）
- 支持规格图片、SKU 封面图上传
- 字段：price（精确到分）、stock（≥0）、skuId、inventoryId、skuCode（可选）

自动发货（发布时配置）：
- 开关：开启后买家付款自动发送所选货源的发货内容
- 关联货源库：从货源库下拉选择

发货设置：
- 包邮 / 一口价·运费 / 无需邮寄 / 支持自提（多选）

AI 生成描述：
- 入口：宝贝描述下方"AI 生成描述"chip
- 流程：先校验 Token 余额 → POST /workflow/ai/rewrite（场景 workflow_rewrite）
- 扣费：通用模型按次计费，按 VIP 等级差异化（普通 3 / VIP 2 / SVP 1 Token，可配置）',
'product_publish,字段,限制,title,price,stock,sku,图片,分类', 96, 1, 17, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='product_publish' AND title='商品发布完整字段与限制');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'product_publish', '商品列表与同步管理',
'商品列表（ProductsPage.vue）：

筛选与搜索：
- 账号下拉 + 状态 Tab（在售=0 / 下架·草稿=1 / 已删除=3）
- 搜索：商品标题 / 商品ID，回车搜索

统计卡片：
- 商品总数
- 在售商品
- 下架/草稿
- 自动发货商品数
- 自动回复账号数

行内操作：
- 同步（单条刷新）
- 编辑（仅鱼小铺商品且 canEdit === 1 可编辑）
- 删除（本地删除 + 远程下架，支持批量删除）
- 行内改价（鱼小铺单价格商品，输入"新价格"确认）
- 售整自动上架开关（PUT /goods/{id}/auto-relist，参数 enabled）

同步闲鱼商品：
- 批量同步按钮，支持多账号并行同步，展示进度百分比
- 前端轮询策略：500ms × 10 次，然后 2s 间隔
- 单次同步 73 个商品约 3 秒完成

同步任务历史：
- 按状态筛选（排队中/运行中/已完成/失败）
- 分页展示
- 接口：GET /item/syncTasks

商品 API：
- GET /goods（分页列表）
- GET /goods/stats（统计）
- POST /goods（创建）
- GET /goods/{id}（详情）
- PUT /goods/{id}（更新）
- DELETE /goods/{id}/local（仅删除本地）
- DELETE /goods/{id}/remote（删除远端）
- PUT /goods/{id}/auto-relist（切换售整自动上架）

鱼小铺商品 API：
- POST /fish-shop/publish（多规格发布）
- POST /fish-shop/edit（多规格编辑）
- POST /fish-shop/detail（详情，body: {xianyuAccountId, itemId}）

商品操作 API（Python 链路）：
- POST /item/list（列表）
- POST /item/refresh（同步触发刷新，60s）
- POST /item/publish（发布）
- POST /item/detail（详情）
- POST /item/delete（删除）
- POST /item/offShelf（下架）
- POST /item/republish（重新上架）
- POST /item/auto-relist/toggle（切换自动上架）
- POST /item/updatePrice（更新价格）
- POST /item/updateStock（更新库存）
- POST /item/updateAutoDeliveryStatus（切换自动发货）
- POST /item/updateAutoConfirmShipment（切换自动确认发货）
- POST /item/updateAutoReplyStatus（切换自动回复）
- POST /item/batch/delete（批量删除）
- POST /item/batch/offShelf（批量下架）
- POST /item/batch/remoteDelete（批量远端删除）

同步进度查询：
- GET /item/syncProgress/{syncId}（轮询）
- GET /item/syncing/{accountId}（是否同步中）
- GET /item/syncTasks（同步任务历史）

注意事项：
- 多规格商品仅鱼小铺账号可用，普通账号无法开启
- 商品标题 30 字符硬限制
- 图片单张 ≤ 5MB，仅支持 JPEG/PNG/GIF/WebP
- AI 生成描述前会强制校验 Token 余额
- 编辑商品仅鱼小铺且 canEdit === 1 支持
- 商品删除会同时尝试远程下架，失败会有警告提示',
'product_publish,list,列表,同步,sync,api,商品,操作,删除', 96, 1, 18, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='product_publish' AND title='商品列表与同步管理');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'product_publish', '自动分类与 AI 视觉识别',
'自动分类功能：
- 接口：POST /xianyu/accounts/{accountId}/auto-category（超时 120s）
- 上传图片触发：POST /xianyu/accounts/{accountId}/auto-category/upload（form 表单）
- 配置查询：GET /xianyu/accounts/auto-category/config

分类策略（重要约束）：
- 必须优先使用 categoryPredictResult，跳过 score/margin/名称检查
- min_score 阈值：0.03
- min_margin 阈值：0.01

分类树管理：
- GET /xianyu/categories（完整分类树）
- POST /xianyu/categories/sync（同步分类，body: {candidates}）

AI 分类建议：
- POST /ai-provider/category-suggest（AI 分类建议）

发布地址管理：
- GET /publish-address/history（常用发布地址历史）
- POST /publish-address/save（保存发布地址，body: {poiName, city, area, detail}）
- GET /address-dict/tree（省市区地址字典）

未生成 AI 封面图的商品严禁发布：
- 发布前必须强制校验 img_ai_ok == True
- 违反此约束即为事故级 Bug',
'product_publish,auto,category,分类,ai,视觉,识别,address,地址', 96, 1, 19, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='product_publish' AND title='自动分类与 AI 视觉识别');

-- ============================================================
-- 4. orders 订单管理（新增分类）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'orders', '订单状态流转与含义',
'订单状态码（orderStatus 字段）：

0 - 待付款：买家下单未付款
1 - 已付款：买家已完成付款
2 - 待发货：已付款等待卖家发货
3 - 已发货：卖家已发货
4 - 已完成：交易完成
5 - 已关闭：订单关闭

今日订单金额统计规则：
- 仅统计 orderStatus IN (1,2,3,4) 且未删除订单
- 汇总 totalAmount 之和
- 接口：GET /orders/today-amount（query: {accountId}）

订单列表筛选：
- 店铺：全部/指定账号
- 订单状态：全部/待发货/已发货/已完成/已关闭/待付款/已付款
- 关键词：订单号 / 买家 / 商品名称 / 商品 ID

统计卡片：
- 全部订单
- 待发货
- 已完成
- 异常订单
- 今日订单金额

批量操作：
- 标记已发货
- 批量同步
- 导出选中（/excel/export/orders）',
'orders,status,状态,流转,待付款,待发货,已完成,今日,金额', 96, 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='orders' AND title='订单状态流转与含义');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'orders', '手动发货操作与字段',
'手动发货（订单详情页）：

发货来源：
- custom：自定义内容（手写文本/卡密/下载链接）
- library：从货源库选择

发货时机（deliveryTiming）：
- after_payment：付款后
- after_receipt：收货后
- after_review：评价后

发货方式（deliveryMode）：
- text：文本发货
- card：卡密发货

货源库选择：
- 文本货源：直接选择
- 卡密货源：检测 cardRemainCount，库存为 0 时阻止发货

提交接口：POST /orders/{id}/manual-delivery
提交后：提示"手动发货任务已提交"，并刷新货源列表

订单同步：
- 单条：POST /orders/{id}/sync
- 批量：POST /orders/sync（body）
- 旧版批量刷新：POST /order/batchRefresh（超时 300s）
- 旧版同步已卖出：POST /order/syncSoldOrders（超时 300s）

注意：列表默认展示本地缓存，需点"同步订单"拉取闲鱼最新数据',
'orders,manual,delivery,手动,发货,timing,mode,card,text', 96, 1, 2, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='orders' AND title='手动发货操作与字段');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'orders', '退款与评价管理',
'退款管理（RefundsPage.vue）：
- 适用账号：仅鱼小铺账号支持退款管理，普通账号被后端拒绝
- 分类筛选：all（全部）/ unshipped（未发货退款）/ shipped（已发货退款）/ return（退货退款）/ freight（退运费）
- 同步退款：POST /refunds/sync（超时 130 秒，后端 120 秒）
- 同步状态查询：GET /refunds/sync-status
- 同意退款：POST /refunds/{refundId}/agree（超时 35 秒）
- 鱼小铺账号列表：GET /refunds/fish-shop-accounts
- 重要：同意退款是资金操作，前端会展示风险说明并要求二次确认

评价管理（RatesPage.vue）：
- 适用账号：仅鱼小铺账号支持评价管理
- 评价列表：GET /rates（query: accountId/category/keyword/page/pageSize）
- 触发评价同步：POST /rates/sync（body: {accountId}）
- 同步状态：GET /rates/sync-status
- 评价概览：GET /rates/overview
- 创建评价：POST /rates/create（body: {accountId, orderId, rate, feedback, anonymous}）
- 鱼小铺账号列表：GET /rates/fish-shop-accounts

自动评价配置（账号详情页）：
- 查询：GET /xianyu/accounts/{id}/auto-rate
- 保存：PUT /xianyu/accounts/{id}/auto-rate
- 评价方式：固定文本 / 外部 API
- 外部 API 超时：默认 3600 秒',
'orders,refund,退款,rate,评价,agree,sync,鱼小铺', 96, 1, 3, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='orders' AND title='退款与评价管理');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'orders', '订单 API 完整清单',
'订单管理 API：

查询类：
- GET /orders（订单列表，支持 query 参数筛选）
- GET /orders/{id}（订单详情）
- GET /orders/today-amount（今日订单金额，query: {accountId}）
- GET /orders（query: {accountId, buyerId, size}，买家近期订单，消息页用）

更新类：
- PUT /orders/{id}（更新订单）
- POST /orders/{id}/manual-delivery（手动发货）
- POST /orders/{id}/sync（同步单笔订单）
- POST /orders/sync（批量同步订单）

旧版 API（Python 链路）：
- POST /order/list（旧版订单列表）
- POST /order/confirmShipment（确认发货）
- POST /order/batchRefresh（批量刷新，超时 300s）
- POST /order/syncSoldOrders（同步已卖出，超时 300s）

导出：
- /excel/export/orders（订单导出 URL，query 参数）

买家近期订单（消息页用）：
- GET /orders（query: {accountId, buyerId, size}）',
'orders,api,接口,清单,list,sync,delivery,export', 96, 1, 4, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='orders' AND title='订单 API 完整清单');

-- ============================================================
-- 5. auto_reply 自动回复（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'auto_reply', 'AI 客服统一回复架构',
'重要架构说明：
本项目的"自动回复"采用 AI 客服统一回复架构，没有传统的"关键词→固定文本"规则。所有自动回复由 AI 客服配置驱动。

- 自动回复页面作用：配置自动回复的作用域（哪些账号、哪些商品启用 AI 自动回复）
- AI 客服话术、知识库、聊天规则：在「AI 客服配置」页面统一维护

作用域层级（优先级从高到低）：
1. 商品级配置（覆盖账号级）
2. 账号级配置（覆盖全局默认）
3. 全局默认配置

操作步骤：
- 左侧：选择账号与商品（支持搜索商品标题、关键词、店铺标签）
- 右侧：查看当前作用域、启用状态、AI 配置摘要
- 状态完整加载后才允许修改

启用商品/账号自动回复时：
- 若 AI 客服主开关未开，会同步开启主开关
- 弹窗确认"同步开启 AI 客服主开关"

AI 客服摘要展示：
- 已配置知识库数量（>1 显示"已配置 N 份知识库"，=1 显示"已配置 1 份知识库"）
- 已配置聊天规则数量
- 跳转链接："前往 AI 客服配置修改"

注意事项：
- 自动回复能力依赖 AI 客服主开关，关闭主开关后所有自动回复失效
- 商品级关闭会覆盖账号级开启，账号级开启会覆盖全局默认状态
- 启用前会校验 AI 客服配置是否可用，不可用会阻止覆盖保存
- "打开后，该账号下未单独关闭的商品都会进入 AI 客服处理链路"',
'auto_reply,架构,ai,客服,统一,作用域,scope,覆盖', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_reply' AND title='AI 客服统一回复架构');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'auto_reply', '自动回复 API 与会话级控制',
'自动回复规则 API：
- GET /auto-reply/rules（规则列表）
- POST /auto-reply/rules（创建规则）
- PUT /auto-reply/rules/{id}（更新规则）
- DELETE /auto-reply/rules/{id}（删除规则）
- POST /auto-reply/rules/preview（预览规则效果）
- GET /auto-reply/rules/logs（自动回复日志）
- GET /auto-reply/rules/stats（自动回复统计）

作用域管理 API：
- GET /auto-reply-scope/products（query: {accountId}，商品自动回复作用域）
- POST /auto-reply-scope/product（body: {itemId, enabled}，更新商品作用域）
- POST /auto-reply-scope/account（body: {accountId, enabled}，更新账号作用域）
- POST /auto-reply-scope/batch（批量更新作用域）
- GET /auto-reply-scope/status（query: {accountId}，作用域状态）

会话级手动开关：
- POST /auto-reply-scope/conversation-toggle（body: {accountId, sid, peerUserId, enabled}）
- GET /auto-reply-scope/conversation-status（会话级状态）

使用场景：
- 卖家可在消息页对特定会话手动关闭 AI 自动回复
- 关闭后该会话由人工接管，AI 不再自动回复
- 重新开启后恢复 AI 自动回复',
'auto_reply,api,接口,scope,会话,conversation,toggle,手动', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_reply' AND title='自动回复 API 与会话级控制');

-- ============================================================
-- 6. auto_delivery 自动发货（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'auto_delivery', '发货方式与触发时机',
'发货方式：
- text（文本发货）：直接发送文本内容，可引用货源库
- card（卡密发货）：从卡密分组自动扣减，按模板发送

历史模式（已停用）：
- api、custom 模式现已停用
- 编辑时需改用文本或卡密发货

发货触发时机（timing）：
1. payDelivery（付款后发货）
   - 系统定时扫描自动执行
   - 由 auto_redelivery 定时任务驱动（默认每 10 分钟扫描）

2. confirmDelivery（确认收货后赠送）
   - 可在发货记录页手动触发
   - 或接入事件自动化

3. reviewDelivery（好评后赠送）
   - 可在发货记录页手动触发
   - 或接入事件自动化

商品级发货配置：
- 每个商品可针对 3 种时机独立配置
- 启用开关：每种时机单独开关
- 文本发货：
  * 可选"不使用货源库，直接手写内容"
  * 可选引用货源库（自动填充正文，可继续补充或覆盖）
  * 支持 {货源:ID} 占位符，发货时自动替换为对应货源最新内容
  * 字段：header（可选正文前说明）、body（正文）、footer（可选正文后补充）
- 卡密发货：
  * 绑定卡密分组（必选）
  * 卡密模板：例如"您的卡密为：{卡密}"

商品级配置 API：
- 批量获取：POST /auto-delivery/goods/configs/batch（body: {goodsIds}，避免逐个请求 3s+ 等待）
- 单个获取：GET /auto-delivery/goods/{goodsId}/config
- 保存：PUT /auto-delivery/goods/{goodsId}/config
- 切换开关：PATCH /auto-delivery/goods/{goodsId}/config/{timing}（body: {enabled}）',
'auto_delivery,mode,timing,付款,收货,评价,触发,配置', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_delivery' AND title='发货方式与触发时机');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'auto_delivery', '全店默认配置与批量操作',
'全店默认配置：
- GET /auto-delivery/global-config（查询）
- PUT /auto-delivery/global-config（保存）

批量操作：
- POST /auto-delivery/rules/batch（批量设置规则）
- POST /auto-delivery/rules/batch-delete（批量删除规则）
- POST /auto-delivery/rules/apply-all（应用到所有商品）

发货规则 CRUD：
- GET /auto-delivery/rules（规则列表）
- POST /auto-delivery/rules（创建规则）
- PUT /auto-delivery/rules/{id}（更新规则）
- DELETE /auto-delivery/rules/{id}（删除规则）

手动触发发货：
- POST /auto-delivery/trigger（body: {orderId, timing}，手动触发发货）
- POST /auto-delivery/scan（扫描待发货订单）

注意事项：
- "付款后发货"由系统定时扫描自动执行
- "确认收货后赠送"和"好评后赠送"目前主要靠手动触发
- 卡密发货前会检测 cardRemainCount，库存为 0 阻止发货
- 卡密库存低于 alertThreshold（默认 10）会标红预警
- 历史规则若使用已停用的 api 模式，编辑时需改用文本或卡密发货',
'auto_delivery,global,批量,batch,rules,apply,trigger,scan', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_delivery' AND title='全店默认配置与批量操作');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'auto_delivery', '发货记录与重试机制',
'发货记录（DeliveryRecordsPage.vue）：

状态筛选：
- 0=待处理
- 1=进行中
- 2=成功
- 3=失败
- 6=缺货
- 7=配置错误

时机筛选：付款后 / 收货后 / 评价后
方式筛选：文本 / 卡密
关键词搜索：商品关键词 / 买家关键词 / 订单号·外部订单号

重试机制：
- 单条重试：POST /auto-delivery/records/{id}/retry
- 批量重试：选中后"重试选中"
- 重新发货计划：POST /auto-delivery/records/{id}/schedule-redelivery（支持 Cron 表达式，如 0 0/15 * * * ?）

发货记录 API：
- GET /auto-delivery/records（列表）
- GET /auto-delivery/records/{id}（详情）
- POST /auto-delivery/records/{id}/retry（重试）
- POST /auto-delivery/records/{id}/schedule-redelivery（计划补发）
- GET /auto-delivery/stats（发货统计）

发货声明（卖家手动处理会话）：
- 查询会话：GET /auto-delivery/statement/sessions（query: page/size/status/accountId）
- 确认会话：POST /auto-delivery/statement/sessions/{id}/confirm
- 取消会话：POST /auto-delivery/statement/sessions/{id}/cancel
- 会话状态：declaring（发送中）/ waiting（等待买家确认）/ confirmed（已确认）/ cancelled（已取消）

发货声明管理：
- GET /auto-delivery/statement（查询）
- PUT /auto-delivery/statement（保存）
- PATCH /auto-delivery/statement/toggle（切换开关）
- POST /auto-delivery/statement/preview（预览）',
'auto_delivery,records,记录,重试,retry,redelivery,statement,声明', 96, 1, 16, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_delivery' AND title='发货记录与重试机制');

-- ============================================================
-- 7. card_key 卡密管理（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'card_key', '卡密分组与字段限制',
'卡密分组字段（CardWarehousePage.vue）：

必填字段：
- groupName：分组名称（如"月卡VIP"）
- cardType：卡密类型（必选）

可选字段：
- remark：备注信息
- alertThreshold：库存预警阈值，默认 10
- status：1=启用，0=禁用

统计卡片：
- 卡密组数
- 卡密总量（stockStats.total）
- 未使用（stockStats.remain）
- 已使用（stockStats.used）
- 异常/作废（stockStats.invalid）
- 低库存数（剩余 < alertThreshold，默认 10）

库存预警：
- 低于 alertThreshold 标红
- 全局预警查询：GET /cards/alerts
- 单组库存统计：GET /cards/{groupId}/stats

卡密分组 API：
- GET /cards（分组列表）
- POST /cards（创建分组）
- PUT /cards/{id}（更新分组）
- DELETE /cards/{id}（删除分组）
- GET /cards/{groupId}（分组详情）
- GET /cards/{groupId}/stats（库存统计）
- GET /cards/{groupId}/usage（使用记录，分页）
- GET /cards/{groupId}/export（导出为 blob）
- GET /cards/alerts（全局预警）',
'card_key,group,分组,字段,alert,预警,stats,统计', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='card_key' AND title='卡密分组与字段限制');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'card_key', '卡密明细批量导入与状态操作',
'卡密明细批量导入支持格式：

1. 卡密内容（每行一条）：
   VIP-AAAA-BBBB

2. 卡号----密码（卡号+密码类型）：
   VIP-AAAA-BBBB----1234

3. 卡号,密码：
   VIP-AAAA-BBBB,1234

导入验证：POST /cards/import/validate（验证导入格式）

卡密明细 API：
- GET /cards/{groupId}/items（列表，分页）
- POST /cards/{groupId}/items（单条新增）
- POST /cards/{groupId}/items/batch（批量新增）
- DELETE /cards/{groupId}/items/{itemId}（删除）
- POST /cards/{groupId}/items/{itemId}/reset（重置为未使用）
- POST /cards/{groupId}/items/{itemId}/invalid（标记为异常/作废）
- POST /cards/{groupId}/items/{itemId}/lock（锁定不可领取）

卡密状态说明：
- 未使用：可被发货系统自动领取
- 已使用：已被订单消耗
- 锁定：临时不可领取（如手动暂停）
- 异常/作废：标记为无效，不会被领取

操作说明：
- 重置：将已使用/异常的卡密恢复为未使用状态
- 作废：标记为异常，不会被发货系统领取
- 锁定：临时冻结，不可领取（可解锁）
- 导出：导出为 txt 文件（blob 流）',
'card_key,import,批量,导入,格式,reset,invalid,lock,export', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='card_key' AND title='卡密明细批量导入与状态操作');

-- ============================================================
-- 8. delivery_source 货源库（新增分类）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'delivery_source', '货源库字段与发货模式',
'货源库（DeliverySourceLibraryPage.vue）：

字段限制：
- title：最长 50 字符（给用户和 AI 模型看的标题，maxlength=50）
- content：最长 5000 字符（实际发货文本内容，maxlength=5000）
- remark：最长 200 字符（备注信息，maxlength=200）
- deliveryMode：text（文本发货）/ card（卡密发货）
- fromMall：布尔（是否商城货源，商城货源固定文本模式，不可改）

文本发货：
- 实际发货文本内容
- 可插入 {货源:ID} 占位符（商城货源场景）
- 商城货源：可编辑标题、正文、备注，发货类型固定为文本模式

卡密发货：
- 实际发货文本，必须包含 {卡密占位}
- 发货时自动替换为认领到的卡密
- 显示剩余卡密数量 cardRemainCount

统计指标：
- 货源总数
- 卡密发货源数
- 文本发货源数
- 绑定商品总数
- 低库存预警数（卡密库存不足时提示"卡密库存不足，请补充"）

货源库 API：
- GET /auto-delivery/sources（列表，支持搜索：标题/正文/备注）
- POST /auto-delivery/sources（新增货源）
- GET /auto-delivery/sources/{id}（详情）
- PUT /auto-delivery/sources/{id}（编辑）
- DELETE /auto-delivery/sources/{id}（删除）
- GET /auto-delivery/sources/{id}/goods（关联商品）
- POST /auto-delivery/sources/{id}/recommend（AI 推荐适配商品）
- POST /auto-delivery/sources/{id}/apply（批量绑定商品）
- DELETE /auto-delivery/sources/{id}/goods/{goodsId}（解除绑定）
- GET /auto-delivery/sources/by-mall-product/{mallProductId}（按商城货源查）',
'delivery_source,字段,限制,title,content,mode,card,text,商城', 96, 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='delivery_source' AND title='货源库字段与发货模式');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'delivery_source', '发货模板与商城',
'发货模板（DeliveryTemplatesPage.vue）：
- 列表：GET /auto-delivery/templates
- 创建：POST /auto-delivery/templates
- 更新：PUT /auto-delivery/templates/{id}
- 删除：DELETE /auto-delivery/templates/{id}
- 复制：POST /auto-delivery/templates/{id}/copy
- 模板变量：GET /auto-delivery/templates/variables

货源商城（DeliveryMallPage.vue）：
- 用于购买商城货源
- 商城商品：GET /mall/products
- 商城分类：GET /mall/categories
- 商品详情：GET /mall/products/{id}
- 购买：POST /mall/purchase
- FAQ：GET /mall/faqs
- 客服配置：GET /system/config

注意事项：
- 货源库标题 50 字符、正文 5000 字符、备注 200 字符硬限制
- 卡密发货文本必须包含 {卡密占位} 占位符
- 商城货源固定文本模式，不可改为卡密
- 卡密库存低于 alertThreshold（默认 10）会预警
- 卡密批量导入支持三种格式（每行一条/卡号----密码/卡号,密码）
- 卡密可锁定（不可领取）、作废（异常状态）、重置（恢复未使用）
- 货源库支持 AI 一键匹配适配商品（POST /auto-delivery/sources/{id}/recommend）',
'delivery_source,template,模板,mall,商城,购买,variables', 96, 1, 2, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='delivery_source' AND title='发货模板与商城');

-- ============================================================
-- 9. workflow 工作流（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'workflow', '工作流节点类型与配置',
'工作流是一系列节点的有向图组合，用于自动化商品运营流程（获取→筛选→润色→生图→发布）。

节点类型（nodeTypes）：

1. TRIGGER（触发器）
   - 工作流入口，定义触发方式
   - 触发方式：manual（手动）/ scheduled（定时）/ event（事件）

2. PRODUCT_FETCH（商品获取）
   - 获取方式：keyword（商品搜索）/ shop（店铺搜索）
   - 店铺搜索：粘贴闲鱼店铺链接（https://www.goofish.com/personal?userId=...）
   - 关键词：输入框 + 回车/逗号添加
   - AI 关键词提取：粘贴品类表/商品列表/想法描述，AI 自动提取关键词
   - 获取模式：random（随机）/ top（按热度）/ newest（按最新）

3. PRODUCT_FILTER（商品筛选）
   - 筛选条件：自然语言描述（如"只保留价格低于100元、标题中包含iPhone、成色较新、描述完整的商品"）
   - 未配置时：跳过筛选节点
   - 失败处理：retry（回到获取节点重新获取）/ skip（跳过当前商品继续）/ terminate（终止工作流）
   - 最大重试次数：1-20

4. PRODUCT_POLISH（润色节点）
   - 润色风格：口语化 / 简洁 / 吸引眼球 / 自定义
   - 自定义提示词：自由输入润色要求
   - 默认提示词：请根据商品的标题和正文，生成适合闲鱼平台的商品标题和描述

5. IMAGE_GENERATE（生图节点）
   - 并行数量：1（顺序执行）/ 3（默认）/ 其他
   - 图片尺寸：默认 1024x1024
   - 模型选择：从已启用且完成配置的生图模型列表选择
   - 提示词模式：default（默认）/ custom（自定义）
   - 自定义提示词：支持 {{TITLE}} 和 {{CONTENT}} 占位符
   - 参考图片：referenceImages 数组
   - 默认提示词：生成1张适合闲鱼/淘宝风格的中国电商商品主图（1:1正方形）...

6. PUBLISH（发布节点）
   - 发布账号由触发器节点提供（自动获取）',
'workflow,node,节点,trigger,fetch,filter,polish,image,publish', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='workflow' AND title='工作流节点类型与配置');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'workflow', '工作流操作与执行 API',
'工作流操作 API：

定义管理：
- GET /workflow/overview（概览）
- GET /workflow/definitions（列表，分页）
- GET /workflow/definitions/{id}（详情）
- POST /workflow/definitions（创建）
- PUT /workflow/definitions/{id}（更新）
- DELETE /workflow/definitions/{id}（删除）
- POST /workflow/definitions/{id}/publish（发布，发布后可执行）

执行管理：
- POST /workflow/definitions/{id}/execute（执行，超时 180 秒）
- GET /workflow/executions（执行历史）
- GET /workflow/executions/{id}（执行详情）
- POST /workflow/executions/{id}/terminate（终止执行）
- POST /workflow/executions/{id}/retry-failed-node（重试失败节点）
- POST /workflow/executions/{id}/continue（继续执行，复用原 execution_id，跳过已成功节点）
- GET /workflow/executions/{id}/logs（执行日志）
- GET /workflow/recent-runs（最近运行）

版本管理：
- GET /workflow/definitions/{id}/versions（版本列表）
- POST /workflow/definitions/{id}/rollback（回滚版本，body: {version}）

AI 能力接口：
- POST /workflow/ai/screen（AI 筛选商品）
- POST /workflow/ai/rewrite（AI 改写商品，扣费场景 workflow_rewrite）
- POST /workflow/ai/generate-images（AI 生成图片）
- POST /workflow/ai/extract-keywords（AI 提取关键词）

工作流发布商品：
- POST /workflow/publish（发布商品到闲鱼）

商品草稿箱：
- GET /workflow/drafts（列表）
- GET /workflow/drafts/stats（统计）
- GET /workflow/drafts/{draftId}（详情）
- POST /workflow/drafts/{draftId}/retry-publish（重试发布，body: {accountId?}）
- POST /workflow/drafts/batch-retry-publish（批量重试，body: {ids, accountId?}）
- DELETE /workflow/drafts/{draftId}（删除草稿）

注意事项：
- 工作流必须先"发布"才能"执行"
- 执行超时 180 秒
- 失败节点可单独重试，或继续执行跳过已成功节点
- 润色节点调用前需校验 Token 余额（ensureAiTokenBalance()）
- 工作流全局地址预检：点击运行测试时若三级查找均失败则弹出地址选择对话框
- 画布支持缩放（50%-160%，步进 10%）
- 节点支持拖拽、连线',
'workflow,api,接口,execute,执行,publish,版本,version,drafts', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='workflow' AND title='工作流操作与执行 API');

-- ============================================================
-- 10. scheduled_task 定时任务（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'scheduled_task', '任务类型与 Cron 生成规则',
'仅以下 5 种类型可在创建下拉中选择：

1. sync_goods（同步商品）
   - 调度模式：daily
   - 说明：每日指定时间同步商品
   - Cron 模式：0 mm HH * * ?
   - 示例：每日 09:30 → 0 30 9 * * ?

2. sync_orders（同步订单）
   - 调度模式：daily
   - 说明：每日指定时间同步订单
   - Cron 模式：0 mm HH * * ?
   - 示例：每日 23:00 → 0 0 23 * * ?

3. auto_redelivery（自动补发订单）
   - 调度模式：interval
   - 说明：间隔 N 分钟执行
   - 限制：最低 10 分钟
   - Cron 模式：0 */N * * * ?
   - 示例：每 15 分钟 → 0 */15 * * * ?

4. one_click_polish（一键擦亮商品）
   - 调度模式：daily
   - 说明：每日指定时间擦亮
   - Cron 模式：0 mm HH * * ?
   - 示例：每日 08:00 → 0 0 8 * * ?

5. workflow（执行工作流）
   - 调度模式：daily_or_weekly
   - 说明：每日或每周指定日执行
   - daily Cron：0 mm HH * * ?
   - weekly Cron：0 mm HH ? * DOW
   - 示例：每周一 09:00 → 0 0 9 ? * 1

时间解析：
- HH：0-23
- mm：0-59
- 超界自动钳制

历史类型（仅展示，不在创建下拉中）：
sync_delivery_status、redelivery、polish_goods、auto_delivery、sync_account、auto_reply 等

重要：Cron 表达式由前端自动生成，用户无需手填',
'scheduled_task,type,类型,cron,表达式,生成,daily,interval,weekly', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='scheduled_task' AND title='任务类型与 Cron 生成规则');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'scheduled_task', '定时任务字段与 API',
'定时任务字段说明：

必填字段：
- taskName：任务名称（如"每日同步商品"）
- taskType：必选，5 种类型之一

条件必填：
- accountIds：账号 ID 数组（多选，工作流任务不需要）
- dailyTime：HH:mm（每日运行时间，daily 模式必填）
- intervalMinutes：最少 10（间隔分钟数，interval 模式必填）
- workflowId：工作流 ID（工作流任务必填）
- scheduleMode：daily / weekly（调度模式，工作流任务）
- workflowTime：HH:mm（工作流运行时间）
- weekdays：1-7（每周运行日，weekly 模式必选，至少一个）

可选字段：
- enabled：0/1（启用状态）

定时任务 API：
- GET /scheduled-tasks（列表）
- POST /scheduled-tasks（创建）
- PUT /scheduled-tasks/{id}（更新）
- DELETE /scheduled-tasks/{id}（删除）
- POST /scheduled-tasks/{id}/run（立即执行）
- PATCH /scheduled-tasks/{id}/enabled（启用/禁用，body: {enabled: 1/0}）

注意事项：
- 工作流任务不需要选择账号（使用工作流自带的账号配置）
- weekly 模式至少选择一个运行日，否则提示"每周模式下请至少选择一个运行日"
- intervalMinutes 最低 10 分钟，低于 10 自动钳制为 10
- Cron 表达式由前端自动生成，无需用户手填',
'scheduled_task,字段,api,接口,create,update,delete,run,enabled', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='scheduled_task' AND title='定时任务字段与 API');

-- ============================================================
-- 11. ai_customer_service AI 客服（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'ai_customer_service', 'AI 客服工作模式与配置',
'AI 客服"小梦"工作模式配置（AiCsSettings.vue）：

启用与时段：
- 启用 AI 自动回复（总开关）：关闭后所有自动回复失效
- 24 小时全天在线：关闭后按工作时段回复，工作时段外转人工
- 工作时段：workStart 至 workEnd（HH:mm，仅当不开启 24 小时时显示）
- 接待模式：auto（全自动）/ hybrid（混合模式）/ manual（仅人工）
- 回复延时（秒）：0-120，建议 5-15 秒，过短易被风控识别
- 携带对话上下文：读取最近 10 条历史消息
- 人工干预自动暂停：人工接管后 AI 自动暂停该会话

客服角色与人设：
- 客服人设：文本（如"专业客服"）
- 回复语气：friendly（友好亲切）/ professional（专业严谨）/ casual（轻松活泼）
- 回复语言：zh-CN（简体中文）/ en（English）
- 系统提示词：长文本（4 行），定义 AI 角色、店铺信息、商品特色、回复边界，支持"恢复默认"
- 欢迎语：文本（2 行），新会话进入时自动发送，支持"恢复默认"

安全与会话策略：
- 启用安全模式：检测敏感词或高风险场景自动转人工
- 转人工关键词：用 、 分隔（如"退款、投诉、维权"）
- 会话黑名单关键词：用 、 分隔（命中后 AI 不回复，如"低价、加微"）
- 转人工阈值（分）：0-100，AI 置信度低于此分数时转人工
- 会话超时（分钟）：1-120
- 每日最大回复数：1-10000，超出后自动转人工

业务配置 API：
- GET /business-settings/{category}（读取，4 类：ai-customer-service、message-settings、delivery-settings、product-op-settings）
- POST /business-settings/{category}（保存）
- GET /business-settings/ai-customer-service/defaults（默认值）
- POST /business-settings/ai-customer-service/test（测试回复，body: {message}）
- POST /business-settings/ai-customer-service/upload-knowledge（上传知识库文件，超时 120 秒）',
'ai_customer_service,config,配置,模式,时段,人设,安全,转人工', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='ai_customer_service' AND title='AI 客服工作模式与配置');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'ai_customer_service', '知识库管理与优先级',
'知识库管理：

自定义知识库：
- 上传文件：支持 .md、.txt、.pptx、.xlsx、.csv，由 AI 提取回复规则
- 手动新增：填写名称 + 内容
- 字段：name（名称）、content（内容）、source（upload/manual）
- 优先级：自定义知识库优先于默认知识库，AI 先读用户知识库再读默认知识库

系统默认知识库：
- 只读展示，用户可折叠查看
- 自动生效（自定义知识库为空时）

聊天规则：
- 自定义规则：name + content
- 示例：只能回答商品本身，不要主动延展售后承诺
- 优先级：自定义规则优先于默认规则
- 系统默认规则只读展示

知识库学习页（KnowledgeBaseSettings）：
- 平台学习知识库（只读）：AI 每天自动学习海量真实对话
  * 按分类筛选
  * 关键词搜索
  * 批量启用绑定
- 用户私有知识库：
  * title（必填）、content（必填，支持 Markdown）、category（可选）、tags（可选）

知识库 API：
- GET /api/ai-cs/kb/learned（平台学习 KB 列表）
- GET /api/ai-cs/kb/learned/{id}（详情）
- GET /api/ai-cs/kb/categories（分类列表）
- GET /api/ai-cs/kb/user-kb（用户私有 KB 列表）
- POST /api/ai-cs/kb/user-kb（创建私有 KB）
- PUT /api/ai-cs/kb/user-kb/{id}（更新）
- DELETE /api/ai-cs/kb/user-kb/{id}（删除）
- GET /api/ai-cs/kb/bindings（绑定关系）
- POST /api/ai-cs/kb/bindings（绑定，body: {items}）
- DELETE /api/ai-cs/kb/bindings（解绑，query: {kbType, kbId}）',
'ai_customer_service,knowledge,知识库,规则,rule,学习,learned,绑定', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='ai_customer_service' AND title='知识库管理与优先级');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'ai_customer_service', 'AI 客服会话与 SSE 流式聊天',
'AI 客服会话 API：
- POST /ai-cs/session/create（创建会话，自动关闭已有活跃会话）
- GET /ai-cs/session/current（当前会话）
- POST /ai-cs/session/close（关闭会话，body: {sessionId}）
- GET /ai-cs/messages（历史消息，query: {sessionId, limit 默认 100}）
- GET /ai-cs/config（客服配置 + Token 余额）
- PUT /ai-cs/billing-config（保存计费配置）
- POST /ai-cs/compress（上下文压缩，不扣费，body: {sessionId}）
- POST /ai-cs/tool/confirm（工具调用确认，body: {sessionId, toolCallId, accept}）

SSE 流式聊天：
- 接口：POST /ai-cs/chat（fetch 直连，不走 axios）
- body: {sessionId, message}

SSE 事件类型：
- delta：增量内容（流式输出文本）
- tool_call：工具调用请求（AI 请求执行工具）
- tool_result：工具执行结果
- insufficient_balance：余额不足
- context_exceeded：上下文超限
- casual_remind：闲聊提醒
- done：流结束（含 tokensCharged 字段）
- error：错误

计费与每日额度：
- 用户每日免费额度（条）：0-1000，0 表示无免费额度
- 每条消息扣费 Token 数：1-100，默认 3
- 上下文消息上限（条）：10-200，超出后提示新建会话或压缩上下文（压缩不扣费）
- 启用计费：关闭后所有客服消息均不扣费（仅调试用途）

注意事项：
- AI 客服主开关关闭后，所有自动回复失效
- 自定义知识库优先于默认知识库
- 转人工关键词用 、 分隔
- 测试 AI 客服回复会扣费（场景 rag_chat / auto_reply），需先校验 Token 余额
- SSE 接口 401 不调用 clearAuth（避免误踢出登录）
- 上下文压缩不扣费
- 面板切换路由时自动以动画方式收起，历史消息保留',
'ai_customer_service,session,sse,stream,chat,事件,计费,compress,tool', 96, 1, 16, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='ai_customer_service' AND title='AI 客服会话与 SSE 流式聊天');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'ai_customer_service', 'AI 客服工具调用能力',
'AI 客服"小梦"具备工具调用能力，可帮助用户执行权限内操作。

工具调用协议：
- AI 在回复中包含 ```tool_call 代码块，内含 JSON
- 格式：{"tool": "工具名", "arguments": {"参数名": "参数值"}}
- 用户确认后执行

工具调用规则：
- 一次只能调用一个工具
- 工具调用需用户确认后才会执行
- 调用工具前先用自然语言说明你将要做什么
- 工具返回结果后，用自然语言总结结果
- 查询类工具可直接调用
- 写操作（创建/修改/删除）需先向用户确认意图
- 涉及资金操作（如同意退款）不得通过工具调用，必须引导用户手动处理

可用工具列表（22 个）：

账号与商品：
- list_accounts()：列出闲鱼账号
- get_account_status(accountId)：查询账号运行时状态
- get_account_summary()：账号汇总统计
- list_products(accountId, limit?)：列出商品
- get_goods_detail(goodsId)：商品详情

订单与发货：
- list_orders(accountId?, status?, limit?)：订单列表
- list_delivery_records(accountId?, status?, limit?)：发货记录
- retry_delivery_record(recordId)：重试失败发货

卡密与工作流：
- list_card_groups()：卡密分组列表
- list_workflows(limit?)：工作流列表
- list_scheduled_tasks()：定时任务列表
- list_auto_reply_rules(accountId?, limit?)：自动回复规则

数据面板与余额：
- get_token_balance()：Token 余额
- get_dashboard_summary()：数据面板汇总

创建类：
- create_qr_login()：创建扫码登录会话
- create_auto_reply_rule(accountId, ruleName, matchType, matchKeywords, replyContent)：创建自动回复规则
- create_delivery_rule(accountId, ruleName, goodsId, deliveryMode, cardGroupId?, deliveryContent?, triggerOnPay?, triggerKeyword?)：创建发货规则
- create_card_group(groupName, groupType?, remark?)：创建卡密分组
- create_workflow(name, description?, triggerType?)：创建工作流
- create_scheduled_task(accountId, taskType, cronExpr, taskName?)：创建定时任务
- polish_product_title(goodsId)：润色商品标题（按次计费）

切换类：
- toggle_scheduled_task(taskId, enabled)：启用/禁用定时任务
- toggle_auto_reply_rule(ruleId, enabled)：启用/禁用自动回复规则',
'ai_customer_service,tool,工具,调用,list,create,toggle,confirm', 96, 1, 17, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='ai_customer_service' AND title='AI 客服工具调用能力');

-- ============================================================
-- 12. opportunity 商机发掘（新增分类）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'opportunity', '商品关键词搜索三种模式',
'商机发掘（OpportunityPage.vue）支持三种搜索模式（mode 参数）：

1. auto（智能模式，默认）
   - 实现方式：先快速搜索，失败自动降级到慢速搜索
   - 平均耗时：~2-3 秒
   - 稳定性：最高
   - 返回结果含 searchMode 字段标识实际使用的搜索方式（fast 或 slow）

2. fast（快速搜索）
   - 实现方式：直调闲鱼 MTOP API（不经浏览器）
   - 平均耗时：~1 秒
   - 稳定性：低（可能触发 Baxia 风控）
   - 不降级，失败直接抛错

3. slow（慢速搜索）
   - 实现方式：Playwright 浏览器拦截 MTOP 响应
   - 平均耗时：~2-3 秒
   - 稳定性：高（浏览器自动处理反爬令牌）

操作步骤：
1. 选择模式：商品/店铺
2. 选择搜索方式（仅商品模式）：智能/快速/慢速
3. 输入关键词（如 iPhone 15、露营车、二手相机）
4. 点击"开始搜索"

接口：
- API：GET /goofish/search?q=&page=&pageSize=&mode=&accountId=
- 超时：180 秒（慢速搜索可能触发 Baxia 风控，由 crawler-service 委托 Python patchright 求解滑块，实测需要 120-150 秒）
- 分页：page（默认 1）、pageSize（默认 20）
- 可选 accountId：指定使用哪个闲鱼账号的 Cookie/_m_h5_tk

风控检测：
快速搜索触发以下错误时，auto 模式自动降级到慢速搜索：
- FAIL_SYS_USER_VALIDATE（Baxia 验证）
- RGV587_ERROR（风控拦截）
- _m_h5_tk 过期（Token 失效）

重要约束（不得更改）：
- 不得用固定 waitForTimeout 替代 Promise.race 事件驱动
- 不得删除 SEARCH_API_MARKER 精确匹配逻辑
- 不得删除 Cookie 注入逻辑
- 不得更改 MTOP API 端点（mtop.taobao.idlemtopsearch.pc.search）
- 不得删除 Baxia 风控检测
- 源码与编译产物必须同步（src/crawler/goofishSearch.ts 与 dist/crawler/goofishSearch.js）',
'opportunity,search,搜索,mode,fast,slow,auto,风控,baxia', 96, 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='opportunity' AND title='商品关键词搜索三种模式');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'opportunity', '店铺搜索与标题改写',
'店铺链接搜索：
- 操作步骤：
  1. 切换到"店铺"模式
  2. 粘贴闲鱼店铺链接（如 https://www.goofish.com/personal?userId=...）
  3. 点击"开始抓取"
  4. 异步抓取，支持"一键采集全部"

接口：
- 提交抓取：POST /crawler/import/goofish（body: {url}，返回 jobId）
- 查询状态：GET /crawler/crawl-jobs/{jobId}
- 获取商品：GET /crawler/goofish/stores/{userId}/items

重要约束：
- 店铺链接搜索功能实现不得影响现有的商品关键词搜索
- 店铺商品爬取必须通过浏览器进行，不可使用 API 接口

标题改写功能：
- 入口：搜索结果中选中商品 → "AI 商品改写"
- 改写风格：
  * friendly：口语化风格
  * concise：简洁风格
  * click：吸引眼球风格
  * custom：自定义风格（自定义提示词，最少 100px 高度）
- 改写结果：
  * 标题：最长 30 字符（maxlength=30，实时计数）
  * 正文：长文本域
  * 标签：tags 数组
  * 安全检查：safety.blocked + safety.message
- 接口：POST /opportunity/rewrite
- 扣费：调用前 ensureAiTokenBalance() 校验余额，场景 opportunity_rewrite，按 VIP 等级扣费

AI 生图（商机发掘集成）：
- 提示词模式：default / custom
- 自定义提示词：支持 {{TITLE}} 和 {{CONTENT}} 占位符
- 模型选择：从已启用生图模型列表选择
- 图片数量：可选 1-N
- 接口：
  * 生图：POST /opportunity/generate-images（超时 240 秒，后端 200 秒轮询窗口）
  * 模型列表：GET /opportunity/image-models
  * 历史列表：GET /opportunity/image-history
  * 历史详情：GET /opportunity/image-history/{requestId}
  * 恢复图片：POST /opportunity/image-recover/{historyId}

商机分析：
- 接口：POST /opportunity/analyze
- 历史记录：GET /opportunity/history
- 草稿列表：GET /opportunity/drafts
- 草稿详情：GET /opportunity/drafts/{id}
- AI 状态：GET /opportunity/ai-status、GET /opportunity/image-status',
'opportunity,shop,店铺,rewrite,改写,生图,generate,analyze', 96, 1, 2, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='opportunity' AND title='店铺搜索与标题改写');

-- ============================================================
-- 13. membership 会员与计费（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'membership', '会员等级与 Token 扣费规则',
'会员等级：

| 等级 | vip_level | 说明 |
|------|-----------|------|
| 普通 | 0 | 默认等级 |
| VIP | 1 | 解锁更多高效功能 |
| SVP（SVIP） | 2 | 最高等级，享受所有权益 |

Token 余额查询：
- GET /ai-billing/balance（余额查询）
- GET /profile/overview（个人概览，含 tokenBalance 和 tokenYuanValue）
  * tokenBalance：Token 余额
  * tokenYuanValue：≈ ¥（balance / 100）
- GET /profile/token-trend（Token 趋势）
- GET /profile/token-ledger（Token 流水，分页）
- GET /profile/recharge-records（充值记录）

Token 扣费规则（重要）：
通用模型（model-config-general）强制按次计费，扣费数量按 VIP 等级差异化：

| 等级 | 默认扣费 | 可调整范围 |
|------|---------|-----------|
| 普通（vip_level=0） | 3 Token | 管理员可调整 |
| VIP（vip_level=1） | 3 Token | 默认可改为 2 |
| SVP（vip_level=2） | 3 Token | 默认可改为 1 |

扣费优先级：
1. ai_model_tier_price.tokens_per_call（按 vip_level 查询）
2. ai_model_price_config.tokens_per_call（回退）
3. 代码层默认值 3L（再回退）

扣费公式：
chargeTokens = perCallPrice × tokenExchangeRate
            = 0.03 × 100 = 3 Token（默认配置）

- imageCount 对文本调用默认为 1
- tokensPerCall 未配置时不走固定销售价模式，由 costYuan × exchangeRate 计算

Token 余额校验（重要）：
- 所有主动调用通用模型的场景，必须先调用 ensureAiTokenBalance() 校验 Token 余额
- 余额 ≤ 0 时弹出"Token 余额为 0，请先充值 Token 后再使用 AI 功能"提示并返回 false
- 查询失败时不阻断（由后端 precheck 402 兜底）

已接入的页面：
- ProductPublishPage.vue → aiDesc()
- OpportunityPage.vue → rewriteSelected()
- WorkflowPage.vue → testPolish()
- settings/AiCsSettings.vue → runTest()',
'membership,vip,svp,token,扣费,balance,余额,等级,计费', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='membership' AND title='会员等级与 Token 扣费规则');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'membership', '充值流程与套餐升级',
'充值流程：
- 充值方式：GET /payment/methods
- 充值套餐：GET /payment/token-plans
- 创建订单：POST /payment/orders
- 查询订单：GET /payment/orders/{orderNo}
- 关闭订单：POST /payment/orders/{orderNo}/close
- 模拟支付（沙箱）：POST /payment/orders/{orderNo}/mock-pay
- 强制标记已支付（管理员）：POST /admin-api/payment/orders/{orderNo}/force-paid

Token 有效期：365 天
Token 套餐：购买后立刻到账

套餐升级：
- 套餐列表：GET /billing/plans
- 周期选项：月度 / 季度 / 年度（按后台配置）
- 促销活动：
  * 活动标签、原价划线、立省金额、折扣率
  * 名额限制：剩余份数、已售份数、进度条
  * 倒计时
- 会员等级功能对比：普通/VIP/SVIP 三档对比，✓ 表示可用，— 表示不可用
- 数据来源：后台「系统运维 → 功能管理」配置
- 当前活动：GET /promotion/active
- 活动预览：GET /promotion/preview（query: {planId, periodType}）

API 凭证管理（滑块求解 API）：
- 能力范围：仅处理 WS 掉线引起的滑块问题，Cookie 失效不能通过该能力解决
- 扣费保证：仅对成功求解的滑块任务扣除 Token，失败/预检测未通过/超时/服务不可用一律不扣费
- 获取凭证：GET /api-integration/credential
- 重置密钥：POST /api-integration/credential/reset（旧密钥失效）
- 概览：GET /api-integration/overview
- 调用记录：GET /api-integration/records
- 统计：GET /api-integration/stats
- 客服微信：JiShu0724

注意事项：
- Token 余额为 0 时阻止调用 AI 功能
- 滑块求解 API 仅处理 WS 掉线引起的滑块，Cookie 失效需重新扫码
- 重置 API 密钥后旧密钥立即失效
- Token 套餐有效期 365 天
- 通用模型强制按次计费，不可改回按 Token 量计费',
'membership,payment,充值,order,套餐,plan,promotion,活动,api-integration', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='membership' AND title='充值流程与套餐升级');

-- ============================================================
-- 14. data_panel 数据面板（新增分类）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'data_panel', '数据指标含义与 API',
'数据面板（DataPage.vue）：

数据指标含义：
- 今日订单：todayOrderCount / orderCount（今日新增订单数）
- 发货成功：deliverySuccessCount（成功率 = success / (success + fail)）
- 发货失败：deliveryFailCount（需处理）
- 待发货：pendingDeliveryCount（排队中）
- AI 回复：autoReplyCount / aiReplyCount（今日命中次数）
- 今日销售额：todaySalesAmount（订单金额合计）
- 商品总数：goodsCount（在售 sellingGoodsCount + 已售 totalSoldCount）
- 账号数：accountCount
- 消息数：messageCount

趋势数据：
- 业务趋势：近 N 天多维度走势（7/14/30 天可选）
  * 订单数、消息数、发货数、发货成功、发货失败、AI 回复数
- 发货分布：饼图展示发货成功/失败/待发货占比
- 核心指标对比：柱状图
- 运营概览：商品在售率等
- 趋势明细表格：按日展示各项业务指标，支持导出 CSV

数据更新频率：
- 汇总数据：POST /data-panel/stats（参数 days、accountId）
- 趋势数据：POST /data-panel/trend
- 实时事件：通过 SSE 推送（订单、发货、AI 回复等实时事件）

数据面板 API：
- GET /dashboard/summary（仪表盘汇总）
- GET /dashboard/sales-trend（销售趋势）
- GET /dashboard/order-message-trend（订单消息趋势）
- GET /dashboard/account-health（账号健康度）
- GET /dashboard/recent-logs（最近操作日志，query: {limit}）
- POST /data-panel/stats（数据面板统计）
- POST /data-panel/trend（数据面板趋势）

导航 API：
- GET /navigation/home（首页导航，持久化缓存）
- GET /navigation/overview（导航概览）
- GET /navigation/notifications（导航通知）
- GET /navigation/system-status（系统状态）

注意事项：
- 趋势范围可选 7/14/30 天
- 实时事件依赖 SSE 连接，连接状态会展示
- SSE 未连接时提示"当前未确认实时连接可用，请以各业务列表中的服务端数据为准"
- 支持导出趋势明细 CSV',
'data_panel,指标,趋势,trend,stats,summary,sse,实时', 96, 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='data_panel' AND title='数据指标含义与 API');

-- ============================================================
-- 15. messages 在线消息（新增分类）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'messages', '在线消息与会话管理',
'在线消息（MessagesPage.vue）：

消息 API：
- POST /msg/list（消息列表）
- POST /msg/context（消息上下文）
- GET /msg/online/conversations（在线会话，cursor 真分页，query: {xianyuAccountId, cursor, pageSize}）
- POST /msg/avatars（批量查询用户头像，body: {accountId, queries}）
- 语音消息 URL：/msg/audio/{messageId}

会话管理 API：
- GET /conversations（会话列表）
- GET /conversations/{id}/messages（会话消息）
- PATCH /conversations/{id}/status（更新会话状态）
- PATCH /conversations/{id}/read（标记会话已读）

WebSocket 操作 API：
- POST /websocket/start（启动 WS 监听，超时 180s，body: {accountId, ...}）
- POST /websocket/stop（停止 WS，body: {accountId}）
- POST /websocket/status（查询 WS 状态，body: {accountId}）
- POST /websocket/sendMessage（发送文本消息）
- POST /websocket/sendImageMessage（发送图片消息）
- POST /websocket/updateCookie（更新 Cookie）
- POST /websocket/updateToken（更新 Token）
- POST /websocket/refreshToken（刷新 Token，body: {accountId}）
- POST /websocket/passwordLogin（密码登录闲鱼，超时 300s，body: {accountId}）
- POST /websocket/clearCaptchaWait（清除验证码等待）
- POST /websocket/retryAutoCaptcha（重试自动验证码）
- POST /websocket/confirmManualVerification（确认人工验证）
- GET /websocket/pendingManualVerification（待处理人工验证）
- POST /websocket/checkLogin（检查登录状态）

会话级自动回复控制：
- POST /auto-reply-scope/conversation-toggle（body: {accountId, sid, peerUserId, enabled}）
- GET /auto-reply-scope/conversation-status（会话级状态）

使用场景：
- 卖家可在消息页对特定会话手动关闭 AI 自动回复
- 关闭后该会话由人工接管，AI 不再自动回复
- 重新开启后恢复 AI 自动回复',
'messages,消息,会话,conversation,websocket,ws,在线,语音', 96, 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='messages' AND title='在线消息与会话管理');

-- ============================================================
-- 16. troubleshoot 故障排查（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'troubleshoot', '账号异常排查指南',
'账号异常排查：

1. Cookie 失效
- 现象：Cookie 状态为 0（失效）
- 原因：Cookie 过期或被闲鱼平台清除
- 处理：必须重新扫码或更新 Cookie，滑块求解无法恢复
- 接口：POST /qrlogin/generate（扫码）/ POST /xianyu/accounts/{id}/cookie（更新 Cookie）

2. WS 掉线
- 现象：在线状态为离线
- 原因：网络波动或服务重启
- 处理：点击"连接 WS"重新建立
- 接口：POST /websocket/start

3. 滑块求解失败
- 现象：WS Token 获取失败 / 滑块求解失败
- 原因：闲鱼平台风控触发滑块验证，系统自动求解失败
- 处理：
  * 点击"重试求解"
  * 多次失败建议手动完成验证
  * 在闲鱼 APP 中验证可解除风控
- 限制：每分钟最多 1 次主动求解，失败后"重试求解"不受冷却限制

4. 多账号同时掉线
- 现象：多个账号同时离线
- 原因：IP 被风控或网络故障
- 处理：
  * 检查 IP 是否被风控
  * 更换网络环境
  * 联系管理员

5. 消息不同步
- 现象：在线消息页无新消息
- 原因：WS 连接断开
- 处理：检查 WS 连接状态，必要时重启 WS
- 接口：POST /websocket/status

6. 账号不活跃/已禁用
- 现象：账号状态显示不活跃或已禁用
- 原因：超过 3 天未操作或被管理员禁用
- 处理：手动连接账号或联系管理员启用

7. 人脸验证
- 现象：闲鱼平台要求人脸验证
- 处理：在闲鱼 APP 中完成人脸验证
- 接口：GET /xianyu/accounts/face-verifications（查询）/ POST /xianyu/accounts/face-verifications/{id}/read（标记已读）',
'troubleshoot,cookie,ws,滑块,掉线,风控,不活跃,人脸', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='troubleshoot' AND title='账号异常排查指南');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'troubleshoot', 'AI 功能与计费异常排查',
'AI 功能异常排查：

1. Token 余额为 0
- 现象：调用 AI 功能提示"Token 余额为 0，请先充值 Token 后再使用 AI 功能"
- 处理：充值 Token
- 接口：GET /ai-billing/balance（查询余额）

2. AI 调用失败
- 现象：AI 生成描述、改写、生图等功能失败
- 排查：
  * 检查 Token 余额是否充足
  * 检查 AI 服务商配置（管理后台「AI 管理 → 模型配置」）
  * 检查网络连接
  * 查看后端日志

3. AI 客服不回复
- 现象：买家消息无 AI 自动回复
- 排查：
  * 检查 AI 客服主开关是否开启
  * 检查账号/商品作用域是否启用自动回复
  * 检查工作时段设置（若非 24 小时在线）
  * 检查 Token 余额
  * 检查 AI 客服配置是否可用

4. AI 客服回复质量差
- 排查：
  * 补充自定义知识库内容
  * 调整系统提示词
  * 完善聊天规则
  * 上传知识库文件（.md、.txt、.pptx、.xlsx、.csv）

5. SSE 连接失败
- 现象：AI 客服聊天无法收到回复
- 排查：
  * 检查网络连接
  * 检查登录状态（SSE 401 不清除 token，但需重新登录）
  * 查看浏览器控制台错误

6. 上下文超限
- 现象：AI 客服提示上下文超限
- 处理：新建会话或压缩上下文（压缩不扣费）
- 接口：POST /ai-cs/compress

7. 工作流执行失败
- 现象：工作流节点执行失败
- 处理：
  * 查看执行日志（GET /workflow/executions/{id}/logs）
  * 重试失败节点（POST /workflow/executions/{id}/retry-failed-node）
  * 继续执行跳过已成功节点（POST /workflow/executions/{id}/continue）
  * 检查 Token 余额（润色、生图节点需扣费）

8. 搜索功能异常
- 现象：商品关键词搜索失败
- 排查：
  * 快速搜索触发风控时，auto 模式会自动降级到慢速搜索
  * 慢速搜索超时 180 秒（包含滑块求解时间）
  * 检查账号 Cookie 是否有效
  * 检查 crawler-service 是否运行',
'troubleshoot,ai,token,余额,客服,sse,工作流,搜索,失败', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='troubleshoot' AND title='AI 功能与计费异常排查');

-- ============================================================
-- 17. faq 常见问题（深度补充）
-- ============================================================
INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'faq', '账号与登录常见问题',
'Q: 如何添加闲鱼账号？
A: 在账号管理页面点击"添加账号"，选择三种方式之一：
1. 扫码登录（推荐）：生成二维码，用闲鱼 App 扫码
2. Cookie 手动导入：从浏览器 F12 复制 Cookie，必须包含 unb 字段
3. 更新已有账号 Cookie：粘贴新 Cookie，系统会做身份校验防串号

Q: Cookie 失效怎么办？
A: Cookie 失效（状态为 0）必须重新扫码或更新 Cookie，滑块求解无法恢复。
- 扫码：POST /qrlogin/generate
- 更新 Cookie：POST /xianyu/accounts/{id}/cookie

Q: 为什么账号显示离线？
A: WS 连接断开，点击"连接 WS"重新建立。若多次掉线，检查网络或 IP 是否被风控。

Q: 滑块求解失败怎么办？
A: 点击"重试求解"，多次失败建议在闲鱼 APP 中完成验证。每分钟最多 1 次主动求解，失败后"重试求解"不受冷却限制。

Q: 如何刷新账号资料？
A: 在账号列表点"刷新资料"（POST /xianyu/accounts/{id}/refresh-profile），拉取闲鱼主页资料（粉丝、已售、评价等）。

Q: 忘记密码怎么办？
A: 在登录页点击"忘记密码"，通过邮箱验证码重置密码（POST /login/resetPassword）。

Q: 如何修改密码？
A: 个人中心 → 账号安全 → 修改密码（POST /profile/change-password）。

Q: 滑块求解 API 是什么？
A: 仅处理 WS 掉线引起的滑块问题，对外提供 API 能力。Cookie 失效不能通过该能力解决。仅对成功求解的任务扣费。客服微信：JiShu0724',
'faq,账号,登录,cookie,扫码,滑块,密码,离线', 96, 1, 14, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='faq' AND title='账号与登录常见问题');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'faq', '商品与订单常见问题',
'Q: 如何发布商品？
A: 在商品管理页点击"发布商品"，填写：
- 闲鱼账号（必选）
- 宝贝标题（最长 30 字符）
- 宝贝描述
- 宝贝图片（最多 10 张，单张 ≤ 5MB，JPEG/PNG/GIF/WebP）
- 商品分类（三级级联，支持 AI 自动选择）
- 价格与库存
- 发货设置
支持 AI 生成描述（需 Token 余额）。

Q: 多规格商品怎么发布？
A: 多规格商品仅鱼小铺账号可用，最多 2 个规格类型，自动生成 SKU 笛卡尔积。

Q: 商品为什么不同步？
A: 检查账号 Cookie 是否失效。同步方向：闲鱼 → 本地（单向），本地修改不会回写到闲鱼。

Q: 如何同步闲鱼商品？
A: 商品管理页点击"同步闲鱼商品"按钮，支持多账号并行同步。前端轮询策略：500ms × 10 次，然后 2s 间隔。

Q: 订单状态有哪些？
A: 0=待付款，1=已付款，2=待发货，3=已发货，4=已完成，5=已关闭。今日订单金额仅统计 orderStatus IN (1,2,3,4) 且未删除订单。

Q: 如何手动发货？
A: 订单详情页"手动发货"，选择发货来源（custom/library）、发货时机（付款后/收货后/评价后）、发货方式（text/card）。

Q: 退款管理在哪里？
A: 退款管理仅鱼小铺账号支持。同意退款是资金操作，需二次确认。

Q: 评价管理在哪里？
A: 评价管理仅鱼小铺账号支持。可创建评价（POST /rates/create）或配置自动评价。

Q: 商品标题限制多少字？
A: 最长 30 字符（硬限制）。

Q: AI 生成描述会扣费吗？
A: 会。通用模型按次计费，扣费数量按 VIP 等级差异化（普通 3 / VIP 2 / SVP 1 Token，可配置）。调用前会校验 Token 余额。',
'faq,商品,发布,订单,发货,退款,评价,同步,标题', 96, 1, 15, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='faq' AND title='商品与订单常见问题');

INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time)
SELECT NULL, 'faq', '自动化与 AI 客服常见问题',
'Q: 自动回复怎么配置？
A: 本项目采用 AI 客服统一回复架构：
1. 在「AI 客服配置」页面配置话术、知识库、聊天规则
2. 在「自动回复」页面配置作用域（哪些账号/商品启用）
作用域优先级：商品级 > 账号级 > 全局默认

Q: AI 客服主开关关闭会怎样？
A: 所有自动回复失效。启用商品/账号自动回复时，若主开关未开，会同步开启（弹窗确认）。

Q: 自动发货怎么配置？
A: 在自动发货页面为每个商品配置 3 种时机的发货规则：
1. 付款后发货（系统定时扫描自动执行，默认每 10 分钟）
2. 确认收货后赠送（手动触发或事件自动化）
3. 好评后赠送（手动触发或事件自动化）
发货方式：text（文本）/ card（卡密）

Q: 卡密库存不足怎么办？
A: 卡密库存低于 alertThreshold（默认 10）会标红预警。库存为 0 时阻止发货。可在卡密仓库批量导入卡密。

Q: 工作流是什么？
A: 工作流是自动化商品运营流程（获取→筛选→润色→生图→发布）。必须先"发布"才能"执行"。执行超时 180 秒。

Q: 定时任务有哪些类型？
A: 5 种：sync_goods（同步商品）、sync_orders（同步订单）、auto_redelivery（自动补发，最低 10 分钟）、one_click_polish（一键擦亮）、workflow（执行工作流）。Cron 表达式由前端自动生成。

Q: AI 客服会扣费吗？
A: 每条成功回复扣费 Token 数（默认 3）。每日免费额度内免费，超出后按条扣费。上下文压缩不扣费。

Q: Token 余额怎么查？
A: 个人中心或 AI 客服面板顶部显示。接口：GET /ai-billing/balance

Q: Token 怎么充值？
A: 点击右上角余额或充值按钮。Token 套餐购买后立刻到账，有效期 365 天。

Q: 商机发掘支持哪些搜索？
A: 商品关键词搜索（fast/slow/auto 三种模式）和店铺链接搜索。auto 模式（默认）先快速搜索，失败降级到慢速搜索。

Q: 如何升级 VIP？
A: 访问 VIP 会员中心，选择套餐（月度/季度/年度），查看功能对比表后升级。',
'faq,自动回复,ai,客服,自动发货,工作流,定时任务,token,充值,搜索,vip', 96, 1, 16, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='faq' AND title='自动化与 AI 客服常见问题');
