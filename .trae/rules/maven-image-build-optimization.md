# Maven 镜像构建加速规则

> **强制规则**：任何 AI 模型在执行"涉及 core-api 后端构建/部署"动作前，必须先完整阅读本文件。
> 每次 Maven 镜像构建必须控制在 10 分钟以内；超过 10 分钟即为事故级流程 Bug，必须排查并采用本文件规定的加速方案。
> 本规则与 `database-migration-on-release.md`、`data-sync-bridge-token.md`、`maintenance-mode-deployment.md`、`release-notes-workflow.md` 并行生效，均为上线前置条件。

## 一、背景与问题概述

### 1.1 问题现象

项目部署到国内商业版服务器时，core-api 后端 Docker 镜像构建经常耗时 30 分钟以上，严重影响上线效率和用户体验：
- 维护模式横幅需要持续显示，用户长时间看到"系统更新中"
- 占用服务器 CPU/内存/带宽资源
- 部署窗口变长，增加风险
- AI 模型在等待构建过程中容易超时

### 1.2 根因分析

当前 `apps/core-api/Dockerfile` 的构建流程：

```dockerfile
FROM maven:3.9.16-eclipse-temurin-17 AS build
# ... 配置阿里云镜像源 ...
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline   # ← 瓶颈1：下载所有依赖
COPY src ./src
RUN mvn -q -DskipTests package                  # ← 瓶颈2：编译+打包

FROM eclipse-temurin:17-jre-jammy
# ... 运行时镜像 ...
COPY --from=build /app/target/xianyu-assistant-admin-backend-*.jar app.jar
```

**三大瓶颈**：

| 瓶颈 | 原因 | 耗时占比 |
|------|------|---------|
| 依赖下载 | 每次构建都执行 `dependency:go-offline`，Spring Boot 全家桶 + 第三方依赖合计几百 MB | ~70% |
| 编译打包 | `mvn package` 触发完整编译、资源处理、打包流程 | ~20% |
| 镜像层失效 | Dockerfile 其他层变化导致 Maven 缓存层失效，依赖需重新下载 | ~10% |

**关键问题**：即使 `pom.xml` 未变化，只要 Dockerfile 中 `pom.xml` 之前的任何一层发生变化（如镜像源配置），Maven 缓存层就会失效，导致所有依赖重新下载。

### 1.3 影响范围

- **构建时间长**：每次部署 Maven 镜像构建 20-40 分钟
- **资源占用高**：构建期间服务器 CPU 满载，影响其他容器
- **维护窗口长**：用户长时间看到维护横幅
- **部署风险高**：构建失败需要排查，延长不可用时间

## 二、核心约束（违反即为流程 Bug）

1. **Maven 镜像构建必须控制在 10 分钟以内**：从 `docker build` 开始到镜像就绪，总耗时不得超过 10 分钟。超过即为流程 Bug，必须采用本文件的加速方案。
2. **优先使用本地预构建方案**：日常部署必须使用方案 A（本地预构建 jar + 服务器只构建运行时镜像），构建时间应 < 2 分钟。
3. **兜底方案必须可用**：服务器构建必须配置 BuildKit 缓存挂载（方案 B），确保本地构建失败时服务器构建仍能在 5 分钟内完成。
4. **禁止在服务器上重复下载依赖**：不得使用未配置缓存的原始 Dockerfile 进行服务器构建。
5. **pom.xml 变化时必须更新依赖缓存**：`pom.xml` 变化后，必须重建依赖基础镜像或刷新 BuildKit 缓存，不得依赖过期的缓存。
6. **构建失败必须排查根因**：构建失败时必须查看完整日志，不得盲目重试。常见根因：网络问题、依赖冲突、磁盘空间不足、内存不足。
7. **构建产物必须验证**：构建完成后必须验证 jar 文件存在且大小合理（通常 80-120 MB），不得直接信任构建成功标志。

## 三、加速方案

### 方案 A：本地预构建 jar + 服务器只构建运行时镜像（推荐，< 2 分钟）

**原理**：在本地（Windows 开发机）执行 `mvn package` 生成 jar，服务器只负责将 jar 复制到 JRE 镜像中，完全跳过 Maven 依赖下载和编译。

