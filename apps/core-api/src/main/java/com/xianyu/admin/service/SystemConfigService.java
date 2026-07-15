package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * 系统配置服务。
 * 管理系统全局配置项（网站名称、LOGO、备案号、联系方式等）。
 * 数据存储在 admin_module_record 表中，module_key = 'system-settings'，status = 'config'。
 */
@Service
public class SystemConfigService {
    private static final Logger log = LoggerFactory.getLogger(SystemConfigService.class);

    private static final String MODULE_KEY = "system-settings";
    private static final String CONFIG_STATUS = "config";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SystemConfigService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 获取系统配置。
     */
    public Map<String, Object> getConfig() {
        return getRawConfig();
    }

    /**
     * 获取系统配置（供后端内部使用）。
     */
    public Map<String, Object> getRawConfig() {
        String json = getConfigJson();
        if (json != null) {
            try {
                Map<String, Object> parsed = objectMapper.readValue(json,
                        new TypeReference<LinkedHashMap<String, Object>>() {});
                // 合并默认值，确保所有字段存在
                Map<String, Object> merged = new LinkedHashMap<>(defaultConfig());
                merged.putAll(parsed);
                removeRetiredLocationProviderKeys(merged);
                return merged;
            } catch (Exception e) {
                log.error("解析系统配置JSON失败, errorType={}", e.getClass().getSimpleName());
                throw new BizException(503, "系统配置数据异常，请联系管理员核验");
            }
        }
        return defaultConfig();
    }

    /**
     * 保存系统配置
     * 若敏感字段为掩码值 ******，则保留数据库原值，避免被覆盖为掩码字符串
     */
    @Transactional
    public void saveConfig(Map<String, Object> config) {
        if (config == null || config.isEmpty()) {
            throw new BizException(400, "系统配置不能为空");
        }
        try {
            Map<String, Object> safeConfig = new LinkedHashMap<>(config);
            removeRetiredLocationProviderKeys(safeConfig);
            String json = objectMapper.writeValueAsString(safeConfig);
            if (json.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 64 * 1024) {
                throw new BizException(413, "系统配置内容过大");
            }
            Long existingId = findConfigRecordId();
            if (existingId != null) {
                int affected = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json, existingId);
                if (affected != 1) throw new BizException(409, "系统配置状态已变化，请刷新后重试");
                log.info("系统配置已更新 (id={})", existingId);
            } else {
                int affected = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) " +
                        "VALUES(?, ?, ?, NOW(), NOW(), 0)",
                        MODULE_KEY, CONFIG_STATUS, json);
                if (affected != 1) throw new BizException(503, "系统配置写入未被数据库确认");
                log.info("系统配置已创建");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存系统配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "系统配置暂时无法保存，请稍后重试");
        }
    }

    private boolean removeRetiredLocationProviderKeys(Map<String, Object> config) {
        int sizeBefore = config.size();
        config.keySet().removeIf(key -> {
            String normalized = String.valueOf(key).toLowerCase(Locale.ROOT);
            return normalized.contains("map") && (normalized.endsWith("key") || normalized.contains("security"));
        });
        return config.size() != sizeBefore;
    }

    /**
     * 获取默认配置
     */
    private Map<String, Object> defaultConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("siteName", "闲鱼助手后台管理系统");
        config.put("logoUrl", "");
        config.put("icpFilingNo", "");
        config.put("psbFilingNo", "");
        config.put("contactPhone", "");
        config.put("contactEmail", "");
        config.put("workHours", "周一至周五 9:00-18:00");
        config.put("companyAddress", "");
        config.put("wechatOfficial", "");
        return config;
    }

    private String getConfigJson() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1) throw new BizException(503, "系统配置存在重复记录，请联系管理员核验");
            Object json = rows.get(0).get("json_text");
            return json == null ? null : String.valueOf(json);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("读取系统配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "系统配置暂时无法读取，请稍后重试");
        }
    }

    private Long findConfigRecordId() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1 || !(rows.get(0).get("id") instanceof Number id) || id.longValue() <= 0) {
                throw new BizException(503, "系统配置记录异常，请联系管理员核验");
            }
            return id.longValue();
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("定位系统配置记录失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "系统配置暂时无法保存，请稍后重试");
        }
    }
}
