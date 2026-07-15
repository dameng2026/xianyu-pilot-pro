package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.BillingPlanService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 套餐接口：管理员后台和用户前台共用同一份 billing_plan 数据。
 */
@RestController
public class BillingPlanController {
    private final BillingPlanService billingPlanService;

    public BillingPlanController(BillingPlanService billingPlanService) {
        this.billingPlanService = billingPlanService;
    }

    @GetMapping({"/api/billing/plans", "/admin-api/billing/plans"})
    public Result<List<Map<String, Object>>> enabledPlans() {
        return Result.ok(billingPlanService.enabledPlans());
    }

    @GetMapping("/admin-api/billing/plans/page")
    public Result<PageResult<Map<String, Object>>> page(@RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size,
                                                        @RequestParam(required = false) String keyword,
                                                        @RequestParam(required = false) String status) {
        return Result.ok(billingPlanService.page(current, size, keyword, status));
    }

    @GetMapping("/admin-api/billing/plans/{id}")
    public Result<Map<String, Object>> detail(@PathVariable long id) {
        return Result.ok(billingPlanService.detail(id));
    }

    @PostMapping("/admin-api/billing/plans")
    public Result<Map<String, Object>> create(@RequestBody Map<String, Object> data) {
        return Result.ok(billingPlanService.create(data));
    }

    @PutMapping("/admin-api/billing/plans/{id}")
    public Result<Map<String, Object>> update(@PathVariable long id, @RequestBody Map<String, Object> data) {
        return Result.ok(billingPlanService.update(id, data));
    }

    @DeleteMapping("/admin-api/billing/plans/{id}")
    public Result<Void> delete(@PathVariable long id) {
        billingPlanService.delete(id);
        return Result.ok(null);
    }
}
