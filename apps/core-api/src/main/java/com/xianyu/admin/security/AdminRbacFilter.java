package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * Enforces the server-side privilege boundary for platform-wide configuration
 * and cross-tenant administration. The JWT filter authenticates the caller;
 * this filter deliberately runs afterwards and authorizes high-impact routes.
 */
@Component
@Order(4)
public class AdminRbacFilter extends OncePerRequestFilter {
    private static final Set<String> SENSITIVE_MODULES = Set.of(
            "users", "plans", "licenses", "model-config-general", "model-config-chat",
            "model-config-image", "model-config-image-2", "model-config-image-3",
            "model-config-image-prompts", "notify-channels", "system-settings",
            "backups", "versions", "xianyu-accounts", "files"
    );
    private static final String MODULE_PREFIX = "/admin-api/admin/modules/";
    private static final ObjectMapper JSON = new ObjectMapper();

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !requiresSuperAdmin(request.getMethod(), canonicalPath(request));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (AdminContext.userId() == null) {
            deny(response, HttpServletResponse.SC_UNAUTHORIZED, "authentication required");
            return;
        }
        if (!AdminContext.hasRole("R_SUPER")) {
            deny(response, HttpServletResponse.SC_FORBIDDEN, "super administrator permission required");
            return;
        }
        filterChain.doFilter(request, response);
    }

    static boolean requiresSuperAdmin(String method, String path) {
        if (path == null || !path.startsWith("/admin-api/") || "OPTIONS".equalsIgnoreCase(method)) {
            return false;
        }
        if (hasPathPrefix(path, "/admin-api/system")
                || hasPathPrefix(path, "/admin-api/payment/configs")
                || hasPathPrefix(path, "/admin-api/payment/token-plans")
                || hasPathPrefix(path, "/admin-api/billing/plans")
                || hasPathPrefix(path, "/admin-api/ai-billing/model-prices")
                || hasPathPrefix(path, "/admin-api/ai-scene-sell-config")
                || hasPathPrefix(path, "/admin-api/ai-scene-plan-benefit")
                || hasPathPrefix(path, "/admin-api/ai-provider/test")
                || hasPathPrefix(path, "/admin-api/admin/xianyu/accounts")
                || hasPathPrefix(path, "/admin-api/open-source-admin")
                || hasPathPrefix(path, "/admin-api/client-errors")
                || hasPathPrefix(path, "/admin-api/admin/users")
                || hasPathPrefix(path, "/admin-api/admin/tenants")) {
            return true;
        }
        if (!path.startsWith(MODULE_PREFIX)) {
            return false;
        }
        String remainder = path.substring(MODULE_PREFIX.length());
        String moduleKey = remainder.split("/", 2)[0];
        return SENSITIVE_MODULES.contains(moduleKey) || isUnsafeMethod(method);
    }

    private static boolean isUnsafeMethod(String method) {
        return !("GET".equalsIgnoreCase(method) || "HEAD".equalsIgnoreCase(method));
    }

    private static boolean hasPathPrefix(String path, String prefix) {
        return path.equals(prefix) || path.startsWith(prefix + "/");
    }

    private static String canonicalPath(HttpServletRequest request) {
        String raw = request.getRequestURI();
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.isEmpty() && raw.startsWith(contextPath)) {
            raw = raw.substring(contextPath.length());
        }
        try {
            raw = URLDecoder.decode(raw, StandardCharsets.UTF_8);
        } catch (IllegalArgumentException ignored) {
            // A malformed escape will not map to a controller; retain it so it
            // cannot accidentally be canonicalized into an allowed endpoint.
        }
        raw = raw.replaceAll(";[^/]*", "").replaceAll("/{2,}", "/");
        return raw;
    }

    private static void deny(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSON.writeValueAsString(new Result<>(status, message, null)));
    }
}
