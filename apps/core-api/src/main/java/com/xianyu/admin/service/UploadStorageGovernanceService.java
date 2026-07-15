package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.config.UploadPathConfig;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.jdbc.core.JdbcTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

/** Cross-process quota/rate/concurrency admission for Java upload writers. */
@Service
public class UploadStorageGovernanceService {
    private static final int STALE_RESERVATION_SECONDS = 600;
    private static final String GLOBAL_UPLOAD_LOCK = "tenant-upload-global";
    private static final Pattern SAFE_METADATA = Pattern.compile("[A-Za-z0-9_-]{1,64}");
    private static final Pattern SAFE_IMAGE_TYPE = Pattern.compile("image/(?:jpeg|png|gif|webp)");
    private static final Logger log = LoggerFactory.getLogger(UploadStorageGovernanceService.class);

    private final JdbcTemplate jdbcTemplate;
    private final TransactionTemplate transactionTemplate;
    private final UploadPathConfig uploadPaths;
    private final Environment environment;
    private final String enabledRaw;
    private final String tenantQuotaRaw;
    private final String globalQuotaRaw;
    private final String rateRequestsRaw;
    private final String rateWindowRaw;
    private final String tenantConcurrentRaw;
    private final String globalConcurrentRaw;

    private boolean enabled;
    private long tenantQuotaBytes;
    private long globalQuotaBytes;
    private int rateRequests;
    private int rateWindowSeconds;
    private int maxConcurrentPerTenant;
    private int maxConcurrentGlobal;
    private Semaphore localWriteSemaphore;

    public UploadStorageGovernanceService(
            JdbcTemplate jdbcTemplate,
            PlatformTransactionManager transactionManager,
            UploadPathConfig uploadPaths,
            Environment environment,
            @Value("${UPLOAD_GOVERNANCE_ENABLED:}") String enabledRaw,
            @Value("${UPLOAD_TENANT_QUOTA_BYTES:}") String tenantQuotaRaw,
            @Value("${UPLOAD_GLOBAL_QUOTA_BYTES:}") String globalQuotaRaw,
            @Value("${UPLOAD_RATE_LIMIT_REQUESTS:}") String rateRequestsRaw,
            @Value("${UPLOAD_RATE_LIMIT_WINDOW_SECONDS:}") String rateWindowRaw,
            @Value("${UPLOAD_MAX_CONCURRENT_PER_TENANT:}") String tenantConcurrentRaw,
            @Value("${UPLOAD_MAX_CONCURRENT_GLOBAL:}") String globalConcurrentRaw) {
        this.jdbcTemplate = jdbcTemplate;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.uploadPaths = uploadPaths;
        this.environment = environment;
        this.enabledRaw = enabledRaw;
        this.tenantQuotaRaw = tenantQuotaRaw;
        this.globalQuotaRaw = globalQuotaRaw;
        this.rateRequestsRaw = rateRequestsRaw;
        this.rateWindowRaw = rateWindowRaw;
        this.tenantConcurrentRaw = tenantConcurrentRaw;
        this.globalConcurrentRaw = globalConcurrentRaw;
    }

    @PostConstruct
    void init() {
        boolean production = environment.acceptsProfiles(Profiles.of("prod", "production", "staging"));
        if (production && (!"true".equalsIgnoreCase(enabledRaw)
                || tenantQuotaRaw.isBlank() || globalQuotaRaw.isBlank()
                || rateRequestsRaw.isBlank() || rateWindowRaw.isBlank()
                || tenantConcurrentRaw.isBlank() || globalConcurrentRaw.isBlank())) {
            throw new IllegalStateException("production upload governance limits must be explicit");
        }
        enabled = enabledRaw.isBlank() || Boolean.parseBoolean(enabledRaw);
        tenantQuotaBytes = positiveLong(tenantQuotaRaw, 100L * 1024 * 1024, "tenant quota");
        globalQuotaBytes = positiveLong(globalQuotaRaw, 10L * 1024 * 1024 * 1024, "global quota");
        rateRequests = positiveInt(rateRequestsRaw, 30, "rate requests");
        rateWindowSeconds = positiveInt(rateWindowRaw, 60, "rate window");
        maxConcurrentPerTenant = positiveInt(tenantConcurrentRaw, 2, "tenant concurrency");
        maxConcurrentGlobal = positiveInt(globalConcurrentRaw, 8, "global concurrency");
        if (globalQuotaBytes < tenantQuotaBytes || maxConcurrentGlobal < maxConcurrentPerTenant) {
            throw new IllegalStateException("global upload limits must not be smaller than tenant limits");
        }
        localWriteSemaphore = new Semaphore(maxConcurrentGlobal, true);
    }

