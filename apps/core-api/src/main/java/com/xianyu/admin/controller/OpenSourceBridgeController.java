package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.OpenSourceAdService;
import com.xianyu.admin.service.OpenSourceBridgeAuthService;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.TenantSupportService;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin-api/open-source-bridge")
public class OpenSourceBridgeController {
    private static final Logger logger = LoggerFactory.getLogger(OpenSourceBridgeController.class);

    private final JdbcTemplate jdbcTemplate;
    private final TenantSupportService tenantSupportService;
    private final OpenSourceBridgeAuthService bridgeAuthService;
    private final OpenSourceContentService contentService;
    private final OpenSourceAdService adService;

    @Value("${payment.sandbox.enabled:false}")
    private boolean paymentSandboxEnabled;

    public OpenSourceBridgeController(
            JdbcTemplate jdbcTemplate,
            TenantSupportService tenantSupportService,
            OpenSourceBridgeAuthService bridgeAuthService,
            OpenSourceContentService contentService,
            OpenSourceAdService adService
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.tenantSupportService = tenantSupportService;
        this.bridgeAuthService = bridgeAuthService;
        this.contentService = contentService;
        this.adService = adService;
    }

    @GetMapping("/health")
    public Result<Map<String, Object>> health(HttpServletRequest request) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("status", "UP");
            data.put("siteCode", site.siteCode());
            data.put("siteName", site.siteName());
            data.put("frontendUrl", site.frontendUrl());
            data.put("adminUrl", site.adminUrl());
            boolean feedbackReady = tableExists("user_feedback") && tableExists("user_feedback_reply");
            boolean adsReady = tableExists("admin_module_record") && tableExists("open_source_ad_application");
            data.put("feedbackBridgeReady", feedbackReady);
            data.put("adsBridgeReady", adsReady);
            data.put("checkedAt", LocalDateTime.now().toString());
            if (!feedbackReady || !adsReady) {
                throw new BizException(503, "开源站桥接所需数据结构尚未就绪");
            }
            return Result.ok(data);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("open-source bridge health check failed, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "开源站桥接服务暂时不可用");
        }
    }

    @GetMapping("/home/carousels")
    public Result<Object> homeCarousels(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            return Result.ok(contentService.listHomeCarousels());
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/home/announcements")
    public Result<Object> homeAnnouncements(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            return Result.ok(contentService.listHomeAnnouncements());
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/about")
    public Result<Object> about(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            return Result.ok(contentService.getAboutContent());
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/ads/text")
    public Result<Object> textAds(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            return Result.ok(adService.listEnabledTextAds());
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/ads/plans")
    public Result<Object> adPlans(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            return Result.ok(adService.listEnabledAdPlans());
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/ads/applications/mine")
    public Result<PageResult<Map<String, Object>>> myAdApplications(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            return Result.ok(adService.pageSiteApplications(current, size, site.siteCode(), site.instanceToken()));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @PostMapping("/ads/applications")
    public Result<Map<String, Object>> createAdApplication(
            @RequestBody Map<String, Object> body,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            return Result.ok(adService.createApplication(site, body));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("create open-source bridge ad application failed, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "广告申请暂时无法提交，请稍后重试");
        }
    }

    @GetMapping("/ads/payment/methods")
    public Result<Object> adPaymentMethods(HttpServletRequest request) {
        try {
            bridgeAuthService.requireSiteContext(request);
            List<Map<String, Object>> methods = adService.listEnabledPaymentMethods();
            if (methods == null || methods.isEmpty()) {
                throw new BizException(503, "当前暂无可用支付方式，请稍后再试");
            }
            return Result.ok(methods);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("list open-source bridge payment methods failed, errorType={}",
                    ex.getClass().getSimpleName());
            throw new BizException(503, "支付方式暂时无法加载，请稍后重试");
        }
    }

    @PostMapping("/ads/applications/{id}/payment-order")
    public Result<Map<String, Object>> createAdPaymentOrder(
            @PathVariable("id") long id,
            @RequestBody Map<String, Object> body,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            if (id <= 0) {
                throw new BizException(400, "广告申请 ID 非法");
            }
            if (body == null || body.isEmpty()) {
                throw new BizException(400, "支付订单参数不能为空");
            }
            return Result.ok(requireBridgePaymentResult(
                    adService.createApplicationPaymentOrder(id, site, body, clientIp(request)),
                    "广告支付订单暂时无法创建，请稍后重试"));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("create open-source ad payment order failed, errorType={}",
                    ex.getClass().getSimpleName());
            throw new BizException(503, "广告支付订单暂时无法创建，请稍后重试");
        }
    }

    @GetMapping("/ads/payment/orders/{orderNo}")
    public Result<Map<String, Object>> adPaymentOrderDetail(
            @PathVariable("orderNo") String orderNo,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            return Result.ok(requireBridgePaymentResult(
                    adService.getApplicationPaymentOrder(requirePaymentOrderNo(orderNo), site),
                    "广告支付订单暂时无法查询，请稍后重试"));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("get open-source ad payment order failed, errorType={}",
                    ex.getClass().getSimpleName());
            throw new BizException(503, "广告支付订单暂时无法查询，请稍后重试");
        }
    }

    @PostMapping("/ads/payment/orders/{orderNo}/close")
    public Result<Map<String, Object>> closeAdPaymentOrder(
            @PathVariable("orderNo") String orderNo,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            return Result.ok(requireBridgePaymentResult(
                    adService.closeApplicationPaymentOrder(requirePaymentOrderNo(orderNo), site),
                    "广告支付订单暂时无法关闭，请稍后重试"));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("close open-source ad payment order failed, errorType={}",
                    ex.getClass().getSimpleName());
            throw new BizException(503, "广告支付订单暂时无法关闭，请稍后重试");
        }
    }

    @PostMapping("/ads/payment/orders/{orderNo}/mock-pay")
    public Result<Map<String, Object>> mockPayAdPaymentOrder(
            @PathVariable("orderNo") String orderNo,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
            requirePaymentSandbox();
            return Result.ok(requireBridgePaymentResult(
                    adService.mockPayApplicationPaymentOrder(requirePaymentOrderNo(orderNo), site),
                    "模拟支付不可用或执行失败"));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("mock pay open-source ad payment order failed, errorType={}",
                    ex.getClass().getSimpleName());
            throw new BizException(503, "模拟支付不可用或执行失败");
        }
    }

    @GetMapping("/feedback")
    public Result<PageResult<Map<String, Object>>> listFeedback(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String category,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
                long tenantId = tenantId();
            int safeCurrent = PageUtils.normalizeCurrent(current);
            int safeSize = PageUtils.normalizeSize(size, 200);
            int offset = (safeCurrent - 1) * safeSize;

            StringBuilder where = new StringBuilder(" WHERE tenant_id=? AND deleted=0 AND site_source=?");
            List<Object> args = new ArrayList<>();
            args.add(tenantId);
            args.add(site.siteCode());
            if (status != null && !status.isBlank()) {
                where.append(" AND status=?");
                args.add(status.trim());
            }
            if (category != null && !category.isBlank()) {
                where.append(" AND category=?");
                args.add(category.trim());
            }

            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM user_feedback" + where,
                    Long.class,
                    args.toArray()
            );
            List<Object> pageArgs = new ArrayList<>(args);
            pageArgs.add(safeSize);
            pageArgs.add(offset);

            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, tenant_id AS tenantId, user_id AS userId, username, category, title, " +
                            "LEFT(content, 200) AS contentPreview, content, contact, status, priority, " +
                            "site_source AS siteSource, site_name AS siteName, " +
                            "replier_username AS replierUsername, replied_time AS repliedTime, " +
                            "created_time AS createdTime, updated_time AS updatedTime " +
                            "FROM user_feedback" + where + " ORDER BY created_time DESC LIMIT ? OFFSET ?",
                    pageArgs.toArray()
            );
            appendUserReplyCounts(rows);
            return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/feedback/stats")
    public Result<Map<String, Object>> feedbackStats(HttpServletRequest request) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
                long tenantId = tenantId();
            Map<String, Object> stats = new LinkedHashMap<>();
            stats.put("open", 0);
            stats.put("in_progress", 0);
            stats.put("replied", 0);
            stats.put("closed", 0);
            stats.put("total", 0);

            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT status, COUNT(*) AS cnt FROM user_feedback " +
                            "WHERE tenant_id=? AND site_source=? AND deleted=0 GROUP BY status",
                    tenantId,
                    site.siteCode()
            );
            long total = 0;
            for (Map<String, Object> row : rows) {
                String key = safe(row.get("status"));
                long count = row.get("cnt") instanceof Number number ? number.longValue() : 0L;
                if (stats.containsKey(key)) {
                    stats.put(key, count);
                }
                total += count;
            }
            stats.put("total", total);
            return Result.ok(stats);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @GetMapping("/feedback/{id}")
    public Result<Map<String, Object>> feedbackDetail(@PathVariable Long id, HttpServletRequest request) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
                List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, tenant_id AS tenantId, user_id AS userId, username, category, title, content, contact, " +
                            "site_source AS siteSource, site_name AS siteName, " +
                            "status, priority, replier_user_id AS replierUserId, replier_username AS replierUsername, " +
                            "replied_time AS repliedTime, created_time AS createdTime, updated_time AS updatedTime " +
                            "FROM user_feedback WHERE id=? AND tenant_id=? AND site_source=? AND deleted=0 LIMIT 1",
                    id,
                    tenantId(),
                    site.siteCode()
            );
            if (rows.isEmpty()) {
                throw new BizException(404, "反馈记录不存在");
            }

            Map<String, Object> feedback = rows.get(0);
            List<Map<String, Object>> replies = jdbcTemplate.queryForList(
                    "SELECT id, replier_role AS replierRole, replier_user_id AS replierUserId, " +
                            "replier_username AS replierUsername, content, created_time AS createdTime " +
                            "FROM user_feedback_reply WHERE feedback_id=? ORDER BY created_time ASC",
                    id
            );
            feedback.put("replies", replies);
            return Result.ok(feedback);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        }
    }

    @PostMapping("/feedback")
    public Result<Map<String, Object>> createFeedback(
            @RequestBody Map<String, Object> body,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
    
            String title = safe(body.get("title")).trim();
            String content = safe(body.get("content")).trim();
            if (title.isEmpty()) {
                throw new BizException(400, "请填写反馈标题");
            }
            if (content.isEmpty()) {
                throw new BizException(400, "请填写反馈内容");
            }
            if (title.length() > 200) {
                throw new BizException(400, "反馈标题过长，请控制在 200 字以内");
            }

            String category = normalizeCategory(body.get("category"));
            String contact = trimToNull(body.get("contact"), 200);
            String username = trimToLength(site.siteName() + "用户", 120);

            jdbcTemplate.update(
                    "INSERT INTO user_feedback(" +
                            "tenant_id, user_id, username, category, title, content, contact, site_source, site_name, " +
                            "status, priority, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,'open','normal',NOW(),NOW(),0)",
                    tenantId(),
                    0L,
                    username,
                    category,
                    title,
                    content,
                    contact,
                    site.siteCode(),
                    site.siteName()
            );
            Long feedbackId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (feedbackId == null) {
                throw new BizException(503, "反馈已写入但无法确认记录编号，请稍后查询");
            }
            return feedbackDetail(feedbackId, request);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("create open-source bridge feedback failed, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "反馈暂时无法提交，请稍后重试");
        }
    }

    @PostMapping("/feedback/{id}/reply")
    public Result<Map<String, Object>> appendFeedbackReply(
            @PathVariable Long id,
            @RequestBody Map<String, Object> body,
            HttpServletRequest request
    ) {
        try {
            OpenSourceBridgeAuthService.OpenSourceSiteContext site = bridgeAuthService.requireSiteContext(request);
    
            Integer exists = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM user_feedback WHERE id=? AND tenant_id=? AND site_source=? AND deleted=0",
                    Integer.class,
                    id,
                    tenantId(),
                    site.siteCode()
            );
            if (exists == null || exists == 0) {
                throw new BizException(404, "反馈记录不存在");
            }

            String content = safe(body.get("content")).trim();
            if (content.isEmpty()) {
                throw new BizException(400, "请填写补充内容");
            }
            if (content.length() > 2000) {
                throw new BizException(400, "补充内容过长，请控制在 2000 字以内");
            }

            jdbcTemplate.update(
                    "INSERT INTO user_feedback_reply(" +
                            "feedback_id, tenant_id, replier_user_id, replier_username, replier_role, content, created_time" +
                            ") VALUES(?,?,?,?,?,?,NOW())",
                    id,
                    tenantId(),
                    0L,
                    trimToLength(site.siteName() + "用户", 120),
                    "user",
                    content
            );
            jdbcTemplate.update(
                    "UPDATE user_feedback SET " +
                            "status=CASE WHEN status='closed' THEN 'open' ELSE status END, " +
                            "updated_time=NOW() WHERE id=? AND tenant_id=? AND site_source=?",
                    id,
                    tenantId(),
                    site.siteCode()
            );
            return feedbackDetail(id, request);
        } catch (OpenSourceBridgeAuthService.BridgeAuthException ex) {
            throw ex;
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            logger.error("append open-source bridge feedback reply failed, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "反馈补充暂时无法提交，请稍后重试");
        }
    }

    private boolean tableExists(String tableName) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?",
                Integer.class,
                tableName
        );
        return count != null && count > 0;
    }

    private void appendUserReplyCounts(List<Map<String, Object>> rows) {
        if (rows.isEmpty()) {
            return;
        }
        List<Long> ids = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Object idValue = row.get("id");
            if (idValue instanceof Number number) {
                ids.add(number.longValue());
            }
        }
        if (ids.isEmpty()) {
            return;
        }

        String inClause = ids.stream().map(String::valueOf).reduce((left, right) -> left + "," + right).orElse("0");
        List<Map<String, Object>> replyCounts = jdbcTemplate.queryForList(
                "SELECT feedback_id AS feedbackId, COUNT(*) AS replyCount " +
                        "FROM user_feedback_reply WHERE replier_role='user' AND feedback_id IN (" + inClause + ") " +
                        "GROUP BY feedback_id"
        );
        Map<Long, Long> countMap = new LinkedHashMap<>();
        for (Map<String, Object> row : replyCounts) {
            Object feedbackId = row.get("feedbackId");
            Object replyCount = row.get("replyCount");
            if (feedbackId instanceof Number feedbackNumber && replyCount instanceof Number replyNumber) {
                countMap.put(feedbackNumber.longValue(), replyNumber.longValue());
            }
        }
        for (Map<String, Object> row : rows) {
            Object idValue = row.get("id");
            long feedbackId = idValue instanceof Number number ? number.longValue() : 0L;
            row.put("userReplyCount", countMap.getOrDefault(feedbackId, 0L));
        }
    }


    private long tenantId() {
        return tenantSupportService.resolveCurrentOrDefaultTenantId();
    }

    private String normalizeCategory(Object value) {
        String category = safe(value).trim();
        return category.isEmpty() ? "other" : trimToLength(category, 40);
    }

    private String trimToNull(Object value, int maxLength) {
        String text = safe(value).trim();
        if (text.isEmpty()) {
            return null;
        }
        return trimToLength(text, maxLength);
    }

    private String trimToLength(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        return value.length() > maxLength ? value.substring(0, maxLength) : value;
    }

    private String safe(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String clientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }

    private String requirePaymentOrderNo(String orderNo) {
        String normalized = orderNo == null ? "" : orderNo.trim();
        if (normalized.isEmpty() || normalized.length() > 120) {
            throw new BizException(400, "支付订单号不正确");
        }
        return normalized;
    }

    private void requirePaymentSandbox() {
        if (!paymentSandboxEnabled) {
            throw new BizException(403, "支付沙箱未启用，模拟支付不可用");
        }
    }

    private Map<String, Object> requireBridgePaymentResult(Map<String, Object> result, String message) {
        if (result == null) {
            throw new BizException(503, message);
        }
        return result;
    }
}
