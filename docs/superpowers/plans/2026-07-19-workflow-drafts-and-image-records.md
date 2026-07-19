# 工作流商品草稿箱与图片生成记录 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作流子类下新增「商品草稿箱」与「图片生成记录」两个子页面，并改造 PUBLISH 节点在发布前先存草稿（无论成功失败都保留）。

**Architecture:** 方案 A（复用扩展）：复用 `opportunity_image_history` 表加 `source` 字段区分生图来源；新建 `workflow_goods_draft` 表存储商品草稿与发布状态流转；PUBLISH 节点改造为先创建草稿、再尝试发布、更新状态。

**Tech Stack:** Java 17 + Spring Boot 3.5 + JdbcTemplate + Flyway；Python 3 + FastAPI + SQLAlchemy 2.0 async；Vue 3.5 + Vite 8 + 自研组件库；MySQL 8.4

**Spec:** `docs/superpowers/specs/2026-07-19-workflow-drafts-and-image-records-design.md`

**版本号修正**：spec 中提到的 automation-service 迁移 `V1.10__create_workflow_goods_draft.sql` 实际应为 `V1.12__create_workflow_goods_draft.sql`（当前最新版本为 V1.11，需衔接为 V1.12）。core-api 迁移 `V1.25` 保持不变（当前最新 V1.24）。

---

## 文件结构

**新建文件：**

| 文件 | 职责 |
|------|------|
| `apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql` | core-api 迁移：opportunity_image_history 加 source 字段 |
| `apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql` | automation-service 迁移：新建 workflow_goods_draft 表 |
| `apps/automation-service/app/services/workflow_draft_service.py` | 草稿服务：CRUD + 重试发布 |
| `apps/automation-service/tests/test_workflow_draft_service.py` | 草稿服务单元测试 |
| `apps/user-web/src/api/workflowDrafts.js` | 草稿箱前端 API |
| `apps/user-web/src/pages/WorkflowDraftsPage.vue` | 商品草稿箱页面 |

**修改文件：**

| 文件 | 改动点 |
|------|--------|
| `apps/automation-service/app/models/entities.py` | 追加 `WorkflowGoodsDraft` ORM 类 |
| `apps/automation-service/app/api/v1/routes/workflow.py` | 追加 6 个草稿箱路由 |
| `apps/automation-service/app/services/automation_runtime.py` | PUBLISH 节点改造 + IMAGE_GENERATE 节点传 source |
| `apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java` | 追加 6 个草稿箱端点 + image-history source 透传 + generate-images source 透传 |
| `apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java` | saveGenerationHistory/listHistory 接受 source 参数 |
| `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java` | 兜底 ALTER 新字段 |
| `apps/user-web/src/data/nav.js` | 追加 2 个 nav 项 |
| `apps/user-web/src/App.vue` | pageMap 注册 2 个页面 |
| `apps/user-web/src/api/opportunity.js` | 已有 listImageRecords，确认无需修改 |
| `apps/user-web/src/pages/WorkflowImageRecordsPage.vue` | 已存在，需对照接口字段微调 |
| `db/migrations-manifest.json` | 追加 V1.25 + V1.12 条目 |
| `apps/user-web/src/data/releaseNotes.js` | 追加更新日志 |
| `apps/user-web/package.json` | 版本号 +1 |

---

## Task 1: core-api 迁移脚本 V1.25

**Files:**
- Create: `apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- V1.25: 为 opportunity_image_history 增加生图来源字段，区分商机发掘与工作流
ALTER TABLE opportunity_image_history
  ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'opportunity'
    COMMENT '生图来源：opportunity=商机发掘 / workflow=工作流',
  ADD COLUMN workflow_id BIGINT NULL COMMENT '工作流定义ID（source=workflow 时）',
  ADD COLUMN workflow_execution_id BIGINT NULL COMMENT '工作流执行记录ID（source=workflow 时）',
  ADD COLUMN workflow_node_key VARCHAR(100) NULL COMMENT '生图节点key（source=workflow 时）',
  ADD INDEX idx_oih_source_tenant_created (source, tenant_id, created_time DESC);
```

- [ ] **Step 2: 计算文件 sha256**

Run: `certutil -hashfile apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql SHA256` (Windows) 或 `sha256sum apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql` (Linux)

记录输出 sha256 值，Task 13 中会用到。

- [ ] **Step 3: Commit**

```bash
git add apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql
git commit -m "feat(core-api): V1.25 迁移 - opportunity_image_history 增加生图来源字段"
```

---

## Task 2: SchemaCompatibilityRunner 兜底 ALTER

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java`

`SchemaCompatibilityRunner` 已有 `addColumnIfMissing` 与 `createIndexIfMissing` 工具方法，且已对 `opportunity_image_history` 现有字段做过兜底（第 1760-1780 行附近）。本任务追加新字段兜底。

- [ ] **Step 1: 定位插入点**

在 `SchemaCompatibilityRunner.java` 中搜索 `idx_oih_created_time`，在它之后的 `opportunity_image_history` 兜底块末尾追加新字段。

- [ ] **Step 2: 追加兜底 ALTER**

```java
// V1.25: 生图来源相关字段（兼容旧库自动补字段）
addColumnIfMissing("opportunity_image_history", "source", "VARCHAR(20) NOT NULL DEFAULT 'opportunity'");
addColumnIfMissing("opportunity_image_history", "workflow_id", "BIGINT NULL");
addColumnIfMissing("opportunity_image_history", "workflow_execution_id", "BIGINT NULL");
addColumnIfMissing("opportunity_image_history", "workflow_node_key", "VARCHAR(100) NULL");
createIndexIfMissing("opportunity_image_history", "idx_oih_source_tenant_created",
        "CREATE INDEX idx_oih_source_tenant_created ON opportunity_image_history(source, tenant_id, created_time DESC)");
```

- [ ] **Step 3: 编译验证**

Run: `cd apps/core-api && mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/config/SchemaCompatibilityRunner.java
git commit -m "feat(core-api): SchemaCompatibilityRunner 兜底 opportunity_image_history 来源字段"
```

---

## Task 3: ImageGenerationService.saveGenerationHistory 接受 source 参数

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java`

当前 `saveGenerationHistory` 在第 1147 行，签名是 `(tenantId, userId, requestId, model, prompt, size, images, method)`。需要扩展接受可选 source 参数。

- [ ] **Step 1: 改造方法签名（重载保持向后兼容）**

将原 `private void saveGenerationHistory(...)` 改为委托到新签名：

```java
private void saveGenerationHistory(Long tenantId, Long userId, String requestId,
                                    String model, String prompt, String size,
                                    List<Map<String, Object>> images, String method) {
    saveGenerationHistory(tenantId, userId, requestId, model, prompt, size, images, method,
            "opportunity", null, null, null);
}

private void saveGenerationHistory(Long tenantId, Long userId, String requestId,
                                    String model, String prompt, String size,
                                    List<Map<String, Object>> images, String method,
                                    String source, Long workflowId,
                                    Long workflowExecutionId, String workflowNodeKey) {
    try {
        List<Map<String, Object>> saveImages = new ArrayList<>();
        for (Map<String, Object> img : images) {
            Map<String, Object> saveImg = new LinkedHashMap<>();
            if (img.containsKey("url")) saveImg.put("url", img.get("url"));
            if (img.containsKey("originalUrl")) {
                saveImg.put("encryptedOriginalUrl",
                        sensitiveValueCrypto.encrypt(String.valueOf(img.get("originalUrl"))));
            }
            if (img.containsKey("index")) saveImg.put("index", img.get("index"));
            saveImages.add(saveImg);
        }
        String imagesJson = objectMapper.writeValueAsString(saveImages);

        jdbcTemplate.update(
                "INSERT INTO opportunity_image_history(tenant_id,user_id,request_id,model,prompt,image_size," +
                "image_count,result_images,method_used,status,raw_response,source,workflow_id," +
                "workflow_execution_id,workflow_node_key,created_time,updated_time,deleted) " +
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId, userId, requestId, model, prompt, size,
                saveImages.size(), imagesJson, method, "success", "{}",
                source == null ? "opportunity" : source, workflowId,
                workflowExecutionId, workflowNodeKey);
    } catch (Exception e) {
        log.warn("[生图历史] 保存失败, errorType={}", e.getClass().getSimpleName());
    }
}
```

- [ ] **Step 2: 在 generate 方法中识别 source 参数**

定位 `generate()` 方法（约第 100 行起），在解析 payload 处提取 source 相关字段并传给 `saveGenerationHistory`。原调用点在第 364 行：

