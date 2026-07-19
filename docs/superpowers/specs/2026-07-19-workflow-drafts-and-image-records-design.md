# 工作流商品草稿箱与图片生成记录 - 设计文档

> **状态**：已批准，待实施
> **创建日期**：2026-07-19
> **作者**：AI 协同设计
> **方案**：方案 A（复用扩展）

---

## 一、背景与目标

### 1.1 业务背景

工作流是用户在闲鱼助手中设计自动化业务流程的核心能力，已有 6 种节点：触发器、商品获取、商品筛选、润色节点、生图节点、发布节点。当前发布节点直接调用闲鱼发布 API，存在以下问题：

1. **发布失败即丢失**：商品在工作流中经过润色、生图等步骤产生后，若发布失败，商品数据没有任何持久化记录，用户无法重试
2. **图片生成记录分散**：工作流中调用的生图图片，与商机发掘中调用的生图图片共用 `opportunity_image_history` 表，但用户无法区分来源，也无法查看工作流生图历史
3. **缺少工作流产物视图**：工作流任务页面只展示执行状态，没有产物（商品、图片）的聚合视图

### 1.2 设计目标

1. **商品草稿箱**：工作流发布节点在发布前先将商品存入草稿箱，无论发布成功或失败都保留草稿记录，支持重试发布、批量操作
2. **图片生成记录**：展示所有生图模型调用产生的图片历史，区分商机发掘与工作流来源，支持预览、恢复
3. **导航重构**：将商品草稿箱、图片生成记录作为工作流的子页面，纳入侧边栏「自动化」分组

### 1.3 用户已确认决策

- **「商品参考箱」与「商品草稿箱」是同一功能**，统一命名为「商品草稿箱」
- **UI 形式**：扁平添加 nav 同级项，标 `child: true` 表示从属于工作流（与现有货源库等子页面风格一致）
- **整体方案**：方案 A（复用扩展）— 复用 `opportunity_image_history` 表加 `source` 字段，新建 `workflow_goods_draft` 表

---

## 二、整体架构

### 2.1 模块划分

```
[前端 user-web]
  ├─ pages/WorkflowDraftsPage.vue        新建：商品草稿箱列表页
  ├─ pages/WorkflowImageRecordsPage.vue  新建：图片生成记录页
  ├─ api/workflowDrafts.js               新建：草稿箱 API
  ├─ api/opportunity.js                  扩展：listWorkflowImageRecords
  ├─ data/nav.js                         扩展：追加 2 个 nav 项
  └─ App.vue                             扩展：pageMap 注册 2 个页面

[Java 网关 core-api]
  ├─ controller/AutomationProxyController.java  扩展：6 个草稿箱端点 + image-history source 透传
  ├─ service/ImageGenerationService.java        扩展：saveGenerationHistory 接受 source 参数
  ├─ config/SchemaCompatibilityRunner.java      扩展：兜底 ALTER 新字段
  └─ db/migration/V1.25__add_opportunity_image_history_source.sql  新建

[Python 服务 automation-service]
  ├─ models/entities.py                          扩展：WorkflowGoodsDraft ORM
  ├─ services/workflow_draft_service.py          新建：草稿 CRUD + 重试发布
  ├─ api/v1/routes/workflow.py                   扩展：6 个草稿箱路由
  ├─ services/automation_runtime.py              改造：PUBLISH 节点先存草稿，IMAGE_GENERATE 传 source
  └─ migrations/V1.10__create_workflow_goods_draft.sql  新建

[数据库]
  ├─ core_mysql.opportunity_image_history        扩展：source/workflow_id/workflow_execution_id/workflow_node_key
  └─ automation_mysql.workflow_goods_draft       新建
```

### 2.2 数据流

