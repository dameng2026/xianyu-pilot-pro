package com.xianyu.admin.controller;

import com.xianyu.admin.config.UploadPathConfig;
import com.xianyu.admin.security.MediaSessionCookieService;
import com.xianyu.admin.service.UploadedImageValidator;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class MediaAssetControllerTest {
    @TempDir
    Path tempDir;

    private StubJdbc jdbc;
    private MediaSessionCookieService mediaSessions;
    private MediaAssetController controller;

    @BeforeEach
    void setUp() throws IOException {
        UploadPathConfig uploadPaths = new UploadPathConfig(tempDir.toString());
        uploadPaths.init();
        jdbc = new StubJdbc();
        mediaSessions = mock(MediaSessionCookieService.class);
        when(mediaSessions.authenticateUser(any())).thenReturn(Optional.empty());
        when(mediaSessions.authenticateAdmin(any())).thenReturn(Optional.empty());
        controller = new MediaAssetController(
                jdbc, mediaSessions, uploadPaths, new UploadedImageValidator());
    }

    @Test
    void publicActiveAssetIsAnonymousAndIntegrityChecked() throws Exception {
        String path = "/uploads/images/tenant-7/public_demo.png";
        byte[] content = pngBytes();
        write("images/tenant-7/public_demo.png", content);
        jdbc.assetRows = List.of(asset(path, "tenant-7/public_demo.png", 7, "public", content));

        MockHttpServletResponse response = serve("GET", path);

        assertEquals(200, response.getStatus());
        assertArrayEquals(content, response.getContentAsByteArray());
        assertEquals("public, max-age=300", response.getHeader("Cache-Control"));
        assertEquals("nosniff", response.getHeader("X-Content-Type-Options"));
        assertEquals("\"" + sha256(content) + "\"", response.getHeader("ETag"));
        verify(mediaSessions, never()).authenticateUser(any());
    }

    @Test
    void anonymousContentAssetRequiresApprovedPublicationMetadata() throws Exception {
        String path = "/uploads/images/tenant-7/public_policy.png";
        byte[] content = pngBytes();
        write("images/tenant-7/public_policy.png", content);
        Map<String, Object> row = asset(
                path, "tenant-7/public_policy.png", 7, "public", content);
        jdbc.assetRows = List.of(row);
        assertEquals(200, serve("GET", path).getStatus());

        for (String field : List.of(
                "purpose", "owner_type", "published_time", "source_type")) {
            Map<String, Object> invalid = new HashMap<>(row);
            invalid.remove(field);
            jdbc.assetRows = List.of(invalid);
            assertEquals(404, serve("GET", path).getStatus(), field);
        }

        Map<String, Object> userOwned = new HashMap<>(row);
        userOwned.put("user_id", 9L);
        jdbc.assetRows = List.of(userOwned);
        assertEquals(404, serve("GET", path).getStatus());

        Map<String, Object> ownerBound = new HashMap<>(row);
        ownerBound.put("owner_id", 9L);
        jdbc.assetRows = List.of(ownerBound);
        assertEquals(404, serve("GET", path).getStatus());

        Map<String, Object> deleted = new HashMap<>(row);
        deleted.put("deleted_time", "2026-07-11T00:01:00");
        jdbc.assetRows = List.of(deleted);
        assertEquals(404, serve("GET", path).getStatus());

        Map<String, Object> unapprovedPurpose = new HashMap<>(row);
        unapprovedPurpose.put("purpose", "user-media");
        unapprovedPurpose.put("source_type", "user-media");
        jdbc.assetRows = List.of(unapprovedPurpose);
        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void privateAssetRequiresMatchingUserTenantAndUsesNoStore() throws Exception {
        String path = "/uploads/images/tenant-7/private_demo.png";
        byte[] content = pngBytes();
        write("images/tenant-7/private_demo.png", content);
        jdbc.assetRows = List.of(asset(path, "tenant-7/private_demo.png", 7, "private", content));

        assertEquals(404, serve("GET", path).getStatus());

        when(mediaSessions.authenticateUser(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.UserMediaPrincipal(22, 8)));
        assertEquals(404, serve("GET", path).getStatus());

        when(mediaSessions.authenticateUser(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.UserMediaPrincipal(11, 7)));
        MockHttpServletResponse allowed = serve("GET", path);
        assertEquals(200, allowed.getStatus());
        assertArrayEquals(content, allowed.getContentAsByteArray());
        assertEquals("private, no-store, max-age=0", allowed.getHeader("Cache-Control"));
        assertEquals("Cookie", allowed.getHeader("Vary"));
    }

    @Test
    void missingVisibilityDefaultsToPrivate() throws Exception {
        String path = "/uploads/images/tenant-7/legacy.png";
        byte[] content = pngBytes();
        write("images/tenant-7/legacy.png", content);
        Map<String, Object> row = asset(path, "tenant-7/legacy.png", 7, "private", content);
        row.remove("visibility");
        jdbc.assetRows = List.of(row);

        assertEquals(404, serve("GET", path).getStatus());
        when(mediaSessions.authenticateUser(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.UserMediaPrincipal(11, 7)));
        assertEquals(200, serve("GET", path).getStatus());
    }

    @Test
    void deletedWrongSizeWrongDigestAndWrongMimeAllFailAs404() throws Exception {
        String path = "/uploads/images/tenant-7/check.png";
        byte[] content = "content".getBytes();
        write("images/tenant-7/check.png", content);
        Map<String, Object> row = asset(path, "tenant-7/check.png", 7, "public", content);

        row.put("status", "deleted");
        jdbc.assetRows = List.of(row);
        assertEquals(404, serve("GET", path).getStatus());

        row.put("status", "active");
        row.put("size_bytes", content.length + 1L);
        assertEquals(404, serve("GET", path).getStatus());

        row.put("size_bytes", (long) content.length);
        row.put("sha256", "0".repeat(64));
        assertEquals(404, serve("GET", path).getStatus());

        row.put("sha256", sha256(content));
        row.put("media_type", "text/html");
        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void matchingDigestAndMimeCannotMakeArbitraryBytesAnImage() throws Exception {
        String path = "/uploads/images/tenant-7/not_really_png.png";
        byte[] content = "not-an-image".getBytes();
        write("images/tenant-7/not_really_png.png", content);
        jdbc.assetRows = List.of(asset(
                path, "tenant-7/not_really_png.png", 7, "public", content));

        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void headPerformsAuthorizationAndIntegrityButReturnsNoBody() throws Exception {
        String path = "/uploads/images/tenant-7/head.png";
        byte[] content = pngBytes();
        write("images/tenant-7/head.png", content);
        jdbc.assetRows = List.of(asset(path, "tenant-7/head.png", 7, "public", content));

        MockHttpServletResponse response = serve("HEAD", path);

        assertEquals(200, response.getStatus());
        assertEquals(content.length, response.getContentLengthLong());
        assertEquals(0, response.getContentAsByteArray().length);
    }

    @Test
    void cacheAssetsUseSameVisibilityTenantAndIntegrityBoundary() throws Exception {
        String path = "/uploads/cache/tenant-12/cache_demo.jpg";
        byte[] content = jpegBytes();
        write("cache/tenant-12/cache_demo.jpg", content);
        jdbc.assetRows = List.of(asset(path, "cache/tenant-12/cache_demo.jpg", 12, "private", content));
        jdbc.assetRows.get(0).put("media_type", "image/jpeg");
        when(mediaSessions.authenticateUser(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.UserMediaPrincipal(44, 12)));

        MockHttpServletResponse response = serve("GET", path);

        assertEquals(200, response.getStatus());
        assertArrayEquals(content, response.getContentAsByteArray());
        assertArrayEquals(
                new Object[]{path, "cache/tenant-12/cache_demo.jpg"},
                jdbc.calls.get(0).args());
    }

    @Test
    void pathTenantMustMatchTheGovernedAssetTenant() throws Exception {
        String path = "/uploads/images/tenant-7/mismatch.png";
        byte[] content = "mismatch-content".getBytes();
        write("images/tenant-7/mismatch.png", content);
        jdbc.assetRows = List.of(asset(path, "tenant-7/mismatch.png", 8, "public", content));

        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void malformedAndEncodedTraversalPathsReturn404WithoutDatabaseLookup() throws Exception {
        assertEquals(404, serve("GET", "/uploads/images/tenant-7/../secret.png").getStatus());
        assertEquals(404, serve("GET", "/uploads/images/tenant-7/%2e%2e/secret.png").getStatus());
        assertEquals(404, serve("GET", "/uploads/cache/a%2fb.png").getStatus());
        assertEquals(404, serve("GET", "/uploads/cache/legacy-flat.png").getStatus());
        assertTrue(jdbc.calls.isEmpty());
    }

    @Test
    void symbolicLinkIsNeverServed() throws Exception {
        Path outside = tempDir.resolve("outside.png");
        Files.write(outside, "outside".getBytes());
        Path tenantDir = tempDir.resolve("images/tenant-7");
        Files.createDirectories(tenantDir);
        Path link = tenantDir.resolve("link.png");
        try {
            Files.createSymbolicLink(link, outside);
        } catch (IOException | UnsupportedOperationException | SecurityException exception) {
            Assumptions.abort("symbolic links are unavailable in this environment");
        }
        byte[] content = Files.readAllBytes(outside);
        String path = "/uploads/images/tenant-7/link.png";
        jdbc.assetRows = List.of(asset(path, "tenant-7/link.png", 7, "public", content));

        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void assetDatabaseOutageReturns503ButMissingAssetReturns404() throws Exception {
        String path = "/uploads/images/tenant-7/missing.png";
        jdbc.assetRows = List.of();
        assertEquals(404, serve("GET", path).getStatus());

        jdbc.fail = true;
        MockHttpServletResponse unavailable = serve("GET", path);
        assertEquals(503, unavailable.getStatus());
        assertEquals("private, no-store, max-age=0", unavailable.getHeader("Cache-Control"));
    }

    @Test
    void mediaAuthStateOutageReturns503InsteadOfLookingLikeMissingAsset() throws Exception {
        String path = "/uploads/images/tenant-7/private.png";
        byte[] content = "private".getBytes();
        write("images/tenant-7/private.png", content);
        jdbc.assetRows = List.of(asset(path, "tenant-7/private.png", 7, "private", content));
        when(mediaSessions.authenticateUser(any())).thenThrow(
                new MediaSessionCookieService.MediaSessionUnavailableException(
                        new IllegalStateException("db")));

        assertEquals(503, serve("GET", path).getStatus());
    }

    @Test
    void avatarRequiresMatchingAdminCookieAndAuthoritativeAvatarReference() throws Exception {
        String path = "/uploads/avatars/20260711/admin_99_profile.png";
        byte[] png = pngBytes();
        write("avatars/20260711/admin_99_profile.png", png);
        jdbc.avatarRows = List.of(Map.of("id", 99L));
        jdbc.assetRows = List.of(asset(
                path, "avatars/20260711/admin_99_profile.png", 0, "private", png));

        assertEquals(404, serve("GET", path).getStatus());

        when(mediaSessions.authenticateAdmin(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.AdminMediaPrincipal(99, "R_SUPER")));
        MockHttpServletResponse response = serve("GET", path);

        assertEquals(200, response.getStatus());
        assertArrayEquals(png, response.getContentAsByteArray());
        assertEquals("image/png", response.getContentType());
        assertEquals("private, no-store, max-age=0", response.getHeader("Cache-Control"));
        assertArrayEquals(
                new Object[]{99L, "avatars/20260711/admin_99_profile.png", path},
                jdbc.calls.get(jdbc.calls.size() - 1).args());
    }

    @Test
    void avatarMissingReferenceIs404AndDatabaseOutageIs503() throws Exception {
        String path = "/uploads/avatars/20260711/admin_99_profile.png";
        write("avatars/20260711/admin_99_profile.png", pngBytes());
        when(mediaSessions.authenticateAdmin(any())).thenReturn(Optional.of(
                new MediaSessionCookieService.AdminMediaPrincipal(99, "R_SUPER")));

        jdbc.avatarRows = List.of();
        assertEquals(404, serve("GET", path).getStatus());

        jdbc.avatarRows = List.of(Map.of("id", 99L));
        jdbc.assetRows = List.of();
        assertEquals(404, serve("GET", path).getStatus());

        jdbc.fail = true;
        assertEquals(503, serve("GET", path).getStatus());
    }

    @Test
    void publicSystemLogoRequiresOnePublishedGovernedRowAndFileIntegrity() throws Exception {
        String path = "/uploads/public/logos/20260711/0123456789abcdef0123456789abcdef.png";
        byte[] png = pngBytes();
        write("public/logos/20260711/0123456789abcdef0123456789abcdef.png", png);
        jdbc.assetRows = List.of(asset(
                path,
                "public/logos/20260711/0123456789abcdef0123456789abcdef.png",
                0,
                "public",
                png));

        MockHttpServletResponse response = serve("GET", path);

        assertEquals(200, response.getStatus());
        assertArrayEquals(png, response.getContentAsByteArray());
        assertEquals("public, max-age=300", response.getHeader("Cache-Control"));
        assertEquals("\"" + sha256(png) + "\"", response.getHeader("ETag"));
        QueryCall query = jdbc.calls.get(0);
        assertTrue(query.sql().contains("source_type='system-logo'"));
        assertTrue(query.sql().contains("published_time IS NOT NULL"));
        assertArrayEquals(new Object[]{
                "public/logos/20260711/0123456789abcdef0123456789abcdef.png", path
        }, query.args());

        jdbc.assetRows = List.of();
        assertEquals(404, serve("GET", path).getStatus());

        Map<String, Object> corrupt = asset(
                path,
                "public/logos/20260711/0123456789abcdef0123456789abcdef.png",
                0,
                "public",
                png);
        corrupt.put("sha256", "0".repeat(64));
        jdbc.assetRows = List.of(corrupt);
        assertEquals(404, serve("GET", path).getStatus());
    }

    @Test
    void malformedOrUnavailablePublicSystemLogoFailsClosed() throws Exception {
        assertEquals(404, serve(
                "GET", "/uploads/public/logos/20260711/not-a-content-address.png").getStatus());
        assertTrue(jdbc.calls.isEmpty());

        String validPath = "/uploads/public/logos/20260711/0123456789abcdef0123456789abcdef.png";
        jdbc.fail = true;
        assertEquals(503, serve("GET", validPath).getStatus());
    }

    @Test
    void governedGifAndWebpRemainUsableAfterDeliveryDecodeValidation() throws Exception {
        byte[] gif = gifBytes();
        String gifPath = "/uploads/images/tenant-7/animated.gif";
        write("images/tenant-7/animated.gif", gif);
        Map<String, Object> gifRow = asset(
                gifPath, "tenant-7/animated.gif", 7, "public", gif);
        gifRow.put("media_type", "image/gif");
        jdbc.assetRows = List.of(gifRow);
        assertArrayEquals(gif, serve("GET", gifPath).getContentAsByteArray());

        byte[] webp = java.util.Base64.getDecoder().decode(
                "UklGRhwAAABXRUJQVlA4TA8AAAAvAUAAAAcQ/Y/+ByKi/wEA");
        String webpPath = "/uploads/images/tenant-7/lossless.webp";
        write("images/tenant-7/lossless.webp", webp);
        Map<String, Object> webpRow = asset(
                webpPath, "tenant-7/lossless.webp", 7, "public", webp);
        webpRow.put("media_type", "image/webp");
        jdbc.assetRows = List.of(webpRow);
        assertArrayEquals(webp, serve("GET", webpPath).getContentAsByteArray());
    }

    private MockHttpServletResponse serve(String method, String path) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest(method, path);
        MockHttpServletResponse response = new MockHttpServletResponse();
        controller.serve(request, response);
        return response;
    }

    private void write(String relativePath, byte[] content) throws IOException {
        Path path = tempDir.resolve(relativePath);
        Files.createDirectories(path.getParent());
        Files.write(path, content);
    }

    private Map<String, Object> asset(
            String publicUrl,
            String storageKey,
            long tenantId,
            String visibility,
            byte[] content) {
        Map<String, Object> row = new HashMap<>();
        row.put("tenant_id", tenantId);
        row.put("storage_key", storageKey);
        row.put("public_url", publicUrl);
        row.put("media_type", "image/png");
        row.put("size_bytes", (long) content.length);
        row.put("sha256", sha256(content));
        row.put("status", "active");
        row.put("visibility", visibility);
        if ("public".equals(visibility)) {
            row.put("source_type", "carousel");
            row.put("purpose", "carousel");
            row.put("owner_type", "service");
            row.put("published_time", "2026-07-11T00:00:00");
        }
        return row;
    }

    private byte[] pngBytes() throws IOException {
        BufferedImage image = new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB);
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        assertTrue(ImageIO.write(image, "png", output));
        return output.toByteArray();
    }

    private byte[] jpegBytes() throws IOException {
        BufferedImage image = new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB);
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        assertTrue(ImageIO.write(image, "jpeg", output));
        return output.toByteArray();
    }

    private byte[] gifBytes() throws IOException {
        BufferedImage image = new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB);
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        assertTrue(ImageIO.write(image, "gif", output));
        return output.toByteArray();
    }

    private String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (Exception exception) {
            throw new AssertionError(exception);
        }
    }

    private static final class StubJdbc extends JdbcTemplate {
        List<Map<String, Object>> assetRows = List.of();
        List<Map<String, Object>> avatarRows = List.of();
        final List<QueryCall> calls = new ArrayList<>();
        boolean fail;

        @Override
        public List<Map<String, Object>> queryForList(String sql, Object... args) {
            calls.add(new QueryCall(sql, args.clone()));
            if (fail) throw new DataAccessResourceFailureException("database unavailable");
            return sql.contains("sys_admin_user") ? avatarRows : assetRows;
        }
    }

    private record QueryCall(String sql, Object[] args) {}
}
