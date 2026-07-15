# AI 二十四小时自动客服 & 自动回复功能重构设计文档

- **日期**：2026-06-28
- **状态**：待实施
- **作者**：AI 协助设计 + 用户确认
- **关联文件**：
  - `apps/user-web/src/pages/settings/AiCsSettings.vue`
  - `apps/user-web/src/pages/AutoReplyPage.vue`
  - `apps/user-web/src/pages/ProductsPage.vue`
  - `apps/core-api/src/main/java/com/xianyu/admin/controller/BusinessSettingsController.java`
  - `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java`
  - `apps/automation-service/app/api/v1/routes/items.py`
  - `apps/automation-service/app/models/entities.py`

---

## 一、背景与目标

### 1.1 现状问题
1. **AI 客服配置页面**：`systemPrompt`/`welcomeMessage` 默认值简单；`knowledgeBase` 文本框过小（rows=4）；不支持文件上传；"实时回复预览"测试失败时提示不清晰。
2. **自动回复页面**：包含大量由模型生成的字段（规则名称/匹配模式/回复模式/优先级/安全模式/最低价底线/每日上限/关键词/人工接管关键词/回复内容/策略预览/命中日志/规则列表），实际不符合业务场景，导致页面复杂、不可用。
3. **商品管理页面**：自动回复开关点击只跳转到自动回复页面（`emit('navigate', 'auto-reply')`），未实际切换；`xianyu_goods` 表无 `auto_reply_enabled` 字段，`replyOn` 恒为 false。

### 1.2 重构目标
- 以**最少最简单的功能**实现 AI 客服 + 自动回复闭环，后续根据实际需求逐步添加。
- 配置统一在 **AI 客服配置页面** 完成（系统提示词/欢迎语/知识库），自动回复页面只负责"启用范围"管理。
- 支持**商品管理页面直接开启**自动回复，无需跳转，前置校验 AI 客服主开关。
- 三档作用域：**商品级 > 账号级 > 全局**（覆盖式）。

---

## 二、整体架构

```
前端（user-web）
├── AiCsSettings.vue        # 全局AI客服配置（增强：文件上传+大段文本+恢复默认+预览修复）
├── AutoReplyPage.vue       # 重构：账号/商品双列 + 极简策略面板
└── ProductsPage.vue        # 商品级直接开关（不跳转 + 前置校验）

后端
├── Java core-api
│   ├── BusinessSettingsController    # 扩展：知识库文件上传代理 + 默认值优化
│   ├── AutoReplyScopeController(新)  # 账号/商品级 enabled 状态读写
│   └── AutomationProxyController     # 透传文件上传到 Python
└── Python automation-service
    ├── knowledge_base.py(新)        # 文件解析(MD/PPT/Excel) + AI提取规则
    ├── auto_reply_scope.py(新)      # 商品/账号级 enabled 持久化
    └── items.py                     # 替换 updateAutoReplyStatus 占位实现
```

---

## 三、数据存储设计（三档作用域）

### 3.1 作用域优先级
**商品级 > 账号级 > 全局**（覆盖式）

### 3.2 存储位置

| 作用域 | 存储位置 | 字段/键 | 说明 |
|--------|---------|---------|------|
| 全局开关 | `user_business_setting` 配置 `ai-customer-service.enabled` | 布尔 | 主开关，关闭时所有层级都不生效 |
| 账号级 | `user_business_setting` 新配置 `auto-reply-account-scopes` | JSON `{accounts: {accountId: bool}}` | 复用现有表，无表结构变更 |
| 商品级 | `xianyu_goods` 表新增列 `auto_reply_enabled` | TINYINT，NULL=继承，0=强制关，1=强制开 | 添加列到商品表 |

### 3.3 生效判定算法

查询某商品是否启用自动回复时：

```python
def is_auto_reply_active(goods, account_scopes, global_enabled):
    if not global_enabled:
        return False  # 主开关关闭
    if goods.auto_reply_enabled is not None:
        return goods.auto_reply_enabled == 1  # 商品级覆盖
    if str(goods.account_id) in account_scopes.get('accounts', {}):
        return account_scopes['accounts'][str(goods.account_id)]  # 账号级
    return False  # 默认关闭（不自动继承全局，避免误开）
```

