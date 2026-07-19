package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.dto.XianyuTradeOrderDTO;
import com.xianyu.admin.dto.XianyuTradeOrderVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.OrderDeliveryCommandService;
import com.xianyu.admin.service.XianyuTradeOrderService;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/orders")
@Validated
public class XianyuTradeOrderController {
    private final XianyuTradeOrderService orderService;
    private final OrderDeliveryCommandService orderDeliveryCommandService;

    public XianyuTradeOrderController(XianyuTradeOrderService orderService,
                                      OrderDeliveryCommandService orderDeliveryCommandService) {
        this.orderService = orderService;
        this.orderDeliveryCommandService = orderDeliveryCommandService;
    }

    /**
     * 分页查询订单列表
     */
    @GetMapping
    public Result<PageResult<XianyuTradeOrderVO>> page(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) String buyerId,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "false") boolean sync) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (sync) {
            throw new BizException(410, "GET 订单列表不再执行同步；请先调用 POST /api/orders/sync，再刷新列表");
        }
        PageResult<XianyuTradeOrderVO> result = orderService.page(tenantId, accountId, keyword, status, buyerId, current, size);
        return Result.ok(result);
    }

    /**
     * 查询订单详情（含订单项）
     */
    @GetMapping("/{id}")
    public Result<XianyuTradeOrderVO> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuTradeOrderVO result = orderService.detail(tenantId, id);
        return Result.ok(result);
    }

    /**
     * 查询今日订单金额（仅统计 order_status IN (1,2,3,4) 且 deleted=0 的订单 total_amount 之和）。
     * accountId 为空时统计当前租户全部账号。
     */
    @GetMapping("/today-amount")
    public Result<Map<String, Object>> todayAmount(@RequestParam(required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        BigDecimal amount = orderService.todayAmount(tenantId, accountId);
        Map<String, Object> result = new HashMap<>();
        result.put("todayAmount", amount == null ? BigDecimal.ZERO : amount);
        return Result.ok(result);
    }

    /**
     * 更新订单
     */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody XianyuTradeOrderDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        orderService.update(tenantId, id, dto);
        return Result.ok(null);
    }

    @PostMapping("/{id}/manual-delivery")
    public Result<Void> manualDelivery(@PathVariable Long id, @Valid @RequestBody OrderManualDeliveryRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        orderDeliveryCommandService.manualDelivery(tenantId, id, request);
        return Result.ok(null);
    }

    @PostMapping("/{id}/sync")
    public Result<Map<String, Object>> syncOne(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = orderDeliveryCommandService.syncOrder(tenantId, id);
        return Result.ok(result);
    }

    @PostMapping("/sync")
    public Result<Map<String, Object>> syncList(@RequestBody OrderSyncRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = orderDeliveryCommandService.syncOrders(tenantId, request);
        return Result.ok(result);
    }
}
