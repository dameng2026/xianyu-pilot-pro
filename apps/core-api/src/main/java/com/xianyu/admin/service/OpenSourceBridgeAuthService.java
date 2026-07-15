package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Service
public class OpenSourceBridgeAuthService {
    public static final String HEADER_TOKEN = "X-Open-Source-Token";
    public static final String HEADER_SITE_CODE = "X-Open-Source-Site-Code";
    public static final String HEADER_SITE_NAME = "X-Open-Source-Site-Name";
    public static final String HEADER_FRONTEND_URL = "X-Open-Source-Frontend-Url";
    public static final String HEADER_ADMIN_URL = "X-Open-Source-Admin-Url";
    /**
     * Per-instance correlation token. Each open-source deployment generates a
     * unique, immutable identifier on first boot and sends it with every bridge
     * request. The commercial backend uses this token to attribute advertising
     * applications and payment records to the originating deployment and to
     * return only that deployment's records on history queries.
     */
    public static final String HEADER_INSTANCE_TOKEN = "X-Open-Source-Instance-Token";

    @Value("${open.source.bridge.token:}")
    private String bridgeToken;

    @Value("${open.source.bridge.site-code:open-source}")
    private String allowedSiteCode;

    @Value("${open.source.bridge.site-name:开源版}")
    private String defaultSiteName;

    public OpenSourceSiteContext requireSiteContext(HttpServletRequest request) {
        String configuredToken = safe(bridgeToken).trim();
        if (configuredToken.isEmpty()) {
            throw new BridgeAuthException(503, "开源站桥接服务尚未配置");
        }

        String requestToken = safe(request.getHeader(HEADER_TOKEN)).trim();
        if (requestToken.isEmpty() || !MessageDigest.isEqual(
                configuredToken.getBytes(StandardCharsets.UTF_8),
                requestToken.getBytes(StandardCharsets.UTF_8))) {
            throw new BridgeAuthException(401, "桥接凭证无效");
        }

        String expectedSiteCode = normalizeSiteCode(allowedSiteCode, "open-source");
        String siteCode = normalizeSiteCode(decodeHeader(request.getHeader(HEADER_SITE_CODE)), expectedSiteCode);
        if (!expectedSiteCode.equals(siteCode)) {
            throw new BridgeAuthException(403, "当前站点无权访问桥接接口");
        }

        String siteName = normalizeText(decodeHeader(request.getHeader(HEADER_SITE_NAME)), safe(defaultSiteName).trim(), 120);
        if (siteName.isEmpty()) {
            siteName = "开源版";
        }

        // Per-instance correlation token. Used to attribute advertising
        // applications to the originating open-source deployment. May be blank
        // for older open-source builds that have not yet adopted the instance
        // token; the ad service falls back to site_code filtering in that case.
        String instanceToken = normalizeText(decodeHeader(request.getHeader(HEADER_INSTANCE_TOKEN)), "", 120);

        return new OpenSourceSiteContext(
                siteCode,
                siteName,
                normalizeText(decodeHeader(request.getHeader(HEADER_FRONTEND_URL)), "", 500),
                normalizeText(decodeHeader(request.getHeader(HEADER_ADMIN_URL)), "", 500),
                instanceToken
        );
    }

    private String normalizeSiteCode(String value, String fallback) {
        String text = safe(value).trim().toLowerCase();
        if (text.isEmpty()) {
            return fallback;
        }
        if (text.length() > 40) {
            return text.substring(0, 40);
        }
        return text;
    }

    private String normalizeText(String value, String fallback, int maxLength) {
        String text = safe(value).trim();
        if (text.isEmpty()) {
            text = fallback;
        }
        if (text.length() > maxLength) {
            return text.substring(0, maxLength);
        }
        return text;
    }

    private String safe(String value) {
        return value == null ? "" : value;
    }

    /**
     * URL-decode header values sent by open-source bridge clients. The
     * OpenSourceBridgeClient URL-encodes non-ASCII header values (e.g., Chinese
     * site names) to comply with RFC 7230's ASCII-only requirement for
     * java.net.http.HttpRequest. This method decodes them back to their
     * original form. Values that are not URL-encoded are returned as-is.
     */
    private String decodeHeader(String value) {
        if (value == null || value.isEmpty()) return "";
        if (!value.contains("%")) return value;
        try {
            return URLDecoder.decode(value, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return value;
        }
    }

    public record OpenSourceSiteContext(
            String siteCode,
            String siteName,
            String frontendUrl,
            String adminUrl,
            String instanceToken
    ) {
    }

    public static class BridgeAuthException extends BizException {
        public BridgeAuthException(int code, String message) {
            super(code, message);
        }
    }
}
