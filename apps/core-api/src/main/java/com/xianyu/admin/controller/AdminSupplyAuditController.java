package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SupplyAuditService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 后台审核工作台 API
 */
@RestController
@RequestMapping("/admin-api/supply/audit")
public class AdminSupplyAuditController {

    private final SupplyAuditService auditService;

    public AdminSupplyAuditController(SupplyAuditService auditService) {
        this.auditService = auditService;
    }

    @GetMapping("/pending")
    public Result<Map<String, Object>> pendingList(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String moduleKey) {
        return Result.ok(auditService.pendingList(page, size, moduleKey));
    }

    @PostMapping("/{id}/approve")
    public Result<Map<String, Object>> approve(@PathVariable Long id, @RequestBody(required = false) Map<String, Object> body) {
        String reason = body != null ? (String) body.get("reason") : "";
        return Result.ok(auditService.approve(id, reason));
    }

    @PostMapping("/{id}/reject")
    public Result<Map<String, Object>> reject(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        String reason = (String) body.get("reason");
        return Result.ok(auditService.reject(id, reason));
    }

    @GetMapping("/history")
    public Result<Map<String, Object>> history(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String moduleKey,
            @RequestParam(required = false) String status) {
        return Result.ok(auditService.history(page, size, moduleKey, status));
    }
}
