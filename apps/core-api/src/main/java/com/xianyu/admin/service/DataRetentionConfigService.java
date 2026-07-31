package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 数据保留策略配置服务。
 *
 * 存储模式：复用 admin_module_record 表，module_key = 'data-retention-policy'，status = 'config'。
 * 严格遵循 SystemConfigService 的读/写/异常处理模式：
 *   - 缺省配置返回文档化默认值
 *   - 数据库故障抛 503（不返回伪造默认值）
 *   - 零行更新抛 409（并发保护）
 *
 * 默认配置：enabled=true, retentionDays=14, cleanupCron="0 0 4 * * ?", 所有类别默认开启。
 */
@Service
public class DataRetentionConfigService {
    private static final Logger log = LoggerFactory.getLogger(DataRetentionConfigService.class);

    private static final String MODULE_KEY = "data-retention-policy";
    private static final String CONFIG_STATUS = "config";

    /**
     * 可清理类别白名单（与 spec 第三节 3.1 一致，受保护表绝不在此列表中）。
     *
     * 2026-07 扩展：新增 goodsInfo / ordersInfo / uploadedImage 三个类别，分别用于清理
     * 已下架商品、已完结订单、已删除/过期图片资产。这三类数据均可从闲鱼重新同步获取，
     * 满足"无关用户使用且可以二次获取的数据"的定义。
     */
    static final List<String> CLEANUP_CATEGORIES = List.of(
            "operationLog", "clientErrorLog", "notificationLog", "notificationDedup",
            "chatMessage", "captchaRecord", "autoReplyLog", "uploadRateEvent",
            "goodsInfo", "ordersInfo", "uploadedImage"
    );

    /**
     * 各类别默认保留天数（管理员未在 categoryDays 中显式覆盖时使用）。
     * 业务衍生数据（商品/订单/图片）默认保留更久，避免误删近期业务数据。
     *
     * 注：Map.of() 最多 10 对键值，此处有 11 对，因此使用 Map.ofEntries()。
     */
    static final Map<String, Integer> DEFAULT_CATEGORY_DAYS = Map.ofEntries(
            Map.entry("operationLog", 30),
            Map.entry("clientErrorLog", 30),
            Map.entry("notificationLog", 60),
            Map.entry("notificationDedup", 30),
            Map.entry("chatMessage", 14),
            Map.entry("captchaRecord", 30),
            Map.entry("autoReplyLog", 30),
            Map.entry("uploadRateEvent", 14),
            Map.entry("goodsInfo", 90),
            Map.entry("ordersInfo", 180),
            Map.entry("uploadedImage", 60)
    );

    private static final int MIN_RETENTION_DAYS = 1;
    private static final int MAX_RETENTION_DAYS = 365;
    private static final int DEFAULT_RETENTION_DAYS = 14;
    private static final String DEFAULT_CLEANUP_CRON = "0 0 4 * * ?";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public DataRetentionConfigService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 读取完整配置（管理端用）。合并默认值，确保所有字段存在。
     *
     * 缓存：结果缓存到 dataRetention key='config'；saveConfig 后失效。
     */
    @Cacheable(value = "dataRetention", key = "'config'")
    public Map<String, Object> getConfig() {
        String json = getConfigJson();
        if (json != null) {
            try {
                Map<String, Object> parsed = objectMapper.readValue(json,
                        new TypeReference<LinkedHashMap<String, Object>>() {});
                return mergeWithDefaults(parsed);
            } catch (Exception e) {
                log.error("解析数据保留策略JSON失败, errorType={}", e.getClass().getSimpleName());
                throw new BizException(503, "数据保留策略配置异常，请联系管理员核验");
            }
        }
        return defaultConfig();
    }

