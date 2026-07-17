package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;

/**
 * 数据同步接收端鉴权过滤器：保护 /api/sync/* 系列接口。
 * <p>
 * 路径走 /api/sync/* 以复用线上 Nginx 已有的 /api/ 反代规则（/open-api/ 走 SPA fallback 不可达）。
 * UserJwtAuthFilter 在 shouldNotFilter 中跳过 /api/sync/，由本过滤器独立鉴权。
 * 采用 fail-closed 策略：若 xianyu.sync.token 未配置，直接返回 503 拒绝所有请求。
 * Token 比较使用 MessageDigest.isEqual 实现常量时间比较，避免时序攻击。
 */
@Component
@Order(3)
public class SyncAuthFilter extends OncePerRequestFilter {
    private static final Set<String> PROTECTED_PATHS = Set.of(
            "/api/sync/ping",
            "/api/sync/receive"
    );
    private static final ObjectMapper JSON = new ObjectMapper();

    private final String configuredToken;

    public SyncAuthFilter(@Value("${xianyu.sync.token:}") String configuredToken) {
        this.configuredToken = configuredToken == null ? "" : configuredToken.trim();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // 反向匹配：只有受保护路径才进入过滤器
        return !PROTECTED_PATHS.contains(request.getRequestURI());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (configuredToken.isBlank()) {
            deny(response, HttpServletResponse.SC_SERVICE_UNAVAILABLE, "sync API is disabled");
            return;
        }
        String supplied = request.getHeader("X-Sync-Token");
        if (supplied == null || supplied.isBlank()) {
            String authorization = request.getHeader("Authorization");
            if (authorization != null && authorization.startsWith("Bearer ")) {
                supplied = authorization.substring(7);
            }
        }
        if (supplied == null || !MessageDigest.isEqual(
                configuredToken.getBytes(StandardCharsets.UTF_8),
                supplied.getBytes(StandardCharsets.UTF_8))) {
            deny(response, HttpServletResponse.SC_FORBIDDEN, "invalid sync token");
            return;
        }
        response.setHeader("Cache-Control", "no-store");
        filterChain.doFilter(request, response);
    }

    private static void deny(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSON.writeValueAsString(new Result<>(status, message, null)));
    }
}
