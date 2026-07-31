package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 后台商品权重调整 API
 */
@RestController
@RequestMapping("/admin-api/supply/weight")
public class AdminSupplyWeightController {

    private final JdbcTemplate jdbcTemplate;

    public AdminSupplyWeightController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PutMapping
    public Result<Map<String, Object>> updateWeight(@RequestBody Map<String, Object> body) {
        String source = (String) body.get("source");
        Long id = ((Number) body.get("id")).longValue();
        Integer weight = ((Number) body.get("weight")).intValue();

        String table = "mall".equals(source) ? "mall_product" : "supply_product";
        int updated = jdbcTemplate.update(
            "UPDATE " + table + " SET weight = ?, updated_time = NOW() WHERE id = ?",
            weight, id);

        Map<String, Object> result = new HashMap<>();
        result.put("message", updated > 0 ? "权重已更新" : "商品不存在");
        result.put("updated", updated);
        return Result.ok(result);
    }
}
