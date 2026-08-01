# Cookie 有效账号 WS 持久化规则

> **强制规则**：任何 AI 模型在修改"滑块求解冷却时间"、"WS 重连策略"、"账号风控处理"、"滑块求解触发条件"相关功能前，必须先完整阅读本文件。
> 项目核心目标是保持所有 Cookie 有效账号的 WebSocket（WS）持久化连接，不得因滑块求解冷却或风控处理长时间阻断 WS 重连。
> 本规则与 `local-dev-default-credentials.md`、`database-migration-on-release.md` 并行生效。

## 一、核心目标

**将所有 Cookie 有效的账号保持 WS 持久化连接**。

- Cookie 有效的账号必须保持 WS 持久连接，这是项目的核心功能目标
- 任何冷却、退避、风控处理机制都不得长时间阻断 Cookie 有效账号的 WS 重连
- WS 失效但 Cookie 有效的账号必须能够快速重试恢复连接

### 1.1 冷却功能的存在目的（必须写入）

**我们给"Cookie 有效但 WS 失效"的账号设置冷却时间，其唯一目的是服务于 WS 持久化目标，而非阻断它。**

- 冷却机制的定位：避免瞬时高频触发 Baxia 风控的"保护性间隔"，不是对账号的"惩罚"
- 冷却时长的边界：**最大只有 1 分钟**。超过 1 分钟的冷却会阻止 Cookie 有效账号快速重连 WS，违背持久化目标
- 冷却与 WS 持久化的关系：60 秒冷却 → 冷却结束后立即允许再次求解 → 求解成功 → WS 重连成功 → 账号回到持久化状态
- 任何冷却配置变更都必须回答一个问题："这个冷却时长是否阻止了 Cookie 有效账号在 1 分钟内恢复 WS？" 如果答案是是，则配置错误

## 二、核心约束（违反即为事故级 Bug）

1. **滑块求解冷却时间最大 1 分钟**：所有失败原因（slider_fail/cookie_invalid/timeout/browser_crashed/其他）的冷却时间统一为 60 秒，不得设置超过 1 分钟的冷却时间。冷却的唯一目的是避免瞬时高频触发，服务于 WS 持久化。
2. **不得给 Cookie 有效但 WS 失效的账号设置长冷却**：Cookie 有效账号的 WS 重连必须快速重试，不得被长冷却机制阻断。长冷却（>60 秒）会让 Cookie 有效的账号长时间无法恢复 WS，违背核心目标。
3. **不得移除滑块求解的冷却机制**：60 秒冷却用于避免瞬时高频触发，必须保留，但不得超过 1 分钟。
4. **不得对 Cookie 有效账号做长时间滑块求解冷却**：滑块求解失败后，账号必须在 1 分钟内能够再次尝试求解，以支持 WS 持久化目标。
5. **累进冷却已废弃**：不得恢复基于 fail_count 的累进冷却（10/30/60 分钟），所有失败统一 60 秒冷却。累进冷却会让频繁失败的账号陷入长冷却，与 WS 持久化目标冲突。
6. **手动触发跳过冷却**：手动触发（manual/manual_retry）始终跳过冷却（force=True），确保用户主动操作立即响应。
7. **【核心】不得给 Cookie 有效的账号主动做滑块求解**：后续任何 AI 模型都不得主动给 Cookie 有效的账号做滑块求解。Cookie 有效且 WS 正常的账号不需要求解滑块；只有在 WS 掉线且需要恢复时才允许触发滑块求解。主动给正常账号做滑块求解会触发 Baxia 风控，导致账号被 punish。
8. **【核心】Cookie 失效的账号不得触发滑块求解**：Cookie 已失效（cookie_status=0）的账号求解滑块必然失败（页面会跳转到登录页），属于无效操作，必须在求解预检查阶段直接跳过，不得入队求解。求解滑块的唯一前提是 Cookie 仍然有效但 WS 因风控掉线。
9. **【核心】punish 状态必须尝试拖动滑块**：账号被 Baxia punish 后，拖动滑块是脱离 punish 状态的唯一途径。不得在检测到 punish 状态时立即放弃拖动——这会导致账号永远无法脱离 punish，违背 WS 持久化目标。检测到 punish 状态时仍应尝试拖动滑块（控制尝试次数避免加码）。

## 三、冷却时间配置（权威）

### 3.1 当前冷却时间

| 失败原因 | 冷却时间 | 说明 |
|---------|---------|------|
| slider_fail | 60 秒 | 滑块通过失败，快速重试 |
| cookie_invalid | 60 秒 | Cookie 失效，快速重试（等用户重新登录） |
| timeout | 60 秒 | 超时，临时性错误 |
| browser_crashed | 60 秒 | 浏览器崩溃，临时性错误 |
| service_unavailable | 60 秒 | 服务不可用，临时性错误 |
| 其他 | 60 秒 | 默认快速重试 |

### 3.2 配置文件

**文件**：`apps/automation-service/app/services/captcha_backoff.py`

```python
MAX_COOLDOWN_SEC = 60  # 最大冷却时间 1 分钟（所有失败原因统一）
```

### 3.3 禁止的配置（违反即为 Bug）

- `SLIDER_FAIL_COOLDOWN_LEVEL_1 = 600`  # 10 分钟 ❌
- `SLIDER_FAIL_COOLDOWN_LEVEL_2 = 1800`  # 30 分钟 ❌
- `SLIDER_FAIL_COOLDOWN_LEVEL_3 = 3600`  # 60 分钟 ❌
- `COOKIE_INVALID_COOLDOWN_SEC = 1800`   # 30 分钟 ❌
- 任何超过 60 秒的冷却时间 ❌

