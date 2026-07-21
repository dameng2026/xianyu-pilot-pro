package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Phase3 运营监控面板接口。
 * 面向后台：AI 成本/调用、自动回复效果、工作流失败率。
 */
@RestController
@RequestMapping("/admin-api/monitor")
public class AdminMonitoringController {
    private static final Logger log = LoggerFactory.getLogger(AdminMonitoringController.class);
    private final JdbcTemplate jdbcTemplate;

    public AdminMonitoringController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/ai/token-stats")
    public Result<Map<String, Object>> aiTokenStats(@RequestParam(defaultValue = "7") int days) {
        try {
            int safeDays = clamp(days, 1, 90);
            LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("totalTokens", optionalLong("SELECT COALESCE(SUM(total_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalChargeTokens", optionalLong("SELECT COALESCE(SUM(charge_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalCalls", optionalLong("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalCostCent", optionalLong("SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalCachedTokens", optionalLong("SELECT COALESCE(SUM(cached_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalPromptTokens", optionalLong("SELECT COALESCE(SUM(prompt_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("totalCompletionTokens", optionalLong("SELECT COALESCE(SUM(completion_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1"));
            m.put("dailyTokens", queryList(
                    "SELECT DATE(created_time) AS statDate, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS promptTokens, COALESCE(SUM(completion_tokens),0) AS completionTokens, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(total_tokens),0) AS totalTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent " +
                            "FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));
            m.put("dailyCost", queryList(
                    "SELECT DATE(created_time) AS statDate, COALESCE(SUM(cost_cent),0) AS costCent FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));
            return Result.ok(m);
        } catch (Exception e) {
            log.error("aiTokenStats error, days={}, errorType={}", days, e.getClass().getSimpleName());
            throw new BizException(503, "Token 统计数据暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/ai/cost-stats")
    public Result<Map<String, Object>> aiCostStats(@RequestParam(defaultValue = "7") int days,
                                                    @RequestParam(required = false) String groupBy) {
        try {
            if (groupBy != null && !groupBy.isBlank()
                    && !List.of("all", "day", "model", "scene").contains(groupBy.trim().toLowerCase())) {
                throw new BizException(400, "groupBy 仅支持 all、day、model 或 scene");
            }
            int safeDays = clamp(days, 1, 90);
            LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("totalCostCent", optionalLong("SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=?", start));
            m.put("totalCalls", optionalLong("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=?", start));
            m.put("totalChargeTokens", optionalLong("SELECT COALESCE(SUM(charge_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=?", start));
            m.put("totalCachedTokens", optionalLong("SELECT COALESCE(SUM(cached_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=?", start));

            m.put("byModel", queryList(
                    "SELECT COALESCE(provider_name,'-') AS providerName, COALESCE(model_name,'-') AS modelName, " +
                            "COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS promptTokens, COALESCE(SUM(completion_tokens),0) AS completionTokens, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(total_tokens),0) AS totalTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent " +
                            "FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=? GROUP BY provider_name, model_name ORDER BY calls DESC LIMIT 20", start));

            m.put("byScene", queryList(
                    "SELECT COALESCE(scene,'unknown') AS scene, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS promptTokens, COALESCE(SUM(completion_tokens),0) AS completionTokens, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(total_tokens),0) AS totalTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent " +
                            "FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=? GROUP BY COALESCE(scene,'unknown') ORDER BY calls DESC LIMIT 20", start));

            m.put("dailyTrend", queryList(
                    "SELECT DATE(created_time) AS statDate, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS promptTokens, COALESCE(SUM(completion_tokens),0) AS completionTokens, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(total_tokens),0) AS totalTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent " +
                            "FROM ai_usage_log WHERE deleted=0 AND status=1 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));

            return Result.ok(m);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("aiCostStats error, days={}, errorType={}", days, e.getClass().getSimpleName());
            throw new BizException(503, "费用统计数据暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/ai/user-stats")
    public Result<PageResult<Map<String, Object>>> aiUserStats(@RequestParam(defaultValue = "1") int current,
                                                               @RequestParam(defaultValue = "20") int size,
                                                               @RequestParam(defaultValue = "7") int days,
                                                               @RequestParam(required = false) String keyword,
                                                               @RequestParam(defaultValue = "calls") String sortBy,
                                                               @RequestParam(defaultValue = "desc") String sortOrder) {
        try {
            int safeDays = clamp(days, 1, 90);
            int safeCurrent = Math.max(1, current);
            int safeSize = clamp(size, 1, 200);
            int offset = (safeCurrent - 1) * safeSize;
            LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
            List<Object> args = new ArrayList<>();
            StringBuilder where = new StringBuilder(" WHERE l.deleted=0 AND l.status=1 AND l.created_time>=?");
            args.add(start);
            if (keyword != null && !keyword.isBlank()) {
                where.append(" AND u.username LIKE ?");
                args.add("%" + keyword.trim() + "%");
            }
            String validSort;
            switch (sortBy) {
                case "calls": case "totalTokens": case "chargeTokens": case "costCent":
                    validSort = sortBy; break;
                default: validSort = "calls";
            }
            String validOrder = "asc".equalsIgnoreCase(sortOrder) ? "ASC" : "DESC";

            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(DISTINCT l.user_id) FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where,
                    Long.class, args.toArray());

            List<Object> pageArgs = new ArrayList<>(args);
            pageArgs.add(safeSize); pageArgs.add(offset);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT l.user_id AS userId, COALESCE(u.username,'-') AS username, " +
                            "COUNT(*) AS calls, COALESCE(SUM(l.prompt_tokens),0) AS promptTokens, " +
                            "COALESCE(SUM(l.completion_tokens),0) AS completionTokens, COALESCE(SUM(l.cached_tokens),0) AS cachedTokens, " +
                            "COALESCE(SUM(l.total_tokens),0) AS totalTokens, " +
                            "COALESCE(SUM(l.charge_tokens),0) AS chargeTokens, COALESCE(SUM(l.cost_cent),0) AS costCent, " +
                            "MAX(l.created_time) AS lastCallTime " +
                            "FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where +
                            " GROUP BY l.user_id, u.username ORDER BY " + validSort + " " + validOrder +
                            " LIMIT ? OFFSET ?", pageArgs.toArray());
            rows.forEach(this::decorateCost);
            return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
        } catch (Exception e) {
            log.error("aiUserStats error, days={}, sortBy={}, errorType={}", days, sortBy, e.getClass().getSimpleName());
            throw new BizException(503, "用户 AI 统计数据暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/ai")
    public Result<Map<String, Object>> ai(@RequestParam(defaultValue = "7") int days) {
        int safeDays = clamp(days, 1, 90);
        LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("days", safeDays);
        m.put("todayCalls", optionalLong("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayChargeTokens", optionalLong("SELECT COALESCE(SUM(charge_tokens),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayCostCent", optionalLong("SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log WHERE deleted=0 AND status=1 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("totalCalls", optionalLong("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0"));
        m.put("failedCalls", optionalLong("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status<>1"));
        m.put("lowBalanceUsers", optionalLong("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND COALESCE(token_balance,0)<100"));
        m.put("daily", queryList("SELECT DATE(created_time) AS statDate, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS promptTokens, COALESCE(SUM(completion_tokens),0) AS completionTokens, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent FROM ai_usage_log WHERE deleted=0 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));
        m.put("byScene", queryList("SELECT COALESCE(scene,'unknown') AS scene, COUNT(*) AS calls, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent FROM ai_usage_log WHERE deleted=0 AND created_time>=? GROUP BY COALESCE(scene,'unknown') ORDER BY calls DESC LIMIT 20", start));
        m.put("byModel", queryList("SELECT COALESCE(provider_name,'-') AS providerName, COALESCE(model_name,'-') AS modelName, COUNT(*) AS calls, COALESCE(SUM(cached_tokens),0) AS cachedTokens, COALESCE(SUM(charge_tokens),0) AS chargeTokens, COALESCE(SUM(cost_cent),0) AS costCent FROM ai_usage_log WHERE deleted=0 AND created_time>=? GROUP BY provider_name, model_name ORDER BY calls DESC LIMIT 20", start));
        return Result.ok(m);
    }

    @GetMapping("/ai/usage")
    public Result<PageResult<Map<String, Object>>> aiUsage(@RequestParam(defaultValue = "1") int current,
                                                           @RequestParam(defaultValue = "20") int size,
                                                           @RequestParam(required = false) String scene,
                                                           @RequestParam(required = false) String keyword,
                                                           @RequestParam(required = false) String status,
                                                           @RequestParam(required = false) Long userId) {
        int safeCurrent = Math.max(1, current);
        int safeSize = clamp(size, 1, 200);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE l.deleted=0 ");
        if (userId != null) {
            where.append(" AND l.user_id=? ");
            args.add(userId);
        }
        if (scene != null && !scene.isBlank()) {
            where.append(" AND l.scene=? ");
            args.add(scene.trim());
        }
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (l.model_name LIKE ? OR l.provider_name LIKE ? OR l.request_id LIKE ? OR u.username LIKE ?) ");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw); args.add(kw);
        }
        if (status != null && !status.isBlank()) {
            if ("success".equalsIgnoreCase(status.trim()) || "成功".equals(status.trim()) || "1".equals(status.trim())) {
                where.append(" AND l.status=1 ");
            } else if ("failed".equalsIgnoreCase(status.trim()) || "失败".equals(status.trim()) || "0".equals(status.trim())) {
                where.append(" AND l.status=0 ");
            }
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT l.id, l.tenant_id AS tenantId, l.user_id AS userId, u.username, l.scene, l.provider_name AS providerName, l.model_name AS modelName, l.request_id AS requestId, l.prompt_tokens AS promptTokens, l.completion_tokens AS completionTokens, l.cached_tokens AS cachedTokens, l.total_tokens AS totalTokens, l.charge_tokens AS chargeTokens, l.cost_cent AS costCent, l.status, CASE WHEN l.error_message IS NULL OR l.error_message='' THEN NULL ELSE '调用失败，请按 requestId 查询服务端日志' END AS errorMessage, l.created_time AS createdTime FROM ai_usage_log l LEFT JOIN sys_user u ON u.id=l.user_id" + where + " ORDER BY l.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        rows.forEach(this::decorateCost);
        return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
    }

    @GetMapping("/auto-reply")
    public Result<Map<String, Object>> autoReply(@RequestParam(defaultValue = "7") int days) {
        int safeDays = clamp(days, 1, 90);
        LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("days", safeDays);
        m.put("todayHits", optionalLong("SELECT COUNT(*) FROM auto_reply_log WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayAutoAllowed", optionalLong("SELECT COUNT(*) FROM auto_reply_log WHERE deleted=0 AND action='auto_send_allowed' AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayManual", optionalLong("SELECT COUNT(*) FROM auto_reply_log WHERE deleted=0 AND action IN ('manual','suggest_only') AND DATE(created_time)=CURRENT_DATE()"));
        m.put("enabledRules", optionalLong("SELECT COUNT(*) FROM auto_reply_rule WHERE deleted=0 AND status=1"));
        m.put("daily", queryList("SELECT DATE(created_time) AS statDate, COUNT(*) AS hits, SUM(CASE WHEN action='auto_send_allowed' THEN 1 ELSE 0 END) AS autoAllowed, SUM(CASE WHEN action IN ('manual','suggest_only') THEN 1 ELSE 0 END) AS handoff FROM auto_reply_log WHERE deleted=0 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));
        m.put("actions", queryList("SELECT COALESCE(action,'unknown') AS action, COUNT(*) AS count FROM auto_reply_log WHERE deleted=0 AND created_time>=? GROUP BY COALESCE(action,'unknown') ORDER BY count DESC", start));
        m.put("topRules", queryList("SELECT l.rule_id AS ruleId, COALESCE(r.rule_name, CONCAT('规则#',l.rule_id)) AS ruleName, COUNT(*) AS hits, SUM(CASE WHEN l.action='auto_send_allowed' THEN 1 ELSE 0 END) AS autoAllowed FROM auto_reply_log l LEFT JOIN auto_reply_rule r ON r.id=l.rule_id WHERE l.deleted=0 AND l.created_time>=? GROUP BY l.rule_id, r.rule_name ORDER BY hits DESC LIMIT 20", start));
        return Result.ok(m);
    }

    @GetMapping("/workflow")
    public Result<Map<String, Object>> workflow(@RequestParam(defaultValue = "7") int days) {
        int safeDays = clamp(days, 1, 90);
        LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("days", safeDays);
        m.put("todayExecutions", optionalLong("SELECT COUNT(*) FROM workflow_execution WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()"));
        m.put("todayFailed", optionalLong("SELECT COUNT(*) FROM workflow_execution WHERE deleted=0 AND status IN ('failed','terminated') AND DATE(created_time)=CURRENT_DATE()"));
        m.put("running", optionalLong("SELECT COUNT(*) FROM workflow_execution WHERE deleted=0 AND status IN ('queued','running')"));
        m.put("publishedDefinitions", optionalLong("SELECT COUNT(*) FROM workflow_definition WHERE deleted=0 AND status='published'"));
        m.put("daily", queryList("SELECT DATE(created_time) AS statDate, COUNT(*) AS executions, SUM(CASE WHEN status IN ('failed','terminated') THEN 1 ELSE 0 END) AS failed, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success FROM workflow_execution WHERE deleted=0 AND created_time>=? GROUP BY DATE(created_time) ORDER BY statDate", start));
        m.put("byStatus", queryList("SELECT status, COUNT(*) AS count FROM workflow_execution WHERE deleted=0 AND created_time>=? GROUP BY status ORDER BY count DESC", start));
        m.put("topFailures", queryList("SELECT workflow_id AS workflowId, COUNT(*) AS failedCount, '执行失败，请查询服务端日志' AS lastError, MAX(created_time) AS lastFailedAt FROM workflow_execution WHERE deleted=0 AND status IN ('failed','terminated') AND created_time>=? GROUP BY workflow_id ORDER BY failedCount DESC LIMIT 20", start));
        return Result.ok(m);
    }

    private int clamp(int v, int min, int max) {
        return Math.max(min, Math.min(max, v));
    }

    private long optionalLong(String sql) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class);
            return v == null ? 0 : v;
        } catch (Exception e) {
            log.error("monitoring aggregate query failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "监控数据暂时不可用，请稍后重试");
        }
    }

    private long optionalLong(String sql, Object... args) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class, args);
            return v == null ? 0 : v;
        } catch (Exception e) {
            log.error("monitoring aggregate query failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "监控数据暂时不可用，请稍后重试");
        }
    }

    private List<Map<String, Object>> queryList(String sql, Object... args) {
        try {
            return jdbcTemplate.queryForList(sql, args);
        } catch (Exception e) {
            log.error("monitoring list query failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "监控数据暂时不可用，请稍后重试");
        }
    }

    private void decorateCost(Map<String, Object> row) {
        Long cent = null;
        Object raw = row.get("costCent");
        try {
            cent = raw == null ? 0L : Long.parseLong(String.valueOf(raw));
        } catch (NumberFormatException ignored) {
            row.put("dataStatus", "invalid_cost");
        }
        row.put("costYuan", cent == null ? null : BigDecimal.valueOf(cent).divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString());
        Object status = row.get("status");
        String statusValue = String.valueOf(status);
        row.put("statusText", "1".equals(statusValue) ? "成功" : ("0".equals(statusValue) ? "失败" : "未知"));
    }
}
