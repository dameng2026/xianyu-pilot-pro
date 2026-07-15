package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryTextSourceService;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/auto-delivery/sources")
public class DeliveryTextSourceController {
    private final DeliveryTextSourceService deliveryTextSourceService;

    public DeliveryTextSourceController(DeliveryTextSourceService deliveryTextSourceService) {
        this.deliveryTextSourceService = deliveryTextSourceService;
    }

    @GetMapping
    public Result<PageResult<Map<String, Object>>> page(@RequestParam(required = false) String keyword,
                                                        @RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(deliveryTextSourceService.page(tenantId, keyword, current, size));
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(deliveryTextSourceService.detail(tenantId, id));
    }

    @PostMapping
    public Result<Map<String, Object>> create(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long id = deliveryTextSourceService.create(tenantId, body);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        return Result.ok(result);
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        deliveryTextSourceService.update(tenantId, id, body);
        return Result.ok(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        deliveryTextSourceService.delete(tenantId, id);
        return Result.ok(null);
    }

    @GetMapping("/{id}/goods")
    public Result<Map<String, Object>> goods(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source", deliveryTextSourceService.detail(tenantId, id));
        result.put("configuredGoods", deliveryTextSourceService.listConfiguredGoods(tenantId, id));
        result.put("allGoods", deliveryTextSourceService.candidateGoods(tenantId));
        return Result.ok(result);
    }

    @PostMapping("/{id}/recommend")
    public Result<Map<String, Object>> recommend(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(deliveryTextSourceService.recommendGoods(tenantId, id));
    }

    @PostMapping("/{id}/apply")
    public Result<Void> apply(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        @SuppressWarnings("unchecked")
        List<Number> rawGoodsIds = (List<Number>) body.get("goodsIds");
        List<Long> goodsIds = rawGoodsIds == null ? List.of() : rawGoodsIds.stream().map(Number::longValue).toList();
        String timing = body == null ? null : String.valueOf(body.getOrDefault("timing", "payDelivery"));
        deliveryTextSourceService.applySourceToGoods(tenantId, id, goodsIds, timing);
        return Result.ok(null);
    }

    @DeleteMapping("/{id}/goods/{goodsId}")
    public Result<Void> removeGoods(@PathVariable Long id, @PathVariable Long goodsId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        deliveryTextSourceService.removeGoodsFromSource(tenantId, id, goodsId);
        return Result.ok(null);
    }
}
