package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.HotGoodsStatService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 热销商品统计控制器
 * 提供手动刷新统计数据的接口
 */
@RestController
@RequestMapping("/admin-api/api/hot-goods")
@Validated
public class HotGoodsStatController {

    private static final Logger log = LoggerFactory.getLogger(HotGoodsStatController.class);

    private final HotGoodsStatService hotGoodsStatService;

    public HotGoodsStatController(HotGoodsStatService hotGoodsStatService) {
        this.hotGoodsStatService = hotGoodsStatService;
    }

    /**
     * 手动刷新热销商品统计数据
     */
    @PostMapping("/refresh")
    public Result<Map<String, Object>> refresh(@RequestParam(defaultValue = "5") int minSales) {
        Long tenantId = TenantContext.getCurrentTenantId();
        int count = hotGoodsStatService.refreshDailyStats(tenantId, minSales);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("count", count);
        result.put("date", LocalDate.now().toString());
        result.put("message", "热销商品统计刷新完成，共记录 " + count + " 条");
        log.info("手动刷新热销商品统计: tenantId={}, minSales={}, count={}", tenantId, minSales, count);
        return Result.ok(result);
    }

    /**
     * 获取统计数据的日期列表
     */
    @GetMapping("/dates")
    public Result<java.util.List<LocalDate>> dates() {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(hotGoodsStatService.listDistinctDates(tenantId));
    }
}