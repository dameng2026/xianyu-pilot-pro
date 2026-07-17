package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.ClientIpResolver;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.MallProductService;
import com.xianyu.admin.service.PaymentService;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 货源商城前台用户控制器。
 * /api/mall 前缀，需要 UserContext 鉴权。
 * 购买接口复用 PaymentService.createOrder，orderType=mall_product。
 */
@RestController
@RequestMapping("/api/mall")
public class MallProductShopController {
    private static final Logger log = LoggerFactory.getLogger(MallProductShopController.class);

    private final MallProductService mallProductService;
    private final PaymentService paymentService;

    public MallProductShopController(MallProductService mallProductService, PaymentService paymentService) {
        this.mallProductService = mallProductService;
        this.paymentService = paymentService;
    }

    @GetMapping("/products")
    public Result<PageResult<Map<String, Object>>> listProducts(
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        requireUserContext();
        PageResult<Map<String, Object>> result = mallProductService.listShopProducts(type, category, keyword, page, size);
        Long userId = UserContext.userId();
        if (userId != null && userId > 0) {
            mallProductService.attachPurchasedInfo(result.getRecords(), userId);
        }
        return Result.ok(result);
    }

    @GetMapping("/categories")
    public Result<List<Map<String, Object>>> listCategories() {
        requireUserContext();
        return Result.ok(mallProductService.listCategories());
    }

    @GetMapping("/products/{id}")
    public Result<Map<String, Object>> getProduct(@PathVariable long id) {
        requireUserContext();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        Map<String, Object> product = mallProductService.getShopProduct(id);
        Long userId = UserContext.userId();
        if (userId != null && userId > 0) {
            mallProductService.attachPurchasedInfo(product, userId);
        }
        return Result.ok(product);
    }

    /**
     * 创建商城商品支付订单。
     * 复用 PaymentService.createOrder，orderType=mall_product，targetType=mall_product，targetId=商品ID。
     */
    @PostMapping("/purchase")
    public Result<Map<String, Object>> purchase(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        requireUserContext();
        if (body == null || body.isEmpty()) throw new BizException(400, "购买参数不能为空");
        Object productIdRaw = body.get("productId");
        if (productIdRaw == null || String.valueOf(productIdRaw).isBlank()) {
            throw new BizException(400, "请选择要购买的商品");
        }
        long productId;
        try {
            productId = Long.parseLong(String.valueOf(productIdRaw).trim());
        } catch (NumberFormatException e) {
            throw new BizException(400, "商品 ID 非法");
        }
        if (productId <= 0) throw new BizException(400, "商品 ID 非法");
        // 二次校验商品可用并检查库存
        Map<String, Object> product = mallProductService.getShopProduct(productId);
        String productType = String.valueOf(product.getOrDefault("productType", "text"));
        if ("card".equals(productType)) {
            Object stockObj = product.get("stock");
            long stock = stockObj instanceof Number ? ((Number) stockObj).longValue() : 0;
            if (stock <= 0) {
                throw new BizException(400, "商品库存不足，暂时无法购买");
            }
        }
        // 组装支付订单参数
        Map<String, Object> orderData = new LinkedHashMap<>();
        orderData.put("orderType", "mall_product");
        orderData.put("targetType", "mall_product");
        orderData.put("targetId", productId);
        orderData.put("productId", productId);
        Object paymentMethod = body.get("paymentMethod");
        if (paymentMethod == null) paymentMethod = body.get("channel");
        if (paymentMethod == null || String.valueOf(paymentMethod).isBlank()) {
            throw new BizException(400, "请选择支付方式");
        }
        orderData.put("paymentMethod", paymentMethod);
        String clientIp = ClientIpResolver.resolve(request);
        try {
            return Result.ok(paymentService.createOrder(orderData, clientIp));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("商城商品下单失败, productId={}, errorType={}", productId, e.getClass().getSimpleName());
            throw new BizException(503, "下单暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/faqs")
    public Result<List<Map<String, Object>>> listFaqs() {
        requireUserContext();
        return Result.ok(mallProductService.listShopFaqs());
    }

    // ==================== 鉴权 ====================

    private void requireUserContext() {
        Long userId = UserContext.userId();
        Long userTenantId = UserContext.getTenantId();
        Long tenantUserId = TenantContext.getCurrentUserId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (userId == null || userTenantId == null || userTenantId <= 0
                || !Objects.equals(userId, tenantUserId)
                || !Objects.equals(userTenantId, tenantId)) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
    }
}
