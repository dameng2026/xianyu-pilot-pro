package com.xianyu.admin.controller;

import com.xianyu.admin.config.UploadPathConfig;
import com.xianyu.admin.security.MediaSessionCookieService;
import com.xianyu.admin.service.PublicMediaPolicy;
import com.xianyu.admin.service.ThumbnailService;
import com.xianyu.admin.service.UploadedImageValidator;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Authorization and integrity boundary for private uploaded media.
 *
 * <p>Request paths are treated only as locators. An active database record,
 * exact tenant binding, canonical non-symlink file, size and SHA-256 match are
 * required before bytes are returned.</p>
 */
@RestController
public class MediaAssetController {
    private static final Pattern IMAGE_PATH = Pattern.compile(
            "^/uploads/images/(tenant-([1-9][0-9]*)/[A-Za-z0-9_-]{1,180}\\.(?:jpg|jpeg|png|gif|webp))$");
    private static final Pattern CACHE_PATH = Pattern.compile(
            "^/uploads/cache/(tenant-([1-9][0-9]*)/[A-Za-z0-9_-]{1,180}\\.(?:jpg|jpeg|png|gif|webp))$");
    private static final Pattern AVATAR_PATH = Pattern.compile(
            "^/uploads/avatars/([0-9]{8}/admin_([1-9][0-9]*)_[A-Za-z0-9_-]{1,80}\\.(?:jpg|jpeg|png|webp))$");
    private static final long MAX_MANAGED_MEDIA_BYTES = 20L * 1024 * 1024;
    private static final long MAX_AVATAR_BYTES = 2L * 1024 * 1024;

