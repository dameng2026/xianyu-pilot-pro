---
name: "service-lifecycle-management"
description: "约束 AI 在修改代码后必须正确管理服务进程：先杀掉旧进程再重启，确保每个服务只有一个实例运行，并尽可能保持所有服务持续运行。Invoke when AI modifies code that affects any running service (core-api, automation-service, crawler-service, admin-web, user-web) or when AI needs to restart/recompile/redeploy any service."
---

# 服务生命周期管理 - 进程约束规则

> **强制规则**：任何 AI 模型在修改代码后若需要重启服务以验证修改效果，必须先完整阅读本文件。
> 必须遵循"先查租约 → 再杀 → 再启、单实例运行、持续在线"原则。
> 项目中可能存在大量绘画任务由多个 AI 模型并行处理，服务中断会直接导致任务失败，因此服务持续运行至关重要。
>
> **前置关卡**：杀进程前必须先经过 [service-lease-coordination](../service-lease-coordination/SKILL.md) 的 kill-gate，检查是否有他会话持有该服务端口的 active lease。若有，禁止 eviction，按该技能的冲突解决流程处理。

## 一、核心三原则（违反即为 Bug）

### 原则 1：先查租约 → 再杀 → 再启（必须）
- **杀进程前必须先查 lease**：经 [service-lease-coordination](../service-lease-coordination/SKILL.md) 的 kill-gate 检查，无 active lease 或 holder 是本会话才可杀。
- **重启任何服务前，必须先杀掉该服务已存在的进程**，再重新启动。
- 严禁在已有进程仍运行时直接启动新进程，这会导致端口冲突或多个实例同时运行。
- 严禁仅启动新进程而不清理旧进程。

### 原则 2：单实例运行（必须）
- **每个服务在任意时刻只能有一个进程在运行**，避免多个进程重复运行造成资源浪费、端口冲突、数据竞争。
- 重启前若发现服务已运行，必须先杀掉旧进程，确认端口释放后，再启动新进程。
- 启动后应验证端口确实被新进程占用，且旧进程已彻底退出。

### 原则 3：持续在线（必须）
- **所有服务应尽可能保持启动状态**，因为项目中可能同时有多个 AI 模型在并行处理绘画等长任务。
- 修改代码后允许重启服务以查看效果，但重启动作必须高效：杀进程→启动→验证存活，尽快完成。
- 严禁以"调试"为由长时间停掉某个服务，导致其他依赖该服务的并行任务失败。
- 重启失败时必须立即排查并恢复，不得让服务停留在宕机状态。

## 二、服务清单与端口映射（不得更改）

| 服务名 | 类型 | 端口 | 工作目录 | 启动命令 |
|--------|------|------|----------|----------|
| core-api | Java Spring Boot | 18080 | `apps/core-api` | `mvn package -DskipTests -q` 后 `java -jar target/xianyu-assistant-admin-backend-1.0.0.jar` |
| automation-service | Python FastAPI | 12401 | `apps/automation-service` | `python run-fast.py` |
| crawler-service | Node.js Express | 3001 | `apps/crawler-service` | `npm run dev`（开发）或 `npm start`（生产） |
| admin-web | Vue3 + Vite | 3006 | `apps/admin-web` | `pnpm dev` |
| user-web | Vue3 + Vite | 5174 | `apps/user-web` | `pnpm dev` |

## 三、标准杀进程流程（Windows PowerShell）

**通用杀进程函数**（按端口号清理，确保单实例）：

