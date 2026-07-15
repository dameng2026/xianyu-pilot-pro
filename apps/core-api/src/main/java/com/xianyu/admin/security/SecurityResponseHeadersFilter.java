package com.xianyu.admin.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/** Adds defense-in-depth browser headers to API and public upload responses. */
@Component
@Order(0)
public class SecurityResponseHeadersFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-Frame-Options", "DENY");
        response.setHeader("Referrer-Policy", "no-referrer");
        response.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
        String path = request.getRequestURI();
        boolean sensitiveApiResponse = (path.startsWith("/api/")
                && !path.startsWith("/api/proxy-image/"))
                || path.startsWith("/admin-api/")
                || path.startsWith("/open-api/internal/");
        if (sensitiveApiResponse) {
            response.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
            response.setHeader("Pragma", "no-cache");
            response.setHeader("Expires", "0");
        }
        if (path.startsWith("/uploads/") || path.startsWith("/api/proxy-image/")) {
            response.setHeader("Content-Security-Policy",
                    "default-src 'none'; frame-ancestors 'none'; sandbox");
        }
        filterChain.doFilter(request, response);
    }
}