**适用场景**：日常部署，本地有 JDK 17 环境。

**文件**：`apps/core-api/Dockerfile.prebuilt`

```dockerfile
# 运行时镜像：直接使用本地预构建的 jar，跳过 Maven 构建
# 使用方法：
#   1. 本地执行：mvn -f apps/core-api/pom.xml -DskipTests package
#   2. 服务器构建：docker build -f apps/core-api/Dockerfile.prebuilt -t xianyu-admin-backend:latest apps/core-api/
# 构建时间：< 30 秒

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
# 直接复制本地构建好的 jar（构建上下文为 apps/core-api/）
COPY target/xianyu-assistant-admin-backend-*.jar app.jar
USER 10001:10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**部署流程**：

```powershell
# 1. 本地构建 jar（约 1-2 分钟）
cd apps\core-api
mvn -DskipTests package

# 2. 验证 jar 存在
if (Test-Path target\xianyu-assistant-admin-backend-*.jar) {
    Get-Item target\xianyu-assistant-admin-backend-*.jar | Select-Object Name, Length
} else {
    Write-Error "jar 构建失败"
    exit 1
}

# 3. 上传源码到服务器（包含 target/ 目录）
scp -r apps\core-api root@211.161.232.54:/home/ubuntu/project/apps/

# 4. 服务器构建镜像（约 30 秒）
ssh root@211.161.232.54 "cd /home/ubuntu/project && docker build -f apps/core-api/Dockerfile.prebuilt -t xianyu-admin-backend:latest apps/core-api/"

# 5. 重启容器
ssh root@211.161.232.54 "cd /home/ubuntu/project && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate backend"
```

**优点**：
- 构建时间 < 2 分钟（本地 1 分钟 + 服务器 30 秒）
- 不依赖服务器网络
- 不依赖 Maven 仓库可用性
- 服务器资源占用低

**缺点**：
- 本地必须有 JDK 17 + Maven 环境
- 本地操作系统与服务器不同时需注意路径问题（Windows 反斜杠）

### 方案 B：BuildKit 缓存挂载（兜底，5 分钟内）

**原理**：使用 Docker BuildKit 的 `--mount=type=cache` 将 Maven 本地仓库持久化为构建缓存，只在 `pom.xml` 变化时重新下载依赖。

**适用场景**：本地构建失败、CI/CD 环境、首次部署。

**文件**：`apps/core-api/Dockerfile`（修改现有 Dockerfile）

```dockerfile
# syntax=docker/dockerfile:1.4
FROM maven:3.9.16-eclipse-temurin-17 AS build
WORKDIR /app
# 配置阿里云 Maven 镜像源
RUN mkdir -p /root/.m2 && cat > /root/.m2/settings.xml <<'EOF'
<settings>
  <mirrors>
    <mirror>
      <id>aliyun</id>
      <mirrorOf>central</mirrorOf>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
EOF
# 使用 BuildKit 缓存挂载，依赖只在 pom.xml 变化时重新下载
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 mvn -q -DskipTests package

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
COPY --from=build --chown=app:app /app/target/xianyu-assistant-admin-backend-*.jar app.jar
USER 10001:10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**部署流程**：

```bash
# 服务器启用 BuildKit 构建（首次约 5-8 分钟，后续 1-3 分钟）
ssh root@211.161.232.54 "cd /home/ubuntu/project && DOCKER_BUILDKIT=1 docker build -f apps/core-api/Dockerfile -t xianyu-admin-backend:latest apps/core-api/"
```

**优点**：
- 标准做法，无需额外文件
- 依赖持久化缓存，后续构建快速
- 适合 CI/CD 环境

**缺点**：
- 首次构建仍慢（5-8 分钟）
- 缓存可能被 `docker builder prune` 清理
- 需要启用 BuildKit

### 方案 C：预构建依赖基础镜像（长期方案，< 2 分钟）

**原理**：定期构建包含所有 Maven 依赖的基础镜像 `xianyu-maven-deps:<pom-hash>`，主 Dockerfile FROM 这个基础镜像。

**适用场景**：`pom.xml` 变化不频繁的场景。

**文件 1**：`apps/core-api/Dockerfile.deps`