```powershell
function Stop-ServiceByPort($port) {
    # 1. 通过端口查找所有 LISTENING 进程
    $entries = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
    $killedPids = @()
    foreach ($entry in $entries) {
        $pidStr = ($entry -split '\s+')[-1]
        if ($pidStr -match '^\d+$') {
            try {
                Stop-Process -Id ([int]$pidStr) -Force -ErrorAction Stop
                $killedPids += $pidStr
            } catch {
                Write-Warning "无法杀掉 PID $pidStr (端口 $port): $($_.Exception.Message)"
            }
        }
    }
    # 2. 等待端口释放
    if ($killedPids.Count -gt 0) {
        Start-Sleep -Milliseconds 800
        Write-Host "  ->  已杀掉端口 $port 上的进程: $($killedPids -join ', ')" -ForegroundColor Yellow
    }
    # 3. 二次确认端口已释放
    $remain = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
    if ($remain) {
        Write-Warning "端口 $port 仍有进程占用，强制再次清理"
        foreach ($entry in $remain) {
            $pidStr = ($entry -split '\s')[-1]
            if ($pidStr -match '^\d+$') {
                try { Stop-Process -Id ([int]$pidStr) -Force } catch {}
            }
        }
        Start-Sleep -Milliseconds 500
    }
}

function Stop-ServiceByName($processName) {
    # 按进程名清理（如 java、python、node），仅在确认是该服务时使用
    $procs = Get-Process -Name $processName -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } while ($false)
        }
        Write-Host "  ->  已杀掉 $processName 进程" -ForegroundColor Yellow
        Start-Sleep -Milliseconds 500
    }
}
```

## 四、各服务标准重启流程

### 4.1 core-api 重启（Java Spring Boot）

```powershell
# 1. 杀掉占用 18080 端口的旧进程
Stop-ServiceByPort 18080

# 2. 重新编译并启动（在新窗口中，避免阻塞当前会话）
$workDir = "apps\core-api"
# 方式 A：完整重新编译（修改了 Java 源码后必须）
#   mvn package -DskipTests -q
#   $env:JAVA_TOOL_OPTIONS = "-Xmx512m -XX:+TieredCompilation -XX:TieredStopAtLevel=1 -XX:+UseParallelGC -Djava.awt.headless=true -Dfile.encoding=UTF-8"
#   java -jar "target\xianyu-assistant-admin-backend-1.0.0.jar"
# 方式 B：触发 DevTools 热重启（仅修改了 resources 下的配置文件）
#   (Get-Item "src\main\resources\.trigger").LastWriteTime = Get-Date

# 3. 验证存活
Start-Sleep -Seconds 3
$alive = (Invoke-WebRequest -Uri "http://localhost:18080/api/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue)
if ($alive) { Write-Host "[OK] core-api 已启动" -ForegroundColor Green }
else { Write-Warning "core-api 启动失败，需排查" }
```

**注意**：
- Java 源码修改后必须执行 `mvn package -DskipTests -q` 重新编译，不能依赖 DevTools 热重启。
- DevTools 的 `.trigger` 触发方式仅适用于 `src/main/resources/` 下配置文件修改，不适用于 Java 代码修改。
- 编译失败时必须修复，不得跳过重启步骤直接进行下一步。

### 4.2 automation-service 重启（Python FastAPI）

```powershell
# 1. 杀掉占用 12401 端口的旧进程
Stop-ServiceByPort 12401

# 2. 在新窗口启动（避免阻塞当前会话）
#   cd apps\automation-service
#   python run-fast.py
# 注意：run-fast.py 内部已实现端口清理逻辑，但仍建议外部先清理一次以确保单实例

# 3. 验证存活
Start-Sleep -Seconds 2
$alive = (Invoke-WebRequest -Uri "http://localhost:12401/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue)
if ($alive) { Write-Host "[OK] automation-service 已启动" -ForegroundColor Green }
else { Write-Warning "automation-service 启动失败" }
```

### 4.3 crawler-service 重启（Node.js）

```powershell
# 1. 杀掉占用 3001 端口的旧进程
Stop-ServiceByPort 3001

# 2. 在新窗口启动
#   cd apps\crawler-service
#   npm run dev

# 3. 验证存活
Start-Sleep -Seconds 2
$alive = (Invoke-WebRequest -Uri "http://localhost:3001/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue)
if ($alive) { Write-Host "[OK] crawler-service 已启动" -ForegroundColor Green }
else { Write-Warning "crawler-service 启动失败" }
```

