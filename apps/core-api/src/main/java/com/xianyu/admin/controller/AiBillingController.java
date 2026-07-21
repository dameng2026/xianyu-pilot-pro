package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiBillingService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

@RestController
public class AiBillingController {
    private final AiBillingService aiBillingService;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public AiBillingController(AiBillingService aiBillingService) {
        this.aiBillingService = aiBillingService;
    }

    @GetMapping("/admin-api/ai-billing/summary")
    public Result<Map<String, Object>> summary() {
        return Result.ok(aiBillingService.summary());
    }

    @GetMapping("/admin-api/ai-billing/model-prices/page")
    public Result<PageResult<Map<String, Object>>> pricePage(@RequestParam(defaultValue = "1") int current,
                                                             @RequestParam(defaultValue = "20") int size,
                                                             @RequestParam(required = false) String keyword,
                                                             @RequestParam(required = false) String modelType,
                                                             @RequestParam(required = false) String enabled) {
        return Result.ok(aiBillingService.pageModelPrices(current, size, keyword, modelType, enabled));
    }

    @PostMapping("/admin-api/ai-billing/model-prices")
    public Result<Map<String, Object>> savePrice(@RequestBody Map<String, Object> data) {
        return Result.ok(aiBillingService.saveModelPrice(data));
    }

    @DeleteMapping("/admin-api/ai-billing/model-prices/{id}")
    public Result<Void> deletePrice(@PathVariable long id) {
        aiBillingService.deleteModelPrice(id);
        return Result.ok(null);
    }

    @GetMapping("/admin-api/ai-billing/usage/page")
    public Result<PageResult<Map<String, Object>>> usagePage(@RequestParam(defaultValue = "1") int current,
                                                             @RequestParam(defaultValue = "20") int size,
                                                             @RequestParam(required = false) String keyword,
                                                             @RequestParam(required = false) String scene,
                                                             @RequestParam(required = false) String status,
                                                             @RequestParam(required = false) Long userId) {
        return Result.ok(aiBillingService.pageUsageLogs(current, size, keyword, scene, status, userId));
    }

    @GetMapping("/admin-api/ai-billing/ledger/page")
    public Result<PageResult<Map<String, Object>>> ledgerPage(@RequestParam(defaultValue = "1") int current,
                                                              @RequestParam(defaultValue = "20") int size,
                                                              @RequestParam(required = false) String keyword,
                                                              @RequestParam(required = false) String changeType) {
        return Result.ok(aiBillingService.pageLedger(current, size, keyword, changeType));
    }

    @GetMapping("/admin-api/ai-billing/recharge-records/page")
    public Result<PageResult<Map<String, Object>>> rechargeRecordsPage(@RequestParam(defaultValue = "1") int current,
                                                                       @RequestParam(defaultValue = "20") int size,
                                                                       @RequestParam(required = false) Long userId,
                                                                       @RequestParam(required = false) String keyword,
                                                                       @RequestParam(required = false) String source) {
        return Result.ok(aiBillingService.pageRechargeRecords(current, size, userId, keyword, source));
    }

    @GetMapping("/admin-api/ai-billing/recharge-records/summary")
    public Result<Map<String, Object>> rechargeRecordsSummary(@RequestParam(required = false) Long userId) {
        return Result.ok(aiBillingService.rechargeRecordsSummary(userId));
    }

    @GetMapping("/api/ai-billing/balance")
    public Result<Map<String, Object>> balance() {
        return Result.ok(aiBillingService.balance());
    }

    @PostMapping("/api/ai-billing/estimate")
    public Result<Map<String, Object>> estimate(@RequestBody Map<String, Object> usage) {
        return Result.ok(aiBillingService.estimateForCurrentUser(usage));
    }

    @PostMapping("/api/ai-billing/estimate-scene")
    public Result<Map<String, Object>> estimateScene(@RequestBody Map<String, Object> usage) {
        return Result.ok(aiBillingService.estimateScenePricingForCurrentUser(usage));
    }

    @PostMapping("/open-api/internal/ai-billing/precheck")
    public Result<Map<String, Object>> internalPrecheck(@RequestBody Map<String, Object> usage, HttpServletRequest request) {
        verifyInternal(request);
        return Result.ok(aiBillingService.precheck(usage));
    }

    @PostMapping("/open-api/internal/ai-billing/charge")
    public Result<Map<String, Object>> internalCharge(@RequestBody Map<String, Object> usage, HttpServletRequest request) {
        verifyInternal(request);
        return Result.ok(aiBillingService.charge(usage));
    }

    private void verifyInternal(HttpServletRequest request) {
        if (internalToken == null || internalToken.isBlank()) {
            throw new BizException(503, "internal API token is not configured");
        }
        String token = request.getHeader("X-Internal-Token");
        if (token == null || !MessageDigest.isEqual(
                internalToken.getBytes(StandardCharsets.UTF_8),
                token.getBytes(StandardCharsets.UTF_8))) {
            throw new BizException(403, "invalid internal token");
        }
    }
}
