package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.UserContext;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.client.j2se.MatrixToImageWriter;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.math.BigDecimal;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import javax.imageio.ImageIO;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 支付与充值服务。
 * Java 端负责订单、金额校验、幂等回调、权益发放和余额变动；第三方支付网关只作为收款通道。
 */
@Service
public class PaymentService {
    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);
    private static final long MAX_PAYMENT_AMOUNT_CENT = 100_000_000L;
    private static final long MAX_TOKEN_AMOUNT = 1_000_000_000_000L;
    private static final int MAX_TITLE_LENGTH = 200;
    private final JdbcTemplate jdbcTemplate;
    private final CookieCryptoService cryptoService;
    private final PaymentCallbackAuditService callbackAuditService;

    /**
     * 会员充值活动服务（可选依赖）。
     * 使用字段注入以保持现有测试构造函数兼容；测试中为 null 时活动相关方法自动 no-op。
     */
    @Autowired(required = false)
    private MemberPromotionService promotionService;

    /**
     * 增长合伙人服务（可选依赖）：消费成功后触发邀请奖励与现金分成。
     * 使用 @Lazy 避免循环依赖。
     */
    @Autowired
    @Lazy
    private GrowthService growthService;

    @Value("${payment.sandbox.enabled:false}")
    private boolean sandboxModeEnabled;

    @Value("${payment.external-base-url:}")
    private String externalBaseUrl;

    @Autowired
    public PaymentService(JdbcTemplate jdbcTemplate, CookieCryptoService cryptoService,
                          PaymentCallbackAuditService callbackAuditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.cryptoService = cryptoService;
        this.callbackAuditService = callbackAuditService;
    }

    PaymentService(JdbcTemplate jdbcTemplate, CookieCryptoService cryptoService) {
        this(jdbcTemplate, cryptoService, new PaymentCallbackAuditService(jdbcTemplate));
    }

    PaymentService(JdbcTemplate jdbcTemplate) {
        this(jdbcTemplate, new CookieCryptoService(
                "unit-test-payment-secret-that-is-longer-than-thirty-two-characters"));
    }

    public List<Map<String, Object>> enabledMethods() {
        String sandboxClause = sandboxModeEnabled ? "" : " AND sandbox=0";
        return jdbcTemplate.queryForList(
                "SELECT channel_type AS channelType, provider_type AS providerType, config_name AS configName, enabled, sandbox " +
                        "FROM payment_config WHERE deleted=0 AND enabled=1" + sandboxClause +
                        " ORDER BY FIELD(channel_type,'wechat','alipay'), id ASC");
    }

    public List<Map<String, Object>> tokenPlans() {
        return jdbcTemplate.queryForList(
                "SELECT id, plan_name AS planName, token_amount AS tokenAmount, bonus_token AS bonusToken, price_cent AS priceCent, " +
                        "ROUND(price_cent/100,2) AS priceYuan, status, sort_order AS sortOrder " +
                        "FROM token_recharge_plan WHERE deleted=0 AND status=1 ORDER BY sort_order ASC, price_cent ASC, id ASC");
    }

    public PageResult<Map<String, Object>> pageOrders(int current, int size, String keyword, String status, String orderType) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE o.deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (o.order_no LIKE ? OR u.username LIKE ? OR o.title LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(orderType)) {
            where.append(" AND o.order_type=?");
            args.add(normalizeOrderType(orderType));
        }
        Integer statusValue = parseStatus(status);
        if (StringUtils.hasText(status) && statusValue == null) throw new BizException(400, "非法支付订单状态");
        if (statusValue != null) {
            where.append(" AND o.status=?");
            args.add(statusValue);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM payment_order o LEFT JOIN sys_user u ON u.id=o.user_id" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT o.id, o.tenant_id AS tenantId, o.user_id AS userId, u.username, o.order_no AS orderNo, o.order_type AS orderType, " +
                        "o.target_type AS targetType, o.target_id AS targetId, o.plan_id AS planId, o.token_plan_id AS tokenPlanId, o.title, " +
                        "o.amount_cent AS amountCent, ROUND(o.amount_cent/100,2) AS amountYuan, o.token_amount AS tokenAmount, " +
                        "o.payment_method AS paymentMethod, o.provider_type AS providerType, o.payment_config_id AS paymentConfigId, o.status, o.paid_time AS paidTime, " +
                        "o.expire_time AS expireTime, o.created_time AS createdTime, o.updated_time AS updatedTime " +
                        "FROM payment_order o LEFT JOIN sys_user u ON u.id=o.user_id" + where +
                        " ORDER BY o.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        records.forEach(this::decorateOrder);
        if (total == null) throw new BizException(503, "支付订单总数暂时无法读取");
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    public PageResult<Map<String, Object>> pageTokenPlans(int current, int size, String keyword, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND plan_name LIKE ?");
            args.add("%" + keyword.trim() + "%");
        }
        Integer statusValue = parseEnabled(status);
        if (StringUtils.hasText(status) && statusValue == null) throw new BizException(400, "非法充值套餐状态");
        if (statusValue != null) {
            where.append(" AND status=?");
            args.add(statusValue);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_recharge_plan" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT id, plan_name AS planName, token_amount AS tokenAmount, bonus_token AS bonusToken, price_cent AS priceCent, " +
                        "ROUND(price_cent/100,2) AS priceYuan, status, sort_order AS sortOrder, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM token_recharge_plan" + where + " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        if (total == null) throw new BizException(503, "充值套餐总数暂时无法读取");
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    @Transactional
    public Map<String, Object> saveTokenPlan(Map<String, Object> data) {
        if (data == null) throw new BizException(400, "充值套餐参数不能为空");
        Object id = data.get("id");
        String name = boundedRequired(data, "planName", "充值套餐名称不能为空", 120);
        long tokenAmount = requireWholeNumber(first(data, "tokenAmount", "token_amount"), "token 数量", 1, MAX_TOKEN_AMOUNT);
        long bonusToken = optionalWholeNumber(first(data, "bonusToken", "bonus_token"), "赠送 token 数量", 0, MAX_TOKEN_AMOUNT, 0);
        long priceCent = parseMoneyCent(data);
        if (priceCent <= 0 || priceCent > MAX_PAYMENT_AMOUNT_CENT) {
            throw new BizException(400, "充值金额必须在 0.01 至 1000000 元之间");
        }
        try {
            if (Math.addExact(tokenAmount, bonusToken) > MAX_TOKEN_AMOUNT) {
                throw new BizException(400, "套餐 token 总数超出允许范围");
            }
        } catch (ArithmeticException e) {
            throw new BizException(400, "套餐 token 总数超出允许范围");
        }
        int status = optionalEnabled(first(data, "status"), 1, "套餐状态");
        int sortOrder = (int) optionalWholeNumber(first(data, "sortOrder", "sort_order"), "排序值", -1_000_000, 1_000_000, 100);
        if (id == null || String.valueOf(id).isBlank()) {
            requireSingleWrite("保存 Token 充值套餐失败",
                    "INSERT INTO token_recharge_plan(plan_name, token_amount, bonus_token, price_cent, status, sort_order, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,NOW(),NOW(),0)",
                    name, tokenAmount, bonusToken, priceCent, status, sortOrder);
            Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (newId == null || newId <= 0) throw new BizException(503, "充值套餐已写入但无法确认记录编号，请稍后核验");
            return tokenPlanDetail(newId);
        }
        long planId = requireWholeNumber(id, "套餐 ID", 1, Long.MAX_VALUE);
        int affected = safeUpdate("更新 Token 充值套餐失败",
                "UPDATE token_recharge_plan SET plan_name=?, token_amount=?, bonus_token=?, price_cent=?, status=?, sort_order=?, updated_time=NOW() WHERE id=? AND deleted=0",
                name, tokenAmount, bonusToken, priceCent, status, sortOrder, planId);
        if (affected != 1) throw new BizException(404, "Token 充值套餐不存在");
        return tokenPlanDetail(planId);
    }

    public Map<String, Object> tokenPlanDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, plan_name AS planName, token_amount AS tokenAmount, bonus_token AS bonusToken, price_cent AS priceCent, ROUND(price_cent/100,2) AS priceYuan, status, sort_order AS sortOrder FROM token_recharge_plan WHERE id=? AND deleted=0", id);
        if (rows.isEmpty()) throw new BizException(404, "Token 充值套餐不存在");
        return rows.get(0);
    }

    @Transactional
    public void deleteTokenPlan(long id) {
        if (id <= 0) throw new BizException(400, "套餐 ID 非法");
        int affected = safeUpdate("删除 Token 充值套餐失败",
                "UPDATE token_recharge_plan SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
        if (affected != 1) throw new BizException(404, "Token 充值套餐不存在");
    }

    public List<Map<String, Object>> listConfigs() {
        return jdbcTemplate.queryForList(
                "SELECT id, channel_type AS channelType, provider_type AS providerType, config_name AS configName, merchant_id AS merchantId, app_id AS appId, " +
                        "notify_url AS notifyUrl, gateway_url AS gatewayUrl, enabled, sandbox, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM payment_config WHERE deleted=0 ORDER BY FIELD(channel_type,'wechat','alipay'), id ASC");
    }

    @Transactional
    public Map<String, Object> saveConfig(Map<String, Object> data) {
        if (data == null) throw new BizException(400, "支付配置参数不能为空");
        Object id = data.get("id");
        String channelType = normalizeChannel(required(data, "channelType", "支付方式不能为空"));
        String providerType = normalizeProvider(text(first(data, "providerType", "provider_type")));
        String configName = StringUtils.hasText(String.valueOf(first(data, "configName", "config_name")))
                ? String.valueOf(first(data, "configName", "config_name")).trim()
                : ("wechat".equals(channelType) ? "微信支付" : "支付宝") + ("yipay".equals(providerType) ? "·易支付" : "·官方");
        if (configName.length() > 120) throw new BizException(400, "支付配置名称不能超过 120 个字符");
        int enabled = optionalEnabled(first(data, "enabled"), 1, "启用状态");
        int sandbox = optionalEnabled(first(data, "sandbox"), 0, "沙箱状态");
        if (sandbox == 1 && !sandboxModeEnabled) {
            throw new BizException(403, "支付沙箱全局开关未启用，不能保存沙箱配置");
        }
        String merchantId = boundedOptional(first(data, "merchantId", "merchant_id"), "商户 ID", 160);
        String appId = boundedOptional(first(data, "appId", "app_id"), "应用 ID", 200);
        Map<String, Object> existingSecrets = Map.of();
        if (id != null && !String.valueOf(id).isBlank()) {
            long existingId = requireWholeNumber(id, "支付配置 ID", 1, Long.MAX_VALUE);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT private_key, api_key FROM payment_config WHERE id=? AND deleted=0",
                    existingId);
            if (rows.isEmpty()) throw new BizException(404, "支付配置不存在");
            existingSecrets = rows.get(0);
        }
        String apiKeyPlain = secretInput(first(data, "apiKey", "api_key"), existingSecrets.get("api_key"));
        String privateKeyPlain = secretInput(first(data, "privateKey", "private_key"), existingSecrets.get("private_key"));
        if (apiKeyPlain.length() > 32_000 || privateKeyPlain.length() > 32_000) {
            throw new BizException(400, "支付密钥长度超出允许范围");
        }
        String apiKey = encryptedSecret(apiKeyPlain);
        String privateKey = encryptedSecret(privateKeyPlain);
        String notifyUrl = boundedOptional(first(data, "notifyUrl", "notify_url"), "回调地址", 500);
        String gatewayUrl = boundedOptional(first(data, "gatewayUrl", "gateway_url"), "网关地址", 500);
        validateEnabledPaymentConfiguration(providerType, enabled, sandbox, merchantId, apiKeyPlain, gatewayUrl, notifyUrl);
        if (enabled == 1 && sandbox == 0 && looksLikeSandboxCredential(merchantId, appId, apiKeyPlain)) {
            throw new BizException(400, "生产支付配置不能使用 sandbox/mock/test 占位凭据，请先切换为沙箱模式或填写真实商户参数");
        }
        Object[] values = new Object[]{
                channelType, providerType, configName,
                merchantId, appId,
                privateKey, boundedOptional(first(data, "publicKey", "public_key"), "支付公钥", 32_000),
                apiKey, notifyUrl,
                gatewayUrl, enabled, sandbox, boundedOptional(first(data, "remark"), "备注", 2_000)
        };
        if (id == null || String.valueOf(id).isBlank()) {
            requireSingleWrite("保存支付配置失败",
                    "INSERT INTO payment_config(channel_type, provider_type, config_name, merchant_id, app_id, private_key, public_key, api_key, notify_url, gateway_url, enabled, sandbox, remark, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)", values);
            Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (newId == null || newId <= 0) throw new BizException(503, "支付配置已写入但无法确认记录编号，请稍后核验");
            long savedId = newId;
            isolatePaymentEnvironment(savedId, channelType, enabled, sandbox);
            return configDetail(savedId);
        }
        long configId = requireWholeNumber(id, "支付配置 ID", 1, Long.MAX_VALUE);
        Object[] updateValues = Arrays.copyOf(values, values.length + 1);
        updateValues[values.length] = configId;
        requireSingleWrite("更新支付配置失败",
                "UPDATE payment_config SET channel_type=?, provider_type=?, config_name=?, merchant_id=?, app_id=?, private_key=?, public_key=?, api_key=?, notify_url=?, gateway_url=?, enabled=?, sandbox=?, remark=?, updated_time=NOW() WHERE id=? AND deleted=0", updateValues);
        isolatePaymentEnvironment(configId, channelType, enabled, sandbox);
        return configDetail(configId);
    }

    public Map<String, Object> configDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, channel_type AS channelType, provider_type AS providerType, config_name AS configName, merchant_id AS merchantId, app_id AS appId, " +
                        "notify_url AS notifyUrl, gateway_url AS gatewayUrl, enabled, sandbox, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM payment_config WHERE id=? AND deleted=0", id);
        if (rows.isEmpty()) throw new BizException(404, "支付配置不存在");
        return rows.get(0);
    }

    @Transactional
    public Map<String, Object> createOrder(Map<String, Object> data, String clientIp) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        if (tenantId == null || tenantId <= 0) throw new BizException(401, "登录租户上下文已失效，请重新登录");
        if (data == null) throw new BizException(400, "支付订单参数不能为空");
        String orderType = normalizeOrderType(required(data, "orderType", "订单类型不能为空"));
        if ("ad".equals(orderType)) throw new BizException(400, "广告订单只能通过广告申请流程创建");
        // paymentMethod 在免费订单（amountCent=0）时允许为空，待 amountCent 计算后判断
        Object paymentMethodRaw = first(data, "paymentMethod", "channel");
        String paymentMethod = (paymentMethodRaw != null && StringUtils.hasText(String.valueOf(paymentMethodRaw))) ? normalizeChannel(String.valueOf(paymentMethodRaw)) : null;
        Map<String, Object> config = null;
        long paymentConfigId = 0L;
        String providerType = "free";
        Long planId = null;
        Long tokenPlanId = null;
        String title;
        long amountCent;
        long tokenAmount = 0;
        String targetType = text(first(data, "targetType", "target_type"));
        Long targetId = parseNullableLong(first(data, "targetId", "target_id"));
        if (!StringUtils.hasText(targetType)) targetType = "user_account";
        // VIP 订单的计费周期（month/quarter/year），仅 VIP 分支使用，用于按周期取对应价格并保存到订单
        String vipPeriodType = null;
        // 活动订单快照字段（仅 vip 订单可能填充）
        Long activityId = null;
        Long activityPlanId = null;
        String activityName = null;
        long originalPriceCent = 0L;
        long activityPriceCent = 0L;
        long discountCent = 0L;
        int isActivityOrder = 0;
        int activityRuleVersion = 0;
        // 前端传入的活动套餐配置ID（可选）：非空表示用户走活动价下单
        Long requestActivityPlanId = parseNullableLong(first(data, "activityPlanId", "activity_plan_id"));

        if ("vip".equals(orderType)) {
            targetType = normalizeSubscriptionTarget(targetType);
            targetId = validateSubscriptionTarget(targetType, targetId, tenantId, userId);
            planId = parseNullableLong(first(data, "planId", "plan_id"));
            if (planId == null) throw new BizException(400, "请选择会员套餐");
            vipPeriodType = normalizePeriodType(first(data, "periodType", "period_type"));
            Map<String, Object> plan = queryOne(
                    "SELECT id, plan_name, plan_code, price_month_cent, price_quarter_cent, price_year_cent FROM billing_plan WHERE id=? AND deleted=0 AND status=1", planId);
            if (plan == null) throw new BizException(404, "套餐不存在或已下架");
            amountCent = resolveVipPriceCent(plan, vipPeriodType);
            if (amountCent <= 0) throw new BizException(400, "该套餐未配置" + periodLabel(vipPeriodType) + "价格，请联系管理员");
            if (amountCent > MAX_PAYMENT_AMOUNT_CENT) throw new BizException(503, "会员套餐价格配置超出系统允许范围");
            title = boundedText("会员充值-" + text(plan.get("plan_name")), MAX_TITLE_LENGTH);
            // 活动订单校验：若前端指定 activityPlanId，则服务端重新校验活动状态、价格、名额
            if (requestActivityPlanId != null && promotionService != null) {
                Map<String, Object> preview = promotionService.previewActivityPlan(planId, vipPeriodType);
                if (!Boolean.TRUE.equals(preview.get("available"))) {
                    String reason = text(preview.get("reason"));
                    throw new BizException(400, mapActivityUnavailableReason(reason));
                }
                // 严格校验：前端传入的 activityPlanId 必须与服务端查到的一致
                Long serverActivityPlanId = toLong(preview.get("activityPlanId"));
                if (!requestActivityPlanId.equals(serverActivityPlanId)) {
                    throw new BizException(409, "活动信息已变更，请刷新页面后重新下单");
                }
                Long serverActivityId = toLong(preview.get("activityId"));
                long finalPriceCent = toLong(preview.get("finalPriceCent"));
                long serverOriginalCent = toLong(preview.get("originalPriceCent"));
                int serverRuleVersion = toInt(preview.get("ruleVersion"));
                if (finalPriceCent <= 0) throw new BizException(400, "活动价格异常，请刷新后重试");
                if (finalPriceCent > amountCent) {
                    throw new BizException(400, "活动价高于套餐原价，请刷新页面后重新下单");
                }
                activityId = serverActivityId;
                activityPlanId = serverActivityPlanId;
                activityName = text(preview.get("activityName"));
                originalPriceCent = amountCent; // 套餐正常售价（划线原价）
                activityPriceCent = finalPriceCent;
                discountCent = Math.max(0, amountCent - finalPriceCent);
                isActivityOrder = 1;
                activityRuleVersion = serverRuleVersion;
                amountCent = finalPriceCent; // 实际支付价改用活动价
            }
        } else if ("mall_product".equals(orderType)) {
            targetType = "mall_product";
            targetId = parseNullableLong(first(data, "targetId", "target_id", "productId", "product_id"));
            if (targetId == null) throw new BizException(400, "请选择要购买的商城商品");
            Map<String, Object> product = queryOne(
                    "SELECT id, title, price_cent, product_type, status FROM mall_product WHERE id=? AND deleted=0 AND status=1",
                    targetId);
            if (product == null) throw new BizException(404, "商品不存在或已下架");
            // 允许价格为 0（免费商品），由 createOrder 末尾自动标记已支付
            amountCent = storedNonNegativeLong(product.get("price_cent"), "商城商品价格");
            if (amountCent > MAX_PAYMENT_AMOUNT_CENT) throw new BizException(503, "商城商品价格配置超出系统允许范围");
            title = boundedText("货源商城-" + text(product.get("title")), MAX_TITLE_LENGTH);
        } else {
            targetType = "user_account";
            targetId = null;
            tokenPlanId = parseNullableLong(first(data, "tokenPlanId", "token_plan_id"));
            if (tokenPlanId == null) throw new BizException(400, "请选择 Token 充值套餐");
            Map<String, Object> plan = queryOne("SELECT id, plan_name, token_amount, bonus_token, price_cent FROM token_recharge_plan WHERE id=? AND deleted=0 AND status=1", tokenPlanId);
            if (plan == null) throw new BizException(404, "Token 充值套餐不存在或已下架");
            amountCent = storedPositiveLong(plan.get("price_cent"), "Token 套餐价格");
            if (amountCent > MAX_PAYMENT_AMOUNT_CENT) throw new BizException(503, "Token 套餐价格配置超出系统允许范围");
            try {
                tokenAmount = Math.addExact(
                        storedPositiveLong(plan.get("token_amount"), "Token 套餐数量"),
                        storedNonNegativeLong(plan.get("bonus_token"), "Token 套餐赠送数量"));
            } catch (ArithmeticException e) {
                throw new BizException(503, "Token 套餐数量配置溢出");
            }
            if (tokenAmount > MAX_TOKEN_AMOUNT) throw new BizException(503, "Token 套餐数量配置超出系统允许范围");
            title = boundedText("Token充值-" + text(plan.get("plan_name")), MAX_TITLE_LENGTH);
        }
        // 支付配置：金额 > 0 时必填且查询通道配置；金额 = 0 时跳过（免费商品无需支付通道）
        // 余额支付：使用 sys_user.balance 扣款，跳过支付网关
        boolean balancePay = "balance".equals(paymentMethod);
        if (amountCent > 0) {
            if (paymentMethod == null) throw new BizException(400, "支付方式不能为空");
            if (balancePay) {
                // 余额支付：校验余额是否充足
                Map<String, Object> user = queryOne("SELECT balance FROM sys_user WHERE id=? AND tenant_id=? FOR UPDATE", userId, tenantId);
                if (user == null) throw new BizException(404, "用户不存在");
                long balance = storedNonNegativeLong(user.get("balance"), "用户余额");
                if (balance < amountCent) {
                    throw new BizException(400, "可提现余额不足，当前余额 " + (balance / 100.0) + " 元");
                }
                providerType = "balance";
            } else {
                config = chooseConfig(paymentMethod);
                paymentConfigId = storedPositiveLong(first(config, "id"), "支付配置 ID");
                providerType = normalizeProvider(text(first(config, "provider_type", "providerType")));
            }
        } else if (paymentMethod == null) {
            paymentMethod = "free"; // 免费订单占位，避免数据库 NOT NULL 约束失败
        }
        String orderNo = newOrderNo(orderType);
        LocalDateTime expireAt = LocalDateTime.now().plusMinutes(15);
        // 免费商品（amountCent=0）或余额支付：跳过支付网关下单，qr_content / pay_url 留空
        Map<String, Object> payPayload = (amountCent == 0 || balancePay)
                ? new LinkedHashMap<>()
                : buildPayPayload(orderNo, title, amountCent, paymentMethod, providerType, config, expireAt);
        requireSingleWrite("创建支付订单失败",
                "INSERT INTO payment_order(tenant_id, user_id, order_no, order_type, target_type, target_id, plan_id, token_plan_id, title, amount_cent, token_amount, payment_method, provider_type, payment_config_id, status, client_ip, qr_content, pay_url, expire_time, created_time, updated_time, deleted, period_type, " +
                        "activity_id, activity_plan_id, activity_name, original_price_cent, activity_price_cent, discount_cent, is_activity_order, quota_preoccupied, activity_rule_version) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,NOW(),NOW(),0,?,?,?,?,?,?,?,?,0,?)",
                tenantId, userId, orderNo, orderType, targetType, targetId, planId, tokenPlanId, title, amountCent, tokenAmount, paymentMethod, providerType, paymentConfigId,
                boundedText(clientIp, 80), payPayload.get("qrContent"), payPayload.get("payUrl"), expireAt, vipPeriodType,
                activityId, activityPlanId, activityName, originalPriceCent > 0 ? originalPriceCent : null,
                activityPriceCent > 0 ? activityPriceCent : null, discountCent, isActivityOrder, activityRuleVersion > 0 ? activityRuleVersion : null);
        // 活动订单：创建订单成功后立即预占名额（事务内）
        if (isActivityOrder == 1 && activityPlanId != null && promotionService != null) {
            try {
                promotionService.preoccupyQuota(activityPlanId, orderNo);
                // 标记 quota_preoccupied=1（与 INSERT 默认值 0 不同，预占成功后置 1）
                jdbcTemplate.update("UPDATE payment_order SET quota_preoccupied=1 WHERE order_no=? AND deleted=0", orderNo);
            } catch (BizException e) {
                // 名额预占失败：订单已写入但名额未占，需释放订单（标记为已关闭）
                log.warn("活动订单名额预占失败，关闭订单 orderNo={} activityPlanId={} reason={}", orderNo, activityPlanId, e.getMessage());
                jdbcTemplate.update("UPDATE payment_order SET status=2, updated_time=NOW() WHERE order_no=? AND status=0 AND deleted=0", orderNo);
                throw e;
            }
        }
        // 免费商品（amountCent=0）：跳过支付网关，直接发放权益并标记订单为已支付
        if (amountCent == 0) {
            log.info("免费商品自动完成订单 orderNo={} orderType={} amountCent={}", orderNo, orderType, amountCent);
            markPaid(orderNo, "free_purchase", null);
        } else if (balancePay) {
            // 余额支付：扣减用户余额并标记订单已支付
            requireSingleWrite("扣减用户余额失败",
                    "UPDATE sys_user SET balance=balance-?, updated_time=NOW() WHERE id=? AND tenant_id=? AND balance>=?",
                    amountCent, userId, tenantId, amountCent);
            log.info("余额支付自动完成订单 orderNo={} orderType={} amountCent={}", orderNo, orderType, amountCent);
            markPaid(orderNo, "balance_pay", null);
        }
        return orderDetail(orderNo);
    }

    @Transactional
    public Map<String, Object> createBridgeAdOrder(
            long tenantId,
            long applicationId,
            String title,
            long amountCent,
            String paymentMethod,
            String clientIp
    ) {
        if (tenantId <= 0) {
            throw new BizException(400, "Ad tenant is required");
        }
        if (applicationId <= 0) {
            throw new BizException(400, "Ad application is required");
        }
        if (amountCent <= 0 || amountCent > MAX_PAYMENT_AMOUNT_CENT) {
            throw new BizException(400, "Ad payment amount is outside the allowed range");
        }
        String safeTitle = text(title);
        if (safeTitle.isBlank() || safeTitle.length() > MAX_TITLE_LENGTH) {
            throw new BizException(400, "Ad payment title is invalid");
        }
        String normalizedMethod = normalizeChannel(paymentMethod);
        Map<String, Object> config = chooseConfig(normalizedMethod);
        long paymentConfigId = storedPositiveLong(first(config, "id"), "支付配置 ID");
        String providerType = normalizeProvider(text(first(config, "provider_type", "providerType")));
        String orderNo = newOrderNo("ad");
        LocalDateTime expireAt = LocalDateTime.now().plusMinutes(15);
        Map<String, Object> payPayload = buildPayPayload(orderNo, safeTitle, amountCent, normalizedMethod, providerType, config, expireAt);
        requireSingleWrite("创建广告支付订单失败",
                "INSERT INTO payment_order(tenant_id, user_id, order_no, order_type, target_type, target_id, plan_id, token_plan_id, title, amount_cent, token_amount, payment_method, provider_type, payment_config_id, status, client_ip, qr_content, pay_url, expire_time, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,NOW(),NOW(),0)",
                tenantId, 0L, orderNo, "ad", "open_source_ad_application", applicationId, null, null, safeTitle, amountCent, 0L,
                normalizedMethod, providerType, paymentConfigId, boundedText(clientIp, 80), payPayload.get("qrContent"), payPayload.get("payUrl"), expireAt);
        return orderDetail(orderNo);
    }

    public Map<String, Object> orderDetail(String orderNo) {
        Map<String, Object> row = queryOne(
                "SELECT o.id, o.tenant_id AS tenantId, o.user_id AS userId, o.order_no AS orderNo, o.order_type AS orderType, o.target_type AS targetType, o.target_id AS targetId, " +
                        "o.plan_id AS planId, o.token_plan_id AS tokenPlanId, o.title, o.amount_cent AS amountCent, ROUND(o.amount_cent/100,2) AS amountYuan, o.token_amount AS tokenAmount, " +
                        "o.payment_method AS paymentMethod, o.provider_type AS providerType, o.payment_config_id AS paymentConfigId, o.status, o.qr_content AS qrContent, o.pay_url AS payUrl, o.paid_time AS paidTime, o.expire_time AS expireTime, o.created_time AS createdTime " +
                        "FROM payment_order o WHERE o.order_no=? AND o.deleted=0", orderNo);
        if (row == null) throw new BizException(404, "支付订单不存在");
        decorateOrder(row);
        String qr = text(row.get("qrContent"));
        if (StringUtils.hasText(qr)) {
            row.put("qrImage", qrBase64(qr));
        }
        return row;
    }

    public Map<String, Object> userOrderDetail(String orderNo) {
        Map<String, Object> row = orderDetail(orderNo);
        ensureCurrentUserOwnsOrder(row);
        return row;
    }

    @Transactional
    public Map<String, Object> handleCallback(String channel, Map<String, Object> payload, String rawBody) {
        String normalizedChannel = normalizeChannel(channel);
        if (payload == null || payload.isEmpty()) throw new BizException(400, "支付回调内容不能为空");
        String orderNo = text(first(payload, "orderNo", "order_no", "out_trade_no", "outTradeNo"));
        if (!StringUtils.hasText(orderNo)) throw new BizException(400, "回调缺少订单号");
        if (orderNo.length() > 80) throw new BizException(400, "支付回调订单号非法");
        Map<String, Object> order = queryOne("SELECT * FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE", orderNo);
        if (order == null) throw new BizException(404, "支付订单不存在");
        String orderChannel = text(order.get("payment_method"));
        if (StringUtils.hasText(orderChannel) && !orderChannel.equals(normalizedChannel)) {
            throw new BizException(400, "支付通道不匹配");
        }
        // provider 必须以订单创建时记录为准，不能信任回调请求体，避免伪造 provider 绕过验签。
        String provider = normalizeProvider(text(order.get("provider_type")));
        Object callbackAmount = first(payload, "amountCent", "amount_cent", "money", "total_fee", "totalAmount");
        long paidAmount = callbackAmount == null ? -1L
                : (payload.containsKey("money") || payload.containsKey("totalAmount")
                ? yuanToCent(first(payload, "money", "totalAmount"))
                : requireWholeNumber(callbackAmount, "支付回调金额", 0, MAX_PAYMENT_AMOUNT_CENT));
        String gatewayTransactionId = text(first(payload, "trade_no", "transaction_id", "transactionId"));
        boolean signatureOk = verifyCallbackSignature(provider, payload, order);
        int processStatus = 0;
        String message = "回调待处理";
        try {
            if (!signatureOk) throw new BizException(400, "支付回调签名校验失败");
            if (!isSuccessfulCallback(provider, payload)) throw new BizException(400, "支付回调状态不是成功");
            if (callbackAmount == null) throw new BizException(400, "支付回调缺少金额");
            if (paidAmount != storedPositiveLong(order.get("amount_cent"), "支付订单金额")) {
                throw new BizException(400, "支付金额不匹配");
            }
            if (!StringUtils.hasText(gatewayTransactionId) || gatewayTransactionId.length() > 120) {
                throw new BizException(400, "支付回调缺少合法的网关交易号");
            }
            String existingGatewayTransactionId = text(order.get("out_trade_no"));
            if (storedStatus(order.get("status"), "支付订单状态") == 1) {
                if (!StringUtils.hasText(existingGatewayTransactionId)) {
                    throw new BizException(409, "历史已支付订单缺少网关交易号，请人工核验，不能自动重绑");
                }
                if (!MessageDigest.isEqual(existingGatewayTransactionId.getBytes(StandardCharsets.UTF_8),
                        gatewayTransactionId.getBytes(StandardCharsets.UTF_8))) {
                    throw new BizException(409, "支付订单已绑定其他网关交易号");
                }
            }
            Map<String, Object> duplicateTrade = queryOne(
                    "SELECT order_no FROM payment_order WHERE out_trade_no=? AND order_no<>? AND deleted=0 LIMIT 1",
                    gatewayTransactionId, orderNo);
            if (duplicateTrade != null) throw new BizException(409, "网关交易号已绑定其他订单");
            markPaid(orderNo, "callback:" + normalizedChannel, gatewayTransactionId);
            processStatus = 1;
            message = "处理成功";
        } catch (RuntimeException e) {
            message = e instanceof BizException ? e.getMessage() : "支付回调处理失败";
            throw e;
        } finally {
            callbackAuditService.record(orderNo, normalizedChannel, provider, rawBody,
                    text(first(payload, "sign", "signature")), signatureOk, processStatus == 1, message);
        }
        return orderDetail(orderNo);
    }

    @Transactional
    public Map<String, Object> mockPay(String orderNo) {
        requireSandboxMode();
        return markPaid(orderNo, "dev_mock", null);
    }

    /**
     * 管理员强制标记订单为已支付（不要求沙箱模式）。
     * 用于本地开发测试（易支付回调无法到达本机）或生产环境回调丢失的订单补救。
     * 与 mockPay 区别：mockPay 仅在沙箱模式下可用，用于开发流程；
     * forceMarkPaid 由管理员显式触发，用于真实支付但回调未到的订单。
     */
    @Transactional
    public Map<String, Object> forceMarkPaidByAdmin(String orderNo, String remark) {
        if (!StringUtils.hasText(orderNo)) throw new BizException(400, "订单号不能为空");
        Map<String, Object> order = queryOne(
                "SELECT order_no, status FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE", orderNo);
        if (order == null) throw new BizException(404, "支付订单不存在");
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) return orderDetail(orderNo);
        if (status != 0) throw new BizException(400, "订单状态不可标记为已支付（当前状态=" + status + "）");
        String source = "admin_force_paid" + (StringUtils.hasText(remark) ? ":" + boundedText(remark, 50) : "");
        log.warn("管理员强制标记订单为已支付 orderNo={} remark={}", orderNo, remark);
        return markPaid(orderNo, source, null);
    }

    @Transactional
    public Map<String, Object> mockPayUserOrder(String orderNo) {
        requireSandboxMode();
        Map<String, Object> order = queryOne("SELECT order_no AS orderNo, tenant_id AS tenantId, user_id AS userId, payment_method AS paymentMethod, payment_config_id AS paymentConfigId, status FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE", orderNo);
        if (order == null) throw new BizException(404, "支付订单不存在");
        ensureCurrentUserOwnsOrder(order);
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) return orderDetail(orderNo);
        if (status != 0) throw new BizException(400, "订单状态不可模拟支付");
        String channel = text(order.get("paymentMethod"));
        Map<String, Object> config = configForOrder(order);
        int sandbox = storedStatus(config.getOrDefault("sandbox", 0), "支付沙箱状态");
        if (sandbox != 1) throw new BizException(403, "仅沙箱支付配置允许模拟支付");
        return markPaid(orderNo, "sandbox_mock", null);
    }

    @Transactional
    public Map<String, Object> mockPayBridgeOrder(String orderNo) {
        requireSandboxMode();
        Map<String, Object> order = queryOne(
                "SELECT order_no AS orderNo, payment_method AS paymentMethod, payment_config_id AS paymentConfigId, status " +
                        "FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE",
                orderNo
        );
        if (order == null) throw new BizException(404, "支付订单不存在");
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) return orderDetail(orderNo);
        if (status != 0) throw new BizException(400, "订单状态不允许模拟支付");
        String channel = text(order.get("paymentMethod"));
        Map<String, Object> config = configForOrder(order);
        int sandbox = storedStatus(config.getOrDefault("sandbox", 0), "支付沙箱状态");
        if (sandbox != 1) throw new BizException(403, "仅沙箱支付配置允许模拟支付");
        return markPaid(orderNo, "sandbox_mock", null);
    }

    private void requireSandboxMode() {
        if (!sandboxModeEnabled) {
            throw new BizException(403, "支付沙箱未启用，模拟支付不可用");
        }
    }

    @Transactional
    public Map<String, Object> closeUserOrder(String orderNo) {
        Map<String, Object> order = queryOne("SELECT id, user_id, status, is_activity_order, quota_preoccupied, activity_plan_id, order_no FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE", orderNo);
        if (order == null) throw new BizException(404, "支付订单不存在");
        ensureCurrentUserOwnsOrder(order);
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) throw new BizException(400, "订单已支付，不能关闭");
        if (status == 0) {
            requireSingleWrite("关闭支付订单失败",
                    "UPDATE payment_order SET status=2, updated_time=NOW() WHERE order_no=? AND status=0 AND deleted=0", orderNo);
            // 活动订单：用户主动关闭后释放预占名额
            releaseActivityQuotaIfPreoccupied(order, "user_close");
        }
        return orderDetail(orderNo);
    }

    @Transactional
    public Map<String, Object> closeBridgeOrder(String orderNo) {
        Map<String, Object> order = queryOne(
                "SELECT id, status, is_activity_order, quota_preoccupied, activity_plan_id, order_no FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE",
                orderNo
        );
        if (order == null) throw new BizException(404, "支付订单不存在");
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) throw new BizException(400, "订单已支付，不能关闭");
        if (status == 0) {
            requireSingleWrite("关闭支付订单失败",
                    "UPDATE payment_order SET status=2, updated_time=NOW() WHERE order_no=? AND status=0 AND deleted=0", orderNo);
            // 活动订单：关闭后释放预占名额
            releaseActivityQuotaIfPreoccupied(order, "bridge_close");
        }
        return orderDetail(orderNo);
    }

    private void ensureCurrentUserOwnsOrder(Map<String, Object> order) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        Object owner = first(order, "userId", "user_id");
        Object orderTenant = first(order, "tenantId", "tenant_id");
        if (owner == null || !Objects.equals(String.valueOf(userId), String.valueOf(owner))
                || (orderTenant != null && (tenantId == null
                || !Objects.equals(String.valueOf(tenantId), String.valueOf(orderTenant))))) {
            throw new BizException(404, "支付订单不存在");
        }
    }

    private Map<String, Object> markPaid(String orderNo, String source, String gatewayTransactionId) {
        Map<String, Object> order = queryOne("SELECT * FROM payment_order WHERE order_no=? AND deleted=0 FOR UPDATE", orderNo);
        if (order == null) throw new BizException(404, "支付订单不存在");
        int status = storedStatus(order.get("status"), "支付订单状态");
        if (status == 1) return orderDetail(orderNo);
        if (status != 0) throw new BizException(400, "订单状态不可支付");
        if ("vip".equals(order.get("order_type"))) {
            activateVip(order, source);
        } else if ("token".equals(order.get("order_type"))) {
            rechargeToken(order, source);
        } else if ("mall_product".equals(order.get("order_type"))) {
            fulfillMallProduct(order, source);
        } else if (!"ad".equals(order.get("order_type"))) {
            throw new BizException(503, "支付订单类型配置异常，无法发放权益");
        }
        requireSingleWrite("确认支付订单失败",
                "UPDATE payment_order SET status=1, out_trade_no=COALESCE(?, out_trade_no), paid_time=NOW(), updated_time=NOW() WHERE order_no=? AND status=0 AND deleted=0",
                StringUtils.hasText(gatewayTransactionId) ? gatewayTransactionId : null, orderNo);
        // 活动订单：支付成功后确认扣减名额（preoccupied-1, sold+1）。幂等：通过 quota_preoccupied 标志控制。
        confirmActivityQuotaIfPreoccupied(order);
        // 增长合伙人：消费成功后触发邀请奖励（Token 奖励 + 现金分成）
        triggerGrowthReward(order, source);
        return orderDetail(orderNo);
    }

    /**
     * 增长合伙人奖励触发：消费成功后调用 GrowthService 发放邀请人 Token 奖励与现金分成。
     * 异常不阻断支付成功（已发放权益），仅记录日志便于人工核对。
     */
    private void triggerGrowthReward(Map<String, Object> order, String source) {
        if (growthService == null) return;
        try {
            long userId = storedPositiveLong(order.get("user_id"), "支付用户 ID");
            long tenantId = storedPositiveLong(order.get("tenant_id"), "支付租户 ID");
            String orderNo = text(order.get("order_no"));
            String orderType = text(order.get("order_type"));
            long amountCent = storedNonNegativeLong(order.get("amount_cent"), "支付金额");
            String title = text(order.get("title"));
            growthService.onConsumptionPaid(userId, tenantId, orderNo, orderType, amountCent, title);
        } catch (Exception e) {
            log.error("增长合伙人奖励触发失败 orderNo={} errorType={}", text(order.get("order_no")), e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 活动订单支付成功后确认扣减名额。
     * 幂等性：仅当 quota_preoccupied=1 时执行，执行后置 0 防止重复扣减。
     */
    private void confirmActivityQuotaIfPreoccupied(Map<String, Object> order) {
        if (promotionService == null) return;
        int isActivityOrder = storedStatus(order.getOrDefault("is_activity_order", 0), "活动订单标志");
        int quotaPreoccupied = storedStatus(order.getOrDefault("quota_preoccupied", 0), "名额预占标志");
        if (isActivityOrder != 1 || quotaPreoccupied != 1) return;
        Long activityPlanId = storedNullablePositiveLong(order.get("activity_plan_id"), "活动套餐配置 ID");
        String orderNo = text(order.get("order_no"));
        if (activityPlanId == null) {
            log.warn("活动订单缺少 activity_plan_id，跳过名额确认 orderNo={}", orderNo);
            return;
        }
        try {
            promotionService.confirmQuota(activityPlanId, orderNo);
            // 置 quota_preoccupied=0，防止重复扣减（已转为 sold_count）
            jdbcTemplate.update("UPDATE payment_order SET quota_preoccupied=0 WHERE order_no=? AND deleted=0", orderNo);
        } catch (Exception e) {
            // 名额确认失败不阻断支付成功（已发放权益），仅记录日志便于人工核对
            log.error("活动订单名额确认失败 orderNo={} activityPlanId={} errorType={}", orderNo, activityPlanId, e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 订单关闭/超时时释放活动预占名额。
     * 幂等性：仅当 quota_preoccupied=1 时执行，执行后置 0 防止重复释放。
     */
    private void releaseActivityQuotaIfPreoccupied(Map<String, Object> order, String reason) {
        if (promotionService == null) return;
        int isActivityOrder = storedStatus(order.getOrDefault("is_activity_order", 0), "活动订单标志");
        int quotaPreoccupied = storedStatus(order.getOrDefault("quota_preoccupied", 0), "名额预占标志");
        if (isActivityOrder != 1 || quotaPreoccupied != 1) return;
        Long activityPlanId = storedNullablePositiveLong(order.get("activity_plan_id"), "活动套餐配置 ID");
        String orderNo = text(order.get("order_no"));
        if (activityPlanId == null) {
            log.warn("活动订单缺少 activity_plan_id，跳过名额释放 orderNo={}", orderNo);
            return;
        }
        try {
            promotionService.releaseQuota(activityPlanId, orderNo, reason);
            jdbcTemplate.update("UPDATE payment_order SET quota_preoccupied=0 WHERE order_no=? AND deleted=0", orderNo);
        } catch (Exception e) {
            log.error("活动订单名额释放失败 orderNo={} activityPlanId={} reason={} errorType={}",
                    orderNo, activityPlanId, reason, e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 将活动不可用原因映射为用户友好提示。
     */
    private String mapActivityUnavailableReason(String reason) {
        if (reason == null) return "活动不可用，请刷新页面后重试";
        switch (reason) {
            case "no_activity": return "活动已结束或不存在，请按套餐正常价格下单";
            case "activity_not_started": return "活动尚未开始，请稍后再试";
            case "activity_ended": return "活动已结束，请按套餐正常价格下单";
            case "activity_closed": return "活动已关闭，请按套餐正常价格下单";
            case "quota_full": return "活动名额已满，请稍后再试或选择其他套餐";
            case "plan_offline": return "套餐已下架，请选择其他套餐";
            case "price_invalid": return "活动价格异常，请刷新页面后重新下单";
            default: return "活动不可用，请刷新页面后重试";
        }
    }

    private void activateVip(Map<String, Object> order, String source) {
        long userId = storedPositiveLong(order.get("user_id"), "支付用户 ID");
        long tenantId = storedPositiveLong(order.get("tenant_id"), "支付租户 ID");
        long planId = storedPositiveLong(order.get("plan_id"), "会员套餐 ID");
        String targetType = normalizeSubscriptionTarget(text(order.get("target_type")));
        Long targetId = storedNullablePositiveLong(order.get("target_id"), "订阅目标 ID");
        // 按订单 period_type 推导会员有效期天数：month=30, quarter=90, year=365
        // NULL 视为 month（兼容 V1.30 之前的历史订单，旧订单的 duration_days 已不再读取）
        String periodType = normalizePeriodType(order.get("period_type"));
        int days = daysForPeriod(periodType);
        safeUpdate("停用旧会员权益失败",
                "UPDATE billing_subscription SET status=0, updated_time=NOW() WHERE tenant_id=? AND user_id=? AND status=1 AND target_type=? AND ((? IS NULL AND target_id IS NULL) OR target_id=?)",
                tenantId, userId, targetType, targetId, targetId);
        if (days <= 0) {
            requireSingleWrite("发放会员权益失败",
                "INSERT INTO billing_subscription(tenant_id, user_id, plan_id, target_type, target_id, start_time, end_time, status, source, created_time, updated_time) VALUES(?,?,?,?,?,NOW(),NULL,1,?,NOW(),NOW())",
                tenantId, userId, planId, targetType, targetId, boundedText(source, 50));
        } else {
            requireSingleWrite("发放会员权益失败",
                "INSERT INTO billing_subscription(tenant_id, user_id, plan_id, target_type, target_id, start_time, end_time, status, source, created_time, updated_time) VALUES(?,?,?,?,?,NOW(),DATE_ADD(NOW(), INTERVAL ? DAY),1,?,NOW(),NOW())",
                tenantId, userId, planId, targetType, targetId, days, boundedText(source, 50));
        }
    }

    private void rechargeToken(Map<String, Object> order, String source) {
        long userId = storedPositiveLong(order.get("user_id"), "充值用户 ID");
        long tenantId = storedPositiveLong(order.get("tenant_id"), "充值租户 ID");
        long orderId = storedPositiveLong(order.get("id"), "支付订单 ID");
        long tokenAmount = storedPositiveLong(order.get("token_amount"), "充值 Token 数量");
        if (tokenAmount > MAX_TOKEN_AMOUNT) throw new BizException(503, "支付订单 Token 数量超出系统允许范围");
        Map<String, Object> user = queryOne("SELECT token_balance FROM sys_user WHERE id=? AND tenant_id=? FOR UPDATE", userId, tenantId);
        if (user == null) throw new BizException(409, "充值用户不存在或不属于当前租户，请人工核验支付订单");
        long before = storedNonNegativeLong(user.get("token_balance"), "用户 Token 余额");
        long after;
        try {
            after = Math.addExact(before, tokenAmount);
        } catch (ArithmeticException e) {
            throw new BizException(409, "用户 Token 余额已达到上限，请人工处理该支付订单");
        }
        requireSingleWrite("更新 Token 余额失败",
                "UPDATE sys_user SET token_balance=?, updated_time=NOW() WHERE id=? AND tenant_id=?", after, userId, tenantId);
        requireSingleWrite("写入 Token 充值记录失败",
                "INSERT INTO token_recharge_record(tenant_id, user_id, payment_order_id, order_no, token_amount, before_balance, after_balance, source, remark, created_time) VALUES(?,?,?,?,?,?,?,?,?,NOW())",
                tenantId, userId, orderId, boundedText(text(order.get("order_no")), 80), tokenAmount, before, after, boundedText(source, 80), "支付充值");
        requireSingleWrite("写入 Token 余额账本失败",
                "INSERT INTO token_balance_ledger(tenant_id, user_id, change_type, change_amount, before_balance, after_balance, ref_type, ref_id, ref_no, remark, created_time) VALUES(?,?,?,?,?,?,?,?,?,?,NOW())",
                tenantId, userId, "recharge", tokenAmount, before, after, "payment_order", orderId,
                boundedText(text(order.get("order_no")), 120), "支付充值");
    }

    /**
     * 商城商品支付成功后处理：更新购买人数，卡密商品自动分配一张可用卡密，
     * 同时将商品绑定到用户货源库（from_mall=1 + mall_product_id），货源内容实时从 mall_product 读取。
     */
    private void fulfillMallProduct(Map<String, Object> order, String source) {
        Long productIdRaw = storedNullablePositiveLong(order.get("target_id"), "商城商品 ID");
        if (productIdRaw == null || productIdRaw <= 0) {
            throw new BizException(409, "支付订单缺少商品 ID，请人工核验支付订单");
        }
        long productId = productIdRaw;
        Map<String, Object> product = queryOne(
                "SELECT id, product_type, status, title FROM mall_product WHERE id=? AND deleted=0", productId);
        if (product == null) {
            throw new BizException(409, "商品不存在或已删除，请人工核验支付订单");
        }
        // 更新购买人数
        safeUpdate("更新购买人数失败",
                "UPDATE mall_product SET bought_count=bought_count+1, updated_time=NOW() WHERE id=? AND deleted=0",
                productId);
        // 卡密商品自动分配一张可用卡密
        String productType = text(product.get("product_type"));
        if ("card".equals(productType)) {
            String orderNo = text(order.get("order_no"));
            int assigned = safeUpdate("分配卡密失败",
                    "UPDATE mall_card_key SET status='sold', order_no=?, sold_time=NOW() " +
                            "WHERE product_id=? AND status='available' ORDER BY id ASC LIMIT 1",
                    orderNo, productId);
            if (assigned != 1) {
                log.error("卡密商品无可用卡密可分配（用户已付款），需人工补发卡密或退款, productId={}, orderNo={}", productId, orderNo);
            }
        }
        // 将商品绑定到用户货源库（仅保存商品 ID 与标题快照，货源内容实时从 mall_product 读取以保证后台更新同步）
        Long userId = storedNullablePositiveLong(order.get("user_id"), "支付订单用户 ID");
        Long tenantId = storedNullablePositiveLong(order.get("tenant_id"), "支付订单租户 ID");
        if (userId != null && tenantId != null) {
            try {
                Integer existing = jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM delivery_text_source WHERE tenant_id=? AND from_mall=1 AND mall_product_id=? AND deleted=0",
                        Integer.class, tenantId, productId);
                if (existing == null || existing == 0) {
                    String titleSnapshot = text(product.get("title"));
                    jdbcTemplate.update(
                            "INSERT INTO delivery_text_source(tenant_id, source_type, delivery_mode, card_group_id, title, content, remark, from_mall, mall_product_id, created_time, updated_time, deleted) " +
                                    "VALUES(?, 'text', 'text', NULL, ?, '', '商城购买货源', 1, ?, NOW(), NOW(), 0)",
                            tenantId, titleSnapshot, productId);
                    log.info("商城购买货源已绑定到用户货源库 tenantId={} userId={} productId={}", tenantId, userId, productId);
                }
            } catch (DataAccessException e) {
                log.error("商城购买货源绑定到用户货源库失败（不影响卡密分发与购买计数） tenantId={} productId={} errorType={} error={}",
                        tenantId, productId, e.getClass().getSimpleName(), e.getMessage());
            }
        }
    }

    private Map<String, Object> buildPayPayload(String orderNo, String title, long amountCent, String channel, String provider, Map<String, Object> config, LocalDateTime expireAt) {
        String gateway = text(config.get("gateway_url"));
        String notifyUrl = text(config.get("notify_url"));
        Map<String, Object> res = new LinkedHashMap<>();
        boolean sandbox = ((Number) config.getOrDefault("sandbox", 0)).intValue() == 1;
        if (sandbox) {
            String qrContent = "SANDBOX-PAY:" + channel + ":" + orderNo + ":" + amountCent + ":" + expireAt.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
            res.put("payUrl", qrContent);
            res.put("qrContent", qrContent);
            return res;
        }
        if ("yipay".equals(provider) && StringUtils.hasText(gateway)) {
            validateEnabledPaymentConfiguration(provider, 1, 0,
                    text(config.get("merchant_id")), text(config.get("api_key")), gateway, notifyUrl);
            String resolvedNotifyUrl = resolveNotifyUrl(notifyUrl);
            // return_url 是用户支付完成后浏览器跳转地址，必须指向用户可访问的前端页面，不能用后端回调 URL
            String resolvedReturnUrl = resolveReturnUrl(notifyUrl);
            Map<String, String> params = new LinkedHashMap<>();
            params.put("pid", text(config.get("merchant_id")));
            params.put("type", "wechat".equals(channel) ? "wxpay" : "alipay");
            params.put("out_trade_no", orderNo);
            params.put("notify_url", resolvedNotifyUrl);
            params.put("return_url", resolvedReturnUrl);
            params.put("name", title);
            params.put("money", BigDecimal.valueOf(amountCent).divide(BigDecimal.valueOf(100)).stripTrailingZeros().toPlainString());
            String sign = signYipay(params, text(config.get("api_key")));
            params.put("sign", sign);
            params.put("sign_type", "MD5");
            String query = params.entrySet().stream()
                    .map(e -> e.getKey() + "=" + urlEncode(e.getValue()))
                    .collect(Collectors.joining("&"));
            String submitUrl = normalizeYipayGateway(gateway);
            String payUrl = submitUrl + (submitUrl.contains("?") ? "&" : "?") + query;
            // 二维码内容直接放易支付 GET URL：扫码后浏览器直接打开收银台，无需我方中转。
            // 易支付 submit.php 同时支持 GET 和 POST，GET 方式会自动跳转到收银台页面。
            res.put("payUrl", payUrl);
            res.put("qrContent", payUrl);
            return res;
        }
        throw new BizException(503, "官方微信/支付宝下单与验签适配器尚未接入，请使用沙箱或已完成验签的支付通道");
    }


    private String qrBase64(String content) {
        try {
            BitMatrix matrix = new QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, 220, 220);
            BufferedImage image = MatrixToImageWriter.toBufferedImage(matrix);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            if (!ImageIO.write(image, "png", out)) throw new IllegalStateException("PNG encoder unavailable");
            return "data:image/png;base64," + Base64.getEncoder().encodeToString(out.toByteArray());
        } catch (Exception e) {
            throw new BizException(503, "支付二维码暂时无法生成，请稍后重试");
        }
    }

    private boolean verifyCallbackSignature(String provider, Map<String, Object> payload, Map<String, Object> order) {
        if (!"yipay".equals(provider)) {
            // 官方微信/支付宝适配器尚未实现证书/平台公钥强验签，必须 fail-closed，不能默认通过。
            return false;
        }
        String sign = text(first(payload, "sign", "signature"));
        if (!StringUtils.hasText(sign)) return false;
        Map<String, Object> config = configForOrder(order);
        String apiKey = text(config.get("api_key"));
        if (!StringUtils.hasText(apiKey) || apiKey.length() < 16) return false;
        String configuredMerchant = text(config.get("merchant_id"));
        String callbackMerchant = text(first(payload, "pid", "merchant_id", "merchantId"));
        if (!StringUtils.hasText(configuredMerchant) || !StringUtils.hasText(callbackMerchant)
                || !MessageDigest.isEqual(configuredMerchant.getBytes(StandardCharsets.UTF_8),
                callbackMerchant.getBytes(StandardCharsets.UTF_8))) return false;
        String expectedType = "wechat".equals(text(order.get("payment_method"))) ? "wxpay" : "alipay";
        String callbackType = text(first(payload, "type", "payment_type", "paymentType"));
        if (!expectedType.equalsIgnoreCase(callbackType)) return false;
        Map<String, String> sorted = new TreeMap<>();
        for (Map.Entry<String, Object> e : payload.entrySet()) {
            if (e.getValue() == null) continue;
            String k = e.getKey();
            if ("sign".equals(k) || "sign_type".equals(k) || "signature".equals(k)) continue;
            String v = String.valueOf(e.getValue());
            if (!v.isBlank()) sorted.put(k, v);
        }
        String local = signYipay(sorted, apiKey);
        return MessageDigest.isEqual(
                sign.toLowerCase(Locale.ROOT).getBytes(StandardCharsets.US_ASCII),
                local.toLowerCase(Locale.ROOT).getBytes(StandardCharsets.US_ASCII));
    }

    private void validateEnabledPaymentConfiguration(String provider, int enabled, int sandbox,
                                                     String merchantId, String apiKey,
                                                     String gatewayUrl, String notifyUrl) {
        if (enabled != 1 || sandbox == 1) return;
        if ("official".equals(provider)) {
            throw new BizException(503, "官方微信/支付宝生产适配器尚未接入，当前不能启用");
        }
        if (!StringUtils.hasText(merchantId)) {
            throw new BizException(400, "启用易支付生产通道前必须填写商户 ID");
        }
        if (!StringUtils.hasText(apiKey) || apiKey.length() < 16) {
            throw new BizException(400, "易支付 API Key 未配置或强度不足");
        }
        if (!isSecureHttpsUrl(gatewayUrl)) {
            throw new BizException(400, "易支付生产网关地址必须使用标准 HTTPS URL");
        }
        if (!isRelativePath(notifyUrl) && !isSecureHttpsUrl(notifyUrl)) {
            throw new BizException(400, "易支付回调地址必须使用标准 HTTPS URL 或以 / 开头的相对路径");
        }
    }

    private boolean isSuccessfulCallback(String provider, Map<String, Object> payload) {
        if (!"yipay".equals(provider)) return false;
        String status = text(first(payload, "trade_status", "tradeStatus", "status"));
        return "TRADE_SUCCESS".equalsIgnoreCase(status);
    }

    private String boundedText(String value, int maxLength) {
        if (value == null) return "";
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    private boolean isSecureHttpsUrl(String value) {
        if (!StringUtils.hasText(value)) return false;
        try {
            URI uri = URI.create(value.trim());
            return "https".equalsIgnoreCase(uri.getScheme())
                    && StringUtils.hasText(uri.getHost())
                    && uri.getRawUserInfo() == null
                    && uri.getFragment() == null
                    && (uri.getPort() == -1 || uri.getPort() == 443);
        } catch (RuntimeException e) {
            return false;
        }
    }

    private boolean isRelativePath(String value) {
        return StringUtils.hasText(value) && value.startsWith("/") && !value.startsWith("//");
    }

    private String resolveNotifyUrl(String notifyUrl) {
        if (!isRelativePath(notifyUrl)) {
            return notifyUrl;
        }
        // 优先使用管理员显式配置的 external-base-url
        String base = externalBaseUrl == null ? "" : externalBaseUrl.trim();
        // 配置缺失时，尝试从当前 HTTP 请求自动推断外部访问地址（基于反向代理转发的 X-Forwarded-* 头）
        if (base.isEmpty()) {
            base = inferExternalBaseUrlFromRequest();
        }
        if (base.isEmpty()) {
            log.warn("支付回调地址解析失败：notifyUrl={}, externalBaseUrl={}, 推断失败。请配置环境变量 PAYMENT_EXTERNAL_BASE_URL", notifyUrl, externalBaseUrl);
            throw new BizException(503, "支付回调地址为相对路径，但系统未配置 payment.external-base-url，且无法从当前请求推断外部访问地址。请在环境变量 PAYMENT_EXTERNAL_BASE_URL 中设置外部可访问地址（例如：http://1.12.66.249:18080 或 https://your-domain.com），重启服务后生效");
        }
        if (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        return base + notifyUrl;
    }

    /**
     * 从当前 HTTP 请求推断外部访问基础地址。
     * 依次尝试：
     *   1. X-Forwarded-Proto + X-Forwarded-Host（标准反向代理转发头）
     *   2. request.getScheme() + request.getServerName() + request.getServerPort()
     * 优先返回 HTTPS URL；若反向代理或直连为 HTTP，则返回 HTTP URL 并记录警告（回调地址仍可用，但存在被中间人篡改风险）。
     * 若推断结果是 localhost/127.0.0.1 等本机回环地址，返回空串（手机扫码无法访问本机）。
     */
    private String inferExternalBaseUrlFromRequest() {
        HttpServletRequest request = currentHttpRequest();
        if (request == null) {
            log.warn("支付回调地址推断失败：当前线程无 HTTP 请求上下文（可能是异步调用），请配置 payment.external-base-url");
            return "";
        }
        String scheme = firstForwardedValue(request.getHeader("X-Forwarded-Proto"));
        if (scheme == null || scheme.isEmpty()) {
            scheme = request.getScheme();
        }
        String host = firstForwardedValue(request.getHeader("X-Forwarded-Host"));
        if (host == null || host.isEmpty()) {
            host = request.getServerName();
        }
        if (host == null || host.isEmpty()) {
            log.warn("支付回调地址推断失败：无法从请求中解析 host（X-Forwarded-Host 和 serverName 均为空），请配置 payment.external-base-url");
            return "";
        }
        // X-Forwarded-Host 可能包含端口（如 example.com:8443），解析分离
        String hostPart = host;
        String portPart = "";
        int colon = host.lastIndexOf(':');
        if (colon > 0 && host.indexOf(']') < colon) {
            hostPart = host.substring(0, colon);
            portPart = host.substring(colon + 1);
        }
        if (hostPart.isEmpty()) {
            log.warn("支付回调地址推断失败：host 解析为空（原始值={}），请配置 payment.external-base-url", host);
            return "";
        }
        // 拒绝本机回环地址：手机扫码无法访问本机的 localhost/127.0.0.1
        if (isLoopbackHost(hostPart)) {
            log.warn("支付回调地址推断失败：推断出的 host 是本机回环地址（{}），手机扫码无法访问。请配置环境变量 PAYMENT_EXTERNAL_BASE_URL 为服务器外网地址（例如 http://1.12.66.249:18080 或 https://your-domain.com）", hostPart);
            return "";
        }
        // 构建 base URL：支持 HTTPS 和 HTTP（HTTP 时记录警告，仍允许使用）
        String candidate;
        if ("https".equalsIgnoreCase(scheme)) {
            candidate = "https://" + hostPart + (portPart.isEmpty() || "443".equals(portPart) ? "" : ":" + portPart);
        } else if ("http".equalsIgnoreCase(scheme)) {
            // 若无显式端口，从 request.getServerPort() 补充（直连场景 scheme=http 时通常需要带上端口）
            if (portPart.isEmpty()) {
                int serverPort = request.getServerPort();
                if (serverPort > 0 && serverPort != 80) {
                    portPart = String.valueOf(serverPort);
                }
            }
            candidate = "http://" + hostPart + (portPart.isEmpty() || "80".equals(portPart) ? "" : ":" + portPart);
            log.warn("支付回调地址推断为 HTTP（非 HTTPS），存在被中间人篡改风险，建议配置 HTTPS 反向代理或显式设置 payment.external-base-url：{}", candidate);
        } else {
            log.warn("支付回调地址推断失败：未知 scheme={}（X-Forwarded-Proto={}），请配置 payment.external-base-url", scheme, request.getHeader("X-Forwarded-Proto"));
            return "";
        }
        return candidate;
    }

    /** 判断 host 是否为本机回环地址（localhost / 127.0.0.1 / 0:0:0:0:0:0:0:1 等） */
    private boolean isLoopbackHost(String host) {
        if (host == null) return false;
        String h = host.trim().toLowerCase(Locale.ROOT);
        return "localhost".equals(h)
                || "127.0.0.1".equals(h)
                || "0.0.0.0".equals(h)
                || "::1".equals(h)
                || "0:0:0:0:0:0:0:1".equals(h);
    }

    private HttpServletRequest currentHttpRequest() {
        try {
            RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
            if (attrs instanceof ServletRequestAttributes servletAttrs) {
                return servletAttrs.getRequest();
            }
        } catch (IllegalStateException ignored) {
            // 非请求线程（如异步/定时任务）调用时无请求上下文
        }
        return null;
    }

    private String firstForwardedValue(String headerValue) {
        if (headerValue == null || headerValue.isBlank()) {
            return null;
        }
        // X-Forwarded-* 可能是逗号分隔的多跳列表，取第一跳（最接近客户端的那一跳由反向代理写入）
        String first = headerValue.split(",")[0].trim();
        return first.isEmpty() ? null : first;
    }

    /**
     * 解析 return_url（用户支付完成后浏览器跳转地址）。
     * 与 notify_url（服务器异步回调）不同，return_url 必须指向用户可访问的前端页面。
     * 优先使用 externalBaseUrl 作为前端基址（去掉后端 /api 前缀），失败时回退到 notify_url 推断出的基址。
     */
    private String resolveReturnUrl(String notifyUrl) {
        String base = inferExternalBaseUrlFromRequest();
        if (base.isEmpty() && externalBaseUrl != null) {
            base = externalBaseUrl.trim();
        }
        if (base.isEmpty() && !isRelativePath(notifyUrl)) {
            // notify_url 是绝对地址时，从中提取基址作为 return_url 基址
            try {
                java.net.URI uri = java.net.URI.create(notifyUrl);
                String host = uri.getHost();
                if (host != null && !host.isEmpty()) {
                    int port = uri.getPort();
                    base = uri.getScheme() + "://" + host + (port > 0 && port != 80 && port != 443 ? ":" + port : "");
                }
            } catch (IllegalArgumentException ignored) {
            }
        }
        if (base.isEmpty()) {
            // 兜底：使用 notify_url 本身（虽然不理想，但保证签名能算出来）
            return notifyUrl;
        }
        return base;
    }

    /**
     * 根据 orderNo 重建易支付参数并返回自动提交的 POST 表单 HTML。
     * 用户扫码后浏览器打开 /api/payment/redirect/{orderNo}，渲染此 HTML 自动 POST 到易支付 submit.php。
     */
    public String buildYipayRedirectHtml(String orderNo) {
        Map<String, Object> order = queryOne(
                "SELECT order_no, title, amount_cent, payment_method, provider_type, payment_config_id, status, expire_time " +
                        "FROM payment_order WHERE order_no=? AND deleted=0", orderNo);
        if (order == null) {
            return errorRedirectHtml("支付订单不存在");
        }
        int status = ((Number) order.getOrDefault("status", 0)).intValue();
        if (status == 1) {
            return alreadyPaidHtml(orderNo);
        }
        if (status >= 2) {
            return errorRedirectHtml("订单已关闭或已过期，请重新发起支付");
        }
        String providerType = text(order.get("provider_type"));
        if (!"yipay".equals(providerType)) {
            return errorRedirectHtml("该订单不是易支付订单，无法跳转");
        }
        Map<String, Object> config = configForOrder(order);
        String gateway = text(config.get("gateway_url"));
        String notifyUrl = text(config.get("notify_url"));
        String resolvedNotifyUrl = resolveNotifyUrl(notifyUrl);
        String resolvedReturnUrl = resolveReturnUrl(notifyUrl);
        String channel = text(order.get("payment_method"));
        long amountCent = ((Number) order.getOrDefault("amount_cent", 0L)).longValue();
        String title = text(order.get("title"));
        Map<String, String> params = new LinkedHashMap<>();
        params.put("pid", text(config.get("merchant_id")));
        params.put("type", "wechat".equals(channel) ? "wxpay" : "alipay");
        params.put("out_trade_no", orderNo);
        params.put("notify_url", resolvedNotifyUrl);
        params.put("return_url", resolvedReturnUrl);
        params.put("name", title);
        params.put("money", BigDecimal.valueOf(amountCent).divide(BigDecimal.valueOf(100)).stripTrailingZeros().toPlainString());
        String sign = signYipay(params, text(config.get("api_key")));
        params.put("sign", sign);
        params.put("sign_type", "MD5");
        String submitUrl = normalizeYipayGateway(gateway);
        return buildAutoSubmitFormHtml(submitUrl, params);
    }

    private String buildAutoSubmitFormHtml(String action, Map<String, String> params) {
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">");
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">");
        html.append("<title>正在跳转到支付页面</title>");
        html.append("<style>");
        html.append("body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;");
        html.append("display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;");
        html.append("background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;}");
        html.append(".box{text-align:center;padding:40px;background:rgba(255,255,255,0.1);");
        html.append("border-radius:16px;backdrop-filter:blur(10px);max-width:90%;}");
        html.append(".spinner{width:48px;height:48px;border:4px solid rgba(255,255,255,0.3);");
        html.append("border-top-color:#fff;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 20px;}");
        html.append("@keyframes spin{to{transform:rotate(360deg);}}");
        html.append("h2{margin:0 0 8px;font-size:20px;font-weight:600;}");
        html.append("p{margin:0;font-size:14px;opacity:0.9;line-height:1.5;}");
        html.append(".pay-btn{display:inline-block;margin-top:24px;padding:14px 32px;");
        html.append("background:#fff;color:#667eea;border:none;border-radius:8px;");
        html.append("font-size:16px;font-weight:600;cursor:pointer;text-decoration:none;}");
        html.append(".pay-btn:hover{background:#f5f5ff;}");
        html.append(".fallback-hint{margin-top:16px;font-size:13px;opacity:0.85;}");
        html.append("</style></head><body>");
        html.append("<div class=\"box\">");
        html.append("<div class=\"spinner\" id=\"spinner\"></div>");
        html.append("<h2>正在跳转到支付页面</h2>");
        html.append("<p>请稍候，即将打开微信/支付宝收银台...</p>");
        html.append("<form id=\"paying\" action=\"").append(escapeHtml(action)).append("\" method=\"post\">");
        for (Map.Entry<String, String> entry : params.entrySet()) {
            html.append("<input type=\"hidden\" name=\"").append(escapeHtml(entry.getKey()))
                    .append("\" value=\"").append(escapeHtml(entry.getValue())).append("\"/>");
        }
        // 显式 submit 按钮：当 CSP 阻止内联 JS 时，用户可手动点击跳转。
        // 浏览器原生表单提交不依赖 JS，CSP 不会阻止。
        html.append("<button type=\"submit\" class=\"pay-btn\" id=\"payBtn\">立即支付</button>");
        html.append("</form>");
        html.append("<p class=\"fallback-hint\">如未自动跳转，请点击上方按钮</p>");
        html.append("</div>");
        // 内联脚本自动提交：若 CSP 允许则自动跳转，若被阻止则用户使用上方按钮手动跳转
        html.append("<script>document.forms['paying'].submit();</script>");
        html.append("</body></html>");
        return html.toString();
    }

    private String alreadyPaidHtml(String orderNo) {
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">");
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">");
        html.append("<title>支付已完成</title>");
        html.append("<style>");
        html.append("body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;");
        html.append("display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;");
        html.append("background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%);color:#fff;}");
        html.append(".box{text-align:center;padding:40px;background:rgba(255,255,255,0.15);");
        html.append("border-radius:16px;backdrop-filter:blur(10px);max-width:90%;}");
        html.append(".icon{font-size:64px;margin-bottom:16px;}");
        html.append("h2{margin:0 0 8px;font-size:22px;font-weight:600;}");
        html.append("p{margin:0;font-size:14px;opacity:0.9;}");
        html.append("</style></head><body>");
        html.append("<div class=\"box\"><div class=\"icon\">✓</div>");
        html.append("<h2>支付已完成</h2>");
        html.append("<p>订单 ").append(escapeHtml(orderNo)).append(" 已支付成功</p>");
        html.append("<p>请返回原页面查看支付结果</p></div>");
        html.append("</body></html>");
        return html.toString();
    }

    private String errorRedirectHtml(String message) {
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">");
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">");
        html.append("<title>支付跳转失败</title>");
        html.append("<style>");
        html.append("body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;");
        html.append("display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;");
        html.append("background:linear-gradient(135deg,#eb3349 0%,#f45c43 100%);color:#fff;}");
        html.append(".box{text-align:center;padding:40px;background:rgba(255,255,255,0.15);");
        html.append("border-radius:16px;backdrop-filter:blur(10px);max-width:90%;}");
        html.append(".icon{font-size:64px;margin-bottom:16px;}");
        html.append("h2{margin:0 0 8px;font-size:22px;font-weight:600;}");
        html.append("p{margin:0;font-size:14px;opacity:0.9;}");
        html.append("</style></head><body>");
        html.append("<div class=\"box\"><div class=\"icon\">⚠</div>");
        html.append("<h2>无法跳转到支付页面</h2>");
        html.append("<p>").append(escapeHtml(message)).append("</p></div>");
        html.append("</body></html>");
        return html.toString();
    }

    private String escapeHtml(String value) {
        if (value == null) return "";
        return value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }

    private String signYipay(Map<String, ?> params, String key) {
        String base = params.entrySet().stream()
                .filter(e -> e.getValue() != null && !String.valueOf(e.getValue()).isBlank())
                .sorted(Map.Entry.comparingByKey())
                .map(e -> e.getKey() + "=" + e.getValue())
                .collect(Collectors.joining("&"));
        return md5Hex(base + key);
    }

    private Map<String, Object> chooseConfig(String channel) {
        String sandboxClause = sandboxModeEnabled ? "" : " AND sandbox=0";
        List<Map<String, Object>> configs;
        try {
            configs = jdbcTemplate.queryForList(
                    "SELECT * FROM payment_config WHERE channel_type=? AND enabled=1 AND deleted=0"
                            + sandboxClause + " ORDER BY id ASC LIMIT 1", normalizeChannel(channel));
        } catch (DataAccessException e) {
            throw new BizException(503, "支付配置暂时无法读取，请稍后重试");
        }
        if (configs.isEmpty()) throw new BizException(503,
                "当前未配置可用的" + ("wechat".equals(channel) ? "微信" : "支付宝") + "支付通道");
        return decryptConfig(configs.get(0));
    }

    private Map<String, Object> configForOrder(Map<String, Object> order) {
        Object configIdValue = first(order, "paymentConfigId", "payment_config_id");
        if (configIdValue == null || text(configIdValue).isBlank()) {
            // 兼容升级前创建的未绑定配置订单。新订单始终保存 payment_config_id。
            return chooseConfig(text(first(order, "paymentMethod", "payment_method")));
        }
        long configId = storedPositiveLong(configIdValue, "订单支付配置 ID");
        Map<String, Object> config = queryOne("SELECT * FROM payment_config WHERE id=? AND deleted=0", configId);
        if (config == null) throw new BizException(503, "该订单绑定的支付配置已不存在，暂时不能继续处理");
        return decryptConfig(config);
    }

    private Map<String, Object> decryptConfig(Map<String, Object> source) {
        Map<String, Object> config = new LinkedHashMap<>(source);
        try {
            config.computeIfPresent("api_key", (key, value) -> cryptoService.decryptIfNeeded(text(value)));
            config.computeIfPresent("private_key", (key, value) -> cryptoService.decryptIfNeeded(text(value)));
        } catch (RuntimeException e) {
            throw new BizException(503, "支付密钥暂时无法解密，请联系管理员核验密钥配置");
        }
        return config;
    }

    private String secretInput(Object submittedValue, Object existingValue) {
        String submitted = text(submittedValue);
        if (submitted.isBlank() || submitted.matches("\\*{4,}")) {
            String existing = text(existingValue);
            return existing.isBlank() ? "" : cryptoService.decryptIfNeeded(existing);
        }
        return submitted;
    }

    private String encryptedSecret(String plainText) {
        return plainText == null || plainText.isBlank() ? "" : cryptoService.encrypt(plainText);
    }

    private void decorateOrder(Map<String, Object> row) {
        int s = storedStatus(row.get("status"), "支付订单状态");
        row.put("statusText", switch (s) { case 1 -> "已支付"; case 2 -> "已关闭"; case 3 -> "支付失败"; case 4 -> "已退款"; default -> "待支付"; });
        row.put("amount", "¥" + BigDecimal.valueOf(storedNonNegativeLong(row.get("amountCent"), "支付订单金额"))
                .movePointLeft(2).stripTrailingZeros().toPlainString());
        try {
            Map<String, Object> config = configForOrder(row);
            row.put("sandbox", config.getOrDefault("sandbox", 0));
            row.put("paymentAvailable", true);
            row.remove("paymentUnavailableReason");
        } catch (BizException e) {
            row.put("sandbox", null);
            row.put("paymentAvailable", false);
            row.put("paymentUnavailableReason", e.getMessage());
        }
    }

    private void isolatePaymentEnvironment(long currentConfigId, String channelType, int enabled, int sandbox) {
        if (enabled != 1) return;
        // 防止测试/生产混用，并保证同一环境同一通道只有一条配置处于启用状态。
        safeUpdate("隔离支付环境失败",
                "UPDATE payment_config SET enabled=0, updated_time=NOW() WHERE deleted=0 AND id<>? AND (sandbox<>? OR (sandbox=? AND channel_type=?))",
                currentConfigId, sandbox, sandbox, channelType);
    }

    private boolean looksLikeSandboxCredential(String... values) {
        for (String value : values) {
            String v = value == null ? "" : value.toLowerCase(Locale.ROOT);
            if (v.contains("sandbox") || v.contains("mock") || v.contains("test")) return true;
        }
        return false;
    }

    private Integer parseStatus(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        if (value instanceof Number) {
            int parsed = ((Number) value).intValue();
            return parsed >= 0 && parsed <= 4 ? parsed : null;
        }
        String s = String.valueOf(value);
        if ("待支付".equals(s) || "pending".equalsIgnoreCase(s)) return 0;
        if ("已支付".equals(s) || "paid".equalsIgnoreCase(s)) return 1;
        if ("已关闭".equals(s) || "closed".equalsIgnoreCase(s)) return 2;
        if ("支付失败".equals(s) || "failed".equalsIgnoreCase(s)) return 3;
        if ("已退款".equals(s) || "refunded".equalsIgnoreCase(s)) return 4;
        try {
            int parsed = Integer.parseInt(s);
            return parsed >= 0 && parsed <= 4 ? parsed : null;
        } catch (Exception e) { return null; }
    }

    private Integer parseEnabled(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        if (value instanceof Boolean) return (Boolean) value ? 1 : 0;
        if (value instanceof Number) {
            int parsed = ((Number) value).intValue();
            return parsed == 0 || parsed == 1 ? parsed : null;
        }
        String s = String.valueOf(value);
        if ("正常".equals(s) || "启用".equals(s) || "1".equals(s) || "true".equalsIgnoreCase(s)) return 1;
        if ("禁用".equals(s) || "0".equals(s) || "false".equalsIgnoreCase(s)) return 0;
        return null;
    }

    private String normalizeOrderType(String type) {
        String t = type == null ? "" : type.trim().toLowerCase(Locale.ROOT);
        if ("vip".equals(t) || "member".equals(t)) return "vip";
        if ("token".equals(t) || "tokens".equals(t)) return "token";
        if ("ad".equals(t) || "advertisement".equals(t) || "advertising".equals(t)) return "ad";
        if ("mall_product".equals(t) || "mallproduct".equals(t)) return "mall_product";
        throw new BizException(400, "非法订单类型");
    }

    /**
     * 标准化 VIP 订单的计费周期。NULL/空/未知值统一视为 month（兼容历史订单与默认行为）。
     */
    private String normalizePeriodType(Object value) {
        if (value == null) return "month";
        String s = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if ("quarter".equals(s) || "season".equals(s)) return "quarter";
        if ("year".equals(s) || "annual".equals(s)) return "year";
        return "month";
    }

    /**
     * 按计费周期推导会员有效期天数：月=30天，季=90天，年=365天。
     */
    private int daysForPeriod(String periodType) {
        if ("quarter".equals(periodType)) return 90;
        if ("year".equals(periodType)) return 365;
        return 30;
    }

    private String periodLabel(String periodType) {
        if ("quarter".equals(periodType)) return "季度";
        if ("year".equals(periodType)) return "年度";
        return "月度";
    }

    /**
     * 按计费周期从套餐记录中取对应价格（分）。month→price_month_cent，quarter→price_quarter_cent，year→price_year_cent。
     */
    private long resolveVipPriceCent(Map<String, Object> plan, String periodType) {
        if ("quarter".equals(periodType)) {
            return storedNonNegativeLong(plan.get("price_quarter_cent"), "季度价格");
        }
        if ("year".equals(periodType)) {
            return storedNonNegativeLong(plan.get("price_year_cent"), "年度价格");
        }
        return storedNonNegativeLong(plan.get("price_month_cent"), "月度价格");
    }

    private String normalizeChannel(String channel) {
        String c = channel == null ? "" : channel.trim().toLowerCase(Locale.ROOT);
        if ("wx".equals(c) || "weixin".equals(c)) c = "wechat";
        if ("ali".equals(c)) c = "alipay";
        if ("balance".equals(c) || "wallet".equals(c)) c = "balance";
        if (!"wechat".equals(c) && !"alipay".equals(c) && !"balance".equals(c)) throw new BizException(400, "非法支付方式");
        return c;
    }

    private String normalizeProvider(String provider) {
        String p = provider == null || provider.isBlank() ? "official" : provider.trim().toLowerCase(Locale.ROOT);
        if ("easy-pay".equals(p) || "epay".equals(p)) p = "yipay";
        if (!"official".equals(p) && !"yipay".equals(p)) throw new BizException(400, "非法支付提供方");
        return p;
    }

    private String newOrderNo(String prefix) {
        String normalized = prefix == null ? "" : prefix.trim().toLowerCase(Locale.ROOT);
        String orderPrefix = switch (normalized) {
            case "vip" -> "VIP";
            case "ad", "advertisement", "advertising" -> "ADP";
            case "mall_product" -> "MAL";
            default -> "TOK";
        };
        return orderPrefix + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + UUID.randomUUID().toString().replace("-", "").substring(0, 20).toUpperCase(Locale.ROOT);
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args);
            return rows.isEmpty() ? null : rows.get(0);
        } catch (DataAccessException e) {
            throw new BizException(503, "支付数据暂时无法读取，请稍后重试");
        }
    }

    private Object first(Map<String, Object> data, String... keys) {
        if (data == null) return null;
        for (String k : keys) if (data.containsKey(k)) return data.get(k);
        return null;
    }

    private String required(Map<String, Object> data, String key, String msg) {
        Object value = first(data, key);
        if (value == null || String.valueOf(value).isBlank()) throw new BizException(400, msg);
        return String.valueOf(value).trim();
    }

    private String boundedRequired(Map<String, Object> data, String key, String msg, int maxLength) {
        String value = required(data, key, msg);
        if (value.length() > maxLength) throw new BizException(400, msg + "，且不能超过 " + maxLength + " 个字符");
        return value;
    }

    private String boundedOptional(Object value, String field, int maxLength) {
        String normalized = text(value);
        if (normalized.length() > maxLength) throw new BizException(400, field + "不能超过 " + maxLength + " 个字符");
        return normalized;
    }

    private String text(Object value) { return value == null ? "" : String.valueOf(value).trim(); }

    private Long parseNullableLong(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        return requireWholeNumber(value, "ID", 1, Long.MAX_VALUE);
    }

    /** 安全转 Long（null/空/异常返回 null），用于解析 preview 返回的不确定字段。 */
    private Long toLong(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        try {
            if (value instanceof Number n) return n.longValue();
            return new BigDecimal(String.valueOf(value).trim()).longValueExact();
        } catch (RuntimeException e) {
            return null;
        }
    }

    /** 安全转 int（null/空/异常返回 0），用于解析 preview 返回的不确定字段。 */
    private int toInt(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return 0;
        try {
            if (value instanceof Number n) return n.intValue();
            return new BigDecimal(String.valueOf(value).trim()).intValueExact();
        } catch (RuntimeException e) {
            return 0;
        }
    }

    private long requireWholeNumber(Object value, String field, long min, long max) {
        if (value == null || String.valueOf(value).isBlank()) throw new BizException(400, field + "不能为空");
        try {
            BigDecimal decimal = value instanceof BigDecimal bd ? bd : new BigDecimal(String.valueOf(value).trim());
            long parsed = decimal.longValueExact();
            if (parsed < min || parsed > max) throw new BizException(400, field + "超出允许范围");
            return parsed;
        } catch (BizException e) {
            throw e;
        } catch (RuntimeException e) {
            throw new BizException(400, field + "必须是合法整数");
        }
    }

    private long optionalWholeNumber(Object value, String field, long min, long max, long defaultValue) {
        if (value == null || String.valueOf(value).isBlank()) return defaultValue;
        return requireWholeNumber(value, field, min, max);
    }

    private long storedPositiveLong(Object value, String field) {
        return storedLong(value, field, 1, Long.MAX_VALUE);
    }

    private long storedNonNegativeLong(Object value, String field) {
        return storedLong(value, field, 0, Long.MAX_VALUE);
    }

    private Long storedNullablePositiveLong(Object value, String field) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        return storedPositiveLong(value, field);
    }

    private long storedLong(Object value, String field, long min, long max) {
        try {
            if (value == null || String.valueOf(value).isBlank()) throw new ArithmeticException();
            BigDecimal decimal = value instanceof BigDecimal bd ? bd : new BigDecimal(String.valueOf(value).trim());
            long parsed = decimal.longValueExact();
            if (parsed < min || parsed > max) throw new ArithmeticException();
            return parsed;
        } catch (RuntimeException e) {
            throw new BizException(503, field + "数据异常，请联系管理员核验");
        }
    }

    private int storedStatus(Object value, String field) {
        long status = storedLong(value, field, 0, 4);
        return (int) status;
    }

    private int optionalEnabled(Object value, int defaultValue, String field) {
        if (value == null || String.valueOf(value).isBlank()) return defaultValue;
        Integer parsed = parseEnabled(value);
        if (parsed == null) throw new BizException(400, field + "只能为启用或禁用");
        return parsed;
    }

    private long parseMoneyCent(Map<String, Object> data) {
        Object cent = first(data, "priceCent", "price_cent", "amountCent", "amount_cent");
        if (cent != null && !String.valueOf(cent).isBlank()) {
            return requireWholeNumber(cent, "金额（分）", 1, MAX_PAYMENT_AMOUNT_CENT);
        }
        return yuanToCent(first(data, "priceYuan", "amountYuan", "price", "amount"));
    }

    private long yuanToCent(Object value) {
        if (value == null || String.valueOf(value).isBlank()) throw new BizException(400, "金额不能为空");
        try {
            String normalized = String.valueOf(value).replace("¥", "").replace("元", "").trim();
            long cents = new BigDecimal(normalized).movePointRight(2).longValueExact();
            if (cents < 0 || cents > MAX_PAYMENT_AMOUNT_CENT) throw new BizException(400, "金额超出允许范围");
            return cents;
        } catch (BizException e) {
            throw e;
        } catch (RuntimeException e) {
            throw new BizException(400, "金额最多保留两位小数");
        }
    }

    private String normalizeSubscriptionTarget(String value) {
        String target = text(value).toLowerCase(Locale.ROOT);
        if (target.isBlank()) target = "user_account";
        if (!"user_account".equals(target) && !"xianyu_account".equals(target)) {
            throw new BizException(400, "非法会员权益目标");
        }
        return target;
    }

    private Long validateSubscriptionTarget(String targetType, Long targetId, long tenantId, long userId) {
        if ("user_account".equals(targetType)) {
            if (targetId != null && targetId != userId) throw new BizException(404, "会员权益目标不存在");
            return null;
        }
        if (targetId == null) throw new BizException(400, "请选择要开通会员的闲鱼账号");
        Map<String, Object> account = queryOne(
                "SELECT id FROM xianyu_account WHERE id=? AND tenant_id=? AND user_id=? AND deleted=0",
                targetId, tenantId, userId);
        if (account == null) throw new BizException(404, "会员权益目标不存在");
        return targetId;
    }

    private int safeUpdate(String unavailableMessage, String sql, Object... args) {
        try {
            return jdbcTemplate.update(sql, args);
        } catch (DataAccessException e) {
            // 记录详细错误信息以便定位根因（之前只返回模糊的"请稍后重试"，无法排查）
            log.error("数据库写入失败 unavailableMessage={} sql={} args={} rootCause={}",
                    unavailableMessage, sql, java.util.Arrays.toString(args), e.getMessage(), e);
            throw new BizException(503, unavailableMessage + "，请稍后重试");
        }
    }

    private void requireSingleWrite(String unavailableMessage, String sql, Object... args) {
        int affected;
        try {
            affected = jdbcTemplate.update(sql, args);
        } catch (DataAccessException e) {
            log.error("数据库写入失败(requireSingleWrite) unavailableMessage={} sql={} args={} rootCause={}",
                    unavailableMessage, sql, java.util.Arrays.toString(args), e.getMessage(), e);
            throw new BizException(503, unavailableMessage + "，请稍后重试");
        }
        if (affected != 1) {
            log.error("数据库未确认唯一写入 unavailableMessage={} affected={} sql={} args={}",
                    unavailableMessage, affected, sql, java.util.Arrays.toString(args));
            throw new BizException(503, unavailableMessage + "，数据库未确认唯一写入");
        }
    }

    private String urlEncode(String value) {
        return java.net.URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private String md5Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(32);
            for (byte b : digest) {
                sb.append(String.format("%02x", b & 0xff));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("MD5 algorithm not available", e);
        }
    }

    /**
     * 确保易支付网关地址包含 submit.php 路径
     */
    private String normalizeYipayGateway(String gateway) {
        if (!StringUtils.hasText(gateway)) return gateway;
        String g = gateway.trim();
        if (g.contains("/submit.php")) return g;
        if (g.endsWith("/")) return g + "submit.php";
        return g + "/submit.php";
    }
}