### 4.4 admin-web 重启（Vue3 + Vite）

```powershell
# 1. 杀掉占用 3006 端口的旧进程
Stop-ServiceByPort 3006

# 2. 在新窗口启动
#   cd apps\admin-web
#   pnpm dev

# 3. Vite 自带 HMR，通常无需重启；仅在 package.json 依赖变更或 vite.config 修改时才需重启
```

### 4.5 user-web 重启（Vue3 + Vite）

```powershell
# 1. 杀掉占用 5174 端口的旧进程
Stop-ServiceByPort 5174

# 2. 在新窗口启动
#   cd apps\user-web
#   pnpm dev

# 3. Vite 自带 HMR，通常无需重启；仅在 package.json 依赖变更或 vite.config 修改时才需重启
```

## 五、启动后验证清单（必须执行）

每次重启服务后，必须执行存活验证，确认服务真正启动成功：

| 服务 | 验证方式 | 期望结果 |
|------|----------|----------|
| core-api | `Invoke-WebRequest http://localhost:18080/api/health` | HTTP 200 |
| automation-service | `Invoke-WebRequest http://localhost:12401/health` | HTTP 200 |
| crawler-service | `Invoke-WebRequest http://localhost:3001/health` | HTTP 200 |
| admin-web | 浏览器访问 http://localhost:3006 | 页面正常加载 |
| user-web | 浏览器访问 http://localhost:5174 | 页面正常加载 |

## 六、关键约束（违反即为 Bug）

1. **不得在未杀掉旧进程的情况下启动新进程**：会导致端口冲突或多个实例同时运行。
2. **不得使用 `Stop-ServiceByName` 杀掉所有同名进程**：会误杀其他不相关的 java/python/node 进程。必须按端口号精确定位。
3. **不得跳过启动后验证**：必须确认服务真正存活后才能继续后续工作。
4. **不得长时间让服务处于宕机状态**：重启失败必须立即排查并恢复。
5. **不得在主会话中前台启动服务**：会阻塞 AI 无法继续后续工作。必须在新窗口或后台任务中启动。
6. **Java 源码修改后不得仅用 DevTools 热重启**：必须 `mvn package` 重新编译打包。
7. **不得同时启动多个相同服务实例**：每个服务只能有一个进程在运行。
8. **修改代码后若无需重启服务即可生效（如前端 HMR），不要无故重启**：避免不必要的停机。
9. **重启前必须告知用户**：明确说明将重启哪个服务、原因、预计耗时。

## 七、启动顺序建议

首次启动或全部重启时，建议按依赖顺序启动：

```
1. core-api (18080)         ← Java 后端，最慢，先启动
2. crawler-service (3001)   ← Node 爬虫服务
3. automation-service (12401) ← Python FastAPI，依赖 core-api
4. admin-web (3006)         ← 前端管理后台
5. user-web (5174)           ← 前端用户端
```

启动间隔约 2-3 秒，避免资源争抢。core-api 首次编译约需 30-60 秒，需耐心等待。

## 八、相关文件清单

| 文件 | 作用 |
|------|------|
| `start.bat` | 项目根目录一键启动脚本（仅启动 automation-service） |
| `dev-start.bat` / `dev-start.ps1` | 完整开发环境启动脚本（启动全部 5 个服务） |
| `apps/core-api/restart.ps1` | 触发 Spring Boot DevTools 热重启 |
| `apps/automation-service/run-fast.py` | Python 服务启动脚本（内置端口清理） |
| `apps/automation-service/run-worker.py` | Python Celery worker 启动脚本 |
| `apps/crawler-service/package.json` | Node 服务启动命令定义 |
| `apps/admin-web/package.json` | admin-web 启动命令定义 |
| `apps/user-web/package.json` | user-web 启动命令定义 |
