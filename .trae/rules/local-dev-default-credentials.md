# 本地部署默认账号密码规则

> **强制规则**：任何 AI 模型在修改"本地部署默认账号"、"前台/后台登录账号"、"种子用户初始化"相关功能前，必须先完整阅读本文件。
> 本地部署时，前台（user-web）与后台（admin-web）登录账号密码统一为 `admin / 123456`，严禁分散配置或引入不同账号。
> 本规则与 `local-dev-no-docker.md` 并行生效，均为本地开发环境约束。

## 一、背景与功能概述

为降低本地部署与开发联调的门槛，前台（user-web，面向终端用户）与后台（admin-web，面向平台运营）共用同一套默认账号密码 `admin / 123456`。该账号由后端 core-api 在应用启动时通过"种子初始化"机制自动创建，前端登录页面在本地开发模式下自动预填，开发者无需手动注册或查阅文档即可直接登录。

## 二、核心约束（违反即为事故级 Bug）

1. **本地部署前台与后台账号密码必须统一**：均为 `admin / 123456`，不得在前台使用 `demo`、`user`、`test` 等其他用户名，不得在后台使用其他密码。
2. **默认密码必须为 `123456`**：`AuthService.DEFAULT_ADMIN_PASSWORD` 与 `UserAuthService.seedUser()` 中的密码字面量必须为 `"123456"`，不得修改为其他值。
3. **默认用户名必须为 `admin`**：前台 `sys_user` 种子记录的 `username` 必须为 `"admin"`，后台 `sys_admin_user` 种子记录的 `username` 必须为 `"admin"`。
4. **种子初始化仅限非生产环境**：`AuthService.seedAdmin()` 与 `UserAuthService.seedUser()` 内部均通过 `isProdProfile()` 拦截，**生产环境严禁执行种子初始化**。
5. **`ADMIN_SEED_ENABLED` 在本地 `.env` 必须为 `true`**：本地开发环境必须启用种子初始化，否则首次启动无法登录。
6. **`ADMIN_SEED_ENABLED` 在生产 `.env.production` 必须为 `false`**（或未设置，回退默认值 `false`）：生产环境严禁初始化默认账号。
7. **前端登录页仅在 DEV 模式预填**：admin-web 与 user-web 登录页通过 `import.meta.env.DEV` 判断，**生产构建（`vite build`）下不得预填账号密码**。
8. **不得在 SQL 迁移脚本中 INSERT 默认用户**：默认账号仅由 Java 代码（`AuthService` / `UserAuthService`）在启动时初始化，不得写入 Flyway 迁移脚本，避免污染生产数据库。

## 三、当前权威账号密码值

> **注意**：以下为当前生效值。如需轮换，必须同步更新本文件、`AuthService.java`、`UserAuthService.java` 三处。

```
前台（user-web）登录账号：admin / 123456
后台（admin-web）登录账号：admin / 123456
```

### 3.1 账号密码出现位置清单

| 位置 | 文件 | 字段/行号 | 说明 |
|------|------|-----------|------|
| 后台种子账号用户名 | `apps/core-api/src/main/java/com/xianyu/admin/service/AuthService.java` | `DEFAULT_ADMIN_USERNAME = "admin"`（第 24 行） | 后台默认管理员用户名 |
| 后台种子账号密码 | 同上 | `DEFAULT_ADMIN_PASSWORD = "123456"`（第 25 行） | 后台默认管理员密码 |
| 后台种子账号昵称 | 同上 | `DEFAULT_ADMIN_NICKNAME = "超级管理员"`（第 27 行） | 后台默认管理员昵称 |
| 后台种子账号邮箱 | 同上 | `DEFAULT_ADMIN_EMAIL = "admin@xianyu.local"`（第 28 行） | 后台默认管理员邮箱 |
| 后台演示运营账号 | 同上 | `DEMO_OPERATOR_USERNAME = "User"`（第 31 行） | 后台演示运营账号（密码同为 `123456`） |
| 前台种子账号用户名 | `apps/core-api/src/main/java/com/xianyu/admin/service/UserAuthService.java` | `seedUser()` 中 `"admin"`（第 339 行） | 前台默认用户用户名 |
| 前台种子账号密码 | 同上 | `encoder.encode("123456")`（第 335 行） | 前台默认用户密码 |
| 前台种子账号昵称 | 同上 | `"管理员"`（第 339 行） | 前台默认用户昵称 |
| 前台种子账号邮箱 | 同上 | `"admin@xianyu.local"`（第 339 行） | 前台默认用户邮箱 |
| 本地环境开关 | `.env` | `ADMIN_SEED_ENABLED=true`（第 21 行） | 本地启用种子初始化 |
| 生产环境开关 | `application.yml` | `${ADMIN_SEED_ENABLED:false}` | 生产默认关闭种子初始化 |
| admin-web 登录预填 | `apps/admin-web/src/views/auth/login/index.vue` | `formData` 第 134-137 行 | DEV 模式预填 `admin/123456` |
| user-web 登录预填 | `apps/user-web/src/pages/LoginPage.vue` | `username`/`password` 第 378-380 行 | DEV 模式预填 `admin/123456` |

