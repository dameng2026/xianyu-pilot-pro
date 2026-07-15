---
name: "service-lease-coordination"
description: "Coordinates service process access across concurrent AI sessions using time-bounded leases, preventing kill-loops where one session keeps terminating a process another session is actively using. Invoke before starting any drawing/painting/image-generation/crawling task that uses a shared backend service (crawler-service, automation-service, core-api), before killing or restarting a service process, or when repeated process-killing loops occur across sessions."
---

# 服务租约协调 - 跨会话进程占用管理

> **强制规则**：任何 AI 会话在启动长时间任务（绘画、爬取、批量生成）前，或在杀掉/重启服务进程前，必须先完整阅读本文件。
> 本技能是 [service-lifecycle-management](../service-lifecycle-management/SKILL.md) 的前置关卡：后者管"怎么杀怎么启"，本技能管"该不该杀"。

## 一、问题与机制

当多个 AI 会话并行处理绘画任务时，会出现**杀进程循环**：会话 A 为应用代码改动杀掉 crawler-service，会话 B 正在用该服务跑绘画任务，发现服务挂了就重启；A 又需要服务、又杀掉 B 刚启动的进程。如此往复，绘画任务永远跑不完。

**机制**：用项目内一个共享 JSON 文件作为**租约登记表**（lease registry）。每个会话在长时间任务前**claim 一个租约**（声明占用某服务端口的时长），任务期间**heartbeat 续期**，结束后**release 释放**。任何会话在杀进程前**必须先查登记表**，若他会有 active lease 则不得杀（eviction 禁止）。

**核心术语**（leading words，全文一致使用）：
- **lease**（租约）：会话对某服务端口的限时独占持有
- **claim**（声明）：获取租约的动作；也指登记表中一条记录
- **holder**（持有者）：当前拥有 active lease 的会话
- **eviction**（驱逐）：杀掉他人持有 lease 的进程——禁止行为
- **heartbeat**（心跳）：任务进行中续期 lease 的 expires_at

## 二、租约登记表

**文件路径**：`.trae/service-leases.json`（项目根下，所有会话共享）

**格式**：

```json
{
  "claims": [
    {
      "port": 3001,
      "session_id": "6a328e7ebca8756576da01fb",
      "started_at": "2026-06-26T20:30:00+08:00",
      "expires_at": "2026-06-26T20:40:00+08:00",
      "purpose": "drawing: 猫咪头像生成",
      "pid": 12345
    }
  ]
}
```

**字段说明**：
| 字段 | 必填 | 说明 |
|------|------|------|
| `port` | 是 | 被占用的服务端口（如 3001/12401/18080） |
| `session_id` | 是 | 当前会话 ID（从 memory topics 的 `session_id:` 获取；若未知，用 `unknown-` + 时间戳） |
| `started_at` | 是 | claim 时间，ISO 8601 带时区 |
| `expires_at` | 是 | 过期时间。默认 claim 时设为 `started_at + lease_duration` |
| `purpose` | 是 | 人类可读的任务描述，便于他会有事时协调 |
| `pid` | 否 | 占用期间实际运行的服务进程 PID，便于核验 |

**读写规则**：
- 读：随时可读，无需加锁（JSON 文件读取是原子的）
- 写：先读全量 → 修改 → 全量覆盖写回。写回前重新读一次以防他会有变更（乐观锁：比对 claims 数量，若变了则重试一次）

## 三、Claim：启动长时间任务前声明租约（必须）

**触发条件**：会话即将执行任何依赖后端服务的长时间任务，包括但不限于：
- 绘画/生图任务（调用 core-api 的生图模型，耗时常达 30-60 秒甚至更久）
- 闲鱼店铺爬取（crawler-service，Playwright 浏览器，单次数秒到数十秒）
- 批量商品关键词搜索（auto 模式可能降级到 slow 搜索，占 crawler-service）
- 工作流执行（automation-service，可能数分钟）

**步骤**：

1. **确定 lease_duration**：按任务预估耗时上浮 50% 作为安全余量。
   - 单张生图：默认 120 秒
   - 批量生图（≤5 张）：默认 300 秒
   - 店铺爬取：默认 180 秒
   - 工作流执行：默认 600 秒
   - 不确定时：默认 300 秒，宁可声明长一点

2. **读取登记表**，清理自身可能残留的 stale claim（同 session_id 且 expires_at 已过期的）。

3. **写入 claim**：追加一条记录，`started_at` = 当前时间，`expires_at` = 当前时间 + lease_duration。

4. **记录 PID**（可选但推荐）：服务启动后，把其 PID 回填到 claim 的 `pid` 字段，便于他会有事时核验进程是否真在跑。

5. **开始执行任务**。

**完成判据**：登记表中存在一条本会话的 active claim，覆盖目标端口，且 expires_at 在未来。

## 四、Heartbeat：任务进行中续期（必须）

长时间任务（>lease_duration 的 50%）执行期间，若尚未完成，必须续期，否则 lease 过期后他会有权杀进程。

**续期时机**：
- 每完成一个子步骤后（如生完一张图）
- 距 `expires_at` 不足 30 秒时

**续期动作**：把 `expires_at` 更新为 `当前时间 + 剩余预估时长上浮 50%`。更新 `pid`（若服务进程换了）。