```
工作流执行
  ├─ IMAGE_GENERATE 节点
  │   └─ 调用 /opportunity/generate-images (source=workflow)
  │       └─ ImageGenerationService.saveGenerationHistory(source=workflow, ...)
  │           └─ 写入 opportunity_image_history
  │
  └─ PUBLISH 节点（改造后）
      ├─ 步骤1：校验 img_ai_ok == True（未生成 AI 封面图严禁发布）
      ├─ 步骤2：创建 WorkflowGoodsDraft (status=draft)
      ├─ 步骤3：更新 status=publishing
      ├─ 步骤4：调用 XianyuItemPublisher.publish() 尝试发布
      ├─ 步骤5：发布成功 → status=published, xianyu_goods_id=xxx
      └─ 步骤6：发布失败 → status=failed, error_message=xxx（草稿保留）

商品草稿箱页面
  └─ GET /api/workflow/drafts → 展示列表，支持重试发布、删除

图片生成记录页面
  └─ GET /api/opportunity/image-history?source=workflow → 展示工作流生图历史
```

---

## 三、数据模型

### 3.1 新建表：`workflow_goods_draft`

放在 automation-service 数据库（与 `workflow_definition` 等表同库），ORM 类添加到 `apps/automation-service/app/models/entities.py`。

```python
class WorkflowGoodsDraft(Base):
    __tablename__ = "workflow_goods_draft"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=True)

    # 工作流溯源
    workflow_id = Column(BigInteger, nullable=True, index=True)
    workflow_execution_id = Column(BigInteger, nullable=True, index=True)
    workflow_name = Column(String(200), nullable=True)        # 冗余存储，列表展示用
    node_key = Column(String(100), nullable=True)             # 产生该商品的节点key
    account_id = Column(BigInteger, nullable=True)            # 闲鱼账号ID

    # 商品快照字段（与 xianyu_goods 表对齐）
    title = Column(String(500), nullable=False)
    price = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    cover_pic = Column(Text, nullable=True)
    image_urls = Column(JSON, nullable=True)                  # 多图URL列表
    category = Column(String(100), nullable=True)
    stock = Column(Integer, default=1)
    location = Column(JSON, nullable=True)                    # 发货地 {prov,city,area,...}
    raw_payload = Column(JSON, nullable=True)                 # 原始商品数据快照

    # 发布状态追踪
    publish_status = Column(String(20), default="draft", index=True)
    # draft: 待发布（草稿）
    # publishing: 发布中
    # published: 已发布
    # failed: 发布失败
    publish_time = Column(DateTime, nullable=True)
    xianyu_goods_id = Column(String(100), nullable=True)      # 闲鱼返回的商品ID
    publish_error_message = Column(Text, nullable=True)
    publish_attempt_count = Column(Integer, default=0)

    # 审计字段
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted = Column(TINYINT, default=0, nullable=False)
```

**索引**：
- `idx_tenant_status_created (tenant_id, publish_status, created_time DESC)` — 列表查询主索引
- `idx_workflow_execution (workflow_execution_id)` — 按执行记录查询
- `idx_tenant_deleted (tenant_id, deleted)` — 软删除过滤

### 3.2 扩展现有表：`opportunity_image_history`

新建 core-api 迁移脚本 `V1.25__add_opportunity_image_history_source.sql`：

```sql
ALTER TABLE opportunity_image_history
  ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'opportunity'
    COMMENT '生图来源：opportunity=商机发掘 / workflow=工作流',
  ADD COLUMN workflow_id BIGINT NULL COMMENT '工作流定义ID（source=workflow时）',
  ADD COLUMN workflow_execution_id BIGINT NULL COMMENT '工作流执行记录ID（source=workflow时）',
  ADD COLUMN workflow_node_key VARCHAR(100) NULL COMMENT '生图节点key（source=workflow时）',
  ADD INDEX idx_source_tenant_created (source, tenant_id, created_time DESC);
```

**SchemaCompatibilityRunner** 兜底：在 `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java` 中追加 `ensureColumn("opportunity_image_history", "source", ...)` 等兜底 ALTER，确保旧库自动补字段。

### 3.3 与 `workflow_publish_record` 的关系

现有 `workflow_publish_record` 表保留不动，记录的是「发布动作的结果」（goods_id、xianyu_goods_id、image_urls、发布时间），与新建的 `workflow_goods_draft` 是**互补关系**：

