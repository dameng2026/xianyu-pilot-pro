package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Map;

@Component
public class JwtAuthFilter extends OncePerRequestFilter {
    private final JwtUtil jwtUtil;
    private final AuthSessionValidator authSessionValidator;
    private final ObjectMapper objectMapper = new ObjectMapper();
    public JwtAuthFilter(JwtUtil jwtUtil, AuthSessionValidator authSessionValidator) {
        this.jwtUtil = jwtUtil;
        this.authSessionValidator = authSessionValidator;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String uri = applicationPath(request);
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) return true;
        return !uri.startsWith("/admin-api/") || uri.equals("/admin-api/auth/login") || uri.equals("/admin-api/health")
                || uri.equals("/admin-api/ops/liveness") || uri.equals("/admin-api/ops/readiness") || uri.equals("/admin-api/ops/prometheus")
                || uri.startsWith("/admin-api/open-source-bridge/");
    }

    private String applicationPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.isEmpty() && uri.startsWith(contextPath)) {
            return uri.substring(contextPath.length());
        }
        return uri;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain) throws ServletException, IOException {
        try {
            String token = request.getHeader("Authorization");
            if (token != null && token.startsWith("Bearer ")) token = token.substring(7);
            if (token == null || token.isBlank()) throw new IllegalArgumentException("missing token");
            Map<String, Object> payload = jwtUtil.verify(token);
            if (!"admin".equals(payload.get("tokenType"))) {
                throw new IllegalArgumentException("wrong token type");
            }
            Long userId = Long.valueOf(String.valueOf(payload.get("sub")));
            String username = String.valueOf(payload.get("userName"));
            String roles = payload.get("roles") == null ? "" : String.valueOf(payload.get("roles"));
            long authVersion = Long.parseLong(String.valueOf(payload.get("authVersion")));
            authSessionValidator.validateAdmin(userId, username, roles, authVersion);
            // admin 端也设置 TenantContext，方便 DashboardService 等 Service 统一使用
            // admin 平台管理员的 tenantId 为 null，表示可查看所有租户数据
            Object tenantIdObj = payload.get("tenantId");
            Long tenantId = null;
            if (tenantIdObj != null) {
                try { tenantId = Long.valueOf(String.valueOf(tenantIdObj)); } catch (Exception ignored) {}
            }
            AdminContext.set(userId, username, roles);
            TenantContext.setCurrentUserId(userId);
            TenantContext.setCurrentTenantId(tenantId);
            filterChain.doFilter(request, response);
        } catch (AuthSessionValidator.AuthStateUnavailableException e) {
            response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(
                    new Result<>(503, "管理员登录状态暂时无法核验，请稍后重试", null)));
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(Result.unauthorized("登录已过期，请重新登录")));
        } finally {
            AdminContext.clear();
            TenantContext.clear();
        }
    }
}
