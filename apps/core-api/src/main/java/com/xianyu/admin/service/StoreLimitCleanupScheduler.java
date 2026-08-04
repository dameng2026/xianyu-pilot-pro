package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 会员等级店铺数量超限清理定时任务。
 *
 * 背景：会员体系升级为 普通用户 / VIP（单店版）/ VIP / SVIP 后，
 * 部分存量用户（如普通用户绑定多个闲鱼店铺）超过其等级允许的店铺数量。
 * 上线后按计划于 2026-08-06 24:00（2026-08-07 00:00:00）执行一次，
 * 保留每个用户最活跃的店铺，其余多余店铺执行软删除（可恢复）。
 *
 * 幂等与并发：
 * - 通过 admin_module_record（module_key=store_limit_cleanup）记录执行状态；
 * - running：正在执行（其他实例跳过）；done：已完成（不再执行）；failed：执行失败（下次重试）。
 *
 * 保留策略：优先保留 Cookie 可用且最近活跃（最后登录/心跳/更新时间）的店铺。
 */
@Component
public class StoreLimitCleanupScheduler {
    private static final Logger log = LoggerFactory.getLogger(StoreLimitCleanupScheduler.class);

    private static final String MODULE_KEY = "store_limit_cleanup";
    private static final String STATUS_RUNNING = "running";
    private static final String STATUS_DONE = "done";
    private static final String STATUS_FAILED = "failed";

    private final JdbcTemplate jdbcTemplate;
    private final FeatureSwitchService featureSwitchService;
    private final XianyuAccountService accountService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${xianyu.store-limit.cleanup-after:2026-08-07T00:00:00}")
    private String cleanupAfter;

    public StoreLimitCleanupScheduler(JdbcTemplate jdbcTemplate,
                                      FeatureSwitchService featureSwitchService,
                                      XianyuAccountService accountService) {
        this.jdbcTemplate = jdbcTemplate;
        this.featureSwitchService = featureSwitchService;
        this.accountService = accountService;
    }

    @Scheduled(cron = "${xianyu.store-limit.cleanup-cron:0 */10 * * * ?}")
    public void scheduledCleanup() {
        LocalDateTime target;
        try {
            target = LocalDateTime.parse(cleanupAfter);
        } catch (DateTimeParseException e) {
            log.warn("店铺数量清理时间配置无效 cleanupAfter={}, 跳过本次执行", cleanupAfter);
            return;
        }
        if (LocalDateTime.now().isBefore(target)) {
            return;
        }
        try {
            if (!tryAcquireRun()) return;
            Map<String, Object> summary = runCleanup();
            completeRun(summary);
        } catch (Exception e) {
            log.error("店铺数量超限清理失败, errorType={}", e.getClass().getSimpleName(), e);
            failRun(e.getMessage());
        }
    }

