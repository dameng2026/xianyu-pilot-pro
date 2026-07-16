package com.xianyu.admin.service;

import com.xianyu.admin.config.UploadPathConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/**
 * 上传图片自动清理服务。
 *
 * 设计目标：
 *   1. 不再对用户做图片存储配额限制（已移除 tenant / global quota 检查）；
 *   2. 为防止磁盘被无限累积，每日凌晨清理 7 天前上传且当前未被任何业务引用的图片；
 *   3. 删除前严格校验资产未被引用，确保删除后不会产生任何业务影响。
 *
 * 引用检查范围（与调研结果对齐）：
 *   - workflow_published_goods.source_image_url  —— 已发布商品的 AI 封面图本地 URL（审计/重试）
 *   - opportunity_image_history.result_images    —— 商机发掘生图历史 JSON（用户可见预览）
 *
 * 已发布商品的实时展示依赖闲鱼 CDN（xianyu_goods.cover_pic），不依赖本地路径，
 * 因此删除本地副本不会影响线上商品展示。
 */
@Service
public class UploadStorageCleanupService {
    private static final Logger log = LoggerFactory.getLogger(UploadStorageCleanupService.class);

    private final JdbcTemplate jdbcTemplate;
    private final UploadPathConfig uploadPaths;
    private final UploadStorageGovernanceService storageGovernance;

    @Value("${xianyu.upload.cleanup.retention-days:7}")
    private int retentionDays;

    @Value("${xianyu.upload.cleanup.batch-size:200}")
    private int batchSize;

    public UploadStorageCleanupService(
            JdbcTemplate jdbcTemplate,
            UploadPathConfig uploadPaths,
            UploadStorageGovernanceService storageGovernance) {
        this.jdbcTemplate = jdbcTemplate;
        this.uploadPaths = uploadPaths;
        this.storageGovernance = storageGovernance;
    }

    /** 测试用：覆盖保留天数。生产环境通过 @Value 注入。 */
    void setRetentionDaysForTest(int days) {
        this.retentionDays = days;
    }

    /** 测试用：覆盖批量大小。生产环境通过 @Value 注入。 */
    void setBatchSizeForTest(int size) {
        this.batchSize = size;
    }

    /**
     * 每日凌晨 03:30 执行清理。默认 cron 可通过配置覆盖。
     * 故意使用与 SyncTaskMaintenanceService 错开的时间点，避免抖动。
     */
    @Scheduled(cron = "${xianyu.upload.cleanup.cron:0 30 3 * * ?}")
    public void scheduledCleanup() {
        try {
            int deleted = cleanupUnreferencedOldAssets();
            if (deleted > 0) {
                log.info("上传图片自动清理完成：deletedAssets={} retentionDays={}", deleted, retentionDays);
            }
        } catch (Exception e) {
            log.warn("上传图片自动清理失败, errorType={}", e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 清理超过保留期且无业务引用的上传资产。
     *
     * @return 实际删除的资产数量
     */
    public int cleanupUnreferencedOldAssets() {
        int days = Math.max(1, retentionDays);
        int limit = Math.max(1, Math.min(batchSize, 1000));

        // 选取超过保留期、状态为 active、且未被任何业务表引用的资产。
        // - workflow_published_goods.source_image_url 直接等值匹配 public_url；
        // - opportunity_image_history.result_images 是 JSON 文本，使用 LIKE 模糊匹配 public_url 子串。
        //   public_url 形如 /uploads/images/tenant-1/xxx.png，足够独特不会误匹配。
        List<Map<String, Object>> candidates = jdbcTemplate.queryForList(
                "SELECT a.id, a.tenant_id, a.storage_key, a.public_url, a.size_bytes " +
                        "FROM tenant_storage_asset a " +
                        "WHERE a.status = 'active' " +
                        "  AND a.created_time < TIMESTAMPADD(DAY, -?, NOW()) " +
                        "  AND NOT EXISTS ( " +
                        "    SELECT 1 FROM workflow_published_goods w " +
                        "    WHERE w.source_image_url = a.public_url " +
                        "      AND COALESCE(w.deleted, 0) = 0 " +
                        "  ) " +
                        "  AND NOT EXISTS ( " +
                        "    SELECT 1 FROM opportunity_image_history o " +
                        "    WHERE o.result_images LIKE CONCAT('%', a.public_url, '%') " +
                        "      AND COALESCE(o.deleted, 0) = 0 " +
                        "  ) " +
                        "ORDER BY a.created_time ASC " +
                        "LIMIT ?",
                days, limit
        );

        if (candidates.isEmpty()) {
            return 0;
        }

        int deletedCount = 0;
        long deletedBytes = 0L;
        for (Map<String, Object> row : candidates) {
            long assetId = ((Number) row.get("id")).longValue();
            long tenantId = ((Number) row.get("tenant_id")).longValue();
            String storageKey = String.valueOf(row.get("storage_key"));
            long sizeBytes = ((Number) row.get("size_bytes")).longValue();
            try {
                Path target = uploadPaths.resolve(storageKey);
                storageGovernance.deleteStoredAsset(
                        assetId, tenantId, target, "auto-cleanup-7d-retention");
                deletedCount++;
                deletedBytes += sizeBytes;
            } catch (Exception e) {
                // 单条资产删除失败不阻断整体清理；deleting 状态会被后续 reconcile 恢复。
                log.warn("上传资产自动清理失败 assetId={} tenantId={} errorType={}",
                        assetId, tenantId, e.getClass().getSimpleName());
            }
        }

        if (deletedCount > 0) {
            log.info("上传图片自动清理统计：deletedCount={} deletedBytes={} retentionDays={}",
                    deletedCount, deletedBytes, days);
        }
        return deletedCount;
    }
}