    public StoredAsset store(long scopeTenantId, Long userId, String storageKey,
                             String publicUrl, String mediaType, String sourceType,
                             byte[] content) {
        return storeInternal(
                scopeTenantId, userId, storageKey, publicUrl, mediaType, sourceType,
                "private", sourceType, userId == null ? "service" : "user", userId, content);
    }

    /** Store an asset in the deliberately public namespace. */
    public StoredAsset storePublic(long scopeTenantId, Long userId, String storageKey,
                                   String publicUrl, String mediaType, String sourceType,
                                   String purpose, byte[] content) {
        if (!PublicMediaPolicy.allowsSystemLogoWrite(
                scopeTenantId, userId, storageKey, publicUrl, mediaType, sourceType, purpose)) {
            throw new BizException(400, "公开媒体路径、归属或用途无效");
        }
        return storeInternal(
                scopeTenantId, userId, storageKey, publicUrl, mediaType, sourceType,
                "public", purpose, userId == null ? "service" : "user", userId, content);
    }

    private StoredAsset storeInternal(
            long scopeTenantId,
            Long userId,
            String storageKey,
            String publicUrl,
            String mediaType,
            String sourceType,
            String visibility,
            String purpose,
            String ownerType,
            Long ownerId,
            byte[] content) {
        if (!enabled) throw new BizException(503, "上传治理服务不可用");
        if (scopeTenantId < 0 || userId != null && userId <= 0
                || content == null || content.length == 0
                || storageKey == null || storageKey.isBlank() || storageKey.length() > 512
                || storageKey.contains("\\")
                || publicUrl == null || !publicUrl.startsWith("/uploads/")
                || publicUrl.length() > 700 || publicUrl.contains("\\")
                || publicUrl.contains("?") || publicUrl.contains("#")
                || mediaType == null || !SAFE_IMAGE_TYPE.matcher(mediaType).matches()
                || sourceType == null || !SAFE_METADATA.matcher(sourceType).matches()
                || purpose == null || !SAFE_METADATA.matcher(purpose).matches()
                || ownerType == null || !SAFE_METADATA.matcher(ownerType).matches()
                || !("private".equals(visibility) || "public".equals(visibility))) {
            throw new BizException(400, "上传资产参数无效");
        }
        boolean permit;
        try {
            permit = localWriteSemaphore.tryAcquire(2, TimeUnit.SECONDS);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "上传请求已中断");
        }
        if (!permit) throw new BizException(429, "平台并发上传已达上限，请稍后重试");