## 四、滑块求解触发条件（核心）

### 4.1 允许触发滑块求解的场景

**唯一允许的场景**：Cookie 有效（cookie_status=1）但 WS 失效（ws_status=0）的账号，且 WS 重连时检测到 Baxia 风控（FAIL_SYS_USER_VALIDATE）。

```
WS 掉线（Cookie 仍有效，cookie_status=1）
  → token_refresh 触发
  → 检测到 Baxia 风控（FAIL_SYS_USER_VALIDATE）
  → 触发滑块求解（仅在此时）
  → 求解成功 → WS 重连成功
  → 求解失败 → 60 秒冷却 → 再次尝试求解
```

### 4.2 禁止触发滑块求解的场景

| 场景 | 原因 |
|------|------|
| Cookie 失效（cookie_status=0） | 页面会跳转登录页，求解必然失败，浪费资源 |
| Cookie 有效且 WS 正常 | 主动求解会触发 Baxia 风控，导致账号被 punish |
| 主动定时求解（无 WS 掉线） | 同上，会触发风控 |
| AI 主动给账号做求解测试 | 同上，会触发风控 |

### 4.3 求解前预检查（强制）

任何滑块求解触发前必须执行以下预检查：

1. **Cookie 有效性检查**：从 `xianyu_account_runtime.cookie_status` 读取，若 `cookie_status=0` 直接拒绝求解，返回 `precheck_rejected` + `cookie_invalid`
2. **冷却期检查**：从 `xianyu_captcha_backoff` 读取，若在冷却期内直接跳过（手动触发除外）
3. **WS 状态检查**（自动触发场景）：仅在 `ws_status=0` 时才允许自动触发求解

## 五、WS 持久化与滑块求解的关系

### 5.1 关键约束

- **WS 重连不得被滑块求解冷却阻断超过 1 分钟**：即使滑块求解失败，WS 也必须在 1 分钟内能够再次尝试求解以恢复连接。
- **自动触发场景在冷却期内跳过入队**：`token_refresh`/`ws_health_check`/`ws_connect` 场景在 60 秒冷却期内直接跳过入队，不创建失败记录。冷却期过后立即允许再次求解。
- **手动触发场景跳过冷却**：用户主动点击求解按钮时，`force=True` 跳过冷却，立即处理。

### 5.2 punish 状态处理原则

账号被 Baxia punish 后：
- **不得立即放弃拖动**：punish 状态下拖动滑块是脱离 punish 的唯一方法
- **必须尝试拖动**：检测到 punish 状态时仍应尝试拖动滑块
- **控制尝试次数**：连续失败 2 次后返回，避免 Baxia 加码惩罚
- **冷却后重试**：60 秒冷却后再次尝试，给 Baxia 风控状态恢复时间

## 六、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/automation-service/app/services/captcha_backoff.py` | 冷却机制（统一 60 秒） |
| `apps/automation-service/app/services/captcha_queue.py` | 滑块求解优先级队列（自动触发冷却检查） |
| `apps/automation-service/app/services/captcha_solver.py` | 滑块求解服务（调用 assert_auto_solve_allowed + Cookie 预检查） |
| `apps/automation-service/app/services/ws_client.py` | WS 客户端（token_refresh 触发滑块求解） |
| `apps/crawler-service/sliderSolve.py` | Python patchright 滑块求解器（punish 状态下仍尝试拖动） |
| `apps/crawler-service/src/server.ts` | crawler-service 服务（Playwright + Python fallback） |
| `apps/crawler-service/src/crawler/sliderSolver.ts` | Playwright 滑块求解实现 |

## 七、上线前检查流程（强制）

### 7.1 检查冷却时间配置

```bash
grep -n "MAX_COOLDOWN_SEC\|SLIDER_FAIL_COOLDOWN\|COOKIE_INVALID_COOLDOWN" \
  apps/automation-service/app/services/captcha_backoff.py
```

预期输出：所有值均为 `60`，不得出现 `600`/`1800`/`3600` 等超过 60 的值。

### 7.2 检查累进冷却已废弃

```bash
grep -n "_cooldown_seconds" apps/automation-service/app/services/captcha_backoff.py
```

`_cooldown_seconds` 函数必须直接返回 `MAX_COOLDOWN_SEC`（60 秒），不得基于 fail_count 累进。

### 7.3 检查 Cookie 预检查逻辑

```bash
grep -n "cookie_status\|precheck_rejected\|cookie_invalid" \
  apps/automation-service/app/services/captcha_solver.py
```

预期：存在 Cookie 有效性预检查逻辑，`cookie_status=0` 时直接返回 `precheck_rejected`。

### 7.4 检查 punish 状态处理

```bash
grep -n "has_punish\|punish" apps/crawler-service/sliderSolve.py | head -20
```

预期：检测到 punish 状态时**不得立即返回**，仍应调用拖动函数尝试求解。

### 7.5 一致性判定

| 情况 | 处理 |
|------|------|
| 所有冷却时间 = 60 秒 | ✅ 通过，继续上线流程 |
| 任何冷却时间 > 60 秒 | ❌ **停止上线**，必须改为 60 秒 |
| 累进冷却逻辑被恢复 | ❌ **停止上线**，必须改为统一 60 秒 |
| 冷却机制被完全移除 | ❌ **停止上线**，60 秒冷却必须保留 |
| Cookie 失效账号仍能触发求解 | ❌ **停止上线**，必须增加 Cookie 预检查 |
| punish 状态立即放弃拖动 | ❌ **停止上线**，必须改为仍尝试拖动 |
