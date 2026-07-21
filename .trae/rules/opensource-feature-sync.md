# 开源版功能同步约束规则

> **强制规则**：任何 AI 模型在执行"向开源版同步功能"动作前，必须先完整阅读本文件。
> 未经能力区分度评估，不得将本项目（商业版）的滑块求解能力同步到开源版。
> 本规则与 `release-notes-workflow.md`、`database-migration-on-release.md`、`data-sync-bridge-token.md` 并行生效，均为功能同步前置条件。

## 一、背景与目的

本项目（商业版）一直保持更新迭代，而开源版作为引流与品牌建设入口已具备基础能力。为保持商业版相对开源版的能力区分度，吸引流量与付费转化到商业版，需对"商业版 → 开源版"的功能同步进行约束。

**核心目标**：
- 保护商业版的差异化竞争力，避免被同步功能稀释商业价值
- 明确开源版本地路径，使用户未来只需说"同步某功能"即可由 AI 直接定位目标，无需重复提供地址
- 对关键差异化能力（如滑块求解）建立"禁止同步"清单

## 二、开源版地址（无需用户再次提供）

> **权威路径**：今后用户表示要"向开源版同步某功能"时，AI 直接使用以下路径作为开源版根目录，无需向用户询问。

| 项 | 值 |
|----|----|
| 开源版根目录 | `G:\源码\项目借鉴\xianyu-assistant-opensource` |
| 开源版后端（Python） | `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api` |
| 开源版前端（Web） | `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\web` |
| 开源版爬虫（Node） | `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\crawler` |
| 开源版迁移脚本 | `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\migrations` |

### 2.1 路径使用约定

- 用户说"同步某功能到开源版"时，AI 应：
  1. 在本项目（商业版，`g:\源码\xianyu-assistant-package-temp`）中定位该功能的源文件
  2. 在开源版对应目录中定位同源文件（按目录映射关系查找）
  3. 比较双方差异，判断是否属于"禁止同步清单"中的能力
  4. 不在禁止清单内时，按"四、同步流程"执行
- 若开源版对应目录不存在目标文件，AI 可按本项目的目录结构在开源版创建对应文件，但必须遵循开源版已有的代码风格、依赖约束（如开源版无 `policy.js`、无 Java 网关、无 admin-web）

### 2.2 目录映射关系

| 商业版目录 | 开源版对应目录 | 说明 |
|-----------|---------------|------|
| `apps/automation-service` | `apps/api` | Python 后端服务（开源版为单体 FastAPI） |
| `apps/crawler-service` | `apps/crawler` | Node 爬虫服务 |
| `apps/user-web` | `apps/web` | 前端用户界面 |
| `apps/admin-web` | （无对应） | 开源版无独立管理端，管理能力内置于 `apps/web` 的 admin 页面 |
| `apps/core-api` | （无对应） | 开源版无 Java 网关，所有路由在 `apps/api` 中以 Python 实现 |

## 三、禁止同步清单（事故级红线）

### 3.1 滑块求解能力（严禁同步）

**严禁将本项目（商业版）的滑块求解能力同步到开源版。** 开源版已有基础滑块求解能力（见 3.2），但能力弱于商业版，需保持此区分度。

#### 商业版独有增强（不得同步到开源版）

| 增强能力 | 商业版位置 | 说明 |
|---------|-----------|------|
| 账号绑定代理（全自动固定出口） | `apps/crawler-service/src/crawler/sliderSolver.ts` 的 `SlideSolveOptions.proxy` | 商业版支持按账号绑定代理 IP，开源版无此能力 |
| profile 选择策略（persistent / seed / temp） | `apps/crawler-service/src/crawler/sliderSolver.ts` 的 `SlideSolveOptions.profileStrategy` | 商业版支持三种浏览器 profile 策略，开源版仅基础模式 |
| 半自动兜底（全自动失败后保留浏览器窗口供人工拖拽） | `apps/crawler-service/src/crawler/sliderSolver.ts` 的 `SlideSolveOptions.semiAutoFallback` | 商业版支持失败后 120 秒人工兜底，开源版无此能力 |
| Python 脚本调用路径 | `apps/crawler-service/sliderSolve.py` | 商业版支持通过 Python 调用滑块求解，开源版无此调用路径 |
| policy.js 安全策略 | `apps/crawler-service/src/policy.ts` | 商业版有 URL 白名单、错误脱敏等安全策略，开源版无此依赖 |
| 自动化服务侧求解器（含 Java 网关联动） | `apps/automation-service/app/services/captcha_solver.py` + `apps/core-api/.../AdminCaptchaSolveRecordController.java` | 商业版有完整的求解记录、统计、管理端 UI，开源版仅基础记录 |
| 管理端求解记录页面 | `apps/admin-web/src/views/admin/captcha-records/index.vue` | 商业版管理端可视化查看求解记录，开源版无此页面 |
| ws_client 滑块触发联动 | `apps/automation-service/app/services/ws_client.py` 中的滑块检测逻辑 | 商业版 WebSocket 收到滑块触发时自动调用求解，开源版联动逻辑较弱 |

