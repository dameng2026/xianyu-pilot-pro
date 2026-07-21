package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 数据保留策略定时清理服务。
 *
 * 设计要点（遵循 UploadStorageCleanupService 模式）：
 *   1. 每日凌晨 04:00 执行（与 UploadStorageCleanupService 03:30 错开）
 *   2. 对每个开启的类别，分批 500 条删除，每批独立事务，避免长事务锁表
 *   3. chatMessage 使用 message_time（毫秒时间戳），条件为
 *      `message_time < UNIX_TIMESTAMP(NOW() - INTERVAL ? DAY) * 1000`
 *   4. 其他类别使用 `created_time < DATE_SUB(NOW(), INTERVAL ? DAY)`
 *   5. 单类别清理异常不阻断其他类别
 *   6. 清理完成后回写 lastCleanup 统计
 *
 * 受保护表（订单、Token、充值等）绝不在此服务的 SQL 中引用。
 * 仅可清理 DataRetentionConfigService.CLEANUP_CATEGORIES 中列出的 8 张表。
 */
@Service
public class DataRetentionCleanupService {
    private static final Logger log = LoggerFactory.getLogger(DataRetentionCleanupService.class);

    private static final int BATCH_SIZE = 500;

    private final JdbcTemplate jdbcTemplate;
    private final DataRetentionConfigService configService;

    @Value("${xianyu.retention.cleanup-cron:0 0 4 * * ?}")
    private String cleanupCron;

    public DataRetentionCleanupService(JdbcTemplate jdbcTemplate, DataRetentionConfigService configService) {
        this.jdbcTemplate = jdbcTemplate;
        this.configService = configService;
    }

    /** 测试用：覆盖 cron（生产环境通过 @Value 注入，此处仅占位以保持一致性）。 */
    void setCleanupCronForTest(String cron) {
        this.cleanupCron = cron;
    }

    /**
     * 每日凌晨 04:00 执行清理。默认 cron 可通过 xianyu.retention.cleanup-cron 覆盖。
     */
    @Scheduled(cron = "${xianyu.retention.cleanup-cron:0 0 4 * * ?}")
    public void scheduledCleanup() {
        try {
            CleanupResult result = executeCleanup();
            if (result.totalDeleted > 0) {
                log.info("数据保留策略清理完成：totalDeleted={} byCategory={}",
                        result.totalDeleted, result.byCategory);
            }
        } catch (Exception e) {
            log.warn("数据保留策略清理失败, errorType={}", e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 执行一次完整清理。供定时任务和管理端手动触发调用。
     */
    public CleanupResult executeCleanup() {
        Map<String, Object> config = configService.getConfig();
        Object enabledObj = config.get("enabled");
        if (!Boolean.TRUE.equals(enabledObj)) {
            log.info("数据保留策略已禁用，跳过清理");
            return new CleanupResult(0, new LinkedHashMap<>());
        }

        int retentionDays;
        Object daysObj = config.get("retentionDays");
        if (daysObj instanceof Number n) {
            retentionDays = n.intValue();
        } else {
            retentionDays = 14;
        }
        if (retentionDays < 1) retentionDays = 1;

        @SuppressWarnings("unchecked")
        Map<String, Object> categories = (Map<String, Object>) config.get("categories");
        if (categories == null) categories = new LinkedHashMap<>();

        CleanupResult result = new CleanupResult(0, new LinkedHashMap<>());
        for (String category : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            if (!Boolean.TRUE.equals(categories.get(category))) {
                continue;
            }
            try {
                int deleted = cleanupCategory(category, retentionDays);
                if (deleted > 0) {
                    result.totalDeleted += deleted;
                    result.byCategory.put(category, deleted);
                }
            } catch (Exception e) {
                log.warn("清理类别 {} 失败, errorType={}", category, e.getClass().getSimpleName(), e);
            }
        }

        try {
            configService.recordCleanupResult(result.totalDeleted, result.byCategory);
        } catch (Exception e) {
            log.warn("回写清理统计失败, errorType={}", e.getClass().getSimpleName(), e);
        }
        return result;
    }

    /**
     * 清理单个类别的旧数据，分批删除直到某批返回 0 行。
     */
    private int cleanupCategory(String category, int retentionDays) {
        String sql = buildDeleteSql(category);
        if (sql == null) {
            log.warn("未知的清理类别：{}", category);
            return 0;
        }
        int totalDeleted = 0;
        int maxBatches = 200; // 安全阀：单类别最多 200 批 = 100,000 条
        while (maxBatches-- > 0) {
            int affected;
            try {
                affected = jdbcTemplate.update(sql, retentionDays, BATCH_SIZE);
            } catch (Exception e) {
                log.warn("清理类别 {} 第 {} 批失败, errorType={}",
                        category, 200 - maxBatches, e.getClass().getSimpleName(), e);
                throw e;
            }
            if (affected <= 0) break;
            totalDeleted += affected;
            if (affected < BATCH_SIZE) break;
        }
        return totalDeleted;
    }

    /**
     * 为每个类别构建 DELETE SQL。
     *
     * chatMessage 使用 message_time（毫秒时间戳），条件为
     *   `message_time < UNIX_TIMESTAMP(NOW() - INTERVAL ? DAY) * 1000`
     * 其他类别使用 `created_time < DATE_SUB(NOW(), INTERVAL ? DAY)`
     *
     * LIMIT 用于分批，避免长事务锁表。
     */
    private String buildDeleteSql(String category) {
        // 表名硬编码（不通过字符串拼接外部输入），避免 SQL 注入风险
        switch (category) {
            case "operationLog":
                return "DELETE FROM operation_log WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "clientErrorLog":
                return "DELETE FROM client_error_log WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "notificationLog":
                return "DELETE FROM notification_delivery_log WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "notificationDedup":
                return "DELETE FROM notification_dedup WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "chatMessage":
                return "DELETE FROM xianyu_chat_message WHERE message_time < UNIX_TIMESTAMP(NOW() - INTERVAL ? DAY) * 1000 LIMIT ?";
            case "captchaRecord":
                return "DELETE FROM xianyu_captcha_solve_record WHERE created_at < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "autoReplyLog":
                return "DELETE FROM auto_reply_log WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            case "uploadRateEvent":
                return "DELETE FROM tenant_upload_rate_event WHERE created_time < DATE_SUB(NOW(), INTERVAL ? DAY) LIMIT ?";
            default:
                return null;
        }
    }

    /** 清理结果。 */
    public static class CleanupResult {
        public int totalDeleted;
        public final Map<String, Integer> byCategory;

        public CleanupResult(int totalDeleted, Map<String, Integer> byCategory) {
            this.totalDeleted = totalDeleted;
            this.byCategory = byCategory;
        }
    }
}
