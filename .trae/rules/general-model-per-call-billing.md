# 通用模型按次计费规则

> **强制规则**：任何 AI 模型在修改"通用模型计费"或"前台调用通用模型"相关功能前，必须先完整阅读本文件。
> 通用模型（`model-config-general`）统一采用**按次计费**，严禁改回按 Token 量计费。
> 扣费 Token 数按用户 VIP 等级差异化（普通/VIP/SVP 三档），由「费用设置」页面的三档定价卡片统一管理。
> 前台所有调用通用模型的行为，扣费数量由后端根据用户等级查询 `ai_model_tier_price` 表决定，不得在前端硬编码。

## 一、背景与功能概述

通用模型（`model-config-general`）是平台前台 AI 功能的默认文本模型。原先按"输入 Token × 输入单价 + 输出 Token × 输出单价"计费，每次调用都需手动计算，十分麻烦且不透明。

现统一改为**按次计费 + 按用户 VIP 等级差异化定价**：
- 每调用一次通用模型，扣减固定 Token 数
- 该 Token 数由数据库表 `ai_model_tier_price` 按 `vip_level` 查询决定
- 三档配置：`normal`（普通用户 vip_level=0）、`vip`（VIP 用户 vip_level=1）、`svp`（SVP 用户 vip_level=2）
- 默认每档 3 Token，可由管理员在「费用设置」页面修改
- 扣费数量统一由后端 `AiBillingService.resolveTierTokensPerCall(userId)` 决定，前台不得硬编码

历史演进：
- v1：固定 `perCallPrice × tokenExchangeRate = 0.03 × 100 = 3 Token`，由模型配置页 `perCallPrice` 控制
- v2（当前）：按 VIP 等级三档定价，由 `ai_model_tier_price.tokens_per_call` 控制

## 二、核心约束（违反即为事故级 Bug）

1. **通用模型必须按次计费**：`model-config-general` 的 `billingMode` 必须为 `per_call`，后端 `AiBillingService.estimateUsage()` 会根据价格配置的 `module_key == "model-config-general"` 强制按次计费，**忽略调用方传入的 billingMode**。
2. **扣费 Token 数按 VIP 等级差异化**：扣费 Token 数由 `ai_model_tier_price.tokens_per_call` 字段决定，按 `vip_level` 区分三档（普通/VIP/SVP）。后端 `AiBillingService.resolveTierTokensPerCall(userId)` 按用户 `vip_level` 查询对应档位。
3. **默认扣费 3 Token**：当 `ai_model_tier_price` 表中无对应档位配置或值为 0 时，回退到 `ai_model_price_config.tokens_per_call`；若仍为空，使用代码层默认值 `3`。
4. **费用配置统一入口为「费用设置」页面**：管理端「模型配置」页面通用模型 section 已移除 `perCallPrice` 和 `tokenExchangeRate` 字段，改为提示"已迁移至费用设置页面"。**严禁在模型配置页面恢复价格字段**。
5. **扣费数量由后端决定，不得前端硬编码**：前台不得写死"扣 3 Token"，必须调用后端接口获取余额与扣费信息。管理员修改三档定价后，扣费数量自动随之变化。
6. **输入/输出/缓存单价已移除**：管理端通用模型配置中不再展示 `inputPricePer1k`、`outputPricePer1k`、`cachedInputPricePer1k`、`billingMode`、`billingUnit` 字段；后端同步时将这些字段强制清零。
7. **前台调用前必须校验 Token 余额**：当 Token 余额为 0 时，提示"Token 余额为 0，请先充值 Token 后再使用 AI 功能"并阻止调用，不得发起请求。
8. **不得为通用模型恢复按 Token 计费**：不得在管理端重新添加输入/输出单价字段，不得在后端移除 `module_key == "model-config-general"` 的按次强制逻辑。

## 三、前台调用通用模型的场景清单

以下场景均调用通用模型，每使用一次扣费 `ai_model_tier_price.tokens_per_call`（按用户 VIP 等级）个 Token：

| 场景 | 前端页面 | 前端 API | 后端路由 | scene |
|------|---------|---------|---------|-------|
| 发布商品 AI 生成描述 | `ProductPublishPage.vue` | `aiRewriteGoods` → POST `/workflow/ai/rewrite` | Python `workflow.py` | `workflow_rewrite` |
| 商机发掘标题与文案改写 | `OpportunityPage.vue` | `rewriteOpportunity` → POST `/opportunity/rewrite` | Java `AutomationProxyController` → `AiProviderService` | `opportunity_rewrite` |
| 工作流文案改写润色（测试） | `WorkflowPage.vue` | `aiRewriteGoods` → POST `/workflow/ai/rewrite` | Python `workflow.py` | `workflow_rewrite` |
| 工作流润色节点（执行时） | `automation_runtime.py` | - | Python 运行时 | `product_polish` |
| AI 客服配置测试发送 | `settings/AiCsSettings.vue` | `testAiCustomerService` → POST `/business-settings/ai-customer-service/test` | Java → Python RAG | `rag_chat` / `auto_reply` |
| 在线消息自动回复 | （后端被动触发） | - | Python `automation_runtime.py` | `auto_reply` |

