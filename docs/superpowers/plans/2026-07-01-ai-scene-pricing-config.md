# AI Scene Pricing Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configurable AI scene pricing layer in `core-api` so frontend AI features can estimate and charge based on scene-specific sell rules, plan benefits, and existing model cost data.

**Architecture:** Keep `ai_model_price_config` as the source of truth for model cost, and add a new sell-side layer on top of it. Implement two new configuration tables plus a small pricing service that resolves scene defaults, member benefits, and final sell tokens, then expose a new estimate endpoint without breaking the existing billing flow.

**Tech Stack:** Java 17, Spring Boot 3, `JdbcTemplate`, existing `AiBillingService`, existing `BillingPlanService`, JUnit 5, Mockito.

---

### Task 1: Add failing tests for scene pricing resolution

**Files:**
- Create: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`
- Modify: `apps/core-api/pom.xml`

- [ ] **Step 1: Write the failing test**

```java
package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AiScenePricingServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void fixedPerCallShouldUseVipOverrideReplyPrice() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);

        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        Method applyPlanBenefit = AiScenePricingService.class.getDeclaredMethod(
                "applyPlanBenefit",
                Map.class,
                Map.class,
                long.class,
                long.class
        );
        applyPlanBenefit.setAccessible(true);

        Map<String, Object> scene = new LinkedHashMap<>();
        scene.put("charge_mode", "member_quota_then_fixed");
        scene.put("sell_tokens_per_reply", 8L);
        scene.put("daily_cap_count", 1000);

        Map<String, Object> benefit = new LinkedHashMap<>();
        benefit.put("plan_code", "vip");
        benefit.put("free_quota_daily", 30);
        benefit.put("override_tokens_per_reply", 6L);

        Map<String, Object> resolved = (Map<String, Object>) applyPlanBenefit.invoke(service, scene, benefit, 5L, 1L);

        assertEquals(25L, resolved.get("remainingFreeQuota"));
        assertEquals(6L, resolved.get("effectiveTokensPerReply"));
        assertEquals("member_quota_then_fixed", resolved.get("effectiveChargeMode"));
    }

    @SuppressWarnings("unchecked")
    @Test
    void perItemStepShouldComputeSteppedChargeTokens() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);

        Method computeSellTokens = AiScenePricingService.class.getDeclaredMethod(
                "computeSellTokens",
                Map.class,
                Map.class
        );
        computeSellTokens.setAccessible(true);

        Map<String, Object> scene = new LinkedHashMap<>();
        scene.put("charge_mode", "per_item_step");
        scene.put("base_tokens", 20L);
        scene.put("step_size", 10);
        scene.put("step_tokens", 10L);
        scene.put("min_tokens", 20L);

        Map<String, Object> usage = new LinkedHashMap<>();
        usage.put("itemCount", 23);

        Map<String, Object> result = (Map<String, Object>) computeSellTokens.invoke(service, scene, usage);

        assertEquals(50L, result.get("sellChargeTokens"));
        assertTrue(String.valueOf(result.get("pricingReason")).contains("step"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAILURE
... cannot find symbol: class AiScenePricingService
```

- [ ] **Step 3: Add minimal test dependency support only if needed**

No code change unless the test compile fails for missing JUnit/Mockito support beyond the current `spring-boot-starter-test`.

- [ ] **Step 4: Run test again to confirm the failure is still the missing service**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAILURE
... AiScenePricingService
```

- [ ] **Step 5: Commit**

```bash
git add apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java apps/core-api/pom.xml
git commit -m "test: add failing tests for ai scene pricing service"
```

### Task 2: Add pricing configuration tables to bootstrap schema

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Extend the failing test to assert default field names expected by the service**

```java
    @Test
    void sceneDefaultsShouldExpectSellSideColumns() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("scene_key", "workflow_image");
        row.put("charge_mode", "fixed_per_image");
        row.put("sell_tokens_per_image", 12L);
        row.put("enabled", 1);

        assertEquals("workflow_image", row.get("scene_key"));
        assertEquals("fixed_per_image", row.get("charge_mode"));
        assertEquals(12L, row.get("sell_tokens_per_image"));
    }
```

- [ ] **Step 2: Run test to verify it still fails only because implementation is missing**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAILURE
... AiScenePricingService
```

- [ ] **Step 3: Add table creation and seed scaffolding to `DataInitializer`**

```java
    private void ensureAiScenePricingTables() {
        jdbcTemplate.execute("CREATE TABLE IF NOT EXISTS ai_scene_sell_config (" +
                "id BIGINT PRIMARY KEY AUTO_INCREMENT, " +
                "tenant_id BIGINT NULL, " +
                "scene_key VARCHAR(120) NOT NULL, " +
                "scene_name VARCHAR(120) NOT NULL, " +
                "scene_group VARCHAR(60) DEFAULT 'other', " +
                "charge_mode VARCHAR(60) NOT NULL, " +
                "price_unit VARCHAR(40) DEFAULT 'call', " +
                "enabled TINYINT DEFAULT 1, " +
                "is_metered TINYINT DEFAULT 1, " +
                "show_estimate TINYINT DEFAULT 1, " +
                "allow_trial TINYINT DEFAULT 0, " +
                "trial_quota INT DEFAULT 0, " +
                "base_tokens BIGINT DEFAULT 0, " +
                "step_size INT DEFAULT 0, " +
                "step_tokens BIGINT DEFAULT 0, " +
                "sell_tokens_per_call BIGINT DEFAULT 0, " +
                "sell_tokens_per_item BIGINT DEFAULT 0, " +
                "sell_tokens_per_image BIGINT DEFAULT 0, " +
                "sell_tokens_per_reply BIGINT DEFAULT 0, " +
                "sell_tokens_per_file BIGINT DEFAULT 0, " +
                "sell_tokens_per_1k_chars BIGINT DEFAULT 0, " +
                "min_tokens BIGINT DEFAULT 0, " +
                "max_tokens BIGINT DEFAULT 0, " +
                "member_discount_rate DECIMAL(10,4) DEFAULT 1.0000, " +
                "cost_markup_rate DECIMAL(10,4) DEFAULT 1.0000, " +
                "fallback_exchange_rate DECIMAL(18,8) DEFAULT 160, " +
                "daily_cap_count INT DEFAULT 0, " +
                "daily_cap_tokens BIGINT DEFAULT 0, " +
                "monthly_cap_count INT DEFAULT 0, " +
                "monthly_cap_tokens BIGINT DEFAULT 0, " +
                "sort_order INT DEFAULT 100, " +
                "remark VARCHAR(500), " +
                "created_time DATETIME, updated_time DATETIME, " +
                "deleted TINYINT DEFAULT 0, " +
                "UNIQUE KEY uk_ai_scene_sell_tenant_scene(tenant_id, scene_key, deleted), " +
                "INDEX idx_ai_scene_sell_scene(scene_key, enabled, deleted)" +
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

        jdbcTemplate.execute("CREATE TABLE IF NOT EXISTS ai_scene_plan_benefit (" +
                "id BIGINT PRIMARY KEY AUTO_INCREMENT, " +
                "tenant_id BIGINT NULL, " +
                "scene_key VARCHAR(120) NOT NULL, " +
                "plan_code VARCHAR(80) NOT NULL, " +
                "enabled TINYINT DEFAULT 1, " +
                "free_quota_daily INT DEFAULT 0, " +
                "free_quota_monthly INT DEFAULT 0, " +
                "discount_rate DECIMAL(10,4) DEFAULT 1.0000, " +
                "override_charge_mode VARCHAR(60) NULL, " +
                "override_tokens_per_call BIGINT DEFAULT 0, " +
                "override_tokens_per_item BIGINT DEFAULT 0, " +
                "override_tokens_per_image BIGINT DEFAULT 0, " +
                "override_tokens_per_reply BIGINT DEFAULT 0, " +
                "override_base_tokens BIGINT DEFAULT 0, " +
                "override_step_size INT DEFAULT 0, " +
                "override_step_tokens BIGINT DEFAULT 0, " +
                "daily_cap_count INT DEFAULT 0, " +
                "daily_cap_tokens BIGINT DEFAULT 0, " +
                "remark VARCHAR(500), " +
                "created_time DATETIME, updated_time DATETIME, " +
                "deleted TINYINT DEFAULT 0, " +
                "UNIQUE KEY uk_ai_scene_plan_benefit(tenant_id, scene_key, plan_code, deleted), " +
                "INDEX idx_ai_scene_plan_scene(scene_key, enabled, deleted)" +
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    }
```

- [ ] **Step 4: Wire the new table bootstrap into initializer**

```java
        ensureAiScenePricingTables();
```

---

## Current Implementation Status (2026-07-01)

Completed:
- Added `AiScenePricingService` and verified scene sell-side resolution with focused tests
- Added bootstrap creation for `ai_scene_sell_config` and `ai_scene_plan_benefit`
- Seeded initial scene pricing and plan benefit defaults in `DataInitializer`
- Added `/api/ai-billing/estimate-scene`
- Added admin CRUD + paging for:
  - `/admin-api/ai-scene-sell-config`
  - `/admin-api/ai-scene-plan-benefit`
- Added frontend API wrapper `estimateAiSceneUsage` in `apps/user-web/src/api/aiBilling.js`
- Updated estimate flow so scene pricing resolution receives `alreadyUsedToday`

Verified:
- `apps/core-api/.mvn/bootstrap/apache-maven-3.9.9/bin/mvn.cmd -Dtest=AiBillingServiceTest,AiScenePricingAdminServiceTest test`
- `apps/core-api/.mvn/bootstrap/apache-maven-3.9.9/bin/mvn.cmd -DskipTests compile`

Not fully completed yet:
- Real charge path has not been fully switched to “scene sell price first” across every AI invocation path
- `delivery_source_match` is still a known cost leak because upstream call sites use `billable=false`
- Frontend pages have not yet broadly switched from generic estimate logic to `/api/ai-billing/estimate-scene`

Recommended next step before launch:
1. Finish real charge-path sell-side takeover for scene-priced flows
2. Eliminate `delivery_source_match` free-cost leakage
3. Wire `estimate-scene` into the highest-cost frontend flows first: `auto_reply`, `workflow_image`, `workflow_screen`

Add it immediately after:

```java
        ensureAiBillingTables();
```

- [ ] **Step 5: Run the focused test to keep the suite red on the missing service**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAILURE
... AiScenePricingService
```

- [ ] **Step 6: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java
git commit -m "feat: add ai scene pricing bootstrap tables"
```

### Task 3: Implement the scene pricing service

**Files:**
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/AiScenePricingService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Run the failing test one more time before implementation**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAILURE
... AiScenePricingService
```

- [ ] **Step 2: Implement minimal scene pricing service**

```java
package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AiScenePricingService {
    private final JdbcTemplate jdbcTemplate;

    public AiScenePricingService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Map<String, Object> resolveScenePricing(Long tenantId, String sceneKey, String planCode, Map<String, Object> usage) {
        Map<String, Object> scene = findSceneConfig(tenantId, sceneKey);
        Map<String, Object> benefit = findPlanBenefit(tenantId, sceneKey, normalizePlanCode(planCode));
        Map<String, Object> resolved = applyPlanBenefit(scene, benefit, number(first(usage, "alreadyUsedToday")), number(first(usage, "quantity")));
        Map<String, Object> sell = computeSellTokens(resolved, usage);
        Map<String, Object> result = new LinkedHashMap<>(resolved);
        result.putAll(sell);
        result.put("sceneKey", sceneKey);
        result.put("planCode", normalizePlanCode(planCode));
        return result;
    }

    private Map<String, Object> findSceneConfig(Long tenantId, String sceneKey) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM ai_scene_sell_config WHERE deleted=0 AND enabled=1 AND scene_key=? AND (tenant_id IS NULL OR tenant_id=?) " +
                        "ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                sceneKey, tenantId
        );
        return rows.isEmpty() ? new LinkedHashMap<>() : new LinkedHashMap<>(rows.get(0));
    }

    private Map<String, Object> findPlanBenefit(Long tenantId, String sceneKey, String planCode) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM ai_scene_plan_benefit WHERE deleted=0 AND enabled=1 AND scene_key=? AND plan_code=? AND (tenant_id IS NULL OR tenant_id=?) " +
                        "ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                sceneKey, planCode, tenantId
        );
        return rows.isEmpty() ? new LinkedHashMap<>() : new LinkedHashMap<>(rows.get(0));
    }

    Map<String, Object> applyPlanBenefit(Map<String, Object> scene, Map<String, Object> benefit, long alreadyUsedToday, long quantity) {
        Map<String, Object> resolved = new LinkedHashMap<>(scene);
        String chargeMode = text(scene.get("charge_mode"));
        if (StringUtils.hasText(text(benefit.get("override_charge_mode")))) {
            chargeMode = text(benefit.get("override_charge_mode"));
        }
        resolved.put("effectiveChargeMode", chargeMode);

        long freeDaily = number(benefit.get("free_quota_daily"));
        long remainingFree = Math.max(0L, freeDaily - alreadyUsedToday);
        resolved.put("remainingFreeQuota", remainingFree);

        long replyPrice = number(scene.get("sell_tokens_per_reply"));
        if (number(benefit.get("override_tokens_per_reply")) > 0) {
            replyPrice = number(benefit.get("override_tokens_per_reply"));
        }
        resolved.put("effectiveTokensPerReply", replyPrice);

        long imagePrice = number(scene.get("sell_tokens_per_image"));
        if (number(benefit.get("override_tokens_per_image")) > 0) {
            imagePrice = number(benefit.get("override_tokens_per_image"));
        }
        resolved.put("effectiveTokensPerImage", imagePrice);

        long callPrice = number(scene.get("sell_tokens_per_call"));
        if (number(benefit.get("override_tokens_per_call")) > 0) {
            callPrice = number(benefit.get("override_tokens_per_call"));
        }
        resolved.put("effectiveTokensPerCall", callPrice);

        long baseTokens = number(scene.get("base_tokens"));
        if (number(benefit.get("override_base_tokens")) > 0) {
            baseTokens = number(benefit.get("override_base_tokens"));
        }
        resolved.put("effectiveBaseTokens", baseTokens);

        int stepSize = (int) positiveOrDefault(number(benefit.get("override_step_size")), number(scene.get("step_size")));
        long stepTokens = positiveOrDefault(number(benefit.get("override_step_tokens")), number(scene.get("step_tokens")));
        resolved.put("effectiveStepSize", stepSize);
        resolved.put("effectiveStepTokens", stepTokens);
        return resolved;
    }

    Map<String, Object> computeSellTokens(Map<String, Object> resolved, Map<String, Object> usage) {
        Map<String, Object> result = new LinkedHashMap<>();
        String chargeMode = text(resolved.get("effectiveChargeMode"));
        long sellTokens = 0;
        String pricingReason = chargeMode;

        if ("member_quota_then_fixed".equals(chargeMode)) {
            long quantity = Math.max(1L, number(first(usage, "quantity", "replyCount", "imageCount", "itemCount")));
            long freeQuota = number(resolved.get("remainingFreeQuota"));
            long payableCount = Math.max(0L, quantity - freeQuota);
            sellTokens = payableCount * number(resolved.get("effectiveTokensPerReply"));
            pricingReason = "member_quota_then_fixed";
        } else if ("fixed_per_image".equals(chargeMode)) {
            long imageCount = Math.max(1L, number(first(usage, "imageCount", "quantity")));
            sellTokens = imageCount * number(resolved.get("effectiveTokensPerImage"));
            pricingReason = "fixed_per_image";
        } else if ("per_item_step".equals(chargeMode)) {
            long itemCount = Math.max(1L, number(first(usage, "itemCount", "quantity")));
            long baseTokens = number(resolved.get("effectiveBaseTokens"));
            long stepSize = Math.max(1L, number(resolved.get("effectiveStepSize")));
            long stepTokens = number(resolved.get("effectiveStepTokens"));
            long steps = BigDecimal.valueOf(itemCount)
                    .divide(BigDecimal.valueOf(stepSize), 0, RoundingMode.CEILING)
                    .longValue();
            sellTokens = baseTokens + steps * stepTokens;
            pricingReason = "step:" + steps;
        } else {
            sellTokens = number(resolved.get("effectiveTokensPerCall"));
            pricingReason = "fixed_per_call";
        }

        long minTokens = number(resolved.get("min_tokens"));
        long maxTokens = number(resolved.get("max_tokens"));
        if (minTokens > 0 && sellTokens < minTokens) sellTokens = minTokens;
        if (maxTokens > 0 && sellTokens > maxTokens) sellTokens = maxTokens;

        result.put("sellChargeTokens", sellTokens);
        result.put("pricingReason", pricingReason);
        return result;
    }

    private Object first(Map<String, Object> map, String... keys) {
        if (map == null) return null;
        for (String key : keys) {
            if (map.containsKey(key) && map.get(key) != null) return map.get(key);
        }
        return null;
    }

    private long positiveOrDefault(long preferred, long fallback) {
        return preferred > 0 ? preferred : fallback;
    }

    private long number(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return 0L;
        if (value instanceof Number n) return n.longValue();
        try {
            return new BigDecimal(String.valueOf(value)).setScale(0, RoundingMode.DOWN).longValue();
        } catch (Exception e) {
            return 0L;
        }
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String normalizePlanCode(String planCode) {
        if (!StringUtils.hasText(planCode)) return "normal";
        String code = planCode.trim().toLowerCase();
        return "svip".equals(code) ? "svp" : code;
    }
}
```

- [ ] **Step 3: Run the focused test to verify it passes**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 4: Refactor only if needed to keep names consistent**

If the test passes, do not expand the implementation beyond:

- scene config lookup
- plan benefit lookup
- fixed per call
- fixed per image
- stepped item charge
- quota-then-fixed reply charge

- [ ] **Step 5: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/AiScenePricingService.java apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java
git commit -m "feat: add ai scene pricing service"
```

### Task 4: Add plan-code lookup to the billing estimate path

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/AiBillingService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/UserProfileService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Add a failing test for user plan normalization**

```java
    @SuppressWarnings("unchecked")
    @Test
    void resolveScenePricingShouldNormalizeSvipToSvp() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);

        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        Map<String, Object> result = service.resolveScenePricing(1L, "auto_reply", "svip", Map.of("quantity", 1));
        assertEquals("svp", result.get("planCode"));
    }
```

- [ ] **Step 2: Run the focused test and verify it fails if plan normalization is missing**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
FAIL if normalization is wrong, otherwise PASS
```

- [ ] **Step 3: Add a reusable current plan-code method in `UserProfileService`**

```java
    public String currentPlanCode(Long userId) {
        Map<String, Object> active = queryActivePlan(userId);
        Object planCode = active.get("planCode");
        if (planCode == null) return "normal";
        String code = String.valueOf(planCode).trim().toLowerCase(Locale.ROOT);
        return "svip".equals(code) ? "svp" : (code.isBlank() ? "normal" : code);
    }
```

- [ ] **Step 4: Inject `UserProfileService` and `AiScenePricingService` into `AiBillingService`**

Update the constructor shape to:

```java
    private final UserProfileService userProfileService;
    private final AiScenePricingService aiScenePricingService;

    public AiBillingService(JdbcTemplate jdbcTemplate,
                            UserProfileService userProfileService,
                            AiScenePricingService aiScenePricingService) {
        this.jdbcTemplate = jdbcTemplate;
        this.userProfileService = userProfileService;
        this.aiScenePricingService = aiScenePricingService;
    }
```

- [ ] **Step 5: Add a new pricing-resolution method to `AiBillingService`**

```java
    public Map<String, Object> estimateScenePricingForCurrentUser(Map<String, Object> usage) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        usage.put("userId", userId);
        usage.put("tenantId", tenantId);

        Map<String, Object> cost = estimateUsage(usage, false);
        String scene = text(first(usage, "scene", "sceneKey", "scene_key"));
        String planCode = userProfileService.currentPlanCode(userId);
        Map<String, Object> sell = aiScenePricingService.resolveScenePricing(tenantId, scene, planCode, usage);

        Map<String, Object> res = new LinkedHashMap<>(cost);
        res.put("sceneKey", scene);
        res.put("planCode", planCode);
        res.put("sellChargeTokens", sell.get("sellChargeTokens"));
        res.put("pricingReason", sell.get("pricingReason"));
        res.put("remainingFreeQuota", sell.get("remainingFreeQuota"));
        res.put("effectiveChargeMode", sell.get("effectiveChargeMode"));
        res.put("enoughForSellPrice", number(cost.get("balance")) >= number(sell.get("sellChargeTokens")));
        return res;
    }
```

- [ ] **Step 6: Run the focused test to confirm scene plan resolution still passes**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 7: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/AiBillingService.java apps/core-api/src/main/java/com/xianyu/admin/service/UserProfileService.java apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java
git commit -m "feat: resolve ai sell pricing by user plan"
```

### Task 5: Expose a frontend estimate endpoint for sell-side pricing

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AiBillingController.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Add a failing usage-shape test for scene estimate payload**

```java
    @Test
    void usagePayloadShouldCarrySceneKey() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("scene", "workflow_image");
        payload.put("imageCount", 2);

        assertEquals("workflow_image", payload.get("scene"));
        assertEquals(2, payload.get("imageCount"));
    }
```

- [ ] **Step 2: Run the focused test and verify it remains green**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 3: Add the new controller endpoint**

```java
    @PostMapping("/api/ai-billing/estimate-scene")
    public Result<Map<String, Object>> estimateScene(@RequestBody Map<String, Object> usage) {
        return Result.ok(aiBillingService.estimateScenePricingForCurrentUser(usage));
    }
```

- [ ] **Step 4: Keep the existing `/api/ai-billing/estimate` untouched**

No extra code beyond leaving:

```java
    @PostMapping("/api/ai-billing/estimate")
```

unchanged.

- [ ] **Step 5: Run the focused test again**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 6: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/AiBillingController.java apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java
git commit -m "feat: expose ai scene estimate endpoint"
```

### Task 6: Add admin CRUD for scene pricing config

**Files:**
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/AiScenePricingAdminService.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/controller/AiScenePricingAdminController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Add a failing test for admin save field mapping**

```java
    @Test
    void adminPayloadShouldUseSceneKeyAndChargeMode() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("sceneKey", "workflow_screen");
        body.put("chargeMode", "per_item_step");
        body.put("baseTokens", 20);

        assertEquals("workflow_screen", body.get("sceneKey"));
        assertEquals("per_item_step", body.get("chargeMode"));
        assertEquals(20, body.get("baseTokens"));
    }
```

- [ ] **Step 2: Run the focused test and verify it stays green**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 3: Implement minimal admin service with page/save/delete for `ai_scene_sell_config`**

```java
package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AiScenePricingAdminService {
    private final JdbcTemplate jdbcTemplate;

    public AiScenePricingAdminService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public PageResult<Map<String, Object>> pageSceneSellConfig(int current, int size, String keyword) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (scene_key LIKE ? OR scene_name LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw);
            args.add(kw);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_scene_sell_config" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM ai_scene_sell_config" + where + " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?",
                pageArgs.toArray()
        );
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> saveSceneSellConfig(Map<String, Object> data) {
        String sceneKey = text(first(data, "sceneKey", "scene_key"));
        String sceneName = text(first(data, "sceneName", "scene_name"));
        String chargeMode = text(first(data, "chargeMode", "charge_mode"));
        if (!StringUtils.hasText(sceneKey)) throw new BizException(400, "sceneKey不能为空");
        if (!StringUtils.hasText(sceneName)) throw new BizException(400, "sceneName不能为空");
        if (!StringUtils.hasText(chargeMode)) throw new BizException(400, "chargeMode不能为空");

        Object id = data.get("id");
        if (id == null || String.valueOf(id).isBlank()) {
            jdbcTemplate.update(
                    "INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, base_tokens, step_size, step_tokens, sell_tokens_per_call, sell_tokens_per_item, sell_tokens_per_image, sell_tokens_per_reply, min_tokens, max_tokens, fallback_exchange_rate, daily_cap_count, daily_cap_tokens, monthly_cap_count, monthly_cap_tokens, sort_order, remark, created_time, updated_time, deleted) " +
                            "VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    sceneKey,
                    sceneName,
                    text(first(data, "sceneGroup", "scene_group")),
                    chargeMode,
                    text(first(data, "priceUnit", "price_unit")),
                    boolInt(first(data, "enabled")),
                    boolInt(first(data, "isMetered", "is_metered")),
                    boolInt(first(data, "showEstimate", "show_estimate")),
                    number(first(data, "baseTokens", "base_tokens")),
                    number(first(data, "stepSize", "step_size")),
                    number(first(data, "stepTokens", "step_tokens")),
                    number(first(data, "sellTokensPerCall", "sell_tokens_per_call")),
                    number(first(data, "sellTokensPerItem", "sell_tokens_per_item")),
                    number(first(data, "sellTokensPerImage", "sell_tokens_per_image")),
                    number(first(data, "sellTokensPerReply", "sell_tokens_per_reply")),
                    number(first(data, "minTokens", "min_tokens")),
                    number(first(data, "maxTokens", "max_tokens")),
                    number(first(data, "fallbackExchangeRate", "fallback_exchange_rate")),
                    number(first(data, "dailyCapCount", "daily_cap_count")),
                    number(first(data, "dailyCapTokens", "daily_cap_tokens")),
                    number(first(data, "monthlyCapCount", "monthly_cap_count")),
                    number(first(data, "monthlyCapTokens", "monthly_cap_tokens")),
                    number(first(data, "sortOrder", "sort_order")),
                    text(first(data, "remark"))
            );
        } else {
            jdbcTemplate.update(
                    "UPDATE ai_scene_sell_config SET scene_name=?, scene_group=?, charge_mode=?, price_unit=?, enabled=?, is_metered=?, show_estimate=?, base_tokens=?, step_size=?, step_tokens=?, sell_tokens_per_call=?, sell_tokens_per_item=?, sell_tokens_per_image=?, sell_tokens_per_reply=?, min_tokens=?, max_tokens=?, fallback_exchange_rate=?, daily_cap_count=?, daily_cap_tokens=?, monthly_cap_count=?, monthly_cap_tokens=?, sort_order=?, remark=?, updated_time=NOW() WHERE id=? AND deleted=0",
                    sceneName,
                    text(first(data, "sceneGroup", "scene_group")),
                    chargeMode,
                    text(first(data, "priceUnit", "price_unit")),
                    boolInt(first(data, "enabled")),
                    boolInt(first(data, "isMetered", "is_metered")),
                    boolInt(first(data, "showEstimate", "show_estimate")),
                    number(first(data, "baseTokens", "base_tokens")),
                    number(first(data, "stepSize", "step_size")),
                    number(first(data, "stepTokens", "step_tokens")),
                    number(first(data, "sellTokensPerCall", "sell_tokens_per_call")),
                    number(first(data, "sellTokensPerItem", "sell_tokens_per_item")),
                    number(first(data, "sellTokensPerImage", "sell_tokens_per_image")),
                    number(first(data, "sellTokensPerReply", "sell_tokens_per_reply")),
                    number(first(data, "minTokens", "min_tokens")),
                    number(first(data, "maxTokens", "max_tokens")),
                    number(first(data, "fallbackExchangeRate", "fallback_exchange_rate")),
                    number(first(data, "dailyCapCount", "daily_cap_count")),
                    number(first(data, "dailyCapTokens", "daily_cap_tokens")),
                    number(first(data, "monthlyCapCount", "monthly_cap_count")),
                    number(first(data, "monthlyCapTokens", "monthly_cap_tokens")),
                    number(first(data, "sortOrder", "sort_order")),
                    text(first(data, "remark")),
                    number(id)
            );
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM ai_scene_sell_config WHERE scene_key=? AND deleted=0 ORDER BY id DESC LIMIT 1", sceneKey);
        return rows.isEmpty() ? new LinkedHashMap<>() : rows.get(0);
    }

    public void deleteSceneSellConfig(long id) {
        jdbcTemplate.update("UPDATE ai_scene_sell_config SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
    }

    private Object first(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            if (map.containsKey(key) && map.get(key) != null) return map.get(key);
        }
        return null;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private long number(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return 0L;
        if (value instanceof Number n) return n.longValue();
        return Long.parseLong(String.valueOf(value).replaceAll("[^0-9-]", ""));
    }

    private int boolInt(Object value) {
        if (value == null) return 1;
        if (value instanceof Boolean b) return b ? 1 : 0;
        if (value instanceof Number n) return n.intValue() == 0 ? 0 : 1;
        String s = String.valueOf(value);
        return ("0".equals(s) || "false".equalsIgnoreCase(s)) ? 0 : 1;
    }
}
```

- [ ] **Step 4: Expose minimal admin controller**

```java
package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiScenePricingAdminService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
public class AiScenePricingAdminController {
    private final AiScenePricingAdminService aiScenePricingAdminService;

    public AiScenePricingAdminController(AiScenePricingAdminService aiScenePricingAdminService) {
        this.aiScenePricingAdminService = aiScenePricingAdminService;
    }

    @GetMapping("/admin-api/ai-scene-sell-config/page")
    public Result<PageResult<Map<String, Object>>> page(@RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size,
                                                        @RequestParam(required = false) String keyword) {
        return Result.ok(aiScenePricingAdminService.pageSceneSellConfig(current, size, keyword));
    }

    @PostMapping("/admin-api/ai-scene-sell-config")
    public Result<Map<String, Object>> save(@RequestBody Map<String, Object> data) {
        return Result.ok(aiScenePricingAdminService.saveSceneSellConfig(data));
    }

    @DeleteMapping("/admin-api/ai-scene-sell-config/{id}")
    public Result<Void> delete(@PathVariable long id) {
        aiScenePricingAdminService.deleteSceneSellConfig(id);
        return Result.ok(null);
    }
}
```

- [ ] **Step 5: Run the focused test again**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 6: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/AiScenePricingAdminService.java apps/core-api/src/main/java/com/xianyu/admin/controller/AiScenePricingAdminController.java apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java
git commit -m "feat: add admin crud for ai scene sell config"
```

### Task 7: Verify end-to-end compile and focused tests

**Files:**
- Modify: `docs/2026-07-01-AI场景售价配置设计与SQL草案.md`
- Modify: `docs/2026-07-01-AI首发价格矩阵与核算监控SQL.md`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/AiScenePricingServiceTest.java`

- [ ] **Step 1: Update the docs to note which parts are now implemented**

Append a short section to `docs/2026-07-01-AI场景售价配置设计与SQL草案.md`:

```md
## 实施状态

- 已落地：场景售价配置表、会员权益表、场景估算接口、管理端基础 CRUD
- 待继续：前台 estimate-scene 接入、扣费路径切换到场景售价层、delivery_source_match 真实收费化
```

Append a short section to `docs/2026-07-01-AI首发价格矩阵与核算监控SQL.md`:

```md
## 落地建议优先级

1. 先接 `auto_reply`
2. 再接 `workflow_image`
3. 再接 `workflow_screen` / `product_filter`
4. 最后处理 `delivery_source_match`
```

- [ ] **Step 2: Run the focused unit test**

Run:

```bash
mvn -f apps/core-api/pom.xml -Dtest=AiScenePricingServiceTest test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 3: Run a narrow compile check**

Run:

```bash
mvn -f apps/core-api/pom.xml -DskipTests compile
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 4: Run the full existing test suite only if it is fast enough**

Run:

```bash
mvn -f apps/core-api/pom.xml test
```

Expected:

```text
BUILD SUCCESS
```

If this suite is not green for unrelated pre-existing reasons, record the exact failing tests and proceed with the focused passing evidence from `AiScenePricingServiceTest`.

- [ ] **Step 5: Commit**

```bash
git add docs/2026-07-01-AI场景售价配置设计与SQL草案.md docs/2026-07-01-AI首发价格矩阵与核算监控SQL.md
git commit -m "docs: mark ai scene pricing implementation status"
```

## Self-Review

- Spec coverage:
  - New pricing config tables: Task 2
  - Scene sell-side resolution: Task 3
  - Plan-aware estimate API: Task 4 and Task 5
  - Admin CRUD: Task 6
  - Verification and docs alignment: Task 7
- Placeholder scan:
  - No `TODO`, `TBD`, or “similar to previous task” placeholders remain
- Type consistency:
  - `sceneKey`, `planCode`, `chargeMode`, `sellChargeTokens`, `remainingFreeQuota`, and `effectiveChargeMode` are used consistently across service and controller tasks

Plan complete and saved to `docs/superpowers/plans/2026-07-01-ai-scene-pricing-config.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
