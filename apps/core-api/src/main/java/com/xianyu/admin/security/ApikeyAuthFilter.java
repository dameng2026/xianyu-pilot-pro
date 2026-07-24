package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 对外滑块求解 API 的 X-Api-Key 鉴权过滤器。
 * 仅拦截 /api/v1/slider/solve，校验 apiKey 并设置 ApiSliderContext。
 * UserJwtAuthFilter 已豁免该路径，避免与 JWT 鉴权叠加。
 */
@Component
@Order(4)
public class ApikeyAuthFilter extends OncePerRequestFilter {

    private static final Set<String> PROTECTED_PATHS = Set.of("/api/v1/slider/solve");
    private static final ObjectMapper JSON = new ObjectMapper();

    private final ApikeyVerifier verifier;

    @Autowired
    public ApikeyAuthFilter(ApikeyVerifier verifier) {
        this.verifier = verifier;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !PROTECTED_PATHS.contains(request.getRequestURI());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String apiKey = request.getHeader("X-Api-Key");
        if (apiKey == null || apiKey.isBlank()) {
            deny(response, HttpServletResponse.SC_UNAUTHORIZED, "missing X-Api-Key header");
            return;
        }
        ApikeyVerifier.VerifiedCredential cred = verifier.verify(apiKey);
        if (cred == null) {
            deny(response, HttpServletResponse.SC_UNAUTHORIZED, "invalid or disabled api key");
            return;
        }
        ApiSliderContext.set(cred.tenantId(), cred.apiKeyPrefix());
        try {
            response.setHeader("Cache-Control", "no-store");
            filterChain.doFilter(request, response);
        } finally {
            ApiSliderContext.clear();
        }
    }

    private static void deny(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSON.writeValueAsString(new Result<>(status, message, null)));
    }
}
