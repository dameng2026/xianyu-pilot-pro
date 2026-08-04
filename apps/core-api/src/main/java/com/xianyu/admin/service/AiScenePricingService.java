package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class AiScenePricingService {
    private static final BigDecimal DEFAULT_MARKUP_RATE = BigDecimal.ONE;
    private static final BigDecimal DEFAULT_EXCHANGE_RATE = BigDecimal.valueOf(160);

    private final JdbcTemplate jdbcTemplate;

    public AiScenePricingService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Map<String, Object> resolveScenePricing(Long tenantId, String sceneKey, String planCode, Map<String, Object> usage) {
        Map<String, Object> scene = findSceneConfig(tenantId, sceneKey);
        Map<String, Object> benefit = findPlanBenefit(tenantId, sceneKey, normalizePlanCode(planCode));
        Map<String, Object> resolved = applyPlanBenefit(scene, benefit, number(first(usage, "alreadyUsedToday", "usedToday", "todayUsedCount")));
        Map<String, Object> sell = computeSellTokens(resolved, usage);
        Map<String, Object> result = new LinkedHashMap<>(resolved);
        result.putAll(sell);
        result.put("sceneKey", sceneKey);
        result.put("planCode", normalizePlanCode(planCode));
        result.put("sceneConfigExists", !scene.isEmpty());
        return result;
    }

    Map<String, Object> applyPlanBenefit(Map<String, Object> scene, Map<String, Object> benefit, long alreadyUsedToday) {
        Map<String, Object> resolved = new LinkedHashMap<>(scene == null ? Map.of() : scene);
        String chargeMode = text(first(benefit, "override_charge_mode"));
        if (!StringUtils.hasText(chargeMode)) {
            chargeMode = text(first(scene, "charge_mode"));
        }
        resolved.put("effectiveChargeMode", chargeMode);

        long freeDaily = number(first(benefit, "free_quota_daily"));
        resolved.put("remainingFreeQuota", Math.max(0L, freeDaily - alreadyUsedToday));

        resolved.put("effectiveTokensPerCall", overrideOrScene(benefit, scene, "override_tokens_per_call", "sell_tokens_per_call"));
        resolved.put("effectiveTokensPerItem", overrideOrScene(benefit, scene, "override_tokens_per_item", "sell_tokens_per_item"));
        resolved.put("effectiveTokensPerImage", overrideOrScene(benefit, scene, "override_tokens_per_image", "sell_tokens_per_image"));
        resolved.put("effectiveTokensPerReply", overrideOrScene(benefit, scene, "override_tokens_per_reply", "sell_tokens_per_reply"));
        resolved.put("effectiveBaseTokens", overrideOrScene(benefit, scene, "override_base_tokens", "base_tokens"));
        resolved.put("effectiveStepSize", overrideOrScene(benefit, scene, "override_step_size", "step_size"));
        resolved.put("effectiveStepTokens", overrideOrScene(benefit, scene, "override_step_tokens", "step_tokens"));
        return resolved;
    }

    Map<String, Object> computeSellTokens(Map<String, Object> resolved, Map<String, Object> usage) {
        Map<String, Object> result = new LinkedHashMap<>();
        String chargeMode = text(first(resolved, "effectiveChargeMode", "charge_mode"));
        long sellTokens;
        String pricingReason;

        switch (chargeMode) {
            case "member_quota_then_fixed" -> {
                long quantity = Math.max(1L, number(first(usage, "quantity", "replyCount", "imageCount", "itemCount")));
                long remainingFree = Math.max(0L, number(first(resolved, "remainingFreeQuota")));
                long payableCount = Math.max(0L, quantity - remainingFree);
                sellTokens = payableCount * number(first(resolved, "effectiveTokensPerReply"));
                pricingReason = "member_quota_then_fixed";
            }
            case "fixed_per_image" -> {
                long imageCount = Math.max(1L, number(first(usage, "imageCount", "quantity")));
                sellTokens = imageCount * number(first(resolved, "effectiveTokensPerImage"));
                pricingReason = "fixed_per_image";
            }
            case "per_item_step" -> {
                long itemCount = Math.max(1L, number(first(usage, "itemCount", "quantity")));
                long baseTokens = number(first(resolved, "effectiveBaseTokens"));
                long stepSize = Math.max(1L, number(first(resolved, "effectiveStepSize")));
                long stepTokens = number(first(resolved, "effectiveStepTokens"));
                long steps = BigDecimal.valueOf(itemCount)
                        .divide(BigDecimal.valueOf(stepSize), 0, RoundingMode.CEILING)
                        .longValue();
                sellTokens = baseTokens + steps * stepTokens;
                pricingReason = "step:" + steps;
            }
            case "cost_plus_rate" -> {
                BigDecimal costYuan = decimal(first(usage, "costYuan", "cost_yuan"));
                BigDecimal exchangeRate = decimal(first(resolved, "fallback_exchange_rate"));
                if (exchangeRate.compareTo(BigDecimal.ZERO) <= 0) {
                    exchangeRate = DEFAULT_EXCHANGE_RATE;
                }
                BigDecimal markupRate = decimal(first(resolved, "cost_markup_rate"));
                if (markupRate.compareTo(BigDecimal.ZERO) <= 0) {
                    markupRate = DEFAULT_MARKUP_RATE;
                }
                sellTokens = costYuan
                        .multiply(exchangeRate)
                        .multiply(markupRate)
                        .setScale(0, RoundingMode.CEILING)
                        .longValue();
                pricingReason = "cost_plus_rate";
            }
            case "free" -> {
                sellTokens = 0L;
                pricingReason = "free";
            }
            default -> {
                long quantity = Math.max(1L, number(first(usage, "quantity", "callCount")));
                sellTokens = quantity * number(first(resolved, "effectiveTokensPerCall"));
                pricingReason = "fixed_per_call";
            }
        }

        long minTokens = number(first(resolved, "min_tokens"));
        long maxTokens = number(first(resolved, "max_tokens"));
        if (minTokens > 0 && sellTokens < minTokens) {
            sellTokens = minTokens;
        }
        if (maxTokens > 0 && sellTokens > maxTokens) {
            sellTokens = maxTokens;
        }

        result.put("sellChargeTokens", sellTokens);
        result.put("pricingReason", pricingReason);
        return result;
    }

    private Map<String, Object> findSceneConfig(Long tenantId, String sceneKey) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM ai_scene_sell_config WHERE deleted=0 AND enabled=1 AND scene_key=? " +
                        "AND (tenant_id IS NULL OR tenant_id=?) " +
                        "ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                sceneKey, tenantId
        );
        return rows.isEmpty() ? new LinkedHashMap<>() : new LinkedHashMap<>(rows.get(0));
    }

    private Map<String, Object> findPlanBenefit(Long tenantId, String sceneKey, String planCode) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM ai_scene_plan_benefit WHERE deleted=0 AND enabled=1 AND scene_key=? AND plan_code=? " +
                        "AND (tenant_id IS NULL OR tenant_id=?) " +
                        "ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                sceneKey, planCode, tenantId
        );
        return rows.isEmpty() ? new LinkedHashMap<>() : new LinkedHashMap<>(rows.get(0));
    }

    private long overrideOrScene(Map<String, Object> benefit, Map<String, Object> scene, String overrideKey, String sceneKey) {
        long overrideValue = number(first(benefit, overrideKey));
        return overrideValue > 0 ? overrideValue : number(first(scene, sceneKey));
    }

    private Object first(Map<String, Object> map, String... keys) {
        if (map == null) {
            return null;
        }
        for (String key : keys) {
            if (map.containsKey(key) && map.get(key) != null) {
                return map.get(key);
            }
        }
        return null;
    }

    private long number(Object value) {
        if (value == null || String.valueOf(value).isBlank()) {
            return 0L;
        }
        if (value instanceof Number n) {
            return n.longValue();
        }
        try {
            return new BigDecimal(String.valueOf(value)).setScale(0, RoundingMode.DOWN).longValue();
        } catch (Exception e) {
            return 0L;
        }
    }

    private BigDecimal decimal(Object value) {
        if (value == null || String.valueOf(value).isBlank()) {
            return BigDecimal.ZERO;
        }
        if (value instanceof BigDecimal bd) {
            return bd;
        }
        if (value instanceof Number n) {
            return BigDecimal.valueOf(n.doubleValue());
        }
        try {
            return new BigDecimal(String.valueOf(value).trim());
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String normalizePlanCode(String planCode) {
        String code = StringUtils.hasText(planCode) ? planCode.trim().toLowerCase(Locale.ROOT) : "normal";
        if ("svip".equals(code)) return "svp";
        if (code.startsWith("vip-single") || code.startsWith("vip_single") || "vip1".equals(code)) return "vip";
        return code;
    }
}