    /**
     * 读取公开信息（前台展示用）。仅返回 retentionDays + chatMessageCleanupEnabled。
     * 不暴露全局 enabled、cleanupCron、其他类别开关详情。
     *
     * 缓存：结果缓存到 dataRetention key='public'；saveConfig 后失效。
     */
    @Cacheable(value = "dataRetention", key = "'public'")
    public Map<String, Object> getRetentionInfoForPublic() {
        Map<String, Object> config = getConfig();
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("retentionDays", ((Number) config.get("retentionDays")).intValue());
        @SuppressWarnings("unchecked")
        Map<String, Object> categories = (Map<String, Object>) config.get("categories");
        info.put("chatMessageCleanupEnabled", Boolean.TRUE.equals(categories.get("chatMessage")));
        return info;
    }

    /**
     * 保存配置。校验 retentionDays 范围 [1, 365]，超出抛 400。
     * categoryDays 中每个值也校验 [1, 365]，非法值剔除并使用默认值。
     *
     * 缓存：写入成功后清空整个 dataRetention cache（getConfig 与 getRetentionInfoForPublic 都依赖）。
     */
    @Transactional
    @CacheEvict(value = "dataRetention", allEntries = true)
    public void saveConfig(Map<String, Object> config) {
        if (config == null || config.isEmpty()) {
            throw new BizException(400, "数据保留策略配置不能为空");
        }
        int retentionDays = parseRetentionDays(config.get("retentionDays"));
        if (retentionDays < MIN_RETENTION_DAYS || retentionDays > MAX_RETENTION_DAYS) {
            throw new BizException(400, "保留天数必须在 " + MIN_RETENTION_DAYS + " 到 " + MAX_RETENTION_DAYS + " 之间");
        }
        try {
            Map<String, Object> safeConfig = mergeWithDefaults(new LinkedHashMap<>(config));
            safeConfig.put("retentionDays", retentionDays);
            // 强制覆盖 categoryDays 中的非法值为默认值
            @SuppressWarnings("unchecked")
            Map<String, Object> daysMap = (Map<String, Object>) safeConfig.get("categoryDays");
            if (daysMap != null) {
                for (String cat : CLEANUP_CATEGORIES) {
                    Object v = daysMap.get(cat);
                    int days = (v instanceof Number n) ? n.intValue() : DEFAULT_CATEGORY_DAYS.getOrDefault(cat, DEFAULT_RETENTION_DAYS);
                    if (days < MIN_RETENTION_DAYS || days > MAX_RETENTION_DAYS) {
                        days = DEFAULT_CATEGORY_DAYS.getOrDefault(cat, DEFAULT_RETENTION_DAYS);
                    }
                    daysMap.put(cat, days);
                }
            }
            String json = objectMapper.writeValueAsString(safeConfig);
            if (json.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 64 * 1024) {
                throw new BizException(413, "数据保留策略配置内容过大");
            }
            Long existingId = findConfigRecordId();
            if (existingId != null) {
                int affected = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json, existingId);
                if (affected != 1) throw new BizException(409, "数据保留策略配置状态已变化，请刷新后重试");
                log.info("数据保留策略配置已更新 (id={})", existingId);
            } else {
                int affected = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) " +
                                "VALUES(?, ?, ?, NOW(), NOW(), 0)",
                        MODULE_KEY, CONFIG_STATUS, json);
                if (affected != 1) throw new BizException(503, "数据保留策略配置写入未被数据库确认");
                log.info("数据保留策略配置已创建");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存数据保留策略配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "数据保留策略配置暂时无法保存，请稍后重试");
        }
    }

    /**
     * 清理完成后回写 lastCleanup 统计。
     */
    @Transactional
    public void recordCleanupResult(int totalDeleted, Map<String, Integer> byCategory) {
        try {
            Map<String, Object> config = getConfig();
            Map<String, Object> lastCleanup = new LinkedHashMap<>();
            lastCleanup.put("time", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
            lastCleanup.put("totalDeleted", totalDeleted);
            lastCleanup.put("byCategory", byCategory != null ? byCategory : Map.of());
            config.put("lastCleanup", lastCleanup);

            String json = objectMapper.writeValueAsString(config);
            Long existingId = findConfigRecordId();
            if (existingId != null) {
                int affected = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json, existingId);
                if (affected != 1) {
                    log.warn("回写清理统计失败：零行更新 (id={})", existingId);
                }
            }
        } catch (Exception e) {
            log.warn("回写清理统计失败, errorType={}", e.getClass().getSimpleName(), e);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mergeWithDefaults(Map<String, Object> parsed) {
        Map<String, Object> merged = new LinkedHashMap<>(defaultConfig());
        merged.putAll(parsed);
        // 确保 categories 包含所有白名单类别
        Map<String, Object> defaultCats = defaultCategories();
        Object parsedCatsObj = merged.get("categories");
        if (!(parsedCatsObj instanceof Map)) {
            merged.put("categories", defaultCats);
        } else {
            Map<String, Object> mergedCats = new LinkedHashMap<>(defaultCats);
            mergedCats.putAll((Map<String, Object>) parsedCatsObj);
            merged.put("categories", mergedCats);
        }
        // 确保 categoryDays 包含所有白名单类别的默认值
        Map<String, Object> defaultDays = defaultCategoryDays();
        Object parsedDaysObj = merged.get("categoryDays");
        if (!(parsedDaysObj instanceof Map)) {
            merged.put("categoryDays", defaultDays);
        } else {
            Map<String, Object> mergedDays = new LinkedHashMap<>(defaultDays);
            Map<String, Object> parsedDays = (Map<String, Object>) parsedDaysObj;
            for (String cat : CLEANUP_CATEGORIES) {
                Object v = parsedDays.get(cat);
                if (v instanceof Number n) {
                    int days = n.intValue();
                    if (days >= MIN_RETENTION_DAYS && days <= MAX_RETENTION_DAYS) {
                        mergedDays.put(cat, days);
                    }
                }
            }
            merged.put("categoryDays", mergedDays);
        }
        return merged;
    }

    private Map<String, Object> defaultConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("enabled", true);
        config.put("retentionDays", DEFAULT_RETENTION_DAYS);
        config.put("cleanupCron", DEFAULT_CLEANUP_CRON);
        config.put("categories", defaultCategories());
        config.put("categoryDays", defaultCategoryDays());
        config.put("lastCleanup", null);
        return config;
    }

    private Map<String, Object> defaultCategories() {
        Map<String, Object> cats = new LinkedHashMap<>();
        for (String cat : CLEANUP_CATEGORIES) {
            cats.put(cat, true);
        }
        return cats;
    }

    private Map<String, Object> defaultCategoryDays() {
        Map<String, Object> days = new LinkedHashMap<>();
        for (String cat : CLEANUP_CATEGORIES) {
            days.put(cat, DEFAULT_CATEGORY_DAYS.getOrDefault(cat, DEFAULT_RETENTION_DAYS));
        }
        return days;
    }

    private int parseRetentionDays(Object value) {
        if (value instanceof Number n) return n.intValue();
        if (value instanceof String s) {
            try {
                return Integer.parseInt(s.trim());
            } catch (NumberFormatException e) {
                throw new BizException(400, "保留天数必须是整数");
            }
        }
        throw new BizException(400, "保留天数必须是整数");
    }

    private String getConfigJson() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1) throw new BizException(503, "数据保留策略配置存在重复记录，请联系管理员核验");
            Object json = rows.get(0).get("json_text");
            return json == null ? null : String.valueOf(json);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("读取数据保留策略配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "数据保留策略配置暂时无法读取，请稍后重试");
        }
    }

    private Long findConfigRecordId() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1 || !(rows.get(0).get("id") instanceof Number id) || id.longValue() <= 0) {
                throw new BizException(503, "数据保留策略配置记录异常，请联系管理员核验");
            }
            return id.longValue();
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("定位数据保留策略配置记录失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "数据保留策略配置暂时无法保存，请稍后重试");
        }
    }
}
