package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.ApiSliderSolveService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 对外滑块求解 API（X-Api-Key 鉴权，由 ApikeyAuthFilter 拦截）。
 * 注意：不使用 Result 包装，直接返回业务 body（第三方对接友好）。
 */
@RestController
@RequestMapping("/api/v1/slider")
public class ExternalSliderSolveController {

    private final ApiSliderSolveService solveService;

    public ExternalSliderSolveController(ApiSliderSolveService solveService) {
        this.solveService = solveService;
    }

    @PostMapping("/solve")
    public Map<String, Object> solve(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        String cookie = body == null ? null : (String) body.get("cookie");
        if (cookie == null || cookie.isBlank()) {
            return Map.of("ok", false, "status", "invalid_params", "error", "cookie is required");
        }
        String clientIp = extractClientIp(request);
        return solveService.solve(body, clientIp);
    }

    private String extractClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isBlank()) ip = request.getHeader("X-Real-IP");
        if (ip == null || ip.isBlank()) ip = request.getRemoteAddr();
        if (ip != null && ip.contains(",")) ip = ip.split(",")[0].trim();
        return ip;
    }
}
