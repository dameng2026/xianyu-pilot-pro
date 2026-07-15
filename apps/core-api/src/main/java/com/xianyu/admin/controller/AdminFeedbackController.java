package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.AdminContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin-api/feedback")
public class AdminFeedbackController {
    private static final Logger logger = LoggerFactory.getLogger(AdminFeedbackController.class);

    private static final String DEFAULT_SITE_SOURCE = "commercial";
    private static final String DEFAULT_SITE_NAME = "商业版";
    private static final List<String> ALLOWED_STATUS = List.of("open", "in_progress", "replied", "closed");
    private static final List<String> ALLOWED_PRIORITY = List.of("low", "normal", "high", "urgent");

    private final JdbcTemplate jdbcTemplate;

    public AdminFeedbackController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping
    public Result<PageResult<Map<String, Object>>> list(@RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size,
                                                        @RequestParam(required = false) String keyword,
                                                        @RequestParam(required = false) String status,
                                                        @RequestParam(required = false) String category,
                                                        @RequestParam(required = false) String priority,
                                                        @RequestParam(required = false) String siteSource,
                                                        @RequestParam(required = false) Long tenantId) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;

        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        List<Object> args = new ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (" +
                    "title LIKE ? OR content LIKE ? OR username LIKE ? OR site_name LIKE ? OR site_source LIKE ? " +
                    "OR CAST(user_id AS CHAR) LIKE ? OR CAST(id AS CHAR) LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
        }
        if (status != null && !status.isBlank()) {
            where.append(" AND status=?");
            args.add(status.trim());
        }
        if (category != null && !category.isBlank()) {
            where.append(" AND category=?");
            args.add(category.trim());
        }
        if (priority != null && !priority.isBlank()) {
            where.append(" AND priority=?");
            args.add(priority.trim());
        }
        if (siteSource != null && !siteSource.isBlank()) {
            where.append(" AND site_source=?");
            args.add(siteSource.trim());
        }
        if (tenantId != null) {
            where.append(" AND tenant_id=?");
            args.add(tenantId);
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
                        "LEFT(content, 200) AS contentPreview, status, priority, contact, " +
                        "site_source AS siteSource, site_name AS siteName, " +
                        "replier_username AS replierUsername, replied_time AS repliedTime, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM user_feedback" + where + " ORDER BY created_time DESC LIMIT ? OFFSET ?",
                pageArgs.toArray()
        );

