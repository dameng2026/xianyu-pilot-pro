package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * User publish address management.
 * Stores POI location data selected by the user for workflow publishing.
 */
@RestController
@RequestMapping("/api/publish-address")
public class PublishAddressController {
    private static final Logger log = LoggerFactory.getLogger(PublishAddressController.class);

    private final JdbcTemplate jdbcTemplate;

    public PublishAddressController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/history")
    public Result<List<Map<String, Object>>> history() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        requireLogin(tenantId, userId);
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id AS id, address_poi_name AS poiName, address_city AS city, address_area AS area, " +
                            "address_prov AS prov, address_division_id AS divisionId, address_gps AS gps, " +
                            "address_poi_id AS poiId, address_detail AS detail, use_count AS useCount " +
                            "FROM user_publish_address WHERE tenant_id=? AND user_id=? AND deleted=0 " +
                            "ORDER BY use_count DESC, updated_time DESC LIMIT 20",
                    tenantId, userId
            );
            List<Map<String, Object>> addresses = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Map<String, Object> normalized = normalizeAddressRow(row);
                // 历史数据必须完整返回：旧版手工地址或旧字段格式仍可回显，不能因新校验被隐藏。
                normalized.put("complete", isAddressComplete(normalized));
                addresses.add(normalized);
            }
            return Result.ok(addresses);
        } catch (Exception e) {
            log.error("查询发布地址历史失败, tenantId={}, userId={}, errorType={}", tenantId, userId, e.getClass().getSimpleName());
            throw new BizException(503, "发布地址历史暂时无法加载，请稍后重试");
        }
    }

    @PostMapping("/save")
    public Result<Void> save(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        requireLogin(tenantId, userId);
        if (body == null) {
            throw new BizException(400, "地址信息不能为空");
        }

        String poiName = clean(body.getOrDefault("poiName", body.getOrDefault("addressText", "")));
        String city = clean(body.getOrDefault("city", ""));
        String area = clean(body.getOrDefault("area", ""));
        String detail = clean(body.getOrDefault("detail", ""));
        String prov = clean(body.getOrDefault("prov", ""));
        String divisionId = clean(body.getOrDefault("divisionId", ""));
        String gps = clean(body.getOrDefault("gps", ""));
        String poiId = clean(body.getOrDefault("poiId", ""));

        if (poiName.isBlank()) {
            throw new BizException(400, "地址不能为空");
        }

        List<String> missingFields = missingAddressFields(poiName, prov, city, area, divisionId, gps, poiId);
        if (!missingFields.isEmpty()) {
            throw new BizException(400, "发布地址缺少关键字段: " + String.join("、", missingFields));
        }

        try {
            int affected = jdbcTemplate.update(
                    "INSERT INTO user_publish_address(tenant_id, user_id, address_poi_name, address_city, address_area, " +
                            "address_prov, address_division_id, address_gps, address_poi_id, address_detail, use_count, deleted, created_time, updated_time) " +
                            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, NOW(), NOW()) " +
                            "ON DUPLICATE KEY UPDATE use_count=use_count+1, " +
                            "address_city=VALUES(address_city), address_area=VALUES(address_area), " +
                            "address_prov=VALUES(address_prov), address_division_id=VALUES(address_division_id), " +
                            "address_gps=VALUES(address_gps), address_poi_id=VALUES(address_poi_id), " +
                            "address_detail=VALUES(address_detail), deleted=0, updated_time=NOW()",
                    tenantId, userId, poiName, city, area, prov, divisionId, gps, poiId, detail
            );
            if (affected != 1 && affected != 2) {
                throw new BizException(503, "发布地址暂时无法保存，请稍后重试");
            }
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存发布地址失败, tenantId={}, userId={}, errorType={}", tenantId, userId, e.getClass().getSimpleName());
            throw new BizException(503, "发布地址暂时无法保存，请稍后重试");
        }
    }

    private void requireLogin(Long tenantId, Long userId) {
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效");
        }
    }

    private Map<String, Object> normalizeAddressRow(Map<String, Object> row) {
        Map<String, Object> normalized = new LinkedHashMap<>(row);
        normalized.put("poiName", clean(row.get("poiName")));
        normalized.put("prov", clean(row.get("prov")));
        normalized.put("city", clean(row.get("city")));
        normalized.put("area", clean(row.get("area")));
        normalized.put("divisionId", clean(row.get("divisionId")));
        normalized.put("gps", clean(row.get("gps")));
        normalized.put("poiId", clean(row.get("poiId")));
        normalized.put("detail", clean(row.get("detail")));
        return normalized;
    }

    private boolean isAddressComplete(Map<String, Object> row) {
        return missingAddressFields(
                clean(row.get("poiName")),
                clean(row.get("prov")),
                clean(row.get("city")),
                clean(row.get("area")),
                clean(row.get("divisionId")),
                clean(row.get("gps")),
                clean(row.get("poiId"))
        ).isEmpty();
    }

    private List<String> missingAddressFields(String poiName, String prov, String city, String area,
                                              String divisionId, String gps, String poiId) {
        List<String> missing = new ArrayList<>();
        if (poiName.isBlank()) missing.add("poiName");
        if (prov.isBlank()) missing.add("prov");
        if (city.isBlank()) missing.add("city");
        if (area.isBlank()) missing.add("area");
        if (divisionId.isBlank()) missing.add("divisionId");
        if (gps.isBlank()) missing.add("gps");
        if (poiId.isBlank()) missing.add("poiId");
        return missing;
    }

    private String clean(Object value) {
        if (value == null) return "";
        String text = String.valueOf(value).trim();
        return "null".equalsIgnoreCase(text) ? "" : text;
    }
}
