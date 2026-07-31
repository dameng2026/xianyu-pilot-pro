package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SupplyProductService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 供货商前台 API
 */
@RestController
@RequestMapping("/api/supply")
public class SupplyProductController {

    private final SupplyProductService productService;

    public SupplyProductController(SupplyProductService productService) {
        this.productService = productService;
    }

    @PostMapping("/products")
    public Result<Map<String, Object>> createProduct(@RequestBody Map<String, Object> body) {
        return Result.ok(productService.createProduct(body));
    }

    @GetMapping("/products")
    public Result<Map<String, Object>> listProducts(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String auditStatus) {
        return Result.ok(productService.listMyProducts(page, size, auditStatus));
    }

    @GetMapping("/products/{id}")
    public Result<Map<String, Object>> getProduct(@PathVariable Long id) {
        return Result.ok(productService.getProduct(id));
    }

    @PutMapping("/products/{id}")
    public Result<Map<String, Object>> updateProduct(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(productService.updateProduct(id, body));
    }

    @PostMapping("/products/{id}/online")
    public Result<Map<String, Object>> online(@PathVariable Long id) {
        return Result.ok(productService.online(id));
    }

    @PostMapping("/products/{id}/offline")
    public Result<Map<String, Object>> offline(@PathVariable Long id) {
        return Result.ok(productService.offline(id));
    }

    @DeleteMapping("/products/{id}")
    public Result<Map<String, Object>> delete(@PathVariable Long id) {
        return Result.ok(productService.delete(id));
    }

    @GetMapping("/products/{id}/stats")
    public Result<Map<String, Object>> stats(@PathVariable Long id) {
        return Result.ok(productService.stats(id));
    }

    @GetMapping("/dashboard")
    public Result<Map<String, Object>> dashboard() {
        return Result.ok(productService.dashboard());
    }

    @GetMapping("/sales/trend")
    public Result<Map<String, Object>> salesTrend() {
        return Result.ok(productService.salesTrend());
    }
}