```dockerfile
# 依赖基础镜像：包含所有 Maven 依赖
# pom.xml 变化时重新构建此镜像
# 使用方法：docker build -f Dockerfile.deps -t xianyu-maven-deps:latest .
FROM maven:3.9.16-eclipse-temurin-17
WORKDIR /app
RUN mkdir -p /root/.m2 && cat > /root/.m2/settings.xml <<'EOF'
<settings>
  <mirrors>
    <mirror>
      <id>aliyun</id>
      <mirrorOf>central</mirrorOf>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
EOF
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
```

**文件 2**：`apps/core-api/Dockerfile`（修改为 FROM 依赖镜像）

```dockerfile
# 主构建镜像：FROM 依赖基础镜像，只编译源码
FROM xianyu-maven-deps:latest AS build
WORKDIR /app
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
COPY --from=build --chown=app:app /app/target/xianyu-assistant-admin-backend-*.jar app.jar
USER 10001:10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**部署流程**：

```bash
# 1. pom.xml 变化时，重建依赖镜像（约 5-8 分钟，每月 1-2 次）
ssh root@211.161.232.54 "cd /home/ubuntu/project && docker build -f apps/core-api/Dockerfile.deps -t xianyu-maven-deps:latest apps/core-api/"

# 2. 日常构建（约 1-2 分钟，只编译源码）
ssh root@211.161.232.54 "cd /home/ubuntu/project && docker build -f apps/core-api/Dockerfile -t xianyu-admin-backend:latest apps/core-api/"
```

**优点**：
- 日常构建极快（1-2 分钟）
- 依赖镜像可复用
- 易于回滚到旧依赖版本

**缺点**：
- 需要维护两个 Dockerfile
- `pom.xml` 变化时需手动重建依赖镜像
- 依赖镜像占用磁盘空间

## 四、方案选择决策树

```
开始部署
  │
  ├─ 本地有 JDK 17 + Maven？
  │   ├─ 是 → 使用方案 A（本地预构建 jar）
  │   │       构建时间：< 2 分钟
  │   │
  │   └─ 否 → 继续判断
  │
  ├─ pom.xml 是否变化？
  │   ├─ 是 → 使用方案 B（BuildKit 缓存挂载）
  │   │       构建时间：5-8 分钟（首次）/ 1-3 分钟（后续）
  │   │
  │   └─ 否 → 使用方案 C（预构建依赖镜像）
  │           构建时间：1-2 分钟
  │
  └─ 紧急回滚 → 使用方案 A（本地预构建 jar）
                  构建时间：< 2 分钟
```

## 五、本地预构建详细流程（推荐）

### 5.1 环境准备（一次性）

```powershell
# 1. 安装 JDK 17（如已安装可跳过）
winget install Microsoft.OpenJDK.17

# 2. 安装 Maven（如已安装可跳过）
winget install Apache.Maven

# 3. 验证版本
java -version    # 应显示 17.x
mvn -version     # 应显示 3.9.x
```

### 5.2 日常部署流程

```powershell
# 步骤 1：本地构建 jar（约 1-2 分钟）
cd g:\源码\xianyu-assistant-package-temp\apps\core-api
mvn -DskipTests package

# 步骤 2：验证 jar（应显示 80-120 MB）
Get-Item target\xianyu-assistant-admin-backend-*.jar | Select-Object Name, @{N='SizeMB';E={[math]::Round($_.Length/1MB,2)}}

# 步骤 3：打包源码（包含 target/ 目录）
cd g:\源码\xianyu-assistant-package-temp
Compress-Archive -Path apps\core-api\Dockerfile.prebuilt, apps\core-api\target, apps\core-api\src -DestinationPath core-api-bundle.zip -Force

# 步骤 4：上传到服务器
scp core-api-bundle.zip root@211.161.232.54:/tmp/

# 步骤 5：服务器解压并构建镜像（约 30 秒）
ssh root@211.161.232.54 'cd /home/ubuntu/project && \
  unzip -o /tmp/core-api-bundle.zip -d apps/core-api-prebuilt/ && \
  cp apps/core-api-prebuilt/apps/core-api/Dockerfile.prebuilt apps/core-api/ && \
  cp -r apps/core-api-prebuilt/apps/core-api/target apps/core-api/ && \
  docker build -f apps/core-api/Dockerfile.prebuilt -t xianyu-admin-backend:latest apps/core-api/ && \
  rm -rf apps/core-api-prebuilt /tmp/core-api-bundle.zip'