**完成判据**：claim 的 `expires_at` 始终在未来，直到任务结束。

## 五、Release：任务结束后释放（必须）

任务完成（无论成功失败）后，立即从登记表删除本会话在该端口的 claim。不得依赖自然过期——他人会等你到过期才能动手，造成无谓等待。

**完成判据**：登记表中不再有本会话在该端口的 active claim。

## 六、Kill-Gate：杀进程前查登记表（必须）

**这是本技能最关键的关卡**。在调用 [service-lifecycle-management](../service-lifecycle-management/SKILL.md) 的 `Stop-ServiceByPort` 之前，必须执行此 gate。

**步骤**：

1. **读登记表**。

2. **查目标端口是否有 active claim**（`expires_at` 在未来）：
   - 若**无 active claim**：放行，继续走 service-lifecycle-management 的标准杀进程流程。
   - 若**有 active claim 且 holder 是本会话**：放行（自己占着自己杀，无妨），但杀前先 release 自己的 claim。
   - 若**有 active claim 且 holder 是他会话**：**禁止 eviction**。进入冲突解决流程（第八节）。

3. **清理 stale claim**：若 `expires_at` 已过期，该 claim 视为 stale，可安全忽略并删除（holder 会话可能已崩溃或忘记 release）。删除后放行。

**完成判据**：要么已放行（无 active claim 或 holder 是自身），要么进入冲突解决流程（holder 是他会话）。

## 七、Kill-Loop Guard：检测并打破循环（必须）

若会话发现自己**在 5 分钟内对同一端口杀进程 2 次以上**，立即停止杀进程。这是 kill-loop 的强信号：他会有 active lease 在跑任务。

**动作**：
1. 不再调用 `Stop-ServiceByPort`。
2. 读登记表，查 active claim。
3. 若有 active claim：等其过期，或尝试通过 `purpose` 字段联系 holder 会话协调。
4. 若无 active claim 但仍 loop：说明 holder 没声明 lease（违规）。此时可强行杀，但必须在登记表留一条 audit 记录，便于事后排查。

**完成判据**：停止盲目杀进程，转为基于登记表的协调等待。

## 八、冲突解决（holder 是他会话时）

当 kill-gate 拦截到他人 active lease 时，按以下优先级处理：

1. **等待**（首选）：若 claim 的 `expires_at` 距现在 < 60 秒，直接等其过期再杀。告知用户"等待约 N 秒，他会话任务结束后再重启"。

2. **协调**（次选）：若距过期 60-300 秒，通过 claim 的 `purpose` 字段告知用户任务性质，让用户决定是否等待或手动协调。不得擅自 eviction。

3. **强占**（末选，仅当用户明确要求且距过期 > 300 秒）：
   - 在登记表留 audit 记录：`{"action":"force-evict","port":...,"victim_session_id":...,"reason":"user-requested","at":"..."}`
   - 删除受害者的 claim
   - 写入本会话的 claim
   - 执行杀进程+重启
   - **告知用户**：已强制驱逐他会有任务，可能导致其任务失败，建议用户事后协调。

**禁止**：任何情况下不得静默 eviction。

## 九、与 service-lifecycle-management 的关系

| 职责 | 归属 |
|------|------|
| 该不该杀（lease 检查、kill-loop 检测） | **本技能** |
| 怎么杀（Stop-ServiceByPort 实现） | service-lifecycle-management |
| 怎么启（启动命令、端口） | service-lifecycle-management |
| 启动后存活验证 | service-lifecycle-management |
| claim/heartbeat/release | **本技能** |

**调用顺序**（杀进程场景）：
```
kill-gate（本技能）→ 通过 → Stop-ServiceByPort（service-lifecycle-management）→ 启动 → 验证存活
```

**调用顺序**（长任务场景）：
```
claim（本技能）→ 启动/复用服务 → 执行任务 → heartbeat（本技能）→ release（本技能）
```

## 十、关键约束（违反即为 Bug）

1. **不得跳过 kill-gate 直接杀进程**：会破坏他会有 lease 的任务。
2. **不得在长任务前不 claim**：无 claim 的任务不受保护，他人会按"无 active claim"放行杀进程。
3. **不得忘记 heartbeat**：lease 过期后保护失效。
4. **不得忘记 release**：他人会被迫等到过期才能动手，造成无谓等待。
5. **不得静默 eviction**：任何驱逐必须留 audit 记录并告知用户。
6. **不得依赖自然过期代替 release**：release 是主动行为，过期是兜底。
7. **stale claim 必须清理**：过期 claim 不占资源，发现即删。
8. **不得把 lease 当作服务独占锁**：lease 只阻止"杀进程"，不阻止"使用服务"。多个会话可同时读同一个运行中的服务，无需互相 claim。仅在需要"杀/重启"时 lease 才发挥作用。

## 十一、与 service-lifecycle-management 的集成要求

`service-lifecycle-management` 技能的"先杀后启"原则在本技能存在后修正为：

> **先查 lease → 再杀 → 再启**

即：杀进程前必须先经过本技能的 kill-gate。建议在 `service-lifecycle-management` 的标准重启流程中，把 kill-gate 检查作为第 0 步。