    /**
     * 尝试标记为 running（幂等/并发保护）。
     * 已存在 running/done 记录时返回 false；failed 记录允许重试。
     */
    private boolean tryAcquireRun() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, status FROM admin_module_record WHERE module_key=? AND deleted=0 ORDER BY id ASC LIMIT 1",
                MODULE_KEY);
        if (!rows.isEmpty()) {
            String status = String.valueOf(rows.get(0).get("status"));
            if (STATUS_RUNNING.equals(status) || STATUS_DONE.equals(status)) {
                return false;
            }
            // failed：重置为 running 后重试
            jdbcTemplate.update(
                    "UPDATE admin_module_record SET status=?, json_text=?, updated_time=NOW() WHERE id=?",
                    STATUS_RUNNING, "{\"retry\": true}", rows.get(0).get("id"));
            return true;
        }
        int affected = jdbcTemplate.update(
                "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) " +
                        "VALUES(?, ?, ?, NOW(), NOW(), 0)",
                MODULE_KEY, STATUS_RUNNING, "{\"running\": true}");
        return affected == 1;
    }

    private Map<String, Object> runCleanup() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("executedAt", LocalDateTime.now().toString());
        summary.put("targetTime", cleanupAfter);
        List<Map<String, Object>> removed = new ArrayList<>();
        int userCount = 0;
        int removedCount = 0;

        List<Map<String, Object>> users = jdbcTemplate.queryForList(
                "SELECT DISTINCT a.user_id, a.tenant_id FROM xianyu_account a " +
                        "WHERE a.deleted=0 AND a.user_id IS NOT NULL ORDER BY a.user_id");
        for (Map<String, Object> userRow : users) {
            Number userIdNum = (Number) userRow.get("user_id");
            Number tenantIdNum = (Number) userRow.get("tenant_id");
            if (userIdNum == null) continue;
            long userId = userIdNum.longValue();
            Long tenantId = tenantIdNum == null ? null : tenantIdNum.longValue();
            String planCode = featureSwitchService.resolveUserPlanCode(userId);
            int limit = featureSwitchService.storeLimitForPlanCode(planCode);
            if (limit <= 0) continue;

            long count = countAccounts(userId);
            if (count <= limit) continue;
            userCount++;

            // 保留策略：Cookie 可用优先，其次最近活跃（最后登录/心跳/更新时间），最后按 id 倒序
            List<Map<String, Object>> candidates = jdbcTemplate.queryForList(
                    "SELECT a.id, a.tenant_id FROM xianyu_account a " +
                            "LEFT JOIN xianyu_account_auth auth ON auth.account_id=a.id AND auth.tenant_id=a.tenant_id AND auth.deleted=0 " +
                            "LEFT JOIN xianyu_account_runtime r ON r.account_id=a.id AND r.tenant_id=a.tenant_id AND r.deleted=0 " +
                            "WHERE a.user_id=? AND a.deleted=0 " +
                            "ORDER BY (auth.cookie_status=1) DESC, " +
                            "COALESCE(r.last_login_time, r.last_heartbeat_time, a.updated_time, a.created_time) DESC, " +
                            "a.id DESC",
                    userId);
            for (int i = 0; i < candidates.size(); i++) {
                if (i < limit) continue; // 保留前 limit 个
                Map<String, Object> row = candidates.get(i);
                long accountId = ((Number) row.get("id")).longValue();
                Long acctTenantId = row.get("tenant_id") == null ? null : ((Number) row.get("tenant_id")).longValue();
                try {
                    accountService.delete(acctTenantId == null ? (tenantId == null ? 0L : tenantId) : acctTenantId, accountId);
                    removedCount++;
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("userId", userId);
                    item.put("tenantId", acctTenantId == null ? tenantId : acctTenantId);
                    item.put("accountId", accountId);
                    item.put("planCode", planCode);
                    item.put("limit", limit);
                    item.put("countBefore", count);
                    removed.add(item);
                } catch (Exception e) {
                    log.warn("删除超限店铺失败 userId={} accountId={} errorType={}",
                            userId, accountId, e.getClass().getSimpleName());
                }
            }
        }
        summary.put("userCount", userCount);
        summary.put("removedCount", removedCount);
        summary.put("removedAccounts", removed);
        return summary;
    }

    private long countAccounts(Long userId) {
        Long n = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM xianyu_account WHERE user_id=? AND deleted=0",
                Long.class, userId);
        return n == null ? 0 : n;
    }

    private void completeRun(Map<String, Object> summary) {
        try {
            String json = objectMapper.writeValueAsString(summary);
            jdbcTemplate.update(
                    "UPDATE admin_module_record SET status=?, json_text=?, updated_time=NOW() WHERE module_key=? AND deleted=0",
                    STATUS_DONE, json, MODULE_KEY);
            log.info("店铺数量超限清理完成: 用户数={}, 移除店铺数={}",
                    summary.get("userCount"), summary.get("removedCount"));
        } catch (Exception e) {
            log.warn("写入店铺数量清理完成标记失败, errorType={}", e.getClass().getSimpleName());
        }
    }

    private void failRun(String message) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("status", STATUS_FAILED);
            body.put("failedAt", LocalDateTime.now().toString());
            body.put("message", message == null ? "unknown" : message.substring(0, Math.min(message.length(), 500)));
            jdbcTemplate.update(
                    "UPDATE admin_module_record SET status=?, json_text=?, updated_time=NOW() WHERE module_key=? AND deleted=0",
                    STATUS_FAILED, objectMapper.writeValueAsString(body), MODULE_KEY);
        } catch (Exception e) {
            log.warn("写入店铺数量清理失败标记异常, errorType={}", e.getClass().getSimpleName());
        }
    }
}