| 表 | 关注点 | 主要字段 |
|----|--------|---------|
| `workflow_goods_draft` | 商品快照 + 发布状态流转 | title/price/image_urls/publish_status/error_message |
| `workflow_publish_record` | 发布动作日志 | goods_id/xianyu_goods_id/publish_time |

`workflow_goods_draft.publish_status=published` 的记录可与 `workflow_publish_record` 通过 `(workflow_execution_id, xianyu_goods_id)` 关联。

---

## 四、后端 API 设计

### 4.1 商品草稿箱 API

**Python 层** (`apps/automation-service/app/api/v1/routes/workflow.py` 追加)：

| 方法 | 路由 | 用途 |
|------|------|------|
| GET | `/api/v1/workflow/drafts` | 分页查询草稿列表，支持 `status`/`workflowId`/`keyword`/`startDate`/`endDate` 过滤 |
| GET | `/api/v1/workflow/drafts/{id}` | 草稿详情 |
| POST | `/api/v1/workflow/drafts/{id}/retry-publish` | 重试发布单个草稿 |
| POST | `/api/v1/workflow/drafts/batch-retry-publish` | 批量重试发布（body: `{ids: []}`） |
| DELETE | `/api/v1/workflow/drafts/{id}` | 删除草稿（软删除） |
| GET | `/api/v1/workflow/drafts/stats` | 草稿统计（总数/待发布/已发布/失败数） |

**Java 网关层** (`AutomationProxyController.java` 追加)：

| 方法 | 路由 | 透传到 Python |
|------|------|--------------|
| GET | `/api/workflow/drafts` | `/automation/api/v1/workflow/drafts` |
| GET | `/api/workflow/drafts/{id}` | `/automation/api/v1/workflow/drafts/{id}` |
| POST | `/api/workflow/drafts/{id}/retry-publish` | 同名透传 |
| POST | `/api/workflow/drafts/batch-retry-publish` | 同名透传 |
| DELETE | `/api/workflow/drafts/{id}` | 同名透传 |
| GET | `/api/workflow/drafts/stats` | 同名透传 |

按现有惯例：Java 网关拆包 Python 返回的 `ResultObject {code, msg, data}`，仅返回 `data`。

### 4.2 图片生成记录 API

**复用现有 API**，仅扩展查询参数。该页面默认展示**所有来源**的生图历史（商机发掘 + 工作流），用户可通过筛选器按来源过滤：

| 方法 | 路由 | 新增参数 |
|------|------|---------|
| GET | `/api/opportunity/image-history` | `source`（可选，`all`/`opportunity`/`workflow`，默认 `all`）/ `workflowId` / `nodeKey` |
| GET | `/api/opportunity/image-history/{requestId}` | 不变 |
| POST | `/api/opportunity/image-recover/{historyId}` | 不变 |

**说明**：`source` 参数为新增可选过滤项。当 `source=all` 或不传时，返回所有来源记录；当 `source=workflow` 时仅返回工作流生图；当 `source=opportunity` 时仅返回商机发掘生图（保持现有商机发掘页面调用兼容）。

**Java 层 `ImageGenerationService.java` 改造**：
- `saveGenerationHistory()` 方法签名扩展，接受可选参数 `source`、`workflowId`、`workflowExecutionId`、`workflowNodeKey`
- 调用方未传 `source` 时默认 `opportunity`（保持现有商机发掘调用兼容）

**automation-service 生图调用改造**：
- `automation_runtime.py` 中 IMAGE_GENERATE 节点调用 Java `/opportunity/generate-images` 时，请求体追加 `source: "workflow"`、`workflowId`、`workflowExecutionId`、`nodeKey` 字段
- Java 侧 `AutomationProxyController` 的 `/opportunity/generate-images` 端点透传这些字段

### 4.3 重试发布的实现

新建 `apps/automation-service/app/services/workflow_draft_service.py`：

