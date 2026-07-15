package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 工作流执行前的发布地址预检服务。
 *
 * 闲鱼发布 API 强制要求完整的地图定位信息（prov/divisionId/gps/poiId），
 * 缺失任一字段会触发 FAIL_BIZ_ITEM_EDIT_INVALID_MAP_LOCATION 错误（参见项目记忆）。
 *
 * 本服务在 workflow_execution 创建前对 input.addressPayload 做关键字段校验，
 * 任一失效则抛 BizException(400) 阻断执行，避免无意义的执行记录与生图额度浪费。
 */
@Service
public class WorkflowAddressValidationService {

    private static final String INVALID_REASON = "ADDRESS_INVALID";

    /**
     * 必须齐全的关键字段（与 _resolve_publish_address 的 REQUIRED_KEYS 对齐）。
     * 注：poiName/city/area/detail 也需要，但 prov/divisionId/gps/poiId 是历史最常见的缺失点。
     */
    private static final String[] REQUIRED_KEYS = {"poiName", "prov", "city", "area", "divisionId", "gps", "poiId"};

    /**
     * 断言 input 中的 addressPayload 已包含所有关键字段且非空。
     * 失效时抛 BizException(400)，由 GlobalExceptionHandler 统一返回给前端。
     */
    public void assertExecutionAddressReady(Map<String, Object> input) {
        Map<String, Object> payload = extractAddressPayload(input);
        if (payload == null || payload.isEmpty()) {
            throwAddressInvalid("未配置发布地址，请先在地址管理中添加地址或在运行前选择地址",
                    null, null, null, null, null, null, null, null, REQUIRED_KEYS);
        }
        List<String> missing = new ArrayList<>();
        List<String> blank = new ArrayList<>();
        for (String key : REQUIRED_KEYS) {
            Object v = payload.get(key);
            if (v == null) {
                missing.add(key);
            } else {
                String s = String.valueOf(v).trim();
                if (s.isEmpty() || "null".equalsIgnoreCase(s)) {
                    blank.add(key);
                }
            }
        }
        if (missing.isEmpty() && blank.isEmpty()) {
            return;
        }
        // 合并缺失与空值字段
        List<String> allBad = new ArrayList<>(missing);
        allBad.addAll(blank);
        throwAddressInvalid(
                "发布地址缺少关键字段：" + String.join("、", allBad) + "。请重新选择完整的省、市、区",
                textOr(payload.get("poiName")), textOr(payload.get("prov")),
                textOr(payload.get("city")), textOr(payload.get("area")),
                textOr(payload.get("divisionId")), textOr(payload.get("gps")),
                textOr(payload.get("poiId")), textOr(payload.get("detail")),
                allBad.toArray(new String[0]));
    }

    /**
     * 仅做非阻断校验，返回结果对象。供 continueExecution 等需要返回 JSON 而非抛异常的场景使用。
     *
     * @return Map{ ok:boolean, reason, message, missingFields, addressPayload }
     */
    public Map<String, Object> validateExecutionAddress(Map<String, Object> input) {
        Map<String, Object> payload = extractAddressPayload(input);
        Map<String, Object> r = new LinkedHashMap<>();
        if (payload == null || payload.isEmpty()) {
            r.put("ok", false);
            r.put("reason", INVALID_REASON);
            r.put("message", "未配置发布地址，请先在地址管理中添加地址或在运行前选择地址");
            r.put("missingFields", REQUIRED_KEYS);
            r.put("addressPayload", null);
            return r;
        }
        List<String> missing = new ArrayList<>();
        for (String key : REQUIRED_KEYS) {
            Object v = payload.get(key);
            if (v == null) {
                missing.add(key);
                continue;
            }
            String s = String.valueOf(v).trim();
            if (s.isEmpty() || "null".equalsIgnoreCase(s)) {
                missing.add(key);
            }
        }
        if (missing.isEmpty()) {
            r.put("ok", true);
            r.put("addressPayload", payload);
            return r;
        }
        r.put("ok", false);
        r.put("reason", INVALID_REASON);
        r.put("message", "发布地址缺少关键字段：" + String.join("、", missing) + "。请重新选择完整的省、市、区");
        r.put("missingFields", missing);
        r.put("addressPayload", payload);
        return r;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> extractAddressPayload(Map<String, Object> input) {
        if (input == null || input.isEmpty()) {
            return null;
        }
        Object ap = input.get("addressPayload");
        if (ap instanceof Map<?, ?> raw) {
            Map<String, Object> m = new LinkedHashMap<>();
            raw.forEach((k, v) -> m.put(String.valueOf(k), v));
            return m;
        }
        return null;
    }

    private void throwAddressInvalid(String message, String poiName, String prov, String city, String area,
                                     String divisionId, String gps, String poiId, String detail, String... missingFields) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("ok", false);
        payload.put("reason", INVALID_REASON);
        payload.put("message", message);
        Map<String, Object> addr = new LinkedHashMap<>();
        addr.put("poiName", poiName);
        addr.put("prov", prov);
        addr.put("city", city);
        addr.put("area", area);
        addr.put("divisionId", divisionId);
        addr.put("gps", gps);
        addr.put("poiId", poiId);
        addr.put("detail", detail);
        payload.put("addressPayload", addr);
        payload.put("missingFields", missingFields);
        throw new BizException(400, message, payload);
    }

    private String textOr(Object value) {
        if (value == null) return "";
        String s = String.valueOf(value).trim();
        return "null".equalsIgnoreCase(s) ? "" : s;
    }
}
