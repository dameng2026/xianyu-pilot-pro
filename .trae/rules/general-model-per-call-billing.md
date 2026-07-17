# 通用模型按次计费规则

> **强制规则**：任何 AI 模型在修改"通用模型计费"或"前台调用通用模型"相关功能前，必须先完整阅读本文件。
> 通用模型（`model-config-general`）统一采用**按次计费**，严禁改回按 Token 量计费。
> 前台所有调用通用模型的行为，必须按后台通用模型配置中的按次价格扣费，不得在前端硬编码扣费数量。

## 一、背景与功能概述

通用模型（`model-config-general`）是平台前台 AI 功能的默认文本模型。原先按"输入 Token × 输入单价 + 输出 Token × 输出单价"计费，每次调用都需手动计算，十分麻烦且不透明。

现统一改为**按次计费**：每调用一次通用模型，扣减固定 Token 数 = `perCallPrice × tokenExchangeRate`（默认 `0.03 × 100 = 3 Token`）。扣费数量由后台通用模型配置中的按次价格决定，前台不得硬编码。

## 二、核心约束（违反即为事故级 Bug）

1. **通用模型必须按次计费**：`model-config-general` 的 `billingMode` 必须为 `per_call`，后端 `AiBillingService.estimateUsage()` 会根据价格配置的 `module_key == "model-config-general"` 强制按次计费，**忽略调用方传入的 billingMode**。
2. **按次价格默认 0.03 元/次**：`perCallPrice` 未配置或为 0 时，后端默认使用 `0.03`。兑换比例默认 `100`，即每次调用扣 `0.03 × 100 = 3 Token`。
3. **扣费数量由后台配置决定，不得前端硬编码**：前台不得写死"扣 3 Token"，必须读取后台 `perCallPrice` 的实际值。后台管理员修改 `perCallPrice` 后，扣费数量自动随之变化。
4. **输入/输出/缓存单价已移除**：管理端通用模型配置中不再展示 `inputPricePer1k`、`outputPricePer1k`、`cachedInputPricePer1k`、`billingMode`、`billingUnit` 字段；后端同步时将这些字段强制清零。
5. **前台调用前必须校验 Token 余额**：当 Token 余额为 0 时，提示"Token 余额为 0，请先充值 Token 后再使用 AI 功能"并阻止调用，不得发起请求。
6. **不得为通用模型恢复按 Token 计费**：不得在管理端重新添加输入/输出单价字段，不得在后端移除 `module_key == "model-config-general"` 的按次强制逻辑。

## 三、前台调用通用模型的场景清单

以下场景均调用通用模型，每使用一次扣费 `perCallPrice × tokenExchangeRate` 个 Token：

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

### 4.2 按次价格默认值

`estimateUsage()` 的 `per_call` 分支中，通用模型 `perCallPrice` 为 0 时默认 `0.03`：

```java
BigDecimal perCall = decimal(price.get("per_call_price"));
if (perCall.compareTo(BigDecimal.ZERO) <= 0 && "model-config-general".equals(price.get("module_key"))) {
    perCall = new BigDecimal("0.03");
}
```

### 4.3 配置同步时清零输入/输出单价

`normalizeAndSyncModelConfig()` 中，通用模型保存时强制：

```java
if ("model-config-general".equals(moduleKey)) {
    data.put("billingMode", "per_call");
    data.put("inputPricePer1k", BigDecimal.ZERO);
    data.put("outputPricePer1k", BigDecimal.ZERO);
    data.put("cachedInputPricePer1k", BigDecimal.ZERO);
    // perCallPrice 未配置时默认 0.03
}
```

### 4.4 扣费公式

```
chargeTokens = perCallPrice × tokenExchangeRate
            = 0.03 × 100 = 3 Token（默认配置）
```

- `imageCount` 对文本调用默认为 1（`boundedUsageValue` 默认值）
- `tokensPerCall` 未配置时不走固定销售价模式，由 `costYuan × exchangeRate` 计算
- `minChargeToken` 仅在非固定价模式下生效

## 五、管理端配置要点（不得更改）

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
| `perCallPrice` | **按次计费价格（元），默认 0.03** |
| `tokenExchangeRate` | 兑换比例（Token/元），默认 100 |
| `polishKeywords` | 润色关键词 |
| `polishForbiddenKeywords` | 润色禁止关键词 |

**已移除字段**（不得恢复）：`billingMode`、`billingUnit`、`inputPricePer1k`、`cachedInputPricePer1k`、`outputPricePer1k`

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
| `apps/core-api/src/main/java/com/xianyu/admin/service/AiBillingService.java` | 计费核心：强制通用模型按次计费、默认 0.03、配置同步清零 |
| `apps/core-api/src/main/java/com/xianyu/admin/service/AiProviderService.java` | AI 调用：precheck → HTTP 调用 → charge |
| `apps/admin-web/src/views/admin/model-config/index.vue` | 管理端通用模型配置（已移除输入/输出单价字段） |
| `apps/admin-web/src/views/admin/model-config/ModelConfigForm.vue` | 配置表单（perCallPrice 默认 0.03） |
| `apps/user-web/src/utils/aiTokenGuard.js` | 前端 Token 余额校验工具 |
| `apps/user-web/src/api/quickReply.js` | `getTokenBalance()` → GET `/ai-billing/balance` |
| `apps/user-web/src/pages/ProductPublishPage.vue` | 发布商品 AI 生成描述 |
| `apps/user-web/src/pages/OpportunityPage.vue` | 商机发掘改写 |
| `apps/user-web/src/pages/WorkflowPage.vue` | 工作流润色测试 |
| `apps/user-web/src/pages/settings/AiCsSettings.vue` | AI 客服测试发送 |
| `apps/automation-service/app/services/ai_billing.py` | Python 计费客户端（回传 usage 给 Java） |
| `apps/automation-service/app/services/ai_provider.py` | Python 模型调用封装 |