```python
async def retry_publish_draft(draft_id: int, tenant_id: int):
    draft = await get_draft(draft_id, tenant_id)
    if draft.publish_status == "publishing":
        raise BadRequestError("该草稿正在发布中，请勿重复操作")
    if draft.publish_status == "published":
        raise BadRequestError("该草稿已发布成功，无需重试")

    # 更新状态为发布中
    draft.publish_status = "publishing"
    draft.publish_attempt_count += 1
    draft.publish_time = datetime.utcnow()
    await session.commit()

    try:
        # 复用现有 XianyuItemPublisher
        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        result = await publisher.publish({
            "title": draft.title,
            "description": draft.description,
            "imageUrls": draft.image_urls,
            "price": draft.price,
            "stock": draft.stock,
            "category": draft.category,
            "location": draft.location,
            "xianyuAccountId": draft.account_id,
        })

        # 发布成功
        draft.publish_status = "published"
        draft.xianyu_goods_id = result.get("itemId")
        draft.publish_error_message = None
        await session.commit()
        return {"success": True, "xianyuGoodsId": draft.xianyu_goods_id}

    except Exception as e:
        # 发布失败，但草稿保留
        draft.publish_status = "failed"
        draft.publish_error_message = str(e)
        await session.commit()
        return {"success": False, "error": str(e)}
```

---

## 五、工作流发布节点改造

### 5.1 改造后流程

`apps/automation-service/app/services/automation_runtime.py` 中 PUBLISH 节点执行逻辑（第 9407 行起）改造为：

```python
async def _execute_publish_node(node, state, context, execution, session):
    """改造后的 PUBLISH 节点执行逻辑"""

    # 1. 收集要发布的商品（来自上游节点）
    polished_products = state.get("polished_products", [])
    generated_images = state.get("generated_images", {})
    account_id = state.get("selected_account_id")

    draft_records = []  # 用于返回节点输出

    # 2. 遍历商品，逐个创建草稿并尝试发布
    for product in polished_products:
        product_images = _resolve_product_images(product, generated_images)

        # 步骤A：先创建草稿记录（status=draft）
        draft = WorkflowGoodsDraft(
            tenant_id=execution.tenant_id,
            user_id=execution.user_id,
            workflow_id=execution.workflow_id,
            workflow_execution_id=execution.id,
            workflow_name=execution.workflow_name,
            node_key=node.node_key,
            account_id=account_id,
            title=product.get("title", ""),
            price=str(product.get("price", "")),
            description=product.get("description", ""),
            cover_pic=product_images[0] if product_images else None,
            image_urls=product_images,
            category=product.get("category", ""),
            stock=product.get("stock", 1),
            location=product.get("location"),
            raw_payload=product,
            publish_status="draft",
        )
        session.add(draft)
        await session.flush()  # 拿到 draft.id

        # 步骤B：尝试发布
        draft.publish_status = "publishing"
        draft.publish_attempt_count = 1
        draft.publish_time = datetime.utcnow()
        await session.commit()

        try:
            publisher = XianyuItemPublisher(cookie_str, execution.tenant_id)
            result = await publisher.publish({...})
            draft.publish_status = "published"
            draft.xianyu_goods_id = result.get("itemId")
        except Exception as e:
            draft.publish_status = "failed"
            draft.publish_error_message = str(e)

        await session.commit()
        draft_records.append({
            "draft_id": draft.id,
            "title": draft.title,
            "publish_status": draft.publish_status,
            "xianyu_goods_id": draft.xianyu_goods_id,
            "error": draft.publish_error_message,
        })

    # 3. 节点输出（保持与现有 publish_results 结构兼容）
    return {
        "publish_results": draft_records,
        "publish_result": {
            "total": len(draft_records),
            "success": sum(1 for d in draft_records if d["publish_status"] == "published"),
            "failed": sum(1 for d in draft_records if d["publish_status"] == "failed"),
        }
    }
```

### 5.2 关键约束

1. **无论发布成功或失败，草稿记录都保留** — 这是核心约束，通过 try/except 确保失败也写入 status=failed
2. **未生成 AI 封面图的商品严禁发布**（项目记忆中的硬约束）— 在创建草稿前先校验 `img_ai_ok == True`
3. **价格 <= 0 直接跳过**（保持现有逻辑）— 但仍创建草稿记录，状态为 `failed`，错误信息 "价格无效"
4. **已发布商品去重**（保持现有 `workflow_publish_record` 检查）— 在创建草稿前查询是否已有相同商品的 published 草稿