    private final JdbcTemplate jdbcTemplate;
    private final MediaSessionCookieService mediaSessions;
    private final UploadPathConfig uploadPaths;
    private final UploadedImageValidator imageValidator;
    private final ThumbnailService thumbnailService;
    private final Map<String, String> validatedMediaDigests =
            java.util.Collections.synchronizedMap(new LinkedHashMap<>(256, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
                    return size() > 2_048;
                }
            });

    public MediaAssetController(
            JdbcTemplate jdbcTemplate,
            MediaSessionCookieService mediaSessions,
            UploadPathConfig uploadPaths,
            UploadedImageValidator imageValidator,
            ThumbnailService thumbnailService) {
        this.jdbcTemplate = jdbcTemplate;
        this.mediaSessions = mediaSessions;
        this.uploadPaths = uploadPaths;
        this.imageValidator = imageValidator;
        this.thumbnailService = thumbnailService;
    }

    @RequestMapping(
            value = {"/uploads/images/**", "/uploads/cache/**", "/uploads/avatars/**", "/uploads/public/**"},
            method = {RequestMethod.GET, RequestMethod.HEAD})
    public void serve(HttpServletRequest request, HttpServletResponse response) throws IOException {
        applyBaselineHeaders(response);
        String publicPath = applicationPath(request);
        try {
            Matcher avatarMatcher = AVATAR_PATH.matcher(publicPath);
            if (avatarMatcher.matches()) {
                serveAvatar(request, response, publicPath, avatarMatcher.group(1));
                return;
            }

            Optional<PublicMediaPolicy.SystemLogoLocation> publicLogo =
                    PublicMediaPolicy.systemLogoLocation(publicPath);
            if (publicLogo.isPresent()) {
                servePublicLogo(
                        request, response, publicPath,
                        publicLogo.get().relativePath(), publicLogo.get().storageKey());
                return;
            }

            Matcher imageMatcher = IMAGE_PATH.matcher(publicPath);
            if (imageMatcher.matches()) {
                serveManagedAsset(
                        request, response, publicPath, "images", imageMatcher.group(1),
                        imageMatcher.group(1), Long.parseLong(imageMatcher.group(2)));
                return;
            }

            Matcher cacheMatcher = CACHE_PATH.matcher(publicPath);
            if (cacheMatcher.matches()) {
                serveManagedAsset(
                        request, response, publicPath, "cache", cacheMatcher.group(1),
                        "cache/" + cacheMatcher.group(1), Long.parseLong(cacheMatcher.group(2)));
                return;
            }
            notFound(response);
        } catch (MediaSessionCookieService.MediaSessionUnavailableException | DataAccessException exception) {
            unavailable(response);
        } catch (IOException exception) {
            unavailable(response);
        } catch (RuntimeException exception) {
            notFound(response);
        }
    }

    private void serveManagedAsset(
            HttpServletRequest request,
            HttpServletResponse response,
            String publicPath,
            String namespace,
            String relativePath,
            String expectedStorageKey,
            Long pathTenantId) throws IOException {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM tenant_storage_asset WHERE public_url=? AND storage_key=? LIMIT 2",
                publicPath, expectedStorageKey);
        if (rows.size() != 1) {
            // 缩略图请求（{原图}_thumb.jpg）在 DB 中无独立记录，基于原图记录派生校验并懒生成
            if (serveDerivedThumbnail(request, response, publicPath, namespace, relativePath, pathTenantId)) {
                return;
            }
            notFound(response);
            return;
        }
        Map<String, Object> row = rows.get(0);
        if (!"active".equalsIgnoreCase(text(row.get("status")))) {
            notFound(response);
            return;
        }

        long tenantId = positiveLong(row.get("tenant_id"));
        if (pathTenantId != null && tenantId != pathTenantId) {
            notFound(response);
            return;
        }
        boolean isPublic = "public".equalsIgnoreCase(text(row.get("visibility")));
        if (isPublic && !isApprovedPublicContent(row)) {
            notFound(response);
            return;
        }
        if (!isPublic) {
            Optional<MediaSessionCookieService.UserMediaPrincipal> principal =
                    mediaSessions.authenticateUser(request);
            if (principal.isEmpty() || principal.get().tenantId() != tenantId) {
                notFound(response);
                return;
            }
        }

        long expectedSize = positiveLong(row.get("size_bytes"));
        if (expectedSize > MAX_MANAGED_MEDIA_BYTES) {
            notFound(response);
            return;
        }
        String expectedSha256 = text(row.get("sha256")).toLowerCase(Locale.ROOT);
        if (!expectedSha256.matches("[0-9a-f]{64}")) {
            notFound(response);
            return;
        }
        String contentType = safeContentType(row.get("media_type"), relativePath);
        if (contentType == null) {
            notFound(response);
            return;
        }

        byte[] content = readCanonicalFile(namespace, relativePath, expectedSize);
        if (!sha256(content).equals(expectedSha256)) {
            notFound(response);
            return;
        }
        if (!isDecodableImage(content, contentType, expectedSha256)) {
            notFound(response);
            return;
        }
        writeMedia(
                request, response, content, contentType, fileName(relativePath),
                isPublic, expectedSha256);
    }

    /**
     * 服务缩略图请求：{原图}_thumb.jpg 在 DB 中无独立记录，安全模型基于原图记录。
     *
     * <p>校验链路与原图一致（status/tenant/visibility/会话/size/sha256/可解码），
     * 通过后由 {@link ThumbnailService} 懒生成等比缩略图并落盘（共享卷），
     * 下一分钟 rsync 同步至香港节点，后续命中本地 alias 缓存。</p>
     */
    private boolean serveDerivedThumbnail(
            HttpServletRequest request,
            HttpServletResponse response,
            String publicPath,
            String namespace,
            String thumbRelative,
            Long pathTenantId) throws IOException {
        if (!"images".equals(namespace)
                || !thumbRelative.endsWith(ThumbnailService.THUMB_SUFFIX)
                || pathTenantId == null) {
            return false;
        }
        String originalBase = thumbRelative.substring(
                0, thumbRelative.length() - ThumbnailService.THUMB_SUFFIX.length());
        int slash = originalBase.lastIndexOf('/');
        if (slash <= 0 || !originalBase.substring(0, slash).matches("tenant-[1-9][0-9]*")) {
            return false;
        }

        List<Map<String, Object>> originals = jdbcTemplate.queryForList(
                "SELECT * FROM tenant_storage_asset WHERE storage_key LIKE ? AND status='active' LIMIT 2",
                originalBase + ".%");
        if (originals.size() != 1) {
            return false;
        }
        Map<String, Object> original = originals.get(0);
        long tenantId = positiveLong(original.get("tenant_id"));
        if (tenantId != pathTenantId) {
            return false;
        }
        String originalKey = text(original.get("storage_key"));
        if (!originalKey.startsWith(originalBase + ".")) {
            return false;
        }
        boolean isPublic = "public".equalsIgnoreCase(text(original.get("visibility")));
        if (isPublic && !isApprovedPublicContent(original)) {
            return false;
        }
        if (!isPublic) {
            Optional<MediaSessionCookieService.UserMediaPrincipal> principal =
                    mediaSessions.authenticateUser(request);
            if (principal.isEmpty() || principal.get().tenantId() != tenantId) {
                return false;
            }
        }

        long expectedSize = positiveLong(original.get("size_bytes"));
        if (expectedSize > MAX_MANAGED_MEDIA_BYTES) {
            return false;
        }
        String expectedSha256 = text(original.get("sha256")).toLowerCase(Locale.ROOT);
        if (!expectedSha256.matches("[0-9a-f]{64}")) {
            return false;
        }
        String originalType = safeContentType(original.get("media_type"), originalKey);
        if (originalType == null) {
            return false;
        }
        byte[] originalBytes = readCanonicalFile(namespace, originalKey, expectedSize);
        if (!sha256(originalBytes).equals(expectedSha256)) {
            return false;
        }
        if (!isDecodableImage(originalBytes, originalType, expectedSha256)) {
            return false;
        }

        Optional<Path> thumbOpt = thumbnailService.ensureThumbnailContain(namespace, originalKey);
        if (thumbOpt.isEmpty()) {
            return false;
        }
        Path thumbPath = thumbOpt.get();
        byte[] thumbBytes;
        try {
            if (Files.size(thumbPath) <= 0 || Files.size(thumbPath) > MAX_MANAGED_MEDIA_BYTES) {
                return false;
            }
            thumbBytes = Files.readAllBytes(thumbPath);
        } catch (IOException exception) {
            return false;
        }
        String thumbSha256 = sha256(thumbBytes);
        if (!isDecodableImage(thumbBytes, "image/jpeg", thumbSha256)) {
            return false;
        }
        writeMedia(
                request, response, thumbBytes, "image/jpeg", fileName(thumbRelative),
                isPublic, isPublic ? thumbSha256 : null);
        return true;
    }

    private boolean isApprovedPublicContent(Map<String, Object> row) {
        String purpose = text(row.get("purpose"));
        return ("carousel".equals(purpose) || "open-source-content".equals(purpose))
                && purpose.equals(text(row.get("source_type")))
                && "service".equals(text(row.get("owner_type")))
                && text(row.get("owner_id")).isBlank()
                && text(row.get("user_id")).isBlank()
                && !text(row.get("published_time")).isBlank()
                && text(row.get("deleted_time")).isBlank();
    }

    private boolean isDecodableImage(byte[] content, String expectedType, String sha256) {
        String cachedType = validatedMediaDigests.get(sha256);
        if (expectedType.equals(cachedType)) return true;
        try {
            UploadedImageValidator.ValidatedImage image =
                    imageValidator.validate(content, MAX_MANAGED_MEDIA_BYTES);
            if (!expectedType.equals(image.contentType())) return false;
            validatedMediaDigests.put(sha256, expectedType);
            return true;
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    private void serveAvatar(
            HttpServletRequest request,
            HttpServletResponse response,
            String publicPath,
            String relativePath) throws IOException {
        Optional<MediaSessionCookieService.AdminMediaPrincipal> principal =
                mediaSessions.authenticateAdmin(request);
        if (principal.isEmpty()) {
            notFound(response);
            return;
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id FROM sys_admin_user WHERE id=? AND avatar=? "
                        + "AND status=1 AND deleted=0 LIMIT 2",
                principal.get().userId(), publicPath);
        if (rows.size() != 1) {
            notFound(response);
            return;
        }

        String storageKey = "avatars/" + relativePath;
        List<Map<String, Object>> assetRows = jdbcTemplate.queryForList(
                "SELECT size_bytes, sha256, media_type FROM tenant_storage_asset "
                        + "WHERE tenant_id=0 AND user_id=? AND storage_key=? AND public_url=? "
                        + "AND source_type='admin-avatar' AND status='active' LIMIT 2",
                principal.get().userId(), storageKey, publicPath);
        if (assetRows.size() != 1) {
            notFound(response);
            return;
        }
        Map<String, Object> asset = assetRows.get(0);
        long expectedSize = positiveLong(asset.get("size_bytes"));
        if (expectedSize > MAX_AVATAR_BYTES) {
            notFound(response);
            return;
        }
        String expectedSha256 = text(asset.get("sha256")).toLowerCase(Locale.ROOT);
        String expectedType = safeContentType(asset.get("media_type"), relativePath);
        if (!expectedSha256.matches("[0-9a-f]{64}") || expectedType == null) {
            notFound(response);
            return;
        }

        byte[] content = readCanonicalFile("avatars", relativePath, expectedSize);
        if (!sha256(content).equals(expectedSha256)) {
            notFound(response);
            return;
        }
        final UploadedImageValidator.ValidatedImage image;
        try {
            image = imageValidator.validate(content, MAX_AVATAR_BYTES);
        } catch (IllegalArgumentException exception) {
            notFound(response);
            return;
        }
        if (!expectedType.equals(image.contentType())) {
            notFound(response);
            return;
        }
        writeMedia(
                request, response, image.bytes(), image.contentType(), fileName(relativePath),
                false, null);
    }

    private void servePublicLogo(
            HttpServletRequest request,
            HttpServletResponse response,
            String publicPath,
            String relativePath,
            String storageKey) throws IOException {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT size_bytes, sha256, media_type FROM tenant_storage_asset "
                        + "WHERE tenant_id=0 AND user_id IS NULL AND storage_key=? AND public_url=? "
                        + "AND source_type='system-logo' AND purpose='system-logo' "
                        + "AND owner_type='service' AND visibility='public' AND status='active' "
                        + "AND published_time IS NOT NULL LIMIT 2",
                storageKey, publicPath);
        if (rows.size() != 1) {
            notFound(response);
            return;
        }
        Map<String, Object> row = rows.get(0);
        long expectedSize = positiveLong(row.get("size_bytes"));
        if (expectedSize > MAX_MANAGED_MEDIA_BYTES) {
            notFound(response);
            return;
        }
        String expectedSha256 = text(row.get("sha256")).toLowerCase(Locale.ROOT);
        String expectedType = safeContentType(row.get("media_type"), relativePath);
        if (!expectedSha256.matches("[0-9a-f]{64}") || expectedType == null) {
            notFound(response);
            return;
        }
        byte[] content = readCanonicalFile("public", relativePath, expectedSize);
        if (!sha256(content).equals(expectedSha256)) {
            notFound(response);
            return;
        }
        final UploadedImageValidator.ValidatedImage image;
        try {
            image = imageValidator.validate(content, MAX_MANAGED_MEDIA_BYTES);
        } catch (IllegalArgumentException exception) {
            notFound(response);
            return;
        }
        if (!expectedType.equals(image.contentType())) {
            notFound(response);
            return;
        }
        writeMedia(
                request, response, image.bytes(), image.contentType(), fileName(relativePath),
                true, expectedSha256);
    }

    private byte[] readCanonicalFile(
            String namespace,
            String relativePath,
            Long expectedSize) throws IOException {
        Path root = uploadPaths.root().toAbsolutePath().normalize();
        Path base = root.resolve(namespace).normalize();
        Path candidate = base.resolve(relativePath).normalize();
        if (!base.startsWith(root) || !candidate.startsWith(base)
                || containsSymbolicLink(root, candidate)
                || !Files.isRegularFile(candidate, LinkOption.NOFOLLOW_LINKS)) {
            throw new MediaNotFoundException();
        }
        Path rootReal = root.toRealPath();
        Path baseReal = base.toRealPath();
        Path candidateReal = candidate.toRealPath();
        if (!baseReal.startsWith(rootReal) || !candidateReal.startsWith(baseReal)) {
            throw new MediaNotFoundException();
        }
        long actualSize = Files.size(candidateReal);
        if (actualSize <= 0 || actualSize > MAX_MANAGED_MEDIA_BYTES
                || (expectedSize != null && actualSize != expectedSize)) {
            throw new MediaNotFoundException();
        }
        byte[] content = Files.readAllBytes(candidateReal);
        if (content.length != actualSize) throw new MediaNotFoundException();
        return content;
    }

    private boolean containsSymbolicLink(Path root, Path candidate) {
        if (Files.isSymbolicLink(root)) return true;
        Path current = root;
        for (Path component : root.relativize(candidate)) {
            current = current.resolve(component);
            if (Files.isSymbolicLink(current)) return true;
        }
        return false;
    }

    private void writeMedia(
            HttpServletRequest request,
            HttpServletResponse response,
            byte[] content,
            String contentType,
            String fileName,
            boolean isPublic,
            String sha256) throws IOException {
        response.setStatus(HttpServletResponse.SC_OK);
        response.setContentType(contentType);
        response.setContentLengthLong(content.length);
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + fileName + "\"");
        if (isPublic) {
            response.setHeader(HttpHeaders.CACHE_CONTROL, "public, max-age=300");
            if (sha256 != null) response.setHeader(HttpHeaders.ETAG, "\"" + sha256 + "\"");
        } else {
            response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store, max-age=0");
            response.setHeader(HttpHeaders.PRAGMA, "no-cache");
            response.setHeader(HttpHeaders.VARY, HttpHeaders.COOKIE);
        }
        if (!HttpMethod.HEAD.matches(request.getMethod())) {
            response.getOutputStream().write(content);
        }
    }

    private String safeContentType(Object mediaTypeValue, String relativePath) {
        String mediaType = text(mediaTypeValue).toLowerCase(Locale.ROOT);
        String lowerPath = relativePath.toLowerCase(Locale.ROOT);
        String expected;
        if (lowerPath.endsWith(".jpg") || lowerPath.endsWith(".jpeg")) expected = "image/jpeg";
        else if (lowerPath.endsWith(".png")) expected = "image/png";
        else if (lowerPath.endsWith(".gif")) expected = "image/gif";
        else if (lowerPath.endsWith(".webp")) expected = "image/webp";
        else return null;
        return expected.equals(mediaType) ? expected : null;
    }

    private String applicationPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.isEmpty() && uri.startsWith(contextPath)) {
            return uri.substring(contextPath.length());
        }
        return uri;
    }

    private String fileName(String relativePath) {
        return relativePath.substring(relativePath.lastIndexOf('/') + 1);
    }

    private long positiveLong(Object value) {
        try {
            long parsed = Long.parseLong(String.valueOf(value));
            if (parsed <= 0) throw new NumberFormatException();
            return parsed;
        } catch (RuntimeException exception) {
            throw new MediaNotFoundException();
        }
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    private void applyBaselineHeaders(HttpServletResponse response) {
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-Frame-Options", "DENY");
        response.setHeader("Referrer-Policy", "no-referrer");
        response.setHeader("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; sandbox");
    }

    private void notFound(HttpServletResponse response) {
        response.resetBuffer();
        applyBaselineHeaders(response);
        response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store, max-age=0");
        response.setHeader(HttpHeaders.PRAGMA, "no-cache");
        response.setStatus(HttpServletResponse.SC_NOT_FOUND);
    }

    private void unavailable(HttpServletResponse response) {
        response.resetBuffer();
        applyBaselineHeaders(response);
        response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store, max-age=0");
        response.setHeader(HttpHeaders.PRAGMA, "no-cache");
        response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
    }

    private static final class MediaNotFoundException extends RuntimeException {}
}