**说明（设计决策，需用户确认）**：商品级和账号级未设置（NULL）时，**不自动继承全局 enabled**，而是默认关闭。全局 `enabled` 仅作为"主开关/能力开关"：
- 关闭时：所有层级都不生效（门控）
- 开启时：仅表示"具备自动回复能力"，具体商品/账号仍需显式开启

**这样设计的理由**：避免用户开启全局主开关后，所有商品被误启用自动回复。匹配用户描述的流程"开启后可在商品管理页面选中商品为其开启自动回复"（即商品需显式开启）。

**与"商品级覆盖账号级覆盖全局"的关系**：覆盖指 precedence（优先级）——当商品级/账号级显式设置了值（0 或 1）时，更具体的级别优先；当都未设置时，默认关闭而非继承全局。如果用户期望"未设置时继承全局 enabled"，请在此环节提出，将改为继承式判定。

### 3.4 数据库迁移

```sql
-- xianyu_goods 表新增 auto_reply_enabled 列
ALTER TABLE xianyu_goods 
  ADD COLUMN auto_reply_enabled TINYINT NULL DEFAULT NULL 
  COMMENT 'NULL继承账号级/全局 0强制关 1强制开';
```

`user_business_setting` 已有表，复用即可（运行时由 `BusinessSettingsService.ensureTable()` 保证存在）。

---

## 四、模块A：AI客服配置页面改造（`AiCsSettings.vue`）

### A1. 默认值优化 + 恢复默认按钮

**后端**（`BusinessSettingsService.defaultConfig()`）：
- 优化 `systemPrompt` 默认值，内容更完整、更专业（覆盖：身份定位、主营商品、回复语气、售后政策、转人工场景、禁止行为）。
- 优化 `welcomeMessage` 默认值，更友好、更具体。

**前端**（`AiCsSettings.vue`）：
- 系统提示词字段右上角加"恢复默认"按钮。
- 欢迎语字段右上角加"恢复默认"按钮。
- 点击按钮 → 调用新接口 `GET /api/business-settings/ai-customer-service/defaults` 拉取默认值 → 填入对应字段（用户可继续编辑，不自动保存）。
- 二次确认弹窗："恢复默认将覆盖当前内容，是否继续？"

### A2. 知识库大段文本

- `knowledgeBase` textarea 从 `rows="4"` 升级为 `rows="12"`，`min-height: 240px`。
- 移除 placeholder 中的"每行一条"提示，改为"可输入大段文字描述客服规则、售后政策、商品参数等；也可上传文件由 AI 自动提取"。
- 添加字符计数显示（右下角 `已输入 N 字`）。
- 支持垂直拉伸（`resize: vertical`）。

### A3. 文件上传 + AI 提取规则

**支持的文件类型**：`.md` / `.ppt` / `.pptx` / `.xlsx` / `.xls` / `.csv`
**单文件大小限制**：10MB

**上传流程**：
1. 前端在知识库字段下方新增"上传文件提取规则"区域，含拖拽上传 + 点击选择。
2. 选择文件后立即上传到 `POST /api/business-settings/ai-customer-service/upload-knowledge`（multipart/form-data）。
3. Java 网关接收 → 透传到 Python `POST /api/knowledge-base/extract`（保留文件流）。
4. Python 解析：
   - `.md` → 直接读取文本
   - `.ppt/.pptx` → `python-pptx` 提取所有幻灯片文本
   - `.xlsx/.xls` → `openpyxl` 提取所有 sheet 的表格内容
   - `.csv` → `csv` 模块读取
5. Python 调用 AI 模型（复用 `aiProviderService` 通用文本模型），提示词：
   ```
   你是客服规则提取助手。请从以下文件内容中提取所有可作为 AI 客服回复规则的信息，
   输出为结构化 Markdown 文本，按类别分组（如 ## 售后政策 / ## 发货说明 / ## 商品 FAQ / ## 退换货规则）。
   每条规则用 - 开头，包含：触发场景、回复要点、注意事项。
   不要输出与客服回复无关的内容。
   
   文件内容：
   {extracted_text}
   ```