### 5.3 现有节点配置不变

PUBLISH 节点的前端默认配置保持不变（`apps/user-web/src/pages/WorkflowPage.vue` 第 2555 行）：

```javascript
{ publishIntervalSeconds: 30, category: '', addressText: '', address: {},
  priceStrategy: 'keep', enabled: true }
```

后端节点配置解析逻辑不变，仅发布执行逻辑改造。

---

## 六、前端页面设计

### 6.1 导航结构与路由注册

**`apps/user-web/src/data/nav.js`** 的「自动化」分组追加两个 `child: true` 子项：

```javascript
{ title: '自动化', items: [
  { key: 'workflow', label: '工作流', icon: 'workflow' },
  { key: 'workflow-tasks', label: '工作流任务', icon: 'task' },
  { key: 'workflow-drafts', label: '商品草稿箱', icon: 'document', child: true },
  { key: 'workflow-image-records', label: '图片生成记录', icon: 'image', child: true },
  { key: 'auto-delivery', label: '自动发货', icon: 'truck' },
  // ... 其余不变
]}
```

**`apps/user-web/src/App.vue`** 的 `pageMap` 追加：

```javascript
'workflow-drafts': asyncPage(() => import('./pages/WorkflowDraftsPage.vue')),
'workflow-image-records': asyncPage(() => import('./pages/WorkflowImageRecordsPage.vue')),
```

`pageTitles` 追加：

```javascript
'workflow-drafts': ['商品草稿箱', '工作流生成的商品草稿与发布记录'],
'workflow-image-records': ['图片生成记录', '所有生图模型调用产生的图片历史'],
```

### 6.2 商品草稿箱页面 `WorkflowDraftsPage.vue`

**布局参考**：`WorkflowTasksPage.vue`（同等工作流子页面风格）

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部统计卡片网格（4 个 StatCard）                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │ 草稿总数  │ │ 待发布    │ │ 已发布    │ │ 发布失败  │         │
│ │   156    │ │   42     │ │   98     │ │   16     │         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
├─────────────────────────────────────────────────────────────┤
│ CardPanel: 商品草稿列表                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 筛选区: [状态▼] [工作流▼] [关键词搜索] [时间范围]  [刷新] │ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │ │
│ │ │ [封面图]     │ │ [封面图]     │ │ [封面图]     │         │ │
│ │ │             │ │             │ │             │         │ │
│ │ │ 商品标题...  │ │ 商品标题...  │ │ 商品标题...  │         │ │
│ │ │ ¥29.9       │ │ ¥15.0       │ │ ¥88.0       │         │ │
│ │ │ [待发布]     │ │ [已发布]     │ │ [发布失败]   │         │ │
│ │ │ 来自: XX工作流│ │ 闲鱼ID:xxx  │ │ 失败: ...    │         │ │
│ │ │ 2026-07-19  │ │ 2026-07-18  │ │ 2026-07-17  │         │ │
│ │ │             │ │             │ │             │         │ │
│ │ │ [重试发布]   │ │ [查看详情]   │ │ [重试发布]   │         │ │
│ │ │ [删除]      │ │ [删除]      │ │ [查看详情]   │         │ │
│ │ └─────────────┘ └─────────────┘ └─────────────┘         │ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ [批量重试发布] [批量删除]    分页: < 1 2 3 ... >          │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**关键 UI 元素**：
- **状态徽章配色**（用现有 Badge 组件）：
  - 待发布：`type="blue"`（蓝色）
  - 已发布：`type="green"`（绿色）
  - 发布失败：`type="red"`（红色）
  - 发布中：`type="blue"` + 脉冲动画
- **卡片网格**：`grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))`，与 OpportunityPage 商品卡片风格一致
- **详情抽屉**：点击「查看详情」从右侧滑出抽屉，展示完整商品信息、图片大图预览、发布日志时间线（每次尝试的时间、状态、错误信息）、重试按钮
- **批量操作**：复选框选择后顶部出现批量操作栏