# 步骤 6：重启容器
ssh root@211.161.232.54 'cd /home/ubuntu/project && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate backend'
```

### 5.3 兜底流程（本地构建失败时）

如果本地 `mvn package` 失败（依赖冲突、编译错误等），回退到方案 B：

```bash
# 服务器使用 BuildKit 构建（约 5-8 分钟）
ssh root@211.161.232.54 'cd /home/ubuntu/project && DOCKER_BUILDKIT=1 docker build -f apps/core-api/Dockerfile -t xianyu-admin-backend:latest apps/core-api/'
```

## 六、构建时间监控

### 6.1 构建计时

每次构建必须计时并记录：

```bash
# 服务器构建计时
ssh root@211.161.232.54 'cd /home/ubuntu/project && time docker build -f apps/core-api/Dockerfile.prebuilt -t xianyu-admin-backend:latest apps/core-api/'
```

### 6.2 时间阈值

| 方案 | 预期时间 | 告警阈值 | 事故阈值 |
|------|---------|---------|---------|
| 方案 A（本地预构建） | < 2 分钟 | > 5 分钟 | > 10 分钟 |
| 方案 B（BuildKit 缓存） | 1-3 分钟（缓存命中） | > 8 分钟 | > 15 分钟 |
| 方案 B（BuildKit 首次） | 5-8 分钟 | > 12 分钟 | > 20 分钟 |
| 方案 C（预构建依赖） | 1-2 分钟 | > 5 分钟 | > 10 分钟 |

超过告警阈值必须排查原因，超过事故阈值必须立即切换方案。

### 6.3 常见慢构建原因

| 原因 | 现象 | 解决方案 |
|------|------|---------|
| Maven 仓库网络慢 | 下载依赖耗时长 | 检查阿里云镜像可用性，或使用方案 A |
| Docker 缓存失效 | 依赖重新下载 | 检查 Dockerfile 层顺序，使用 BuildKit 缓存 |
| 磁盘空间不足 | 构建中途失败 | `docker system prune -f` 清理空间 |
| 内存不足 | Maven OOM | 增加 `MAVEN_OPTS=-Xmx2g` |
| CPU 满载 | 编译极慢 | 停止其他容器，或使用方案 A |
| pom.xml 依赖膨胀 | 下载量大 | 检查是否有不必要的依赖 |

## 七、Dockerfile 维护规范

### 7.1 文件清单

| 文件 | 用途 | 维护频率 |
|------|------|---------|
| `apps/core-api/Dockerfile` | 标准构建（方案 B/C） | `pom.xml` 变化时 |
| `apps/core-api/Dockerfile.prebuilt` | 本地预构建（方案 A） | 极少变化 |
| `apps/core-api/Dockerfile.deps` | 依赖基础镜像（方案 C） | `pom.xml` 变化时 |

### 7.2 Dockerfile 层顺序原则

1. **不变层在前**：镜像源配置、基础包安装等不变或极少变化的层放在前面
2. **依赖层在中**：`pom.xml` 和依赖下载放在中间
3. **源码层在后**：`src/` 复制和编译放在最后

这样源码变化时不会导致依赖层缓存失效。

### 7.3 镜像标签规范

```bash
# 生产镜像
xianyu-admin-backend:latest          # 当前生产版本
xianyu-admin-backend:<git-sha-7>     # 按 Git SHA 标记，便于回滚
xianyu-admin-backend:<release-id>    # 按 Release ID 标记

# 依赖镜像（方案 C）
xianyu-maven-deps:latest             # 最新依赖镜像
xianyu-maven-deps:<pom-sha-7>        # 按 pom.xml SHA 标记
```

## 八、上线前构建检查流程

### 8.1 构建前检查

```powershell
# 1. 确认本地 JDK/Maven 环境（方案 A）
java -version
mvn -version

