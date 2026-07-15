package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * 商品同步任务维护服务。
 * 第二阶段补强：避免 xianyu_goods_sync_task 长期增长，并将长时间无更新的运行中任务标记为失败，
 * 便于用户端历史面板和后台排障看到稳定、可恢复的任务状态。
 */
@Service
public class SyncTaskMaintenanceService {
    private static final Logger log = LoggerFactory.getLogger(SyncTaskMaintenanceService.class);

    private final JdbcTemplate jdbcTemplate;

    @Value("${xianyu.sync-task.retention-days:30}")
    private int retentionDays;

    @Value("${xianyu.sync-task.stale-running-minutes:60}")
    private int staleRunningMinutes;

    public SyncTaskMaintenanceService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Scheduled(cron = "${xianyu.sync-task.cleanup-cron:0 15 3 * * ?}")
    public void scheduledCleanup() {
        try {
            int stale = markStaleRunningTasksFailed();
            int archived = softDeleteOldFinishedTasks();
            if (stale > 0 || archived > 0) {
                log.info("商品同步任务维护完成：staleFailed={}, archived={}", stale, archived);
            }
        } catch (Exception e) {
            log.warn("商品同步任务维护失败, errorType={}", e.getClass().getSimpleName());
        }
    }

    public int markStaleRunningTasksFailed() {
        int minutes = Math.max(5, staleRunningMinutes);
        return jdbcTemplate.update(
                "UPDATE xianyu_goods_sync_task SET status='failed', progress=COALESCE(NULLIF(progress,0),0), " +
                        "error_message=COALESCE(NULLIF(error_message,''),'任务长时间无更新，已自动标记失败'), " +
                        "finished_time=NOW(), updated_time=NOW() " +
                        "WHERE deleted=0 AND status IN ('queued','running') AND updated_time < DATE_SUB(NOW(), INTERVAL ? MINUTE)",
                minutes
        );
    }

    public int softDeleteOldFinishedTasks() {
        int days = Math.max(1, retentionDays);
        return jdbcTemplate.update(
                "UPDATE xianyu_goods_sync_task SET deleted=1, updated_time=NOW() " +
                        "WHERE deleted=0 AND status IN ('completed','failed','cancelled') " +
                        "AND COALESCE(finished_time, updated_time, created_time) < DATE_SUB(NOW(), INTERVAL ? DAY)",
                days
        );
    }
}