```java
// 原代码：
// saveGenerationHistory(tenantId, userId, requestId, model, finalPrompt, size, validImages, methodUsed);

// 改为：
String source = String.valueOf(payload.getOrDefault("source", "opportunity"));
Long workflowId = payload.get("workflowId") instanceof Number n ? n.longValue() : null;
Long workflowExecutionId = payload.get("workflowExecutionId") instanceof Number n ? n.longValue() : null;
String workflowNodeKey = payload.get("workflowNodeKey") == null ? null : String.valueOf(payload.get("workflowNodeKey"));
saveGenerationHistory(tenantId, userId, requestId, model, finalPrompt, size, validImages, methodUsed,
        source, workflowId, workflowExecutionId, workflowNodeKey);
```

- [ ] **Step 3: 编译验证**

Run: `cd apps/core-api && mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java
git commit -m "feat(core-api): ImageGenerationService.saveGenerationHistory 支持 source 参数"
```

---

## Task 4: ImageGenerationService.listHistory 支持 source 过滤

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java`

当前 `listHistory(tenantId, limit)` 在第 439 行，只返回固定 limit 条记录。需扩展为支持 source/分页/关键词过滤。

- [ ] **Step 1: 新增 listHistory 重载方法**

```java
public List<Map<String, Object>> listHistory(Long tenantId, int limit) {
    return listHistory(tenantId, limit, null, null, null, null, null, null, null);
}

/**
 * 查询生图历史（支持来源/分页/关键词过滤）
 * @param source "all" 或 null=所有来源；"opportunity"=商机发掘；"workflow"=工作流
 */
public Map<String, Object> listHistoryPaged(Long tenantId, String source, String status, String keyword,
                                              Long workflowId, String nodeKey,
                                              int page, int pageSize) {
    int offset = Math.max(0, (page - 1) * pageSize);
    StringBuilder where = new StringBuilder("WHERE tenant_id=? AND deleted=0");
    List<Object> args = new ArrayList<>();
    args.add(tenantId);
    if (source != null && !source.isBlank() && !"all".equalsIgnoreCase(source)) {
        where.append(" AND source=?");
        args.add(source);
    }
    if (status != null && !status.isBlank()) {
        where.append(" AND status=?");
        args.add(status);
    }
    if (keyword != null && !keyword.isBlank()) {
        where.append(" AND (prompt LIKE ? OR model LIKE ?)");
        args.add("%" + keyword + "%");
        args.add("%" + keyword + "%");
    }
    if (workflowId != null) {
        where.append(" AND workflow_id=?");
        args.add(workflowId);
    }
    if (nodeKey != null && !nodeKey.isBlank()) {
        where.append(" AND workflow_node_key=?");
        args.add(nodeKey);
    }

    Long total = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM opportunity_image_history " + where, Long.class, args.toArray());
    if (total == null) total = 0L;

    List<Map<String, Object>> records = jdbcTemplate.queryForList(
            "SELECT id,tenant_id,user_id,request_id,model,prompt,image_size,image_count,result_images," +
            "method_used,status,error_message,source,workflow_id,workflow_execution_id,workflow_node_key," +
            "created_time,updated_time FROM opportunity_image_history " + where +
            " ORDER BY created_time DESC LIMIT ? OFFSET ?",
            appendArgs(args, pageSize, offset));

    Map<String, Object> result = new LinkedHashMap<>();
    result.put("records", records);
    result.put("total", total);
    result.put("page", page);
    result.put("pageSize", pageSize);
    return result;
}

private List<Map<String, Object>> listHistory(Long tenantId, int limit, String source, String status,
                                                String keyword, Long workflowId, String nodeKey,
                                                Integer page, Integer pageSize) {
    // 兼容旧调用：仅按 limit 返回
    if (page == null || pageSize == null) {
        StringBuilder where = new StringBuilder("WHERE tenant_id=? AND deleted=0");
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (source != null && !source.isBlank() && !"all".equalsIgnoreCase(source)) {
            where.append(" AND source=?");
            args.add(source);
        }
        return jdbcTemplate.queryForList(
                "SELECT id,tenant_id,user_id,request_id,model,prompt,image_size,image_count,result_images," +
                "method_used,status,source,workflow_id,workflow_execution_id,workflow_node_key," +
                "created_time FROM opportunity_image_history " + where +
                " ORDER BY created_time DESC LIMIT ?",
                appendArgs(args, limit));
    }
    return (List<Map<String, Object>>) listHistoryPaged(tenantId, source, status, keyword,
            workflowId, nodeKey, page, pageSize).get("records");
}

private Object[] appendArgs(List<Object> args, Object... tail) {
    List<Object> all = new ArrayList<>(args);
    for (Object t : tail) all.add(t);
    return all.toArray();
}
```

- [ ] **Step 2: 编译验证**

Run: `cd apps/core-api && mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java
git commit -m "feat(core-api): ImageGenerationService.listHistory 支持 source/分页/关键词过滤"
```

---

## Task 5: AutomationProxyController 透传 source 参数

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java`

`/opportunity/generate-images` 当前在第 476 行，body 已经透传给 service，无需额外改造（source 已在 payload 中）。`/opportunity/image-history` 在第 490 行，需要改造为支持 source 参数。

- [ ] **Step 1: 改造 /opportunity/image-history 端点**

```java
@GetMapping("/opportunity/image-history")
public Result<Object> opportunityImageHistory(
        @RequestParam(defaultValue = "all") String source,
        @RequestParam(required = false) String status,
        @RequestParam(required = false) String keyword,
        @RequestParam(required = false) Long workflowId,
        @RequestParam(required = false) String nodeKey,
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "20") int pageSize,
        @RequestParam(defaultValue = "20") int limit) {
    try {
        // 如果只传了 limit 没传 page/pageSize 的非默认值，走旧接口（兼容商机发掘页面）
        if (page == 1 && pageSize == 20 && "all".equalsIgnoreCase(source)
                && status == null && keyword == null && workflowId == null && nodeKey == null) {
            return Result.ok(imageGenerationService.listHistory(TenantContext.getCurrentTenantId(), limit));
        }
        return Result.ok(imageGenerationService.listHistoryPaged(
                TenantContext.getCurrentTenantId(), source, status, keyword,
                workflowId, nodeKey, page, pageSize));
    } catch (Exception e) {
        log.error("查询图片生成历史失败, errorType={}", e.getClass().getSimpleName());
        throw new BizException(503, "图片生成历史暂时无法查询，请稍后重试");
    }
}
```

- [ ] **Step 2: 编译验证**

Run: `cd apps/core-api && mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java
git commit -m "feat(core-api): /opportunity/image-history 端点支持 source/分页/关键词过滤"
```

---

## Task 6: automation-service 迁移脚本 V1.12

**Files:**
- Create: `apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- V1.12: 工作流商品草稿箱表（与 workflow_definition 等表同库）
CREATE TABLE IF NOT EXISTS workflow_goods_draft (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL COMMENT '租户ID',
  user_id BIGINT NULL COMMENT '用户ID',
  workflow_id BIGINT NULL COMMENT '工作流定义ID',
  workflow_execution_id BIGINT NULL COMMENT '工作流执行记录ID',
  workflow_name VARCHAR(200) NULL COMMENT '工作流名称（冗余存储）',
  node_key VARCHAR(100) NULL COMMENT '产生该商品的节点key',
  account_id BIGINT NULL COMMENT '闲鱼账号ID',
  title VARCHAR(500) NOT NULL COMMENT '商品标题',
  price VARCHAR(50) NULL COMMENT '商品价格',
  description TEXT NULL COMMENT '商品描述',
  cover_pic TEXT NULL COMMENT '封面图URL',
  image_urls JSON NULL COMMENT '图片URL列表',
  category VARCHAR(100) NULL COMMENT '分类',
  stock INT DEFAULT 1 COMMENT '库存',
  location JSON NULL COMMENT '发货地',
  raw_payload JSON NULL COMMENT '原始商品数据快照',
  source_item_id VARCHAR(100) NULL COMMENT '源商品ID（去重用）',
  source_title_hash VARCHAR(64) NULL COMMENT '源标题hash（去重用）',
  publish_status VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT 'draft/publishing/published/failed',
  publish_time DATETIME NULL COMMENT '发布时间',
  xianyu_goods_id VARCHAR(100) NULL COMMENT '闲鱼返回的商品ID',
  publish_error_message TEXT NULL COMMENT '发布失败错误信息',
  publish_attempt_count INT DEFAULT 0 COMMENT '发布尝试次数',
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted TINYINT NOT NULL DEFAULT 0,
  INDEX idx_wgd_tenant_status_created (tenant_id, publish_status, created_time DESC),
  INDEX idx_wgd_workflow_execution (workflow_execution_id),
  INDEX idx_wgd_tenant_deleted (tenant_id, deleted),
  INDEX idx_wgd_dedup (tenant_id, account_id, source_item_id, source_title_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流商品草稿箱';
```

