# 上线数据库迁移与数据保护规则

> **强制规则**：任何 AI 模型在执行"上线"动作前，必须先完整阅读本文件。
> 上线必须做好数据库迁移，严禁清空现有数据。未经数据库备份与迁移验证，不得执行上线。
> 本规则与 `release-notes-workflow.md` 并行生效，二者均为上线前置条件。

## 一、背景与功能概述

线上版曾发生用户配置的货源库在服务器更新后丢失的事故，根因是更新服务器过程中未按规范执行数据库迁移，导致已有业务数据被清空。本规则用于固化"上线必迁移、迁移不清空"的纪律，避免此类事故再次发生。

项目已具备完整的数据库迁移基础设施，本规则是对既有机制的强制执行约束：

- **迁移清单**：`db/migrations-manifest.json`（唯一权威清单，含 sha256 校验与策略）
- **迁移脚本目录**：
  - core-api：`apps/core-api/src/main/resources/db/migration/`
  - automation-service：`apps/automation-service/migrations/`
  - crawler-service：`apps/crawler-service/migrations/`
- **迁移凭证**：`db/migration-evidence.example.json`（上线前需产出对应的 evidence JSON）
- **生产环境开关**：`SCHEMA_RUNTIME_MUTATIONS_ENABLED: "false"`（生产禁止运行时 schema 变更）
- **清单策略**：`immutableAfterRelease: true`、`productionRuntimeSchemaMutation: false`、`rollback: "restore-or-forward-fix-only"`

涉及三个数据库：

| 数据库 ID | 引擎 | 归属服务 | 数据卷 |
|-----------|------|---------|--------|
| `core_mysql` | MySQL 8.4 | core-api | `mysql_data` |
| `automation_mysql` | MySQL 8.4 | automation-service | `mysql_data`（共享） |
| `crawler_postgres` | PostgreSQL 16 | crawler-service | `crawler_pg_data` |

## 二、核心约束（违反即为事故级 Bug）

1. **严禁清空现有数据**：不得执行任何会丢弃用户业务数据的操作，包括但不限于 `DROP TABLE`、`DROP DATABASE`、`TRUNCATE`、不带 `WHERE` 的 `DELETE`、`DROP COLUMN`（除非有明确的数据迁移补偿）。
2. **严禁 `docker compose down -v`**：`-v` 参数会删除命名数据卷（`mysql_data`、`crawler_pg_data`），导致全部数据库数据丢失。停止/重启容器只能使用 `docker compose down`（不带 `-v`）或 `docker compose restart`。
3. **严禁 Flyway `clean`**：不得在非开发环境执行 `flyway clean` 或任何调用 `flyway.clean()` 的逻辑，该命令会删除整个 schema。
4. **严禁重建数据卷**：不得 `docker volume rm` 已有数据卷，不得在 docker-compose 中改变已有数据卷的挂载路径或卷名。
5. **严禁运行时 schema 变更**：生产环境 `SCHEMA_RUNTIME_MUTATIONS_ENABLED` 必须保持 `"false"`，所有 schema 变更只能通过版本化迁移脚本在维护窗口内执行。
6. **迁移脚本必须幂等且仅追加**：使用 `CREATE TABLE IF NOT EXISTS`、`ADD COLUMN`（带存在性检查）等非破坏性 DDL；已发布迁移脚本不可修改（`immutableAfterRelease: true`），新增变更只能追加新版本号脚本。

## 三、上线前数据库迁移流程（强制）

### 3.1 评估是否需要迁移

1. 对比代码差异，检查 `apps/core-api/src/main/resources/db/migration/`、`apps/automation-service/migrations/`、`apps/crawler-service/migrations/` 三个目录是否新增了迁移脚本。
2. 若本次上线未新增任何迁移脚本，且仅修改前端/纯逻辑代码，跳过 3.2~3.4，但仍需执行 3.5 的数据卷持久性检查。
3. 若新增了迁移脚本，必须完整执行 3.2~3.4。

### 3.2 备份所有数据库（上线前必做）

上线前必须对三个数据库做完整逻辑备份，并记录备份文件的 sha256：

```bash
# MySQL（core_mysql + automation_mysql 共享实例，按库分别导出）
mysqldump -h <host> -u <user> -p --single-transaction --routines --triggers --set-gtid-purged=OFF \
  core_db > backup_core_<timestamp>.sql
mysqldump -h <host> -u <user> -p --single-transaction --routines --triggers --set-gtid-purged=OFF \
  automation_db > backup_automation_<timestamp>.sql

# PostgreSQL（crawler_postgres）
pg_dump -h <host> -U <user> -Fc -f backup_crawler_<timestamp>.dump crawler_db
```

备份产物必须：
- 保存到独立于部署目录的备份存储（不得放在会被部署覆盖的路径下）
- 计算 sha256 并记录到 migration-evidence JSON
- 保留至下一次成功上线之后方可清理

### 3.3 校验迁移清单完整性

```bash
# 校验 manifest 中的 sha256 与实际迁移脚本一致
python scripts/validate_migrations.py   # 或项目既有的清单校验命令
```

