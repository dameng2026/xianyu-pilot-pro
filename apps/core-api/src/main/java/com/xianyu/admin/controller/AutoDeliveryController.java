package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.DeliveryRuleDTO;
import com.xianyu.admin.dto.DeliveryRuleVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutoDeliveryService;
import com.xianyu.admin.service.DeliveryGoodsConfigService;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/auto-delivery/rules")
@Validated
public class AutoDeliveryController {

    private final AutoDeliveryService autoDeliveryService;
    private final DeliveryGoodsConfigService goodsConfigService;

    public AutoDeliveryController(AutoDeliveryService autoDeliveryService,
                                  DeliveryGoodsConfigService goodsConfigService) {
        this.autoDeliveryService = autoDeliveryService;
        this.goodsConfigService = goodsConfigService;
    }

    /**
     * 分页查询发货规则列表
     */
    @GetMapping
    public Result<PageResult<DeliveryRuleVO>> rules(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<DeliveryRuleVO> result = autoDeliveryService.rules(tenantId, accountId, current, size);
        return Result.ok(result);
    }

    /**
     * 创建发货规则
     */
    @PostMapping
    public Result<Void> createRule(@Valid @RequestBody DeliveryRuleDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoDeliveryService.createRule(tenantId, dto);
        return Result.ok(null);
    }

    /**
     * 更新发货规则
     */
    @PutMapping("/{id}")
    public Result<Void> updateRule(@PathVariable Long id, @Valid @RequestBody DeliveryRuleDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoDeliveryService.updateRule(tenantId, id, dto);
        return Result.ok(null);
    }

    /**
     * 删除发货规则（软删除）
     */
    @DeleteMapping("/{id}")
    public Result<Void> deleteRule(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoDeliveryService.deleteRule(tenantId, id);
        return Result.ok(null);
    }

    /**
     * 批量设置发货配置
     * POST /api/auto-delivery/rules/batch
     */
    @PostMapping("/batch")
    public Result<Void> batchSet(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        goodsConfigService.apply(tenantId, goodsIds(body), body);
        return Result.ok(null);
    }

    /**
     * 批量删除发货配置
     * POST /api/auto-delivery/rules/batch-delete
     */
    @PostMapping("/batch-delete")
    public Result<Void> batchDelete(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        goodsConfigService.delete(tenantId, goodsIds(body));
        return Result.ok(null);
    }

    /**
     * 一键配置全部商品
     * POST /api/auto-delivery/rules/apply-all
     */
    @PostMapping("/apply-all")
    public Result<Void> applyAll(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        goodsConfigService.applyAll(tenantId, body);
        return Result.ok(null);
    }

    private List<Long> goodsIds(Map<String, Object> body) {
        if (body == null || !(body.get("goodsIds") instanceof List<?> raw) || raw.isEmpty()) {
            throw new BizException(422, "请选择商品");
        }
        List<Long> ids = new ArrayList<>();
        for (Object value : raw) {
            try {
                long id = value instanceof Number number
                        ? number.longValue()
                        : Long.parseLong(String.valueOf(value));
                if (id <= 0) throw new NumberFormatException();
                ids.add(id);
            } catch (Exception ignored) {
                throw new BizException(422, "商品编号无效");
            }
        }
        return ids;
    }
}
