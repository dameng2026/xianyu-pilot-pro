package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryGoodsConfigService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** Single-goods adapter over the centralized delivery configuration module. */
@RestController
@RequestMapping("/api/auto-delivery/goods")
public class DeliveryGoodsConfigController {
    private final DeliveryGoodsConfigService configService;

    public DeliveryGoodsConfigController(DeliveryGoodsConfigService configService) {
        this.configService = configService;
    }

    @GetMapping("/{goodsId}/config")
    public Result<Map<String, Object>> getConfig(@PathVariable Long goodsId) {
        return Result.ok(configService.read(TenantContext.getCurrentTenantId(), goodsId));
    }

    @PutMapping("/{goodsId}/config")
    public Result<Void> saveConfig(@PathVariable Long goodsId, @RequestBody Map<String, Object> body) {
        configService.apply(TenantContext.getCurrentTenantId(), List.of(goodsId), body);
        return Result.ok(null);
    }

    @PatchMapping("/{goodsId}/config/{timing}")
    public Result<Void> toggleTiming(@PathVariable Long goodsId,
                                     @PathVariable String timing,
                                     @RequestBody Map<String, Object> body) {
        configService.setEnabled(
                TenantContext.getCurrentTenantId(),
                goodsId,
                timing,
                body == null ? 0 : body.getOrDefault("enabled", 0)
        );
        return Result.ok(null);
    }
}
