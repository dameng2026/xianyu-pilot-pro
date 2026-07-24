# 更新日志

本文件记录 xianyu-assistant 商业版所有版本的功能变更与修复。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [2.0.0] - 2026-07-24

### ✨ 新增

#### API 滑块求解 SaaS 对外对接
- **对外 HTTP API**：商业版滑块求解能力以 SaaS API 形式对外开放，第三方系统（含开源版）可通过 `POST /api/v1/slider/solve` 调用，按成功次数计费 Token
- **X-Api-Key 鉴权**：独立 `ApikeyAuthFilter` + `ApikeyVerifier`，sha256 哈希存储，一租户一密钥；`UserJwtAuthFilter` 豁免 `/api/v1/slider/*`
- **独立并发槽位**：crawler-service `tryAcquireBrowserSlot` 分槽位，对外 API 不与前台用户求解抢占资源
- **独立记录表**：`xianyu_api_captcha_solve_record`（V1.33 + V1.17 迁移），与原 `xianyu_captcha_solve_record` 物理隔离
- **5 分钟对账定时任务**：`ApiSliderChargeReconcileJob` 校准漏单/多扣
- **前台双端管理页面**：PC 端 `ApiSliderSolvePage.vue` + 移动端 `MobileApiSliderSolve.vue`，支持凭证生成/重置、记录查询、统计概览、对接文档
- **后台管理页面**：admin-web `/admin/api-integration`，管理所有租户的 API 凭证与计费
- **默认价格**：`api-slider-solve` 模块 0.05 元/次，兑换比例 100，即 5 Token/次

#### 维护模式横幅
- 上线期间前台所有页面（PC 端、移动端、登录页）顶部显示"项目正在更新中"持久横幅
- 维护状态存于 Redis（key `xianyu:maintenance:enabled`），前端 60 秒轮询 `GET /api/maintenance/status`，路由切换立即刷新
- Redis 不可达时降级为未维护（不锁死前台）
- 部署操作方通过 `redis-cli` 切换；上线开始必须开启，上线结束（无论成功失败）必须关闭并验证

#### VIP 会员套餐多周期价格
- 套餐支持月/季/年三档价格（`price_month_cent` / `price_quarter_cent` / `price_year_cent`）
- 下单时订单记录 `period_type`（V1.30 迁移），支付成功后按周期推导会员有效期（月=30天，季=90天，年=365天）
- 历史订单 `period_type` 为 NULL 视为月度（兼容）

#### 滑块求解记录统计口径调整
- 成功率统计排除 `timeout`（超时）和 `precheck_rejected`（预检验拒绝）记录，避免不可重试场景污染成功率
- 后端 `selectKpi` / `selectTrend` / `selectAccountGroups` 通过 CASE WHEN 过滤指定状态与失败原因
- 前端管理端新增排除口径说明与徽标

#### crawler-service 进程监测机制
- 新增 `ProcessRegistry` + `ProcessMonitor`：每个求解会话（Python spawn 子进程 / Chrome launchPersistentContext）注册到 registry，记录 sessionId/kind/pid/userDataDir/deadlineAt
- 每 30 秒扫描清理超过 deadline+30s 的进程（SIGTERM → 5s → SIGKILL），已退出进程自动注销
- 安全策略：只清理注册表中的 PID，PID < 100 不清理（系统进程保护）
- 新增 `/api/health/processes` 端点（豁免 internal token）查看活跃会话与清理日志

#### 滑块求解排队位置原子化
- `captcha_queue.py` 的 `enqueue` 方法持锁原子加入 `_pending_tasks` 并直接返回排队位置
- 修复异步竞态：原方案广播 SSE 时 await 让出控制权，worker 协程被调度取出任务后，二次查询返回 (0, 0)

### ♻️ 优化

