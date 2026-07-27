# 上线前本地-商业版桥接 Token 检查规则

> **强制规则**：任何 AI 模型在执行"上线"动作前，必须先完整阅读本文件，并按本文件流程检查本地与商业版（线上）的数据同步桥接 token 是否正确配置。
> 未经 token 一致性校验，不得执行上线。本规则与 `database-migration-on-release.md`、`release-notes-workflow.md` 并行生效，三者均为上线前置条件。

## 一、背景与功能概述

项目实现了"本地 → 线上"的配置数据同步功能：本地版可将闲鱼账号 cookie、工作流、AI 客服配置、货源库、自动发货、自动回复、通知设置等全量推送到线上商业版账号。

同步链路依赖一个共享鉴权 token（`DATA_SYNC_API_TOKEN`）：

- **本地发送端**：通过 `BusinessSettingsService` 的 `data-sync-config` 默认配置预填到前端表单，作为 `X-Sync-Token` 请求头发送
- **线上接收端**：通过 `application.yml` 的 `xianyu.sync.token` 配置（环境变量 `DATA_SYNC_API_TOKEN`），由 `SyncAuthFilter` 常量时间比较校验
- **一致性要求**：两端 token 必须完全一致，否则线上接收端返回 503 拒绝同步请求

## 二、核心约束（违反即为事故级 Bug）

1. **本地与线上 token 必须一致**：本地发送端的 `targetToken` 必须与线上接收端的 `DATA_SYNC_API_TOKEN` 环境变量值完全相同。
2. **token 长度必须 ≥ 32 字符**：`StartupSecurityGuard` 的 `requireStrong` 校验要求，否则线上启动失败。
3. **token 必须包含 ≥ 4 个不同字符**：避免弱口令（如全相同字符）。
4. **不得使用占位符值**：不得使用 `replace-with`、`placeholder`、`dev-only`、`change-me` 等弱值。
5. **商业版前端不得显示数据同步板块**：`VITE_SHOW_DATA_SYNC` 在生产构建中必须为 `false`（由 `.env.production` 覆盖）。
6. **token 泄露后必须立即轮换**：若 token 被意外提交到公共仓库或泄露给未授权人员，必须同时更新本地默认配置与线上环境变量。

## 三、当前权威 Token 值

> **注意**：以下 token 为当前生效值。若需轮换，必须同步更新本文件、`BusinessSettingsService.java`、`application.yml` 三处。

```
DATA_SYNC_API_TOKEN=HIDpsuvrKSlWfczLiFTJa0Ydhqm8gx7Q
```

### 3.1 token 出现位置清单

| 位置 | 文件 | 字段 | 说明 |
|------|------|------|------|
| 本地发送端默认配置 | `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java` | `config.put("targetToken", "...")` | 预填到前端表单 |
| 本地接收端默认配置 | `apps/core-api/src/main/resources/application.yml` | `xianyu.sync.token: ${DATA_SYNC_API_TOKEN:...}` | 本地联调默认值 |
| 线上接收端环境变量 | 服务器 `/home/ubuntu/project/.env.production` | `DATA_SYNC_API_TOKEN=...` | **必须与本地一致** |

## 四、上线前 Token 一致性检查流程（强制）

### 4.1 检查本地代码中的 token

```bash
# 检查 BusinessSettingsService.java 中的 targetToken 默认值
grep -n "targetToken" apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java

# 检查 application.yml 中的 sync.token 默认值
grep -n "DATA_SYNC_API_TOKEN" apps/core-api/src/main/resources/application.yml
```

两处输出的 token 值必须完全相同，且都为 `HIDpsuvrKSlWfczLiFTJa0Ydhqm8gx7Q`。

### 4.2 检查线上服务器环境变量

```bash
# SSH 到线上服务器
ssh ubuntu@1.12.66.249

# 检查 .env.production 中的 token
cd /home/ubuntu/project
grep "^DATA_SYNC_API_TOKEN=" .env.production
```

输出必须为：
```
DATA_SYNC_API_TOKEN=HIDpsuvrKSlWfczLiFTJa0Ydhqm8gx7Q
```

### 4.3 一致性判定

| 情况 | 处理 |
|------|------|
| 本地代码 token = 线上环境变量 token | ✅ 通过，继续上线流程 |
| 本地代码 token ≠ 线上环境变量 token | ❌ **停止上线**，先同步两端 token |
| 线上未配置 `DATA_SYNC_API_TOKEN` | ❌ **停止上线**，先在 `.env.production` 中配置 |
| token 长度 < 32 或不同字符 < 4 | ❌ **停止上线**，生成新 token 并同步两端 |

### 4.4 token 轮换流程（如需更新）

1. 生成新 token：
   ```powershell
   -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
   ```

2. 同步更新三处：
   - `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java` 中的 `targetToken`
   - `apps/core-api/src/main/resources/application.yml` 中的 `${DATA_SYNC_API_TOKEN:...}` 默认值
   - 本规则文件第三节"当前权威 Token 值"

3. 更新线上服务器：
   ```bash
   # SSH 到线上服务器（国内商业版后端）
   ssh root@211.161.232.54
   cd /home/ubuntu/project
   # 编辑 .env.production，更新 DATA_SYNC_API_TOKEN=<新值>
   # 重启后端使配置生效
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production restart backend
   ```

4. 验证：本地发送端 ping 线上接收端返回 200。

## 五、商业版前端显示控制

数据同步板块仅对本地开发环境可见，商业版（线上生产）必须隐藏：

| 环境 | 文件 | `VITE_SHOW_DATA_SYNC` | 效果 |
|------|------|------------------------|------|
| 本地开发 | `apps/user-web/.env` | `true` | 显示数据同步 tab |
| 生产构建 | `apps/user-web/.env.production` | `false` | 隐藏数据同步 tab |

### 5.1 上线前验证

```bash
# 确认 .env.production 存在且 VITE_SHOW_DATA_SYNC=false
cat apps/user-web/.env.production
```

### 5.2 构建产物验证（可选）

```bash
# 构建后检查 settings-sync 是否被运行时启用
# 注：构建产物中会保留 settings-sync 字符串（静态导入），但运行时 import.meta.env.VITE_SHOW_DATA_SYNC 为 "false"
# 正确的做法是检查 .env.production 文件值
```

## 六、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java` | 本地发送端默认配置（`targetToken` 预填值） |
| `apps/core-api/src/main/resources/application.yml` | 接收端 token 默认值（`${DATA_SYNC_API_TOKEN:...}`） |
| `apps/core-api/src/main/java/com/xianyu/admin/security/SyncAuthFilter.java` | 接收端鉴权 filter（常量时间比较） |
| `apps/core-api/src/main/java/com/xianyu/admin/config/StartupSecurityGuard.java` | 启动时 token 强度校验 |
| `apps/core-api/src/main/java/com/xianyu/admin/service/DataSyncService.java` | 发送端服务（读取本地数据 + HTTPS 推送） |
| `apps/core-api/src/main/java/com/xianyu/admin/service/SyncReceiveService.java` | 接收端服务（应用同步数据） |
| `apps/user-web/.env` | 本地开发环境变量（`VITE_SHOW_DATA_SYNC=true`） |
| `apps/user-web/.env.production` | 生产构建覆盖（`VITE_SHOW_DATA_SYNC=false`） |
| `apps/user-web/src/data/nav.js` | 前端 `settingsTabs` 根据 `VITE_SHOW_DATA_SYNC` 控制显示 |
| `apps/user-web/src/App.vue` | 前端 `settingsKeys` 根据 `VITE_SHOW_DATA_SYNC` 控制路由 |