> **说明**：在线消息回复由后端在收到买家消息时被动触发，前端不直接调用。后端 `AiBillingService.precheck()` 会在调用前校验余额，余额不足时返回 402。

## 四、后端实现要点（不得更改）

### 4.1 强制按次计费

**文件**：`apps/core-api/src/main/java/com/xianyu/admin/service/AiBillingService.java`

`estimateUsage()` 方法中，加载价格配置后强制通用模型按次计费：

```java
Map<String, Object> price = findPriceConfig(tenantId, providerName, modelName, modelType);
if (!StringUtils.hasText(billingMode)) billingMode = defaultText(price.get("billing_mode"), "token");
// 通用模型（model-config-general）强制按次计费：忽略调用方传入的 billingMode
if ("model-config-general".equals(price.get("module_key"))) {
    billingMode = "per_call";
}
billingMode = normalizeBillingMode(billingMode);
```

### 4.2 按用户 VIP 等级解析扣费 Token 数

`AiBillingService.resolveUserVipLevel(userId)` 从 `sys_user.vip_level` 读取用户等级（0=普通, 1=VIP, 2=SVP）；查询失败时回退为 0（普通用户）。

`AiBillingService.resolveTierTokensPerCall(userId)` 按以下优先级解析扣费 Token 数：

1. 查询 `ai_model_tier_price.tokens_per_call WHERE module_key='model-config-general' AND vip_level=<用户等级>`，若 >0 直接返回
2. 回退：查询 `ai_model_price_config.tokens_per_call WHERE module_key='model-config-general' AND enabled=1`
3. 再回退：代码层默认值 `3L`

### 4.3 配置同步时清零输入/输出单价

`normalizeAndSyncModelConfig()` 中，通用模型保存时强制：

```java
if ("model-config-general".equals(moduleKey)) {
    data.put("billingMode", "per_call");
    data.put("inputPricePer1k", BigDecimal.ZERO);
    data.put("outputPricePer1k", BigDecimal.ZERO);
    data.put("cachedInputPricePer1k", BigDecimal.ZERO);
}
```

### 4.4 扣费公式

```
chargeTokens = resolveTierTokensPerCall(userId) × imageCount
            = tierTokens × 1（文本调用默认 imageCount=1）
            = 3 × 1 = 3 Token（默认配置，普通用户）
```

- `imageCount` 对文本调用默认为 1（`boundedUsageValue` 默认值）
- VIP 用户若配置 `tokens_per_call=2`，则扣 2 Token
- SVP 用户若配置 `tokens_per_call=1`，则扣 1 Token

### 4.5 管理端 tier-config 接口

**文件**：`apps/core-api/src/main/java/com/xianyu/admin/controller/AiBillingController.java`

- `GET /admin-api/ai-billing/tier-config?moduleKey=xxx` — 返回 `{moduleKey, normal, vip, svp}` 三档配置
- `PUT /admin-api/ai-billing/tier-config` — 请求体 `{moduleKey, normal, vip, svp}`，upsert 三档记录

`AiBillingService.getTierConfig(moduleKey)` / `saveTierConfig(dto)` 内部通过 `upsertTierPrice(moduleKey, vipLevel, tokens)` 实现幂等写入。

### 4.6 数据库表

**迁移脚本**：`apps/core-api/src/main/resources/db/migration/V1.42__create_ai_model_tier_price.sql`

```sql
CREATE TABLE IF NOT EXISTS ai_model_tier_price (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_key VARCHAR(80) NOT NULL,
    vip_level INT NOT NULL DEFAULT 0,
    tokens_per_call BIGINT NOT NULL DEFAULT 3,
    created_time DATETIME,
    updated_time DATETIME,
    UNIQUE KEY uk_tier_module_level (module_key, vip_level),
    INDEX idx_tier_module (module_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
```

应用启动时由 `SchemaCompatibilityRunner` 幂等创建并迁移 `ai_model_price_config.tokens_per_call` 到三档默认值。

## 五、管理端配置要点（不得更改）

### 5.1 模型配置页面（通用模型 section）

**文件**：`apps/admin-web/src/views/admin/model-config/index.vue`

通用模型（`general` section）的字段清单：

| 保留字段 | 说明 |
|---------|------|
| `providerName` | 默认服务商 |
| `baseUrl` | Base URL |
| `apiKey` | API Key |
| `defaultModel` | 默认模型 |
| `requestTimeout` | 请求超时 |
| `enabled` | 启用状态 |
| `_feeSettingsTip` | 费用配置跳转提示（type='tip'，引导至费用设置页面） |
| `polishKeywords` | 润色关键词 |
| `polishForbiddenKeywords` | 润色禁止关键词 |