        long assetId = 0L;
        Path target = uploadPaths.resolve(storageKey);
        boolean targetPublished = false;
        try {
            if (Files.exists(target)) {
                throw new BizException(409, "上传目标已存在，拒绝覆盖");
            }
            assetId = reserve(scopeTenantId, userId, storageKey, publicUrl,
                    mediaType, sourceType, visibility, purpose, ownerType, ownerId,
                    content.length, sha256(content));
            uploadPaths.writeAtomically(target, content);
            targetPublished = true;
            int activated = jdbcTemplate.update(
                    "UPDATE tenant_storage_asset SET status='active', activated_time=NOW(), " +
                            "published_time=CASE WHEN visibility='public' THEN NOW() ELSE NULL END, " +
                            "updated_time=NOW() " +
                            "WHERE id=? AND tenant_id=? AND status='reserved'",
                    assetId, scopeTenantId);
            if (activated != 1) throw new BizException(503, "上传资产状态确认失败");
            return new StoredAsset(assetId, storageKey, publicUrl, content.length);
        } catch (Exception failure) {
            if (targetPublished) {
                try { Files.deleteIfExists(target); } catch (IOException ignored) {}
            }
            if (assetId > 0) {
                try {
                    jdbcTemplate.update(
                            "UPDATE tenant_storage_asset SET status='failed', deletion_reason=?, updated_time=NOW() " +
                                    "WHERE id=? AND tenant_id=? AND status='reserved'",
                            failure.getClass().getSimpleName(), assetId, scopeTenantId);
                } catch (RuntimeException ignored) {
                    // The stale-reservation reconciler will recover this row.
                }
            }
            if (failure instanceof BizException business) throw business;
            log.error("upload storage failed errorType={}", failure.getClass().getName());
            throw new BizException(503, "上传存储暂时不可用，请稍后重试");
        } finally {
            localWriteSemaphore.release();
        }
    }

    private long reserve(long tenantId, Long userId, String storageKey, String publicUrl,
                         String mediaType, String sourceType, String visibility, String purpose,
                         String ownerType, Long ownerId, long sizeBytes, String sha256) {
        Long result = transactionTemplate.execute(status -> {
            Integer lock = jdbcTemplate.queryForObject(
                    "SELECT GET_LOCK(?, 2)", Integer.class, GLOBAL_UPLOAD_LOCK);
            if (lock == null || lock != 1) throw new BizException(429, "当前上传请求过多，请稍后重试");
            registerNamedLockRelease();
            jdbcTemplate.update(
                    "UPDATE tenant_storage_asset SET status='failed', deletion_reason='reservation timeout', " +
                            "updated_time=NOW() WHERE status='reserved' AND created_time < " +
                            "TIMESTAMPADD(SECOND, ?, NOW())",
                    -STALE_RESERVATION_SECONDS);
            jdbcTemplate.update(
                    "DELETE FROM tenant_upload_rate_event WHERE created_time < " +
                            "TIMESTAMPADD(SECOND, ?, NOW())",
                    -Math.max(rateWindowSeconds * 2, 3600));
            long recent = scalar("SELECT COUNT(*) FROM tenant_upload_rate_event WHERE tenant_id=? " +
                    "AND created_time >= TIMESTAMPADD(SECOND, ?, NOW())", tenantId, -rateWindowSeconds);
            long tenantConcurrent = scalar("SELECT COUNT(*) FROM tenant_storage_asset " +
                    "WHERE tenant_id=? AND status='reserved'", tenantId);
            long globalConcurrent = scalar("SELECT COUNT(*) FROM tenant_storage_asset WHERE status='reserved'");
            long tenantUsed = scalar("SELECT COALESCE(SUM(size_bytes),0) FROM tenant_storage_asset " +
                    "WHERE tenant_id=? AND status IN ('reserved','active','deleting')", tenantId);
            long globalUsed = scalar("SELECT COALESCE(SUM(size_bytes),0) FROM tenant_storage_asset " +
                    "WHERE status IN ('reserved','active','deleting')");
            if (recent >= rateRequests) throw new BizException(429, "上传请求过于频繁，请稍后重试");
            if (tenantConcurrent >= maxConcurrentPerTenant)
                throw new BizException(429, "当前租户并发上传已达上限");
            if (globalConcurrent >= maxConcurrentGlobal)
                throw new BizException(429, "平台并发上传已达上限");
            if (tenantUsed + sizeBytes > tenantQuotaBytes)
                throw new BizException(413, "租户图片存储配额已满");
            if (globalUsed + sizeBytes > globalQuotaBytes)
                throw new BizException(503, "平台图片存储容量已满");

            jdbcTemplate.update(
                    "INSERT INTO tenant_upload_rate_event(tenant_id,user_id,created_time) VALUES(?,?,NOW())",
                    tenantId, userId);
            jdbcTemplate.update(
                    "INSERT INTO tenant_storage_asset(tenant_id,user_id,storage_key,public_url,media_type," +
                            "source_type,visibility,purpose,owner_type,owner_id,size_bytes,sha256,status," +
                            "created_time,updated_time) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'reserved',NOW(),NOW())",
                    tenantId, userId, storageKey, publicUrl, mediaType, sourceType,
                    visibility, purpose, ownerType, ownerId, sizeBytes, sha256);
            Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (id == null || id <= 0) throw new BizException(503, "上传资产预留失败");
            return id;
        });
        if (result == null) throw new BizException(503, "上传资产预留失败");
        return result;
    }

    private void registerNamedLockRelease() {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            releaseNamedLock();
            throw new BizException(503, "上传事务同步不可用");
        }
        try {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCompletion(int status) {
                    releaseNamedLock();
                }
            });
        } catch (RuntimeException registrationFailure) {
            releaseNamedLock();
            throw new BizException(503, "上传事务同步不可用");
        }
    }

    private void releaseNamedLock() {
        try {
            Integer released = jdbcTemplate.queryForObject(
                    "SELECT RELEASE_LOCK(?)", Integer.class, GLOBAL_UPLOAD_LOCK);
            if (released == null || released != 1) {
                log.error("global upload database lock was not released by its owner");
            }
        } catch (RuntimeException failure) {
            log.error("global upload database lock release failed errorType={}",
                    failure.getClass().getSimpleName());
        }
    }

    public void deleteStoredAsset(long assetId, long tenantId, Path target, String reason) {
        String safeReason = reason == null ? "cache expired"
                : reason.substring(0, Math.min(reason.length(), 255));
        Path normalized = target.toAbsolutePath().normalize();
        if (!normalized.startsWith(uploadPaths.root())) {
            throw new BizException(400, "上传资产清理路径无效");
        }
        int claimed = jdbcTemplate.update(
                "UPDATE tenant_storage_asset SET status='deleting', deletion_reason=?, " +
                        "cleaned_by='java-cache-cleaner', updated_time=NOW() " +
                        "WHERE id=? AND tenant_id=? AND status='active'",
                safeReason, assetId, tenantId);
        if (claimed != 1) throw new BizException(503, "上传资产清理认领失败");

        Path trash = normalized.resolveSibling(
                "." + normalized.getFileName() + ".trash-" + assetId + "-" + System.nanoTime());
        boolean quarantined = false;
        boolean deletionRecorded = false;
        try {
            if (Files.exists(normalized)) {
                Files.move(normalized, trash, StandardCopyOption.ATOMIC_MOVE);
                quarantined = true;
            }
            int deleted = jdbcTemplate.update(
                    "UPDATE tenant_storage_asset SET status='deleted', deleted_time=NOW(), updated_time=NOW() " +
                            "WHERE id=? AND tenant_id=? AND status='deleting'",
                    assetId, tenantId);
            if (deleted != 1) throw new BizException(503, "上传资产清理审计失败");
            deletionRecorded = true;
            if (quarantined) Files.deleteIfExists(trash);
        } catch (Exception failure) {
            if (deletionRecorded) {
                throw new BizException(503, "上传资产隔离文件待后台清理");
            }
            boolean restored = !quarantined;
            if (quarantined) {
                try {
                    if (!Files.exists(normalized) && Files.exists(trash)) {
                        Files.move(trash, normalized, StandardCopyOption.ATOMIC_MOVE);
                    }
                    restored = Files.exists(normalized);
                } catch (IOException ignored) {
                    restored = false;
                }
            }
            try {
                jdbcTemplate.update(
                        "UPDATE tenant_storage_asset SET status=?, deletion_reason=?, updated_time=NOW() " +
                                "WHERE id=? AND tenant_id=? AND status='deleting'",
                        restored ? "active" : "failed",
                        restored ? "cache cleanup rolled back" : "cache cleanup restore failed",
                        assetId, tenantId);
            } catch (RuntimeException ignored) {}
            if (failure instanceof BizException business) throw business;
            throw new BizException(503, "上传资产清理失败");
        }
    }

    public void deleteStoredAssetByKey(String storageKey, Path target, String reason) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id FROM tenant_storage_asset " +
                        "WHERE storage_key=? AND status='active' LIMIT 2",
                storageKey);
        if (rows.size() == 1) {
            Map<String, Object> row = rows.get(0);
            deleteStoredAsset(
                    ((Number) row.get("id")).longValue(),
                    ((Number) row.get("tenant_id")).longValue(),
                    target,
                    reason);
            return;
        }
        if (rows.isEmpty()) {
            try {
                Files.deleteIfExists(target);
                return;
            } catch (IOException failure) {
                throw new BizException(503, "遗留缓存文件清理失败");
            }
        }
        throw new BizException(503, "上传资产记录不唯一，拒绝清理");
    }

    private long scalar(String sql, Object... args) {
        Long value = jdbcTemplate.queryForObject(sql, Long.class, args);
        return value == null ? 0L : value;
    }

    private static long positiveLong(String value, long fallback, String name) {
        try {
            long parsed = value == null || value.isBlank() ? fallback : Long.parseLong(value);
            if (parsed <= 0) throw new NumberFormatException();
            return parsed;
        } catch (NumberFormatException invalid) {
            throw new IllegalStateException("invalid " + name);
        }
    }

    private static int positiveInt(String value, int fallback, String name) {
        long parsed = positiveLong(value, fallback, name);
        if (parsed > Integer.MAX_VALUE) throw new IllegalStateException("invalid " + name);
        return (int) parsed;
    }

    private static String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    public record StoredAsset(long assetId, String storageKey, String publicUrl, long sizeBytes) {}
}
