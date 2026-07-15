# Category Image Prompt Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add category-based image prompt management with default/custom prompt selection, and re-classify every product before image generation in both the workflow runtime and the opportunity image flow.

**Architecture:** Reuse `admin_module_record` as the storage layer for image prompt categories, expose them through existing admin module CRUD, resolve prompts in Java for opportunity generation and in Python for live workflow execution, and keep old workflow configs compatible by mapping legacy `imagePrompt` into the new custom mode.

**Tech Stack:** Spring Boot, JdbcTemplate, FastAPI service helpers, Vue 3, Element Plus, plain Vue form state.

---

### Task 1: Add backend tests for category prompt resolution

**Files:**
- Create: `apps/core-api/src/test/java/com/xianyu/admin/service/ModelConfigServiceTest.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ModelConfigService.java`

- [ ] Add tests covering prompt record loading, keyword/category matching, and fallback behavior.
- [ ] Run the Java test class alone and confirm it fails before implementation.
- [ ] Implement the smallest service helpers needed to make the tests pass.

### Task 2: Add automation runtime tests for per-item re-classification

**Files:**
- Modify: `apps/automation-service/tests/test_automation_runtime_ai_cs.py`
- Modify: `apps/automation-service/app/services/automation_runtime.py`

- [ ] Add tests for workflow-side prompt mode selection and per-product category matching.
- [ ] Run the targeted pytest selection and confirm it fails before implementation.
- [ ] Implement isolated helpers in `automation_runtime.py` for category prompt resolution and template rendering.

### Task 3: Add category prompt config support in core-api

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ModuleCatalog.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/AdminModuleService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ModelConfigService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/ImageGenerationService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/AiProviderService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java`

- [ ] Register a new admin module for image prompt categories.
- [ ] Seed default category prompt records for multiple Xianyu-friendly categories.
- [ ] Add service methods for listing enabled category prompts, matching category per item, and resolving final image prompt source.
- [ ] Update opportunity image generation to support `promptMode` and `customPrompt`.

### Task 4: Wire per-product classification into the workflow runtime

**Files:**
- Modify: `apps/automation-service/app/services/automation_runtime.py`

- [ ] Resolve node prompt mode once per node.
- [ ] Re-classify every product item before its own image generation call.
- [ ] Store prompt source/category metadata into generated image steps for debugging.
- [ ] Preserve legacy fallback behavior when no category prompt matches.

### Task 5: Add frontend/admin management and compatibility

**Files:**
- Modify: `apps/admin-web/src/router/modules/admin.ts`
- Modify: `apps/user-web/src/pages/WorkflowPage.vue`
- Modify: `apps/user-web/src/pages/OpportunityPage.vue`

- [ ] Add admin entry to manage image prompt category records through the generic module page.
- [ ] Add default/custom prompt selection to workflow image nodes.
- [ ] Add default/custom prompt selection to the opportunity image area.
- [ ] Keep old saved workflow nodes working by migrating legacy `imagePrompt` values into the new custom prompt shape at load/save time.

### Task 6: Verify the live chains

**Files:**
- No new files required.

- [ ] Run targeted Java tests.
- [ ] Run targeted Python tests.
- [ ] Run focused frontend builds or lint checks if available.
- [ ] Sanity-check that `润色 -> 生图 -> 发布` and `商机发掘 -> 生图` still serialize the expected fields.
