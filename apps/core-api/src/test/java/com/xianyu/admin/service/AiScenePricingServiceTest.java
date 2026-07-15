package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AiScenePricingServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @SuppressWarnings("unchecked")
    @Test
    void fixedPerReplyShouldUsePlanQuotaAndOverridePrice() throws Exception {
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);
        Method applyPlanBenefit = AiScenePricingService.class.getDeclaredMethod(
                "applyPlanBenefit",
                Map.class,
                Map.class,
                long.class
        );
        applyPlanBenefit.setAccessible(true);

        Map<String, Object> scene = new LinkedHashMap<>();
        scene.put("charge_mode", "member_quota_then_fixed");
        scene.put("sell_tokens_per_reply", 8L);

        Map<String, Object> benefit = new LinkedHashMap<>();
        benefit.put("free_quota_daily", 30L);
        benefit.put("override_tokens_per_reply", 6L);

        Map<String, Object> resolved = (Map<String, Object>) applyPlanBenefit.invoke(service, scene, benefit, 5L);

        assertEquals(25L, resolved.get("remainingFreeQuota"));
        assertEquals(6L, resolved.get("effectiveTokensPerReply"));
        assertEquals("member_quota_then_fixed", resolved.get("effectiveChargeMode"));
    }

    @SuppressWarnings("unchecked")
    @Test
    void steppedPricingShouldChargeByCeiledItemBuckets() throws Exception {
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);
        Method computeSellTokens = AiScenePricingService.class.getDeclaredMethod(
                "computeSellTokens",
                Map.class,
                Map.class
        );
        computeSellTokens.setAccessible(true);

        Map<String, Object> scene = new LinkedHashMap<>();
        scene.put("effectiveChargeMode", "per_item_step");
        scene.put("effectiveBaseTokens", 20L);
        scene.put("effectiveStepSize", 10L);
        scene.put("effectiveStepTokens", 10L);
        scene.put("min_tokens", 20L);

        Map<String, Object> usage = new LinkedHashMap<>();
        usage.put("itemCount", 23);

        Map<String, Object> result = (Map<String, Object>) computeSellTokens.invoke(service, scene, usage);

        assertEquals(50L, result.get("sellChargeTokens"));
        assertTrue(String.valueOf(result.get("pricingReason")).contains("step"));
    }

    @SuppressWarnings("unchecked")
    @Test
    void costPlusRateShouldUseMarkupAndFallbackExchangeRate() throws Exception {
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);
        Method computeSellTokens = AiScenePricingService.class.getDeclaredMethod(
                "computeSellTokens",
                Map.class,
                Map.class
        );
        computeSellTokens.setAccessible(true);

        Map<String, Object> scene = new LinkedHashMap<>();
        scene.put("effectiveChargeMode", "cost_plus_rate");
        scene.put("fallback_exchange_rate", 160);
        scene.put("cost_markup_rate", "1.50");

        Map<String, Object> usage = new LinkedHashMap<>();
        usage.put("costYuan", "0.11");

        Map<String, Object> result = (Map<String, Object>) computeSellTokens.invoke(service, scene, usage);

        assertEquals(27L, result.get("sellChargeTokens"));
        assertEquals("cost_plus_rate", result.get("pricingReason"));
    }

    @Test
    void resolveScenePricingShouldNormalizeSvipPlanCode() {
        AiScenePricingService service = new AiScenePricingService(jdbcTemplate);
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class)))
                .thenReturn(List.of());

        Map<String, Object> result = service.resolveScenePricing(1L, "auto_reply", "svip", Map.of("quantity", 1));

        assertEquals("svp", result.get("planCode"));
    }
}