- [ ] **Step 2: 计算 sha256**

Run: `sha256sum apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql` (Linux) 或 `certutil -hashfile apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql SHA256` (Windows)

记录输出，Task 13 中会用到。

- [ ] **Step 3: Commit**

```bash
git add apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql
git commit -m "feat(automation-service): V1.12 迁移 - 工作流商品草稿箱表"
```

---

## Task 7: WorkflowGoodsDraft ORM 实体

**Files:**
- Modify: `apps/automation-service/app/models/entities.py` (在 WorkflowPublishRecord 类后追加)

- [ ] **Step 1: 在 WorkflowPublishRecord 后追加 WorkflowGoodsDraft 类**

```python
class WorkflowGoodsDraft(Base):
    """工作流商品草稿箱：发布前先存草稿，无论成功失败都保留"""
    __tablename__ = "workflow_goods_draft"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=True)
    workflow_id = Column(BigInteger, nullable=True, index=True)
    workflow_execution_id = Column(BigInteger, nullable=True, index=True)
    workflow_name = Column(String(200), nullable=True)
    node_key = Column(String(100), nullable=True)
    account_id = Column(BigInteger, nullable=True)
    title = Column(String(500), nullable=False)
    price = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    cover_pic = Column(Text, nullable=True)
    image_urls = Column(JSON, nullable=True)
    category = Column(String(100), nullable=True)
    stock = Column(Integer, default=1)
    location = Column(JSON, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    source_item_id = Column(String(100), nullable=True)
    source_title_hash = Column(String(64), nullable=True)
    publish_status = Column(String(20), default="draft", nullable=False, index=True)
    publish_time = Column(DateTime, nullable=True)
    xianyu_goods_id = Column(String(100), nullable=True)
    publish_error_message = Column(Text, nullable=True)
    publish_attempt_count = Column(Integer, default=0)
    created_time = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted = Column(SmallInteger, default=0, nullable=False)
```

- [ ] **Step 2: 验证导入**

Run: `cd apps/automation-service && python -c "from app.models.entities import WorkflowGoodsDraft; print(WorkflowGoodsDraft.__tablename__)"`
Expected: `workflow_goods_draft`

- [ ] **Step 3: Commit**

```bash
git add apps/automation-service/app/models/entities.py
git commit -m "feat(automation-service): WorkflowGoodsDraft ORM 实体"
```

---

## Task 8: workflow_draft_service.py 草稿服务

**Files:**
- Create: `apps/automation-service/app/services/workflow_draft_service.py`
- Test: `apps/automation-service/tests/test_workflow_draft_service.py`

- [ ] **Step 1: 编写失败测试**

创建 `apps/automation-service/tests/test_workflow_draft_service.py`：

```python
"""草稿服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.workflow_draft_service import (
    list_drafts, get_draft, retry_publish_draft,
    batch_retry_publish_drafts, delete_draft, get_draft_stats
)


@pytest.mark.anyio
async def test_list_drafts_returns_paged_records():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        MagicMock(id=1, title="测试商品", publish_status="draft",
                 price="9.9", cover_pic="http://x/a.png",
                 workflow_name="WF1", created_time=None)
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=1)
    result = await list_drafts(mock_session, tenant_id=1, page=1, page_size=20)
    assert result["total"] == 1
    assert len(result["records"]) == 1


@pytest.mark.anyio
async def test_retry_publish_draft_rejects_already_publishing():
    mock_session = AsyncMock()
    draft = MagicMock()
    draft.id = 1
    draft.publish_status = "publishing"
    draft.tenant_id = 1
    mock_session.scalar = AsyncMock(return_value=draft)
    with pytest.raises(ValueError, match="正在发布中"):
        await retry_publish_draft(mock_session, draft_id=1, tenant_id=1)


@pytest.mark.anyio
async def test_get_draft_stats_returns_correct_counts():
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[100, 30, 50, 20])
    stats = await get_draft_stats(mock_session, tenant_id=1)
    assert stats["total"] == 100
    assert stats["draft"] == 30
    assert stats["published"] == 50
    assert stats["failed"] == 20
```

- [ ] **Step 2: 验证测试失败**

Run: `cd apps/automation-service && pytest tests/test_workflow_draft_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.workflow_draft_service'`

- [ ] **Step 3: 创建草稿服务**

创建 `apps/automation-service/app/services/workflow_draft_service.py`：

