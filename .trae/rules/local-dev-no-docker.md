# 本地开发无需 Docker 规则

> **强制规则**：任何 AI 模型在执行"本地启动/运行/调试"动作时，必须先完整阅读本文件。
> 本机已原生安装 MySQL、Redis(Memurai)、PostgreSQL，作为 Windows 系统服务自启动运行。
> **本地开发严禁依赖 Docker**——不得用 `docker compose` 启动数据库，不得建议用户安装 Docker Desktop，
> 不得在排查本地启动问题时把"启动 Docker"作为前置步骤。

## 一、背景

本机（Windows）已通过原生安装方式部署项目所需的全部数据库与中间件，作为系统服务开机自启：

| 服务 | 实际进程 | 安装路径 | 监听端口 | 系统服务名 |
|------|---------|---------|---------|-----------|
| MySQL | mysqld.exe | `C:\Program Files\mysql\bin\mysqld.exe` | 3306 | `MySQL`（Automatic） |
| Redis | memurai-run.exe（Memurai，Redis 协议兼容实现） | `C:\Program Files\Redis\` | 6379 | Memurai（Automatic） |
| PostgreSQL | postgres.exe | `C:\Program Files\PostgreSQL\16\bin\` | 5432 | `postgresql-x64-16`（Automatic） |

`dev-start.ps1` 中 `docker compose -f docker-compose.infrastructure.yml up -d` 那一步对本机无效（`docker` 命令未安装），
脚本会打印 `[!] Docker not available, skip databases` 警告并继续——**这是预期的、可忽略的**，数据库已由系统服务提供。

## 二、核心约束（违反即为 Bug）

1. **本地开发严禁依赖 Docker**：不得执行 `docker compose up`、`docker run`、`docker exec` 等命令。
2. **不得建议安装 Docker Desktop**：本机已具备全部所需数据库，无需 Docker。
3. **不得在排查步骤中把"启动 Docker"作为前置**：当服务连不上数据库时，应直接检查 MySQL/Redis/PostgreSQL 系统服务是否在运行（`Get-Service MySQL,postgresql-x64-16`）。
4. **`dev-start.ps1` 中的 Docker 警告可忽略**：`[!] Docker not available, skip databases` 不影响本地开发。
5. **数据库连接凭据固定**：使用下表凭据，不得修改 `application.yml` / `config.py` / `.env` 中的数据库连接信息。

## 三、本地数据库连接凭据（权威）

### 3.1 MySQL（端口 3306）

| 字段 | core-api 使用 | automation-service 使用 |
|------|--------------|------------------------|
| host | localhost | localhost |
| port | 3306 | 3306 |
| user | `root` | `xianyu` |
| password | `123456` | `xianyu_pass` |
| database | `xianyu_assistant_admin` | `xianyu_assistant_admin` |

- 配置来源：core-api `apps/core-api/src/main/resources/application.yml` 第 53-71 行
- 配置来源：automation-service `apps/automation-service/app/core/config.py` 第 40-44 行
- `xianyu` 用户已由本地 DBA 创建，仅授权 `xianyu_assistant_admin.*`

### 3.2 Redis（端口 6379）

| 字段 | 值 |
|------|---|
| host | localhost |
| port | 6379 |
| password | （空） |

- 配置来源：core-api `application.yml` 第 72-77 行（`${REDIS_HOST:localhost}` / `${REDIS_PORT:6379}` / `${REDIS_PASSWORD:}`）
- 本地 Redis 无密码，生产环境通过 `REDIS_PASSWORD` 注入

### 3.3 PostgreSQL（端口 5432，crawler-service 使用）

| 字段 | 值 |
|------|---|
| host | localhost |
| port | 5432 |
| user | `crawler` |
| password | `crawler_pass` |
| database | `xianyu_crawler` |

- 配置来源：crawler-service `apps/crawler-service/src/db/index.ts` 第 62-73 行
- `.env` 文件中 `CRAWLER_DB=xianyu_crawler` / `CRAWLER_DB_USER=crawler` / `CRAWLER_DB_PASSWORD=crawler_pass` / `CRAWLER_DB_PORT=5432`

## 四、本地数据库管理

### 4.1 检查服务状态

```powershell
Get-Service MySQL, postgresql-x64-16
Get-Process memurai* -ErrorAction SilentlyContinue
```

### 4.2 启动/停止/重启数据库服务

```powershell
# MySQL
Start-Service MySQL
Stop-Service MySQL
Restart-Service MySQL

# PostgreSQL
Start-Service postgresql-x64-16
Stop-Service postgresql-x64-16
Restart-Service postgresql-x64-16

# Redis (Memurai) - 通过其启动目录中的脚本或服务管理器
# Memurai 通常作为服务运行，可通过 services.msc 管理
```

### 4.3 连接数据库

```powershell
# MySQL（root）
& "C:\Program Files\mysql\bin\mysql.exe" -uroot -p123456 xianyu_assistant_admin

# MySQL（xianyu）
& "C:\Program Files\mysql\bin\mysql.exe" -uxianyu -pxianyu_pass xianyu_assistant_admin

# PostgreSQL
$env:PGPASSWORD = 'crawler_pass'
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -U crawler -d xianyu_crawler

# Redis
& "C:\Program Files\Redis\redis-cli.exe"
```

## 五、本地启动流程（无需 Docker）

直接运行项目根目录的启动脚本即可，**忽略其中 Docker 警告**：

```powershell
# 在项目根目录
powershell -ExecutionPolicy Bypass -File .\dev-start.ps1 -NoPause
```

该脚本会：
1. 检查环境（Java/Maven/Node/Python）
2. 跳过 Docker 数据库步骤（打印警告，可忽略）
3. 检查 npm/pip 依赖
4. 在 5 个独立窗口启动 5 个服务：
   - core-api（Spring Boot，端口 18080）
   - automation-service（FastAPI，端口 12401）
   - crawler-service（Node.js，端口 3001）
   - admin-web（Vite dev，端口 3006）
   - user-web（Vite dev，端口 5174）

## 六、关键文件清单

| 文件 | 作用 |
|------|------|
| `dev-start.ps1` | 项目启动脚本（第 343-360 行的 Docker 步骤对本机无效，可忽略警告） |
| `docker-compose.infrastructure.yml` | 仅用于其他开发者环境，本机不使用 |
| `apps/core-api/src/main/resources/application.yml` | core-api 数据库连接配置 |
| `apps/automation-service/app/core/config.py` | automation-service 数据库连接配置 |
| `apps/crawler-service/src/db/index.ts` | crawler-service 数据库连接配置 |
| `.env` | 本地环境变量（MYSQL_PORT=3306 / REDIS_PORT=6379 / CRAWLER_DB_PORT=5432） |

## 七、与生产部署的关系

本规则仅约束**本地开发环境**。生产服务器（`211.161.232.54`）仍使用 Docker Compose 部署全部服务（包括数据库），
具体见 `docker-compose.prod.yml` 与 `maintenance-mode-deployment.md` 规则。本地无需 Docker 不代表生产无需 Docker。
