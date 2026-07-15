# 闲鱼助手后台 - 下一阶段全面优化文档

> 文档版本：v1.0
> 编制时间：2026-06-29
> 适用范围：admin-web / core-api / automation-service 三端
> 当前状态：本轮优化已通过浏览器视觉验证 + 29 项 API 测试 + TypeScript 编译，达到公测级别

---

## 一、本轮已完成优化回顾

### 1.1 已修复的 Mock 数据问题

| 文件 | 原问题 | 修复方式 |
|------|--------|----------|
| [art-notification/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/components/core/layouts/art-notification/index.vue) | 硬编码 mock 用户（冷月呆呆、小肥猪等） | 接入 `getRecentEvents()` + `getNotificationDeliveryLogs()` |
| [register/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/auth/register/index.vue) | setTimeout 假注册 | 改为信息提示页（账号由超管创建） |
| [forget-password/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/auth/forget-password/index.vue) | 空函数绑定按钮 | 改为信息提示页（联系超管重置） |
| [user-center/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/user-center/index.vue) | 假用户名/密码/标签 | 接入 `useUserStore().getUserInfo` 真实数据 |

### 1.2 已修复的关键 Bug

- **路由缺失**：在 [admin.ts](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/admin.ts#L100-L119) 中注册 `/system/user-center` 路由（原本 systemRoutes 未被 [modules/index.ts](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/index.ts) 导出，导致 404）
- **TypeScript 类型错误**：
  - [menu/index.vue:182](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/menu/index.vue#L182) 访问不存在的 `updatedTime/createdTime`
  - [user/index.vue:174](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/user/index.vue#L174) `'modify'` 不是合法的列类型

### 1.3 验证结果

- 32 个后台页面全部加载成功，标题正确
- 29 项后端 API 测试全部 PASS
- `pnpm typecheck` 通过，0 错误
- 浏览器控制台无 error

---

## 二、下一阶段优化方向

### 2.1 数据真实性深化（P0 - 最高优先级）

#### 2.1.1 待办列表数据源接入

**当前问题**：[art-notification/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/components/core/layouts/art-notification/index.vue) 的 `pendingList` 始终为空数组（`loadPendingList()` 直接返回 `[]`）。

**优化方案**：
1. 在 core-api 新增 `/admin/dashboard/pending-tasks` 端点
2. 聚合以下数据源作为待办：
   - 失败的工作流执行（status=failed，需用户介入重试）
   - 触发风控但未处理的闲鱼账号（risk_status=blocked）
   - 通知发送失败且 retry_count < 3 的记录
   - 待审核的卡密库存（stock < threshold）
3. 前端 `loadPendingList()` 改为异步调用该端点

**预期收益**：通知面板"待办"标签真正可用，管理员能直观看到需处理事项。

#### 2.1.2 通知已读状态持久化

**当前问题**：`markAllRead()` 仅 `ElMessage.success('已全部标为已读')`，刷新后红点计数恢复。

**优化方案**：
1. core-api 新增 `/admin/notifications/read-status` 端点（POST 标记已读，GET 查询已读列表）
2. 数据库新增 `sys_notification_read` 表（user_id, event_id, read_at）
3. 前端通知计数基于"未读"统计，而非"总数"

#### 2.1.3 用户中心头像上传

**当前问题**：[user-center/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/user-center/index.vue) 头像列显示"未设置"，无上传入口。

**优化方案**：
1. core-api 新增 `/admin/users/{id}/avatar` 端点（multipart 上传）
2. 复用已有的 `/api/image/upload` 代理逻辑
3. 前端新增头像上传组件（ElUpload + 裁剪）
4. 上传成功后更新 `sys_admin_user.avatar` 字段

---

### 2.2 视觉与交互优化（P1 - 高优先级）

#### 2.2.1 仪表盘运营概览增强

**当前状态**：[AdminDashboard](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/module/index.vue) 仅显示 summary 卡片 + trend 图表 + recent events 列表。

**优化方案**：

| 模块 | 新增内容 | 数据来源 |
|------|----------|----------|
| 实时监控卡片 | 在线账号数、今日发布数、今日成交额、AI 调用次数 | 聚合 xianyu_account / workflow_execution / order / ai_usage_log |
| 趋势图表扩展 | 支持切换 7 天 / 30 天 / 90 天维度 | `/admin/dashboard/trend?range=7d\|30d\|90d` |
| 风险雷达图 | 各账号风控等级分布 | xianyu_account.risk_level |
| Top 5 热销商品 | 缩略图 + 标题 + 销量 | 复用 hot-goods 模块数据 |
| 系统健康度 | core-api / automation-service / crawler-service 健康状态 | `/actuator/health` + `/health` + 新增 crawler 健康检查 |

#### 2.2.2 表格统一交互规范

**当前问题**：不同模块表格的分页、筛选、排序行为不一致。

**优化方案**：
统一所有 `/admin/modules/{key}/page` 返回结构为：
```json
{
  "code": 200,
  "data": {
    "records": [...],
    "total": 100,
    "current": 1,
    "size": 10,
    "pages": 10
  }
}
```

前端 [admin/module/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/module/index.vue) 统一使用 `ElPagination`，支持 `page-sizes: [10, 20, 50, 100]`，并持久化分页大小到 localStorage。

#### 2.2.3 深色模式适配

**当前状态**：仅 Tailwind CSS 变量切换，部分组件（如 ElAlert、ElDrawer）在深色模式下对比度不足。

**优化方案**：
1. 审计所有 `bg-white`、`text-g-900` 等硬编码颜色
2. 替换为 `bg-g-50 dark:bg-g-900`、`text-g-900 dark:text-g-100` 模式
3. 重点检查：通知面板、用户中心、登录页、注册页、忘记密码页

---

### 2.3 性能优化（P1 - 高优先级）

#### 2.3.1 列表页查询性能

**当前问题**：商品监管、订单监管等模块在数据量大时（>1000 条）分页查询慢。

**优化方案**：

1. **数据库索引审计**：
   - `xianyu_goods` 表：确保 `(tenant_id, account_id, created_time)` 复合索引
   - `xianyu_order` 表：确保 `(tenant_id, account_id, created_time)` 复合索引
   - `workflow_execution` 表：确保 `(tenant_id, status, created_time)` 复合索引

2. **N+1 查询消除**：
   - 审计 [AdminModuleController.java](file:///g:/源码/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) 的 `page()` 方法
   - 对关联字段（如 account_id 对应的账号名）改用 JOIN 或批量预查询

3. **前端虚拟滚动**：
   - 当 records > 100 时启用 `ElTableV2` 虚拟滚动
   - 缩略图懒加载（`loading="lazy"`）

#### 2.3.2 仪表盘首屏加载

**当前问题**：仪表盘首次加载需串行请求 summary / trend / recent-events 三个接口。

**优化方案**：
1. 新增 `/admin/dashboard/init` 聚合端点，一次返回所有首屏数据
2. 前端使用 `Promise.allSettled` 并行请求（已是并行，但聚合端点可减少 HTTP 开销）
3. 趋势图表数据缓存 5 分钟（Redis 或前端内存缓存）

#### 2.3.3 前端打包体积

**优化方案**：
1. 运行 `pnpm build` 分析 bundle 大小
2. 对 element-plus 按需引入审计（确认未全量引入）
3. 对 echarts / vue-draggable-plus 等大库做动态导入（`import()`）
4. 目标：首屏 JS < 300KB（gzip）

---

### 2.4 安全加固（P1 - 高优先级）

#### 2.4.1 接口权限审计

**当前问题**：部分 `/admin/modules/{key}/*` 端点可能未严格校验角色权限。

**优化方案**：
1. 审计 [AdminModuleController.java](file:///g:/源码/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) 所有方法
2. 确保所有写操作（save/update/delete/batchDelete）标注 `@RequiresRoles("R_SUPER")` 或 `@RequiresPermissions`
3. 读操作允许 `R_ADMIN`，但敏感字段（如密码哈希、API Key）需脱敏

#### 2.4.2 敏感信息脱敏

**当前问题**：闲鱼账号管理可能直接展示完整 Cookie。

**优化方案**：
1. [AdminModuleController.java](file:///g:/源码/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) `page()` 方法返回前对 cookie 字段脱敏（仅显示前 20 字符 + `***`）
2. 新增 `/admin/modules/xianyu-accounts/{id}/cookie` 端点，需 `R_SUPER` 权限才能查看完整 Cookie
3. 操作审计日志记录所有查看完整 Cookie 的行为

#### 2.4.3 CSRF 与 XSS 防护

**优化方案**：
1. 确认 JWT 已设置 `httpOnly` Cookie（当前在 localStorage，需评估迁移）
2. 对所有用户输入（商品标题、自动回复规则、卡密内容）做 HTML 转义
3. CSP Header 配置：`default-src 'self'; script-src 'self' 'unsafe-inline'`

---

### 2.5 功能完善（P2 - 中优先级）

#### 2.5.1 用户管理增强

**当前状态**：[AdminUsers](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/admin.ts#L21) 仅支持基础 CRUD。

**待完善功能**：
- 重置用户密码（生成临时密码 + 强制首次登录修改）
- 用户封禁/解封（status 字段 + 登录拦截）
- 用户操作日志查看（关联 audit-logs 模块，按 user_id 筛选）
- 批量导入用户（Excel 模板下载 + 上传解析）

#### 2.5.2 卡密管理增强

**待完善功能**：
- 卡密批量导入（CSV/Excel）
- 卡密导出（按商品筛选）
- 卡密库存预警（stock < threshold 时自动创建待办）
- 卡密使用统计（每个商品的卡密消耗速度）

#### 2.5.3 通知渠道测试

**待完善功能**：
- 通知渠道配置页新增"发送测试通知"按钮
- 后端新增 `/admin/notify-channels/{id}/test` 端点
- 测试结果实时反馈（成功/失败 + 错误详情）

#### 2.5.4 数据备份与恢复

**待完善功能**：
- 备份任务定时调度（cron 表达式配置）
- 备份文件下载（带权限校验）
- 备份恢复功能（上传备份文件 + 还原）
- 备份保留策略（自动清理 30 天前的备份）

---

### 2.6 监控与可观测性（P2 - 中优先级）

#### 2.6.1 前端错误监控

**当前状态**：[client-errors](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/admin.ts#L93) 页面已有，但需确认上报机制。

**优化方案**：
1. 在 [main.ts](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/main.ts) 注册全局 `window.onerror` + `unhandledrejection` 监听
2. 上报至 `/api/client-errors` 端点（需确认已存在）
3. 上报内容：message / stack / userAgent / url / userId / timestamp
4. 限流：同类型错误 1 分钟内仅上报一次

#### 2.6.2 后端慢查询监控

**优化方案**：
1. 开启 MyBatis 慢查询日志（`slow-query-millis: 1000`）
2. 新增 `/admin/ops/slow-queries` 端点展示慢查询列表
3. 对慢查询自动建议索引（基于 EXPLAIN 结果）

#### 2.6.3 服务健康看板

**优化方案**：
1. 仪表盘新增"系统健康"卡片
2. 实时展示：
   - core-api JVM 内存 / 线程数 / GC 次数
   - automation-service Python 内存 / 事件循环延迟
   - crawler-service 浏览器实例数 / 队列长度
   - MySQL 连接池使用率 / 慢查询数
3. 异常时自动创建告警记录

---

### 2.7 国际化与可访问性（P3 - 低优先级）

#### 2.7.1 国际化完善

**当前状态**：部分页面仍使用硬编码中文（如 [art-notification/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/components/core/layouts/art-notification/index.vue) 的"已全部标为已读"）。

**优化方案**：
1. 全局搜索硬编码中文字符串
2. 迁移至 `src/locales/zh-CN.ts` 和 `en-US.ts`
3. 提供"跟随浏览器语言"选项

#### 2.7.2 可访问性（a11y）

**优化方案**：
1. 所有按钮添加 `aria-label`
2. 表单字段关联 `<label for>`
3. 颜色对比度审计（WCAG AA 标准）
4. 键盘导航支持（Tab 顺序、焦点可见）

---

## 三、执行计划

### 阶段一：数据真实性深化（1-2 天）
- [ ] 待办列表数据源接入（2.1.1）
- [ ] 通知已读状态持久化（2.1.2）
- [ ] 用户中心头像上传（2.1.3）

### 阶段二：性能与安全（2-3 天）
- [ ] 数据库索引审计（2.3.1）
- [ ] N+1 查询消除（2.3.1）
- [ ] 仪表盘首屏聚合端点（2.3.2）
- [ ] 接口权限审计（2.4.1）
- [ ] 敏感信息脱敏（2.4.2）

### 阶段三：功能完善（2-3 天）
- [ ] 用户管理增强（2.5.1）
- [ ] 卡密管理增强（2.5.2）
- [ ] 通知渠道测试（2.5.3）
- [ ] 数据备份恢复（2.5.4）

### 阶段四：监控与视觉（1-2 天）
- [ ] 前端错误监控确认（2.6.1）
- [ ] 后端慢查询监控（2.6.2）
- [ ] 服务健康看板（2.6.3）
- [ ] 仪表盘运营概览增强（2.2.1）
- [ ] 深色模式适配（2.2.3）

### 阶段五：收尾（0.5 天）
- [ ] 国际化完善（2.7.1）
- [ ] 可访问性基础（2.7.2）
- [ ] 前端打包体积优化（2.3.3）
- [ ] 全方位测试回归

---

## 四、关键约束（不可违反）

延续 [project_memory.md](file:///c:/Users/admin/.trae-cn/memory/projects/-g----xianyu-assistant-package-temp/project_memory.md) 中的所有硬约束，下一阶段优化需特别注意：

1. **不得修改闲鱼商品关键词搜索逻辑**（见 `.trae/rules/goofish-keyword-search.md`）
2. **Java 网关代理 Python 服务时必须拆包 ResultObject**，仅返回 data 字段
3. **core-api multipart 上传限制**：`max-file-size:20MB, max-request-size:50MB`
4. **Vite dev server 必须配置 `/uploads` 代理**到 `http://localhost:12401`
5. **未生成 AI 封面图的商品严禁发布**（`img_ai_ok == True` 强制校验）
6. **工作流执行必须异步化**：Python fire-and-forget，Java 立即返回 executionId
7. **跨次运行工作流去重**：`tenant_id + account_id + source_item_id`，无 itemId 用标题 MD5
8. **润色强限制注入所有润色链路**：禁止"盗版""破解版""毕设"关键词
9. **移动端适配必须完全隔离**，不得影响 PC 端
10. **店铺爬取必须用浏览器**，不可用 API 接口

---

## 五、测试验收标准

下一阶段优化完成后，需通过以下验收：

### 5.1 功能测试
- [ ] 所有 32 个后台页面可正常访问
- [ ] 通知面板"待办"标签有真实数据
- [ ] 通知"标为已读"后刷新仍保持已读状态
- [ ] 用户中心可上传头像
- [ ] 用户管理支持重置密码 / 封禁
- [ ] 卡密管理支持批量导入
- [ ] 通知渠道支持发送测试通知
- [ ] 数据备份支持恢复

### 5.2 性能测试
- [ ] 仪表盘首屏加载 < 2 秒
- [ ] 列表页 1000 条数据分页查询 < 500ms
- [ ] 前端打包后首屏 JS < 300KB（gzip）

### 5.3 安全测试
- [ ] 所有写操作有权限校验
- [ ] Cookie 字段脱敏显示
- [ ] XSS 输入过滤生效
- [ ] 操作审计日志完整

### 5.4 兼容性测试
- [ ] Chrome / Edge / Firefox 最新版
- [ ] 浅色 / 深色模式切换正常
- [ ] 1920×1080 / 1366×768 分辨率正常
- [ ] 移动端基础可用（响应式）

### 5.5 回归测试
- [ ] `pnpm typecheck` 0 错误
- [ ] `pnpm build` 成功
- [ ] 浏览器控制台无 error
- [ ] 29 项 API 测试全部 PASS
- [ ] 闲鱼商品关键词搜索功能不受影响

---

## 六、相关文件清单

### 本轮已修改文件

| 文件 | 修改内容 |
|------|----------|
| [art-notification/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/components/core/layouts/art-notification/index.vue) | 接入真实 API |
| [register/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/auth/register/index.vue) | 信息提示页 |
| [forget-password/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/auth/forget-password/index.vue) | 信息提示页 |
| [user-center/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/user-center/index.vue) | 接入真实用户数据 |
| [admin.ts](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/admin.ts) | 新增 user-center 路由 |
| [menu/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/menu/index.vue) | 修复 TS 类型错误 |
| [user/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/system/user/index.vue) | 修复 TS 类型错误 |

### 下一阶段需重点关注的文件

| 文件 | 优化方向 |
|------|----------|
| [AdminModuleController.java](file:///g:/源码/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) | 权限审计 / 脱敏 / 聚合端点 |
| [admin/module/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/module/index.vue) | 表格统一规范 / 虚拟滚动 |
| [admin/dashboard/index.vue](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/module/index.vue) | 仪表盘增强 |
| [main.ts](file:///g:/源码/xianyu-assistant-package-temp/apps/admin-web/src/main.ts) | 前端错误监控 |
| `apps/core-api/.../ModuleCatalog.java` | 新增模块注册 |
| `apps/admin-web/src/api/admin.ts` | 新增 API 函数 |

---

## 七、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 数据库索引调整锁表 | 短时服务不可用 | 低峰期执行 / 使用 `ALGORITHM=INPLACE` |
| 敏感信息脱敏改动影响现有展示 | 前端字段缺失 | 保留原字段名，值改为 `***`，前端无需改 |
| 异步聚合端点性能 | 仪表盘加载变慢 | 设置 5 秒超时 + 降级到原串行请求 |
| 权限收紧导致现有用户无法访问 | 用户投诉 | 灰度发布 + 提供"临时豁免"开关 |
| 深色模式适配工作量超预期 | 延期 | 分批迭代，优先适配高频页面 |

---

**文档结束**

下一阶段优化开始时，请先完整阅读本文档，并遵循"关键约束"章节的所有规则。