#### 卡密发货多层去重防护
- **60 秒窗口去重**：同一 `account_id + pnmId` 60 秒内只触发一次
- **会话 ID 归一化**：`_get_delivery_lock` 对 `s_id` 执行 `.replace("@goofish", "")`，确保同一会话不同消息格式获得同一把锁
- **内存级并发去重**：`_delivery_in_flight` set 防止同一会话+商品并发卡密认领
- **数据库去重查询**：`_has_existing_realtime_delivery` 持锁后二次检查
- **锁内事务提交**：`_process_delivery` 与 `_trigger_delivery_for_confirmed_statement` 锁内 `db.commit()`，确保新记录对后续查询可见，消除 TOCTOU 竞态与 MySQL REPEATABLE READ 事务快照问题
- **delivery_timing 兼容 NULL**：Check 2 SQL 条件兼容历史 NULL 记录

#### delivery_record 接收人信息持久化
- 补齐 `receiver_info` JSON 列（V1.32 迁移），存储 `{sid, pnmId, buyerUserId, xyGoodsId, buyerUserName}` 用于并发去重
- 新增 `(tenant_id, account_id, delivery_timing)` 复合索引加速去重查询

### 🐛 修复

#### delivery_record.order_id 溢出导致多单误判重复发货
- 闲鱼 orderId 为超长字符串，写入 bigint 列时 MySQL 静默写入 NULL
- 导致 `_has_existing_realtime_delivery` Check 1（order_id 精确匹配）永远走不到，退到 Check 2（sid+buyer+goods+10分钟窗口）将同一会话同商品的多单误判为重复发货
- V1.35 迁移将 `order_id` 从 bigint 改为 varchar(64)，历史 bigint 数值安全转换为字符串

#### delivery_goods_config 唯一约束冲突
- 线上手动添加的唯一约束不含 `deleted` 字段，软删除记录阻止新记录 INSERT，触发 DuplicateKeyException
- V1.31 迁移清理软删除记录、统一 `config_json` 为 JSON 类型、添加 `uk_dgc_tenant_goods (tenant_id, goods_id)` 唯一约束与 `idx_dgc_deleted` 索引

#### 已发送卡密被软删除导致统计不可见
- `_safe_mark_cards_used` 原先设置 `status=2, deleted=1`，导致已发送卡密从所有统计和查询中消失（total_count / used_count / 明细均过滤 deleted=0）
- V1.34 迁移恢复 `status=2 AND deleted=1` 的卡密为 `deleted=0, is_used=1`，并刷新所有卡密组统计计数

#### 滑块求解错误分类
- `_is_browser_launch_failure()` 识别 Chrome 启动失败/崩溃错误（browserType.launch、Target page/browser has been closed、spawn EAGAIN、pthread_create 等）
- 归类为 `service_unavailable`（不可重试 + 10 分钟冷却），而非默认 `slider_fail`（重试 3 次）
- 修复 Chrome 资源耗尽时每次 1 秒内失败 → slider_fail 重试 3 次 → 每次又立即失败 → 配合 WS 频繁重连 → 单账号累积 13000+ 失败记录

#### 前后端发货模式术语统一
- 前端与 Java 后端使用 `card` 表示卡密发货，Python 服务常量为 `kami`
- `_load_goods_delivery_rule` 增加 `card` → `kami` 别名归一化，修复 delivery_mode 判断不命中导致发货流程终止

#### BillingPlanService 价格计算精度
- `longValue() * 100` 会先截断小数再乘（9.99 元 → 9 元的 bug）
- 改用 `BigDecimal.multiply(BigDecimal.valueOf(100))` 保证精度

---

## [1.9.0] - 2026-07-22

### ✨ 新增

#### 滑块求解系统综合改造
- **不活跃账号排除表** `xianyu_account_solve_exclusion`：3 天未登录前台的用户的闲鱼账号会被自动录入，求解入队时直接跳过，避免占用排队序列产生脏数据
- **不活跃账号定时扫描器**：每小时扫描 `sys_user.last_login_time`，自动维护排除表；用户登录前台时自动从排除表移除其所有闲鱼账号
- **滑块求解记录状态扩展为 6 种**：`success` / `fail` / `retrying`（求解中）/ `queued`（排队中）/ `timeout`（超时）/ `precheck_rejected`（预检验拒绝），前端与管理端同步展示
- **队列进程去重**：入队前检查内存队列与数据库 `retrying` 状态，同一账号同时只会有一个求解任务在排队或处理

### ♻️ 优化

