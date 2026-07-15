package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 本地省、市、区地址字典服务。
 *
 * 字典数据是发布定位的唯一数据源；服务仅查询已入库的记录，不会请求第三方地图服务。
 */
@Service
public class ChinaAddressDictService {
    private final JdbcTemplate jdbcTemplate;

    public ChinaAddressDictService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** 返回供前端一次性加载的省→市→区树，叶子节点包含发布所需定位字段。 */
    public Map<String, Object> getTree() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT prov, city, area, adcode, division_id AS divisionId, gps, poi_id AS poiId, " +
                        "poi_name AS poiName, detail FROM china_address_dict " +
                        "WHERE sync_status='success' ORDER BY prov, city, area");

        Map<String, LinkedHashMap<String, List<Map<String, Object>>>> grouped = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            String prov = text(row.get("prov"));
            String city = text(row.get("city"));
            if (prov.isEmpty()) continue;
            if (city.isEmpty()) city = prov;
            grouped.computeIfAbsent(prov, ignored -> new LinkedHashMap<>())
                    .computeIfAbsent(city, ignored -> new ArrayList<>())
                    .add(row);
        }

        List<Map<String, Object>> provinces = new ArrayList<>();
        for (Map.Entry<String, LinkedHashMap<String, List<Map<String, Object>>>> province : grouped.entrySet()) {
            List<Map<String, Object>> cities = new ArrayList<>();
            for (Map.Entry<String, List<Map<String, Object>>> city : province.getValue().entrySet()) {
                List<Map<String, Object>> districts = new ArrayList<>();
                for (Map<String, Object> row : city.getValue()) {
                    Map<String, Object> district = new LinkedHashMap<>();
                    district.put("name", text(row.get("area")));
                    district.put("adcode", text(row.get("adcode")));
                    district.put("divisionId", text(row.get("divisionId")));
                    district.put("gps", text(row.get("gps")));
                    district.put("poiId", text(row.get("poiId")));
                    district.put("poiName", text(row.get("poiName")));
                    district.put("detail", text(row.get("detail")));
                    districts.add(district);
                }
                cities.add(Map.of("name", city.getKey(), "districts", districts));
            }
            provinces.add(Map.of("name", province.getKey(), "cities", cities));
        }
        return Map.of("provinces", provinces);
    }

    public Map<String, Object> getStats() {
        Map<String, Object> row = jdbcTemplate.queryForMap(
                "SELECT COUNT(*) AS total, " +
                        "SUM(CASE WHEN sync_status='pending' THEN 1 ELSE 0 END) AS pending, " +
                        "SUM(CASE WHEN sync_status='success' THEN 1 ELSE 0 END) AS success, " +
                        "SUM(CASE WHEN sync_status='failed' THEN 1 ELSE 0 END) AS failed " +
                        "FROM china_address_dict");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", number(row.get("total")));
        result.put("pending", number(row.get("pending")));
        result.put("success", number(row.get("success")));
        result.put("failed", number(row.get("failed")));
        return result;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private long number(Object value) {
        try {
            return value == null ? 0 : Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return 0;
        }
    }
}