### 6.3 图片生成记录页面 `WorkflowImageRecordsPage.vue`

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部统计卡片网格（4 个 StatCard）                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │ 总生成数  │ │ 成功      │ │ 失败      │ │ 本月生成  │         │
│ │   423    │ │   398    │ │   25     │ │   67     │         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
├─────────────────────────────────────────────────────────────┤
│ CardPanel: 图片生成记录                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 筛选区: [来源▼] [模型▼] [状态▼] [工作流▼] [时间范围] [刷新]│ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │ │
│ │ │ [图] │ │ [图] │ │ [图] │ │ [图] │ │ [图] │           │ │
│ │ │      │ │      │ │      │ │      │ │      │           │ │
│ │ │SDXL  │ │FLUX  │ │SDXL  │ │Qwen  │ │SDXL  │           │ │
│ │ │成功   │ │成功   │ │失败   │ │成功   │ │成功   │           │ │
│ │ │07-19 │ │07-19 │ │07-18 │ │07-18 │ │07-17 │           │ │
│ │ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘           │ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ 分页: < 1 2 3 ... >                                     │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**关键 UI 元素**：
- **图片网格**：`grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))`，每个卡片正方形图片 + 下方信息
- **图片预览**：
  - 鼠标 hover 时图片轻微放大（`transform: scale(1.03)`），叠加半透明遮罩显示模型名和创建时间
  - 点击图片打开全屏 Lightbox 弹窗，展示大图、完整 prompt、生图参数（image_size/image_count/method_used）、状态、来源工作流
- **失败卡片**：图片位置展示错误图标 + 错误信息摘要，hover 显示完整错误
- **恢复图片**：详情弹窗中提供「恢复图片」按钮，调用现有 `/opportunity/image-recover/{historyId}` API
- **模型徽章**：用 Badge 显示模型名（如 `SDXL`/`FLUX`/`Qwen-Image`），不同模型不同颜色

### 6.4 视觉风格一致性

所有新页面严格遵循现有设计语言：

| 元素 | 规范 |
|------|------|
| 主色 | `#0d6bff` / `#2563eb` |
| 标题深色 | `#13213d` |
| 副文本 | `#5a6880` / `#8b97aa` |
| 错误红 | `#ef4444` |
| 成功绿 | `#16bf78` |
| 卡片 | 圆角 14-22px，`box-shadow: 0 18px 42px rgba(31, 53, 94, 0.08)`，`border: 1px solid rgba(231, 237, 247, 0.95)` |
| 间距 | 卡片间距 16px |
| 组件 | 复用 `CardPanel` / `StatCard` / `Badge` / `AppButton` / `BaseTable` / `EmptyState` / `Icon` |
| 输入框 | `.aics-input` 统一样式 |
| 三态分支 | `loading` / `loadError` / 正常渲染（错误态用红色边框 + 「重新加载」按钮） |

### 6.5 前端 API 文件

新建 `apps/user-web/src/api/workflowDrafts.js`：

```javascript
import { request } from './index.js'

export const listWorkflowDrafts = (params) =>
  request.get('/workflow/drafts', { params })

export const getWorkflowDraft = (id) =>
  request.get(`/workflow/drafts/${id}`)

export const retryPublishDraft = (id) =>
  request.post(`/workflow/drafts/${id}/retry-publish`)

export const batchRetryPublishDrafts = (ids) =>
  request.post('/workflow/drafts/batch-retry-publish', { ids })

export const deleteWorkflowDraft = (id) =>
  request.delete(`/workflow/drafts/${id}`)

export const getWorkflowDraftStats = () =>
  request.get('/workflow/drafts/stats')
```

扩展 `apps/user-web/src/api/opportunity.js`：

```javascript
// 已有 listOpportunityImageHistory，新增 image-records 专用查询（支持来源切换）
// source: 'all'（默认，所有来源）/ 'workflow' / 'opportunity'
export const listImageRecords = (params) =>
  request.get('/opportunity/image-history', {
    params: { source: 'all', ...params }
  })
```

---

## 七、数据库迁移策略

按 `.trae/rules/database-migration-on-release.md` 规则执行。

### 7.1 core-api 迁移

新建 `apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql`（DDL 见 3.2 节）。

