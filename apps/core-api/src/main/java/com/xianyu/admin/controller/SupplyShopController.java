package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SupplyShopService;
import com.xianyu.admin.service.TradeConfigService;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 买家前台货源商城 API
 */
@RestController
@RequestMapping("/api/supply-shop")
public class SupplyShopController {

    private final SupplyShopService shopService;
    private final TradeConfigService configService;

    public SupplyShopController(SupplyShopService shopService, TradeConfigService configService) {
        this.shopService = shopService;
        this.configService = configService;
    }

    @GetMapping("/products")
    public Result<Map<String, Object>> listProducts(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(value = "size", defaultValue = "20") int size,
            @RequestParam(value = "pageSize", required = false) Integer pageSize,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String sort) {
        int actualSize = (pageSize != null && pageSize > 0) ? pageSize : size;
        return Result.ok(shopService.listProducts(page, actualSize, category, type, keyword, sort));
    }

    @GetMapping("/products/{source}/{id}")
    public Result<Map<String, Object>> getProductDetail(@PathVariable String source, @PathVariable Long id) {
        return Result.ok(shopService.getProductDetail(source, id));
    }

    /**
     * 购买接口（Phase 2 实现完整支付流程，此处先返回提示）
     */
    @PostMapping("/purchase")
    public Result<Map<String, Object>> purchase(@RequestBody Map<String, Object> body) {
        Map<String, Object> result = new HashMap<>();
        result.put("message", "购买功能将在 Phase 2 交易功能上线后可用");
        return Result.ok(result);
    }

    /**
     * 获取客服微信
     */
    @GetMapping("/customer-service")
    public Result<Map<String, Object>> customerService() {
        Map<String, Object> result = new HashMap<>();
        result.put("wechat", configService.getCustomerServiceWechat());
        return Result.ok(result);
    }
}