#### 开源版当前能力基线（不得增强）

开源版滑块求解仅保留以下基础能力，**任何增强都视为违反本规则**：

| 基础能力 | 开源版位置 |
|---------|-----------|
| Playwright 有头浏览器访问 `https://www.goofish.com/im` | `apps/crawler/src/sliderSolver.ts` 的 `DEFAULT_TARGET_URL` |
| 基础 Baxia 滑块组件检测（`#nc_1` / `.nc_wrapper` / `iframe#baxia-dialog` 等） | `apps/crawler/src/sliderSolver.ts` 的 `BAXIA_SELECTORS` |
| 基础反检测脚本（webdriver / chrome / plugins / WebGL / Canvas 指纹覆盖） | `apps/crawler/src/sliderSolver.ts` 的反检测脚本 |
| 模拟人工拖动（先快后慢、随机抖动、人类轨迹） | `apps/crawler/src/sliderSolver.ts` 的拖动逻辑 |
| 多场景处理（加载转圈、点击框体重试、刷新弹窗、登录页跳转） | `apps/crawler/src/sliderSolver.ts` 的场景处理 |
| Python 侧基础求解器 | `apps/api/app/services/captcha_solver.py` |

### 3.2 其他可能加入禁止清单的能力

> 后续如需新增其他禁止同步的能力，按"五、规则维护"流程追加到本节。

| 能力（占位） | 商业版位置 | 禁止原因 |
|-------------|-----------|---------|
| （暂无） | - | - |

## 四、同步流程（针对不在禁止清单的功能）

### 4.1 评估同步范围

1. 用户表示要"同步某功能到开源版"时，AI 首先判断该功能是否属于"三、禁止同步清单"。
2. 若属于禁止清单，**立即停止**，向用户说明该能力属于商业版差异化能力，不同步。
3. 若不属于禁止清单，按 4.2 继续执行。

### 4.2 差异对比与最小化同步

1. 在本项目（商业版）中定位该功能的全部相关文件（含路由、服务、前端、迁移脚本、配置）。
2. 在开源版对应目录中定位同源文件（按 2.2 目录映射关系）。
3. 仅同步"功能本身"所需的代码变更，**不同步以下商业版独有内容**：
   - Java 网关（`apps/core-api`）相关代码 —— 开源版无 Java 网关，需将网关逻辑用 Python 在 `apps/api` 中实现
   - admin-web 管理端页面 —— 开源版管理能力内置于 `apps/web`，需适配到开源版的 admin 页面结构
   - 商业版独有的安全策略（`policy.js` / `policy.ts`）—— 开源版无此依赖，需移除相关 import 或内联基础实现
   - 商业版独有的数据同步桥接（`DATA_SYNC_API_TOKEN` / `SyncAuthFilter` 等）—— 开源版不应有此能力
   - 商业版独有的按次计费强制逻辑（`model-config-general` 强制 per_call）—— 开源版计费策略独立，按开源版现有逻辑处理

### 4.3 同步前检查清单

同步前必须确认：

- [ ] 目标功能不在"三、禁止同步清单"中
- [ ] 已在开源版对应目录定位同源文件（或确认需新建）
- [ ] 已移除商业版独有依赖（policy.js / Java 网关 / admin-web / 数据同步桥接 / 按次计费强制）
- [ ] 同步后的代码符合开源版代码风格（无 `policy.js` import、无 `automation-service` 路径引用、无 Java 网关代理调用）
- [ ] 同步后的代码不引入商业版独有配置项（如 `DATA_SYNC_API_TOKEN`、`SCHEMA_RUNTIME_MUTATIONS_ENABLED` 等）
- [ ] 若涉及数据库迁移，已在 `apps/api/migrations` 追加新迁移脚本（开源版迁移命名：`<序号>_<描述>.sql`，序号连续递增）