6. 返回 `{extractedText: "## 售后政策\n- ...", ruleCount: N, fileName: "xxx.md"}`。
7. 前端将 `extractedText` **自动追加到 `knowledgeBase` 文本框**末尾（用分隔线 `---` 区分不同文件来源），用户可审阅/编辑。
8. Toast 提示："已从 xxx.md 提取 N 条规则，已追加到知识库"。

**错误处理**：
- 文件过大 → "文件不能超过 10MB"
- 不支持的格式 → "仅支持 .md/.ppt/.pptx/.xlsx/.xls/.csv"
- AI 提取失败 → "AI 提取失败：{错误信息}，请检查 AI 模型配置或重试"
- 解析失败 → "文件解析失败：{错误信息}"

### A4. 实时回复预览修复

**仅优化错误提示，不重构后端逻辑。**

**前端**（`runTest()` 函数）改造：
- 区分三种错误状态：
  - `NOT_CONFIGURED`：AI Provider 未配置 → 显示醒目黄色警告"AI 模型未配置，请到「后台 → 模型配置」先配置通用文本模型"，附"前往模型配置"按钮（跳转 admin-web 或对应路由）。
  - `AI_ERROR`：AI 调用异常 → 显示红色错误"AI 调用失败：{具体错误}"，附"重试"按钮。
  - `NETWORK_ERROR`：网络错误 → 显示"网络异常，请检查网络连接"，附"重试"按钮。
- 测试中状态显示加载动画。

**后端**（`BusinessSettingsController.testAiReply()`）：
- 在返回的 Map 中增加 `errorCode` 字段：
  - 未配置 AI → `errorCode: "NOT_CONFIGURED"`
  - AI 调用异常 → `errorCode: "AI_ERROR"`
  - 正常返回 → 不设置 errorCode
- 现有的 `configured: false` 保留用于兼容。

---

## 五、模块B：自动回复页面重构（`AutoReplyPage.vue`）

### B1. 左侧双列结构

**布局**：
```
┌──────────── 账号列表 ───────────┬──────────── 商品列表 ───────────┐
│  📂 全部账号                    │  ☐ 商品A    [已开启]            │
│  👤 账号1（小张闲鱼）           │  ☐ 商品B    [未开启]            │
│  👤 账号2（小李数码）           │  ☐ 商品C    [继承账号级]        │
│  👤 账号3（小王店铺）           │  ...                            │
└────────────────────────────────┴─────────────────────────────────┘
```

**账号列**：
- 顶部选项"全部账号"（虚拟节点）。
- 列出所有闲鱼账号，显示账号名称。
- 单击切换选中态，选中后加载右侧商品列表。
- "全部账号"选中时 → 商品列展示全部账号的所有商品。

**商品列**：
- 选中账号后加载该账号的商品列表（调用 `GET /api/auto-reply-scope/products?accountId={id}`）。
- 商品项显示：商品标题（截断）+ 当前 effective enabled 状态标签（已开启/未开启/继承账号级）。
- 支持多选（复选框）。
- 支持搜索（商品标题关键词）。
- 分页（每页 50 条）。

### B2. 右侧极简策略面板

**移除**：规则名称、匹配模式、回复模式、优先级、安全模式、最低价底线、每日上限、关键词、人工接管关键词、回复内容、策略预览、自动回复命中日志、规则列表、StatCard 统计网格、使用教程卡片（教程内容不再适用）。

**保留**：
```
┌─── 自动回复策略 ───────────────────────┐
│  当前作用域：全局 / 账号X / 商品Y       │
│                                        │
│  启用自动回复     [开关]                │
│                                        │
│  ─── AI 客服配置摘要（只读） ───        │
│  系统提示词：你是闲鱼店铺的客服助手...   │
│  欢迎语：您好，我是本店的AI客服...      │
│  [前往 AI 客服配置修改]                 │
│                                        │
│  ─── 批量操作（仅多选时显示） ───       │
│  [为选中商品开启]  [为选中商品关闭]      │
│  [为当前列表所有商品一键开启]           │
└────────────────────────────────────────┘
```

