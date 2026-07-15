package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AiBillingServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private UserProfileService userProfileService;

    @Mock
    private AiScenePricingService aiScenePricingService;

    private AiBillingService service;

    @BeforeEach
    void setUp() {
        service = new AiBillingService(jdbcTemplate, userProfileService, aiScenePricingService);
        UserContext.set(9L, "tester", 1L);
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
    }

    @Test
    void estimateScenePricingShouldUseTodayUsageAndSellPrice() {
        when(jdbcTemplate.queryForList(
                eq("SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND model_type=? AND (tenant_id IS NULL OR tenant_id=?) AND (model_name=? OR model_name='default') AND (provider_name=? OR provider_name='default') ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, CASE WHEN model_name=? THEN 0 ELSE 1 END, CASE WHEN provider_name=? THEN 0 ELSE 1 END, id DESC LIMIT 1"),
                eq("chat"),
                eq(1L),
                eq("default"),
                eq("default"),
                eq("default"),
                eq("default")
        )).thenReturn(List.of(priceRow()));
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(9L),
                eq(1L)
        )).thenReturn(List.of(Map.of("token_balance", 120L)));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND user_id=? AND scene=? AND DATE(created_time)=CURRENT_DATE()"),
                eq(Long.class),
                eq(9L),
                eq("auto_reply")
        )).thenReturn(7L);
        when(userProfileService.currentPlanCode(9L)).thenReturn("vip");
        when(aiScenePricingService.resolveScenePricing(eq(1L), eq("auto_reply"), eq("vip"), org.mockito.ArgumentMatchers.<Map<String, Object>>any()))
                .thenAnswer(invocation -> {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> usage = invocation.getArgument(3, Map.class);
                    assertEquals(7L, usage.get("alreadyUsedToday"));
                    return new LinkedHashMap<>(Map.of(
                            "sellChargeTokens", 6L,
                            "pricingReason", "member_quota_then_fixed",
                            "remainingFreeQuota", 23L,
                            "effectiveChargeMode", "member_quota_then_fixed"
                    ));
                });

        Map<String, Object> result = service.estimateScenePricingForCurrentUser(new LinkedHashMap<>(Map.of(
                "scene", "auto_reply",
                "modelType", "chat",
                "promptTokens", 200,
                "completionTokens", 60
        )));

        assertEquals("auto_reply", result.get("sceneKey"));
        assertEquals("vip", result.get("planCode"));
        assertEquals(6L, result.get("sellChargeTokens"));
        assertEquals(23L, result.get("remainingFreeQuota"));
        assertEquals(true, result.get("enoughForSellPrice"));
    }

    @Test
    void estimateScenePricingShouldUseModelPriceWhenScenePriceIsUnavailable() {
        Map<String, Object> row = priceRow();
        row.put("tokens_per_call", 25L);
        stubPriceLookup("chat", row);
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(9L),
                eq(1L)
        )).thenReturn(List.of(Map.of("token_balance", 20L)));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND user_id=? AND scene=? AND DATE(created_time)=CURRENT_DATE()"),
                eq(Long.class),
                eq(9L),
                eq("workflow_rewrite")
        )).thenReturn(0L);
        when(userProfileService.currentPlanCode(9L)).thenReturn("normal");
        when(aiScenePricingService.resolveScenePricing(eq(1L), eq("workflow_rewrite"), eq("normal"), org.mockito.ArgumentMatchers.<Map<String, Object>>any()))
                .thenReturn(new LinkedHashMap<>(Map.of(
                        "sceneConfigExists", false,
                        "sellChargeTokens", 0L,
                        "pricingReason", "fixed_per_call",
                        "remainingFreeQuota", 0L,
                        "effectiveChargeMode", ""
                )));

        Map<String, Object> result = service.estimateScenePricingForCurrentUser(new LinkedHashMap<>(Map.of(
                "scene", "workflow_rewrite",
                "modelType", "chat"
        )));

        assertEquals(25L, result.get("sellChargeTokens"));
        assertEquals(25L, result.get("chargeTokens"));
        assertEquals("model_price_fallback", result.get("pricingReason"));
        assertEquals(false, result.get("enoughForSellPrice"));
    }

    @Test
    void precheckShouldUseSceneSellPriceForBalanceValidation() {
        stubChatPriceLookup();
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(9L),
                eq(1L)
        )).thenReturn(List.of(Map.of("token_balance", 5L)));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND user_id=? AND scene=? AND DATE(created_time)=CURRENT_DATE()"),
                eq(Long.class),
                eq(9L),
                eq("workflow_rewrite")
        )).thenReturn(0L);
        when(userProfileService.currentPlanCode(9L)).thenReturn("vip");
        when(aiScenePricingService.resolveScenePricing(eq(1L), eq("workflow_rewrite"), eq("vip"), org.mockito.ArgumentMatchers.<Map<String, Object>>any()))
                .thenReturn(new LinkedHashMap<>(Map.of(
                        "sceneConfigExists", true,
                        "sellChargeTokens", 12L,
                        "pricingReason", "fixed_per_call",
                        "remainingFreeQuota", 0L,
                        "effectiveChargeMode", "fixed_per_call"
                )));

        Assertions.assertThrows(RuntimeException.class, () -> service.precheck(new LinkedHashMap<>(Map.of(
                "tenantId", 1L,
                "userId", 9L,
                "scene", "workflow_rewrite",
                "modelType", "chat",
                "promptTokens", 120,
                "completionTokens", 30
        ))));
    }

    @Test
    void chargeShouldDeductSceneSellPriceWhenConfigExists() {
        stubChatPriceLookup();
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0 FOR UPDATE"),
                eq(9L),
                eq(1L)
        )).thenReturn(List.of(Map.of("token_balance", 100L)));
        when(jdbcTemplate.queryForList(
                eq("SELECT id, tenant_id, user_id, status, charge_tokens, balance_after FROM ai_usage_log WHERE request_id=? AND deleted=0"),
                eq("req_sell_charge")
        )).thenReturn(List.of());
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(9L),
                eq(1L)
        )).thenReturn(List.of(Map.of("token_balance", 100L)));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND user_id=? AND scene=? AND DATE(created_time)=CURRENT_DATE()"),
                eq(Long.class),
                eq(9L),
                eq("workflow_rewrite")
        )).thenReturn(2L);
        when(userProfileService.currentPlanCode(9L)).thenReturn("vip");
        when(aiScenePricingService.resolveScenePricing(eq(1L), eq("workflow_rewrite"), eq("vip"), org.mockito.ArgumentMatchers.<Map<String, Object>>any()))
                .thenReturn(new LinkedHashMap<>(Map.of(
                        "sceneConfigExists", true,
                        "sellChargeTokens", 12L,
                        "pricingReason", "fixed_per_call",
                        "remainingFreeQuota", 0L,
                        "effectiveChargeMode", "fixed_per_call"
                )));
        when(jdbcTemplate.queryForObject(eq("SELECT LAST_INSERT_ID()"), eq(Long.class))).thenReturn(501L);
        doReturn(1).when(jdbcTemplate).update(
                argThat(sql -> sql.startsWith("UPDATE sys_user SET token_balance=")),
                any(Object[].class));
        doReturn(1).when(jdbcTemplate).update(
                argThat(sql -> sql.startsWith("INSERT INTO ai_usage_log")),
                any(Object[].class));
        doReturn(1).when(jdbcTemplate).update(
                argThat(sql -> sql.startsWith("INSERT INTO token_balance_ledger")),
                any(Object[].class));

        Map<String, Object> result = service.charge(new LinkedHashMap<>(Map.of(
                "tenantId", 1L,
                "userId", 9L,
                "scene", "workflow_rewrite",
                "modelType", "chat",
                "promptTokens", 120,
                "completionTokens", 30,
                "requestId", "req_sell_charge"
        )));

        assertEquals(12L, result.get("chargeTokens"));
        assertEquals(88L, result.get("balanceAfter"));
        verify(jdbcTemplate).update(
                eq("UPDATE sys_user SET token_balance=?, updated_time=NOW() WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(88L),
                eq(9L),
                eq(1L)
        );
    }

    @Test
    void chargeRejectsUserOutsideSuppliedTenantBeforeDeduction() {
        when(jdbcTemplate.queryForList(
                eq("SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND model_type=? AND (tenant_id IS NULL OR tenant_id=?) AND (model_name=? OR model_name='default') AND (provider_name=? OR provider_name='default') ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, CASE WHEN model_name=? THEN 0 ELSE 1 END, CASE WHEN provider_name=? THEN 0 ELSE 1 END, id DESC LIMIT 1"),
                eq("chat"),
                eq(22L),
                eq("default"),
                eq("default"),
                eq("default"),
                eq("default")
        )).thenReturn(List.of(priceRow()));
        when(jdbcTemplate.queryForList(
                eq("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0"),
                eq(9L),
                eq(22L)
        )).thenReturn(List.of());

        BizException error = assertThrows(BizException.class, () -> service.charge(new LinkedHashMap<>(Map.of(
                "tenantId", 22L,
                "userId", 9L,
                "scene", "workflow_rewrite",
                "modelType", "chat",
                "promptTokens", 120,
                "completionTokens", 30,
                "requestId", "req_cross_tenant"
        ))));

        assertEquals(404, error.getCode());
    }

    @Test
    void estimateUsageShouldApplyFixedChatTokensPerCall() {
        Map<String, Object> row = priceRow();
        row.put("tokens_per_call", 25L);
        stubPriceLookup("chat", row);

        Map<String, Object> result = service.estimateUsage(new LinkedHashMap<>(Map.of(
                "tenantId", 1L,
                "modelType", "chat",
                "promptTokens", 100,
                "completionTokens", 20
        )), false);

        assertEquals(25L, result.get("chargeTokens"));
    }

    @Test
    void estimateUsageShouldApplyFixedImageTokensForEveryImage() {
        Map<String, Object> row = priceRow();
        row.put("tokens_per_image", 8L);
        stubPriceLookup("image", row);

        Map<String, Object> result = service.estimateUsage(new LinkedHashMap<>(Map.of(
                "tenantId", 1L,
                "modelType", "image",
                "imageCount", 3
        )), false);

        assertEquals(24L, result.get("chargeTokens"));
    }

    @Test
    void chatCostPerCallShouldOverrideTokenCostInsteadOfBeingAddedTwice() {
        Map<String, Object> row = priceRow();
        row.put("input_price_per_1k", BigDecimal.ONE);
        row.put("cost_per_call", BigDecimal.valueOf(2));
        stubPriceLookup("chat", row);

        Map<String, Object> result = service.estimateUsage(new LinkedHashMap<>(Map.of(
                "tenantId", 1L,
                "modelType", "chat",
                "promptTokens", 1000,
                "completionTokens", 0
        )), false);

        assertEquals(new BigDecimal("2.000000"), result.get("costYuan"));
        assertEquals(new BigDecimal("0.000000"), result.get("nonCachedInputCostYuan"));
        assertEquals(200L, result.get("chargeTokens"));
    }

    @Test
    void missingPriceConfigurationFailsClosedInsteadOfAllowingFreeUsage() {
        BizException error = assertThrows(BizException.class, () -> service.estimateUsage(
                new LinkedHashMap<>(Map.of(
                        "tenantId", 1L,
                        "modelType", "chat",
                        "promptTokens", 100
                )), false));

        assertEquals(503, error.getCode());
    }

    @Test
    void malformedPriceInputIsRejectedInsteadOfBecomingZero() {
        BizException error = assertThrows(BizException.class, () -> service.saveModelPrice(
                new LinkedHashMap<>(Map.of(
                        "modelName", "model-a",
                        "modelType", "chat",
                        "inputPricePer1k", "not-a-number"
                ))));

        assertEquals(400, error.getCode());
    }

    private void stubChatPriceLookup() {
        when(jdbcTemplate.queryForList(
                eq("SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND model_type=? AND (tenant_id IS NULL OR tenant_id=?) AND (model_name=? OR model_name='default') AND (provider_name=? OR provider_name='default') ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, CASE WHEN model_name=? THEN 0 ELSE 1 END, CASE WHEN provider_name=? THEN 0 ELSE 1 END, id DESC LIMIT 1"),
                eq("chat"),
                eq(1L),
                eq("default"),
                eq("default"),
                eq("default"),
                eq("default")
        )).thenReturn(List.of(priceRow()));
    }

    private void stubPriceLookup(String modelType, Map<String, Object> row) {
        when(jdbcTemplate.queryForList(
                eq("SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND model_type=? AND (tenant_id IS NULL OR tenant_id=?) AND (model_name=? OR model_name='default') AND (provider_name=? OR provider_name='default') ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, CASE WHEN model_name=? THEN 0 ELSE 1 END, CASE WHEN provider_name=? THEN 0 ELSE 1 END, id DESC LIMIT 1"),
                eq(modelType),
                eq(1L),
                eq("default"),
                eq("default"),
                eq("default"),
                eq("default")
        )).thenReturn(List.of(row));
    }

    private Map<String, Object> priceRow() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("billing_mode", "token");
        row.put("input_price_per_1k", BigDecimal.ZERO);
        row.put("output_price_per_1k", BigDecimal.ZERO);
        row.put("cached_input_price_per_1k", BigDecimal.ZERO);
        row.put("per_call_price", BigDecimal.ZERO);
        row.put("token_exchange_rate", BigDecimal.valueOf(100));
        row.put("min_charge_token", 0L);
        row.put("billing_unit", "1K");
        row.put("cost_per_image", BigDecimal.ZERO);
        row.put("tokens_per_image", 0L);
        row.put("cost_per_call", BigDecimal.ZERO);
        row.put("tokens_per_call", 0L);
        return row;
    }
}
