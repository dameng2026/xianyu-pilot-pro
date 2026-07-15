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

/** Protects business and dependency metrics with a dedicated scrape token. */
@Component
@Order(2)
public class OpsMetricsAuthFilter extends OncePerRequestFilter {
    private static final Set<String> METRICS_PATHS = Set.of(
            "/api/ops/prometheus", "/admin-api/ops/prometheus"
    );
    private static final ObjectMapper JSON = new ObjectMapper();

    private final String configuredToken;

    public OpsMetricsAuthFilter(@Value("${ops.metrics.token:}") String configuredToken) {
        this.configuredToken = configuredToken == null ? "" : configuredToken.trim();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !METRICS_PATHS.contains(request.getRequestURI());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (configuredToken.isBlank()) {
            deny(response, HttpServletResponse.SC_SERVICE_UNAVAILABLE, "metrics endpoint is disabled");
            return;
        }
        String supplied = request.getHeader("X-Metrics-Token");
        if (supplied == null || supplied.isBlank()) {
            String authorization = request.getHeader("Authorization");
            if (authorization != null && authorization.startsWith("Bearer ")) {
                supplied = authorization.substring(7);
            }
        }
        if (supplied == null || !MessageDigest.isEqual(
                configuredToken.getBytes(StandardCharsets.UTF_8),
                supplied.getBytes(StandardCharsets.UTF_8))) {
            deny(response, HttpServletResponse.SC_FORBIDDEN, "invalid metrics token");
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