**面板内容**：
1. **当前作用域显示**：
   - 未选中任何账号/商品 → "全局"
   - 选中账号（未选商品）→ "账号：{账号名}"
   - 选"全部账号"→ "全部账号"
   - 选中单个商品 → "商品：{商品标题}"
   - 选中多个商品 → "已选 {N} 个商品"
2. **启用自动回复开关**：根据作用域切换对应级别的 enabled 状态。
3. **AI 客服配置摘要**（只读）：显示 systemPrompt 前 2 行 + welcomeMessage 前 1 行，附"前往 AI 客服配置修改"按钮（跳转 settings-ai-cs）。
4. **批量操作按钮**（仅商品列表多选时显示）。

### B3. 作用域切换逻辑

| 选中状态 | 作用域 | 开关控制对象 |
|---------|--------|-------------|
| 未选中任何 | 全局 | `ai-customer-service.enabled` |
| 选中单一账号（未选商品） | 账号级 | `auto-reply-account-scopes.accounts[accountId]` |
| 选"全部账号"（未选商品） | 全部账号 | 批量设置所有 `auto-reply-account-scopes.accounts[*]` |
| 选中单个商品 | 商品级 | `xianyu_goods.auto_reply_enabled` |
| 选中多个商品 | 批量 | 批量设置多个 `xianyu_goods.auto_reply_enabled` |

**开关状态显示**：
- 全局 → 显示 `ai-customer-service.enabled`
- 账号级 → 显示该账号在 `auto-reply-account-scopes` 中的状态（无记录则显示"未设置（默认关闭）"）
- 商品级 → 显示该商品的 `auto_reply_enabled`（NULL 则显示"继承账号级/全局"）
- 多选 → 若所有选中项状态一致则显示该状态，否则显示"混合状态"

### B4. 移除的接口调用

- `getAutoReplyRules` / `createAutoReplyRule` / `updateAutoReplyRule` / `deleteAutoReplyRule`
- `previewAutoReplyRule`
- `getAutoReplyLogs` / `getAutoReplyStats`
- `applyPreset`（推荐规则批量创建）

这些 API 函数可保留在 `autoReply.js` 中（不删除，避免破坏其他引用），但 `AutoReplyPage.vue` 不再 import。

---

## 六、模块C：商品管理页面改造（`ProductsPage.vue`）

### C1. 自动回复开关直接生效

**修改**（`ProductsPage.vue` 第 422 行 `toggleReply` 函数）：
- 原：`function toggleReply(row) { emit('navigate', 'auto-reply') }`
- 新：调用 `POST /api/auto-reply-scope/product` 切换 `auto_reply_enabled`，成功后更新 `row.replyOn` 和 `row.raw.auto_reply_enabled`，无需跳转。

### C2. 开启前前置校验

点击自动回复开关时：
1. 调用 `getBusinessSettings('ai-customer-service')` 检查 `enabled` 字段。
2. 若 `enabled === false` → 弹出确认框：
   ```
   ⚠ 尚未开启 AI 自动回复主开关
   请先前往「AI 客服配置」页面开启 24 小时全天在线的 AI 自动回复
   
   [前往配置]  [取消]
   ```
   - 点击"前往配置" → `emit('navigate', 'settings-ai-cs')` 跳转到 AI 客服配置页。
   - 点击"取消" → 关闭弹窗，不切换开关。
3. 若 `enabled === true` → 正常切换商品级 `auto_reply_enabled`。

**缓存优化**：首次校验后缓存 `aiCsEnabled` 状态，避免每次开关都请求；切换失败时刷新缓存。

### C3. 批量操作

- 商品列表选中多个商品 → 工具栏出现"批量开启自动回复"按钮。
- 同样执行前置校验（检查全局 enabled）。
- 调用 `POST /api/auto-reply-scope/batch` 批量更新。

---

## 七、模块D：后端新接口

### 7.1 Python 端（`apps/automation-service/app/api/v1/routes/`）

#### 新文件：`knowledge_base.py`