## 四、种子初始化执行流程

### 4.1 后台管理员账号（sys_admin_user 表）

**入口**：`AuthService.seedAdmin()`（第 223-230 行）

```java
public void seedAdmin() {
    if (!seedEnabled || isProdProfile()) {
        return;
    }
    ensureDefaultAdminAccount();   // 创建 admin / 123456
    ensureDemoOperatorAccount();   // 创建 User / 123456（演示运营账号）
}
```

**执行条件**：
- `seedEnabled = true`（由 `ADMIN_SEED_ENABLED` 环境变量控制）
- `isProdProfile() = false`（非生产环境）

**`ensureDefaultAdminAccount()` 逻辑**（第 232-283 行）：
1. 查询 `sys_admin_user` 表是否存在 `username='admin'` 的记录
2. 若不存在：INSERT 新记录，密码为 BCrypt("123456")
3. 若存在且密码已匹配 `123456`：仅更新昵称/邮箱/角色等元数据
4. 若存在但密码为旧版 `admin123456` 或非 BCrypt 格式：迁移密码到 `123456`，并递增 `security_version`

### 4.2 前台用户账号（sys_user 表）

**入口**：`UserAuthService.seedUser()`（第 327-341 行）

```java
public void seedUser() {
    if (!seedEnabled || isProdProfile()) {
        log.info("已禁用前台演示用户初始化");
        return;
    }
    Long count = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user", Long.class);
    if (count != null && count > 0) return;

    String pwd = encoder.encode("123456");
    Long tenantId = findOrCreateDefaultTenant();
    jdbcTemplate.update(
            "INSERT INTO sys_user(username, password_hash, nickname, email, email_verified, tenant_id, status, created_time, updated_time, deleted) VALUES(?,?,?,?,1,?,1,NOW(),NOW(),0)",
            "admin", pwd, "管理员", "admin@xianyu.local", tenantId);
    log.warn("仅开发环境已初始化 sys_user 默认账户：admin / 123456，请勿用于生产");
}
```

**执行条件**：
- 同后台：`seedEnabled = true` 且非生产环境
- **仅在 `sys_user` 表为空时执行**（避免覆盖已有用户数据）

**关键约束**：`seedUser()` 仅在 `sys_user` 表完全为空时插入一条 `admin` 记录。若表中已有任何用户（包括历史的 `demo` 用户），则不会执行插入。如需从旧版 `demo` 账号迁移到 `admin` 账号，需手动清理 `sys_user` 表或手动创建 `admin` 账号。

## 五、上线前账号密码一致性检查流程（强制）

### 5.1 检查本地代码中的账号密码

```bash
# 检查后台种子账号
grep -n "DEFAULT_ADMIN_USERNAME\|DEFAULT_ADMIN_PASSWORD" apps/core-api/src/main/java/com/xianyu/admin/service/AuthService.java

# 检查前台种子账号
grep -n '"admin"\|"123456"' apps/core-api/src/main/java/com/xianyu/admin/service/UserAuthService.java

# 检查本地环境开关
grep "^ADMIN_SEED_ENABLED=" .env
```

预期输出：
- `DEFAULT_ADMIN_USERNAME = "admin"`
- `DEFAULT_ADMIN_PASSWORD = "123456"`
- `ADMIN_SEED_ENABLED=true`

### 5.2 检查生产环境配置

```bash
# SSH 到生产服务器
ssh root@211.161.232.54
cd /home/ubuntu/project

# 确认生产环境未启用种子初始化
grep "^ADMIN_SEED_ENABLED=" .env.production
```

预期输出：`ADMIN_SEED_ENABLED=false` 或该行不存在（回退默认值 `false`）。