校验内容：
- `db/migrations-manifest.json` 中每个 migration 的 `sha256` 必须与磁盘文件实际 sha256 一致
- 版本号必须连续（`requireContiguousVersions: true`）
- 不得存在已发布版本被修改的情况（`immutableAfterRelease: true`）
- 若新增了迁移脚本，必须同步追加到 `migrations-manifest.json` 并填入正确 sha256

### 3.4 执行迁移并产出 evidence

迁移必须在维护窗口内通过审批门控执行（`execution: "reviewed-maintenance-window-only"`）：

1. 在生产执行迁移（core-api 通过 Flyway 自动执行；automation-service、crawler-service 通过各自 `migrate` 命令执行）
2. 验证迁移后 schema 与预期一致
3. 产出 `migration-evidence.json`，每个数据库必须包含：
   - `backup.status = "verified"` 且有 `sha256`
   - `restore.status = "passed"`（restore drill 验证通过）
4. 将 evidence JSON 路径传给部署脚本（`prod_deploy.py --migration-evidence <path>`）

### 3.5 数据卷持久性检查（每次上线必做）

每次上线前必须确认 Docker 数据卷未被意外清除：

```bash
# 确认数据卷存在且非空
docker volume inspect mysql_data crawler_pg_data
docker run --rm -v mysql_data:/data alpine sh -c 'ls -la /data | head'
docker run --rm -v crawler_pg_data:/data alpine sh -c 'ls -la /data | head'
```

若数据卷为空或不存在，立即停止上线，先从最近备份恢复数据。

## 四、迁移脚本编写规范

### 4.1 文件命名

沿用 Flyway 约定：`V<版本号>__<下划线描述>.sql`，版本号连续递增。

| 服务 | 当前最新版本 | 下一个版本 |
|------|-------------|-----------|
| core-api | V1.17 | V1.18 |
| automation-service | V1.9 | V1.10 |
| crawler-service | V1.1 | V1.2 |

### 4.2 允许的 DDL（仅追加、非破坏性）

- `CREATE TABLE IF NOT EXISTS ...`
- `ALTER TABLE ... ADD COLUMN ...`（建议带 `IF NOT EXISTS` 或先检查 information_schema）
- `CREATE INDEX ...`（建议 `IF NOT EXISTS`）
- `INSERT INTO ... SELECT ...`（用于回填默认值，必须可重入）
- `UPDATE ... WHERE ...`（必须有 WHERE，且能幂等执行）

### 4.3 禁止的 DDL（破坏性）

- `DROP TABLE` / `DROP DATABASE`
- `TRUNCATE`
- `DROP COLUMN` / `DROP INDEX`（如确需删除，必须先评估数据迁移补偿，并经人工审批）
- `ALTER TABLE ... MODIFY` 改变列类型导致数据截断的写法
- `RENAME TABLE`（可能破坏现有应用连接）

### 4.4 新增迁移脚本后的清单同步

新增迁移脚本后，必须：
1. 计算脚本文件的 sha256
2. 在 `db/migrations-manifest.json` 对应 database 的 `migrations` 数组末尾追加条目
3. 填写 `version`、`description`、`path`、`sha256`、`risk`（一般为 `expand`）、`rollback`（一般为 `restore`）

## 五、关键约束汇总（违反即为 Bug）

1. **上线必须先备份数据库**：三个数据库（core_mysql、automation_mysql、crawler_postgres）都要备份，备份要计算 sha256 并记录到 evidence。
2. **严禁清空数据**：不得 DROP/TRUNCATE/不带 WHERE 的 DELETE，不得 `docker compose down -v`，不得 `flyway clean`。
3. **数据卷不得删除**：`mysql_data`、`crawler_pg_data` 必须保持持久化，不得重建、改名、改挂载路径。
4. **迁移脚本仅追加不修改**：已发布版本不可改，新变更追加新版本。
5. **生产禁止运行时 schema 变更**：`SCHEMA_RUNTIME_MUTATIONS_ENABLED` 保持 `"false"`。
6. **新增迁移必须同步 manifest**：否则清单校验失败，部署脚本会拒绝上线。
7. **evidence 必须完整**：backup 和 restore drill 均需 verified/passed，否则 `prod_deploy.py` 不得放行。

## 六、相关文件清单

| 文件 | 作用 |
|------|------|
| `db/migrations-manifest.json` | 迁移清单（权威，含 sha256 与策略） |
| `db/migration-evidence.example.json` | 迁移凭证模板 |
| `apps/core-api/src/main/resources/db/migration/` | core-api 迁移脚本目录 |
| `apps/automation-service/migrations/` | automation-service 迁移脚本目录 |
| `apps/crawler-service/migrations/` | crawler-service 迁移脚本目录 |
| `docker-compose.prod.yml` | 生产 compose（数据卷定义） |
| `docker-compose.yml` | 基础 compose（数据卷 `mysql_data`、`crawler_pg_data`） |
| `scripts/prod_deploy.py` | 部署脚本（含 `--migration-evidence` 门控） |
| `apps/crawler-service/tests/migrationPolicy.test.ts` | 迁移策略测试 |