```python
POST /api/knowledge-base/extract
  Request: multipart/form-data, 字段 file (文件)
  Response: {
    extractedText: "## 售后政策\n- ...",
    ruleCount: 12,
    fileName: "policy.md"
  }
  流程:
    1. 接收文件
    2. 根据扩展名选择解析器:
       - .md → 直接读取文本
       - .ppt/.pptx → python-pptx 提取所有幻灯片文本
       - .xlsx/.xls → openpyxl 提取所有 sheet 内容
       - .csv → csv 模块
    3. 调用 AI 模型按提示词提取规则
    4. 返回结构化 Markdown 文本
```

#### 新文件：`auto_reply_scope.py`

```python
GET /api/auto-reply-scope/products
  Query: accountId (可选, 不传则返回全部账号商品)
  Response: [
    {id, title, accountId, auto_reply_enabled, effective_enabled, account_enabled, global_enabled}
  ]

POST /api/auto-reply-scope/product
  Body: {itemId, enabled}
  Response: {ok: true}
  流程: 更新 xianyu_goods.auto_reply_enabled

POST /api/auto-reply-scope/account
  Body: {accountId, enabled}
  Response: {ok: true}
  流程: 更新 user_business_setting 的 auto-reply-account-scopes 配置

POST /api/auto-reply-scope/batch
  Body: {itemIds: []} 或 {accountIds: [], enabled: bool}
  Response: {ok: true, affected: N}
  流程: 批量更新

GET /api/auto-reply-scope/status
  Query: accountId (可选)
  Response: {global_enabled, account_scopes: {1: true, 2: false}}
```

### 7.2 Java 网关（`apps/core-api/.../controller/`）

#### 扩展：`BusinessSettingsController.java`

```java
GET /api/business-settings/ai-customer-service/defaults
  返回默认 systemPrompt/welcomeMessage/knowledgeBase

POST /api/business-settings/ai-customer-service/upload-knowledge
  接收 multipart 文件, 透传到 Python /api/knowledge-base/extract
```

#### 新增：`AutoReplyScopeController.java`

```java
@RestController
@RequestMapping("/api/auto-reply-scope")
class AutoReplyScopeController {
    GET  /products          → 透传 Python
    POST /product           → 透传 Python
    POST /account           → 透传 Python
    POST /batch             → 透传 Python
    GET  /status            → 透传 Python
}
```

透传逻辑参考 `AutomationProxyController` 现有实现，拆包 Python 返回的 `ResultObject {code, msg, data}`，仅返回 `data` 字段。

### 7.3 依赖项

**Python 新增依赖**（`apps/automation-service/requirements.txt`）：
- `python-pptx`（PPT 解析）
- `openpyxl`（Excel 解析，可能已有）
- `python-markdown`（MD 解析，可选，直接读取文本即可）

**Java 网关**：复用现有 multipart 处理，无需新依赖。

---

## 八、前端 API 封装

### 8.1 扩展 `businessSettings.js`

```javascript
// 获取 AI 客服默认值（用于恢复默认按钮）
export function getAiCsDefaults() {
  return request.get('/business-settings/ai-customer-service/defaults')
}

// 上传知识库文件，AI 提取规则
export function uploadKnowledgeBase(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/business-settings/ai-customer-service/upload-knowledge', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
```

### 8.2 新文件 `autoReplyScope.js`

```javascript
import request from '../utils/request.js'

export function getAutoReplyScopeProducts(accountId) {
  return request.get('/auto-reply-scope/products', { params: { accountId } })
}

export function updateProductAutoReplyScope(itemId, enabled) {
  return request.post('/auto-reply-scope/product', { itemId, enabled })
}

export function updateAccountAutoReplyScope(accountId, enabled) {
  return request.post('/auto-reply-scope/account', { accountId, enabled })
}

export function batchUpdateAutoReplyScope(body) {
  return request.post('/auto-reply-scope/batch', body)
}

export function getAutoReplyScopeStatus(accountId) {
  return request.get('/auto-reply-scope/status', { params: { accountId } })
}
```

---

## 九、实施顺序

