# XianYu Assistant（闲鱼助手）

基于闲鱼官方 Web 能力的个人/商户自动化运营助手。支持多账号 Cookie 管理、即时消息实时监控、AI 智能客服自动回复、商品批量管理、商机发掘、滑块自动求解、自动发货与 Token 计费等功能。

> **声明**：本项目仅供学习研究与实践交流使用。使用前请阅读并遵守闲鱼平台相关服务协议与法律法规，勿将本项目用于任何违反平台规则或国家法律的目的。

---

## ✨ 功能特性

- **多闲鱼账号管理**：Cookie 加密存储、账号健康状态探测、WebSocket 持久化保活、Cookie 失效自动检测
- **即时消息监控**：WS 实时接收买家消息，前端 SSE 实时推送，在线自动回复（AI/关键词/规则多策略）
- **AI 客服**：支持知识库学习（RAG）与多模型接入，可配置润色关键词与禁用词，按 VIP 等级 Token 计费
- **商品管理**：批量上下架、改价、图文生成、发货信息同步
- **商机发掘**：关键词/类目/店铺维度挖掘热门商品，支持「快速（直调 MTOP）」「慢速（浏览器）」「智能」三种搜索模式与自动降级
- **滑块自动求解**：多后端支持（Playwright 原生 / patchright / CloakBrowser），60 秒冷却与成败记录，IP 代理池与 x5sec 缓存
- **自动发货/自动回复/通知设置**：多渠道（短信/邮件/Webhook/飞书）与丰富的规则模板
- **运营分析**：仪表盘、订单统计、商品数据分析、增长合伙人体系
- **多端界面**：管理后台（admin-web）与用户端（user-web），本地开发可开箱即用

## 🏗️ 技术架构

Docker Compose 单栈部署，共 10 个服务：

| 服务 | 说明 | 技术栈 |
|------|------|--------|
| `mysql` | 主业务数据库 = 8.4 LTS | MySQL |
| `redis` | 缓存 / x5sec 缓存 / 队列 | Redis 7 |
| `crawler-postgres` | 爬虫服务数据库 | PostgreSQL 16 |
| `backend` | 管理端与用户端 API（端口 18080） | Java 17 / Spring Boot |
| `automation` | 闲鱼自动化核心服务（WS 保活、消息监控、滑块触发） | Python 3.12 / FastAPI |
| `automation-worker` | 自动化后台任务（定时回复、数据同步） | Python 3.12 |
| `crawler-service` | 浏览器自动化服务（滑块求解、店铺爬取、商机搜索，端口 3001） | Node.js / Playwright / TypeScript |
| `crawler-worker` | 爬虫后台任务（xvfb 有头窗口降风控） | Node.js |
| `admin-web` | 管理后台（本机 HTTP 3006） | Vue 3 / Vite |
| `user-web` | 用户端（本机 HTTP 5174） | Vue 3 / Vite |

## 🚀 快速开始（Docker Compose）

### 环境要求

- Docker Engine 24+（含 Docker Compose v2）
- 服务器内存建议 ≥ 8 GB（浏览器自动化 + 多个服务）

### 第一步：准备环境变量

```bash
cp .env.production.example .env
```

编辑 `.env`，**必须**替换以下三个密钥（compose 启动前强制校验，长度建议 ≥ 32 字符）：

```bash
INTERNAL_API_TOKEN=replace-with-a-strong-random-token
COOKIE_CRYPTO_SECRET=replace-with-a-strong-random-secret
ADMIN_JWT_SECRET=replace-with-a-strong-random-secret
```

其余变量可保留示例默认值或按需修改。首次本地体验请额外设置：

```bash
ADMIN_SEED_ENABLED=true
```

### 第二步：启动

```bash
docker compose up -d --build
```

### 第三步：访问

| 入口 | 地址 | 默认账号 |
|------|------|----------|
| 管理后台 | http://localhost:3006 | 首次启动 seed 生成 `admin` |
| 用户端 | http://localhost:5174 | 注册 / seed 账号 |
| 后端健康 | http://localhost:18080/api/health | - |

首次启动会自动执行数据库迁移（Flyway）并初始化表结构与基础数据。`ADMIN_SEED_ENABLED=true` 时创建的默认管理员密码为 `123456`，**登录后请立即修改**。

> 本地体验完毕，建议将 `ADMIN_SEED_ENABLED` 重新设为 `false` 并重启 `backend`，避免默认密码继续生效。

## 🔐 生产部署

完整的生产发布流程（预检、数据库备份/迁移、发布门控、回滚、监控）参见：

- [docs/production-deploy.md](docs/production-deploy.md)（发布流程与部署拓扑）
- `docker-compose.prod.yml` / `scripts/prod_deploy.py`（生产 compose 与发布脚本）
- [docs/database-migrations.md](docs/database-migrations.md)（数据库迁移纪律）

生产环境必须满足：

- `.env.production` 中所有 `replace-with-*` 占位符均替换为高强度随机值
- `ADMIN_SEED_ENABLED=false`、`SCHEMA_RUNTIME_MUTATIONS_ENABLED=false`
- 上线前完成三套数据库（core / automation / crawler）备份与迁移验证

## 📁 目录结构

```
apps/
  admin-web/           # 管理后台前端（Vue 3）
  user-web/            # 用户端前端（Vue 3）
  core-api/            # 核心后端（Java Spring Boot，管理/用户 API、计费、同步）
  automation-service/  # 自动化服务（Python，WS 保活、消息监控、滑块触发、AI 回复）
  crawler-service/     # 爬虫服务（Node/Playwright，滑块求解、店铺爬取、搜索）
scripts/               # 发布、预检与契约测试脚本
deploy/                # Nginx / systemd 部署模板
docs/                  # 部署与开发文档
db/                    # 迁移清单与发布凭证模板（migrations-manifest.json）
```

## 🧪 测试与质量

仓库内置契约测试，用于保障开源发布安全与部署可运行性：

```bash
python -m pytest scripts/tests/ apps/automation-service/tests/ -q
```

同时可运行前端契约测试（`apps/user-web/scripts`、`apps/admin-web/scripts` 下的 `*.test.mjs`）。

## 📄 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议，允许自由使用、修改与分发（含商用），使用或分发时请遵守许可证要求（保留版权声明、修改文件标注等）。完整条款见 [LICENSE](LICENSE)。

## ⚖️ 免责声明

1. 本项目与闲鱼/淘宝平台无任何隶属关系。项目通过用户自有的 Cookie 与官方 Web 界面接口实现自动化，请自行承担账号使用风险。
2. 请勿将本项目用于批量注册、恶意营销、刷单等违反平台规则的行为。
3. 使用本项目即表示您知悉并同意自行承担由此产生的一切后果。