package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.*;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DashboardService;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/dashboard")
@Validated
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    /**
     * 仪表盘汇总统计
     */
    @GetMapping("/summary")
    public Result<DashboardSummaryVO> summary(@RequestParam(value = "accountId", required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        DashboardSummaryVO result = dashboardService.summary(tenantId, accountId);
        return Result.ok(result);
    }

    /**
     * 销售趋势
     */
    @GetMapping("/sales-trend")
    public Result<SalesTrendVO> salesTrend(
            @RequestParam(defaultValue = "7") int days,
            @RequestParam(value = "accountId", required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        SalesTrendVO result = dashboardService.salesTrend(tenantId, accountId, days);
        return Result.ok(result);
    }

    /**
     * 订单消息趋势
     */
    @GetMapping("/order-message-trend")
    public Result<SalesTrendVO> orderMessageTrend(
            @RequestParam(defaultValue = "7") int days,
            @RequestParam(value = "accountId", required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        SalesTrendVO result = dashboardService.orderMessageTrend(tenantId, accountId, days);
        return Result.ok(result);
    }

    /**
     * 类目销售统计
     */
    @GetMapping("/category-sales")
    public Result<List<CategorySalesVO>> categorySales() {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<CategorySalesVO> result = dashboardService.categorySales(tenantId);
        return Result.ok(result);
    }

    /**
     * 账号健康
     */
    @GetMapping("/account-health")
    public Result<List<AccountHealthVO>> accountHealth() {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<AccountHealthVO> result = dashboardService.accountHealth(tenantId);
        return Result.ok(result);
    }

    /**
     * 最近操作日志
     */
    @GetMapping("/recent-logs")
    public Result<List<RecentLogVO>> recentLogs(
            @RequestParam(defaultValue = "20") int limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<RecentLogVO> result = dashboardService.recentLogs(tenantId, limit);
        return Result.ok(result);
    }
}