**仅追加、非破坏性 DDL**，符合规则。同步更新 `db/migrations-manifest.json`，计算并填入 sha256。

### 7.2 automation-service 迁移

`workflow_goods_draft` 表通过 SQLAlchemy `Base.metadata.create_all` 自动建表（与现有 9 张工作流表一致），同时在 `apps/automation-service/migrations/` 目录追加 `V1.10__create_workflow_goods_draft.sql` 作为版本化记录（与 V1.9 之后衔接）：

```sql
CREATE TABLE IF NOT EXISTS workflow_goods_draft (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  user_id BIGINT NULL,
  workflow_id BIGINT NULL,
  workflow_execution_id BIGINT NULL,
  workflow_name VARCHAR(200) NULL,
  node_key VARCHAR(100) NULL,
  account_id BIGINT NULL,
  title VARCHAR(500) NOT NULL,
  price VARCHAR(50) NULL,
  description TEXT NULL,
  cover_pic TEXT NULL,
  image_urls JSON NULL,
  category VARCHAR(100) NULL,
  stock INT DEFAULT 1,
  location JSON NULL,
  raw_payload JSON NULL,
  publish_status VARCHAR(20) DEFAULT 'draft' NOT NULL,
  publish_time DATETIME NULL,
  xianyu_goods_id VARCHAR(100) NULL,
  publish_error_message TEXT NULL,
  publish_attempt_count INT DEFAULT 0,
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted TINYINT NOT NULL DEFAULT 0,
  INDEX idx_tenant_status_created (tenant_id, publish_status, created_time DESC),
  INDEX idx_workflow_execution (workflow_execution_id),
  INDEX idx_tenant_deleted (tenant_id, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

更新 `db/migrations-manifest.json` 中 `automation_mysql` 的 `migrations` 数组，追加 V1.10 条目并计算 sha256。

### 7.3 evidence 产出

上线前产出 `db/migration-evidence.json`，包含 `core_mysql` 与 `automation_mysql` 两个数据库的 backup/restore drill 验证记录。

---

## 八、实施分阶段

为降低风险，分 3 个阶段实施：

**阶段 1（后端基础）**：
- 数据库迁移脚本（V1.25 + V1.10）
- ORM 实体（`WorkflowGoodsDraft`）
- workflow_draft_service.py（草稿 CRUD + 重试发布）
- ImageGenerationService 扩展 source 参数
- Java 网关 API（草稿箱 6 个端点 + image-history source 参数）
- Python 路由 API

**阶段 2（工作流改造）**：
- automation_runtime.py 中 PUBLISH 节点改造（先存草稿→再发布→更新状态）
- IMAGE_GENERATE 节点调用生图时传入 source=workflow 等参数
- 单元测试覆盖：发布成功/失败/价格无效/已发布去重场景

**阶段 3（前端页面）**：
- nav.js 追加两个 nav 项
- App.vue pageMap 注册
- WorkflowDraftsPage.vue 完整页面
- WorkflowImageRecordsPage.vue 完整页面
- api/workflowDrafts.js + api/opportunity.js 扩展

---

## 九、关键文件清单

### 9.1 新建文件

| 文件 | 用途 |
|------|------|
| `apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql` | core-api 迁移脚本 |
| `apps/automation-service/migrations/V1.10__create_workflow_goods_draft.sql` | automation-service 迁移脚本 |
| `apps/automation-service/app/services/workflow_draft_service.py` | 草稿服务（CRUD + 重试发布） |
| `apps/user-web/src/pages/WorkflowDraftsPage.vue` | 商品草稿箱页面 |
| `apps/user-web/src/pages/WorkflowImageRecordsPage.vue` | 图片生成记录页面 |
| `apps/user-web/src/api/workflowDrafts.js` | 草稿箱前端 API |

### 9.2 修改文件

| 文件 | 改动点 |
|------|--------|
| `apps/automation-service/app/models/entities.py` | 追加 `WorkflowGoodsDraft` ORM 类 |
| `apps/automation-service/app/api/v1/routes/workflow.py` | 追加 6 个草稿箱路由 |
| `apps/automation-service/app/services/automation_runtime.py` | PUBLISH 节点改造 + IMAGE_GENERATE 节点传 source |
| `apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java` | 追加 6 个草稿箱端点 + image-history source 透传 |
| `apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java` | saveGenerationHistory 接受 source 参数 |
| `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java` | 兜底 ALTER 新字段 |
| `apps/user-web/src/data/nav.js` | 追加 2 个 nav 项 |
| `apps/user-web/src/App.vue` | pageMap 注册 2 个页面 |
| `apps/user-web/src/api/opportunity.js` | 追加 listWorkflowImageRecords |
| `db/migrations-manifest.json` | 追加 V1.25 + V1.10 条目 |

---

## 十、约束与风险

### 10.1 必须遵守的硬约束

- **未生成 AI 封面图的商品严禁发布**（`img_ai_ok == True` 才允许进入发布流程）
- **数据库迁移仅追加、非破坏性**：所有 DDL 用 `ADD COLUMN`、`CREATE TABLE IF NOT EXISTS`、`ADD INDEX`
- **Java 网关代理 Python 时必须拆包 ResultObject**，仅返回 `data` 字段
- **Vite dev server 配置 /uploads 路径代理到 http://localhost:12401**（图片访问）
- **core-api multipart 文件上传限制**：max-file-size:20MB, max-request-size:50MB
- **上线前必须执行数据库备份并产出 migration-evidence.json**

### 10.2 风险与对策

| 风险 | 对策 |
|------|------|
| PUBLISH 节点改造影响存量工作流执行 | 保持节点配置字段不变，仅改造执行逻辑；节点输出 `publish_results` 结构保持兼容 |
| `opportunity_image_history` 表数据量增大 | 新增 `idx_source_tenant_created` 索引；列表查询强制带 `source` 过滤 |
| 重试发布与正在执行的工作流冲突 | 重试前检查 `publish_status != "publishing"`；并发场景用乐观锁（`updated_time` 比较） |
| 草稿表与 `workflow_publish_record` 数据不一致 | 草稿 `publish_status=published` 时同步写入 `workflow_publish_record`（保持现有逻辑） |

---

## 十一、验收标准

### 11.1 功能验收

1. **工作流执行后产生草稿**：执行包含 PUBLISH 节点的工作流，商品草稿箱中可见所有商品（含发布成功/失败）
2. **发布失败可重试**：在草稿箱点击「重试发布」，发布成功后状态变为「已发布」
3. **批量重试**：勾选多个失败草稿，点击「批量重试发布」可批量执行
4. **图片生成记录可见**：工作流中调用的生图图片出现在「图片生成记录」页面
5. **图片预览**：点击图片可查看大图、完整 prompt、生图参数
6. **图片恢复**：失败图片可通过「恢复图片」按钮重新获取
7. **筛选与搜索**：草稿箱支持按状态/工作流/关键词/时间筛选；图片记录支持按模型/状态/工作流/时间筛选
8. **统计卡片**：两个页面顶部统计卡片实时反映数据状态

### 11.2 兼容性验收

1. **商机发掘生图不受影响**：`opportunity_image_history.source` 默认 `opportunity`，现有商机发掘调用不传 source 仍正常工作
2. **现有工作流执行不受影响**：未改造的节点（PRODUCT_FETCH/PRODUCT_FILTER/PRODUCT_POLISH/IMAGE_GENERATE/TRIGGER）行为完全不变
3. **PUBLISH 节点输出兼容**：`publish_results` 数组结构保持，下游消费者（如 NOTIFICATION 节点）无需改造
4. **数据库迁移幂等**：迁移脚本可重复执行不报错

### 11.3 上线前检查

- [ ] 数据库迁移脚本已写入 `db/migrations-manifest.json` 并计算 sha256
- [ ] migration-evidence.json 产出（backup/restore drill verified/passed）
- [ ] 本地与线上 `DATA_SYNC_API_TOKEN` 一致性校验通过
- [ ] 商业版前端 `VITE_SHOW_DATA_SYNC=false`
- [ ] 前台更新日志已更新（`apps/user-web/src/data/releaseNotes.js` + `package.json` version）
