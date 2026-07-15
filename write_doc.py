import os

target = r'G:\源码\项目借鉴\xianyu-assistant-opensource\HANDOFF_EXECUTION_DOC.md'

content = r"""# 开源版重构 — 安全/审计/UX 执行文档

> **交接对象**：下一个执行模型
> **项目路径**：G:\源码\项目借鉴\xianyu-assistant-opensource
> **原项目路径（只读）**：g:\源码\xianyu-assistant-package-temp
> **创建日期**：2026-07-06
> **状态**：Phase 1-11 已完成，本文档为增量优化阶段

---

## 一、项目背景与核心约束

| 约束 | 说明 |
|------|------|
| 网站登录 | 单用户（只有 admin，无注册），通过 env ADMIN_USERNAME / ADMIN_PASSWORD_HASH 配置 |
| 闲鱼账号管理 | 多账号（admin 可管理多个闲鱼账号），xianyu_account 表无 user_id 字段 |
| 原项目只读 | 不得修改 g:\源码\xianyu-assistant-package-temp 内任何文件 |
| 已移除模块 | 商机发掘、工作流、工作流任务、生图调用链路、VIP/套餐/支付/授权码/计费 |
| RAG | 保留完整功能（知识库 CRUD + 文档上传/分块/向量化/检索） |

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) + MySQL + Redis |
| 前端 | Vue 3 (script setup, JavaScript, 无 TypeScript) + Vite + 自研组件库 |
| 爬虫 | Node.js 20 + TypeScript + Playwright (仅滑块验证 + 二维码登录) |
| 部署 | Docker Compose（5 服务：mysql / redis / api / crawler / web） |

---

## 二、关键文件索引

### 后端核心文件

| 文件 | 作用 |
|------|------|
| apps/api/app/main.py | FastAPI 入口，lifespan + CORS + 异常处理 + 路由注册 |
| apps/api/app/core/config.py | Pydantic Settings，所有配置项 |
| apps/api/app/core/security.py | bcrypt 密码 + JWT 令牌 |
| apps/api/app/core/database.py | SQLAlchemy async engine + session |
| apps/api/app/core/response.py | ResultObject 统一响应包装 |
| apps/api/app/core/camel.py | CamelModel 基类（snake_case <-> camelCase） |
| apps/api/app/models/entities.py | SQLAlchemy ORM 实体（所有表模型） |
| apps/api/app/api/v1/api.py | 路由聚合，注册所有 router |
| apps/api/app/api/v1/deps.py | get_current_user 依赖（Bearer token 解析） |
| apps/api/app/api/v1/routes/auth.py | 单用户登录路由（Phase 5-6，前缀 /auth） |
| apps/api/app/api/v1/routes/login.py | 旧登录路由（Phase 4，有致命 bug，引用已删除的 SysUser/SysLoginToken） |
| apps/api/app/api/v1/routes/system.py | 旧系统路由（含多个子 router，有致命 bug） |
| apps/api/app/api/v1/routes/operation_log.py | 操作日志路由（Phase 5-6，前缀 /operation-logs） |
| apps/api/app/api/v1/routes/internal.py | 内部接口（qrlogin，需 INTERNAL_API_TOKEN） |
| apps/api/app/schemas/auth.py | 旧认证 DTO（LoginReqDTO / RegisterReqDTO 等） |

### 前端核心文件

| 文件 | 作用 |
|------|------|
| apps/web/src/App.vue | 根组件，路由管理 + 认证守卫 + SSE |
| apps/web/src/pages/LoginPage.vue | 登录页（需精简） |
| apps/web/src/pages/ForgotPasswordPage.vue | 忘记密码页（单用户模式无意义，需移除） |
| apps/web/src/api/auth.js | 认证 API（路径不匹配后端） |
| apps/web/src/utils/request.js | axios 封装，拦截器 |
| apps/web/src/utils/auth.js | token 存取（localStorage） |
| apps/web/src/pages/admin/*.vue | 5 个管理页面（Phase 9 新建） |
"""

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Part1 written: {os.path.getsize(target)} bytes")