### 4.4 同步后验证

1. 同步完成后，在开源版目录执行开源版既有的构建/测试命令（如 `npm run build` / `pytest`），确认无编译错误。
2. 向用户报告同步内容摘要：
   - 同步的功能名称
   - 同步的文件清单（商业版源 → 开源版目标）
   - 移除的商业版独有依赖清单
   - 开源版新增/修改的配置项
   - 是否涉及数据库迁移

## 五、规则维护

### 5.1 新增禁止同步能力

若后续需要将某项商业版能力列入禁止同步清单：

1. 在"三、禁止同步清单 → 3.2 其他可能加入禁止清单的能力"表格中追加条目
2. 填写：能力名称、商业版位置、禁止原因
3. 同步更新本规则文件第三节标题编号

### 5.2 修改开源版地址

若开源版仓库迁移或路径变更：

1. 更新"二、开源版地址"表格中的路径
2. 更新本规则文件第二节
3. 在更新日志中记录路径变更

## 六、关键约束汇总（违反即为 Bug）

1. **滑块求解能力严禁同步**：商业版的账号代理、profile 策略、半自动兜底、Python 调用路径、policy.js 安全策略、Java 网关联动、管理端求解记录页面，均不得同步到开源版。
2. **开源版滑块求解能力不得增强**：开源版仅保留基础 Baxia 检测、基础反检测、基础拖动、基础场景处理，任何增强都视为违反本规则。
3. **开源版地址无需用户重复提供**：用户说"同步某功能"时，AI 直接使用 `G:\源码\项目借鉴\xianyu-assistant-opensource` 作为目标根目录。
4. **同步前必须做能力区分度评估**：判断目标功能是否属于禁止清单，属于则立即停止。
5. **同步时必须移除商业版独有依赖**：policy.js / Java 网关 / admin-web / 数据同步桥接 / 按次计费强制逻辑，均不得带入开源版。
6. **同步后必须验证开源版构建**：执行开源版既有构建/测试命令，确认无编译错误。

## 七、相关文件清单

### 7.1 商业版（本项目）滑块求解相关文件

| 文件 | 作用 |
|------|------|
| `apps/crawler-service/src/crawler/sliderSolver.ts` | 滑块求解核心（含账号代理、profile 策略、半自动兜底等商业版独有增强） |
| `apps/crawler-service/sliderSolve.py` | Python 调用路径（商业版独有） |
| `apps/crawler-service/src/policy.ts` | 安全策略（商业版独有） |
| `apps/automation-service/app/services/captcha_solver.py` | 自动化服务侧求解器 |
| `apps/automation-service/app/services/ws_client.py` | WebSocket 滑块触发联动 |
| `apps/core-api/src/main/java/com/xianyu/admin/controller/AdminCaptchaSolveRecordController.java` | Java 网关求解记录接口 |
| `apps/core-api/src/main/java/com/xianyu/admin/service/AdminCaptchaSolveRecordService.java` | Java 网关求解记录服务 |
| `apps/admin-web/src/views/admin/captcha-records/index.vue` | 管理端求解记录页面 |

### 7.2 开源版滑块求解相关文件（基线，不得增强）

| 文件 | 作用 |
|------|------|
| `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\crawler\src\sliderSolver.ts` | 滑块求解核心（基础版） |
| `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\crawler\src\server.ts` | 爬虫服务入口 |
| `G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services\captcha_solver.py` | Python 侧基础求解器 |

### 7.3 同步流程相关参考文件

| 文件 | 作用 |
|------|------|
| `g:\源码\xianyu-assistant-package-temp\.trae\rules\data-sync-bridge-token.md` | 数据同步桥接 token 规则（开源版不应有此能力） |
| `g:\源码\xianyu-assistant-package-temp\.trae\rules\general-model-per-call-billing.md` | 通用模型按次计费规则（开源版计费独立） |
| `g:\源码\xianyu-assistant-package-temp\.trae\rules\database-migration-on-release.md` | 数据库迁移规则（开源版迁移独立） |