#### 账号活跃度判断逻辑修正
- 从原 `xianyu_account_runtime.last_online_time`（闲鱼账号在线时间）改为 `sys_user.last_login_time`（前台用户登录时间），更准确反映用户是否在主动使用平台

#### 状态分类细化
- 滑块求解超时状态独立：原本超时记录为 `fail`，现独立为 `timeout` 状态，便于区分"预检验拒绝"与"真正求解超时"
- 预检验拒绝状态独立：原本预检验失败记录为 `fail`，现独立为 `precheck_rejected` 状态，前端可针对性提示用户 Cookie 已过期需重新扫码
- Java 网关 KPI 与队列状态查询扩展：管理端可查看 6 种状态的求解统计

---

## [1.8.0] - 2026-07-22

### ✨ 新增

#### 前台用户端 - 首页滑块自动守护惊喜提示
- 首页右侧动画弹窗，展示用户不在场时滑块求解功能自动化解的验证次数
- 仅提示成功次数（好消息），不涉及失败/总数，从后端 SQL 层面确保只返回 `status='success'` 数据
- 弹窗从右侧弹性滑入，5 秒后自动滑出，全程无需用户操作
- 每个浏览会话仅显示一次（`sessionStorage` 标记），距上次访问 < 3 分钟不弹（刷新场景）
- 数字递增动画（easeOutCubic），同时往"最近通知"板块插入守护记录
- 后端新增 `GET /api/captcha/silent-summary` 接口：直接查 MySQL，按 `tenant_id` 过滤，仅统计自动触发场景（`ws_connect` / `cookie_keepalive` / `token_refresh`）的成功次数

#### 后台管理端 - 滑块求解记录"今天"筛选
- 滑块求解记录页面时间范围新增"今天"按钮（`days=1`），与"近 7 天""近 30 天""全部"并列

### ♻️ 优化

#### 移动端设计令牌系统化重构
- 19 个移动端页面 + 6 个移动端通用组件统一迁移至 CSS 设计令牌系统（`var(--m-color-*` / `var(--m-space-*` / `var(--m-radius-*` / `var(--m-shadow-*`）
- 移除硬编码颜色/尺寸/渐变，统一 BEM 类名命名空间，提升主题一致性与可维护性
- 涉及页面：数据面板（MobileData / MobileDataDetail）、自动化（MobileAutomation）、账号（MobileAccounts / MobileAccountDetail）、商品（MobileProducts / MobileProductDetail / MobileProductPublish）、订单（MobileOrders / MobileOrderDetail）、消息（MobileMessages）、通知（MobileNotifications）、商机（MobileOpportunity）、发货源（MobileDeliverySourceLibrary）、自动发货配置（MobileAutoDeliveryConfig）、个人中心（MobileProfile / MobileProfileLedger / MobileProfileRecharge / MobileProfileSecurity）
- 涉及组件：MobileCategoryPicker（分类选择器）、MobileLocationPicker（地区选择器）、MobilePaymentModal（支付弹窗）、MobileOrderShipForm（订单发货表单）、MobileProductLinkPicker（商品链接选择器）、MobileImageUploader（图片上传器）
- 全局导航栏组件（MobileLite.vue / nav.js / MobileIcons.js）未改动，符合导航栏一致性规则

#### 桌面端账号管理 - 滑块求解后自动连接 WebSocket
- 滑块求解成功且 Cookie 恢复后，自动发起 WebSocket 连接，无需用户手动操作
- 轮询 WS 连接状态直至稳定（已连接/失败终态），提示文案随状态动态变化
- 避免用户求解成功后忽略在线状态而反复点击求解按钮

---

## [1.7.0] - 2026-07-21

### ✨ 新增

#### 后端 - 自动回复人工干预机制
- 新增 V1.13 数据库迁移：`xianyu_conversation` 增加 4 字段（`auto_reply_paused` / `auto_reply_manual_disabled` / `last_manual_reply_at` / `last_auto_reply_at`），`xianyu_chat_message` 增加 `is_auto_reply` 字段
- 实现人工干预自动暂停：检测到人工发送消息后，自动暂停当前会话的 AI 自动回复
- 实现 1 分钟自动恢复：距上次人工回复超过 1 分钟时自动恢复 AI 自动回复
- 实现用户手动关闭后禁止自动恢复：仅允许用户手动重新开启
- 新增 `AutoReplyScopeController`：暴露会话级暂停/恢复 API
- 新增 `auto_reply_scope.py` 路由：自动回复范围管理

