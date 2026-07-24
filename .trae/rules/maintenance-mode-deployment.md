# 上线维护模式横幅开关规则

> **强制规则**：任何 AI 模型在执行"上线/部署"动作前，必须先完整阅读本文件。
> 上线开始时必须立即开启维护横幅，上线结束（无论成功或失败）必须关闭维护横幅。
> **未关闭维护横幅即为事故级 Bug**——用户会看到"系统更新中"提示但实际服务已恢复，造成困惑。
> 本规则与 `database-migration-on-release.md`、`data-sync-bridge-token.md`、`release-notes-workflow.md` 并行生效，均为上线前置与收尾条件。

## 一、背景与功能概述

项目频繁更新（基本每天一次，每次约一小时），更新期间后端服务可能短暂不可用。为避免用户困惑，上线时在前台所有页面（PC 端、移动端、登录页）顶部显示一条持久横幅，提示"项目正在更新中，期间部分功能可能暂时不可用，属于正常情况，预计一小时内结束"。

维护状态存储于 Redis，由部署操作方（AI 模型遵循本规则）通过 `redis-cli` 切换：

- **前端**：`MaintenanceBanner.vue` 组件每 60 秒轮询 `GET /api/maintenance/status`，`enabled=true` 时显示横幅
- **后端**：`MaintenanceController` 公开端点读取 Redis 返回状态，Redis 不可达时降级为 `enabled=false`（不锁死前台）
- **状态存储**：Redis key `xianyu:maintenance:enabled` / `xianyu:maintenance:message` / `xianyu:maintenance:until`

## 二、核心约束（违反即为事故级 Bug）

1. **上线开始时必须开启维护模式**：部署流程的第一步（拉取代码/重建镜像之前）就执行开启命令，确保用户在服务开始波动前就看到提示。
2. **上线结束时必须关闭维护模式**：部署成功后立即执行关闭命令。**这是最重要的约束**——忘记关闭会导致服务已恢复但用户仍看到"更新中"提示。
3. **上线失败时也必须关闭维护模式**：部署中断、回滚、报错后，必须执行关闭命令。否则用户被卡在维护提示里但实际后端已回滚到可用版本。
4. **关闭操作必须验证**：执行关闭命令后，必须 `GET xianyu:maintenance:enabled` 确认返回 `(nil)` 或 `false`，才算真正关闭。
5. **不设 TTL**：维护状态不设过期时间，由部署操作方显式关闭。避免因 TTL 导致维护中途横幅消失。
6. **Redis 容器名固定**：命令中的容器名必须为 `xianyu-crawler-redis`，不得更改。

## 三、上线流程（强制）

### 3.1 第一步：开启维护模式（部署开始前）

```bash
# SSH 到线上服务器
ssh ubuntu@1.12.66.249
cd /home/ubuntu/project

# 提取 Redis 密码（避免密码出现在命令历史进程列表）
RP=$(grep -E '^REDIS_PASSWORD=' .env.production | cut -d= -f2-)

# 开启维护模式（必需）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli SET xianyu:maintenance:enabled true

# 可选：设置自定义文案（不设置则前端使用默认文案）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli SET xianyu:maintenance:message "正在升级订单管理功能"

# 可选：设置预计结束时间（ISO 格式，前端会显示为 HH:MM）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli SET xianyu:maintenance:until "2026-07-24T15:00:00"

# 验证已开启（应返回 true）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli GET xianyu:maintenance:enabled
```

### 3.2 中间步骤：执行正常部署流程

开启维护模式后，按正常流程执行部署（拉取代码、重建镜像、重启容器、数据库迁移等）。此期间用户会看到维护横幅。

### 3.3 最后一步：关闭维护模式（部署完成后，无论成功或失败）

```bash
# 关闭维护模式（删除所有相关 key）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli DEL xianyu:maintenance:enabled xianyu:maintenance:message xianyu:maintenance:until

# 验证已关闭（应返回 (nil)）
docker exec -e REDISCLI_AUTH="$RP" xianyu-crawler-redis redis-cli GET xianyu:maintenance:enabled
```

**验证标准**：`GET xianyu:maintenance:enabled` 返回 `(nil)` 表示已关闭。若仍返回 `true`，说明关闭失败，必须重试关闭命令。

### 3.4 异常场景处理

| 情况 | 处理 |
|------|------|
| 部署成功 | ✅ 执行 3.3 关闭维护模式 |
| 部署失败/中断 | ❌ **仍必须执行 3.3 关闭维护模式**，再排查问题 |
| 部署回滚 | ❌ **仍必须执行 3.3 关闭维护模式**，回滚后服务已恢复可用 |
| Redis 容器本身需重建 | ⚠️ Redis 重建后 key 会丢失（无 TTL 且 AOF 可能未持久化最新值），此时维护状态自动消失，等价于已关闭；重建完成后若仍在部署，需重新执行 3.1 开启 |
| 忘记是否关闭 | 🔍 执行 `GET xianyu:maintenance:enabled` 检查，返回非 `(nil)` 则立即关闭 |

## 四、本地开发联调

本地开发时可通过相同命令测试横幅显示效果（本地 Redis 密码默认 `dev-only-redis-password-change-me`，见 docker-compose.yml）：

```bash
# 开启（本地）
docker exec -e REDISCLI_AUTH="dev-only-redis-password-change-me" xianyu-crawler-redis redis-cli SET xianyu:maintenance:enabled true

# 关闭（本地）
docker exec -e REDISCLI_AUTH="dev-only-redis-password-change-me" xianyu-crawler-redis redis-cli DEL xianyu:maintenance:enabled xianyu:maintenance:message xianyu:maintenance:until
```

前端轮询间隔 60 秒，开启后最多 60 秒内横幅出现；关闭后最多 60 秒内横幅消失。路由切换时会立即刷新一次。

## 五、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/core-api/src/main/java/com/xianyu/admin/controller/MaintenanceController.java` | 公开查询端点 `GET /api/maintenance/status` |
| `apps/core-api/src/main/java/com/xianyu/admin/service/MaintenanceService.java` | 读取 Redis 维护状态，Redis 不可达时降级为未维护 |
| `apps/core-api/src/main/java/com/xianyu/admin/dto/MaintenanceStatusVO.java` | 状态 VO：`{ enabled, message, until }` |
| `apps/core-api/src/main/java/com/xianyu/admin/security/UserJwtAuthFilter.java` | 白名单含 `/api/maintenance/status`（无需登录） |
| `apps/user-web/src/api/maintenance.js` | 前端 API 封装，失败降级为未维护 |
| `apps/user-web/src/components/MaintenanceBanner.vue` | 横幅组件，自治轮询（60 秒 + hashchange 刷新） |
| `apps/user-web/src/App.vue` | PC 端 app-shell + 登录页 auth-page-boundary 挂载横幅 |
| `apps/user-web/src/components/MobileLite.vue` | 移动端 m-topbar 后挂载横幅 |
| `docker-compose.yml` | Redis 容器 `xianyu-crawler-redis` 定义 |
