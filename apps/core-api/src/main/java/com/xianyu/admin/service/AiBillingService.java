package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

/**
 * AI Token 精准计费服务。
 *
 * Java 端负责价格配置、余额校验、余额扣减、调用日志和余额流水；
 * Python 自动化端负责执行 AI/爬虫/自动化动作，并把实际 usage 回传到 Java 扣费。
 */
@Service
public class AiBillingService {
    private static final Logger log = LoggerFactory.getLogger(AiBillingService.class);
    private static final BigDecimal ONE_HUNDRED = BigDecimal.valueOf(100);
    private static final BigDecimal ONE_THOUSAND = BigDecimal.valueOf(1000);
    private static final BigDecimal DEFAULT_TOKEN_EXCHANGE_RATE = BigDecimal.valueOf(100); // 1 元 = 100 平台 Token

    private final JdbcTemplate jdbcTemplate;
    private final UserProfileService userProfileService;
    private final AiScenePricingService aiScenePricingService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AiBillingService(JdbcTemplate jdbcTemplate,
                            UserProfileService userProfileService,
                            AiScenePricingService aiScenePricingService) {
        this.jdbcTemplate = jdbcTemplate;
        this.userProfileService = userProfileService;
        this.aiScenePricingService = aiScenePricingService;
    }