### 5.3 一致性判定

| 情况 | 处理 |
|------|------|
| 本地 `.env` 中 `ADMIN_SEED_ENABLED=true` | ✅ 通过，本地可正常初始化默认账号 |
| 本地 `.env` 中 `ADMIN_SEED_ENABLED=false` | ❌ **本地无法登录**，需改为 `true` |
| 生产 `.env.production` 中 `ADMIN_SEED_ENABLED=false` 或未设置 | ✅ 通过，生产不初始化默认账号 |
| 生产 `.env.production` 中 `ADMIN_SEED_ENABLED=true` | ❌ **事故级 Bug**，生产环境会初始化弱密码账号，必须立即改为 `false` |
| 前台种子用户名不是 `admin` | ❌ **停止上线**，需改回 `admin` |
| 默认密码不是 `123456` | ❌ **停止上线**，需改回 `123456` |

## 六、前端登录页预填逻辑

### 6.1 admin-web 后台登录页

**文件**：`apps/admin-web/src/views/auth/login/index.vue`

```typescript
const formData = reactive({
  username: import.meta.env.DEV ? 'admin' : '',
  password: import.meta.env.DEV ? '123456' : ''
})
```

- `import.meta.env.DEV` 在 `vite dev` 模式下为 `true`，在 `vite build` 产物中为 `false`
- 生产构建后，登录页 `username` 和 `password` 均为空字符串，不会泄露默认账号

### 6.2 user-web 前台登录页

**文件**：`apps/user-web/src/pages/LoginPage.vue`

```typescript
const username = ref(import.meta.env.DEV ? 'admin' : '')
const password = ref(import.meta.env.DEV ? '123456' : '')
```

- 同 admin-web，仅在 DEV 模式预填

### 6.3 关键约束

- **不得移除 `import.meta.env.DEV` 判断**：直接写 `username: 'admin'` 会导致生产构建泄露默认账号
- **不得将账号密码硬编码到 `.env.production` 或构建产物中**：生产环境不得存在默认账号

## 七、从旧版 demo 账号迁移

历史版本中，前台 `sys_user` 种子账号为 `demo / 123456`。若本地数据库已存在 `demo` 账号，`seedUser()` 因 `sys_user` 表非空而不会创建 `admin` 账号。迁移方式：

### 7.1 方式一：清空 sys_user 表（仅本地开发）

```sql
-- 本地 MySQL（仅开发环境，会清除所有前台用户）
TRUNCATE TABLE sys_user;
```

重启 core-api 后，`seedUser()` 会自动创建 `admin / 123456`。

> **警告**：此操作仅限本地开发环境，**生产环境严禁执行 TRUNCATE**（违反 `database-migration-on-release.md` 规则）。

### 7.2 方式二：手动创建 admin 账号

```sql
-- 本地 MySQL，手动插入 admin 账号（BCrypt hash 需从 Java 生成或复用现有 demo 账号的 hash）
INSERT INTO sys_user(username, password_hash, nickname, email, email_verified, tenant_id, status, created_time, updated_time, deleted)
SELECT 'admin', password_hash, '管理员', 'admin@xianyu.local', 1, tenant_id, 1, NOW(), NOW(), 0
FROM sys_user WHERE username='demo' LIMIT 1;
```

### 7.3 方式三：直接修改 demo 账号

```sql
-- 本地 MySQL，将 demo 账号改名为 admin
UPDATE sys_user SET username='admin', nickname='管理员', email='admin@xianyu.local' WHERE username='demo';
```

## 八、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/core-api/src/main/java/com/xianyu/admin/service/AuthService.java` | 后台种子账号初始化（`seedAdmin` / `ensureDefaultAdminAccount`） |
| `apps/core-api/src/main/java/com/xianyu/admin/service/UserAuthService.java` | 前台种子账号初始化（`seedUser`） |
| `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java` | `sys_admin_user` / `sys_user` 表结构创建（不含数据初始化） |
| `apps/core-api/src/main/resources/application.yml` | `admin.seed.enabled` 配置（`${ADMIN_SEED_ENABLED:false}`） |
| `.env` | 本地开发环境变量（`ADMIN_SEED_ENABLED=true`） |
| `apps/admin-web/src/views/auth/login/index.vue` | 后台登录页（DEV 模式预填 `admin/123456`） |
| `apps/user-web/src/pages/LoginPage.vue` | 前台登录页（DEV 模式预填 `admin/123456`） |