# 2. 确认服务器磁盘空间（> 5 GB 可用）
ssh root@211.161.232.54 "df -h /var/lib/docker | tail -1"

# 3. 确认服务器 Docker 正常
ssh root@211.161.232.54 "docker info | grep 'Server Version'"

# 4. 确认 Dockerfile 存在
Test-Path apps\core-api\Dockerfile.prebuilt
```

### 8.2 构建中监控

```powershell
# 本地构建监控
$buildStart = Get-Date
mvn -DskipTests package
$buildDuration = (Get-Date) - $buildStart
Write-Host "本地构建耗时: $($buildDuration.TotalSeconds) 秒"
if ($buildDuration.TotalMinutes -gt 5) {
    Write-Warning "本地构建超过 5 分钟，检查依赖缓存"
}
```

### 8.3 构建后验证

```powershell
# 1. 验证 jar 文件
$jar = Get-Item apps\core-api\target\xianyu-assistant-admin-backend-*.jar
if ($jar.Length -lt 50MB -or $jar.Length -gt 200MB) {
    Write-Error "jar 大小异常: $([math]::Round($jar.Length/1MB,2)) MB"
    exit 1
}
Write-Host "jar 大小正常: $([math]::Round($jar.Length/1MB,2)) MB"

# 2. 验证镜像大小
ssh root@211.161.232.54 "docker images xianyu-admin-backend:latest --format '{{.Size}}'"

# 3. 验证容器启动
ssh root@211.161.232.54 "docker logs xianyu-admin-backend --tail 20 2>&1 | Select-String 'Started XianyuAdminApplication'"
```

## 九、迁移计划

### 9.1 阶段一：立即生效（本次部署后）

1. ✅ 创建 `apps/core-api/Dockerfile.prebuilt` 文件
2. ✅ 创建本规则文件
3. ⏳ 下次部署开始使用方案 A

### 9.2 阶段二：优化 Dockerfile（本周内）

1. 修改 `apps/core-api/Dockerfile` 启用 BuildKit 缓存挂载（方案 B）
2. 验证 BuildKit 缓存命中
3. 记录构建时间基线

### 9.3 阶段三：长期优化（本月内）

1. 评估是否需要方案 C（预构建依赖镜像）
2. 集成到 `scripts/prod_deploy.py` 部署脚本
3. 添加构建时间监控告警

## 十、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/core-api/Dockerfile` | 标准 Maven 构建 Dockerfile（方案 B/C） |
| `apps/core-api/Dockerfile.prebuilt` | 本地预构建 Dockerfile（方案 A，待创建） |
| `apps/core-api/Dockerfile.deps` | 依赖基础镜像 Dockerfile（方案 C，待创建） |
| `apps/core-api/pom.xml` | Maven 项目配置文件 |
| `apps/core-api/target/` | 本地构建产物目录 |
| `scripts/prod_deploy.py` | 生产部署脚本 |
| `scripts/deploy-prod.ps1` | Windows 部署脚本 |
| `docs/production-deploy.md` | 生产部署文档 |
| `.trae/rules/maintenance-mode-deployment.md` | 维护模式规则 |
| `.trae/rules/database-migration-on-release.md` | 数据库迁移规则 |

## 十一、关键约束汇总（违反即为 Bug）

1. **Maven 镜像构建必须 < 10 分钟**：超过即为流程 Bug，必须采用本文件的加速方案。
2. **优先使用方案 A（本地预构建）**：日常部署必须使用本地预构建 jar + 服务器只构建运行时镜像。
3. **兜底方案必须可用**：服务器构建必须配置 BuildKit 缓存挂载，确保本地构建失败时服务器构建仍能快速完成。
4. **构建必须计时**：每次构建必须记录耗时，超过阈值必须排查。
5. **构建产物必须验证**：jar 大小应在 80-120 MB 之间，镜像大小应在 300-500 MB 之间。
6. **pom.xml 变化时必须更新缓存**：依赖缓存或依赖镜像必须与 `pom.xml` 同步。
7. **禁止盲目重试**：构建失败必须查看日志排查根因，不得盲目重试。
8. **磁盘空间必须充足**：构建前必须确认服务器 `/var/lib/docker` 有 > 5 GB 可用空间。
