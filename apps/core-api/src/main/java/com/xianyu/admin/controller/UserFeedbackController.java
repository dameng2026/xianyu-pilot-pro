package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.OpenSourceBridgeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/feedback")
public class UserFeedbackController {
    private static final Logger logger = LoggerFactory.getLogger(UserFeedbackController.class);

    private static final String DEFAULT_SITE_SOURCE = "commercial";
    private static final String DEFAULT_SITE_NAME = "商业版";

    private final JdbcTemplate jdbcTemplate;
    private final OpenSourceBridgeClient bridgeClient;

    public UserFeedbackController(JdbcTemplate jdbcTemplate, OpenSourceBridgeClient bridgeClient) {
        this.jdbcTemplate = jdbcTemplate;
        this.bridgeClient = bridgeClient;
    }

    @GetMapping("/bridge-status")
    public Result<Map<String, Object>> bridgeStatus() {
        Map<String, Object> status = new LinkedHashMap<>();
        status.put("bridgeEnabled", bridgeClient.isBridgeEnabled());
        status.put("siteName", bridgeClient.getSiteName());
        return Result.ok(status);
    }

    @PostMapping
    public Result<Map<String, Object>> submit(@RequestBody Map<String, Object> body) {
        // 桥接启用时转发到商业版后端
        if (bridgeClient.isBridgeEnabled()) {
            return Result.ok(bridgeClient.submitFeedback(body));
        }
        // 降级：本地存储
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        if (body == null) throw new BizException(400, "反馈内容不能为空");

        String username = UserContext.username();
        String category = normalizeCategory(body.get("category"));
        String title = safe(body.get("title")).trim();
        String content = safe(body.get("content")).trim();
        String contact = safe(body.get("contact")).trim();

        if (title.isEmpty()) throw new BizException(400, "请填写反馈标题");
        if (content.isEmpty()) throw new BizException(400, "请填写反馈内容");
        if (title.length() > 200) throw new BizException(400, "反馈标题过长，请控制在 200 字以内");
        if (content.length() > 20_000) throw new BizException(400, "反馈内容过长，请控制在 20000 字以内");
        if (contact.length() > 200) throw new BizException(400, "联系方式过长，请控制在 200 字以内");

        try {
            int affected = jdbcTemplate.update(
                    "INSERT INTO user_feedback(" +
                            "tenant_id, user_id, username, category, title, content, contact, site_source, site_name, " +
                            "status, priority, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,'open','normal',NOW(),NOW(),0)",
                    tenantId,
                    userId,
                    username,
                    category,
                    title,
                    content,
                    contact.isEmpty() ? null : contact,
                    DEFAULT_SITE_SOURCE,
                    DEFAULT_SITE_NAME
            );
            if (affected != 1) throw new BizException(503, "反馈提交未被数据库确认，请稍后重试");
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            res.put("message", "反馈已提交，我们会尽快处理");
            return Result.ok(res);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            logger.error("submit feedback failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "反馈提交暂时不可用，请稍后重试");
        }
    }

    @GetMapping
    public Result<Object> myList(@RequestParam(defaultValue = "1") int current,
                                                          @RequestParam(defaultValue = "20") int size,
                                                          @RequestParam(required = false) String status,
                                                          @RequestParam(required = false) String category) {
        // 桥接启用时转发到商业版后端
        if (bridgeClient.isBridgeEnabled()) {
            return Result.ok(bridgeClient.listFeedback(current, size, status, category));
        }
        // 降级：本地查询
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }

        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;

        StringBuilder where = new StringBuilder(" WHERE tenant_id=? AND user_id=? AND deleted=0");
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        args.add(userId);
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
                "SELECT id, category, title, LEFT(content, 200) AS contentPreview, status, priority, " +
                        "site_source AS siteSource, site_name AS siteName, " +
                        "replier_username AS replierUsername, replied_time AS repliedTime, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM user_feedback" + where + " ORDER BY created_time DESC LIMIT ? OFFSET ?",
                pageArgs.toArray()
        );
        return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
    }

    @GetMapping("/stats")
    public Result<Object> myStats() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("open", 0);
        stats.put("in_progress", 0);
        stats.put("replied", 0);
        stats.put("closed", 0);
        stats.put("total", 0);

        // 桥接启用时优先转发到商业版后端，失败则降级到本地查询
        if (bridgeClient.isBridgeEnabled()) {
            try {
                Map<String, Object> bridgeResult = bridgeClient.feedbackStats();
                if (bridgeResult != null) {
                    for (String key : new String[]{"open", "in_progress", "replied", "closed", "total"}) {
                        Object val = bridgeResult.get(key);
                        if (val instanceof Number) {
                            stats.put(key, ((Number) val).longValue());
                        }
                    }
                    return Result.ok(stats);
                }
            } catch (Exception e) {
                logger.warn("bridge feedback stats failed, falling back to local: {}", e.getMessage());
            }
        }

        // 降级：本地查询，失败时返回空统计（不阻塞反馈页面）
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT status, COUNT(*) AS cnt FROM user_feedback " +
                            "WHERE tenant_id=? AND user_id=? AND deleted=0 GROUP BY status",
                    tenantId, userId
            );
            long total = 0;
            for (Map<String, Object> row : rows) {
                String st = String.valueOf(row.get("status"));
                long cnt = ((Number) row.get("cnt")).longValue();
                stats.put(st, cnt);
                total += cnt;
            }
            stats.put("total", total);
        } catch (Exception e) {
            logger.warn("load feedback stats failed, returning empty stats: {}", e.getMessage());
        }
        return Result.ok(stats);
    }

    @GetMapping("/{id}")
    public Result<Object> detail(@PathVariable Long id) {
        // 桥接启用时转发到商业版后端
        if (bridgeClient.isBridgeEnabled()) {
            return Result.ok(bridgeClient.feedbackDetail(id));
        }
        // 降级：本地查询
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, user_id AS userId, username, category, title, content, contact, " +
                        "site_source AS siteSource, site_name AS siteName, " +
                        "status, priority, replier_user_id AS replierUserId, replier_username AS replierUsername, " +
                        "replied_time AS repliedTime, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM user_feedback WHERE id=? AND tenant_id=? AND user_id=? AND deleted=0 LIMIT 1",
                id, tenantId, userId
        );
        if (rows.isEmpty()) throw new BizException(404, "反馈不存在或无权查看");

        Map<String, Object> feedback = rows.get(0);
        List<Map<String, Object>> replies = jdbcTemplate.queryForList(
                "SELECT id, replier_role AS replierRole, replier_username AS replierUsername, content, created_time AS createdTime " +
                        "FROM user_feedback_reply WHERE feedback_id=? ORDER BY created_time ASC",
                id
        );
        feedback.put("replies", replies);
        return Result.ok(feedback);
    }

    @PostMapping("/{id}/reply")
    public Result<Object> appendReply(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        // 桥接启用时转发到商业版后端
        if (bridgeClient.isBridgeEnabled()) {
            String content = safe(body.get("content")).trim();
            if (content.isEmpty()) throw new BizException(400, "请填写补充内容");
            if (content.length() > 2000) throw new BizException(400, "补充内容过长，请控制在 2000 字以内");
            return Result.ok(bridgeClient.appendFeedbackReply(id, content));
        }
        // 降级：本地存储
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }

        String content = safe(body.get("content")).trim();
        if (content.isEmpty()) throw new BizException(400, "请填写补充内容");
        if (content.length() > 2000) throw new BizException(400, "补充内容过长，请控制在 2000 字以内");

        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_feedback WHERE id=? AND tenant_id=? AND user_id=? AND deleted=0",
                Integer.class,
                id,
                tenantId,
                userId
        );
        if (exists == null || exists == 0) throw new BizException(404, "反馈不存在或无权操作");

        try {
            jdbcTemplate.update(
                    "INSERT INTO user_feedback_reply(" +
                            "feedback_id, tenant_id, replier_user_id, replier_username, replier_role, content, created_time" +
                            ") VALUES(?,?,?,?,?,?,NOW())",
                    id,
                    tenantId,
                    userId,
                    UserContext.username(),
                    "user",
                    content
            );
            jdbcTemplate.update(
                    "UPDATE user_feedback SET " +
                            "status=CASE WHEN status='closed' THEN 'open' ELSE status END, " +
                            "updated_time=NOW() WHERE id=? AND tenant_id=? AND user_id=?",
                    id,
                    tenantId,
                    userId
            );
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            return Result.ok(res);
        } catch (Exception e) {
            logger.error("append feedback reply failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "反馈补充暂时不可用，请稍后重试");
        }
    }


    private String normalizeCategory(Object value) {
        String category = safe(value).trim();
        if (category.isEmpty()) return "other";
        if (category.length() > 40 || category.chars().anyMatch(Character::isISOControl)) {
            throw new BizException(400, "反馈分类不合法");
        }
        return category;
    }

    private String safe(Object value) {
        return value == null ? "" : String.valueOf(value);
    }
}