```python
"""工作流商品草稿箱服务：CRUD + 重试发布"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.entities import WorkflowGoodsDraft

logger = logging.getLogger(__name__)


async def list_drafts(
    session: AsyncSession,
    tenant_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    workflow_id: Optional[int] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """分页查询草稿列表"""
    conditions = ["tenant_id = :tenant_id", "deleted = 0"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if status and status != "all":
        conditions.append("publish_status = :status")
        params["status"] = status
    if workflow_id:
        conditions.append("workflow_id = :workflow_id")
        params["workflow_id"] = workflow_id
    if keyword:
        conditions.append("(title LIKE :keyword OR description LIKE :keyword)")
        params["keyword"] = f"%{keyword}%"
    if start_date:
        conditions.append("created_time >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("created_time <= :end_date")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)
    offset = max(0, (page - 1) * page_size)

    count_sql = f"SELECT COUNT(*) FROM workflow_goods_draft WHERE {where_clause}"
    total = await session.scalar(text(count_sql), params)
    total = int(total or 0)

    list_sql = (
        f"SELECT id, tenant_id, user_id, workflow_id, workflow_execution_id, workflow_name, "
        f"node_key, account_id, title, price, description, cover_pic, image_urls, category, "
        f"stock, publish_status, publish_time, xianyu_goods_id, publish_error_message, "
        f"publish_attempt_count, created_time, updated_time "
        f"FROM workflow_goods_draft WHERE {where_clause} "
        f"ORDER BY created_time DESC LIMIT :limit OFFSET :offset"
    )
    params_with_paging = {**params, "limit": page_size, "offset": offset}
    result = await session.execute(text(list_sql), params_with_paging)
    records = [dict(row._mapping) for row in result.all()]

    # 序列化 image_urls JSON
    for r in records:
        if r.get("image_urls") and isinstance(r["image_urls"], str):
            try:
                import json
                r["image_urls"] = json.loads(r["image_urls"])
            except Exception:
                pass
        if r.get("publish_time"):
            r["publish_time"] = r["publish_time"].isoformat() if hasattr(r["publish_time"], "isoformat") else str(r["publish_time"])
        if r.get("created_time"):
            r["created_time"] = r["created_time"].isoformat() if hasattr(r["created_time"], "isoformat") else str(r["created_time"])
        if r.get("updated_time"):
            r["updated_time"] = r["updated_time"].isoformat() if hasattr(r["updated_time"], "isoformat") else str(r["updated_time"])

    return {"records": records, "total": total, "page": page, "pageSize": page_size}


async def get_draft(session: AsyncSession, draft_id: int, tenant_id: int) -> Optional[Dict[str, Any]]:
    """获取草稿详情"""
    result = await session.execute(
        text("SELECT * FROM workflow_goods_draft WHERE id=:id AND tenant_id=:tid AND deleted=0"),
        {"id": draft_id, "tid": tenant_id}
    )
    row = result.first()
    if not row:
        return None
    record = dict(row._mapping)
    if record.get("image_urls") and isinstance(record["image_urls"], str):
        try:
            import json
            record["image_urls"] = json.loads(record["image_urls"])
        except Exception:
            pass
    if record.get("location") and isinstance(record["location"], str):
        try:
            import json
            record["location"] = json.loads(record["location"])
        except Exception:
            pass
    if record.get("raw_payload") and isinstance(record["raw_payload"], str):
        try:
            import json
            record["raw_payload"] = json.loads(record["raw_payload"])
        except Exception:
            pass
    for k in ("publish_time", "created_time", "updated_time"):
        if record.get(k):
            record[k] = record[k].isoformat() if hasattr(record[k], "isoformat") else str(record[k])
    return record


async def retry_publish_draft(session: AsyncSession, draft_id: int, tenant_id: int) -> Dict[str, Any]:
    """重试发布单个草稿"""
    result = await session.execute(
        text("SELECT * FROM workflow_goods_draft WHERE id=:id AND tenant_id=:tid AND deleted=0"),
        {"id": draft_id, "tid": tenant_id}
    )
    row = result.first()
    if not row:
        raise ValueError("草稿不存在")
    draft = dict(row._mapping)

    if draft["publish_status"] == "publishing":
        raise ValueError("该草稿正在发布中，请勿重复操作")
    if draft["publish_status"] == "published":
        raise ValueError("该草稿已发布成功，无需重试")

    # 更新状态为发布中
    await session.execute(
        text("""UPDATE workflow_goods_draft
                SET publish_status='publishing', publish_attempt_count=publish_attempt_count+1,
                    publish_time=NOW(), updated_time=NOW()
                WHERE id=:id"""),
        {"id": draft_id}
    )
    await session.commit()

    # 复用 XianyuItemPublisher
    try:
        from app.services.xianyu_goods_sync import XianyuItemPublisher, extract_token_from_cookie
        from app.services.account_service import get_account_cookie  # 复用现有账号查询

        account_id = draft.get("account_id")
        cookie_str = await get_account_cookie(session, tenant_id, account_id) if account_id else None
        if not cookie_str:
            raise RuntimeError("发布账号登录状态不可用，请重新登录")

        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        item_data = {
            "title": draft["title"],
            "desc": draft.get("description", ""),
            "imageUrls": draft.get("image_urls") or [],
            "price": draft.get("price", "1"),
            "quantity": draft.get("stock", 1),
        }
        if draft.get("category"):
            item_data["category"] = {"catName": draft["category"]}
        if draft.get("location"):
            item_data["location"] = draft["location"]

        result_pub = publisher.publish(item_data)
        if result_pub.get("success"):
            xianyu_goods_id = str(result_pub.get("itemId", ""))
            await session.execute(
                text("""UPDATE workflow_goods_draft
                        SET publish_status='published', xianyu_goods_id=:gid,
                            publish_error_message=NULL, updated_time=NOW()
                        WHERE id=:id"""),
                {"gid": xianyu_goods_id, "id": draft_id}
            )
            await session.commit()
            return {"success": True, "xianyuGoodsId": xianyu_goods_id, "draftId": draft_id}
        else:
            err_msg = str(result_pub.get("error", "发布失败"))
            await session.execute(
                text("""UPDATE workflow_goods_draft
                        SET publish_status='failed', publish_error_message=:err,
                            updated_time=NOW()
                        WHERE id=:id"""),
                {"err": err_msg[:2000], "id": draft_id}
            )
            await session.commit()
            return {"success": False, "error": err_msg, "draftId": draft_id}

    except Exception as e:
        logger.exception("[草稿重试] 发布失败 draft_id=%s", draft_id)
        await session.execute(
            text("""UPDATE workflow_goods_draft
                    SET publish_status='failed', publish_error_message=:err,
                        updated_time=NOW()
                    WHERE id=:id"""),
            {"err": str(e)[:2000], "id": draft_id}
        )
        await session.commit()
        return {"success": False, "error": str(e), "draftId": draft_id}


async def batch_retry_publish_drafts(
    session: AsyncSession, draft_ids: List[int], tenant_id: int
) -> Dict[str, Any]:
    """批量重试发布"""
    results = []
    success_count = 0
    failed_count = 0
    for draft_id in draft_ids:
        try:
            r = await retry_publish_draft(session, draft_id, tenant_id)
            results.append({"draftId": draft_id, **r})
            if r.get("success"):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            results.append({"draftId": draft_id, "success": False, "error": str(e)})
            failed_count += 1
    return {
        "results": results,
        "total": len(draft_ids),
        "success": success_count,
        "failed": failed_count,
    }


async def delete_draft(session: AsyncSession, draft_id: int, tenant_id: int) -> bool:
    """软删除草稿"""
    result = await session.execute(
        text("UPDATE workflow_goods_draft SET deleted=1, updated_time=NOW() WHERE id=:id AND tenant_id=:tid"),
        {"id": draft_id, "tid": tenant_id}
    )
    await session.commit()
    return result.rowcount > 0


async def get_draft_stats(session: AsyncSession, tenant_id: int) -> Dict[str, int]:
    """草稿统计"""
    total = await session.scalar(
        text("SELECT COUNT(*) FROM workflow_goods_draft WHERE tenant_id=:tid AND deleted=0"),
        {"tid": tenant_id}
    )
    draft = await session.scalar(
        text("SELECT COUNT(*) FROM workflow_goods_draft WHERE tenant_id=:tid AND deleted=0 AND publish_status='draft'"),
        {"tid": tenant_id}
    )
    published = await session.scalar(
        text("SELECT COUNT(*) FROM workflow_goods_draft WHERE tenant_id=:tid AND deleted=0 AND publish_status='published'"),
        {"tid": tenant_id}
    )
    failed = await session.scalar(
        text("SELECT COUNT(*) FROM workflow_goods_draft WHERE tenant_id=:tid AND deleted=0 AND publish_status='failed'"),
        {"tid": tenant_id}
    )
    return {
        "total": int(total or 0),
        "draft": int(draft or 0),
        "published": int(published or 0),
        "failed": int(failed or 0),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd apps/automation-service && pytest tests/test_workflow_draft_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/automation-service/app/services/workflow_draft_service.py apps/automation-service/tests/test_workflow_draft_service.py
git commit -m "feat(automation-service): workflow_draft_service 草稿CRUD与重试发布"
```

---

## Task 9: workflow.py 路由 - 6 个草稿端点

**Files:**
- Modify: `apps/automation-service/app/api/v1/routes/workflow.py`

`workflow.py` 中已有 `router = APIRouter(prefix="/workflow")`。在文件末尾追加 6 个草稿路由。

- [ ] **Step 1: 追加 6 个草稿路由**

```python
# ==================== 商品草稿箱 ====================

from app.services.workflow_draft_service import (
    list_drafts, get_draft, retry_publish_draft,
    batch_retry_publish_drafts, delete_draft, get_draft_stats
)


@router.get("/drafts", response_model=ResultObject)
async def list_workflow_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("all"),
    workflow_id: int = Query(None),
    keyword: str = Query(""),
    start_date: str = Query(None),
    end_date: str = Query(None),
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """分页查询草稿列表"""
    result = await list_drafts(db, tenant_id, page, page_size, status, workflow_id,
                                keyword or None, start_date, end_date)
    return ResultObject(code=0, msg="ok", data=result)


@router.get("/drafts/stats", response_model=ResultObject)
async def get_draft_stats_endpoint(
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """草稿统计"""
    stats = await get_draft_stats(db, tenant_id)
    return ResultObject(code=0, msg="ok", data=stats)


@router.get("/drafts/{draft_id}", response_model=ResultObject)
async def get_workflow_draft(
    draft_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """获取草稿详情"""
    result = await get_draft(db, draft_id, tenant_id)
    if result is None:
        return ResultObject(code=404, msg="草稿不存在", data=None)
    return ResultObject(code=0, msg="ok", data=result)


@router.post("/drafts/{draft_id}/retry-publish", response_model=ResultObject)
async def retry_publish_draft_endpoint(
    draft_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """重试发布单个草稿"""
    try:
        result = await retry_publish_draft(db, draft_id, tenant_id)
        return ResultObject(code=0, msg="ok", data=result)
    except ValueError as e:
        return ResultObject(code=400, msg=str(e), data=None)


@router.post("/drafts/batch-retry-publish", response_model=ResultObject)
async def batch_retry_publish_drafts_endpoint(
    body: dict = Body(...),
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """批量重试发布"""
    ids = body.get("ids") or []
    if not ids:
        return ResultObject(code=400, msg="ids 不能为空", data=None)
    result = await batch_retry_publish_drafts(db, ids, tenant_id)
    return ResultObject(code=0, msg="ok", data=result)


@router.delete("/drafts/{draft_id}", response_model=ResultObject)
async def delete_workflow_draft_endpoint(
    draft_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """删除草稿（软删除）"""
    ok = await delete_draft(db, draft_id, tenant_id)
    if not ok:
        return ResultObject(code=404, msg="草稿不存在", data=None)
    return ResultObject(code=0, msg="ok", data={"deleted": True})
```

注意：`get_tenant_id`、`get_db`、`ResultObject` 在 workflow.py 中已存在，直接复用。

- [ ] **Step 2: 重启 automation-service 并验证路由注册**

Run: 重启 automation-service 后访问 `/automation/api/v1/workflow/drafts/stats`
Expected: 返回 `{"code":0,"msg":"ok","data":{"total":0,"draft":0,"published":0,"failed":0}}`

- [ ] **Step 3: Commit**

```bash
git add apps/automation-service/app/api/v1/routes/workflow.py
git commit -m "feat(automation-service): workflow 路由 - 商品草稿箱 6 个端点"
```

---

## Task 10: Java AutomationProxyController 6 个草稿端点

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java`

参考现有 `/opportunity/history` 透传模式（第 533 行），追加 6 个草稿端点。

- [ ] **Step 1: 追加 6 个端点**

```java
// ==================== 工作流商品草稿箱 ====================

