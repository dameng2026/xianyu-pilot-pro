package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.ApiSliderSolveStatsVO;
import com.xianyu.admin.mapper.ApiSliderSolveRecordMapper;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.ApiCredentialService;
import com.xianyu.admin.service.ApiSliderSolveService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class ApiIntegrationController {

    private final ApiCredentialService credentialService;
    private final ApiSliderSolveService solveService;
    private final ApiSliderSolveRecordMapper recordMapper;

    public ApiIntegrationController(ApiCredentialService credentialService,
                                    ApiSliderSolveService solveService,
                                    ApiSliderSolveRecordMapper recordMapper) {
        this.credentialService = credentialService;
        this.solveService = solveService;
        this.recordMapper = recordMapper;
    }

    // ========== 前台用户端 ==========

    @GetMapping("/api/api-integration/credential")
    public Result<Map<String, Object>> getCredential() {
        Long tenantId = UserContext.getTenantId();
        if (tenantId == null) throw new BizException(401, "请先登录");
        return Result.ok(credentialService.getOrCreateCredential(tenantId));
    }

    @PostMapping("/api/api-integration/credential/reset")
    public Result<Map<String, Object>> resetCredential() {
        Long tenantId = UserContext.getTenantId();
        if (tenantId == null) throw new BizException(401, "请先登录");
        String plainKey = credentialService.resetCredential(tenantId);
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("apiKey", plainKey);
        res.put("message", "密钥已重置，旧密钥已失效。");
        return Result.ok(res);
    }

    @GetMapping("/api/api-integration/overview")
    public Result<Map<String, Object>> overview() {
        Long tenantId = UserContext.getTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null && userId == null) throw new BizException(401, "请先登录");
        Map<String, Object> price = solveService.loadPriceConfig(tenantId);
        Map<String, Object> res = new LinkedHashMap<>();
        // 余额（登录上下文可能只有 tenantId 时，解析该租户的主用户）
        try {
            Long balanceUserId = userId != null ? userId : solveService.resolveTenantUserId(tenantId);
            if (balanceUserId == null) throw new IllegalStateException("tenant main user unavailable");
            Map<String, Object> user = solveService.queryUserBalanceRow(balanceUserId);
            res.put("tokenBalance", ((Number) user.get("token_balance")).longValue());
        } catch (Exception e) {
            res.put("tokenBalance", 0);
        }
        // 单次价格
        if (price != null) {
            res.put("available", true);
            res.put("perCallTokens", price.get("perCallTokens"));
            res.put("perCallPrice", price.get("perCallPrice"));
            res.put("tokenExchangeRate", price.get("tokenExchangeRate"));
        } else {
            res.put("perCallTokens", null);
            res.put("perCallPrice", null);
            res.put("tokenExchangeRate", null);
            res.put("available", false);
        }
        // 今日统计
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        Map<String, Object> todayKpi = recordMapper.selectKpi(todayStart, null, tenantId);
        res.put("todayChargedTokens", getLong(todayKpi, "charged_tokens"));
        res.put("todaySolveCount", getLong(todayKpi, "total"));
        res.put("todaySuccess", getLong(todayKpi, "success_count"));
        return Result.ok(res);
    }

    @GetMapping("/api/api-integration/records")
    public Result<PageResult<Map<String, Object>>> records(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime startTime,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime endTime) {
        Long tenantId = UserContext.getTenantId();
        if (tenantId == null) throw new BizException(401, "请先登录");
        current = PageUtils.normalizeCurrent(current);
        size = PageUtils.normalizeSize(size);
        long total = recordMapper.countRecords(tenantId, status, null, keyword, startTime, endTime);
        List<Map<String, Object>> records = recordMapper.selectRecords(tenantId, status, null, keyword, startTime, endTime, (current - 1) * size, size);
        return Result.ok(new PageResult<>(records, current, size, total));
    }

    @GetMapping("/api/api-integration/stats")
    public Result<Map<String, Object>> stats(@RequestParam(defaultValue = "7") Integer days) {
        Long tenantId = UserContext.getTenantId();
        if (tenantId == null) throw new BizException(401, "请先登录");
        LocalDateTime startTime = computeStartTime(days);
        Map<String, Object> kpi = recordMapper.selectKpi(startTime, null, tenantId);
        List<Map<String, Object>> trend = recordMapper.selectTrend(startTime, null, tenantId);
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("kpi", kpi);
        res.put("trend", trend);
        return Result.ok(res);
    }

    // ========== 后台管理端 ==========

    @GetMapping("/admin-api/admin/api-integration/stats")
    public Result<ApiSliderSolveStatsVO> adminStats(@RequestParam(defaultValue = "7") Integer days) {
        requireAdmin();
        LocalDateTime startTime = computeStartTime(days);
        Map<String, Object> kpi = recordMapper.selectKpi(startTime, null, null);
        List<Map<String, Object>> trend = recordMapper.selectTrend(startTime, null, null);
        List<Map<String, Object>> tenants = recordMapper.selectTenantGroups(startTime, null);
        return Result.ok(new ApiSliderSolveStatsVO(kpi, trend, tenants));
    }

    @GetMapping("/admin-api/admin/api-integration/records")
    public Result<PageResult<Map<String, Object>>> adminRecords(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long tenantId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String apiKeyPrefix,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime startTime,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime endTime) {
        requireAdmin();
        current = PageUtils.normalizeCurrent(current);
        size = PageUtils.normalizeSize(size);
        long total = recordMapper.countRecords(tenantId, status, apiKeyPrefix, keyword, startTime, endTime);
        List<Map<String, Object>> records = recordMapper.selectRecords(tenantId, status, apiKeyPrefix, keyword, startTime, endTime, (current - 1) * size, size);
        return Result.ok(new PageResult<>(records, current, size, total));
    }

    @GetMapping("/admin-api/admin/api-integration/today-token")
    public Result<Map<String, Object>> adminTodayToken() {
        requireAdmin();
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        Map<String, Object> kpi = recordMapper.selectKpi(todayStart, null, null);
        return Result.ok(kpi);
    }

    // ========== helpers ==========

    private void requireAdmin() {
        if (!AdminContext.hasRole("R_SUPER") && !AdminContext.hasRole("R_ADMIN")) {
            throw new BizException(403, "需要管理员权限");
        }
    }

    private LocalDateTime computeStartTime(Integer days) {
        if (days == null || days <= 0) return null;
        return LocalDate.now().minusDays((long) days - 1).atStartOfDay();
    }

    private static long getLong(Map<String, Object> row, String key) {
        Object v = row == null ? null : row.get(key);
        if (v == null) return 0;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(v.toString()); } catch (Exception e) { return 0; }
    }
}
