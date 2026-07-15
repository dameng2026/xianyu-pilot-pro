package com.xianyu.admin.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * 为每个 HTTP 请求生成/透传 request id。
 *
 * Phase 3 目标：让 core-api、automation-service、crawler-service 日志可以用同一个
 * X-Request-Id 串联起来，方便线上问题定位和自动化回归失败复盘。
 */
public class TraceIdFilter extends OncePerRequestFilter {
    public static final String HEADER_NAME = "X-Request-Id";
    public static final String MDC_KEY = "requestId";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String requestId = normalize(request.getHeader(HEADER_NAME));
        if (requestId == null) {
            requestId = UUID.randomUUID().toString().replace("-", "");
        }
        MDC.put(MDC_KEY, requestId);
        response.setHeader(HEADER_NAME, requestId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }

    private String normalize(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        if (trimmed.isEmpty() || trimmed.length() > 128) return null;
        // 避免日志注入：仅允许常见 trace id 字符。
        if (!trimmed.matches("[A-Za-z0-9._:-]+")) return null;
        return trimmed;
    }
}