#### 后端 - 滑块求解记录管理
- 新增 `AdminCaptchaSolveRecordController` / `AdminCaptchaSolveRecordService` / `XianyuCaptchaSolveRecordMapper`
- 新增 `AdminCaptchaSolveRecordVO` / `CaptchaSolveStatsVO` DTO
- 支持分页查询明细记录、KPI 统计（成功率/失败率）、账号分组聚合

#### 后端 - 数据保留策略（存储优化）
- 新增 `DataRetentionConfigService` / `DataRetentionCleanupService` / `DataRetentionController`
- 可配置保留天数（默认 14 天）、总开关、8 类可清理数据独立开关
- 定时清理（每日 04:00），批量删除（500/批），单类别最多 100,000 条/次
- 永久保留：订单、Token 消耗、会员充值、用户账号、商品配置、闲鱼 Cookie
- 公开接口 `/api/system/retention-info` 仅返回保留天数与聊天清理开关

#### 前端 - 移动端视觉重做（多页面高精度还原）
- 移动端全局布局 `MobileLite.vue` 全面重做
- 移动端首页 `MobileHome.vue` 视觉优化
- 移动端数据面板 `MobileData.vue` + 新增详情页 `MobileDataDetail.vue`
- 移动端账号管理 `MobileAccounts.vue` + 新增详情页 `MobileAccountDetail.vue`
- 移动端商品管理 `MobileProducts.vue` + 新增商品详情 `MobileProductDetail.vue` + 新增商品发布 `MobileProductPublish.vue`
- 移动端订单管理 `MobileOrders.vue`（新页面）
- 移动端自动发货 `MobileAutoDelivery.vue`（新页面）
- 移动端聊天详情 `MobileChatDetail.vue`（新页面）
- 移动端个人中心 `MobileProfile.vue` 优化
- 新增 `mobileAccountState.js` 状态管理
- 新增 `MobileIcons.js` 图标补充
- 新增 `mobile-visual-restoration-contract.test.mjs` 视觉契约测试

#### 前端 - 数据保留策略展示
- 管理端运维设置页新增"数据保留策略"卡片（总开关、保留天数、8 类别独立开关、最近清理统计）
- 用户端消息页展示聊天记录保留天数提示（移动端 + 桌面端）
- 用户端 `getRetentionInfo` API 缓存 5 分钟

#### 前端 - 管理端新模块
- 滑块求解记录页 `captcha-records`
- 充值记录页 `recharge-records`
- Token 套餐管理 `token-plans`

#### 基础设施
- MySQL binlog 持久化策略：`binlog-expire-logs-seconds=172800`（2 天）、`max-binlog-size=256M` 写入 `docker-compose.prod.yml`
- 数据保留定时清理 cron 写入 `application.yml`：`xianyu.retention.cleanup-cron`
- `.gitignore` 补充 AI 临时调试文件、leaveMsgTest 截图、mobile-390 截图
- 新增项目规则：`mobile-navigation-consistency.md`（移动端全局导航栏一致性）、`opensource-feature-sync.md`（开源版同步约束）
- 新增 `deploy-crawler-service.py` 部署脚本

### 🐛 修复

#### 后端 - 计费修复
- `AiBillingService` 优先匹配 `model-config-general`，避免误匹配 `model-config-chat` 导致异常扣费
- 自动回复 token 扣费时机调整为发送成功后，发送失败时禁止扣费
- `AiBillingController` 透传发送失败错误码

#### 前端 - 增量发布与缓存
- 用户端 chunk hash 轮换，避免浏览器 404 缓存
- 增量前端 dist 上传脚本改为 md5 同步（非文件列表）

#### 后端 - 支付链路修复
- Nginx 添加 `/open-api/` 转发到后端（18081），修复易支付异步回调被 SPA fallback 拦截导致回调永远无法到达后端的问题
- 二维码内容直接指向易支付 GET URL，扫码后浏览器直接跳转收银台，避免中间页跳转
- `PaymentService` / `PaymentConfigController` 配置链路兼容性调整
- `BusinessSettingsService` 配置同步适配

