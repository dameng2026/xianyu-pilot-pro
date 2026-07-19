package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryGoodsConfigService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
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

    /**
     * POST /api/auto-delivery/goods/configs/batch
     * 请求体：{"goodsIds": [1, 2, 3]}
     * 返回：{ "1": {...}, "2": {...}, ... }，未配置的商品不在返回 Map 中。
     * 用于自动发货页面首屏一次性加载所有商品配置，避免逐个请求造成 3s+ 等待。
     */
    @PostMapping("/configs/batch")
    public Result<Map<String, Object>> batchGetConfigs(@RequestBody Map<String, Object> body) {
        Object raw = body == null ? null : body.get("goodsIds");
        List<Long> goodsIds;
        try {
            if (raw instanceof List<?> list) {
                goodsIds = list.stream()
                        .filter(item -> item != null && !String.valueOf(item).isBlank())
                        .map(item -> Long.parseLong(String.valueOf(item)))
                        .filter(id -> id > 0)
                        .distinct()
                        .toList();
            } else {
                goodsIds = List.of();
            }
        } catch (NumberFormatException error) {
            throw new BizException(422, "商品编号列表格式无效");
        }
        Map<Long, Map<String, Object>> rawResult = configService.batchRead(
                TenantContext.getCurrentTenantId(), goodsIds);
        // 转换 Long key → String key，便于前端按字符串 goodsId 索引
        Map<String, Object> response = new LinkedHashMap<>();
        for (Map.Entry<Long, Map<String, Object>> entry : rawResult.entrySet()) {
            response.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        return Result.ok(response);
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