| 阶段 | 任务 | 涉及文件 |
|------|------|---------|
| 1 | 数据库迁移：xianyu_goods 新增 auto_reply_enabled 列 | DB |
| 2 | Python：新建 knowledge_base.py 路由 + 文件解析 + AI 提取 | automation-service |
| 3 | Python：新建 auto_reply_scope.py 路由 + 作用域管理 | automation-service |
| 4 | Python：替换 items.py 的 updateAutoReplyStatus 占位实现 | items.py |
| 5 | Java：BusinessSettingsService 优化默认值 + 新增 defaults 接口 | core-api |
| 6 | Java：BusinessSettingsController 新增 upload-knowledge 代理 | core-api |
| 7 | Java：新建 AutoReplyScopeController 透传 | core-api |
| 8 | 前端：businessSettings.js 扩展 + 新建 autoReplyScope.js | user-web/api |
| 9 | 前端：AiCsSettings.vue 改造（文件上传+大段文本+恢复默认+预览修复） | AiCsSettings.vue |
| 10 | 前端：ProductsPage.vue 直接开关 + 前置校验 | ProductsPage.vue |
| 11 | 前端：AutoReplyPage.vue 重构（双列+极简面板） | AutoReplyPage.vue |
| 12 | 联调验证 | 全栈 |

---

## 十、验收标准

### 10.1 AI 客服配置页面
- [ ] 系统提示词、欢迎语默认值更完整专业
- [ ] 系统提示词、欢迎语字段旁有"恢复默认"按钮，点击后填入默认值（不自动保存）
- [ ] 知识库文本框扩大为 12 行，支持垂直拉伸，显示字符计数
- [ ] 支持上传 .md/.ppt/.pptx/.xlsx/.xls/.csv 文件（≤10MB）
- [ ] 上传后 AI 自动提取规则并以结构化 Markdown 追加到知识库文本框
- [ ] 实时回复预览错误提示清晰：区分未配置/AI异常/网络错误，提供跳转/重试按钮

### 10.2 自动回复页面
- [ ] 左侧双列：账号列 + 商品列
- [ ] 选"全部账号"→商品列显示全部商品；选单一账号→显示该账号商品
- [ ] 右侧极简策略面板：作用域显示 + 启用开关 + AI客服配置摘要 + 批量操作
- [ ] 移除所有规则字段、策略预览、命中日志、规则列表、统计卡片、使用教程
- [ ] 作用域切换正确：未选→全局；选账号→账号级；选全部账号→批量账号级；选商品→商品级
- [ ] 商品级 enabled 覆盖账号级，账号级覆盖全局

### 10.3 商品管理页面
- [ ] 自动回复开关点击直接切换，不跳转
- [ ] 开启前检查 AI 客服主开关，未开启时弹出引导确认框
- [ ] 已开启时正常切换商品级 enabled
- [ ] 支持批量选中商品开启自动回复

### 10.4 数据一致性
- [ ] `xianyu_goods.auto_reply_enabled` 字段正确读写
- [ ] `auto-reply-account-scopes` 配置正确读写
- [ ] 商品级/账号级/全局优先级判定正确

---

## 十一、风险与限制

1. **AI 提取规则质量**：AI 从文件提取的规则可能不完美，需要用户审阅/编辑。已通过"追加到文本框不自动保存"规避。
2. **大文件上传**：10MB 限制 + Java multipart 上传限制（已有 `max-file-size:20MB, max-request-size:50MB`）。
3. **AI Provider 依赖**：文件提取和实时预览都依赖 AI Provider，未配置时功能不可用，需明确提示。
4. **旧 auto_reply_rule 表**：本次不删除旧表和旧数据，仅前端不再使用。如需清理可后续迁移。
5. **账号级作用域存储**：`auto-reply-account-scopes` JSON 在账号数多时会变大，但闲鱼账号数量通常有限（<100），可接受。

---

## 十二、不在本次范围内（后续逐步添加）

- 自动回复规则（关键词匹配/正则/AI意图）
- 策略预览
- 自动回复命中日志
- 规则列表 CRUD
- 安全模式/最低价底线/每日上限/人工接管关键词
- 商品级/账号级独立 systemPrompt 覆盖（目前统一用全局 AI 客服配置）
- AI 自动回复实际执行链路（买家消息触发→AI生成回复→发送）

这些功能由 AI 预先生成或后续根据实际需求逐步添加。
