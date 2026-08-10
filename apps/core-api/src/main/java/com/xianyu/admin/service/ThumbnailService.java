package com.xianyu.admin.service;

import com.xianyu.admin.config.UploadPathConfig;
import net.coobird.thumbnailator.Thumbnails;
import net.coobird.thumbnailator.geometry.Positions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Optional;
import java.util.UUID;

/**
 * 缩略图生成服务。
 *
 * <p>用于「图片生成记录」页面卡片列表快速加载：原图通常为 1024×1024（200KB-1MB），
 * 缩略图统一为 480px 宽 jpg（约 20-50KB），首屏下载量降低 10-20 倍。</p>
 *
 * <p>命名规则：原图 {@code {uuid}.{ext}} → 缩略图 {@code {uuid}_thumb.jpg}，
 * 与原图同目录存储。用户点击放大查看时仍加载原图 URL，画质无损。</p>
 *
 * <p>历史图片 lazy migrate：访问缩略图时若文件不存在，由 MediaAssetController
 * 调用本服务同步生成并返回，后续命中磁盘缓存。</p>
 */
@Service
public class ThumbnailService {
    private static final Logger log = LoggerFactory.getLogger(ThumbnailService.class);

    /** 缩略图宽度（高度按比例缩放，COVER 居中裁剪为正方形适配卡片） */
    public static final int THUMB_WIDTH = 480;
    public static final int THUMB_HEIGHT = 480;
    public static final String THUMB_SUFFIX = "_thumb.jpg";

    private final UploadPathConfig uploadPaths;

    public ThumbnailService(UploadPathConfig uploadPaths) {
        this.uploadPaths = uploadPaths;
    }

    /**
     * 为指定原图生成缩略图。若已存在则直接返回路径。
     *
     * @param namespace     存储命名空间，如 "cache"、"images"
     * @param relativePath  原图相对路径，如 "tenant-1/abc123.jpg"
     * @return 缩略图绝对路径；生成失败返回 empty
     */
    public Optional<Path> ensureThumbnail(String namespace, String relativePath) {
        try {
            Path original = uploadPaths.resolve(namespace, relativePath);
            if (!Files.isRegularFile(original)) {
                return Optional.empty();
            }
            String thumbRelative = thumbRelativePath(relativePath);
            Path thumb = uploadPaths.resolve(namespace, thumbRelative);
            if (Files.isRegularFile(thumb) && Files.size(thumb) > 0) {
                return Optional.of(thumb);
            }
            // 生成缩略图：480×480 居中裁剪，jpg 格式，质量 0.85（视觉无损）
            Thumbnails.of(original.toFile())
                    .size(THUMB_WIDTH, THUMB_HEIGHT)
                    .crop(Positions.CENTER)
                    .outputFormat("jpg")
                    .outputQuality(0.85)
                    .toFile(thumb.toFile());
            log.debug("缩略图已生成: {}", thumb);
            return Optional.of(thumb);
        } catch (IOException e) {
            log.warn("缩略图生成失败, relativePath={}, errorType={}", relativePath, e.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    /**
     * 为指定原图生成等比缩放缩略图（最长边 480，保持宽高比，不裁剪）。
     *
     * <p>用于商品图/消息图等列表预览：原图可能为 3MB webp，缩略图约 20-60KB，
     * 首屏加载量可降低数十倍。缩略图经临时文件原子落盘，避免并发请求写冲突。</p>
     *
     * @param namespace            存储命名空间，如 "images"
     * @param originalRelativePath 原图相对路径，如 "tenant-1/img_abc.webp"
     * @return 缩略图绝对路径；生成失败返回 empty
     */
    public Optional<Path> ensureThumbnailContain(String namespace, String originalRelativePath) {
        try {
            Path original = uploadPaths.resolve(namespace, originalRelativePath);
            if (!Files.isRegularFile(original) || !Files.isReadable(original)) {
                return Optional.empty();
            }
            String thumbRelative = thumbRelativePath(originalRelativePath);
            Path thumb = uploadPaths.resolve(namespace, thumbRelative);
            if (Files.isRegularFile(thumb) && Files.size(thumb) > 0) {
                return Optional.of(thumb);
            }
            Path parent = thumb.toAbsolutePath().normalize().getParent();
            if (parent == null || !Files.isDirectory(parent) || !Files.isWritable(parent)) {
                log.warn("缩略图目录不可写, namespace={}, relativePath={}", namespace, originalRelativePath);
                return Optional.empty();
            }
            Path tmp = parent.resolve(UUID.randomUUID().toString().substring(0, 8) + ".jpg");
            try {
                Thumbnails.of(original.toFile())
                        .size(THUMB_WIDTH, THUMB_HEIGHT)
                        .keepAspectRatio(true)
                        .outputFormat("jpg")
                        .outputQuality(0.85)
                        .toFile(tmp.toFile());
                if (!Files.isRegularFile(tmp) || Files.size(tmp) <= 0) {
                    return Optional.empty();
                }
                Files.move(tmp, thumb, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                log.debug("等比缩略图已生成: {}", thumb);
                return Optional.of(thumb);
            } finally {
                Files.deleteIfExists(tmp);
            }
        } catch (IOException e) {
            log.warn("等比缩略图生成失败, relativePath={}, errorType={}", originalRelativePath, e.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    /**
     * 根据原图相对路径推导缩略图相对路径。
     * 例如 "tenant-1/abc123.png" → "tenant-1/abc123_thumb.jpg"
     */
    public static String thumbRelativePath(String originalRelativePath) {
        if (originalRelativePath == null || originalRelativePath.isBlank()) {
            return originalRelativePath;
        }
        int dotIdx = originalRelativePath.lastIndexOf('.');
        if (dotIdx <= 0 || dotIdx == originalRelativePath.length() - 1) {
            return originalRelativePath + THUMB_SUFFIX;
        }
        String base = originalRelativePath.substring(0, dotIdx);
        return base + THUMB_SUFFIX;
    }

    /**
     * 根据原图 public URL 推导缩略图 public URL。
     * 例如 "/uploads/cache/tenant-1/abc.png" → "/uploads/cache/tenant-1/abc_thumb.jpg"
     */
    public static String thumbPublicUrl(String originalPublicUrl) {
        if (originalPublicUrl == null || originalPublicUrl.isBlank()) {
            return originalPublicUrl;
        }
        int dotIdx = originalPublicUrl.lastIndexOf('.');
        if (dotIdx <= 0 || dotIdx == originalPublicUrl.length() - 1) {
            return originalPublicUrl + THUMB_SUFFIX;
        }
        return originalPublicUrl.substring(0, dotIdx) + THUMB_SUFFIX;
    }
}
