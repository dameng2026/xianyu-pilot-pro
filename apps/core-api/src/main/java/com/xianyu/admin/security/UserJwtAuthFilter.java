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
                || uri.equals("/api/maintenance/status")
                || uri.equals("/api/ops/liveness") || uri.equals("/api/ops/readiness") || uri.equals("/api/ops/prometheus")
                || uri.startsWith("/api/proxy-image/")
                || uri.startsWith("/api/payment/redirect/")
                || uri.startsWith("/api/sync/")
                || uri.startsWith("/api/v1/slider/")
                // AI 客服内部回调：Python 端 SSE 完成后回调持久化消息+扣费，使用 X-Internal-Token 鉴权
                || uri.equals("/api/ai-cs/complete") || uri.equals("/api/ai-cs/tool/result")) {
            // /api/sync/* 由 SyncAuthFilter 独立鉴权（数据同步接收端，后端到后端调用，无用户 JWT）
            // /api/payment/redirect/* 是易支付扫码跳转端点，用户在微信扫码后新浏览器窗口打开，无 JWT
            // /api/v1/slider/* 由 ApikeyAuthFilter 独立鉴权（对外滑块求解 API，X-Api-Key 鉴权）
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

    /**
     * 跳过 ASYNC 分发的重复鉴权。
     *
     * Spring SSE/StreamingResponseBody 会发起 ASYNC 分发，请求会被再次经过过滤器链。
     * 如果不跳过，ASYNC 阶段会重复执行 JWT 校验，且 ASYNC 阶段某些容器会丢失
     * Authorization 头（或控制器在 ASYNC 阶段抛出的业务异常被误判为鉴权失败），
     * 导致 SSE 接口偶发 401，进而被前端误判为"登录过期"。
     *
     * 鉴权只需在初始 REQUEST 分发完成一次即可。
     */
    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        return true;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {
        // 注意：filterChain.doFilter 必须在 try-catch 之外调用。
        // 之前的实现将 doFilter 放在 try 块内，导致控制器（如 AiCsController.chat SSE）
        // 抛出的任何业务异常（DB 连接失败、NPE、超时等）都被 catch (Exception) 捕获，
        // 统一返回 401，前端误判为"登录已过期"并踢出登录。
        //
        // 鉴权只负责校验 token 合法性，业务异常应由控制器自身或全局异常处理器处理。
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
        } catch (AuthSessionValidator.AuthStateUnavailableException e) {
            response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(
                    new Result<>(503, "登录状态暂时无法核验，请稍后重试", null)));
            return;
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(objectMapper.writeValueAsString(
                    Result.unauthorized("登录已过期，请重新登录")));
            return;
        }

        // 鉴权通过后才放行；doFilter 抛出的业务异常由控制器/全局处理器处理，不再被吞成 401
        try {
            filterChain.doFilter(request, response);
        } finally {
            UserContext.clear();
            TenantContext.clear();
        }
    }
}