**已移除字段**（不得恢复）：`billingMode`、`billingUnit`、`inputPricePer1k`、`cachedInputPricePer1k`、`outputPricePer1k`、`perCallPrice`、`tokenExchangeRate`

### 5.2 费用设置页面（三档定价卡片）

**文件**：`apps/admin-web/src/views/admin/ai-pricing/index.vue`

页面顶部概览卡片之后，新增"通用模型按用户等级定价"卡片，含三档 `ElInputNumber`：
- 普通用户（vip_level=0）：默认 3
- VIP 用户（vip_level=1）：默认 3，可改为 2
- SVP 用户（vip_level=2）：默认 3，可改为 1

保存时调用 `saveTierConfig({moduleKey: 'model-config-general', normal, vip, svp})`。

### 5.3 前端 API

**文件**：`apps/admin-web/src/api/billing.ts`

```typescript
export interface TierPriceConfig {
  moduleKey?: string
  normal: number
  vip: number
  svp: number
}
export function getTierConfig(moduleKey?: string): Promise<TierPriceConfig>
export function saveTierConfig(data: TierPriceConfig): Promise<TierPriceConfig>
```

## 六、前端实现要点（不得更改）

### 6.1 Token 余额校验工具

**文件**：`apps/user-web/src/utils/aiTokenGuard.js`

```javascript
export async function ensureAiTokenBalance() {
  // 调用 GET /ai-billing/balance 获取余额
  // 余额 <= 0 时弹出"Token 余额为 0，请先充值"提示并返回 false
  // 查询失败时不阻断（由后端 precheck 402 兜底）
}
```

### 6.2 调用前校验

前台**每个主动调用通用模型**的场景，在发起请求前必须调用 `ensureAiTokenBalance()`：

```javascript
if (!(await ensureAiTokenBalance())) return
// 然后再调用 AI 接口
```

已接入的页面：
- `apps/user-web/src/pages/ProductPublishPage.vue` → `aiDesc()`
- `apps/user-web/src/pages/OpportunityPage.vue` → `rewriteSelected()`
- `apps/user-web/src/pages/WorkflowPage.vue` → `testPolish()`
- `apps/user-web/src/pages/settings/AiCsSettings.vue` → `runTest()`

### 6.3 新增通用模型调用场景时

后续所有需要调用通用模型的新功能，必须：
1. 在调用 AI 接口前调用 `ensureAiTokenBalance()` 校验余额
2. 不得在前端硬编码扣费数量
3. 扣费由后端 `AiBillingService.charge()` 统一处理，前端无需关心具体扣费数

## 七、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/core-api/src/main/java/com/xianyu/admin/service/AiBillingService.java` | 计费核心：强制按次计费、按 VIP 等级解析 tokens_per_call、配置同步清零 |
| `apps/core-api/src/main/java/com/xianyu/admin/controller/AiBillingController.java` | 计费接口：tier-config GET/PUT 端点 |
| `apps/core-api/src/main/java/com/xianyu/admin/dto/TierPriceConfigDTO.java` | 三档定价 DTO（normal/vip/svp） |
| `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java` | 启动时幂等创建 ai_model_tier_price 表并迁移默认数据 |
| `apps/core-api/src/main/resources/db/migration/V1.42__create_ai_model_tier_price.sql` | V1.42 迁移脚本（文档性质，实际由 SchemaCompatibilityRunner 执行） |
| `apps/core-api/src/main/java/com/xianyu/admin/service/AiProviderService.java` | AI 调用：precheck → HTTP 调用 → charge |
| `apps/admin-web/src/api/billing.ts` | 管理端 API：TierPriceConfig 接口与 getTierConfig/saveTierConfig |
| `apps/admin-web/src/views/admin/ai-pricing/index.vue` | 费用设置页面（含三档定价卡片） |
| `apps/admin-web/src/views/admin/model-config/index.vue` | 模型配置页面（已移除 perCallPrice/tokenExchangeRate，改为 tip 提示） |
| `apps/admin-web/src/views/admin/model-config/ModelConfigForm.vue` | 配置表单组件（支持 tip 字段类型） |
| `apps/user-web/src/utils/aiTokenGuard.js` | 前端 Token 余额校验工具 |
| `apps/user-web/src/api/quickReply.js` | `getTokenBalance()` → GET `/ai-billing/balance` |
| `apps/user-web/src/pages/ProductPublishPage.vue` | 发布商品 AI 生成描述 |
| `apps/user-web/src/pages/OpportunityPage.vue` | 商机发掘改写 |
| `apps/user-web/src/pages/WorkflowPage.vue` | 工作流润色测试 |
| `apps/user-web/src/pages/settings/AiCsSettings.vue` | AI 客服测试发送 |
| `apps/automation-service/app/services/ai_billing.py` | Python 计费客户端（回传 usage 给 Java） |
| `apps/automation-service/app/services/ai_provider.py` | Python 模型调用封装 |