### 🔧 变更

#### 前端 - 桌面端配套调整
- `ProfileCenterPage.vue` 扩展
- `AccountsPage.vue` / `ProductsPage.vue` 适配
- `App.vue` 注册新增页面路由

#### 后端 - 用户中心与数据同步
- `UserProfileService` / `UserProfileController` 新增字段
- `DataSyncService` / `SyncReceiveService` 兼容性调整
- `AdminModuleController` 扩展
- `WebSocketController` 兼容性调整

#### 爬虫服务
- `crawler-service/Dockerfile` 优化
- `sliderSolver.ts` 增强

### 🗑 服务器清理（已执行）

上线前在服务器执行的一次性非破坏性清理：
- `docker builder prune -af`：释放约 8GB
- `docker image prune -f`：释放约 351MB
- `PURGE BINARY LOGS BEFORE NOW() - INTERVAL 1 DAY`：释放约 2.4GB
- `swapoff /swap.img && rm /swap.img`：释放约 2GB

磁盘占用从 48G / 84% 降至 36G / 63%。

### 📊 数据库迁移

| 版本 | 服务 | 文件 | 说明 |
|---|---|---|---|
| V1.13 | automation-service | `V1.13__add_conversation_auto_reply_state.sql` | 会话级自动回复运行时状态 + 消息 AI 标记 |

**迁移性质**：纯 `ALTER TABLE ADD COLUMN` + `CREATE INDEX`，非破坏性，无数据丢失风险。
**manifest 同步**：sha256 已写入 `db/migrations-manifest.json`。

### ✅ 验证

- core-api 编译通过
- admin-web typecheck 通过（修复 `captcha-records.ts` Record 约束 + `openDetail` 参数类型）
- admin-web build 通过
- user-web build 通过
- DataRetention 测试 11/11 通过
- docker-compose.prod.yml YAML 语法校验通过
- 本地 token 一致性校验通过（`HIDpsuvrKSlWfczLiFTJa0Ydhqm8gx7Q`）
- 商业版前端 `VITE_SHOW_DATA_SYNC=false` 校验通过

### 🚀 上线验证（2026-07-21）

#### 中国后端服务器（1.12.66.249）
- 8 个容器全部 healthy：mysql / redis / crawler-postgres / automation / automation-worker / crawler-service / crawler-worker / backend
- V1.13 迁移手动执行完成：`xianyu_conversation` 4 字段 + 1 索引、`xianyu_chat_message` 1 字段全部就位
- MySQL binlog_expire_logs_seconds = 172800（2 天）生效
- 磁盘占用稳定在 37G / 59G（65%）
- 健康检查端点 HTTP 200

#### 美国前端服务器（154.9.254.86）
- user-web 上传成功（sha256 校验通过），rsync 同步完成，nginx reload 成功
- admin-web 上传成功（sha256 校验通过），rsync 同步完成，nginx reload 成功
- `https://www.xianyupilot.com/` 返回 HTTP 200
- `https://admin.xianyupilot.com/` 返回 HTTP 200
- 旧版本已备份至 `/var/www/backups/{user-web,admin-web}-20260721-222809`

---

## [1.6.1] - 2026-07-20

### ✨ 新增
- Xvfb 滑块求解恢复（Linux 服务器无头模式）
- 在线消息 peer_key 持久化修复

### 🐛 修复
- 生图空白图片不展示

---

## [1.6.0] - 2026-07-20

### ✨ 新增
- 商品草稿箱与图片生成记录页面
- 视觉优化商品草稿箱与图片生成记录页面

---

## [1.5.0] - 2026-07-19

### ✨ 新增
- 工作流草稿箱
- 图片生成记录页面

---

## [1.4.0] - 2026-07-18

### ✨ 新增
- 定时任务体系重构
- 个人中心视觉升级
- 货源商城购买链路

### 🐛 修复
- 定时任务 5 个 bug
- V1.24 迁移改用直接相关子查询回填 accountIds
- automation-service 启动失败（ping missing reconnect）

---

## [1.3.0] - 2026-07-17

### 🔧 变更
- 恢复丢失的工作并提升版本号
