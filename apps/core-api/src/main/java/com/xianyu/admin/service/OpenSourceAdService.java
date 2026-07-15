package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.AdminContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class OpenSourceAdService {
    private static final Logger log = LoggerFactory.getLogger(OpenSourceAdService.class);

    private static final String TEXT_MODULE_KEY = "open-source-text-ads";
    private static final String PLAN_MODULE_KEY = "open-source-ad-plans";
    private static final String CONFIG_STATUS = "config";
    private static final String DEFAULT_SITE_CODE = "open-source";
    private static final String DEFAULT_SITE_NAME = "开源版";
    private static final Set<String> ALLOWED_POSITION_TYPES = Set.of("home_carousel", "sidebar_text");
    private static final Set<String> ALLOWED_APPLICATION_STATUS = Set.of(
            "pending_payment",
            "pending",
            "approved",
            "rejected",
            "online",
            "offline"
    );
    private static final DateTimeFormatter APPLICATION_NO_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    private static final Pattern PRICE_PATTERN = Pattern.compile("(\\d+(?:\\.\\d+)?)");

    private final JdbcTemplate jdbcTemplate;
    private final TenantSupportService tenantSupportService;
    private final OpenSourceContentService contentService;
    private final PaymentService paymentService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OpenSourceAdService(
            JdbcTemplate jdbcTemplate,
            TenantSupportService tenantSupportService,
            OpenSourceContentService contentService,
            PaymentService paymentService
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.tenantSupportService = tenantSupportService;
        this.contentService = contentService;
        this.paymentService = paymentService;
    }

    public List<Map<String, Object>> listAllTextAds() {
        return loadTextAds();
    }

    public List<Map<String, Object>> listEnabledTextAds() {
        return loadTextAds().stream()
                .filter(item -> booleanValue(item.get("enabled"), true))
                .sorted((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)))
                .limit(10)
                .toList();
    }

    @Transactional
    public Map<String, Object> saveTextAd(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "广告内容不能为空");
        List<Map<String, Object>> items = loadTextAdsForUpdate();
        long nextId = nextId(items);
        Map<String, Object> normalized = normalizeTextAd(input, nextId, null);
        items.add(normalized);
        saveListConfig(TEXT_MODULE_KEY, items);
        return normalized;
    }

    @Transactional
    public Map<String, Object> updateTextAd(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "广告内容不能为空");
        List<Map<String, Object>> items = loadTextAdsForUpdate();
        long id = number(input.get("id"), 0L);
        if (id <= 0) {
            throw new BizException(400, "文字广告 ID 不能为空");
        }
        for (int index = 0; index < items.size(); index += 1) {
            Map<String, Object> current = items.get(index);
            if (number(current.get("id"), 0L) == id) {
                Map<String, Object> merged = new LinkedHashMap<>(current);
                merged.putAll(input);
                Map<String, Object> normalized = normalizeTextAd(merged, id, text(current.get("createdAt")));
                items.set(index, normalized);
                saveListConfig(TEXT_MODULE_KEY, items);
                return normalized;
            }
        }
        throw new BizException(404, "文字广告不存在");
    }

    @Transactional
    public Map<String, Object> deleteTextAd(long id) {
        if (id <= 0) throw new BizException(400, "文字广告 ID 非法");
        List<Map<String, Object>> items = loadTextAdsForUpdate();
        for (int index = 0; index < items.size(); index += 1) {
            Map<String, Object> current = items.get(index);
            if (number(current.get("id"), 0L) == id) {
                Map<String, Object> removed = items.remove(index);
                saveListConfig(TEXT_MODULE_KEY, items);
                return removed;
            }
        }
        throw new BizException(404, "文字广告不存在");
    }

    public List<Map<String, Object>> listAllAdPlans() {
        return loadAdPlans();
    }

    public List<Map<String, Object>> listEnabledAdPlans() {
        return loadAdPlans().stream()
                .filter(item -> booleanValue(item.get("enabled"), true))
                .sorted((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)))
                .toList();
    }

    public List<Map<String, Object>> listEnabledPaymentMethods() {
        return paymentService.enabledMethods();
    }

    @Transactional
    public Map<String, Object> saveAdPlan(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "广告套餐内容不能为空");
        List<Map<String, Object>> items = loadAdPlansForUpdate();
        long nextId = nextId(items);
        Map<String, Object> normalized = normalizeAdPlan(input, nextId, null);
        ensureUniquePlanCode(items, normalized, nextId);
        items.add(normalized);
        saveListConfig(PLAN_MODULE_KEY, items);
        return normalized;
    }

    @Transactional
    public Map<String, Object> updateAdPlan(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "广告套餐内容不能为空");
        List<Map<String, Object>> items = loadAdPlansForUpdate();
        long id = number(input.get("id"), 0L);
        if (id <= 0) {
            throw new BizException(400, "广告套餐 ID 不能为空");
        }
        for (int index = 0; index < items.size(); index += 1) {
            Map<String, Object> current = items.get(index);
            if (number(current.get("id"), 0L) == id) {
                Map<String, Object> merged = new LinkedHashMap<>(current);
                merged.putAll(input);
                Map<String, Object> normalized = normalizeAdPlan(merged, id, text(current.get("createdAt")));
                ensureUniquePlanCode(items, normalized, id);
                items.set(index, normalized);
                saveListConfig(PLAN_MODULE_KEY, items);
                return normalized;
            }
        }
        throw new BizException(404, "广告套餐不存在");
    }

    @Transactional
    public Map<String, Object> deleteAdPlan(long id) {
        if (id <= 0) throw new BizException(400, "广告套餐 ID 非法");
        List<Map<String, Object>> items = loadAdPlansForUpdate();
        for (int index = 0; index < items.size(); index += 1) {
            Map<String, Object> current = items.get(index);
            if (number(current.get("id"), 0L) == id) {
                Map<String, Object> removed = items.remove(index);
                saveListConfig(PLAN_MODULE_KEY, items);
                return removed;
            }
        }
        throw new BizException(404, "广告套餐不存在");
    }

    public PageResult<Map<String, Object>> pageApplications(int current, int size, String status, String positionType, String keyword) {
        return pageApplications(current, size, status, positionType, keyword, DEFAULT_SITE_CODE);
    }

    public PageResult<Map<String, Object>> pageSiteApplications(int current, int size, String siteCode) {
        return pageApplications(current, size, null, null, null, normalizeSiteCode(siteCode), null);
    }

    /**
     * Query applications for a specific open-source instance.
     * <p>
     * When the instance token is present, applications are filtered by
     * {@code instance_token} so each open-source deployment only sees its own
     * records. When the token is blank (older open-source builds), the query
     * falls back to filtering by {@code site_code}.
     */
    public PageResult<Map<String, Object>> pageSiteApplications(int current, int size, String siteCode, String instanceToken) {
        return pageApplications(current, size, null, null, null, normalizeSiteCode(siteCode), instanceToken);
    }

    public Map<String, Object> getApplicationDetail(long id) {
        Map<String, Object> row = queryApplicationById(id, null);
        if (row == null) {
            throw new BizException(404, "广告申请不存在");
        }
        return normalizeApplicationRow(row);
    }

    @Transactional
    public Map<String, Object> createApplication(OpenSourceBridgeAuthService.OpenSourceSiteContext site, Map<String, Object> body) {
        if (body == null) throw new BizException(400, "广告申请内容不能为空");
        String requestedPositionType = normalizePositionType(body.get("positionType"));
        String planCode = text(body.get("planCode"));
        Map<String, Object> plan = resolvePlan(requestedPositionType, planCode);
        if (plan == null) {
            throw new BizException(503, "当前广告位尚未配置可用套餐");
        }

        String positionType = normalizePositionType(plan.get("positionType"));
        String positionLabel = textOr(plan.get("positionLabel"), positionLabel(positionType));
        String planTitle = textOr(plan.get("title"), text(body.get("planTitle")));
        String contactValue = requireText(body, "contact", "Contact is required");
        String landingUrl = validateAdUrl(requireText(body, "landingUrl", "落地页地址不能为空"), "落地页地址");
        String title = positionType.equals("sidebar_text")
                ? requireText(body, "title", "Ad title is required")
                : textOr(body.get("title"), textOr(planTitle, "首页轮播广告"));
        String creativeImageUrl = positionType.equals("home_carousel")
                ? validateAdUrl(requireText(body, "creativeImageUrl", "轮播广告图片不能为空"), "轮播广告图片地址")
                : text(body.get("creativeImageUrl"));
        if (!creativeImageUrl.isBlank() && !positionType.equals("home_carousel")) {
            creativeImageUrl = validateAdUrl(creativeImageUrl, "广告图片地址");
        }
        String companyName = requireText(body, "companyName", "公司或主体名称不能为空");

        long tenantId = tenantId();
        int inserted = jdbcTemplate.update(
                "INSERT INTO open_source_ad_application(" +
                        "tenant_id, site_code, site_name, instance_token, application_no, position_type, position_label, plan_code, plan_title, " +
                        "company_name, contact_name, contact_phone, contact_wechat, contact_value, title, landing_url, creative_image_url, budget, start_date, duration_days, remark, " +
                        "status, status_message, payment_order_no, published_record_id, published_record_type, created_time, updated_time, deleted" +
                        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId,
                normalizeSiteCode(site == null ? null : site.siteCode()),
                textOr(site == null ? null : site.siteName(), DEFAULT_SITE_NAME),
                trimToNull(site == null ? null : site.instanceToken(), 120),
                "__PENDING__",
                positionType,
                positionLabel,
                trimToNull(planCode, 80),
                trimToNull(planTitle, 160),
                trimToLength(companyName, 200),
                trimToLength(textOr(body.get("contactName"), contactValue), 80),
                trimToNull(body.get("contactPhone"), 80),
                trimToNull(body.get("contactWechat"), 80),
                trimToLength(contactValue, 200),
                trimToLength(title, 200),
                trimToLength(landingUrl, 500),
                trimToNull(creativeImageUrl, 500),
                trimToNull(body.get("budget"), 80),
                trimToNull(body.get("startDate"), 40),
                trimToNull(body.get("durationDays"), 40),
                trimToNull(body.get("remark"), 5000),
                "pending_payment",
                defaultStatusMessage("pending_payment"),
                null,
                null,
                null
        );
        if (inserted != 1) throw new BizException(503, "广告申请写入失败");
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (id == null) {
            throw new BizException(503, "广告申请编号无法确认");
        }
        String applicationNo = "OSA" + LocalDateTime.now().format(APPLICATION_NO_FORMAT) + String.format("%04d", id);
        int numberUpdated = jdbcTemplate.update(
                "UPDATE open_source_ad_application SET application_no=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                applicationNo,
                id,
                tenantId
        );
        if (numberUpdated != 1) throw new BizException(503, "广告申请编号写入失败");
        return getApplicationDetail(id);
    }

    @Transactional
    public Map<String, Object> createApplicationPaymentOrder(
            long id,
            OpenSourceBridgeAuthService.OpenSourceSiteContext site,
            Map<String, Object> body,
            String clientIp
    ) {
        if (body == null) throw new BizException(400, "支付订单参数不能为空");
        Map<String, Object> row = queryApplicationById(id, normalizeSiteCode(site == null ? null : site.siteCode()));
        if (row == null) {
            throw new BizException(404, "广告申请不存在");
        }

        String paymentMethod = normalizePaymentMethod(body.get("paymentMethod"));
        Map<String, Object> normalized = normalizeApplicationRow(row);
        if ("paid".equals(text(normalized.get("paymentStatus")))) {
            String existingOrderNo = text(normalized.get("paymentOrderNo"));
            if (!existingOrderNo.isBlank()) {
                return paymentService.orderDetail(existingOrderNo);
            }
        }

        String existingOrderNo = text(row.get("paymentOrderNo"));
        if (!existingOrderNo.isBlank()) {
            Map<String, Object> existingOrder = queryOne(
                    "SELECT order_no AS orderNo, payment_method AS paymentMethod, status, expire_time AS expireTime " +
                            "FROM payment_order WHERE order_no=? AND deleted=0",
                    existingOrderNo
            );
            if (existingOrder != null
                    && number(existingOrder.get("status"), -1) == 0
                    && !isExpired(existingOrder.get("expireTime"))
                    && paymentMethod.equalsIgnoreCase(text(existingOrder.get("paymentMethod")))) {
                return paymentService.orderDetail(existingOrderNo);
            }
        }

        Map<String, Object> plan = resolvePlan(text(row.get("positionType")), text(row.get("planCode")));
        if (plan == null) {
            throw new BizException(503, "广告套餐配置已失效，暂时无法创建支付订单");
        }
        long amountCent = number(plan.get("priceCent"), 0L);
        if (amountCent <= 0) {
            throw new BizException(503, "广告套餐价格配置无效，暂时无法创建支付订单");
        }

        String title = buildPaymentTitle(normalized);
        Map<String, Object> order = paymentService.createBridgeAdOrder(
                tenantId(),
                id,
                title,
                amountCent,
                paymentMethod,
                clientIp
        );
        int orderLinked = jdbcTemplate.update(
                "UPDATE open_source_ad_application SET payment_order_no=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                trimToLength(text(order.get("orderNo")), 80),
                id,
                tenantId()
        );
        if (orderLinked != 1) throw new BizException(409, "广告申请状态已变化，请重新查询");
        return order;
    }

    public Map<String, Object> getApplicationPaymentOrder(
            String orderNo,
            OpenSourceBridgeAuthService.OpenSourceSiteContext site
    ) {
        if (orderNo == null || orderNo.isBlank()) throw new BizException(400, "支付订单号不能为空");
        Map<String, Object> row = queryApplicationByOrderNo(orderNo, normalizeSiteCode(site == null ? null : site.siteCode()));
        if (row == null) {
            throw new BizException(404, "广告支付订单不存在");
        }
        return paymentService.orderDetail(orderNo);
    }

    @Transactional
    public Map<String, Object> closeApplicationPaymentOrder(
            String orderNo,
            OpenSourceBridgeAuthService.OpenSourceSiteContext site
    ) {
        if (orderNo == null || orderNo.isBlank()) throw new BizException(400, "支付订单号不能为空");
        Map<String, Object> row = queryApplicationByOrderNo(orderNo, normalizeSiteCode(site == null ? null : site.siteCode()));
        if (row == null) {
            throw new BizException(404, "广告支付订单不存在");
        }
        return paymentService.closeBridgeOrder(orderNo);
    }

    @Transactional
    public Map<String, Object> mockPayApplicationPaymentOrder(
            String orderNo,
            OpenSourceBridgeAuthService.OpenSourceSiteContext site
    ) {
        if (orderNo == null || orderNo.isBlank()) throw new BizException(400, "支付订单号不能为空");
        Map<String, Object> row = queryApplicationByOrderNo(orderNo, normalizeSiteCode(site == null ? null : site.siteCode()));
        if (row == null) {
            throw new BizException(404, "广告支付订单不存在");
        }
        return paymentService.mockPayBridgeOrder(orderNo);
    }

    @Transactional
    public Map<String, Object> updateApplicationStatus(long id, Map<String, Object> body) {
        if (id <= 0) throw new BizException(400, "广告申请 ID 非法");
        if (body == null || body.get("status") == null || text(body.get("status")).isBlank()) {
            throw new BizException(400, "广告申请状态不能为空");
        }
        Map<String, Object> raw = queryApplicationById(id, null);
        if (raw == null) {
            throw new BizException(404, "广告申请不存在");
        }

        String status = normalizeStatus(body.get("status"));
        if (!ALLOWED_APPLICATION_STATUS.contains(status)) {
            throw new BizException(400, "不支持的广告申请状态");
        }

        Map<String, Object> normalized = normalizeApplicationRow(raw);
        String paymentStatus = text(normalized.get("paymentStatus"));
        String currentStatus = text(normalized.get("status"));
        validateStatusTransition(currentStatus, status);
        if (displayStatus(status) && !"paid".equals(paymentStatus)) {
            throw new BizException(409, "广告申请尚未支付，不能上线投放");
        }

        long publishedRecordId = number(raw.get("publishedRecordId"), 0L);
        String publishedRecordType = text(raw.get("publishedRecordType"));
        boolean statusChanged = !status.equals(currentStatus);
        if (statusChanged && displayStatus(status)) {
            Map<String, Object> publishResult = publishApplication(normalized);
            publishedRecordId = number(publishResult.get("id"), publishedRecordId);
            publishedRecordType = textOr(publishResult.get("publishedType"), publishedRecordType);
        } else if (statusChanged && publishedRecordId > 0 && !displayStatus(status)) {
            unpublishApplication(normalized);
        }

        String statusMessage = textOr(body.get("statusMessage"), defaultStatusMessage(status));
        Long adminId = AdminContext.userId();
        String adminName = textOr(AdminContext.username(), "system");
        int updated = jdbcTemplate.update(
                "UPDATE open_source_ad_application SET status=?, status_message=?, reviewer_user_id=?, reviewer_username=?, reviewed_time=NOW(), " +
                        "published_record_id=?, published_record_type=?, updated_time=NOW() WHERE id=? AND tenant_id=? AND deleted=0",
                status,
                trimToLength(statusMessage, 255),
                adminId == null ? 0L : adminId,
                trimToLength(adminName, 120),
                publishedRecordId <= 0 ? null : publishedRecordId,
                trimToNull(publishedRecordType, 40),
                id,
                tenantId()
        );
        if (updated != 1) throw new BizException(409, "广告申请状态已变化，请重新查询");
        return getApplicationDetail(id);
    }

    private PageResult<Map<String, Object>> pageApplications(int current, int size, String status, String positionType, String keyword, String siteCode) {
        return pageApplications(current, size, status, positionType, keyword, siteCode, null);
    }

    private PageResult<Map<String, Object>> pageApplications(int current, int size, String status, String positionType, String keyword, String siteCode, String instanceToken) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;

        StringBuilder where = new StringBuilder(" WHERE a.tenant_id=? AND a.deleted=0 AND a.site_code=?");
        List<Object> args = new ArrayList<>();
        args.add(tenantId());
        args.add(normalizeSiteCode(siteCode));

        // When the instance token is present, filter by instance_token so each
        // open-source deployment only sees its own advertising applications.
        // Blank token (older builds) falls back to site_code-only filtering.
        if (instanceToken != null && !instanceToken.isBlank()) {
            where.append(" AND a.instance_token=?");
            args.add(instanceToken.trim());
        }

        if (status != null && !status.isBlank()) {
            String normalizedStatus = normalizeStatus(status);
            switch (normalizedStatus) {
                case "pending" -> where.append(" AND (a.status='pending' OR (a.status='pending_payment' AND po.status=1))");
                case "pending_payment" -> where.append(" AND a.status='pending_payment' AND (po.status IS NULL OR po.status<>1)");
                default -> {
                    where.append(" AND a.status=?");
                    args.add(normalizedStatus);
                }
            }
        }

        if (positionType != null && !positionType.isBlank()) {
            where.append(" AND a.position_type=?");
            args.add(normalizePositionType(positionType));
        }

        if (keyword != null && !keyword.isBlank()) {
            String kw = "%" + keyword.trim() + "%";
            where.append(" AND (" +
                    "a.application_no LIKE ? OR a.title LIKE ? OR a.contact_value LIKE ? OR a.contact_name LIKE ? OR a.contact_phone LIKE ? OR a.contact_wechat LIKE ?" +
                    ")");
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
        }

        String fromSql = " FROM open_source_ad_application a " +
                "LEFT JOIN payment_order po ON po.order_no=a.payment_order_no AND po.deleted=0";

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*)" + fromSql + where,
                Long.class,
                args.toArray()
        );

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                selectApplicationColumns() + fromSql + where + " ORDER BY a.created_time DESC LIMIT ? OFFSET ?",
                pageArgs.toArray()
        );
        List<Map<String, Object>> normalized = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            normalized.add(normalizeApplicationRow(row));
        }
        return new PageResult<>(normalized, safeCurrent, safeSize, total == null ? 0 : total);
    }

    private List<Map<String, Object>> loadTextAds() {
        return normalizeTextAds(loadListConfig(TEXT_MODULE_KEY, false));
    }

    private List<Map<String, Object>> loadTextAdsForUpdate() {
        return normalizeTextAds(loadListConfig(TEXT_MODULE_KEY, true));
    }

    private List<Map<String, Object>> normalizeTextAds(List<Map<String, Object>> rows) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (int index = 0; index < rows.size(); index += 1) {
            Map<String, Object> row = rows.get(index);
            result.add(normalizeTextAd(row, number(row.get("id"), index + 1L), text(row.get("createdAt"))));
        }
        result.sort((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)));
        return result;
    }

    private List<Map<String, Object>> loadAdPlans() {
        return normalizeAdPlans(loadListConfig(PLAN_MODULE_KEY, false));
    }

    private List<Map<String, Object>> loadAdPlansForUpdate() {
        return normalizeAdPlans(loadListConfig(PLAN_MODULE_KEY, true));
    }

    private List<Map<String, Object>> normalizeAdPlans(List<Map<String, Object>> rows) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (int index = 0; index < rows.size(); index += 1) {
            Map<String, Object> row = rows.get(index);
            result.add(normalizeAdPlan(row, number(row.get("id"), index + 1L), text(row.get("createdAt"))));
        }
        result.sort((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)));
        return result;
    }

    private Map<String, Object> publishApplication(Map<String, Object> application) {
        String positionType = normalizePositionType(application.get("positionType"));
        return positionType.equals("home_carousel")
                ? publishCarouselApplication(application)
                : publishTextApplication(application);
    }

    private Map<String, Object> publishCarouselApplication(Map<String, Object> application) {
        long applicationId = number(application.get("id"), 0L);
        long publishedRecordId = number(application.get("publishedRecordId"), 0L);
        String imageUrl = text(application.get("creativeImageUrl"));
        if (imageUrl.isBlank()) {
            throw new BizException(400, "轮播广告图片不能为空");
        }

        String title = textOr(application.get("title"), text(application.get("planTitle")));
        String description = buildPublishDescription(application);
        String linkUrl = textOr(application.get("landingUrl"), "#/ad-application");
        int sortOrder = number(application.get("sortOrder"), 100 + (int) applicationId);
        Map<String, Object> payload = linkedMapOf(
                "title", title,
                "description", description,
                "imageUrl", imageUrl,
                "linkUrl", linkUrl,
                "sortOrder", sortOrder,
                "enabled", true,
                "coverItems", List.of(linkedMapOf(
                        "id", "ad-cover-" + applicationId,
                        "title", title,
                        "description", description,
                        "imageUrl", imageUrl,
                        "linkUrl", linkUrl,
                        "sourceType", imageUrl.startsWith("http") ? "url" : "upload",
                        "sortOrder", 0,
                        "enabled", true
                ))
        );
        Map<String, Object> published = publishedRecordId > 0
                ? contentService.updateHomeCarousel(withId(payload, publishedRecordId))
                : contentService.saveHomeCarousel(payload);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", published.get("id"));
        result.put("publishedType", "home_carousel");
        return result;
    }

    private Map<String, Object> publishTextApplication(Map<String, Object> application) {
        long applicationId = number(application.get("id"), 0L);
        long publishedRecordId = number(application.get("publishedRecordId"), 0L);
        String title = textOr(application.get("title"), text(application.get("planTitle")));
        String contact = textOr(application.get("contactValue"), text(application.get("contactName")));
        String summary = contact.isBlank()
                ? "点击查看广告详情与投放内容。"
                : "点击查看详情，联系投放方：" + contact;
        Map<String, Object> payload = linkedMapOf(
                "title", title,
                "summary", summary,
                "badge", "合作广告",
                "linkUrl", textOr(application.get("landingUrl"), "#/ad-application"),
                "enabled", true,
                "sortOrder", number(application.get("sortOrder"), 100 + (int) applicationId)
        );
        Map<String, Object> published = publishedRecordId > 0
                ? updateTextAd(withId(payload, publishedRecordId))
                : saveTextAd(payload);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", published.get("id"));
        result.put("publishedType", "sidebar_text");
        return result;
    }

    private void unpublishApplication(Map<String, Object> application) {
        long publishedRecordId = number(application.get("publishedRecordId"), 0L);
        if (publishedRecordId <= 0) {
            return;
        }
        String publishedRecordType = textOr(application.get("publishedRecordType"), text(application.get("positionType")));
        try {
            if ("home_carousel".equalsIgnoreCase(publishedRecordType)) {
                contentService.updateHomeCarousel(linkedMapOf("id", publishedRecordId, "enabled", false));
            } else {
                updateTextAd(linkedMapOf("id", publishedRecordId, "enabled", false));
            }
        } catch (Exception ex) {
            log.warn("disable published open-source ad failed: applicationId={}, publishedRecordId={}, errorType={}", application.get("id"), publishedRecordId, ex.getClass().getSimpleName());
        }
    }

    private String buildPublishDescription(Map<String, Object> application) {
        String contact = textOr(application.get("contactValue"), text(application.get("contactName")));
        if (contact.isBlank()) {
            return "商业版后台审核通过后自动展示。";
        }
        return "商业版后台审核通过，联系投放方：" + contact;
    }

    private Map<String, Object> queryApplicationById(long id, String siteCode) {
        StringBuilder sql = new StringBuilder(selectApplicationColumns())
                .append(" FROM open_source_ad_application a ")
                .append("LEFT JOIN payment_order po ON po.order_no=a.payment_order_no AND po.deleted=0 ")
                .append("WHERE a.id=? AND a.tenant_id=? AND a.deleted=0");
        List<Object> args = new ArrayList<>();
        args.add(id);
        args.add(tenantId());
        if (siteCode != null && !siteCode.isBlank()) {
            sql.append(" AND a.site_code=?");
            args.add(siteCode);
        }
        sql.append(" LIMIT 1");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql.toString(), args.toArray());
        return rows.isEmpty() ? null : rows.get(0);
    }

    private Map<String, Object> queryApplicationByOrderNo(String orderNo, String siteCode) {
        StringBuilder sql = new StringBuilder(selectApplicationColumns())
                .append(" FROM open_source_ad_application a ")
                .append("LEFT JOIN payment_order po ON po.order_no=a.payment_order_no AND po.deleted=0 ")
                .append("WHERE a.payment_order_no=? AND a.tenant_id=? AND a.deleted=0");
        List<Object> args = new ArrayList<>();
        args.add(orderNo);
        args.add(tenantId());
        if (siteCode != null && !siteCode.isBlank()) {
            sql.append(" AND a.site_code=?");
            args.add(siteCode);
        }
        sql.append(" LIMIT 1");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql.toString(), args.toArray());
        return rows.isEmpty() ? null : rows.get(0);
    }

    private String selectApplicationColumns() {
        return "SELECT " +
                "a.id, a.tenant_id AS tenantId, a.site_code AS siteCode, a.site_name AS siteName, a.application_no AS applicationNo, " +
                "a.position_type AS positionType, a.position_label AS positionLabel, a.plan_code AS planCode, a.plan_title AS planTitle, " +
                "a.company_name AS companyName, a.contact_name AS contactName, a.contact_phone AS contactPhone, a.contact_wechat AS contactWechat, a.contact_value AS contactValue, " +
                "a.title, a.landing_url AS landingUrl, a.creative_image_url AS creativeImageUrl, a.budget, a.start_date AS startDate, a.duration_days AS durationDays, a.remark, " +
                "a.status, a.status_message AS statusMessage, a.payment_order_no AS paymentOrderNo, a.published_record_id AS publishedRecordId, a.published_record_type AS publishedRecordType, " +
                "a.reviewer_user_id AS reviewerUserId, a.reviewer_username AS reviewerUsername, a.reviewed_time AS reviewedTime, a.created_time AS createdTime, a.updated_time AS updatedTime, " +
                "po.payment_method AS paymentMethod, po.provider_type AS paymentProviderType, po.status AS paymentOrderStatus, " +
                "po.amount_cent AS paymentAmountCent, ROUND(po.amount_cent/100, 2) AS paymentAmountYuan, po.paid_time AS paymentPaidTime, po.expire_time AS paymentExpireTime ";
    }

    private List<Map<String, Object>> loadListConfig(String moduleKey, boolean forUpdate) {
        try {
            String json = jdbcTemplate.queryForObject(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 1" + (forUpdate ? " FOR UPDATE" : ""),
                    String.class,
                    moduleKey,
                    CONFIG_STATUS
            );
            if (json == null || json.isBlank()) {
                return List.of();
            }
            List<LinkedHashMap<String, Object>> parsed = objectMapper.readValue(
                    json,
                    new TypeReference<List<LinkedHashMap<String, Object>>>() {}
            );
            return parsed == null ? List.of() : new ArrayList<>(parsed);
        } catch (EmptyResultDataAccessException ex) {
            return List.of();
        } catch (Exception ex) {
            log.error("读取开源站广告配置失败, moduleKey={}, errorType={}", moduleKey, ex.getClass().getSimpleName());
            throw new BizException(503, "广告配置暂时无法读取，请稍后重试");
        }
    }

    private void saveListConfig(String moduleKey, List<Map<String, Object>> items) {
        try {
            String json = objectMapper.writeValueAsString(items);
            List<Long> existingIds = jdbcTemplate.query(
                    "SELECT id FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 1",
                    (rs, rowNum) -> rs.getLong("id"),
                    moduleKey,
                    CONFIG_STATUS
            );
            Long existingId = existingIds.isEmpty() ? null : existingIds.get(0);
            if (existingId == null) {
                int inserted = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) VALUES(?, ?, ?, NOW(), NOW(), 0)",
                        moduleKey,
                        CONFIG_STATUS,
                        json
                );
                if (inserted != 1) throw new BizException(503, "广告配置写入失败");
            } else {
                int updated = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json,
                        existingId
                );
                if (updated != 1) throw new BizException(409, "广告配置已被修改，请刷新后重试");
            }
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("save open source ad config failed: moduleKey={}, errorType={}", moduleKey, ex.getClass().getSimpleName());
            throw new BizException(503, "广告配置暂时无法保存，请稍后重试");
        }
    }

    private Map<String, Object> normalizeTextAd(Map<String, Object> input, long id, String createdAt) {
        String now = LocalDateTime.now().toString();
        String title = text(input.get("title"));
        if (title.isBlank()) throw new BizException(400, "文字广告标题不能为空");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        result.put("title", trimToLength(title, 200));
        result.put("summary", trimToLength(text(firstPresent(input, "summary", "description")), 1000));
        result.put("badge", trimToLength(text(firstPresent(input, "badge", "tag")), 40));
        result.put("linkUrl", validateAdUrl(text(firstPresent(input, "linkUrl", "targetUrl")), "文字广告链接"));
        result.put("enabled", strictBoolean(input.get("enabled"), true, "enabled"));
        result.put("sortOrder", strictInteger(input.get("sortOrder"), 0, -10_000, 10_000, "sortOrder"));
        result.put("createdAt", createdAt == null || createdAt.isBlank() ? now : createdAt);
        result.put("updatedAt", now);
        return result;
    }

    private Map<String, Object> normalizeAdPlan(Map<String, Object> input, long id, String createdAt) {
        if (input.get("positionType") == null || text(input.get("positionType")).isBlank()) {
            throw new BizException(400, "广告位类型不能为空");
        }
        String positionType = normalizePositionType(input.get("positionType"));
        String code = text(input.get("code")).toLowerCase(Locale.ROOT);
        if (code.isBlank()) {
            code = positionType.equals("home_carousel") ? "home-carousel-" + id : "sidebar-text-" + id;
        }
        if (code.length() > 80 || !code.matches("[a-z0-9][a-z0-9._-]*")) {
            throw new BizException(400, "广告套餐编码格式非法");
        }
        long priceCent = resolvePriceCent(input, positionType);
        if (priceCent <= 0 || priceCent > 100_000_000L) {
            throw new BizException(400, "广告套餐价格必须在 0.01 元到 100 万元之间");
        }
        String priceYuan = formatYuan(priceCent);
        List<String> benefits = toStringList(input.get("benefits"));
        if (benefits.size() > 20 || benefits.stream().anyMatch(item -> item.length() > 200)) {
            throw new BizException(400, "广告套餐权益最多 20 条且每条不超过 200 字");
        }
        String title = text(input.get("title"));
        if (title.isBlank()) throw new BizException(400, "广告套餐标题不能为空");
        String now = LocalDateTime.now().toString();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        result.put("code", code);
        result.put("positionType", positionType);
        result.put("positionLabel", textOr(input.get("positionLabel"), positionLabel(positionType)));
        result.put("title", trimToLength(title, 160));
        result.put("description", trimToLength(text(input.get("description")), 2000));
        result.put("priceLabel", textOr(input.get("priceLabel"), "¥" + priceYuan));
        result.put("priceYuan", priceYuan);
        result.put("priceCent", priceCent);
        result.put("benefits", benefits);
        result.put("recommended", strictBoolean(input.get("recommended"), false, "recommended"));
        result.put("enabled", strictBoolean(input.get("enabled"), true, "enabled"));
        result.put("sortOrder", strictInteger(input.get("sortOrder"), 0, -10_000, 10_000, "sortOrder"));
        result.put("createdAt", createdAt == null || createdAt.isBlank() ? now : createdAt);
        result.put("updatedAt", now);
        return result;
    }

    private Map<String, Object> normalizeApplicationRow(Map<String, Object> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", source.get("id"));
        result.put("tenantId", source.get("tenantId"));
        result.put("siteCode", textOr(source.get("siteCode"), DEFAULT_SITE_CODE));
        result.put("siteName", textOr(source.get("siteName"), DEFAULT_SITE_NAME));
        result.put("applicationNo", textOr(source.get("applicationNo"), ""));

        String positionType = normalizePositionType(source.get("positionType"));
        String rawStatus = normalizeStatus(source.get("status"));
        if (!ALLOWED_APPLICATION_STATUS.contains(rawStatus)) {
            throw new BizException(503, "广告申请状态数据异常");
        }
        String paymentStatus = paymentStatusKey(source.get("paymentOrderStatus"));
        String status = resolveEffectiveStatus(rawStatus, paymentStatus);
        String statusMessage = resolveStatusMessage(rawStatus, status, paymentStatus, source.get("statusMessage"));

        result.put("positionType", positionType);
        result.put("positionLabel", textOr(source.get("positionLabel"), positionLabel(positionType)));
        result.put("planCode", textOr(source.get("planCode"), ""));
        result.put("planTitle", textOr(source.get("planTitle"), ""));
        result.put("companyName", textOr(source.get("companyName"), ""));
        result.put("contactName", textOr(source.get("contactName"), ""));
        result.put("contactPhone", textOr(source.get("contactPhone"), ""));
        result.put("contactWechat", textOr(source.get("contactWechat"), ""));
        result.put("contactValue", textOr(source.get("contactValue"), ""));
        result.put("title", textOr(source.get("title"), ""));
        result.put("landingUrl", textOr(source.get("landingUrl"), ""));
        result.put("creativeImageUrl", textOr(source.get("creativeImageUrl"), ""));
        result.put("budget", textOr(source.get("budget"), ""));
        result.put("startDate", textOr(source.get("startDate"), ""));
        result.put("durationDays", textOr(source.get("durationDays"), ""));
        result.put("remark", textOr(source.get("remark"), ""));

        result.put("status", status);
        result.put("rawStatus", rawStatus);
        result.put("statusLabel", statusLabel(status));
        result.put("statusMessage", statusMessage);
        result.put("paymentStatus", paymentStatus);
        result.put("paymentStatusLabel", paymentStatusLabel(paymentStatus));
        result.put("paymentOrderNo", textOr(source.get("paymentOrderNo"), ""));
        result.put("paymentMethod", textOr(source.get("paymentMethod"), ""));
        result.put("paymentProviderType", textOr(source.get("paymentProviderType"), ""));
        result.put("paymentOrderStatus", number(source.get("paymentOrderStatus"), -1));
        result.put("paymentAmountCent", number(source.get("paymentAmountCent"), 0L));
        result.put("paymentAmountYuan", textOr(source.get("paymentAmountYuan"), "0"));
        result.put("paymentPaidTime", source.get("paymentPaidTime"));
        result.put("paymentExpireTime", source.get("paymentExpireTime"));
        result.put("publishedRecordId", source.get("publishedRecordId"));
        result.put("publishedRecordType", textOr(source.get("publishedRecordType"), ""));
        result.put("reviewerUserId", source.get("reviewerUserId"));
        result.put("reviewerUsername", textOr(source.get("reviewerUsername"), ""));
        result.put("reviewedTime", source.get("reviewedTime"));
        result.put("createdTime", source.get("createdTime"));
        result.put("updatedTime", source.get("updatedTime"));
        return result;
    }

    private long tenantId() {
        return tenantSupportService.resolveCurrentOrDefaultTenantId();
    }

    private LinkedHashMap<String, Object> linkedMapOf(Object... keyValues) {
        if (keyValues.length % 2 != 0) {
            throw new IllegalArgumentException("keyValues length must be even");
        }
        LinkedHashMap<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < keyValues.length; index += 2) {
            result.put(String.valueOf(keyValues[index]), keyValues[index + 1]);
        }
        return result;
    }

    private List<String> toStringList(Object value) {
        List<String> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                String normalized = text(item);
                if (!normalized.isBlank()) {
                    result.add(normalized);
                }
            }
            return result;
        }
        String raw = text(value);
        if (!raw.isBlank()) {
            for (String line : raw.split("\\r?\\n")) {
                String normalized = line.trim();
                if (!normalized.isBlank()) {
                    result.add(normalized);
                }
            }
        }
        return result;
    }

    private long nextId(List<Map<String, Object>> rows) {
        long max = 0L;
        for (Map<String, Object> row : rows) {
            max = Math.max(max, number(row.get("id"), 0L));
        }
        return max + 1L;
    }

    private Map<String, Object> resolvePlan(String requestedPositionType, String planCode) {
        List<Map<String, Object>> plans = loadAdPlans().stream()
                .filter(item -> booleanValue(item.get("enabled"), true))
                .sorted((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)))
                .toList();
        if (planCode != null && !planCode.isBlank()) {
            for (Map<String, Object> plan : plans) {
                if (text(plan.get("code")).equalsIgnoreCase(planCode)) {
                    return plan;
                }
            }
            return null;
        }
        String positionType = normalizePositionType(requestedPositionType);
        for (Map<String, Object> plan : plans) {
            if (positionType.equals(normalizePositionType(plan.get("positionType")))) {
                return plan;
            }
        }
        return plans.isEmpty() ? null : plans.get(0);
    }

    private Map<String, Object> withId(Map<String, Object> payload, long id) {
        Map<String, Object> result = new LinkedHashMap<>(payload);
        result.put("id", id);
        return result;
    }

    private void ensureUniquePlanCode(List<Map<String, Object>> plans, Map<String, Object> candidate, long candidateId) {
        String code = text(candidate.get("code"));
        boolean duplicate = plans.stream().anyMatch(plan -> number(plan.get("id"), 0L) != candidateId
                && code.equalsIgnoreCase(text(plan.get("code"))));
        if (duplicate) throw new BizException(409, "广告套餐编码已存在");
    }

    private String normalizePositionType(Object value) {
        String positionType = text(value).toLowerCase(Locale.ROOT);
        if (positionType.isBlank()) return "sidebar_text";
        if (!ALLOWED_POSITION_TYPES.contains(positionType)) {
            throw new BizException(400, "仅支持首页轮播或侧边文字广告位");
        }
        return positionType;
    }

    private String normalizeSiteCode(String value) {
        String siteCode = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        return siteCode.isBlank() ? DEFAULT_SITE_CODE : trimToLength(siteCode, 40);
    }

    private String normalizeStatus(Object value) {
        String status = text(value).toLowerCase(Locale.ROOT);
        return status.isBlank() ? "pending" : status;
    }

    private String normalizePaymentMethod(Object value) {
        String paymentMethod = text(value).toLowerCase(Locale.ROOT);
        if ("wx".equals(paymentMethod) || "weixin".equals(paymentMethod)) {
            return "wechat";
        }
        if ("ali".equals(paymentMethod)) {
            return "alipay";
        }
        if (!paymentMethod.equals("wechat") && !paymentMethod.equals("alipay")) {
            throw new BizException(400, "仅支持微信或支付宝");
        }
        return paymentMethod;
    }

    private String statusLabel(String status) {
        return switch (normalizeStatus(status)) {
            case "pending_payment" -> "待支付";
            case "approved" -> "已通过";
            case "rejected" -> "已拒绝";
            case "online" -> "投放中";
            case "offline" -> "已下线";
            default -> "待审核";
        };
    }

    private String defaultStatusMessage(String status) {
        return switch (normalizeStatus(status)) {
            case "pending_payment" -> "请先完成支付，支付成功后会自动进入商业版后台审核。";
            case "approved" -> "审核通过，已自动展示到开源版首页。";
            case "rejected" -> "审核未通过，请根据处理说明调整后重新提交。";
            case "online" -> "广告已上线展示。";
            case "offline" -> "广告已下线。";
            default -> "已支付，等待商业版后台审核。";
        };
    }

    private String resolveEffectiveStatus(String rawStatus, String paymentStatus) {
        if ("pending_payment".equals(rawStatus) && "paid".equals(paymentStatus)) {
            return "pending";
        }
        return rawStatus;
    }

    private String resolveStatusMessage(String rawStatus, String effectiveStatus, String paymentStatus, Object currentMessage) {
        String message = text(currentMessage);
        if ("pending_payment".equals(rawStatus)) {
            if ("paid".equals(paymentStatus)) {
                return "已支付，等待商业版后台审核。";
            }
            return message.isBlank() ? defaultStatusMessage("pending_payment") : message;
        }
        return message.isBlank() ? defaultStatusMessage(effectiveStatus) : message;
    }

    private boolean displayStatus(String status) {
        String normalized = normalizeStatus(status);
        return "approved".equals(normalized) || "online".equals(normalized);
    }

    private void validateStatusTransition(String currentStatus, String targetStatus) {
        if (targetStatus.equals(currentStatus)) return;
        Set<String> allowed = switch (currentStatus) {
            case "pending_payment" -> Set.of("pending", "rejected");
            case "pending" -> Set.of("approved", "rejected");
            case "approved" -> Set.of("online", "offline", "rejected");
            case "online" -> Set.of("offline");
            case "offline" -> Set.of("online", "rejected");
            case "rejected" -> Set.of("pending");
            default -> Set.of();
        };
        if (!allowed.contains(targetStatus)) {
            throw new BizException(409, "广告申请不能从当前状态切换到目标状态");
        }
    }

    private String paymentStatusKey(Object status) {
        if (status instanceof String textStatus) {
            String normalized = textStatus.trim().toLowerCase(Locale.ROOT);
            if (List.of("pending", "paid", "closed", "failed", "refunded", "uncreated").contains(normalized)) {
                return normalized;
            }
        }
        int code = number(status, -1);
        return switch (code) {
            case 0 -> "pending";
            case 1 -> "paid";
            case 2 -> "closed";
            case 3 -> "failed";
            case 4 -> "refunded";
            default -> "uncreated";
        };
    }

    private String paymentStatusLabel(String status) {
        return switch (paymentStatusKey(status)) {
            case "pending" -> "待支付";
            case "paid" -> "已支付";
            case "closed" -> "已关闭";
            case "failed" -> "支付失败";
            case "refunded" -> "已退款";
            default -> "未创建";
        };
    }

    private String positionLabel(String positionType) {
        return switch (normalizePositionType(positionType)) {
            case "home_carousel" -> "首页轮播广告";
            default -> "首页文字广告";
        };
    }

    private Object firstPresent(Map<String, Object> input, String... keys) {
        for (String key : keys) {
            if (input.containsKey(key) && input.get(key) != null && !text(input.get(key)).isBlank()) {
                return input.get(key);
            }
        }
        return null;
    }

    private String requireText(Map<String, Object> body, String key, String message) {
        String value = text(firstPresent(body, key));
        if (value.isBlank()) {
            value = text(firstPresent(body, normalizeLegacyField(key)));
        }
        if (value.isBlank()) {
            throw new BizException(400, message);
        }
        return value;
    }

    private String normalizeLegacyField(String key) {
        return switch (key) {
            case "contact" -> "contactName";
            case "creativeImageUrl" -> "imageUrl";
            default -> key;
        };
    }

    private long resolvePriceCent(Map<String, Object> input, String positionType) {
        Object explicitValue = firstPresent(input, "priceCent", "amountCent");
        if (explicitValue != null) {
            return strictLong(explicitValue, "priceCent");
        }
        String priceYuan = text(firstPresent(input, "priceYuan", "amountYuan", "price"));
        if (!priceYuan.isBlank()) {
            return yuanToCent(priceYuan);
        }
        String priceLabel = text(input.get("priceLabel"));
        Matcher matcher = PRICE_PATTERN.matcher(priceLabel.replace(",", ""));
        if (matcher.find()) {
            return yuanToCent(matcher.group(1));
        }
        return 0L;
    }

    private String buildPaymentTitle(Map<String, Object> application) {
        String planTitle = text(application.get("planTitle"));
        String title = text(application.get("title"));
        String positionLabel = text(application.get("positionLabel"));
        if (!planTitle.isBlank()) {
            return "广告投放-" + planTitle;
        }
        if (!title.isBlank()) {
            return "广告投放-" + title;
        }
        return "广告投放-" + positionLabel;
    }

    private boolean isExpired(Object value) {
        if (value == null) {
            return false;
        }
        if (value instanceof LocalDateTime dateTime) {
            return dateTime.isBefore(LocalDateTime.now());
        }
        String raw = text(value).replace("T", " ");
        if (raw.isBlank()) {
            return false;
        }
        try {
            return LocalDateTime.parse(raw.replace(" ", "T")).isBefore(LocalDateTime.now());
        } catch (Exception ex) {
            throw new BizException(503, "支付订单过期时间数据异常");
        }
    }

    private long yuanToCent(String value) {
        try {
            return new BigDecimal(value).multiply(BigDecimal.valueOf(100)).setScale(0, RoundingMode.UNNECESSARY).longValueExact();
        } catch (ArithmeticException | NumberFormatException ex) {
            throw new BizException(400, "广告套餐价格必须是最多两位小数的有效金额");
        }
    }

    private String formatYuan(long priceCent) {
        BigDecimal value = BigDecimal.valueOf(priceCent).divide(BigDecimal.valueOf(100));
        return value.stripTrailingZeros().toPlainString();
    }

    private String trimToNull(Object value, int maxLength) {
        String raw = text(value);
        if (raw.isBlank()) {
            return null;
        }
        return trimToLength(raw, maxLength);
    }

    private String trimToLength(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        return value.length() > maxLength ? value.substring(0, maxLength) : value;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String textOr(Object value, String fallback) {
        String result = text(value);
        return result.isBlank() ? fallback : result;
    }

    private int number(Object value, int fallback) {
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception ex) {
            return fallback;
        }
    }

    private long number(Object value, long fallback) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return fallback;
        }
    }

    private boolean booleanValue(Object value, boolean fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Boolean bool) {
            return bool;
        }
        String normalized = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if (List.of("1", "true", "yes", "on").contains(normalized)) {
            return true;
        }
        if (List.of("0", "false", "no", "off").contains(normalized)) {
            return false;
        }
        return fallback;
    }

    private boolean strictBoolean(Object value, boolean fallback, String fieldName) {
        if (value == null || String.valueOf(value).isBlank()) return fallback;
        if (value instanceof Boolean bool) return bool;
        String normalized = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if (List.of("1", "true", "yes", "on").contains(normalized)) return true;
        if (List.of("0", "false", "no", "off").contains(normalized)) return false;
        throw new BizException(400, fieldName + " 仅支持 true/false 或 1/0");
    }

    private int strictInteger(Object value, int fallback, int min, int max, String fieldName) {
        if (value == null || String.valueOf(value).isBlank()) return fallback;
        try {
            int parsed = Integer.parseInt(String.valueOf(value));
            if (parsed < min || parsed > max) throw new BizException(400, fieldName + " 超出允许范围");
            return parsed;
        } catch (NumberFormatException ex) {
            throw new BizException(400, fieldName + " 必须为整数");
        }
    }

    private long strictLong(Object value, String fieldName) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ex) {
            throw new BizException(400, fieldName + " 必须为整数");
        }
    }

    private String validateAdUrl(String value, String fieldName) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.isBlank()) throw new BizException(400, fieldName + "不能为空");
        if (normalized.length() > 500) throw new BizException(400, fieldName + "过长");
        if (normalized.startsWith("#/")) return normalized;
        try {
            URI uri = URI.create(normalized);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null || host.isBlank()
                    || uri.getUserInfo() != null || isLocalHost(host)) {
                throw new BizException(400, fieldName + "必须是安全的 HTTPS 公网地址");
            }
            return uri.normalize().toString();
        } catch (IllegalArgumentException ex) {
            throw new BizException(400, fieldName + "格式非法");
        }
    }

    private boolean isLocalHost(String host) {
        String normalized = host.toLowerCase(Locale.ROOT);
        if (normalized.equals("localhost") || normalized.endsWith(".localhost") || normalized.endsWith(".local")) return true;
        if (normalized.equals("::1") || normalized.startsWith("127.") || normalized.startsWith("10.")
                || normalized.startsWith("192.168.") || normalized.startsWith("169.254.")) return true;
        if (normalized.startsWith("172.")) {
            String[] parts = normalized.split("\\.");
            if (parts.length > 1) {
                try {
                    int second = Integer.parseInt(parts[1]);
                    return second >= 16 && second <= 31;
                } catch (NumberFormatException ignored) {
                    return true;
                }
            }
        }
        return false;
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args);
        return rows.isEmpty() ? null : rows.get(0);
    }
}
