package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.GoodsDataAnalysisService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 商品数据分析 Controller
 *
 * 提供商品维度的数据分析能力：
 *  - GET /api/goods-data/summary           全局概览（KPI + 趋势 + TOP 排行）
 *  - GET /api/goods-data/products           商品列表（带订单数据，分页）
 *  - GET /api/goods-data/products/{id}/summary  单商品概览
 *  - GET /api/goods-data/products/{id}/trend     单商品按日趋势
 *  - GET /api/goods-data/products/worst     最差商品筛选
 *
 * 数据来源：xianyu_goods + xianyu_trade_order + xianyu_trade_order_item 表（Java 直连 DB）
 * 不依赖 Python 服务，避免调用闲鱼 API，响应快速且不受风控影响。
 */
@RestController
@RequestMapping("/api/goods-data")
public class GoodsDataAnalysisController {

    private final GoodsDataAnalysisService service;

    public GoodsDataAnalysisController(GoodsDataAnalysisService service) {
        this.service = service;
    }

    /**
     * 全局概览
     *
     * @param accountId 闲鱼账号 ID，不传表示"全部账号"
     * @param days      时间范围：1/3/7/30（默认 7）
     */
    @GetMapping("/summary")
    public Result<Map<String, Object>> summary(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "7") int days) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = service.summary(tenantId, accountId, days);
        return Result.ok(result);
    }

    /**
     * 商品列表（带订单数据）
     *
     * @param accountId 闲鱼账号 ID，不传表示"全部账号"
     * @param days      时间范围：1/3/7/30（默认 7）
     * @param keyword   商品标题关键词
     * @param sortBy    排序字段：exposure/view/want/order/orderAmount/sold/conversion/newest/price
     * @param current   页码
     * @param size      每页数量
     */
    @GetMapping("/products")
    public Result<PageResult<Map<String, Object>>> products(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "7") int days,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "order") String sortBy,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<Map<String, Object>> result = service.products(tenantId, accountId, days, keyword, sortBy, current, size);
        return Result.ok(result);
    }

    /**
     * 单商品概览
     */
    @GetMapping("/products/{id}/summary")
    public Result<Map<String, Object>> productSummary(
            @PathVariable Long id,
            @RequestParam(defaultValue = "7") int days) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = service.productSummary(tenantId, id, days);
        return Result.ok(result);
    }

    /**
     * 单商品按日趋势
     */
    @GetMapping("/products/{id}/trend")
    public Result<List<Map<String, Object>>> productTrend(
            @PathVariable Long id,
            @RequestParam(defaultValue = "7") int days) {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<Map<String, Object>> result = service.productTrend(tenantId, id, days);
        return Result.ok(result);
    }

    /**
     * 最差商品筛选
     *
     * @param metric 筛选维度：exposure（曝光最低）/ view（浏览最低）/ conversion（转化最低）/ order（订单最少）
     * @param limit  返回数量上限（默认 20，最大 200）
     */
    @GetMapping("/products/worst")
    public Result<List<Map<String, Object>>> worstProducts(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "7") int days,
            @RequestParam(defaultValue = "exposure") String metric,
            @RequestParam(defaultValue = "20") int limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<Map<String, Object>> result = service.worstProducts(tenantId, accountId, days, metric, limit);
        return Result.ok(result);
    }
}
