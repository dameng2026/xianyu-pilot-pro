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

/**
 * 前台用户 API 的 JWT 鉴权过滤器，拦截 /api/* 下的受保护接口。
 * 登录、注册等公开接口通过 shouldNotFilter 跳过。
 */
@Component
public class UserJwtAuthFilter extends OncePerRequestFilter {
    private final JwtUtil jwtUtil;
    private final AuthSessionValidator authSessionValidator;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public UserJwtAuthFilter(JwtUtil jwtUtil, AuthSessionValidator authSessionValidator) {
        this.jwtUtil = jwtUtil;
        this.authSessionValidator = authSessionValidator;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String uri = applicationPath(request);
        String method = request.getMethod();
        if ("OPTIONS".equalsIgnoreCase(method)) return true;
        if (!uri.startsWith("/api/")) return true;
        if (uri.equals("/api/login/login") || uri.equals("/api/login/capabilities") || uri.equals("/api/login/register")
                || uri.equals("/api/login/sendEmailCode") || uri.equals("/api/login/verifyResetCode")
                || uri.equals("/api/login/resetPassword")
                || uri.equals("/api/health")
                || uri.equals("/api/client-errors") || uri.equals("/api/sse/subscribe")
                || uri.equals("/api/carousel/list") || uri.equals("/api/announcement/list")
                || uri.equals("/api/ops/liveness") || uri.equals("/api/ops/readiness") || uri.equals("/api/ops/prometheus")
                || uri.startsWith("/api/proxy-image/")) {
            return true;
        }
        return false;
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
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {
        try {
            String token = request.getHeader("Authorization");
            if (token != null && token.startsWith("Bearer ")) token = token.substring(7);
            if (token == null || token.isBlank()) throw new IllegalArgumentException("missing token");
            Map<String, Object> payload = jwtUtil.verify(token);
            if (!"user".equals(payload.get("tokenType"))) {
                throw new IllegalArgumentException("wrong token type");
            }
            Long userId = Long.valueOf(String.valueOf(payload.get("sub")));
            String username = String.valueOf(payload.get("userName"));
            Object tenantIdObj = payload.get("tenantId");
            Long tenantId = null;
            if (tenantIdObj != null) {
                tenantId = Long.valueOf(String.valueOf(tenantIdObj));
            }
            if (tenantId == null || tenantId <= 0) throw new IllegalArgumentException("missing tenant");
            long authVersion = Long.parseLong(String.valueOf(payload.get("authVersion")));
            authSessionValidator.validateUser(userId, tenantId, username, authVersion);

            TenantContext.setCurrentUserId(userId);
            TenantContext.setCurrentTenantId(tenantId);
            UserContext.set(userId, username, tenantId);
            filterChain.doFilter(request, response);
        } catch (AuthSessionValidator.AuthStateUnavailableException e) {
            response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(
                    new Result<>(503, "登录状态暂时无法核验，请稍后重试", null)));
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(
                    Result.unauthorized("登录已过期，请重新登录")));
        } finally {
            UserContext.clear();
            TenantContext.clear();
        }
    }
}
