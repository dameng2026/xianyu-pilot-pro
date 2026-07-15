package com.xianyu.admin.service;

import com.xianyu.admin.config.UploadPathConfig;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Autowired;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * 文件级图片缓存服务。
 * 将AI生成的图片下载到本地 uploads/cache/ 目录，
 * 提供10分钟TTL、完整性校验、定时清理、缓存失败降级功能。
 */
@Service
public class ImageCacheService {
    private static final Logger log = LoggerFactory.getLogger(ImageCacheService.class);

    /** 缓存生命周期：10分钟 */
    private static final long CACHE_TTL_MS = 10 * 60 * 1000L;

    /** 清理间隔：2分钟 */
    private static final long CLEAN_INTERVAL_MS = 2 * 60 * 1000L;

    /** 最大缓存文件数（防止存储空间溢出） */
    private static final long MAX_CACHE_FILES = 500;

    /** 最大缓存总大小：500MB */
    private static final long MAX_CACHE_BYTES = 500L * 1024 * 1024;

    private final ConcurrentHashMap<String, CacheFileInfo> cacheIndex = new ConcurrentHashMap<>();
    private final SafeRemoteImageFetcher imageFetcher;
    private final UploadPathConfig uploadPaths;
    private final UploadStorageGovernanceService storageGovernance;
    private final Path cacheDir;
    private final ScheduledExecutorService cleaner = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "img-cache-cleaner");
        t.setDaemon(true);
        return t;
    });

    @Autowired
    public ImageCacheService(SafeRemoteImageFetcher imageFetcher, UploadPathConfig uploadPaths,
                             UploadStorageGovernanceService storageGovernance) {
        this.imageFetcher = imageFetcher;
        this.uploadPaths = uploadPaths;
        this.storageGovernance = storageGovernance;
        this.cacheDir = uploadPaths.resolve("cache");
    }

    ImageCacheService(SafeRemoteImageFetcher imageFetcher, UploadPathConfig uploadPaths) {
        this(imageFetcher, uploadPaths, null);
    }

    @PostConstruct
    void init() {
        try {
            if (!Files.exists(cacheDir)) {
                Files.createDirectories(cacheDir);
                log.info("图片缓存目录已创建: {}", cacheDir.toAbsolutePath());
            }
            // 启动时清理已存在的过期文件
            cleanExpired();
        } catch (IOException e) {
            throw new IllegalStateException("图片缓存目录不可用", e);
        }
        // 定时清理
        cleaner.scheduleAtFixedRate(this::cleanExpired,
                CLEAN_INTERVAL_MS, CLEAN_INTERVAL_MS, TimeUnit.MILLISECONDS);
    }

    @PreDestroy
    void shutdown() {
        cleaner.shutdownNow();
    }

    /**
     * 缓存一张图片。
     *
     * @param imageUrl 原始图片URL
     * @return 缓存结果，包含本地可访问URL；如果缓存失败则返回null（调用方应降级）
     */
    public CacheResult cache(String imageUrl) {
        if (imageUrl == null || imageUrl.isBlank()) {
            return null;
        }
        try {
            Long tenantId = TenantContext.getCurrentTenantId();
            if (tenantId == null) tenantId = UserContext.getTenantId();
            Long userId = UserContext.userId();
            if (tenantId == null || tenantId <= 0 || userId == null || userId <= 0
                    || storageGovernance == null) {
                log.warn("图片缓存缺少租户治理上下文，拒绝落盘");
                return null;
            }
            // 1. 检查是否已缓存
            String cacheKey = computeCacheKey(tenantId + "\n" + imageUrl);
            CacheFileInfo existing = cacheIndex.get(cacheKey);
            if (existing != null && !isExpired(existing)) {
                Path file = Path.of(existing.filePath);
                if (Files.exists(file) && Files.size(file) > 0) {
                    return new CacheResult(true, existing.localUrl, existing.filePath, existing.md5);
                }
                // 文件不存在或已损坏，重新下载
                cacheIndex.remove(cacheKey);
            }

            // 2. 检查缓存空间
            ensureCacheSpace();

            // 3. 通过统一的安全出口下载，限制 SSRF、跳转、媒体类型与大小。
            SafeRemoteImageFetcher.FetchedImage fetched = imageFetcher.fetch(imageUrl);
            byte[] imageBytes = fetched.bytes();

            // 4. 计算MD5摘要（完整性校验）
            String md5 = computeMd5(imageBytes);

            // 5. 生成唯一文件名并保存到磁盘
            String contentType = fetched.contentType();
            String ext = extensionFromContentType(contentType);
            String fileName = UUID.randomUUID().toString().replace("-", "") + ext;
            String relativePath = "tenant-" + tenantId + "/" + fileName;
            Path targetPath = cacheDir.resolve(relativePath).normalize();
            String localUrl = "/uploads/cache/" + relativePath;
            UploadStorageGovernanceService.StoredAsset stored = storageGovernance.store(
                    tenantId, userId, "cache/" + relativePath, localUrl,
                    fetched.contentType(), "ai-cache", imageBytes);

            // 6. 验证写入完整性
            byte[] readBack = Files.readAllBytes(targetPath);
            String readBackMd5 = computeMd5(readBack);
            if (!md5.equals(readBackMd5)) {
                log.warn("缓存文件完整性校验失败，删除: {}", targetPath);
                storageGovernance.deleteStoredAsset(
                        stored.assetId(), tenantId, targetPath, "cache integrity failure");
                return null;
            }

            // 7. 记录缓存信息
            CacheFileInfo info = new CacheFileInfo(
                    imageUrl, localUrl, targetPath.toString(), md5, imageBytes.length,
                    System.currentTimeMillis(), stored.assetId(), tenantId);
            cacheIndex.put(cacheKey, info);

            log.debug("图片缓存成功: cacheKey={} -> {} ({} bytes, md5={})", cacheKey, localUrl, imageBytes.length, md5);
            return new CacheResult(true, localUrl, targetPath.toString(), md5);

        } catch (Exception e) {
            // Remote URLs frequently contain signed query credentials; never
            // write the source URL to logs.
            log.warn("图片缓存失败, errorType={}", e.getClass().getSimpleName());
            return null;
        }
    }

    /**
     * 计算缓存的cache key（基于原始URL的MD5）。
     */
    private String computeCacheKey(String url) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(url.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            return url.hashCode() + "";
        }
    }

    private String computeMd5(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(data);
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            return "";
        }
    }

    private boolean isExpired(CacheFileInfo info) {
        return (System.currentTimeMillis() - info.cachedAt) > CACHE_TTL_MS;
    }

    /**
     * 清理过期缓存文件。
     */
    private void cleanExpired() {
        try {
            long now = System.currentTimeMillis();
            int removed = 0;

            // 清理过期索引项和对应文件
            var it = cacheIndex.entrySet().iterator();
            while (it.hasNext()) {
                var entry = it.next();
                CacheFileInfo info = entry.getValue();
                if ((now - info.cachedAt) > CACHE_TTL_MS) {
                    it.remove();
                    try {
                        storageGovernance.deleteStoredAsset(
                                info.assetId, info.tenantId, Path.of(info.filePath), "cache expired");
                    } catch (RuntimeException e) {
                        log.warn("图片缓存清理审计失败, errorType={}", e.getClass().getSimpleName());
                    }
                    removed++;
                }
            }

            // 也清理磁盘上不属于索引的孤立文件（应用重启后残留文件）
            if (Files.exists(cacheDir)) {
                try (var files = Files.walk(cacheDir)) {
                    files.filter(Files::isRegularFile).forEach(file -> {
                        Path normalizedFile = file.toAbsolutePath().normalize();
                        boolean indexed = cacheIndex.values().stream()
                                .anyMatch(v -> Path.of(v.filePath).toAbsolutePath().normalize()
                                        .equals(normalizedFile));
                        if (!indexed) {
                            try {
                                long lastMod = Files.getLastModifiedTime(file).toMillis();
                                if ((now - lastMod) > CACHE_TTL_MS) {
                                    if (storageGovernance != null) {
                                        String relativePath = cacheDir.relativize(file)
                                                .toString().replace('\\', '/');
                                        storageGovernance.deleteStoredAssetByKey(
                                                "cache/" + relativePath, file, "orphan cache cleanup");
                                    } else {
                                        Files.deleteIfExists(file);
                                    }
                                }
                            } catch (IOException | RuntimeException e) {
                                // 忽略
                            }
                        }
                    });
                }
            }

            if (removed > 0) {
                log.info("图片缓存清理: 移除 {} 个过期文件", removed);
            }
        } catch (Exception e) {
            log.warn("清理图片缓存异常, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 确保缓存空间不超过限制，如果超过则删除最旧的文件。
     */
    private void ensureCacheSpace() throws IOException {
        if (!Files.exists(cacheDir)) return;

        // 按文件数量和总大小两个维度检查
        long fileCount = 0;
        long totalBytes = 0;

        try (var files = Files.walk(cacheDir)) {
            var fileList = files.filter(Files::isRegularFile).toList();
            for (Path f : fileList) {
                fileCount++;
                totalBytes += Files.size(f);
            }
        }

        if (fileCount < MAX_CACHE_FILES && totalBytes < MAX_CACHE_BYTES) {
            return;
        }

        log.info("缓存空间接近上限 (文件数={}, 大小={}MB)，开始清理最旧文件",
                fileCount, totalBytes / (1024 * 1024));

        // 删除索引中最旧的条目，直到空间充足
        var sortedEntries = cacheIndex.entrySet().stream()
                .sorted(java.util.Comparator.comparingLong(e -> e.getValue().cachedAt))
                .toList();

        for (var entry : sortedEntries) {
            if (cacheIndex.size() <= MAX_CACHE_FILES / 2
                    && totalBytes <= MAX_CACHE_BYTES / 2) break;
            CacheFileInfo info = entry.getValue();
            cacheIndex.remove(entry.getKey());
            try {
                storageGovernance.deleteStoredAsset(
                        info.assetId, info.tenantId, Path.of(info.filePath), "cache capacity cleanup");
                totalBytes -= info.fileSize;
            } catch (RuntimeException e) {
                // 忽略
            }
        }
    }

    private String extensionFromContentType(String contentType) {
        if (contentType == null) return ".png";
        return switch (contentType.toLowerCase()) {
            case "image/jpeg", "image/jpg" -> ".jpg";
            case "image/webp" -> ".webp";
            case "image/gif" -> ".gif";
            case "image/avif" -> ".avif";
            default -> ".png";
        };
    }

    /**
     * 缓存文件信息。
     */
    private record CacheFileInfo(
            String originalUrl,
            String localUrl,
            String filePath,
            String md5,
            long fileSize,
            long cachedAt,
            long assetId,
            long tenantId
    ) {}

    /**
     * 缓存结果。
     */
    public record CacheResult(
            boolean success,
            String localUrl,
            String filePath,
            String md5
    ) {}
}
