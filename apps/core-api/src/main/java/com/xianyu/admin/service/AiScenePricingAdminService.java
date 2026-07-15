package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class AiScenePricingAdminService {
    private final JdbcTemplate jdbcTemplate;

    public AiScenePricingAdminService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public PageResult<Map<String, Object>> pageScenes(int current, int size, String keyword, String sceneGroup) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (scene_key LIKE ? OR scene_name LIKE ? OR remark LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw);
            args.add(kw);
            args.add(kw);
        }
        if (StringUtils.hasText(sceneGroup)) {
            where.append(" AND scene_group=?");
            args.add(sceneGroup.trim());
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_scene_sell_config" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, scene_key AS sceneKey, scene_name AS sceneName, scene_group AS sceneGroup, " +
                        "charge_mode AS chargeMode, price_unit AS priceUnit, enabled, is_metered AS isMetered, show_estimate AS showEstimate, " +
                        "allow_trial AS allowTrial, trial_quota AS trialQuota, base_tokens AS baseTokens, step_size AS stepSize, step_tokens AS stepTokens, " +
                        "sell_tokens_per_call AS sellTokensPerCall, sell_tokens_per_item AS sellTokensPerItem, sell_tokens_per_image AS sellTokensPerImage, " +
                        "sell_tokens_per_reply AS sellTokensPerReply, sell_tokens_per_file AS sellTokensPerFile, sell_tokens_per_1k_chars AS sellTokensPer1kChars, " +
                        "min_tokens AS minTokens, max_tokens AS maxTokens, member_discount_rate AS memberDiscountRate, cost_markup_rate AS costMarkupRate, " +
                        "fallback_exchange_rate AS fallbackExchangeRate, daily_cap_count AS dailyCapCount, daily_cap_tokens AS dailyCapTokens, " +
                        "monthly_cap_count AS monthlyCapCount, monthly_cap_tokens AS monthlyCapTokens, sort_order AS sortOrder, remark, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM ai_scene_sell_config" + where + " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?",
                pageArgs.toArray()
        );
        rows.forEach(this::decorateSceneRow);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> sceneDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, scene_key AS sceneKey, scene_name AS sceneName, scene_group AS sceneGroup, " +
                        "charge_mode AS chargeMode, price_unit AS priceUnit, enabled, is_metered AS isMetered, show_estimate AS showEstimate, " +
                        "allow_trial AS allowTrial, trial_quota AS trialQuota, base_tokens AS baseTokens, step_size AS stepSize, step_tokens AS stepTokens, " +
                        "sell_tokens_per_call AS sellTokensPerCall, sell_tokens_per_item AS sellTokensPerItem, sell_tokens_per_image AS sellTokensPerImage, " +
                        "sell_tokens_per_reply AS sellTokensPerReply, sell_tokens_per_file AS sellTokensPerFile, sell_tokens_per_1k_chars AS sellTokensPer1kChars, " +
                        "min_tokens AS minTokens, max_tokens AS maxTokens, member_discount_rate AS memberDiscountRate, cost_markup_rate AS costMarkupRate, " +
                        "fallback_exchange_rate AS fallbackExchangeRate, daily_cap_count AS dailyCapCount, daily_cap_tokens AS dailyCapTokens, " +
                        "monthly_cap_count AS monthlyCapCount, monthly_cap_tokens AS monthlyCapTokens, sort_order AS sortOrder, remark, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM ai_scene_sell_config WHERE id=? AND deleted=0",
                id
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "场景售价配置不存在");
        }
        Map<String, Object> row = rows.get(0);
        decorateSceneRow(row);
        return row;
    }

    @Transactional
    public Map<String, Object> createScene(Map<String, Object> data) {
        Map<String, Object> normalized = normalizeScenePayload(data, null);
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_scene_sell_config WHERE tenant_id <=> ? AND scene_key=? AND deleted=0",
                Long.class,
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey")
        );
        if (exists != null && exists > 0) {
            throw new BizException(400, "场景键已存在");
        }
        jdbcTemplate.update(
                "INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, allow_trial, trial_quota, " +
                        "base_tokens, step_size, step_tokens, sell_tokens_per_call, sell_tokens_per_item, sell_tokens_per_image, sell_tokens_per_reply, sell_tokens_per_file, sell_tokens_per_1k_chars, " +
                        "min_tokens, max_tokens, member_discount_rate, cost_markup_rate, fallback_exchange_rate, daily_cap_count, daily_cap_tokens, monthly_cap_count, monthly_cap_tokens, sort_order, remark, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("sceneName"),
                normalized.get("sceneGroup"),
                normalized.get("chargeMode"),
                normalized.get("priceUnit"),
                normalized.get("enabled"),
                normalized.get("isMetered"),
                normalized.get("showEstimate"),
                normalized.get("allowTrial"),
                normalized.get("trialQuota"),
                normalized.get("baseTokens"),
                normalized.get("stepSize"),
                normalized.get("stepTokens"),
                normalized.get("sellTokensPerCall"),
                normalized.get("sellTokensPerItem"),
                normalized.get("sellTokensPerImage"),
                normalized.get("sellTokensPerReply"),
                normalized.get("sellTokensPerFile"),
                normalized.get("sellTokensPer1kChars"),
                normalized.get("minTokens"),
                normalized.get("maxTokens"),
                normalized.get("memberDiscountRate"),
                normalized.get("costMarkupRate"),
                normalized.get("fallbackExchangeRate"),
                normalized.get("dailyCapCount"),
                normalized.get("dailyCapTokens"),
                normalized.get("monthlyCapCount"),
                normalized.get("monthlyCapTokens"),
                normalized.get("sortOrder"),
                normalized.get("remark")
        );
        Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        return sceneDetail(newId == null ? 0 : newId);
    }

    @Transactional
    public Map<String, Object> updateScene(long id, Map<String, Object> data) {
        Map<String, Object> old = sceneDetail(id);
        Map<String, Object> normalized = normalizeScenePayload(data, old);
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_scene_sell_config WHERE tenant_id <=> ? AND scene_key=? AND id<>? AND deleted=0",
                Long.class,
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                id
        );
        if (exists != null && exists > 0) {
            throw new BizException(400, "场景键已存在");
        }
        jdbcTemplate.update(
                "UPDATE ai_scene_sell_config SET tenant_id=?, scene_key=?, scene_name=?, scene_group=?, charge_mode=?, price_unit=?, enabled=?, is_metered=?, show_estimate=?, allow_trial=?, trial_quota=?, " +
                        "base_tokens=?, step_size=?, step_tokens=?, sell_tokens_per_call=?, sell_tokens_per_item=?, sell_tokens_per_image=?, sell_tokens_per_reply=?, sell_tokens_per_file=?, sell_tokens_per_1k_chars=?, " +
                        "min_tokens=?, max_tokens=?, member_discount_rate=?, cost_markup_rate=?, fallback_exchange_rate=?, daily_cap_count=?, daily_cap_tokens=?, monthly_cap_count=?, monthly_cap_tokens=?, sort_order=?, remark=?, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0",
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("sceneName"),
                normalized.get("sceneGroup"),
                normalized.get("chargeMode"),
                normalized.get("priceUnit"),
                normalized.get("enabled"),
                normalized.get("isMetered"),
                normalized.get("showEstimate"),
                normalized.get("allowTrial"),
                normalized.get("trialQuota"),
                normalized.get("baseTokens"),
                normalized.get("stepSize"),
                normalized.get("stepTokens"),
                normalized.get("sellTokensPerCall"),
                normalized.get("sellTokensPerItem"),
                normalized.get("sellTokensPerImage"),
                normalized.get("sellTokensPerReply"),
                normalized.get("sellTokensPerFile"),
                normalized.get("sellTokensPer1kChars"),
                normalized.get("minTokens"),
                normalized.get("maxTokens"),
                normalized.get("memberDiscountRate"),
                normalized.get("costMarkupRate"),
                normalized.get("fallbackExchangeRate"),
                normalized.get("dailyCapCount"),
                normalized.get("dailyCapTokens"),
                normalized.get("monthlyCapCount"),
                normalized.get("monthlyCapTokens"),
                normalized.get("sortOrder"),
                normalized.get("remark"),
                id
        );
        return sceneDetail(id);
    }

    @Transactional
    public void deleteScene(long id) {
        jdbcTemplate.update("UPDATE ai_scene_sell_config SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
    }

    public PageResult<Map<String, Object>> pageBenefits(int current, int size, String keyword, String planCode) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (scene_key LIKE ? OR remark LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw);
            args.add(kw);
        }
        if (StringUtils.hasText(planCode)) {
            where.append(" AND plan_code=?");
            args.add(normalizePlanCode(planCode));
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_scene_plan_benefit" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id, tenant_id AS tenantId, scene_key AS sceneKey, plan_code AS planCode, enabled, free_quota_daily AS freeQuotaDaily, free_quota_monthly AS freeQuotaMonthly, " +
                        "discount_rate AS discountRate, override_charge_mode AS overrideChargeMode, override_tokens_per_call AS overrideTokensPerCall, " +
                        "override_tokens_per_item AS overrideTokensPerItem, override_tokens_per_image AS overrideTokensPerImage, override_tokens_per_reply AS overrideTokensPerReply, " +
                        "override_base_tokens AS overrideBaseTokens, override_step_size AS overrideStepSize, override_step_tokens AS overrideStepTokens, " +
                        "daily_cap_count AS dailyCapCount, daily_cap_tokens AS dailyCapTokens, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM ai_scene_plan_benefit" + where + " ORDER BY scene_key ASC, plan_code ASC, id DESC LIMIT ? OFFSET ?",
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("tenantId", rs.getObject("tenantId"));
                    row.put("sceneKey", rs.getString("sceneKey"));
                    row.put("planCode", normalizePlanCode(rs.getString("planCode")));
                    row.put("enabled", rs.getInt("enabled"));
                    row.put("freeQuotaDaily", rs.getInt("freeQuotaDaily"));
                    row.put("freeQuotaMonthly", rs.getInt("freeQuotaMonthly"));
                    row.put("discountRate", rs.getBigDecimal("discountRate"));
                    row.put("overrideChargeMode", rs.getString("overrideChargeMode"));
                    row.put("overrideTokensPerCall", rs.getLong("overrideTokensPerCall"));
                    row.put("overrideTokensPerItem", rs.getLong("overrideTokensPerItem"));
                    row.put("overrideTokensPerImage", rs.getLong("overrideTokensPerImage"));
                    row.put("overrideTokensPerReply", rs.getLong("overrideTokensPerReply"));
                    row.put("overrideBaseTokens", rs.getLong("overrideBaseTokens"));
                    row.put("overrideStepSize", rs.getInt("overrideStepSize"));
                    row.put("overrideStepTokens", rs.getLong("overrideStepTokens"));
                    row.put("dailyCapCount", rs.getInt("dailyCapCount"));
                    row.put("dailyCapTokens", rs.getLong("dailyCapTokens"));
                    row.put("remark", rs.getString("remark"));
                    row.put("createdTime", rs.getTimestamp("createdTime"));
                    row.put("updatedTime", rs.getTimestamp("updatedTime"));
                    return row;
                },
                pageArgs.toArray()
        );
        rows.forEach(this::decorateBenefitRow);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> benefitDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, scene_key AS sceneKey, plan_code AS planCode, enabled, free_quota_daily AS freeQuotaDaily, free_quota_monthly AS freeQuotaMonthly, " +
                        "discount_rate AS discountRate, override_charge_mode AS overrideChargeMode, override_tokens_per_call AS overrideTokensPerCall, " +
                        "override_tokens_per_item AS overrideTokensPerItem, override_tokens_per_image AS overrideTokensPerImage, override_tokens_per_reply AS overrideTokensPerReply, " +
                        "override_base_tokens AS overrideBaseTokens, override_step_size AS overrideStepSize, override_step_tokens AS overrideStepTokens, " +
                        "daily_cap_count AS dailyCapCount, daily_cap_tokens AS dailyCapTokens, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM ai_scene_plan_benefit WHERE id=? AND deleted=0",
                id
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "会员权益配置不存在");
        }
        Map<String, Object> row = rows.get(0);
        decorateBenefitRow(row);
        return row;
    }

    @Transactional
    public Map<String, Object> createBenefit(Map<String, Object> data) {
        Map<String, Object> normalized = normalizeBenefitPayload(data, null);
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_scene_plan_benefit WHERE tenant_id <=> ? AND scene_key=? AND plan_code=? AND deleted=0",
                Long.class,
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("planCode")
        );
        if (exists != null && exists > 0) {
            throw new BizException(400, "会员权益已存在");
        }
        jdbcTemplate.update(
                "INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, free_quota_monthly, discount_rate, override_charge_mode, override_tokens_per_call, " +
                        "override_tokens_per_item, override_tokens_per_image, override_tokens_per_reply, override_base_tokens, override_step_size, override_step_tokens, daily_cap_count, daily_cap_tokens, remark, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("planCode"),
                normalized.get("enabled"),
                normalized.get("freeQuotaDaily"),
                normalized.get("freeQuotaMonthly"),
                normalized.get("discountRate"),
                normalized.get("overrideChargeMode"),
                normalized.get("overrideTokensPerCall"),
                normalized.get("overrideTokensPerItem"),
                normalized.get("overrideTokensPerImage"),
                normalized.get("overrideTokensPerReply"),
                normalized.get("overrideBaseTokens"),
                normalized.get("overrideStepSize"),
                normalized.get("overrideStepTokens"),
                normalized.get("dailyCapCount"),
                normalized.get("dailyCapTokens"),
                normalized.get("remark")
        );
        Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        return benefitDetail(newId == null ? 0 : newId);
    }

    @Transactional
    public Map<String, Object> updateBenefit(long id, Map<String, Object> data) {
        Map<String, Object> old = benefitDetail(id);
        Map<String, Object> normalized = normalizeBenefitPayload(data, old);
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_scene_plan_benefit WHERE tenant_id <=> ? AND scene_key=? AND plan_code=? AND id<>? AND deleted=0",
                Long.class,
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("planCode"),
                id
        );
        if (exists != null && exists > 0) {
            throw new BizException(400, "会员权益已存在");
        }
        jdbcTemplate.update(
                "UPDATE ai_scene_plan_benefit SET tenant_id=?, scene_key=?, plan_code=?, enabled=?, free_quota_daily=?, free_quota_monthly=?, discount_rate=?, override_charge_mode=?, override_tokens_per_call=?, " +
                        "override_tokens_per_item=?, override_tokens_per_image=?, override_tokens_per_reply=?, override_base_tokens=?, override_step_size=?, override_step_tokens=?, daily_cap_count=?, daily_cap_tokens=?, remark=?, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0",
                parseNullableLong(normalized.get("tenantId")),
                normalized.get("sceneKey"),
                normalized.get("planCode"),
                normalized.get("enabled"),
                normalized.get("freeQuotaDaily"),
                normalized.get("freeQuotaMonthly"),
                normalized.get("discountRate"),
                normalized.get("overrideChargeMode"),
                normalized.get("overrideTokensPerCall"),
                normalized.get("overrideTokensPerItem"),
                normalized.get("overrideTokensPerImage"),
                normalized.get("overrideTokensPerReply"),
                normalized.get("overrideBaseTokens"),
                normalized.get("overrideStepSize"),
                normalized.get("overrideStepTokens"),
                normalized.get("dailyCapCount"),
                normalized.get("dailyCapTokens"),
                normalized.get("remark"),
                id
        );
        return benefitDetail(id);
    }

    @Transactional
    public void deleteBenefit(long id) {
        jdbcTemplate.update("UPDATE ai_scene_plan_benefit SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
    }

    private void decorateSceneRow(Map<String, Object> row) {
        row.put("enabledText", number(row.get("enabled")) == 1 ? "启用" : "禁用");
        row.put("chargeModeText", text(row.get("chargeMode")));
        row.put("pricePreview", switch (text(row.get("chargeMode"))) {
            case "member_quota_then_fixed" -> number(row.get("sellTokensPerReply")) + " Token/条";
            case "fixed_per_image" -> number(row.get("sellTokensPerImage")) + " Token/张";
            case "per_item_step" -> number(row.get("baseTokens")) + " + 阶梯";
            case "cost_plus_rate" -> "成本加成";
            case "free" -> "免费";
            default -> number(row.get("sellTokensPerCall")) + " Token/次";
        });
    }

    private void decorateBenefitRow(Map<String, Object> row) {
        row.put("planCode", normalizePlanCode(row.get("planCode")));
        row.put("enabledText", number(row.get("enabled")) == 1 ? "启用" : "禁用");
    }

    private Map<String, Object> normalizeScenePayload(Map<String, Object> data, Map<String, Object> defaults) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("tenantId", firstPresent(data, defaults, "tenantId", "tenant_id"));
        row.put("sceneKey", normalizeSceneKey(requiredText(firstPresent(data, defaults, "sceneKey", "scene_key"), "场景键不能为空")));
        row.put("sceneName", cleanText(requiredText(firstPresent(data, defaults, "sceneName", "scene_name"), "场景名称不能为空")));
        row.put("sceneGroup", cleanText(textOrDefault(firstPresent(data, defaults, "sceneGroup", "scene_group"), "other")));
        row.put("chargeMode", normalizeChargeMode(requiredText(firstPresent(data, defaults, "chargeMode", "charge_mode"), "收费模式不能为空")));
        row.put("priceUnit", cleanText(textOrDefault(firstPresent(data, defaults, "priceUnit", "price_unit"), "call")));
        row.put("enabled", parseBoolInt(firstPresent(data, defaults, "enabled"), 1));
        row.put("isMetered", parseBoolInt(firstPresent(data, defaults, "isMetered", "is_metered"), 1));
        row.put("showEstimate", parseBoolInt(firstPresent(data, defaults, "showEstimate", "show_estimate"), 1));
        row.put("allowTrial", parseBoolInt(firstPresent(data, defaults, "allowTrial", "allow_trial"), 0));
        row.put("trialQuota", numberOrDefault(firstPresent(data, defaults, "trialQuota", "trial_quota"), 0));
        row.put("baseTokens", numberOrDefault(firstPresent(data, defaults, "baseTokens", "base_tokens"), 0));
        row.put("stepSize", numberOrDefault(firstPresent(data, defaults, "stepSize", "step_size"), 0));
        row.put("stepTokens", numberOrDefault(firstPresent(data, defaults, "stepTokens", "step_tokens"), 0));
        row.put("sellTokensPerCall", numberOrDefault(firstPresent(data, defaults, "sellTokensPerCall", "sell_tokens_per_call"), 0));
        row.put("sellTokensPerItem", numberOrDefault(firstPresent(data, defaults, "sellTokensPerItem", "sell_tokens_per_item"), 0));
        row.put("sellTokensPerImage", numberOrDefault(firstPresent(data, defaults, "sellTokensPerImage", "sell_tokens_per_image"), 0));
        row.put("sellTokensPerReply", numberOrDefault(firstPresent(data, defaults, "sellTokensPerReply", "sell_tokens_per_reply"), 0));
        row.put("sellTokensPerFile", numberOrDefault(firstPresent(data, defaults, "sellTokensPerFile", "sell_tokens_per_file"), 0));
        row.put("sellTokensPer1kChars", numberOrDefault(firstPresent(data, defaults, "sellTokensPer1kChars", "sell_tokens_per_1k_chars"), 0));
        row.put("minTokens", numberOrDefault(firstPresent(data, defaults, "minTokens", "min_tokens"), 0));
        row.put("maxTokens", numberOrDefault(firstPresent(data, defaults, "maxTokens", "max_tokens"), 0));
        row.put("memberDiscountRate", decimalOrDefault(firstPresent(data, defaults, "memberDiscountRate", "member_discount_rate"), "1.0000"));
        row.put("costMarkupRate", decimalOrDefault(firstPresent(data, defaults, "costMarkupRate", "cost_markup_rate"), "1.0000"));
        row.put("fallbackExchangeRate", decimalOrDefault(firstPresent(data, defaults, "fallbackExchangeRate", "fallback_exchange_rate"), "160"));
        row.put("dailyCapCount", numberOrDefault(firstPresent(data, defaults, "dailyCapCount", "daily_cap_count"), 0));
        row.put("dailyCapTokens", numberOrDefault(firstPresent(data, defaults, "dailyCapTokens", "daily_cap_tokens"), 0));
        row.put("monthlyCapCount", numberOrDefault(firstPresent(data, defaults, "monthlyCapCount", "monthly_cap_count"), 0));
        row.put("monthlyCapTokens", numberOrDefault(firstPresent(data, defaults, "monthlyCapTokens", "monthly_cap_tokens"), 0));
        row.put("sortOrder", numberOrDefault(firstPresent(data, defaults, "sortOrder", "sort_order"), 100));
        row.put("remark", cleanText(textOrDefault(firstPresent(data, defaults, "remark"), "")));
        return row;
    }

    private Map<String, Object> normalizeBenefitPayload(Map<String, Object> data, Map<String, Object> defaults) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("tenantId", firstPresent(data, defaults, "tenantId", "tenant_id"));
        row.put("sceneKey", normalizeSceneKey(requiredText(firstPresent(data, defaults, "sceneKey", "scene_key"), "场景键不能为空")));
        row.put("planCode", normalizePlanCode(requiredText(firstPresent(data, defaults, "planCode", "plan_code"), "会员编码不能为空")));
        row.put("enabled", parseBoolInt(firstPresent(data, defaults, "enabled"), 1));
        row.put("freeQuotaDaily", numberOrDefault(firstPresent(data, defaults, "freeQuotaDaily", "free_quota_daily"), 0));
        row.put("freeQuotaMonthly", numberOrDefault(firstPresent(data, defaults, "freeQuotaMonthly", "free_quota_monthly"), 0));
        row.put("discountRate", decimalOrDefault(firstPresent(data, defaults, "discountRate", "discount_rate"), "1.0000"));
        row.put("overrideChargeMode", cleanText(textOrDefault(firstPresent(data, defaults, "overrideChargeMode", "override_charge_mode"), "")));
        row.put("overrideTokensPerCall", numberOrDefault(firstPresent(data, defaults, "overrideTokensPerCall", "override_tokens_per_call"), 0));
        row.put("overrideTokensPerItem", numberOrDefault(firstPresent(data, defaults, "overrideTokensPerItem", "override_tokens_per_item"), 0));
        row.put("overrideTokensPerImage", numberOrDefault(firstPresent(data, defaults, "overrideTokensPerImage", "override_tokens_per_image"), 0));
        row.put("overrideTokensPerReply", numberOrDefault(firstPresent(data, defaults, "overrideTokensPerReply", "override_tokens_per_reply"), 0));
        row.put("overrideBaseTokens", numberOrDefault(firstPresent(data, defaults, "overrideBaseTokens", "override_base_tokens"), 0));
        row.put("overrideStepSize", numberOrDefault(firstPresent(data, defaults, "overrideStepSize", "override_step_size"), 0));
        row.put("overrideStepTokens", numberOrDefault(firstPresent(data, defaults, "overrideStepTokens", "override_step_tokens"), 0));
        row.put("dailyCapCount", numberOrDefault(firstPresent(data, defaults, "dailyCapCount", "daily_cap_count"), 0));
        row.put("dailyCapTokens", numberOrDefault(firstPresent(data, defaults, "dailyCapTokens", "daily_cap_tokens"), 0));
        row.put("remark", cleanText(textOrDefault(firstPresent(data, defaults, "remark"), "")));
        return row;
    }

    private Object firstPresent(Map<String, Object> data, Map<String, Object> defaults, String... keys) {
        if (data != null) {
            for (String key : keys) {
                if (data.containsKey(key) && data.get(key) != null) return data.get(key);
            }
        }
        if (defaults != null) {
            for (String key : keys) {
                if (defaults.containsKey(key) && defaults.get(key) != null) return defaults.get(key);
            }
        }
        return null;
    }

    private String requiredText(Object value, String message) {
        String text = cleanText(value == null ? "" : String.valueOf(value));
        if (!StringUtils.hasText(text)) {
            throw new BizException(400, message);
        }
        return text;
    }

    private String textOrDefault(Object value, String def) {
        String text = cleanText(value == null ? "" : String.valueOf(value));
        return text.isBlank() ? def : text;
    }

    private String cleanText(String value) {
        return value == null ? "" : value.trim();
    }

    private String normalizeSceneKey(String sceneKey) {
        return cleanText(sceneKey).toLowerCase(Locale.ROOT);
    }

    private String normalizeChargeMode(String chargeMode) {
        return cleanText(chargeMode).toLowerCase(Locale.ROOT);
    }

    private String normalizePlanCode(Object planCode) {
        String code = cleanText(planCode == null ? "" : String.valueOf(planCode)).toLowerCase(Locale.ROOT);
        if (!StringUtils.hasText(code)) return "normal";
        return "svip".equals(code) ? "svp" : code;
    }

    private int parseBoolInt(Object value, int def) {
        if (value == null || String.valueOf(value).isBlank()) return def;
        if (value instanceof Boolean b) return b ? 1 : 0;
        if (value instanceof Number n) return n.intValue() == 0 ? 0 : 1;
        String text = String.valueOf(value).trim();
        if ("true".equalsIgnoreCase(text) || "1".equals(text) || "启用".equals(text)) return 1;
        if ("false".equalsIgnoreCase(text) || "0".equals(text) || "禁用".equals(text)) return 0;
        return def;
    }

    private long numberOrDefault(Object value, long def) {
        if (value == null || String.valueOf(value).isBlank()) return def;
        if (value instanceof Number n) return n.longValue();
        try {
            return new BigDecimal(String.valueOf(value).trim()).setScale(0, RoundingMode.DOWN).longValue();
        } catch (Exception e) {
            return def;
        }
    }

    private BigDecimal decimalOrDefault(Object value, String def) {
        String text = value == null || String.valueOf(value).isBlank() ? def : String.valueOf(value).trim();
        try {
            return new BigDecimal(text);
        } catch (Exception e) {
            return new BigDecimal(def);
        }
    }

    private Long parseNullableLong(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        try {
            return new BigDecimal(String.valueOf(value).trim()).longValue();
        } catch (Exception e) {
            return null;
        }
    }

    private long number(Object value) {
        return numberOrDefault(value, 0);
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    public int batchDeleteScenes(List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        String placeholders = ids.stream().map(v -> "?").collect(Collectors.joining(","));
        return jdbcTemplate.update("UPDATE ai_scene_sell_config SET deleted=1, updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")", ids.toArray());
    }

    public int batchDeleteBenefits(List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        String placeholders = ids.stream().map(v -> "?").collect(Collectors.joining(","));
        return jdbcTemplate.update("UPDATE ai_scene_plan_benefit SET deleted=1, updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")", ids.toArray());
    }
}