@GetMapping("/workflow/drafts")
public Result<Object> listWorkflowDrafts(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "20") int pageSize,
        @RequestParam(defaultValue = "all") String status,
        @RequestParam(required = false) Long workflowId,
        @RequestParam(required = false, defaultValue = "") String keyword,
        @RequestParam(required = false) String startDate,
        @RequestParam(required = false) String endDate) {
    Map<String, Object> params = new LinkedHashMap<>();
    params.put("page", page);
    params.put("page_size", pageSize);
    params.put("status", status);
    if (workflowId != null) params.put("workflow_id", workflowId);
    params.put("keyword", keyword == null ? "" : keyword);
    if (startDate != null) params.put("start_date", startDate);
    if (endDate != null) params.put("end_date", endDate);
    try {
        return Result.ok(automationClient.getInternalForData("/api/workflow/drafts", params));
    } catch (Exception ex) {
        log.error("查询草稿列表失败, errorType={}", ex.getClass().getSimpleName());
        throw new BizException(503, "草稿列表暂时无法查询，请稍后重试");
    }
}

@GetMapping("/workflow/drafts/stats")
public Result<Object> getWorkflowDraftStats() {
    try {
        return Result.ok(automationClient.getInternalForData("/api/workflow/drafts/stats"));
    } catch (Exception ex) {
        log.error("查询草稿统计失败, errorType={}", ex.getClass().getSimpleName());
        throw new BizException(503, "草稿统计暂时无法查询，请稍后重试");
    }
}

