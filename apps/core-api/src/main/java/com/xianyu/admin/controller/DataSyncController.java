package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.BusinessSettingsService;
import com.xianyu.admin.service.DataSyncService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 数据同步控制器。
 * <p>
 * 为 user-web 前端提供数据同步功能的 REST API：
 *   GET  /api/data-sync/config    读取同步配置
 *   POST /api/data-sync/config    保存同步配置
 *   POST /api/data-sync/ping      测试与线上接收端的连通性
 *   POST /api/data-sync/execute   执行同步推送（本地 → 线上）
 * <p>
 * 配置存储在 user_business_setting 表的 data-sync-config key 下，
 * 复用 BusinessSettingsService 进行读写（默认值合并、UPSERT）。
 */
@RestController
@RequestMapping("/api/data-sync")
public class DataSyncController {
    private static final Logger log = LoggerFactory.getLogger(DataSyncController.class);
    private static final String SETTING_KEY = "data-sync-config";

    private final BusinessSettingsService settingsService;
    private final DataSyncService dataSyncService;

    public DataSyncController(BusinessSettingsService settingsService, DataSyncService dataSyncService) {
        this.settingsService = settingsService;
        this.dataSyncService = dataSyncService;
    }

    /**
     * 读取同步配置（合并默认值）。
     */
    @GetMapping("/config")
    public Result<Map<String, Object>> getConfig() {
        return Result.ok(settingsService.getConfig(SETTING_KEY));
    }

    /**
     * 保存同步配置。
     */
    @PostMapping("/config")
    public Result<Void> saveConfig(@RequestBody Map<String, Object> config) {
        settingsService.saveConfig(SETTING_KEY, config);
        return Result.ok(null);
    }

    /**
     * 测试与线上接收端的连通性（不传输数据）。
     * <p>
     * 请求体可选：若未提供 targetBaseUrl/targetToken，则使用已保存的配置。
     */
    @PostMapping("/ping")
    public Result<Map<String, Object>> ping(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> config = mergeWithSaved(body);
        Map<String, Object> result = dataSyncService.pingRemote(config);
        return Result.ok(result);
    }

    /**
     * 执行同步推送。
     * <p>
     * 请求体可选：若未提供 targetBaseUrl/targetToken/targetUsername，则使用已保存的配置。
     * 推送成功后会回写 lastSyncAt/lastSyncStatus/lastSyncMessage 到配置。
     */
    @PostMapping("/execute")
    public Result<Map<String, Object>> execute(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> config = mergeWithSaved(body);
        validateExecuteConfig(config);

        Map<String, Object> result;
        try {
            result = dataSyncService.syncToRemote(config);
        } catch (Exception e) {
            log.error("数据同步执行失败: {}", e.getMessage(), e);
            // 记录失败状态到配置
            updateLastSyncStatus(config, "failed", e.getMessage());
            throw new BizException(503, "数据同步失败: " + e.getMessage());
        }

        // 解析响应状态并回写
        int status = parseInt(result.get("status"), 0);
        boolean ok = status >= 200 && status < 300;
        String message = extractMessage(result.get("body"));
        updateLastSyncStatus(config, ok ? "success" : "failed", message);

        return Result.ok(result);
    }

    private Map<String, Object> mergeWithSaved(Map<String, Object> body) {
        Map<String, Object> saved = settingsService.getConfig(SETTING_KEY);
        if (body == null || body.isEmpty()) {
            return saved;
        }
        // body 覆盖 saved（允许临时覆盖配置进行测试）
        // 注意：跳过 body 中的空字符串/ null 值，避免覆盖 saved 中的有效配置
        Map<String, Object> merged = new LinkedHashMap<>(saved);
        for (Map.Entry<String, Object> e : body.entrySet()) {
            Object v = e.getValue();
            if (v == null) continue;
            if (v instanceof String s && s.isBlank()) continue;
            merged.put(e.getKey(), v);
        }
        return merged;
    }

    private void validateExecuteConfig(Map<String, Object> config) {
        String targetBaseUrl = str(config, "targetBaseUrl");
        String targetToken = str(config, "targetToken");
        String targetUsername = str(config, "targetUsername");
        if (targetBaseUrl == null || targetBaseUrl.isBlank()) {
            throw new BizException(400, "请先配置目标服务器地址");
        }
        if (targetToken == null || targetToken.isBlank()) {
            throw new BizException(400, "请先配置同步 API Token");
        }
        if (targetUsername == null || targetUsername.isBlank()) {
            throw new BizException(400, "请先配置目标账号用户名");
        }
    }

    private void updateLastSyncStatus(Map<String, Object> config, String status, String message) {
        try {
            Map<String, Object> toSave = new LinkedHashMap<>(config);
            toSave.put("lastSyncAt", java.time.LocalDateTime.now().toString());
            toSave.put("lastSyncStatus", status);
            // 避免过长的错误信息污染配置
            String trimmed = message == null ? "" : (message.length() > 500 ? message.substring(0, 500) : message);
            toSave.put("lastSyncMessage", trimmed);
            settingsService.saveConfig(SETTING_KEY, toSave);
        } catch (Exception e) {
            log.warn("回写同步状态失败: {}", e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private static String extractMessage(Object body) {
        if (body instanceof Map) {
            Object msg = ((Map<String, Object>) body).get("message");
            if (msg != null) return String.valueOf(msg);
            Object error = ((Map<String, Object>) body).get("error");
            if (error != null) return String.valueOf(error);
        }
        return body == null ? "" : String.valueOf(body);
    }

    private static int parseInt(Object v, int def) {
        if (v instanceof Number) return ((Number) v).intValue();
        if (v == null) return def;
        try {
            return Integer.parseInt(String.valueOf(v));
        } catch (NumberFormatException e) {
            return def;
        }
    }

    private static String str(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return v == null ? null : String.valueOf(v);
    }
}
