# 闲鱼助手后台综合分析报告

> 生成日期：2026-06-26  
> 分析范围：admin-web（Vue3 + Element Plus，端口 3006）+ core-api（Spring Boot + MySQL，端口 18080）  
> 分析方法：源代码审查 + 真实 HTTP 请求回归测试

---

## 目录

1. [项目架构概览](#1-项目架构概览)
2. [已修复的问题（本次会话）](#2-已修复的问题本次会话)
3. [Bug 分析](#3-bug-分析)
4. [功能缺口分析（有页面但无法使用）](#4-功能缺口分析有页面但无法使用)
5. [安全问题分析](#5-安全问题分析)
6. [潜在问题分析](#6-潜在问题分析)
7. [可优化部分](#7-可优化部分)
8. [修复优先级建议](#8-修复优先级建议)

---

## 1. 项目架构概览

### 前端（admin-web）
- **框架**：Vue 3 + TypeScript + Element Plus + Vite
- **路由**：9 大模块组，30+ 个子页面
- **通用模块页**：`/admin/module/:moduleKey` 通过 `ModuleCatalog` 动态渲染列定义和操作按钮
- **专用组件页**：dashboard、payment-config、monitor、settings、notification-logs、audit-logs、client-errors、ai-usage、ai-token、model-config

### 后端（core-api）
- **框架**：Java 17 + Spring Boot + MyBatis + JdbcTemplate + MySQL
- **认证**：JWT（HS256）+ `JwtAuthFilter` 拦截 `/admin-api/*`
- **模块体系**：`AdminModuleController` 统一入口 → `AdminModuleService` 分发 → 专用 Service / `admin_module_record` 表
- **数据分层**：
  - 专用 Service：users、plans、xianyu-accounts、ai-usage、ai-token
  - 真实业务表：goods、orders、messages、delivery、auto-reply、kami、hot-goods
  - JSON 配置表：其余所有模块（存入 `admin_module_record` 的 `json_text` 字段）

### 关键文件路径
| 类型 | 文件 |
|------|------|
| 路由定义 | [admin.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/router/modules/admin.ts) |
| 通用模块页 | [module/index.vue](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/module/index.vue) |
| 后端统一入口 | [AdminModuleController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) |
| 模块注册表 | [ModuleCatalog.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/ModuleCatalog.java) |
| 核心服务 | [AdminModuleService.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/AdminModuleService.java) |
| 真实数据模块 | [AdminRealDataModuleService.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/AdminRealDataModuleService.java) |
| JWT 认证 | [JwtAuthFilter.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/security/JwtAuthFilter.java) |
| 全局异常处理 | [GlobalExceptionHandler.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/config/GlobalExceptionHandler.java) |
| 前端 HTTP 工具 | [http/index.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/utils/http/index.ts) |
| 前端路由守卫 | [beforeEach.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/router/guards/beforeEach.ts) |

---

## 2. 已修复的问题（本次会话）

| # | 问题 | 修复方式 | 状态 |
|---|------|----------|------|
| 1 | 通知发送记录页 500 错误 | 路径拼接 bug：`@RequestMapping("/api")` + `@GetMapping("/admin-api/notifications/delivery-logs")` → `/api/admin-api/...`。新建 `AdminNotificationLogController` 独立挂载到 `/admin-api/notifications` | ✅ 已修复 |
| 2 | 异常告警/文件管理页显示用户管理数据 | `ModuleCatalog` 未注册 alerts 和 files，回退到 `metas.get("users")`。已在构造函数中注册两个新 moduleKey | ✅ 已修复 |
| 3 | 仪表盘"最近后台操作"时间线为空 | `AdminModuleService.recentEvents()` 直接 `return List.of()`。已实现真实查询 `operation_log` 表 | ✅ 已修复 |
| 4 | 热销商品统计刷新 500 | `hot_goods_stat` 表不存在。已执行 V1.6 迁移 SQL | ✅ 已修复 |
| 5 | 7 个业务模块点击新增/编辑抛 400 | 前端 `readonlyModule` 写死 `false`。已改为根据 moduleKey 动态判断，隐藏新增/编辑/批量按钮，保留"详情" | ✅ 已修复 |

---

## 3. Bug 分析

### 3.1 严重：TenantContext 在 admin 端为 null 导致功能异常

**影响范围**：多个 admin 端 Controller 和 Service 调用 `TenantContext.getCurrentTenantId()` 返回 null

**根因**：`JwtAuthFilter` 只设置 `AdminContext`，不设置 `TenantContext`。而 `UserJwtAuthFilter`（拦截 `/api/*`）才设置 `TenantContext`。

**受影响文件**：
- [DashboardController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/DashboardController.java) —— `dashboardService.summary(TenantContext.getCurrentTenantId())` 传入 null
- [AdminModuleController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminModuleController.java) —— `dashboardService.salesTrend(TenantContext.getCurrentTenantId(), 7)` 传入 null
- [HotGoodsStatController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/HotGoodsStatController.java) —— `TenantContext.getCurrentTenantId()` 返回 null
- [OperationLogController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/OperationLogController.java) —— 所有分页查询使用 `TenantContext.getCurrentTenantId()` 为 null

**实际表现**：Dashboard 摘要卡片在 tenantId=null 时仍能工作（因为 SQL 查询 `tenant_id=?` 传入 null 会导致 0 结果），但趋势图、热销统计等会返回空数据。操作日志查询同理。

**修复建议**：在 `JwtAuthFilter` 中从 JWT payload 提取 tenantId 并设置 `TenantContext`，或从数据库中查询用户的 tenantId。

**已验证**：通过 curl 测试 `GET /admin-api/admin/dashboard/summary`，返回 `code=0, msg="tenantId is null"`，确认此问题存在且影响仪表盘数据。

---

### 3.2 中等：GlobalExceptionHandler 吞掉所有异常细节

**位置**：[GlobalExceptionHandler.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/config/GlobalExceptionHandler.java)

**问题**：
```java
@ExceptionHandler(Exception.class)
public Result<Void> handleException(Exception e) {
    log.error("系统异常: {}", e.getMessage(), e);
    return Result.fail("系统繁忙，请稍后重试，错误编号：" + traceId);
}
```
- 所有未捕获异常统一返回 "系统繁忙，请稍后重试"，HTTP 状态码仍为 200
- 前端无法区分 404（资源不存在）和 500（服务器错误）
- `BizException` 的 code=400/404 也被转为 HTTP 200，但 body code 正确

**影响**：用户看到模糊的错误提示，运维排查困难。

**修复建议**：区分异常类型，至少对 `BizException` 返回对应的 HTTP 状态码。

---

### 3.3 中等：前端 notification-logs 页调用 `/notifications/delivery-logs` 传参方式不匹配

**问题**：前端 [notification-logs/index.vue](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/ops/notification-logs/index.vue) 查询参数有 `success`、`channelKey`、`keyword`，但后端 `AdminNotificationLogController` 只支持 `current`、`size` 参数，没有过滤逻辑。

**实际表现**：前端筛选条件不生效，所有记录都返回。

**修复建议**：在后端添加 `success`、`channelKey`、`keyword` 查询参数支持。

---

### 3.4 轻微：前端 system-manage.ts 的 `/system/sms-config` 和 `/system/email-config` 后端无对应接口

**位置**：[system-manage.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/system-manage.ts)

**已验证**：`VITE_API_URL = /admin-api`（[.env](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/.env)），Vite 代理 `/admin-api` → `http://localhost:18080`（[vite.config.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/vite.config.ts) L152-156）。因此所有前端 API 路径拼接后都是正确的。

**但以下两个接口后端无对应 Controller**：
- `GET /admin-api/system/sms-config` → 后端无 handler
- `GET /admin-api/system/email-config` → 后端无 handler

**实际表现**：短信/邮箱配置功能完全不可用。

**修复建议**：在 `SystemConfigController` 或新建 Controller 中实现这两个接口，或将前端对应页面移除。

---

### 3.5 轻微：ModuleCatalog 兜底逻辑存在安全隐患

**位置**：[ModuleCatalog.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/ModuleCatalog.java) L87

```java
public ModuleMeta get(String key) {
    return metas.getOrDefault(key, metas.get("users"));
}
```

**问题**：未注册的 moduleKey 会回退到 users 的元信息，导致：
- 前端显示错误的列定义
- 如果 users 数据被误操作，会污染其他模块

**修复建议**：对未注册的 moduleKey 返回 404 或明确的错误信息，而不是静默回退。

---

## 4. 功能缺口分析（有页面但无法使用）

> **重要前提**：已确认 `VITE_API_URL = /admin-api`（[.env](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/.env) L13），Vite 代理 `/admin-api` → `http://localhost:18080`（[vite.config.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/vite.config.ts) L152-156）。所有前端 API 请求路径拼接后都能正确匹配后端路由，**不存在路径不匹配问题**。以下分析聚焦于真正的功能缺失。

### 4.1 严重：notify-channels 和 risk-events 模块无后端数据

**前端路由**：`/admin/risk-notify` 下有 `notify-channels` 和 `risk-events` 两个 moduleKey

**问题**：这两个 moduleKey 在 `ModuleCatalog` 中没有注册，会回退到 users 的元信息（列定义错乱）。且 `admin_module_record` 表中没有对应数据。

**实际表现**：页面可访问但显示 users 的列定义，数据为空，用户看到的是一个错乱的空表格。

**修复建议**：在 `ModuleCatalog` 中注册这两个 moduleKey，定义正确的列定义。

---

### 4.2 中等：短信/邮箱配置后端接口缺失

**前端**：`system-manage.ts` 调用 `GET /system/sms-config` 和 `GET /system/email-config`  
**后端**：无对应 Controller

**实际表现**：调用返回 404 或 500。

**修复建议**：在 `SystemConfigController` 中实现这两个接口，或从 `NotificationConfigController` 中提供。

---

### 4.3 中等：通知发送记录缺少筛选功能

**前端**：[notification-logs/index.vue](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/ops/notification-logs/index.vue) 有筛选条件（success、channelKey、keyword）  
**后端**：[AdminNotificationLogController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminNotificationLogController.java) 只支持 current、size 参数

**实际表现**：前端筛选条件不生效。

**修复建议**：在后端添加 `success`、`channelKey`、`keyword` 查询参数支持。

---

### 4.4 轻微：支付配置页面功能依赖外部服务

**前端**：[payment-config/index.vue](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/views/admin/payment-config/index.vue) 和 [payment.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/payment.ts)  
**后端**：[PaymentController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/PaymentController.java) 存在，路径 `/admin-api/payment`

**状态**：路径匹配正确，但需确认支付服务（支付宝/微信）已配置。如未配置，前端页面可访问但支付功能不可用。

---

### 4.5 轻微：监控页面功能依赖外部服务

**前端**：[monitor.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/monitor.ts) 调用 `/monitor/ai` 等  
**后端**：[AdminMonitoringController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AdminMonitoringController.java) 路径 `/admin-api/monitor`

**状态**：路径匹配正确。但监控数据来自 automation-service（端口 12401），如果该服务未启动，监控数据将为空。

---

### 4.6 轻微：操作审计日志页面

**前端**：[operation-logs.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/operation-logs.ts) 调用 `/operation-logs`  
**后端**：[OperationLogController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/OperationLogController.java) 路径 `/admin-api/operation-logs`

**状态**：路径匹配正确。但受 TenantContext 为 null 影响（见 3.1），查询结果可能为空。

---

### 4.7 轻微：客户端错误日志页面

**前端**：[client-errors.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/client-errors.ts) 调用 `/client-errors/page`  
**后端**：[ClientErrorController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/ClientErrorController.java) 路径 `/admin-api/client-errors/page`

**状态**：路径匹配正确，功能正常。

---

## 5. 安全问题分析

### 5.1 高危：JWT 密钥使用默认值

**位置**：[JwtUtil.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/security/JwtUtil.java)

**问题**：`admin.jwt.secret` 默认值为 `please-change-this-admin-jwt-secret-at-least-32-chars`（硬编码在 `application.yml` 或 `application.properties` 中）

**影响**：攻击者可以伪造 JWT token，获取任意用户权限。

**缓解措施**：`SecurityStartupValidator` 和 `StartupSecurityGuard` 在 prod profile 下会阻止启动。但当前运行环境非 prod profile，此默认密钥仍在生效。

**修复建议**：通过环境变量覆盖默认值。

---

### 5.2 高危：Cookie 加密密钥使用默认值

**位置**：[AutomationProxyController.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java) L55-56

```java
@Value("${xianyu.cookie.crypto-secret:dev-only-cookie-crypto-secret-change-me-32-chars}")
private String cookieCryptoSecret;
```

**影响**：闲鱼账号 Cookie 的 AES-GCM 加密可被破解，导致所有用户 Cookie 泄露。

---

### 5.3 中危：内部 API Token 使用默认值

**位置**：多处使用 `${xianyu.automation.internal-token:dev-only-internal-api-token-change-me-32-chars}`

**影响**：自动化服务间通信的认证令牌可被预测，攻击者可直接调用内部 API。

---

### 5.4 中危：CORS 配置允许所有来源（开发环境）

**位置**：[WebConfig.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/config/WebConfig.java) L46-53

```java
Arrays.stream(origins.split(",")).map(String::trim).filter(s -> !s.isBlank())
        .forEach(adminConfig::addAllowedOrigin);
adminConfig.addAllowedHeader("*");
adminConfig.addAllowedMethod("*");
```

**问题**：`admin.cors.allowed-origins` 配置决定了允许的来源。应确保生产环境限制为具体域名。

---

### 5.5 中危：种子账号密码硬编码

**位置**：[AuthService.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/AuthService.java) L56-67

```java
public void seedAdmin() {
    if (!seedEnabled || isProdProfile()) return;
    // 创建 admin/admin123456 和 User/123456
}
```

**问题**：`admin.seed.enabled` 为 true 时（非 prod），自动创建固定密码的账号。虽然只在首次启动时执行，但如果数据库被清空后重启，这些账号会重新出现。

**缓解措施**：`StartupSecurityGuard` 要求 prod 环境 `admin.seed.enabled=false`。

---

### 5.6 低危：BCrypt 密码哈希未配置强度

**位置**：[AuthService.java](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/core-api/src/main/java/com/xianyu/admin/service/AuthService.java) L17

```java
private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
```

**问题**：使用默认的 BCrypt 强度（10 rounds），对于生产环境建议使用 12+。

---

### 5.7 低危：JWT 无刷新机制

**问题**：当前返回的 `refreshToken` 与 `token` 相同，没有真正的刷新机制。Token 过期后用户必须重新登录。

---

### 5.8 低危：密码重置接口缺少旧密码验证

**位置**：[system-manage.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/src/api/system-manage.ts) L108-113

```typescript
export function fetchResetUserPassword(id: number, newPassword: string) {
  return request.post({ url: `/system/user/${id}/reset-password`, data: { newPassword } })
}
```

**问题**：管理员可以直接重置任意用户密码，不需要验证旧密码。虽然这是管理员功能，但缺少审计日志记录。

---

## 6. 潜在问题分析

### 6.1 前端 API baseURL 路径已确认正确

**已确认**：`VITE_API_URL = /admin-api`（[.env](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/.env) L13），Vite 代理 `/admin-api` → `http://localhost:18080`（[vite.config.ts](file:///g:/%E6%BA%90%E7%A0%81/xianyu-assistant-package-temp/apps/admin-web/vite.config.ts) L152-156）。

**路径拼接验证**：
| 前端 API 文件 | 请求路径 | 实际请求 URL | 后端路由 | 匹配 |
|-------------|---------|-------------|---------|------|
| admin.ts | `/admin/modules/...` | `/admin-api/admin/modules/...` | `/admin-api/admin/modules/...` | ✅ |
| notification-logs.ts | `/notifications/delivery-logs` | `/admin-api/notifications/delivery-logs` | `/admin-api/notifications` | ✅ |
| system-manage.ts | `/admin/menus` | `/admin-api/admin/menus` | `/admin-api/admin/menus` | ✅ |
| system-manage.ts | `/admin/users` | `/admin-api/admin/users` | `/admin-api/admin/users` | ✅ |
| system-manage.ts | `/system/config` | `/admin-api/system/config` | `/admin-api/system/config` | ✅ |
| system-manage.ts | `/system/sms-config` | `/admin-api/system/sms-config` | **无** | ❌ |
| system-manage.ts | `/system/email-config` | `/admin-api/system/email-config` | **无** | ❌ |
| monitor.ts | `/monitor/ai` | `/admin-api/monitor/ai` | `/admin-api/monitor` | ✅ |
| payment.ts | `/payment/configs` | `/admin-api/payment/configs` | `/admin-api/payment` | ✅ |
| operation-logs.ts | `/operation-logs` | `/admin-api/operation-logs` | `/admin-api/operation-logs` | ✅ |
| client-errors.ts | `/client-errors/page` | `/admin-api/client-errors/page` | `/admin-api/client-errors/page` | ✅ |

**结论**：仅有 `/system/sms-config` 和 `/system/email-config` 两个接口后端缺失，其余所有 API 路径均正确匹配。

---

### 6.2 服务间重启依赖

**问题**：当前 core-api 通过 fat JAR 启动，修改 Java 代码后需要重新打包并重启。DevTools 热重载不可用。

**影响**：每次代码修改后需要手动停止进程、更新 JAR、重启，耗时约 30-60 秒。

**建议**：开发环境改用 `mvn spring-boot:run` 或配置 DevTools。

---

### 6.3 数据库表不存在时的异常处理不一致

**问题**：`AdminModuleService` 中有多处 try-catch 吞掉异常（如 `xianyu_account` 表不存在时忽略），但其他地方（如 `AdminRealDataModuleService`）可能直接抛出异常。

**影响**：部分功能在新部署环境（表未创建）下可能静默失败或直接报 500。

---

### 6.4 admin_module_record 表作为通用 JSON 存储的局限性

**问题**：大量模块（licenses、rag、sensitive-words、notify-channels、risk-events、runtime、backups、versions、model-config-* 等）的数据存储在 `admin_module_record` 的 `json_text` 字段中，缺乏结构化查询能力。

**影响**：
- 无法对 JSON 字段进行高效搜索（keyword 搜索只能匹配整个 JSON 字符串）
- 数据一致性无法通过数据库约束保证
- 大量数据时性能下降

---

### 6.5 前端通用模块页的批量操作对只读模块仍可能被绕过

**问题**：虽然前端已隐藏只读模块的批量操作按钮，但后端 `AdminRealDataModuleService.save()` 仍会抛出异常。如果用户通过 API 直接调用，仍会收到 400 错误。

**建议**：后端也应返回明确的错误信息。

---

## 7. 可优化部分

### 7.1 前端优化

| 项目 | 说明 |
|------|------|
| API 路径统一 | 所有 API 文件中的 URL 路径应统一使用相对路径，依赖 `VITE_API_URL` baseURL |
| 错误处理 | 添加全局错误拦截，区分网络错误、认证错误、业务错误，提供用户友好的提示 |
| 加载状态 | 部分页面缺少骨架屏或加载动画 |
| TypeScript 类型 | 很多 API 响应使用 `any` 类型，应定义完整的接口类型 |
| 路由权限 | 前端路由守卫验证菜单权限，但菜单数据来自后端 `/admin/menus`，需确认该接口正常工作 |

### 7.2 后端优化

| 项目 | 说明 |
|------|------|
| TenantContext 统一 | admin 端和 user 端的 JWT 过滤器应统一设置 TenantContext |
| 异常处理 | 区分业务异常和系统异常，返回不同的 HTTP 状态码 |
| 日志级别 | 生产环境应将 `log.warn` 中的异常堆栈级别调整为 ERROR |
| API 版本化 | 建议对 `/admin-api` 添加版本号，如 `/admin-api/v1/` |
| 接口文档 | 缺少 Swagger/OpenAPI 文档 |
| 单元测试 | 项目中未发现测试代码 |

### 7.3 部署优化

| 项目 | 说明 |
|------|------|
| 健康检查 | 已有 `/admin-api/ops/liveness` 和 `/readiness`，可配置 Docker healthcheck |
| Prometheus 指标 | 已有 `/admin-api/ops/prometheus` 端点，可配置 Grafana 监控 |
| 配置管理 | 敏感配置（密钥、密码）应通过环境变量或配置中心管理，不硬编码 |

---

## 8. 修复优先级建议

### P0 - 立即修复（影响核心功能）
1. **修复 TenantContext 为 null 的问题**（[3.1](#31-严重tenantcontext-在-admin-端为-null-导致功能异常)）—— 影响 Dashboard 数据、操作日志、热销统计等多个功能
2. **注册 notify-channels 和 risk-events 模块**到 ModuleCatalog（[4.1](#41-严重notify-channels-和-risk-events-模块无后端数据)）—— 用户看到错乱的列定义

### P1 - 高优先级（影响用户体验）
3. **实现短信/邮箱配置后端接口**（[4.2](#42-中等短信邮箱配置后端接口缺失)）—— 或移除前端对应页面
4. **通知发送记录添加筛选参数支持**（[4.3](#43-中等通知发送记录缺少筛选功能)）
5. **修复 GlobalExceptionHandler 区分异常类型**（[3.2](#32-中等globalexceptionhandler-吞掉所有异常细节)）

### P2 - 中优先级（改善质量）
6. **ModuleCatalog 兜底逻辑改为返回 404**（[3.5](#35-轻微modulecatalog-兜底逻辑存在安全隐患)）
7. **添加 API 接口文档（Swagger/OpenAPI）**
8. **生产环境密钥配置**（[5.1-5.5](#5-安全问题分析)）

### P3 - 低优先级（长期优化）
9. **添加单元测试**
10. **admin_module_record 表数据迁移到结构化表**（[6.4](#64-admin_module_record-表作为通用-json-存储的局限性)）
11. **DevTools 热重载配置**（[6.2](#62-服务间重启依赖)）
12. **JWT 刷新机制**（[5.7](#57-低危jwt-无刷新机制)）

---

## 附录：ModuleCatalog 注册模块清单（28 个）

| moduleKey | 标题 | 数据来源 |
|-----------|------|----------|
| users | 用户管理 | sys_user 表（专用 Service） |
| plans | 套餐管理 | billing_plan 表（专用 Service） |
| xianyu-accounts | 闲鱼账号 | xianyu_account 表（专用 Service） |
| ai-usage | AI用量 | ai_usage_log 表（专用 Service） |
| ai-token | AI Token | ai_token_ledger 表（专用 Service） |
| goods | 商品管理 | xianyu_goods 表（只读） |
| orders | 订单管理 | xianyu_trade_order 表（只读） |
| messages | 消息管理 | xianyu_message 表（只读） |
| delivery | 发货管理 | auto_delivery 表（只读） |
| auto-reply | 自动回复 | auto_reply 表（只读） |
| kami | 卡密管理 | kami_card 表（只读） |
| hot-goods | 热销商品 | hot_goods_stat 表（只读） |
| licenses | 授权管理 | admin_module_record JSON |
| rag | RAG知识库 | admin_module_record JSON |
| sensitive-words | 敏感词 | admin_module_record JSON |
| model-config-general | 通用模型 | admin_module_record JSON |
| model-config-chat | 聊天模型 | admin_module_record JSON |
| model-config-image | 图像模型1 | admin_module_record JSON |
| model-config-image-2 | 图像模型2 | admin_module_record JSON |
| model-config-image-3 | 图像模型3 | admin_module_record JSON |
| model-config-prompt | 提示词 | admin_module_record JSON |
| runtime | 运行配置 | admin_module_record JSON |
| backups | 备份管理 | admin_module_record JSON |
| versions | 版本管理 | admin_module_record JSON |
| alerts | 异常告警 | admin_module_record JSON（本次新增） |
| files | 文件管理 | admin_module_record JSON（本次新增） |
| notify-channels | 通知渠道 | 未注册（回退到 users） |
| risk-events | 风控事件 | 未注册（回退到 users） |

---

> **报告结束** — 请下一个模型按优先级顺序处理以上问题。建议优先确认 `VITE_API_URL` 环境变量值，因为它是所有 API 路径正确性的前提。