    public PageResult<Map<String, Object>> pageModelPrices(int current, int size, String keyword, String modelType, String enabled) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (provider_name LIKE ? OR model_name LIKE ? OR module_key LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(modelType)) {
            where.append(" AND model_type=?");
            args.add(modelType.trim());
        }
        Integer enabledValue = parseEnabled(enabled);
        if (enabledValue != null) {
            where.append(" AND enabled=?");
            args.add(enabledValue);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_model_price_config" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, module_key AS moduleKey, provider_name AS providerName, model_name AS modelName, " +
                        "model_type AS modelType, billing_mode AS billingMode, input_price_per_1k AS inputPricePer1k, " +
                        "output_price_per_1k AS outputPricePer1k, cached_input_price_per_1k AS cachedInputPricePer1k, " +
                        "per_call_price AS perCallPrice, spec_price_json AS specPriceJson, " +
                        "token_exchange_rate AS tokenExchangeRate, min_charge_token AS minChargeToken, " +
                        "billing_unit AS billingUnit, cost_per_image AS costPerImage, tokens_per_image AS tokensPerImage, " +
                        "cost_per_call AS costPerCall, tokens_per_call AS tokensPerCall, " +
                        "enabled, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM ai_model_price_config" + where + " ORDER BY enabled DESC, id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        rows.forEach(this::decoratePriceRow);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    @Transactional
    public Map<String, Object> saveModelPrice(Map<String, Object> data) {
        Object id = data.get("id");
        String moduleKey = text(first(data, "moduleKey", "module_key"));
        String providerName = defaultText(first(data, "providerName", "provider_name"), "default");
        String modelName = defaultText(first(data, "modelName", "defaultModel", "model_name"), "default");
        String modelType = normalizeModelType(defaultText(first(data, "modelType", "model_type"), inferModelType(moduleKey)));
        String billingMode = normalizeBillingModeInput(first(data, "billingMode", "billing_mode"));
        // 提前解析 enabled：模型被禁用时不强制校验规格/价格配置，允许保存禁用状态的配置以便后续重新启用
        Object enabledRaw = first(data, "enabled");
        Integer enabledValue = parseEnabled(enabledRaw);
        if (enabledRaw != null && !String.valueOf(enabledRaw).isBlank() && enabledValue == null) {
            throw new BizException(400, "enabled 仅支持 true/false 或 1/0");
        }
        int enabled = enabledValue == null ? 1 : enabledValue;
        BigDecimal inputPrice = nonNegativeMoney(first(data, "inputPricePer1k", "input_price_per_1k"), "输入单价");
        BigDecimal outputPrice = nonNegativeMoney(first(data, "outputPricePer1k", "output_price_per_1k"), "输出单价");
        BigDecimal cachedInputPrice = nonNegativeMoney(first(data, "cachedInputPricePer1k", "cached_input_price_per_1k"), "缓存输入单价");
        BigDecimal perCallPrice = nonNegativeMoney(first(data, "perCallPrice", "per_call_price"), "单次调用价格");
        String specPriceJson = text(first(data, "specPriceJson", "spec_price_json"));
        // 仅在模型启用时校验规格价格；禁用模型允许清空价格后保存
        if (enabled == 1) {
            validateSpecPriceJson(specPriceJson);
            if ("spec".equals(billingMode) && !StringUtils.hasText(specPriceJson)) {
                throw new BizException(400, "按规格计费时必须配置规格价格");
            }
        }
        BigDecimal exchangeRate = nonNegativeMoney(first(data, "tokenExchangeRate", "token_exchange_rate"), "Token 兑换比例");
        if (exchangeRate.compareTo(BigDecimal.ZERO) <= 0) exchangeRate = DEFAULT_TOKEN_EXCHANGE_RATE;
        long minChargeToken = nonNegativeLong(first(data, "minChargeToken", "min_charge_token"), "最低扣费 Token");
        String remark = text(first(data, "remark"));
        // 计费单位、每张图片成本、每张图片销售 Token。
        String billingUnit = normalizeBillingUnitInput(first(data, "billingUnit", "billing_unit"));
        BigDecimal costPerImage = nonNegativeMoney(first(data, "cost", "costPerImage", "cost_per_image"), "每张图片成本");
        long tokensPerImage = nonNegativeLong(first(data, "tokensPerImage", "tokens_per_image"), "每张图片 Token");
        // chat 模型每次调用成本（元）与每次固定销售 Token 数。
        BigDecimal costPerCall = nonNegativeMoney(first(data, "costPerCall", "cost_per_call"), "每次调用成本");
        long tokensPerCall = nonNegativeLong(first(data, "tokensPerCall", "tokens_per_call"), "每次调用 Token");

        if (!StringUtils.hasText(moduleKey)) moduleKey = modelTypeToModuleKey(modelType);
        if (!StringUtils.hasText(modelName)) throw new BizException(400, "模型名称不能为空");

        if (id == null || String.valueOf(id).isBlank()) {
            int inserted = jdbcTemplate.update("INSERT INTO ai_model_price_config(tenant_id, module_key, provider_name, model_name, model_type, billing_mode, input_price_per_1k, output_price_per_1k, cached_input_price_per_1k, per_call_price, spec_price_json, token_exchange_rate, min_charge_token, billing_unit, cost_per_image, tokens_per_image, cost_per_call, tokens_per_call, enabled, remark, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    null, moduleKey, providerName, modelName, modelType, billingMode, inputPrice, outputPrice, cachedInputPrice, perCallPrice, specPriceJson, exchangeRate, minChargeToken, billingUnit, costPerImage, tokensPerImage, costPerCall, tokensPerCall, enabled, remark);
            if (inserted != 1) throw new BizException(503, "模型价格配置写入失败");
            Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (newId == null) throw new BizException(503, "模型价格配置编号无法确认");
            return modelPriceDetail(newId);
        }
        long priceId;
        try {
            priceId = Long.parseLong(String.valueOf(id));
        } catch (NumberFormatException e) {
            throw new BizException(400, "价格配置 ID 非法");
        }
        int updated = jdbcTemplate.update("UPDATE ai_model_price_config SET module_key=?, provider_name=?, model_name=?, model_type=?, billing_mode=?, input_price_per_1k=?, output_price_per_1k=?, cached_input_price_per_1k=?, per_call_price=?, spec_price_json=?, token_exchange_rate=?, min_charge_token=?, billing_unit=?, cost_per_image=?, tokens_per_image=?, cost_per_call=?, tokens_per_call=?, enabled=?, remark=?, updated_time=NOW() WHERE id=? AND deleted=0",
                moduleKey, providerName, modelName, modelType, billingMode, inputPrice, outputPrice, cachedInputPrice, perCallPrice, specPriceJson, exchangeRate, minChargeToken, billingUnit, costPerImage, tokensPerImage, costPerCall, tokensPerCall, enabled, remark, priceId);
        if (updated != 1) throw new BizException(404, "模型价格配置不存在或已删除");
        return modelPriceDetail(priceId);
    }

    public Map<String, Object> modelPriceDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, module_key AS moduleKey, provider_name AS providerName, model_name AS modelName, model_type AS modelType, billing_mode AS billingMode, input_price_per_1k AS inputPricePer1k, output_price_per_1k AS outputPricePer1k, cached_input_price_per_1k AS cachedInputPricePer1k, per_call_price AS perCallPrice, spec_price_json AS specPriceJson, token_exchange_rate AS tokenExchangeRate, min_charge_token AS minChargeToken, billing_unit AS billingUnit, cost_per_image AS costPerImage, tokens_per_image AS tokensPerImage, cost_per_call AS costPerCall, tokens_per_call AS tokensPerCall, enabled, remark, created_time AS createdTime, updated_time AS updatedTime FROM ai_model_price_config WHERE id=? AND deleted=0", id);
        if (rows.isEmpty()) throw new BizException(404, "模型价格配置不存在");
        Map<String, Object> row = rows.get(0);
        decoratePriceRow(row);
        return row;
    }

    @Transactional
    public void deleteModelPrice(long id) {
        int updated = jdbcTemplate.update("UPDATE ai_model_price_config SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
        if (updated != 1) throw new BizException(404, "模型价格配置不存在或已删除");
    }

    public PageResult<Map<String, Object>> pageUsageLogs(int current, int size, String keyword, String scene, String status) {
        return pageUsageLogs(current, size, keyword, scene, status, null);
    }

    public PageResult<Map<String, Object>> pageUsageLogs(int current, int size, String keyword, String scene, String status, Long userId) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE l.deleted=0");
        if (userId != null) {
            where.append(" AND l.user_id=?");
            args.add(userId);
        }
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (l.provider_name LIKE ? OR l.model_name LIKE ? OR u.username LIKE ? OR l.request_id LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(scene)) {
            where.append(" AND l.scene=?");
            args.add(scene.trim());
        }
        Integer statusValue = parseStatus(status);
        if (statusValue != null) {
            where.append(" AND l.status=?");
            args.add(statusValue);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT l.id, l.tenant_id AS tenantId, l.user_id AS userId, u.username, l.scene, l.provider_name AS providerName, l.model_name AS modelName, l.model_type AS modelType, " +
                        "l.request_id AS requestId, l.prompt_tokens AS promptTokens, l.completion_tokens AS completionTokens, l.total_tokens AS totalTokens, l.cached_tokens AS cachedTokens, l.image_count AS imageCount, " +
                        "l.spec_key AS specKey, l.cost_cent AS costCent, ROUND(l.cost_cent/100,4) AS costYuan, l.charge_tokens AS chargeTokens, l.balance_before AS balanceBefore, l.balance_after AS balanceAfter, " +
                        "l.status, l.error_message AS errorMessage, l.created_time AS createdTime " +
                        "FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where + " ORDER BY l.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        rows.forEach(this::decorateUsageRow);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public PageResult<Map<String, Object>> pageLedger(int current, int size, String keyword, String changeType) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (u.username LIKE ? OR l.ref_no LIKE ? OR l.remark LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(changeType)) {
            where.append(" AND l.change_type=?");
            args.add(changeType.trim());
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_balance_ledger l LEFT JOIN sys_user u ON u.id=l.user_id" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT l.id, l.tenant_id AS tenantId, l.user_id AS userId, u.username, l.change_type AS changeType, l.change_amount AS changeAmount, l.before_balance AS beforeBalance, l.after_balance AS afterBalance, l.ref_type AS refType, l.ref_id AS refId, l.ref_no AS refNo, l.remark, l.created_time AS createdTime " +
                        "FROM token_balance_ledger l LEFT JOIN sys_user u ON u.id=l.user_id" + where + " ORDER BY l.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        // 统一根据 changeType 覆盖 remark 文案，避免历史数据因数据库字符集问题出现乱码
        for (Map<String, Object> row : rows) {
            Object ct = row.get("changeType");
            String ctStr = ct == null ? "" : String.valueOf(ct);
            row.put("remark", remarkForLedger(ctStr, row.get("remark")));
        }
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 管理端：分页查询 Token 充值记录（token_recharge_record 表）。
     * 支持按 userId 严格过滤、关键词模糊匹配（用户名/订单号）、source 来源过滤。
     */
    public PageResult<Map<String, Object>> pageRechargeRecords(int current, int size, Long userId, String keyword, String source) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (userId != null) {
            where.append(" AND r.user_id=?");
            args.add(userId);
        }
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (u.username LIKE ? OR r.order_no LIKE ? OR r.remark LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(source)) {
            where.append(" AND r.source=?");
            args.add(source.trim());
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM token_recharge_record r LEFT JOIN sys_user u ON u.id=r.user_id" + where,
                Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT r.id, r.tenant_id AS tenantId, r.user_id AS userId, u.username, " +
                        "r.payment_order_id AS paymentOrderId, r.order_no AS orderNo, " +
                        "r.token_amount AS tokenAmount, r.before_balance AS beforeBalance, r.after_balance AS afterBalance, " +
                        "r.source, r.remark, r.created_time AS createdTime " +
                        "FROM token_recharge_record r LEFT JOIN sys_user u ON u.id=r.user_id" + where +
                        " ORDER BY r.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 管理端：充值记录汇总统计（用于顶部卡片）。
     * 若 userId 不为空，则只统计该用户。
     */
    public Map<String, Object> rechargeRecordsSummary(Long userId) {
        Map<String, Object> m = new LinkedHashMap<>();
        StringBuilder whereUser = new StringBuilder(" WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (userId != null) {
            whereUser.append(" AND user_id=?");
            args.add(userId);
        }
        m.put("totalRecords", optionalLong("SELECT COUNT(*) FROM token_recharge_record" + whereUser, args.toArray()));
        m.put("totalTokens", optionalLong("SELECT COALESCE(SUM(token_amount),0) FROM token_recharge_record" + whereUser, args.toArray()));
        m.put("todayRecords", optionalLong("SELECT COUNT(*) FROM token_recharge_record" + whereUser + " AND DATE(created_time)=CURRENT_DATE()", args.toArray()));
        m.put("todayTokens", optionalLong("SELECT COALESCE(SUM(token_amount),0) FROM token_recharge_record" + whereUser + " AND DATE(created_time)=CURRENT_DATE()", args.toArray()));
        m.put("monthTokens", optionalLong("SELECT COALESCE(SUM(token_amount),0) FROM token_recharge_record" + whereUser + " AND created_time >= DATE_FORMAT(CURDATE(), '%Y-%m-01')", args.toArray()));
        return m;
    }

    /**
     * 管理端：分页查询统一充值记录（会员充值 + Token 充值）。
     * 数据源：payment_order 表，order_type IN ('vip','token') AND status=1（已支付成功）。
     * 支持按 userId 严格过滤、关键词模糊匹配（用户名/订单号/套餐名）、orderType 过滤（vip/token）。
     */
    public PageResult<Map<String, Object>> pageUnifiedRechargeRecords(int current, int size, Long userId, String keyword, String orderType) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE o.deleted=0 AND o.status=1 AND o.order_type IN ('vip','token')");
        if (userId != null) {
            where.append(" AND o.user_id=?");
            args.add(userId);
        }
        String normalizedOrderType = normalizeUnifiedOrderType(orderType);
        if (normalizedOrderType != null) {
            where.append(" AND o.order_type=?");
            args.add(normalizedOrderType);
        }
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (u.username LIKE ? OR o.order_no LIKE ? OR o.title LIKE ? OR bp.plan_name LIKE ? OR trp.plan_name LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw); args.add(kw); args.add(kw);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM payment_order o LEFT JOIN sys_user u ON u.id=o.user_id " +
                        "LEFT JOIN billing_plan bp ON bp.id=o.plan_id LEFT JOIN token_recharge_plan trp ON trp.id=o.token_plan_id" + where,
                Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT o.id, o.tenant_id AS tenantId, o.user_id AS userId, u.username, o.order_no AS orderNo, o.order_type AS orderType, " +
                        "o.target_type AS targetType, o.target_id AS targetId, o.plan_id AS planId, o.token_plan_id AS tokenPlanId, o.title, " +
                        "o.amount_cent AS amountCent, ROUND(o.amount_cent/100,2) AS amountYuan, o.token_amount AS tokenAmount, " +
                        "o.payment_method AS paymentMethod, o.provider_type AS providerType, o.period_type AS periodType, o.status, " +
                        "o.paid_time AS paidTime, o.created_time AS createdTime, " +
                        "bp.plan_name AS vipPlanName, trp.plan_name AS tokenPlanName " +
                        "FROM payment_order o LEFT JOIN sys_user u ON u.id=o.user_id " +
                        "LEFT JOIN billing_plan bp ON bp.id=o.plan_id LEFT JOIN token_recharge_plan trp ON trp.id=o.token_plan_id" + where +
                        " ORDER BY o.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        for (Map<String, Object> row : rows) {
            decorateUnifiedRecord(row);
        }
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 管理端：统一充值记录汇总（今日收入 + 累计统计，含会员充值与 Token 充值）。
     * 今日收入基于 paid_time（实际支付时间）统计，仅统计 status=1（已支付成功）的订单。
     * 若 userId 不为空，则只统计该用户。
     */
    public Map<String, Object> unifiedRechargeSummary(Long userId) {
        Map<String, Object> m = new LinkedHashMap<>();
        StringBuilder whereUser = new StringBuilder(" WHERE deleted=0 AND status=1 AND order_type IN ('vip','token')");
        List<Object> args = new ArrayList<>();
        if (userId != null) {
            whereUser.append(" AND user_id=?");
            args.add(userId);
        }
        Object[] allArgs = args.toArray();
        // 今日收入模块（基于 paid_time）
        String todayWhere = whereUser + " AND DATE(paid_time)=CURRENT_DATE()";
        Map<String, Object> todayRevenue = new LinkedHashMap<>();
        todayRevenue.put("totalCount", optionalLong("SELECT COUNT(*) FROM payment_order" + todayWhere, allArgs));
        todayRevenue.put("totalAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + todayWhere, allArgs));
        todayRevenue.put("vipCount", optionalLong("SELECT COUNT(*) FROM payment_order" + todayWhere + " AND order_type='vip'", allArgs));
        todayRevenue.put("vipAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + todayWhere + " AND order_type='vip'", allArgs));
        todayRevenue.put("tokenCount", optionalLong("SELECT COUNT(*) FROM payment_order" + todayWhere + " AND order_type='token'", allArgs));
        todayRevenue.put("tokenAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + todayWhere + " AND order_type='token'", allArgs));
        m.put("todayRevenue", todayRevenue);
        // 累计统计
        Map<String, Object> cumulative = new LinkedHashMap<>();
        cumulative.put("totalRecords", optionalLong("SELECT COUNT(*) FROM payment_order" + whereUser, allArgs));
        cumulative.put("totalAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + whereUser, allArgs));
        cumulative.put("vipTotalRecords", optionalLong("SELECT COUNT(*) FROM payment_order" + whereUser + " AND order_type='vip'", allArgs));
        cumulative.put("vipTotalAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + whereUser + " AND order_type='vip'", allArgs));
        cumulative.put("tokenTotalRecords", optionalLong("SELECT COUNT(*) FROM payment_order" + whereUser + " AND order_type='token'", allArgs));
        cumulative.put("tokenTotalAmountCent", optionalLong("SELECT COALESCE(SUM(amount_cent),0) FROM payment_order" + whereUser + " AND order_type='token'", allArgs));
        cumulative.put("tokenTotalTokens", optionalLong("SELECT COALESCE(SUM(token_amount),0) FROM payment_order" + whereUser + " AND order_type='token'", allArgs));
        m.put("cumulative", cumulative);
        return m;
    }

    /**
     * 装饰统一充值记录行：统一字段名、补充文案。
     */
    private void decorateUnifiedRecord(Map<String, Object> row) {
        String ot = text(row.get("orderType"));
        String planName = "vip".equals(ot) ? text(row.get("vipPlanName")) : text(row.get("tokenPlanName"));
        row.put("planName", planName);
        row.put("recordType", ot);
        row.put("recordTypeText", "vip".equals(ot) ? "会员充值" : "Token 充值");
        String pt = text(row.get("periodType"));
        row.put("periodText", pt.isEmpty() ? "" : switch (pt) {
            case "month" -> "月付";
            case "quarter" -> "季付";
            case "year" -> "年付";
            default -> pt;
        });
        String pm = text(row.get("paymentMethod"));
        row.put("paymentMethodText", switch (pm) {
            case "wechat" -> "微信支付";
            case "alipay" -> "支付宝";
            default -> pm.isEmpty() ? "—" : pm;
        });
        String tt = text(row.get("targetType"));
        row.put("targetTypeText", "xianyu_account".equals(tt) ? "闲鱼账号" : "用户账号");
    }

    /**
     * 归一化统一充值记录的 orderType 过滤值。
     * 返回 null 表示不过滤（展示全部会员+Token）。
     */
    private String normalizeUnifiedOrderType(String type) {
        if (type == null) return null;
        String t = type.trim().toLowerCase(Locale.ROOT);
        if (t.isEmpty()) return null;
        if ("vip".equals(t) || "member".equals(t)) return "vip";
        if ("token".equals(t) || "tokens".equals(t)) return "token";
        return null;
    }

    public Map<String, Object> summary() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("todayChargeTokens", optionalLong("SELECT COALESCE(SUM(charge_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayCostCent", optionalLong("SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayCachedTokens", optionalLong("SELECT COALESCE(SUM(cached_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("totalCachedTokens", optionalLong("SELECT COALESCE(SUM(cached_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
        m.put("enabledModels", optionalLong("SELECT COUNT(*) FROM ai_model_price_config WHERE deleted=0 AND enabled=1"));
        m.put("lowBalanceUsers", optionalLong("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND COALESCE(token_balance,0) < 100"));
        return m;
    }

    public Map<String, Object> balance() {
        Long userId = UserContext.userId();
        if (userId == null) throw new BizException(401, "请先登录");
        return balance(userId);
    }

    public Map<String, Object> balance(Long userId) {
        Map<String, Object> user = queryOne("SELECT id, username, token_balance FROM sys_user WHERE id=? AND deleted=0", userId);
        if (user == null) throw new BizException(404, "用户不存在");
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("userId", user.get("id"));
        res.put("username", user.get("username"));
        long tokenBalance = number(user.get("token_balance"));
        res.put("tokenBalance", tokenBalance);
        res.put("balance", tokenBalance); // 兼容旧前端字段
        // 附带通用模型（model-config-general）单次扣费信息，按当前用户 VIP 等级返回
        Map<String, Object> generalPricing = generalModelPerCallPricing(UserContext.getTenantId(), userId);
        res.putAll(generalPricing);
        return res;
    }

    /**
     * 计算通用模型（model-config-general）的单次扣费信息。
     *
     * 默认：perCallPrice=0.03 元、tokenExchangeRate=100、perCallTokens=3 Token。
     * 若后台未配置或配置为 0，使用默认值；若调用方 tenantId 为空（如内部 API），仅返回默认值。
     */
    public Map<String, Object> generalModelPerCallPricing(Long tenantId) {
        return generalModelPerCallPricing(tenantId, null);
    }

    /**
     * 计算通用模型（model-config-general）的单次扣费信息。
     * 若 userId 不为空，则按用户 VIP 等级查 ai_model_tier_price；
     * 否则按普通用户（vip_level=0）查询。
     */
    public Map<String, Object> generalModelPerCallPricing(Long tenantId, Long userId) {
        long perCallTokens = resolveTierTokensPerCall(userId);
        // 读取上游成本（仅供管理员查看盈亏，不影响扣费）
        BigDecimal costPerCall = BigDecimal.ZERO;
        try {
            if (tenantId != null) {
                Map<String, Object> price = jdbcTemplate.queryForList(
                        "SELECT cost_per_call FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND module_key='model-config-general' " +
                                "AND (tenant_id IS NULL OR tenant_id=?) ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                        tenantId).stream().findFirst().orElse(null);
                if (price != null) {
                    costPerCall = decimal(price.get("cost_per_call"));
                }
            }
        } catch (Exception e) {
            log.warn("查询通用模型上游成本失败: {}", e.getMessage());
        }
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("perCallPrice", new BigDecimal("0.03"));  // 保留字段以兼容旧前端读取
        res.put("tokenExchangeRate", DEFAULT_TOKEN_EXCHANGE_RATE);  // 保留字段以兼容旧前端读取
        res.put("perCallTokens", perCallTokens);
        res.put("costPerCall", costPerCall);
        res.put("moduleKey", "model-config-general");
        return res;
    }

    public Map<String, Object> estimateForCurrentUser(Map<String, Object> usage) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        usage.put("userId", userId);
        usage.put("tenantId", tenantId);
        return estimateUsage(usage, false);
    }

    public Map<String, Object> estimateScenePricingForCurrentUser(Map<String, Object> usage) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        usage.put("userId", userId);
        usage.put("tenantId", tenantId);

        Map<String, Object> cost = estimateUsage(usage, false);
        String scene = text(first(usage, "scene", "sceneKey", "scene_key"));
        String planCode = userProfileService.currentPlanCode(userId);
        long alreadyUsedToday = sceneUsageCountToday(userId, scene);
        Map<String, Object> usageSnapshot = mergeMaps(cost, usage);
        usageSnapshot.put("alreadyUsedToday", alreadyUsedToday);
        Map<String, Object> sell = aiScenePricingService.resolveScenePricing(tenantId, scene, planCode, usageSnapshot);
        long chargeTokens = resolveEffectiveChargeTokens(cost, sell);
        long rawSceneChargeTokens = number(sell.get("sellChargeTokens"));

        Map<String, Object> res = new LinkedHashMap<>(cost);
        res.put("sceneKey", scene);
        res.put("planCode", planCode);
        res.put("alreadyUsedToday", alreadyUsedToday);
        res.put("sellChargeTokens", chargeTokens);
        res.put("chargeTokens", chargeTokens);
        res.put("pricingReason", rawSceneChargeTokens > 0 || chargeTokens == 0
                ? sell.get("pricingReason")
                : "model_price_fallback");
        res.put("remainingFreeQuota", number(sell.get("remainingFreeQuota")));
        res.put("effectiveChargeMode", sell.get("effectiveChargeMode"));
        res.put("enoughForSellPrice", number(cost.get("balance")) >= chargeTokens);
        return res;
    }

    public Map<String, Object> precheck(Map<String, Object> usage) {
        Map<String, Object> estimate = estimateUsage(usage, false);
        Long userId = parseNullableLong(first(usage, "userId", "user_id"));
        Long tenantId = parseNullableLong(first(usage, "tenantId", "tenant_id"));
        if (userId == null) {
            return estimate;
        }
        String scene = text(first(usage, "scene", "sceneKey", "scene_key"));
        String planCode = userProfileService.currentPlanCode(userId);
        long alreadyUsedToday = sceneUsageCountToday(userId, scene);
        Map<String, Object> usageSnapshot = mergeMaps(estimate, usage);
        usageSnapshot.put("alreadyUsedToday", alreadyUsedToday);
        Map<String, Object> sell = aiScenePricingService.resolveScenePricing(tenantId, scene, planCode, usageSnapshot);
        long chargeTokens = resolveEffectiveChargeTokens(estimate, sell);
        long balance = number(estimate.get("balance"));
        if (balance < chargeTokens) throw new BizException(402, "Token 余额不足，请先充值");
        Map<String, Object> res = new LinkedHashMap<>(estimate);
        res.put("sceneKey", scene);
        res.put("planCode", planCode);
        res.put("alreadyUsedToday", alreadyUsedToday);
        res.put("sellChargeTokens", chargeTokens);
        res.put("chargeTokens", chargeTokens);
        res.put("pricingReason", sell.get("pricingReason"));
        res.put("remainingFreeQuota", number(sell.get("remainingFreeQuota")));
        res.put("effectiveChargeMode", sell.get("effectiveChargeMode"));
        res.put("enough", true);
        return res;
    }

    @Transactional
    public Map<String, Object> charge(Map<String, Object> usage) {
        Long userId = parseNullableLong(first(usage, "userId", "user_id"));
        if (userId == null || userId <= 0) throw new BizException(400, "userId 不能为空");
        Long tenantId = parseNullableLong(first(usage, "tenantId", "tenant_id"));
        if (tenantId == null || tenantId <= 0) throw new BizException(400, "tenantId 不能为空");
        Map<String, Object> estimate = estimateUsage(usage, false);
        String scene = text(first(usage, "scene", "sceneKey", "scene_key"));
        String planCode = userProfileService.currentPlanCode(userId);
        long alreadyUsedToday = sceneUsageCountToday(userId, scene);
        Map<String, Object> usageSnapshot = mergeMaps(estimate, usage);
        usageSnapshot.put("alreadyUsedToday", alreadyUsedToday);
        Map<String, Object> sell = aiScenePricingService.resolveScenePricing(tenantId, scene, planCode, usageSnapshot);
        long chargeTokens = resolveEffectiveChargeTokens(estimate, sell);
        long costCent = number(estimate.get("costCent"));
        Map<String, Object> user = queryOne(
                "SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0 FOR UPDATE",
                userId, tenantId);
        if (user == null) throw new BizException(404, "用户不存在");
        long before = number(user.get("token_balance"));
        String requestId = normalizeRequestId(first(usage, "requestId", "request_id"));
        Map<String, Object> exists = queryOne("SELECT id, tenant_id, user_id, status, charge_tokens, balance_after FROM ai_usage_log WHERE request_id=? AND deleted=0", requestId);
        if (exists != null) {
            if (number(exists.get("tenant_id")) != tenantId
                    || number(exists.get("user_id")) != userId) {
                throw new BizException(409, "请求编号已被其他调用占用");
            }
            if (number(exists.get("status")) != 1) {
                throw new BizException(409, "该请求此前执行失败，请使用新的请求编号重试");
            }
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("deducted", false);
            res.put("duplicate", true);
            res.put("requestId", requestId);
            res.put("chargeTokens", number(exists.get("charge_tokens")));
            res.put("balanceAfter", number(exists.get("balance_after")));
            return res;
        }
        if (before < chargeTokens) {
            insertUsageLog(tenantId, userId, usage, estimate, requestId, 0, before, before, "余额不足");
            throw new BizException(402, "Token 余额不足，请先充值");
        }
        long after = before - chargeTokens;
        int balanceUpdated = jdbcTemplate.update(
                "UPDATE sys_user SET token_balance=?, updated_time=NOW() WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                after, userId, tenantId);
        if (balanceUpdated != 1) throw new BizException(409, "用户余额状态已变化，请稍后重试");
        long usageLogId = insertUsageLog(tenantId, userId, usage, estimate, requestId, 1, before, after, null);
        int ledgerInserted = jdbcTemplate.update("INSERT INTO token_balance_ledger(tenant_id, user_id, change_type, change_amount, before_balance, after_balance, ref_type, ref_id, ref_no, remark, created_time) VALUES(?,?,?,?,?,?,?,?,?,?,NOW())",
                tenantId, userId, "ai_charge", -chargeTokens, before, after, "ai_usage", usageLogId, requestId, "AI 调用扣费");
        if (ledgerInserted != 1) throw new BizException(503, "AI 计费流水写入失败");
        Map<String, Object> res = new LinkedHashMap<>(estimate);
        res.put("sceneKey", scene);
        res.put("planCode", planCode);
        res.put("alreadyUsedToday", alreadyUsedToday);
        res.put("sellChargeTokens", chargeTokens);
        res.put("chargeTokens", chargeTokens);
        res.put("pricingReason", sell.get("pricingReason"));
        res.put("remainingFreeQuota", number(sell.get("remainingFreeQuota")));
        res.put("effectiveChargeMode", sell.get("effectiveChargeMode"));
        res.put("deducted", true);
        res.put("requestId", requestId);
        res.put("balanceBefore", before);
        res.put("balanceAfter", after);
        res.put("usageLogId", usageLogId);
        return res;
    }

    public Map<String, Object> estimateUsage(Map<String, Object> usage, boolean checkBalance) {
        Long userId = parseNullableLong(first(usage, "userId", "user_id"));
        Long tenantId = parseNullableLong(first(usage, "tenantId", "tenant_id"));
        String providerName = defaultText(first(usage, "providerName", "provider_name", "provider"), "default");
        String modelName = defaultText(first(usage, "modelName", "model_name", "model"), "default");
        String modelType = normalizeModelType(defaultText(first(usage, "modelType", "model_type"), "chat"));
        String billingMode = text(first(usage, "billingMode", "billing_mode"));
        long promptTokens = boundedUsageValue(first(usage, "promptTokens", "prompt_tokens", "inputTokens", "input_tokens"), "promptTokens", 1_000_000_000L, 0L);
        long completionTokens = boundedUsageValue(first(usage, "completionTokens", "completion_tokens", "outputTokens", "output_tokens"), "completionTokens", 1_000_000_000L, 0L);
        long measuredTotal;
        try {
            measuredTotal = Math.addExact(promptTokens, completionTokens);
        } catch (ArithmeticException e) {
            throw new BizException(400, "Token 使用量超出允许范围");
        }
        long reportedTotal = boundedUsageValue(first(usage, "totalTokens", "total_tokens"), "totalTokens", 2_000_000_000L, 0L);
        long totalTokens = Math.max(measuredTotal, reportedTotal);
        long cachedTokens = boundedUsageValue(first(usage, "cachedTokens", "cached_tokens", "cacheTokens", "cache_tokens"), "cachedTokens", 1_000_000_000L, 0L);
        // DeepSeek 在 prompt_tokens_details.cached_tokens 中返回缓存命中的输入 token，Python 端也可能直接传 cached_tokens。
        if (cachedTokens == 0) {
            cachedTokens = Math.max(0, extractCachedTokensFromRawUsage(first(usage, "rawUsage", "raw_usage")));
        }
        // 缓存命中数不能超过输入 token 总数。
        if (cachedTokens > promptTokens) cachedTokens = promptTokens;
        long nonCachedInputTokens = Math.max(0, promptTokens - cachedTokens);
        long imageCount = boundedUsageValue(first(usage, "imageCount", "image_count"), "imageCount", 1000L, 1L);
        String specKey = text(first(usage, "specKey", "spec_key", "imageSize", "image_size"));

        Map<String, Object> price = findPriceConfig(tenantId, providerName, modelName, modelType);
        if (!StringUtils.hasText(billingMode)) billingMode = defaultText(price.get("billing_mode"), "token");
        // 通用模型（model-config-general）强制按次计费：忽略调用方传入的 billingMode，统一按次扣费
        // 扣费 Token 数由 ai_model_tier_price 按用户 VIP 等级决定，不再走 perCallPrice × tokenExchangeRate 公式
        boolean isGeneralModel = "model-config-general".equals(price.get("module_key"));
        if (isGeneralModel) {
            billingMode = "per_call";
        }
        billingMode = normalizeBillingMode(billingMode);

        BigDecimal costYuan;
        BigDecimal cachedInputCostYuan = BigDecimal.ZERO;
        BigDecimal nonCachedInputCostYuan = BigDecimal.ZERO;
        BigDecimal outputCostYuan = BigDecimal.ZERO;
        // 计费单位决定 Token 换算费用的除数：1K=1000、1M=10^6、1T=10^12。
        BigDecimal unitDivisor = billingUnitDivisor(price.get("billing_unit"));
        if ("image".equals(modelType)) {
            // 生图模型优先使用 cost_per_image 计算成本，未配置时回退到 per_call_price / spec。
            BigDecimal costPerImage = decimal(price.get("cost_per_image"));
            BigDecimal perCall = decimal(price.get("per_call_price"));
            if ("spec".equals(billingMode) && StringUtils.hasText(specKey)) {
                BigDecimal specPrice = specPrice(price.get("spec_price_json"), specKey);
                if (specPrice.compareTo(BigDecimal.ZERO) > 0) perCall = specPrice;
            }
            BigDecimal effectivePerImage = costPerImage.compareTo(BigDecimal.ZERO) > 0 ? costPerImage : perCall;
            costYuan = effectivePerImage.multiply(BigDecimal.valueOf(imageCount));
        } else if ("per_call".equals(billingMode) || "spec".equals(billingMode)) {
            BigDecimal perCall = decimal(price.get("per_call_price"));
            // 通用模型按次价格未配置时默认 0.03 元/次（兑换比例 100 时扣 3 Token）
            if (perCall.compareTo(BigDecimal.ZERO) <= 0 && "model-config-general".equals(price.get("module_key"))) {
                perCall = new BigDecimal("0.03");
            }
            if ("spec".equals(billingMode) && StringUtils.hasText(specKey)) {
                BigDecimal specPrice = specPrice(price.get("spec_price_json"), specKey);
                if (specPrice.compareTo(BigDecimal.ZERO) > 0) perCall = specPrice;
            }
            costYuan = perCall.multiply(BigDecimal.valueOf(imageCount));
        } else {
            BigDecimal input = decimal(price.get("input_price_per_1k"));
            BigDecimal cachedInput = decimal(price.get("cached_input_price_per_1k"));
            BigDecimal output = decimal(price.get("output_price_per_1k"));
            BigDecimal perCall = decimal(price.get("per_call_price"));
            // 缓存命中输入优先使用 cachedInput 单价，未配置时退回 input 单价
            BigDecimal effectiveCachedInput = cachedInput.compareTo(BigDecimal.ZERO) > 0 ? cachedInput : input;
            cachedInputCostYuan = BigDecimal.valueOf(cachedTokens).divide(unitDivisor, 8, RoundingMode.HALF_UP).multiply(effectiveCachedInput);
            nonCachedInputCostYuan = BigDecimal.valueOf(nonCachedInputTokens).divide(unitDivisor, 8, RoundingMode.HALF_UP).multiply(input);
            outputCostYuan = BigDecimal.valueOf(completionTokens).divide(unitDivisor, 8, RoundingMode.HALF_UP).multiply(output);
            costYuan = cachedInputCostYuan.add(nonCachedInputCostYuan).add(outputCostYuan).add(perCall);
        }
        // chat 模型配置 cost_per_call（成本价）时，以它覆盖成本估算，与销售价分离。
        if ("chat".equals(modelType)) {
            BigDecimal costPerCallCfg = decimal(price.get("cost_per_call"));
            if (costPerCallCfg.compareTo(BigDecimal.ZERO) > 0) {
                // 成本按整次覆盖时，清空分项成本
                costYuan = costPerCallCfg.multiply(BigDecimal.valueOf(imageCount));
                cachedInputCostYuan = BigDecimal.ZERO;
                nonCachedInputCostYuan = BigDecimal.ZERO;
                outputCostYuan = BigDecimal.ZERO;
            }
        }
        if (costYuan.compareTo(BigDecimal.ZERO) < 0) costYuan = BigDecimal.ZERO;
        long costCent = costYuan.multiply(ONE_HUNDRED).setScale(0, RoundingMode.CEILING).longValue();
        BigDecimal exchangeRate = decimal(price.get("token_exchange_rate"));
        if (exchangeRate.compareTo(BigDecimal.ZERO) <= 0) exchangeRate = DEFAULT_TOKEN_EXCHANGE_RATE;
        long tokensPerImageCfg = number(price.get("tokens_per_image"));
        long tokensPerCallCfg = number(price.get("tokens_per_call"));
        long chargeTokens = 0;
        if (isGeneralModel) {
            // 通用模型：按用户 VIP 等级查 ai_model_tier_price，与 tokensPerCall/costYuan 解耦
            chargeTokens = resolveTierTokensPerCall(userId) * imageCount;
        } else if ("image".equals(modelType) && tokensPerImageCfg > 0) {
            // 生图模型按张直接扣减销售 Token，不依赖兑换比例。
            chargeTokens = tokensPerImageCfg * imageCount;
        } else if ("chat".equals(modelType) && tokensPerCallCfg > 0) {
            // chat 模型配置固定销售 Token 时，每次调用扣固定 Token，与成本独立。
            chargeTokens = tokensPerCallCfg * imageCount;
        } else {
            chargeTokens = costYuan.multiply(exchangeRate).setScale(0, RoundingMode.CEILING).longValue();
        }
        long minCharge = Math.max(0, number(price.get("min_charge_token")));
        // 固定销售价模式（image tokens_per_image / chat tokens_per_call）不受 min_charge_token 影响。
        boolean fixedPriceMode = ("image".equals(modelType) && tokensPerImageCfg > 0) || ("chat".equals(modelType) && tokensPerCallCfg > 0);
        if (!fixedPriceMode && costYuan.compareTo(BigDecimal.ZERO) > 0 && chargeTokens < Math.max(1, minCharge)) chargeTokens = Math.max(1, minCharge);

        long balance = 0;
        boolean enough = true;
        if (userId != null) {
            if (tenantId == null || tenantId <= 0) {
                throw new BizException(400, "tenantId 不能为空");
            }
            Map<String, Object> user = queryOne(
                    "SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                    userId, tenantId);
            if (user == null) throw new BizException(404, "用户不存在");
            balance = number(user.get("token_balance"));
            enough = balance >= chargeTokens;
        }
        if (checkBalance && !enough) throw new BizException(402, "Token 余额不足，请先充值");

        Map<String, Object> res = new LinkedHashMap<>();
        res.put("providerName", providerName);
        res.put("modelName", modelName);
        res.put("modelType", modelType);
        res.put("moduleKey", price.get("module_key"));
        res.put("billingMode", billingMode);
        res.put("promptTokens", promptTokens);
        res.put("completionTokens", completionTokens);
        res.put("totalTokens", totalTokens);
        res.put("cachedTokens", cachedTokens);
        res.put("nonCachedInputTokens", nonCachedInputTokens);
        res.put("imageCount", imageCount);
        res.put("specKey", specKey);
        res.put("cachedInputCostYuan", cachedInputCostYuan.setScale(6, RoundingMode.HALF_UP));
        res.put("nonCachedInputCostYuan", nonCachedInputCostYuan.setScale(6, RoundingMode.HALF_UP));
        res.put("outputCostYuan", outputCostYuan.setScale(6, RoundingMode.HALF_UP));
        res.put("costYuan", costYuan.setScale(6, RoundingMode.HALF_UP));
        res.put("costCent", costCent);
        res.put("chargeTokens", chargeTokens);
        res.put("tokenExchangeRate", exchangeRate);
        res.put("balance", balance);
        res.put("enough", enough);
        return res;
    }

    /**
     * 从原始 usage 中提取缓存命中的输入 token。
     * 兼容 DeepSeek / OpenAI 常见字段：
     * prompt_tokens_details.cached_tokens、prompt_cache_hit_tokens、cache_read_input_tokens。
     */
    @SuppressWarnings("unchecked")
    private long extractCachedTokensFromRawUsage(Object rawUsage) {
        if (rawUsage == null) return 0;
        try {
            Map<String, Object> usage;
            if (rawUsage instanceof Map) {
                usage = (Map<String, Object>) rawUsage;
            } else {
                String s = String.valueOf(rawUsage).trim();
                if (s.isEmpty() || !s.startsWith("{")) return 0;
                usage = objectMapper.readValue(s, new TypeReference<LinkedHashMap<String, Object>>() {});
            }
            for (String key : new String[]{"cached_tokens", "cache_tokens", "prompt_cache_hit_tokens", "cache_read_input_tokens"}) {
                Object v = usage.get(key);
                if (v != null) return Math.max(0, number(v));
            }
            Object details = usage.get("prompt_tokens_details");
            if (details instanceof Map) {
                Map<String, Object> d = (Map<String, Object>) details;
                for (String key : new String[]{"cached_tokens", "cache_tokens"}) {
                    Object v = d.get(key);
                    if (v != null) return Math.max(0, number(v));
                }
            }
            Object hit = usage.get("prompt_cache_hit_tokens");
            if (hit instanceof Number) return Math.max(0, number(hit));
        } catch (Exception ignored) {
            return 0;
        }
        return 0;
    }

    /**
     * 同步模型配置到 ai_model_price_config 表。
     *
     * 缓存：模型配置写入后，清空 modelConfig cache（供 ModelConfigService 读取使用）。
     * 注意：本方法可能被同类的 normalizeAndSyncAllModelConfigs 调用，self-invocation 下 @CacheEvict 不生效；
     * 调用方需通过 Spring 代理调用本方法（外部 Controller 调用是走代理的）。
     */
    @CacheEvict(value = "modelConfig", allEntries = true)
    public Map<String, Object> normalizeAndSyncModelConfig(String moduleKey, Map<String, Object> config) {
        if (!isModelConfigModule(moduleKey) || config == null) return config;
        try {
            Map<String, Object> data = new LinkedHashMap<>(config);
            data.put("moduleKey", moduleKey);
            data.putIfAbsent("modelType", inferModelType(moduleKey));
            data.putIfAbsent("providerName", first(data, "providerName", "provider_name"));
            data.putIfAbsent("modelName", first(data, "modelName", "defaultModel", "model_name"));
            if (first(data, "inputPricePer1k", "outputPricePer1k", "perCallPrice",
                    "costPerImage", "tokensPerImage", "costPerCall", "tokensPerCall") == null) return config;
            String provider = defaultText(first(data, "providerName", "provider_name"), "default");
            String model = defaultText(first(data, "modelName", "defaultModel", "model_name"), "default");
            String modelType = normalizeModelType(defaultText(first(data, "modelType", "model_type"), inferModelType(moduleKey)));
            // 通用模型强制按次计费：清零输入/输出/缓存命中单价，按次价格默认 0.03 元
            if ("model-config-general".equals(moduleKey)) {
                data.put("billingMode", "per_call");
                data.put("inputPricePer1k", BigDecimal.ZERO);
                data.put("outputPricePer1k", BigDecimal.ZERO);
                data.put("cachedInputPricePer1k", BigDecimal.ZERO);
                BigDecimal perCall = nonNegativeMoney(first(data, "perCallPrice", "per_call_price"), "单次调用价格");
                if (perCall.compareTo(BigDecimal.ZERO) <= 0) {
                    data.put("perCallPrice", new BigDecimal("0.03"));
                }
            }
            List<Map<String, Object>> exists = jdbcTemplate.queryForList("SELECT id FROM ai_model_price_config WHERE deleted=0 AND module_key=? AND provider_name=? AND model_name=? AND model_type=? ORDER BY id DESC LIMIT 1", moduleKey, provider, model, modelType);
            if (exists.isEmpty()) {
                saveModelPrice(data);
            } else {
                data.put("id", exists.get(0).get("id"));
                saveModelPrice(data);
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("同步 AI 模型计费配置失败, moduleKey={}, errorType={}", moduleKey, e.getClass().getSimpleName());
            throw new BizException(503, "AI 模型配置暂时无法同步到计费中心");
        }
        return config;
    }

    /**
     * 读取通用模型三档定价配置。
     * 若某档在表中不存在，使用默认值 3。
     *
     * 缓存：按 moduleKey 缓存到 tierConfig；saveTierConfig 后失效。
     */
    @Cacheable(value = "tierConfig", key = "#moduleKey", condition = "#moduleKey != null")
    public com.xianyu.admin.dto.TierPriceConfigDTO getTierConfig(String moduleKey) {
        if (!StringUtils.hasText(moduleKey)) moduleKey = "model-config-general";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT vip_level, tokens_per_call FROM ai_model_tier_price WHERE module_key=?",
                moduleKey);
        com.xianyu.admin.dto.TierPriceConfigDTO dto = new com.xianyu.admin.dto.TierPriceConfigDTO();
        dto.setModuleKey(moduleKey);
        dto.setNormal(3L);
        dto.setVip(3L);
        dto.setSvp(3L);
        for (Map<String, Object> row : rows) {
            Long tokens = number(row.get("tokens_per_call"));
            if (tokens <= 0) tokens = 3L;
            Integer level = null;
            Object levelObj = row.get("vip_level");
            if (levelObj instanceof Number n) level = n.intValue();
            else if (levelObj != null) {
                try { level = Integer.parseInt(String.valueOf(levelObj)); } catch (Exception ignored) {}
            }
            if (level == null) continue;
            switch (level) {
                case 0 -> dto.setNormal(tokens);
                case 1 -> dto.setVip(tokens);
                case 2 -> dto.setSvp(tokens);
            }
        }
        return dto;
    }

    /**
     * 保存通用模型三档定价配置。
     * 使用 UPSERT 语义：记录存在则更新，不存在则插入。
     *
     * 缓存：写入成功后清空整个 tierConfig cache（allEntries=true），
     * 因为可能影响多个 moduleKey 的聚合视图。
     */
    @Transactional
    @CacheEvict(value = "tierConfig", allEntries = true)
    public com.xianyu.admin.dto.TierPriceConfigDTO saveTierConfig(com.xianyu.admin.dto.TierPriceConfigDTO dto) {
        String moduleKey = StringUtils.hasText(dto.getModuleKey()) ? dto.getModuleKey() : "model-config-general";
        upsertTierPrice(moduleKey, 0, dto.getNormal());
        upsertTierPrice(moduleKey, 1, dto.getVip());
        upsertTierPrice(moduleKey, 2, dto.getSvp());
        return getTierConfig(moduleKey);
    }

    private void upsertTierPrice(String moduleKey, int vipLevel, Long tokens) {
        long tokensPerCall = (tokens == null || tokens <= 0) ? 3L : tokens;
        int updated = jdbcTemplate.update(
                "UPDATE ai_model_tier_price SET tokens_per_call=?, updated_time=NOW() " +
                        "WHERE module_key=? AND vip_level=?",
                tokensPerCall, moduleKey, vipLevel);
        if (updated == 0) {
            jdbcTemplate.update(
                    "INSERT INTO ai_model_tier_price(module_key, vip_level, tokens_per_call, created_time, updated_time) " +
                            "VALUES(?, ?, ?, NOW(), NOW())",
                    moduleKey, vipLevel, tokensPerCall);
        }
    }

    private Map<String, Object> findPriceConfig(Long tenantId, String providerName, String modelName, String modelType) {
        // 通用模型（model-config-general）按 module_key 显式标识，是平台前台 AI 功能的默认文本模型。
        // 对 chat 类型查询，应始终优先匹配通用模型记录（按次计费，默认 3 token/次），
        // 避免误匹配到 model-config-chat 等其他模型（导致走 token 计费或场景定价 20 token/次）。
        // 参见 .trae/rules/general-model-per-call-billing.md：通用模型必须按次计费，
        // 前台所有调用通用模型的行为（AI 客服测试、商机改写、工作流润色等）必须按通用模型按次价格扣费。
        boolean preferGeneral = "chat".equals(modelType);
        List<Object> args = new ArrayList<>();
        String sql = "SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND model_type=? AND (tenant_id IS NULL";
        args.add(modelType);
        if (tenantId != null) {
            sql += " OR tenant_id=?";
            args.add(tenantId);
        }
        sql += ") AND (";
        if (preferGeneral) {
            // chat 查询：通用模型（module_key=model-config-general）始终纳入候选，
            // 不受 provider_name/model_name 过滤限制，确保前台调用任意 chat 模型时都能命中通用模型按次计费
            sql += "module_key='model-config-general' OR ";
        }
        sql += "((model_name=? OR model_name='default') AND (provider_name=? OR provider_name='default'))) " +
                "ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, ";
        if (preferGeneral) {
            sql += "CASE WHEN module_key='model-config-general' THEN 0 ELSE 1 END, ";
        }
        sql += "CASE WHEN model_name=? THEN 0 ELSE 1 END, CASE WHEN provider_name=? THEN 0 ELSE 1 END, id DESC LIMIT 1";
        args.add(modelName); args.add(providerName); args.add(modelName); args.add(providerName);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args.toArray());
        if (!rows.isEmpty()) return rows.get(0);

        throw new BizException(503, "当前 AI 模型缺少有效计费配置，已停止调用以避免漏计费");
    }

    private long insertUsageLog(Long tenantId, Long userId, Map<String, Object> usage, Map<String, Object> estimate,
                                String requestId, int status, long before, long after, String errorMessage) {
        try {
            int inserted = jdbcTemplate.update("INSERT INTO ai_usage_log(tenant_id, user_id, scene, provider_name, model_name, model_type, request_id, prompt_tokens, completion_tokens, total_tokens, cached_tokens, image_count, spec_key, cost_cent, charge_tokens, balance_before, balance_after, status, error_message, raw_usage_json, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    tenantId, userId, text(first(usage, "scene")), estimate.get("providerName"), estimate.get("modelName"), estimate.get("modelType"), requestId,
                    estimate.get("promptTokens"), estimate.get("completionTokens"), estimate.get("totalTokens"), estimate.get("cachedTokens"),
                    estimate.get("imageCount"), estimate.get("specKey"),
                    estimate.get("costCent"), estimate.get("chargeTokens"), before, after, status, errorMessage,
                    objectMapper.writeValueAsString(usage));
            if (inserted != 1) throw new BizException(503, "AI 调用日志写入失败");
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("写入 AI 调用日志失败, requestId={}, errorType={}", requestId, e.getClass().getSimpleName());
            throw new BizException(503, "AI 调用日志暂时无法写入");
        }
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (id == null) throw new BizException(503, "AI 调用日志编号无法确认");
        return id;
    }

    private BigDecimal specPrice(Object json, String specKey) {
        String text = text(json);
        if (!StringUtils.hasText(text)) return BigDecimal.ZERO;
        try {
            Map<String, Object> map = objectMapper.readValue(text, new TypeReference<LinkedHashMap<String, Object>>() {});
            Object value = map.get(specKey);
            if (value == null) value = map.get(specKey.replace(" ", ""));
            return nonNegativeMoney(value, "规格价格");
        } catch (Exception e) {
            log.error("AI 规格价格配置解析失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "AI 规格价格配置无效，已停止计费");
        }
    }

    private void decoratePriceRow(Map<String, Object> row) {
        row.put("enabledText", number(row.get("enabled")) == 1 ? "启用" : "禁用");
        // 计费单位决定单价展示后缀
        String billingUnit = defaultText(row.get("billingUnit"), "1K");
        String unitSuffix;
        String unitText;
        switch (billingUnit) {
            case "百万":
                unitSuffix = "/百万";
                unitText = "百万 Tokens";
                break;
            case "兆":
                unitSuffix = "/兆";
                unitText = "兆 Tokens";
                break;
            default:
                unitSuffix = "/1K";
                unitText = "1K Tokens";
        }
        row.put("billingUnitText", unitText);
        row.put("inputPriceText", "¥" + decimal(row.get("inputPricePer1k")).stripTrailingZeros().toPlainString() + unitSuffix);
        row.put("outputPriceText", "¥" + decimal(row.get("outputPricePer1k")).stripTrailingZeros().toPlainString() + unitSuffix);
        BigDecimal cachedInput = decimal(row.get("cachedInputPricePer1k"));
        row.put("cachedInputPriceText", cachedInput.compareTo(BigDecimal.ZERO) > 0
                ? "¥" + cachedInput.stripTrailingZeros().toPlainString() + unitSuffix
                : "-");
        row.put("perCallPriceText", "¥" + decimal(row.get("perCallPrice")).stripTrailingZeros().toPlainString() + "/次");
        // 生图模型额外展示每张成本和每张 Token
        BigDecimal costPerImage = decimal(row.get("costPerImage"));
        row.put("costPerImageText", costPerImage.compareTo(BigDecimal.ZERO) > 0
                ? "¥" + costPerImage.stripTrailingZeros().toPlainString() + "/张"
                : "-");
        long tokensPerImage = number(row.get("tokensPerImage"));
        row.put("tokensPerImageText", tokensPerImage > 0 ? tokensPerImage + " Token/张" : "-");
        // chat 模型额外展示每次成本和每次售价 Token
        BigDecimal costPerCall = decimal(row.get("costPerCall"));
        row.put("costPerCallText", costPerCall.compareTo(BigDecimal.ZERO) > 0
                ? "¥" + costPerCall.stripTrailingZeros().toPlainString() + "/次"
                : "-");
        long tokensPerCall = number(row.get("tokensPerCall"));
        row.put("tokensPerCallText", tokensPerCall > 0 ? tokensPerCall + " Token/次" : "-");
        // 利润 = 售价 Token 折现 - 成本
        BigDecimal rate = decimal(row.get("tokenExchangeRate"));
        if (rate.compareTo(BigDecimal.ZERO) <= 0) rate = DEFAULT_TOKEN_EXCHANGE_RATE;
        BigDecimal profitYuan;
        if ("image".equals(row.get("modelType")) && tokensPerImage > 0) {
            profitYuan = BigDecimal.valueOf(tokensPerImage).divide(rate, 6, RoundingMode.HALF_UP).subtract(costPerImage);
        } else if ("chat".equals(row.get("modelType")) && tokensPerCall > 0) {
            profitYuan = BigDecimal.valueOf(tokensPerCall).divide(rate, 6, RoundingMode.HALF_UP).subtract(costPerCall);
        } else {
            profitYuan = null;
        }
        row.put("profitYuan", profitYuan == null ? null : profitYuan.setScale(4, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString());
        row.put("profitText", profitYuan == null ? "-" : ("¥" + profitYuan.setScale(4, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString() + "/次"));
    }

    private void decorateUsageRow(Map<String, Object> row) {
        row.put("cost", "¥" + BigDecimal.valueOf(number(row.get("costCent"))).divide(ONE_HUNDRED, 4, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString());
        row.put("statusText", number(row.get("status")) == 1 ? "已扣费" : "失败");
    }

    private boolean isModelConfigModule(String moduleKey) {
        return List.of("model-config-general", "model-config-chat", "model-config-image", "model-config-image-2", "model-config-image-3").contains(moduleKey);
    }

    private String inferModelType(String moduleKey) {
        if (moduleKey != null && moduleKey.startsWith("model-config-image")) return "image";
        return "chat";
    }

    private String modelTypeToModuleKey(String modelType) {
        return switch (modelType) {
            case "image" -> "model-config-image";
            default -> "model-config-chat";
        };
    }

    private String normalizeModelType(String value) {
        String v = defaultText(value, "chat").trim().toLowerCase(Locale.ROOT);
        if (v.contains("image") || v.contains("图")) return "image";
        return "chat";
    }

    private BigDecimal nonNegativeMoney(Object value, String fieldName) {
        if (value == null || String.valueOf(value).isBlank()) return BigDecimal.ZERO;
        String normalized = String.valueOf(value).trim().replace("￥", "").replace("¥", "").replace(",", "");
        try {
            BigDecimal amount = new BigDecimal(normalized);
            if (amount.compareTo(BigDecimal.ZERO) < 0) {
                throw new BizException(400, fieldName + "不能为负数");
            }
            return amount;
        } catch (NumberFormatException e) {
            throw new BizException(400, fieldName + "必须为有效数字");
        }
    }

    private long nonNegativeLong(Object value, String fieldName) {
        if (value == null || String.valueOf(value).isBlank()) return 0L;
        try {
            BigDecimal number = new BigDecimal(String.valueOf(value).trim());
            if (number.scale() > 0 && number.stripTrailingZeros().scale() > 0) {
                throw new BizException(400, fieldName + "必须为整数");
            }
            long parsed = number.longValueExact();
            if (parsed < 0) throw new BizException(400, fieldName + "不能为负数");
            return parsed;
        } catch (ArithmeticException | NumberFormatException e) {
            throw new BizException(400, fieldName + "必须为有效整数");
        }
    }

    private long boundedUsageValue(Object value, String fieldName, long maximum, long defaultValue) {
        if (value == null || String.valueOf(value).isBlank()) return defaultValue;
        long parsed = nonNegativeLong(value, fieldName);
        if (parsed > maximum) throw new BizException(400, fieldName + " 超出允许范围");
        return parsed;
    }

    private String normalizeRequestId(Object value) {
        String requestId = defaultText(value, UUID.randomUUID().toString().replace("-", ""));
        if (requestId.length() < 8 || requestId.length() > 128
                || !requestId.matches("[A-Za-z0-9._:-]+")) {
            throw new BizException(400, "requestId 格式非法");
        }
        return requestId;
    }

    private void validateSpecPriceJson(String json) {
        if (!StringUtils.hasText(json)) return;
        try {
            Map<String, Object> prices = objectMapper.readValue(
                    json, new TypeReference<LinkedHashMap<String, Object>>() {});
            if (prices.isEmpty()) throw new BizException(400, "规格价格不能为空");
            for (Map.Entry<String, Object> entry : prices.entrySet()) {
                if (!StringUtils.hasText(entry.getKey())) throw new BizException(400, "规格名称不能为空");
                nonNegativeMoney(entry.getValue(), "规格 " + entry.getKey() + " 的价格");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw new BizException(400, "规格价格必须为 JSON 对象且每个价格均为非负数字");
        }
    }

    private String normalizeBillingModeInput(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return "token";
        String normalized = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if (normalized.equals("token") || normalized.contains("令牌")) return "token";
        if (normalized.equals("per_call") || normalized.equals("call") || normalized.contains("次")) return "per_call";
        if (normalized.equals("spec") || normalized.contains("规格")) return "spec";
        throw new BizException(400, "billingMode 仅支持 token、per_call 或 spec");
    }

    private String normalizeBillingUnitInput(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return "1K";
        String normalized = String.valueOf(value).trim();
        if (normalized.equalsIgnoreCase("1K") || normalized.equals("千")) return "1K";
        if (normalized.contains("百万") || normalized.equalsIgnoreCase("million") || normalized.equalsIgnoreCase("M")) return "百万";
        if (normalized.contains("兆") || normalized.equalsIgnoreCase("T") || normalized.equalsIgnoreCase("trillion")) return "兆";
        throw new BizException(400, "billingUnit 仅支持 1K、百万或兆");
    }

    private String normalizeBillingMode(String value) {
        String v = defaultText(value, "token").trim().toLowerCase(Locale.ROOT);
        if (v.contains("call") || v.contains("次")) return "per_call";
        if (v.contains("spec") || v.contains("规格")) return "spec";
        return "token";
    }

    /** 归一化计费单位：1K / 百万 / 兆。 */
    private String normalizeBillingUnit(Object value) {
        String v = defaultText(value, "1K").trim();
        if (v.contains("百万") || v.equalsIgnoreCase("million") || v.equalsIgnoreCase("M")) return "百万";
        if (v.contains("兆") || v.equalsIgnoreCase("mega") || v.equalsIgnoreCase("T") || v.equalsIgnoreCase("trillion")) return "兆";
        return "1K";
    }

    /** 根据计费单位返回 Token 转费用的除数：1K=1000，百万=10^6，兆=10^12。 */
    private BigDecimal billingUnitDivisor(Object billingUnit) {
        String unit = normalizeBillingUnit(billingUnit);
        switch (unit) {
            case "百万": return BigDecimal.valueOf(1_000_000L);
            case "兆": return BigDecimal.valueOf(1_000_000_000_000L);
            default: return ONE_THOUSAND;
        }
    }

    private Integer parseEnabled(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        if (value instanceof Boolean b) return b ? 1 : 0;
        if (value instanceof Number n) return n.intValue() == 0 ? 0 : 1;
        String s = String.valueOf(value).trim();
        if ("启用".equals(s) || "正常".equals(s) || "true".equalsIgnoreCase(s) || "1".equals(s)) return 1;
        if ("禁用".equals(s) || "false".equalsIgnoreCase(s) || "0".equals(s)) return 0;
        return null;
    }

    private Integer parseStatus(String value) {
        if (!StringUtils.hasText(value)) return null;
        if ("成功".equals(value) || "已扣费".equals(value) || "1".equals(value) || "success".equalsIgnoreCase(value)) return 1;
        if ("失败".equals(value) || "0".equals(value) || "failed".equalsIgnoreCase(value)) return 0;
        return null;
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private Long optionalLong(String sql) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class);
            return v == null ? 0 : v;
        } catch (Exception e) {
            log.error("查询 AI 计费汇总数据失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "AI 计费汇总数据暂时不可用");
        }
    }

    private Long optionalLong(String sql, Object... args) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class, args);
            return v == null ? 0 : v;
        } catch (Exception e) {
            log.error("查询 AI 计费汇总数据失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "AI 计费汇总数据暂时不可用");
        }
    }

    private long sceneUsageCountToday(Long userId, String scene) {
        if (userId == null || !StringUtils.hasText(scene)) return 0L;
        try {
            Long count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND user_id=? AND scene=? AND DATE(created_time)=CURRENT_DATE()",
                    Long.class,
                    userId,
                    scene.trim()
            );
            return count == null ? 0L : count;
        } catch (Exception e) {
            log.error("查询用户当日 AI 场景用量失败, userId={}, scene={}, errorType={}", userId, scene, e.getClass().getSimpleName());
            throw new BizException(503, "AI 用量暂时无法核验，已停止本次计费");
        }
    }

    private long resolveEffectiveChargeTokens(Map<String, Object> estimate, Map<String, Object> sell) {
        // 通用模型必须按次计费：场景定价不得覆盖通用模型的按次扣费规则（默认 3 token/次）。
        // 若允许 sellChargeTokens 覆盖，则场景配置的 sell_tokens_per_reply 会绕过通用模型按次计费，
        // 导致用户被扣 8 token（场景配置）而非 3 token（通用模型默认）。
        if ("model-config-general".equals(estimate.get("moduleKey"))) {
            long estimatedCharge = number(estimate.get("chargeTokens"));
            if (estimatedCharge > 0) return estimatedCharge;
            throw new BizException(503, "通用模型按次计费结果为零，请检查通用模型 perCallPrice 配置");
        }
        long sellChargeTokens = number(sell == null ? null : sell.get("sellChargeTokens"));
        if (sellChargeTokens > 0) {
            return sellChargeTokens;
        }
        boolean sceneConfigured = sell != null && Boolean.TRUE.equals(sell.get("sceneConfigExists"));
        String mode = text(sell == null ? null : sell.get("effectiveChargeMode"));
        long remainingFree = number(sell == null ? null : sell.get("remainingFreeQuota"));
        if (sceneConfigured && ("free".equals(mode)
                || ("member_quota_then_fixed".equals(mode) && remainingFree > 0))) {
            return 0L;
        }
        long estimatedCharge = number(estimate.get("chargeTokens"));
        if (estimatedCharge > 0) return estimatedCharge;
        throw new BizException(503, "AI 计费结果为零且未配置免费策略，已停止调用以避免漏计费");
    }

    private Object first(Map<String, Object> map, String... keys) {
        if (map == null) return null;
        for (String key : keys) {
            if (map.containsKey(key) && map.get(key) != null) return map.get(key);
        }
        return null;
    }

    private Map<String, Object> mergeMaps(Map<String, Object> primary, Map<String, Object> secondary) {
        Map<String, Object> merged = new LinkedHashMap<>();
        if (primary != null) merged.putAll(primary);
        if (secondary != null) merged.putAll(secondary);
        return merged;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    /**
     * 根据 changeType 返回标准 remark 文案。
     * 用于覆盖数据库中可能因字符集问题产生的乱码 remark，保证前端展示一致。
     * 仅对已知 changeType 覆盖；未知类型保留原 remark。
     */
    private String remarkForLedger(String changeType, Object rawRemark) {
        if (changeType == null) changeType = "";
        switch (changeType) {
            case "ai_charge":
                return "AI 调用扣费";
            case "ai_image_charge":
                return "商机发掘生图扣费";
            case "recharge":
                return "Token 充值";
            case "refund":
                return "退款返还";
            case "admin_adjust":
                return "管理员调整";
            case "system":
                return "系统调整";
            default:
                return rawRemark == null ? "" : String.valueOf(rawRemark);
        }
    }

    private String defaultText(Object value, String def) {
        String t = text(value);
        return t.isBlank() ? def : t;
    }

    private long number(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return 0;
        if (value instanceof Number n) return n.longValue();
        try {
            return new BigDecimal(String.valueOf(value)).setScale(0, RoundingMode.DOWN).longValue();
        } catch (Exception e) {
            return 0;
        }
    }

    private Long parseNullableLong(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        try { return new BigDecimal(String.valueOf(value)).longValue(); } catch (Exception e) { return null; }
    }

    /**
     * 读取用户 VIP 等级。
     * sys_user.vip_level：0=普通, 1=VIP, 2=SVP
     * 用户不存在或字段为空时返回 0（普通用户）。
     */
    private int resolveUserVipLevel(Long userId) {
        if (userId == null) return 0;
        try {
            Integer level = jdbcTemplate.queryForObject(
                    "SELECT vip_level FROM sys_user WHERE id=? AND deleted=0",
                    Integer.class, userId);
            return level == null ? 0 : level;
        } catch (Exception e) {
            log.warn("查询用户 VIP 等级失败, userId={}, 使用普通用户默认值: {}", userId, e.getMessage());
            return 0;
        }
    }

    /**
     * 读取通用模型（model-config-general）当前用户等级对应的每次扣费 Token 数。
     * 优先查 ai_model_tier_price；表中无记录时回退到 ai_model_price_config.tokens_per_call；
     * 仍无记录时使用默认值 3。
     */
    private long resolveTierTokensPerCall(Long userId) {
        int vipLevel = resolveUserVipLevel(userId);
        try {
            Long tokens = jdbcTemplate.queryForObject(
                    "SELECT tokens_per_call FROM ai_model_tier_price " +
                            "WHERE module_key='model-config-general' AND vip_level=?",
                    Long.class, vipLevel);
            if (tokens != null && tokens > 0) return tokens;
        } catch (Exception e) {
            log.warn("查询 ai_model_tier_price 失败, vipLevel={}, 使用回退逻辑: {}", vipLevel, e.getMessage());
        }
        // 回退：从 ai_model_price_config.tokens_per_call 读取（兼容旧配置）
        try {
            Long tokensPerCallCfg = jdbcTemplate.queryForObject(
                    "SELECT tokens_per_call FROM ai_model_price_config " +
                            "WHERE deleted=0 AND enabled=1 AND module_key='model-config-general' " +
                            "ORDER BY id DESC LIMIT 1",
                    Long.class);
            if (tokensPerCallCfg != null && tokensPerCallCfg > 0) return tokensPerCallCfg;
        } catch (Exception ignored) {
            // 继续走默认值
        }
        return 3L;
    }

    private BigDecimal money(Object value) {
        return decimal(value).max(BigDecimal.ZERO);
    }

    private BigDecimal decimal(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return BigDecimal.ZERO;
        if (value instanceof BigDecimal bd) return bd;
        if (value instanceof Number n) return BigDecimal.valueOf(n.doubleValue());
        String s = String.valueOf(value).trim().replace("楼", "").replace(",", "");
        try { return new BigDecimal(s); } catch (Exception e) { return BigDecimal.ZERO; }
    }
}