@GetMapping("/workflow/drafts/{draftId}")
public Result<Object> getWorkflowDraft(@PathVariable("draftId") Long draftId) {
    try {
        return Result.ok(automationClient.getInternalForData("/api/workflow/drafts/" + draftId));
    } catch (BizException e) {
        throw e;
    } catch (Exception ex) {
        log.error("查询草稿详情失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
        throw new BizException(503, "草稿详情暂时无法查询，请稍后重试");
    }
}

@PostMapping("/workflow/drafts/{draftId}/retry-publish")
public Result<Object> retryPublishDraft(@PathVariable("draftId") Long draftId) {
    try {
        return Result.ok(automationClient.postInternalForData("/api/workflow/drafts/" + draftId + "/retry-publish", new java.util.LinkedHashMap<>()));
    } catch (BizException e) {
        throw e;
    } catch (Exception ex) {
        log.error("重试发布失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
        throw new BizException(503, "重试发布暂时无法执行，请稍后重试");
    }
}

@PostMapping("/workflow/drafts/batch-retry-publish")
public Result<Object> batchRetryPublishDrafts(@RequestBody Map<String, Object> body) {
    try {
        return Result.ok(automationClient.postInternalForData("/api/workflow/drafts/batch-retry-publish", body));
    } catch (BizException e) {
        throw e;
    } catch (Exception ex) {
        log.error("批量重试发布失败, errorType={}", ex.getClass().getSimpleName());
        throw new BizException(503, "批量重试发布暂时无法执行，请稍后重试");
    }
}

@DeleteMapping("/workflow/drafts/{draftId}")
public Result<Object> deleteWorkflowDraft(@PathVariable("draftId") Long draftId) {
    try {
        return Result.ok(automationClient.deleteInternalForData("/api/workflow/drafts/" + draftId));
    } catch (BizException e) {
        throw e;
    } catch (Exception ex) {
        log.error("删除草稿失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
        throw new BizException(503, "草稿暂时无法删除，请稍后重试");
    }
}
```

如果 `AutomationClient` 没有 `deleteInternalForData` 方法，则改用现有方式（查 `AutomationClient` 已有方法，可能名为 `deleteInternal` 或需要新增）。如未提供，可改为：

```java
@DeleteMapping("/workflow/drafts/{draftId}")
public Result<Object> deleteWorkflowDraft(@PathVariable("draftId") Long draftId) {
    try {
        return Result.ok(automationClient.exchangeInternalForData(
            org.springframework.http.HttpMethod.DELETE,
            "/api/workflow/drafts/" + draftId, null));
    } catch (BizException e) {
        throw e;
    } catch (Exception ex) {
        log.error("删除草稿失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
        throw new BizException(503, "草稿暂时无法删除，请稍后重试");
    }
}
```

实施前先查 AutomationClient 现有方法签名（Grep `public.*Internal.*Data`）确定正确的调用方式。

- [ ] **Step 2: 编译验证**

Run: `cd apps/core-api && mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java
git commit -m "feat(core-api): AutomationProxyController 6 个工作流草稿端点"
```

---

## Task 11: automation_runtime.py IMAGE_GENERATE 节点传 source

**Files:**
- Modify: `apps/automation-service/app/services/automation_runtime.py`

定位 IMAGE_GENERATE 节点调用 Java `/opportunity/generate-images` 的位置（约第 8105-8304 行附近）。

- [ ] **Step 1: 搜索调用点**

Run: `Grep "opportunity/generate-images|/opportunity/generate-images" apps/automation-service/app/services/automation_runtime.py`

找到调用 Java 生图 API 的代码位置。

- [ ] **Step 2: 在请求体追加 source 字段**

在调用 Java `/opportunity/generate-images` 的请求体中追加：

```python
# 工作流调用生图时，标记来源为 workflow
payload["source"] = "workflow"
payload["workflowId"] = workflow_id
payload["workflowExecutionId"] = execution_id
payload["workflowNodeKey"] = node.get("node_key", "IMAGE_GENERATE")
```

具体变量名以现有代码上下文为准（搜索 `workflow_id`/`execution_id`/`node` 的局部变量名）。

- [ ] **Step 3: 单元测试（如已有 automation_runtime 测试则扩展，否则跳过）**

如项目已有 `tests/test_automation_runtime_*.py`，增加一个验证 source 字段的测试；否则手动验证：执行包含 IMAGE_GENERATE 节点的工作流后，查询 `opportunity_image_history` 表中 source=workflow 的记录。

- [ ] **Step 4: Commit**

```bash
git add apps/automation-service/app/services/automation_runtime.py
git commit -m "feat(automation-service): IMAGE_GENERATE 节点调用生图传 source=workflow"
```

---

## Task 12: automation_runtime.py PUBLISH 节点改造

**Files:**
- Modify: `apps/automation-service/app/services/automation_runtime.py`

PUBLISH 节点位于第 9407 行起。当前逻辑：
1. 优先走「汇总模式」（state 已有 publish_results）
2. 否则走「批量发布模式」

本任务在「批量发布模式」中，**每次发布前先创建草稿记录，发布结果回写到草稿**。「汇总模式」无需改造（草稿已在 IMAGE_GENERATE 内联发布时创建）。

如果 IMAGE_GENERATE 节点也内联发布（第 8674 行 `publish_results.append(pub_result)`），同样需要在该处创建草稿。

- [ ] **Step 1: 在文件顶部导入 WorkflowGoodsDraft 与服务**

```python
from app.models.entities import WorkflowGoodsDraft
from app.services.workflow_draft_service import create_draft_from_publish
```

`create_draft_from_publish` 是新增的辅助函数，在 Task 8 之外的扩展点。在 `workflow_draft_service.py` 中追加：

```python
async def create_draft_from_publish(
    session: AsyncSession,
    tenant_id: int,
    user_id: int,
    workflow_id: int,
    execution_id: int,
    workflow_name: str,
    node_key: str,
    account_id: int,
    product: Dict[str, Any],
    image_urls: List[str],
    cover_pic: str,
    category: str,
    address: Dict[str, Any],
    publish_status: str,
    xianyu_goods_id: str = "",
    error_message: str = "",
    source_item_id: str = "",
    source_title_hash: str = "",
) -> int:
    """从发布流程创建草稿记录，返回 draft_id"""
    draft = WorkflowGoodsDraft(
        tenant_id=tenant_id,
        user_id=user_id,
        workflow_id=workflow_id,
        workflow_execution_id=execution_id,
        workflow_name=workflow_name,
        node_key=node_key,
        account_id=account_id,
        title=product.get("title", "")[:500],
        price=str(product.get("price", ""))[:50],
        description=product.get("description", ""),
        cover_pic=cover_pic,
        image_urls=image_urls,
        category=category,
        stock=product.get("stock", 1),
        location=address,
        raw_payload=product,
        source_item_id=source_item_id,
        source_title_hash=source_title_hash,
        publish_status=publish_status,
        publish_time=datetime.utcnow() if publish_status in ("published", "failed", "publishing") else None,
        xianyu_goods_id=xianyu_goods_id,
        publish_error_message=error_message,
        publish_attempt_count=1 if publish_status != "draft" else 0,
    )
    session.add(draft)
    await session.flush()
    return draft.id
```

- [ ] **Step 2: 在 PUBLISH 节点（批量发布分支）每个商品发布时插入草稿**

在 `automation_runtime.py` 第 9670-9820 行附近，每个 `publish_results.append({...})` 调用前后追加草稿创建逻辑：

```python
# 在「未生成 AI 封面图」分支，append 后追加：
try:
    await create_draft_from_publish(
        db, tenant_id, _pub_user_id, _wf_id, _exec_id, _wf_name,
        node.get("node_key", "PUBLISH"), acct_id, p, [], img_url,
        category, address, "failed", "", "未生成 AI 封面图，已阻止发布",
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_no_ai_image", _draft_err)

# 在「价格无效」分支，append 后追加：
try:
    await create_draft_from_publish(
        db, tenant_id, _pub_user_id, _wf_id, _exec_id, _wf_name,
        node.get("node_key", "PUBLISH"), acct_id, p, [], img_url,
        category, address, "failed", "", "商品价格无效，已阻止发布",
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_invalid_price", _draft_err)

# 在「重复跳过」分支，append 后追加：
try:
    await create_draft_from_publish(
        db, tenant_id, _pub_user_id, _wf_id, _exec_id, _wf_name,
        node.get("node_key", "PUBLISH"), acct_id, p, image_urls, img_url,
        category, address, "failed", "", "该商品已发布过，已跳过重复发布",
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_duplicate", _draft_err)

# 在「发布成功」分支，append 后追加：
try:
    await create_draft_from_publish(
        db, tenant_id, _pub_user_id, _wf_id, _exec_id, _wf_name,
        node.get("node_key", "PUBLISH"), acct_id, p, image_urls, img_url,
        category, address, "published", goods_id, "",
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_published", _draft_err)

# 在「发布失败 except」分支，append 后追加：
try:
    await create_draft_from_publish(
        db, tenant_id, _pub_user_id, _wf_id, _exec_id, _wf_name,
        node.get("node_key", "PUBLISH"), acct_id, p, image_urls, img_url,
        category, address, "failed", "", str(e)[:2000],
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_failed", _draft_err)
```

具体变量名（`_wf_id`/`_exec_id`/`_wf_name`/`_pub_user_id`）以现有代码上下文为准，从 `context` 字典或局部变量获取。实施前先在文件中搜索 `context.get("__workflow_id__")` 等获取上下文变量的写法。

- [ ] **Step 3: 在 IMAGE_GENERATE 内联发布分支也追加草稿创建（第 8674 行附近）**

如果 IMAGE_GENERATE 节点会内联发布（即把发布结果追加到 publish_results），同样需要在该处创建草稿。搜索 `publish_results.append(pub_result)`，在每次 append 后追加：

```python
try:
    await create_draft_from_publish(
        db, tenant_id, user_id, workflow_id, execution_id, workflow_name,
        "IMAGE_GENERATE", acct_id, p, image_urls, img_url,
        category, address, pub_result.get("status", "failed"),
        pub_result.get("goods_id", ""), pub_result.get("error", ""),
        source_item_id, source_title_hash,
    )
    await db.commit()
except Exception as _draft_err:
    _log_runtime_failure("create_draft_inline_publish", _draft_err)
```

- [ ] **Step 4: 手动验证**

执行包含 PUBLISH 节点的工作流后：
1. 检查 `workflow_goods_draft` 表中是否有相应记录
2. 验证发布成功记录 status=published，发布失败记录 status=failed
3. 在草稿箱页面查看是否能展示这些记录

- [ ] **Step 5: Commit**

```bash
git add apps/automation-service/app/services/automation_runtime.py apps/automation-service/app/services/workflow_draft_service.py
git commit -m "feat(automation-service): PUBLISH 节点先存草稿，无论成功失败都保留"
```

---

## Task 13: 更新 migrations-manifest.json

**Files:**
- Modify: `db/migrations-manifest.json`

- [ ] **Step 1: 在 core_mysql.migrations 数组末尾追加 V1.25**

```json
{
  "version": "1.25",
  "description": "add source/workflow_id/workflow_execution_id/workflow_node_key to opportunity_image_history",
  "path": "apps/core-api/src/main/resources/db/migration/V1.25__add_opportunity_image_history_source.sql",
  "sha256": "<Task 1 Step 2 输出的 sha256>",
  "risk": "expand",
  "rollback": "restore"
}
```

- [ ] **Step 2: 在 automation_mysql.migrations 数组末尾追加 V1.12**

```json
{
  "version": "1.12",
  "description": "workflow goods draft table for publish-before-save flow",
  "path": "apps/automation-service/migrations/V1.12__create_workflow_goods_draft.sql",
  "sha256": "<Task 6 Step 2 输出的 sha256>",
  "risk": "expand",
  "rollback": "restore"
}
```

- [ ] **Step 3: 校验清单完整性**

Run: `python scripts/validate_migrations.py`（或项目既有的清单校验命令）
Expected: 通过校验，无报错

- [ ] **Step 4: Commit**

```bash
git add db/migrations-manifest.json
git commit -m "chore(db): 迁移清单追加 V1.25 (core) + V1.12 (automation)"
```

---

## Task 14: 前端 nav.js 注册两个 nav 项

**Files:**
- Modify: `apps/user-web/src/data/nav.js`

- [ ] **Step 1: 在「自动化」分组中追加两个 nav 项**

在 `navGroups` 第 18 行 `'workflow-tasks'` 之后追加：

```javascript
{ key: 'workflow-drafts', label: '商品草稿箱', icon: 'document', child: true },
{ key: 'workflow-image-records', label: '图片生成记录', icon: 'image', child: true },
```

- [ ] **Step 2: 在 pageTitles 中追加两个页面标题**

```javascript
'workflow-drafts': ['商品草稿箱', '工作流生成的商品草稿与发布记录'],
'workflow-image-records': ['图片生成记录', '所有生图模型调用产生的图片历史'],
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-web/src/data/nav.js
git commit -m "feat(user-web): nav 追加商品草稿箱与图片生成记录子项"
```

---

## Task 15: 前端 App.vue 注册两个页面路由

**Files:**
- Modify: `apps/user-web/src/App.vue`

- [ ] **Step 1: 在 pageMap 中追加两个页面注册**

在第 133 行 `'workflow-tasks'` 之后追加：

```javascript
'workflow-drafts': asyncPage(() => import('./pages/WorkflowDraftsPage.vue')),
'workflow-image-records': asyncPage(() => import('./pages/WorkflowImageRecordsPage.vue')),
```

- [ ] **Step 2: Commit**

```bash
git add apps/user-web/src/App.vue
git commit -m "feat(user-web): App.vue 注册商品草稿箱与图片生成记录页面"
```

---

## Task 16: 前端 api/workflowDrafts.js

**Files:**
- Create: `apps/user-web/src/api/workflowDrafts.js`

- [ ] **Step 1: 创建 API 文件**

```javascript
import request from '../utils/request.js'

export const listWorkflowDrafts = params =>
  request.get('/workflow/drafts', { params: params || {} })

export const getWorkflowDraft = id =>
  request.get(`/workflow/drafts/${id}`)

export const retryPublishDraft = id =>
  request.post(`/workflow/drafts/${id}/retry-publish`)

export const batchRetryPublishDrafts = ids =>
  request.post('/workflow/drafts/batch-retry-publish', { ids: ids || [] })

export const deleteWorkflowDraft = id =>
  request.delete(`/workflow/drafts/${id}`)

export const getWorkflowDraftStats = () =>
  request.get('/workflow/drafts/stats')
```

注意：与现有 `apps/user-web/src/api/opportunity.js` 一致使用 `request from '../utils/request.js'`，而非 spec 中说的 `request from './index.js'`。

- [ ] **Step 2: Commit**

```bash
git add apps/user-web/src/api/workflowDrafts.js
git commit -m "feat(user-web): workflowDrafts API 文件"
```

---

## Task 17: 验证 api/opportunity.js 已有 listImageRecords

**Files:**
- Verify: `apps/user-web/src/api/opportunity.js`

- [ ] **Step 1: 确认 listImageRecords 已存在且正确**

Read `apps/user-web/src/api/opportunity.js`，确认第 35-37 行已有：

```javascript
export const listImageRecords = params => request.get('/opportunity/image-history', {
  params: { source: 'all', ...(params || {}) }
})
```

若不存在或不正确，按上述代码补全。

- [ ] **Step 2: Commit（如有修改）**

```bash
git add apps/user-web/src/api/opportunity.js
git commit -m "fix(user-web): listImageRecords 复用 image-history 端点（如有修改）"
```

---

## Task 18: WorkflowDraftsPage.vue 商品草稿箱页面

**Files:**
- Create: `apps/user-web/src/pages/WorkflowDraftsPage.vue`

布局参考 `WorkflowTasksPage.vue` 与 `OpportunityPage.vue` 的商品卡片网格。

- [ ] **Step 1: 创建页面（结构骨架）**

由于 Vue 文件较大，先创建结构骨架，包含：
- `<script setup>`：API 调用、状态管理
- `<template>`：4 个 StatCard + 筛选区 + 卡片网格 + 详情抽屉 + 批量操作栏
- `<style scoped>`：网格布局、卡片样式

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import { listWorkflowDrafts, getWorkflowDraftStats, retryPublishDraft,
         batchRetryPublishDrafts, deleteWorkflowDraft } from '../api/workflowDrafts.js'

const loading = ref(false)
const loadError = ref('')
const records = ref([])
const stats = ref({ total: 0, draft: 0, published: 0, failed: 0 })
const filters = ref({ status: 'all', workflowId: null, keyword: '', page: 1, pageSize: 20 })
const total = ref(0)
const selectedIds = ref(new Set())
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)
const retrying = ref(false)

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'draft', label: '待发布' },
  { value: 'publishing', label: '发布中' },
  { value: 'published', label: '已发布' },
  { value: 'failed', label: '发布失败' }
]

const statusBadgeType = (status) => {
  switch (status) {
    case 'draft': return 'blue'
    case 'publishing': return 'blue'
    case 'published': return 'green'
    case 'failed': return 'red'
    default: return 'gray'
  }
}

const statusBadgeLabel = (status) => {
  return statusOptions.find(o => o.value === status)?.label || status
}

async function loadList() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await listWorkflowDrafts(filters.value)
    records.value = data.records || []
    total.value = data.total || 0
  } catch (e) {
    loadError.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getWorkflowDraftStats()
  } catch (e) {
    // 静默失败
  }
}

async function refresh() {
  await Promise.all([loadList(), loadStats()])
}

async function handleRetry(draftId) {
  retrying.value = true
  try {
    await retryPublishDraft(draftId)
    await refresh()
  } catch (e) {
    alert(e.message || '重试失败')
  } finally {
    retrying.value = false
  }
}

async function handleBatchRetry() {
  if (selectedIds.value.size === 0) return
  retrying.value = true
  try {
    await batchRetryPublishDrafts(Array.from(selectedIds.value))
    selectedIds.value.clear()
    await refresh()
  } catch (e) {
    alert(e.message || '批量重试失败')
  } finally {
    retrying.value = false
  }
}

async function handleDelete(draftId) {
  if (!confirm('确定要删除该草稿吗？')) return
  try {
    await deleteWorkflowDraft(draftId)
    await refresh()
  } catch (e) {
    alert(e.message || '删除失败')
  }
}

function toggleSelect(id) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

function handlePageChange(page) {
  filters.value.page = page
  loadList()
}

onMounted(() => {
  refresh()
})
</script>

<template>
  <div class="workflow-drafts-page">
    <PageHeader title="商品草稿箱" subtitle="工作流生成的商品草稿与发布记录" />

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <StatCard label="草稿总数" :value="stats.total" icon="document" color="blue" />
      <StatCard label="待发布" :value="stats.draft" icon="clock" color="blue" />
      <StatCard label="已发布" :value="stats.published" icon="check" color="green" />
      <StatCard label="发布失败" :value="stats.failed" icon="warn" color="red" />
    </div>

    <CardPanel>
      <!-- 筛选区 -->
      <div class="filter-bar">
        <select v-model="filters.status" class="aics-input" @change="loadList">
          <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <input v-model="filters.keyword" class="aics-input" placeholder="搜索标题/描述"
               @keyup.enter="loadList" />
        <AppButton type="primary" @click="loadList">搜索</AppButton>
        <AppButton @click="refresh">刷新</AppButton>
        <div class="spacer"></div>
        <AppButton v-if="selectedIds.size > 0" type="primary" :loading="retrying"
                   @click="handleBatchRetry">
          批量重试发布 ({{ selectedIds.size }})
        </AppButton>
      </div>

      <!-- 三态分支 -->
      <div v-if="loading" class="loading-state">加载中...</div>
      <div v-else-if="loadError" class="error-state">
        {{ loadError }}
        <AppButton @click="loadList">重新加载</AppButton>
      </div>
      <EmptyState v-else-if="records.length === 0" title="暂无草稿" subtitle="运行包含发布节点的工作流后，商品会自动保存到此处" />
      <div v-else class="drafts-grid">
        <div v-for="rec in records" :key="rec.id" class="draft-card"
             :class="{ selected: selectedIds.has(rec.id) }">
          <div class="card-checkbox">
            <input type="checkbox" :checked="selectedIds.has(rec.id)" @change="toggleSelect(rec.id)" />
          </div>
          <div class="card-cover">
            <img v-if="rec.cover_pic" :src="rec.cover_pic" :alt="rec.title" />
            <div v-else class="cover-placeholder"><Icon name="image" /></div>
          </div>
          <div class="card-info">
            <div class="card-title" :title="rec.title">{{ rec.title }}</div>
            <div class="card-price">¥{{ rec.price }}</div>
            <Badge :type="statusBadgeType(rec.publish_status)">
              {{ statusBadgeLabel(rec.publish_status) }}
            </Badge>
            <div class="card-meta">
              <span v-if="rec.workflow_name">来自：{{ rec.workflow_name }}</span>
              <span v-if="rec.xianyu_goods_id">闲鱼ID：{{ rec.xianyu_goods_id }}</span>
              <span v-if="rec.publish_error_message" class="error-text" :title="rec.publish_error_message">
                失败：{{ rec.publish_error_message.substring(0, 30) }}{{ rec.publish_error_message.length > 30 ? '...' : '' }}
              </span>
            </div>
            <div class="card-time">{{ rec.created_time }}</div>
          </div>
          <div class="card-actions">
            <AppButton v-if="rec.publish_status === 'failed' || rec.publish_status === 'draft'"
                       size="small" type="primary" :loading="retrying"
                       @click="handleRetry(rec.id)">重试发布</AppButton>
            <AppButton v-if="rec.publish_status === 'published'"
                       size="small" @click="detailVisible = true; detailData = rec">查看详情</AppButton>
            <AppButton size="small" @click="handleDelete(rec.id)">删除</AppButton>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > filters.pageSize" class="pagination">
        <button :disabled="filters.page <= 1" @click="handlePageChange(filters.page - 1)">上一页</button>
        <span>第 {{ filters.page }} 页 / 共 {{ Math.ceil(total / filters.pageSize) }} 页</span>
        <button :disabled="filters.page * filters.pageSize >= total" @click="handlePageChange(filters.page + 1)">下一页</button>
      </div>
    </CardPanel>
  </div>
</template>

<style scoped>
.workflow-drafts-page { padding: 20px; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-bar .spacer { flex: 1; }
.filter-bar .aics-input { width: auto; min-width: 180px; }
.drafts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.draft-card {
  border: 1px solid rgba(231, 237, 247, 0.95);
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
  position: relative;
  transition: box-shadow .2s, transform .2s;
}
.draft-card:hover { box-shadow: 0 18px 42px rgba(31, 53, 94, 0.08); transform: translateY(-2px); }
.draft-card.selected { border-color: #0d6bff; box-shadow: 0 0 0 2px rgba(13, 107, 255, .2); }
.card-checkbox { position: absolute; top: 8px; left: 8px; z-index: 1; }
.card-cover { width: 100%; aspect-ratio: 4/3; background: #f5f7fa; overflow: hidden; }
.card-cover img { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; color: #c0c4cc; }
.card-info { padding: 12px; }
.card-title { font-size: 14px; font-weight: 600; color: #13213d; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-price { font-size: 18px; color: #ef4444; font-weight: 600; margin-bottom: 8px; }
.card-meta { font-size: 12px; color: #8b97aa; margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.card-meta .error-text { color: #ef4444; }
.card-time { font-size: 12px; color: #c0c4cc; margin-top: 4px; }
.card-actions { display: flex; gap: 8px; padding: 0 12px 12px; flex-wrap: wrap; }
.loading-state, .error-state { padding: 40px; text-align: center; color: #5a6880; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; padding: 20px 0; }
.pagination button { padding: 6px 12px; border: 1px solid #dcdfe6; background: #fff; border-radius: 4px; cursor: pointer; }
.pagination button:disabled { opacity: .5; cursor: not-allowed; }
</style>
```

- [ ] **Step 2: 启动 user-web dev server 验证页面渲染**

Run: `cd apps/user-web && npm run dev`
访问 `http://localhost:5173/#/workflow-drafts`
Expected: 页面正常渲染，无控制台错误（即使后端未联调，统计为 0 也应正常显示）

- [ ] **Step 3: Commit**

```bash
git add apps/user-web/src/pages/WorkflowDraftsPage.vue
git commit -m "feat(user-web): WorkflowDraftsPage 商品草稿箱页面"
```

---

## Task 19: 验证 WorkflowImageRecordsPage.vue 字段对接

**Files:**
- Verify: `apps/user-web/src/pages/WorkflowImageRecordsPage.vue`

文件已存在（前序会话已创建）。需对照 Task 4 的 `listHistoryPaged` 返回字段做最后调整。

- [ ] **Step 1: 阅读现有 Vue 文件，确认 API 调用与字段映射**

Read `apps/user-web/src/pages/WorkflowImageRecordsPage.vue`，确认：
- 调用 `listImageRecords({ source, status, keyword, page, pageSize })` 与 Task 4 接口字段一致
- 返回结构 `{ records, total, page, pageSize }` 与 Vue 模板渲染字段一致
- 字段映射：`record.model`、`record.prompt`、`record.status`、`record.created_time`、`record.result_images`、`record.source`、`record.workflow_id`

- [ ] **Step 2: 如有字段不匹配，做最小调整**

实施时若发现字段命名不一致（如 `record.imageUrl` 应为 `record.result_images`），用 Edit 工具做最小化修正。

- [ ] **Step 3: 启动 user-web dev server 验证页面渲染**

Run: `cd apps/user-web && npm run dev`
访问 `http://localhost:5173/#/workflow-image-records`
Expected: 页面正常渲染

- [ ] **Step 4: Commit（如有修改）**

```bash
git add apps/user-web/src/pages/WorkflowImageRecordsPage.vue
git commit -m "fix(user-web): WorkflowImageRecordsPage 字段对接 listHistoryPaged（如有修改）"
```

---

## Task 20: 端到端联调 + 更新日志

**Files:**
- Modify: `apps/user-web/src/data/releaseNotes.js`
- Modify: `apps/user-web/package.json`

- [ ] **Step 1: 端到端联调**

启动 core-api、automation-service、user-web dev server，验证：
1. 访问 `http://localhost:5173/#/workflow-drafts`：页面加载，统计与列表为空（无数据时显示 EmptyState）
2. 访问 `http://localhost:5173/#/workflow-image-records`：页面加载，应显示已有商机生图记录（source=opportunity）
3. 执行包含 PUBLISH 节点的工作流：检查草稿箱是否有新记录、检查图片生成记录是否有 source=workflow 的新记录
4. 在草稿箱点击「重试发布」：验证状态从 failed 变为 published（或显示失败错误）

- [ ] **Step 2: 检查 V1.25 迁移已应用**

Run: 在 core-api 启动日志中搜索 `Flyway` 或 `Migrating schema`
Expected: 看到 V1.25 迁移成功

- [ ] **Step 3: 检查 workflow_goods_draft 表已创建**

执行 SQL：`SHOW TABLES LIKE 'workflow_goods_draft'`
Expected: 返回 1 行

- [ ] **Step 4: 同步 releaseNotes.js 与 package.json 版本**

按 `.trae/rules/release-notes-workflow.md` 规则：
- 本次为「新增功能」，type 为 `minor`，次版本号 +1
- 在 `releaseNotes.js` 数组最前面追加新条目
- 同步更新 `package.json` 的 `version` 字段
- 同步更新 `releaseNotes.js` 的 `CURRENT_VERSION` 常量

```javascript
// releaseNotes.js 追加示例
{
  version: '<新版本号>',  // 如 1.x.0
  date: '2026-07-19',
  type: 'minor',
  title: '工作流商品草稿箱与图片生成记录',
  summary: '新增商品草稿箱与图片生成记录两个工作流子页面，发布节点改造为先存草稿再发布',
  changes: [
    { label: '新增', items: [
      '商品草稿箱子页面：展示工作流生成的商品草稿，支持重试发布与批量操作',
      '图片生成记录子页面：聚合展示商机发掘与工作流的生图历史，支持来源筛选',
      '发布节点改造：商品在发布前先存入草稿箱，无论发布成功或失败都保留草稿记录'
    ]},
    { label: '优化', items: [
      '生图历史支持按来源（商机/工作流）筛选与分页查询'
    ]}
  ]
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/data/releaseNotes.js apps/user-web/package.json
git commit -m "chore(release): bump user-web to <新版本号> - 工作流草稿箱与图片记录"
```

---

## Self-Review

### 1. Spec coverage

| Spec 章节 | 覆盖任务 |
|----------|---------|
| 一、背景与目标 | 计划开篇 Goal/Architecture 涵盖 |
| 二、整体架构 | Task 1-19 涵盖所有模块 |
| 三、数据模型（workflow_goods_draft） | Task 6 (迁移) + Task 7 (ORM) |
| 三、数据模型（opportunity_image_history 扩展） | Task 1 (迁移) + Task 2 (兜底) |
| 四、API 设计（草稿箱） | Task 8 (Python 服务) + Task 9 (Python 路由) + Task 10 (Java 网关) |
| 四、API 设计（图片记录复用） | Task 3 + Task 4 + Task 5 |
| 五、PUBLISH 节点改造 | Task 12 |
| 五、IMAGE_GENERATE 节点 source 传参 | Task 11 |
| 六、前端页面（导航 + 路由） | Task 14 + Task 15 |
| 六、前端页面（草稿箱页面） | Task 18 |
| 六、前端页面（图片记录页面） | Task 19 (验证已存在) |
| 六、前端 API 文件 | Task 16 + Task 17 |
| 七、数据库迁移策略 | Task 1 + Task 6 + Task 13 |
| 八、分阶段实施 | 计划整体按阶段顺序排列 |
| 十、约束（img_ai_ok 校验） | Task 12 在 PUBLISH 改造中保持现有约束 |
| 十一、验收标准 | Task 20 端到端联调 |
| release-notes-workflow.md | Task 20 Step 4 |

无遗漏。

### 2. Placeholder scan

- 所有 Step 均含具体代码或具体命令
- 无 "TBD"、"TODO"、"fill in details" 等占位符
- sha256 在 Task 1/Task 6 中以「<Task X Step Y 输出>」标记，由实施时计算填入（这是合理的，无法在计划阶段预先知道）
- Task 11/12 中提到的「以现有代码上下文为准」是必要的灵活点（变量名取决于实际代码位置），已给出搜索方法

### 3. Type consistency

- `WorkflowGoodsDraft.publish_status` 取值：`draft` / `publishing` / `published` / `failed` — 在 Task 6 (DDL DEFAULT 'draft')、Task 7 (ORM default='draft')、Task 8 (Service 查询条件)、Task 9 (路由 status 参数)、Task 12 (PUBLISH 创建草稿)、Task 18 (Vue 状态徽章) 中一致
- `opportunity_image_history.source` 取值：`opportunity` / `workflow` — 在 Task 1 (DDL DEFAULT 'opportunity')、Task 2 (兜底)、Task 3 (Service 默认 'opportunity')、Task 4 (listHistory 过滤)、Task 5 (Controller 参数)、Task 11 (IMAGE_GENERATE 传 'workflow')、Task 17 (Vue 调用 'all'/'workflow'/'opportunity') 中一致
- `listHistoryPaged` 返回结构 `{ records, total, page, pageSize }` — Task 4 (Service)、Task 5 (Controller)、Task 17 (Vue API)、Task 19 (Vue 模板) 中一致
- 草稿 API 路径 `/workflow/drafts` — Task 9 (Python 路由)、Task 10 (Java 网关)、Task 16 (前端 API)、Task 18 (Vue 调用) 中一致
- `retry_publish_draft` 抛出 `ValueError` 表达业务错误（"正在发布中"/"已发布成功"）— Task 8 (Service)、Task 9 (路由捕获并返回 code=400)、Task 8 测试中一致
- migration 版本号修正：spec 中 `V1.10__create_workflow_goods_draft.sql` 在本计划中修正为 `V1.12__create_workflow_goods_draft.sql`（当前 automation-service 最新版本为 V1.11），core-api 保持 V1.25 — 在计划开篇已说明

### 4. Spec 与现有代码差异点

- spec 3.3 节提到 `workflow_publish_record` 表与本功能互补。实际代码中还有 `workflow_published_goods` 表（用于跨次运行去重，见 automation_runtime.py 第 9729 行）。Task 12 改造时保留 `workflow_published_goods` 的去重逻辑不动，仅追加 `workflow_goods_draft` 草稿创建。
- spec 中 `listImageRecords` 用 `request.get('/opportunity/image-history', { params: { source: 'all', ...params } })`，与现有 `listOpportunityImageHistory` 共用端点，已在前序会话完成（Task 17 仅验证）。
- spec 中「V1.10__create_workflow_goods_draft.sql」修正为 V1.12，已在计划开篇说明。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-19-workflow-drafts-and-image-records.md`. Two execution options:**

1. **Subagent-Driven (recommended)** - 每个 Task 派遣独立子代理实施，主代理审查后进入下一任务，快速迭代
2. **Inline Execution** - 在当前会话按 Task 顺序批量执行，检查点处暂停审查

**Which approach?**