        if (!rows.isEmpty()) {
            List<Long> ids = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Object idObj = row.get("id");
                if (idObj instanceof Number number) ids.add(number.longValue());
            }
            if (!ids.isEmpty()) {
                String inClause = ids.stream().map(String::valueOf).reduce((a, b) -> a + "," + b).orElse("0");
                List<Map<String, Object>> replyCounts = jdbcTemplate.queryForList(
                        "SELECT feedback_id AS feedbackId, COUNT(*) AS replyCount " +
                                "FROM user_feedback_reply WHERE replier_role='user' AND feedback_id IN (" + inClause + ") " +
                                "GROUP BY feedback_id"
                );
                Map<Long, Long> countMap = new java.util.HashMap<>();
                for (Map<String, Object> rc : replyCounts) {
                    Object fid = rc.get("feedbackId");
                    Object cnt = rc.get("replyCount");
                    if (fid instanceof Number fn && cnt instanceof Number cn) {
                        countMap.put(fn.longValue(), cn.longValue());
                    }
                }
                for (Map<String, Object> row : rows) {
                    Object idObj = row.get("id");
                    long fid = idObj instanceof Number ? ((Number) idObj).longValue() : 0L;
                    row.put("userReplyCount", countMap.getOrDefault(fid, 0L));
                }
            }
        }

        return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, user_id AS userId, username, category, title, content, contact, " +
                        "site_source AS siteSource, site_name AS siteName, " +
                        "status, priority, replier_user_id AS replierUserId, replier_username AS replierUsername, " +
                        "replied_time AS repliedTime, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM user_feedback WHERE id=? AND deleted=0 LIMIT 1",
                id
        );
        if (rows.isEmpty()) throw new BizException(404, "反馈不存在");

        Map<String, Object> feedback = rows.get(0);
        List<Map<String, Object>> replies = jdbcTemplate.queryForList(
                "SELECT id, replier_role AS replierRole, replier_user_id AS replierUserId, " +
                        "replier_username AS replierUsername, content, created_time AS createdTime " +
                        "FROM user_feedback_reply WHERE feedback_id=? ORDER BY created_time ASC",
                id
        );
        feedback.put("replies", replies);
        return Result.ok(feedback);
    }

    @PostMapping("/{id}/reply")
    public Result<Map<String, Object>> reply(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Long adminId = AdminContext.userId();
        String adminName = AdminContext.username();
        if (adminId == null) throw new BizException(401, "管理员登录状态已失效");

        String content = safe(body.get("content")).trim();
        if (content.isEmpty()) throw new BizException(400, "请填写回复内容");
        if (content.length() > 5000) throw new BizException(400, "回复内容过长，请控制在 5000 字以内");

        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_feedback WHERE id=? AND deleted=0",
                Integer.class,
                id
        );
        if (exists == null || exists == 0) throw new BizException(404, "反馈不存在");

        try {
            jdbcTemplate.update(
                    "INSERT INTO user_feedback_reply(" +
                            "feedback_id, tenant_id, replier_user_id, replier_username, replier_role, content, created_time" +
                            ") VALUES(?,?,?,?,?,?,NOW())",
                    id,
                    jdbcTemplate.queryForObject("SELECT tenant_id FROM user_feedback WHERE id=?", Long.class, id),
                    adminId,
                    adminName,
                    "admin",
                    content
            );
            jdbcTemplate.update(
                    "UPDATE user_feedback SET " +
                            "status='replied', replier_user_id=?, replier_username=?, replied_time=NOW(), updated_time=NOW() " +
                            "WHERE id=?",
                    adminId,
                    adminName,
                    id
            );
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            return Result.ok(res);
        } catch (Exception e) {
            logger.error("reply feedback failed: feedbackId={}, errorType={}", id, e.getClass().getSimpleName());
            throw new BizException(503, "反馈回复暂时不可用，请稍后重试");
        }
    }

    @PostMapping("/{id}/status")
    public Result<Map<String, Object>> changeStatus(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        String status = safe(body.get("status")).trim();
        if (!ALLOWED_STATUS.contains(status)) {
            throw new BizException(400, "状态值非法，允许值: " + String.join(", ", ALLOWED_STATUS));
        }

        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_feedback WHERE id=? AND deleted=0",
                Integer.class,
                id
        );
        if (exists == null || exists == 0) throw new BizException(404, "反馈不存在");

        try {
            jdbcTemplate.update("UPDATE user_feedback SET status=?, updated_time=NOW() WHERE id=?", status, id);
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            res.put("status", status);
            return Result.ok(res);
        } catch (Exception e) {
            logger.error("change feedback status failed: feedbackId={}, status={}, errorType={}", id, status, e.getClass().getSimpleName());
            throw new BizException(503, "反馈状态暂时无法修改，请稍后重试");
        }
    }

    @PostMapping("/{id}/priority")
    public Result<Map<String, Object>> changePriority(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        String priority = safe(body.get("priority")).trim();
        if (!ALLOWED_PRIORITY.contains(priority)) {
            throw new BizException(400, "优先级非法，允许值: " + String.join(", ", ALLOWED_PRIORITY));
        }

        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_feedback WHERE id=? AND deleted=0",
                Integer.class,
                id
        );
        if (exists == null || exists == 0) throw new BizException(404, "反馈不存在");

        try {
            jdbcTemplate.update("UPDATE user_feedback SET priority=?, updated_time=NOW() WHERE id=?", priority, id);
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            res.put("priority", priority);
            return Result.ok(res);
        } catch (Exception e) {
            logger.error("change feedback priority failed: feedbackId={}, priority={}, errorType={}", id, priority, e.getClass().getSimpleName());
            throw new BizException(503, "反馈优先级暂时无法修改，请稍后重试");
        }
    }

    @DeleteMapping("/{id}")
    public Result<Map<String, Object>> delete(@PathVariable Long id) {
        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_feedback WHERE id=? AND deleted=0",
                Integer.class,
                id
        );
        if (exists == null || exists == 0) throw new BizException(404, "反馈不存在");

        try {
            jdbcTemplate.update("UPDATE user_feedback SET deleted=1, updated_time=NOW() WHERE id=?", id);
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            return Result.ok(res);
        } catch (Exception e) {
            logger.error("delete feedback failed: feedbackId={}, errorType={}", id, e.getClass().getSimpleName());
            throw new BizException(503, "反馈暂时无法删除，请稍后重试");
        }
    }


    private String safe(Object value) {
        return value == null ? "" : String.valueOf(value);
    }
}

