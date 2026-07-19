package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * 功能开关服务。
 * 管理前台各功能页面的访问开关，按账号等级（normal/vip/svp）独立控制。
 *
 * 数据存储：复用 admin_module_record 表（零迁移成本）
 *   - module_key = 'user_feature_switch'
 *   - status     = 'config'
 *   - json_text  = 单例 JSON 对象 {"features": { "<pageKey>": {"normal": true, "vip": true, "svp": true}, ... }}
 *
 * 等级权重：normal=0 < vip=1 < svip/svp=2
 * 判定逻辑（用户等级 = L）：
 *   - 功能该等级开关为 true → 可访问
 *   - 功能该等级开关为 false：
 *     - 存在比 L 更高的等级且开关为 true → reason=level, required_level=第一个开启的更高级别
 *     - 所有等级都为 false → reason=disabled（暂未开放）
 *
 * 失败降级：读取异常时返回默认配置（全部开启），避免后端故障锁死前台。
 */
@Service
public class FeatureSwitchService {
    private static final Logger log = LoggerFactory.getLogger(FeatureSwitchService.class);

    public static final String MODULE_KEY = "user_feature_switch";
    public static final String CONFIG_STATUS = "config";

    /** 等级权重表，兼容 svp/svip 两种写法 */
    private static final Map<String, Integer> LEVEL_WEIGHT = new HashMap<>();
    static {
        LEVEL_WEIGHT.put("normal", 0);
        LEVEL_WEIGHT.put("vip", 1);
        LEVEL_WEIGHT.put("svip", 2);
        LEVEL_WEIGHT.put("svp", 2);
    }

    /** 等级从低到高排序，用于查找"第一个开启的更高级别" */
    private static final List<String> LEVELS_ASC = List.of("normal", "vip", "svp");

    /** 默认功能开关清单：每个功能三个等级全部开启 */
    private static final List<Map<String, Object>> DEFAULT_FEATURES = buildDefaultFeatures();

    private final JdbcTemplate jdbcTemplate;
    private final UserProfileService userProfileService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public FeatureSwitchService(JdbcTemplate jdbcTemplate, UserProfileService userProfileService) {
        this.jdbcTemplate = jdbcTemplate;
        this.userProfileService = userProfileService;
    }

    private static List<Map<String, Object>> buildDefaultFeatures() {
        List<Map<String, Object>> list = new ArrayList<>();
        // 概览（所有等级可用）
        list.add(feature("dashboard", "工作台", "overview", true, true, true));
        list.add(feature("data", "数据看板", "overview", true, true, true));
        // 账号与商品（所有等级可用）
        list.add(feature("accounts", "闲鱼账号", "account", true, true, true));
        list.add(feature("connections", "连接状态", "account", true, true, true));
        list.add(feature("products", "商品管理", "account", true, true, true));
        list.add(feature("orders", "订单管理", "account", true, true, true));
        list.add(feature("product-publish", "商品发布", "account", true, true, true));
        // 消息与商机：商机发掘仅 VIP 及以上可用
        list.add(feature("messages", "消息中心", "message", true, true, true));
        list.add(feature("message-center", "会话收件箱", "message", true, true, true));
        list.add(feature("opportunities", "商机发掘", "message", false, true, true));
        // 自动化：
        //   - 自动发货链路（含货源库、发货声明、发货模板、发货记录）所有等级可用
        //   - 货源商城：VIP 及以上可用
        //   - 工作流、工作流任务、商品草稿箱、图片生成记录：SVIP 专属
        //   - 卡密仓库、定时任务：所有等级均关闭（暂未开放）
        list.add(feature("workflow", "工作流", "automation", false, false, true));
        list.add(feature("workflow-tasks", "工作流任务", "automation", false, false, true));
        list.add(feature("workflow-drafts", "商品草稿箱", "automation", false, false, true));
        list.add(feature("workflow-image-records", "图片生成记录", "automation", false, false, true));
        list.add(feature("card-warehouse", "卡密仓库", "automation", false, false, false));
        list.add(feature("auto-delivery", "自动发货", "automation", true, true, true));
        list.add(feature("delivery-source-library", "货源库", "automation", true, true, true));
        list.add(feature("delivery-statement", "发货声明", "automation", true, true, true));
        list.add(feature("delivery-mall", "货源商城", "automation", false, true, true));
        list.add(feature("delivery-templates", "发货模板", "automation", true, true, true));
        list.add(feature("delivery-records", "发货记录", "automation", true, true, true));
        list.add(feature("scheduled-tasks", "定时任务", "automation", false, false, false));
        list.add(feature("auto-reply", "自动回复", "automation", true, true, true));
        // 系统设置：滑块求解记录仅 VIP 及以上可用
        list.add(feature("logs", "操作日志", "system", true, true, true));
        list.add(feature("slider-solve-records", "滑块求解", "system", false, true, true));
        list.add(feature("feedback", "反馈建议", "system", true, true, true));
        list.add(feature("settings-notify", "通知设置", "system", true, true, true));
        list.add(feature("user-manual", "使用手册", "system", true, true, true));
        list.add(feature("profile", "系统设置", "system", true, true, true));
        // 会员（所有等级可见，用于查看权益与升级入口）
        list.add(feature("vip", "会员中心", "hidden", true, true, true));
        list.add(feature("member-upgrade", "升级会员", "hidden", true, true, true));
        return Collections.unmodifiableList(list);
    }

    private static Map<String, Object> feature(String key, String title, String group) {
        return feature(key, title, group, true, true, true);
    }

    private static Map<String, Object> feature(String key, String title, String group,
                                               boolean normal, boolean vip, boolean svp) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("key", key);
        m.put("title", title);
        m.put("group", group);
        m.put("normal", normal);
        m.put("vip", vip);
        m.put("svp", svp);
        return m;
    }

    /**
     * 管理端：列出所有功能开关（合并默认值）。
     * 返回每个功能含 key/title/group/normal/vip/svp 五个字段。
     *
     * 兜底策略：即使读取存储配置出现任何未预期异常，也降级为默认配置返回，
     * 避免用户端「功能对比」页面因后端 5xx 错误而显示加载失败。
     */
    public List<Map<String, Object>> listSwitches() {
        Map<String, Map<String, Object>> stored;
        try {
            stored = loadStoredFeatures();
        } catch (Exception e) {
            log.warn("listSwitches 读取存储配置失败，降级为默认值, errorType={}", e.getClass().getSimpleName());
            stored = Collections.emptyMap();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> def : DEFAULT_FEATURES) {
            String key = String.valueOf(def.get("key"));
            Map<String, Object> merged = new LinkedHashMap<>(def);
            Map<String, Object> override = stored.get(key);
            if (override != null) {
                for (String level : LEVELS_ASC) {
                    if (override.containsKey(level)) merged.put(level, override.get(level));
                }
                if (override.containsKey("title")) merged.put("title", override.get("title"));
                if (override.containsKey("group")) merged.put("group", override.get("group"));
            }
            result.add(merged);
        }
        // 允许后台预置清单之外的自定义条目（向前兼容）
        for (Map.Entry<String, Map<String, Object>> e : stored.entrySet()) {
            if (isDefaultKey(e.getKey())) continue;
            Map<String, Object> extra = new LinkedHashMap<>(e.getValue());
            if (!extra.containsKey("key")) extra.put("key", e.getKey());
            for (String level : LEVELS_ASC) {
                if (!extra.containsKey(level)) extra.put(level, true);
            }
            result.add(extra);
        }
        return result;
    }

    /**
     * 用户端：返回当前用户可访问/被拦截的页面状态。
     * 返回结构：
     *   {
     *     "level": "normal|vip|svp",
     *     "accessible": { "<pageKey>": true, ... },
     *     "blocked": { "<pageKey>": { "reason": "disabled|level", "required_level": "vip" } }
     *   }
     *
     * 判定逻辑：
     *   - 用户等级对应的开关为 true → 可访问
     *   - 用户等级对应的开关为 false：
     *     - 存在更高级别开关为 true → reason=level, required_level=第一个开启的更高级别
     *     - 所有级别都为 false → reason=disabled
     */
    public Map<String, Object> getStatusForCurrentUser(Long userId) {
        Map<String, Object> status = new LinkedHashMap<>();
        String userLevel = resolveUserLevel(userId);
        status.put("level", userLevel);

        Map<String, Map<String, Object>> stored = loadStoredFeatures();
        Map<String, Boolean> accessible = new LinkedHashMap<>();
        Map<String, Map<String, Object>> blocked = new LinkedHashMap<>();

        for (Map<String, Object> def : DEFAULT_FEATURES) {
            String key = String.valueOf(def.get("key"));
            Map<String, Boolean> levelSwitches = resolveLevelSwitches(key, def, stored);

            boolean userAllowed = boolOr(levelSwitches.get(normalizeLevel(userLevel)), true);
            if (userAllowed) {
                accessible.put(key, true);
                continue;
            }
            accessible.put(key, false);
            Map<String, Object> info = new LinkedHashMap<>();
            String firstHigherOn = findFirstHigherEnabled(userLevel, levelSwitches);
            if (firstHigherOn != null) {
                info.put("reason", "level");
                info.put("required_level", firstHigherOn);
            } else {
                info.put("reason", "disabled");
                info.put("required_level", normalizeLevel(userLevel));
            }
            blocked.put(key, info);
        }
        status.put("accessible", accessible);
        status.put("blocked", blocked);
        return status;
    }

    /**
     * 管理端：保存功能开关配置（整体覆盖）。
     */
    @Transactional
    public void saveConfig(List<Map<String, Object>> features) {
        if (features == null) throw new BizException(400, "功能开关配置不能为空");
        Map<String, Map<String, Object>> normalized = normalizeConfig(features);
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("features", normalized);
        try {
            String json = objectMapper.writeValueAsString(root);
            if (json.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 64 * 1024) {
                throw new BizException(413, "功能开关配置内容过大");
            }
            Long existingId = findConfigRecordId();
            if (existingId != null) {
                int affected = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json, existingId);
                if (affected != 1) throw new BizException(409, "功能开关状态已变化，请刷新后重试");
                log.info("功能开关配置已更新 (id={})", existingId);
            } else {
                int affected = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) " +
                        "VALUES(?, ?, ?, NOW(), NOW(), 0)",
                        MODULE_KEY, CONFIG_STATUS, json);
                if (affected != 1) throw new BizException(503, "功能开关写入未被数据库确认");
                log.info("功能开关配置已创建");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存功能开关配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "功能开关暂时无法保存，请稍后重试");
        }
    }

    /**
     * 初始化默认配置（幂等，已存在则不写）。
     */
    public void initDefaultsIfAbsent() {
        if (findConfigRecordId() != null) return;
        Map<String, Map<String, Object>> features = new LinkedHashMap<>();
        for (Map<String, Object> def : DEFAULT_FEATURES) {
            Map<String, Object> f = new LinkedHashMap<>();
            for (String level : LEVELS_ASC) {
                f.put(level, def.get(level));
            }
            features.put(String.valueOf(def.get("key")), f);
        }
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("features", features);
        try {
            String json = objectMapper.writeValueAsString(root);
            jdbcTemplate.update(
                    "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) " +
                    "VALUES(?, ?, ?, NOW(), NOW(), 0)",
                    MODULE_KEY, CONFIG_STATUS, json);
            log.info("功能开关默认配置已初始化");
        } catch (Exception e) {
            log.warn("初始化功能开关默认配置失败（可忽略）, errorType={}", e.getClass().getSimpleName());
        }
    }

    // ===================== 内部方法 =====================

    /**
     * 解析某功能的三个等级开关状态（合并默认值与存储覆盖）。
     */
    private Map<String, Boolean> resolveLevelSwitches(String key, Map<String, Object> def, Map<String, Map<String, Object>> stored) {
        Map<String, Boolean> result = new LinkedHashMap<>();
        for (String level : LEVELS_ASC) {
            boolean val = boolOr(def.get(level), true);
            Map<String, Object> override = stored.get(key);
            if (override != null && override.containsKey(level)) {
                val = boolOr(override.get(level), val);
            }
            result.put(level, val);
        }
        return result;
    }

    /**
     * 查找比用户等级更高的、第一个开关为 true 的等级。
     * 返回 null 表示没有更高级别开启（含所有级别都关闭的情况）。
     */
    private String findFirstHigherEnabled(String userLevel, Map<String, Boolean> levelSwitches) {
        int userWeight = weightOf(userLevel);
        for (String level : LEVELS_ASC) {
            if (weightOf(level) > userWeight && Boolean.TRUE.equals(levelSwitches.get(level))) {
                return level;
            }
        }
        return null;
    }

    private Map<String, Map<String, Object>> loadStoredFeatures() {
        try {
            String json = getConfigJson();
            if (json == null) return Collections.emptyMap();
            Map<String, Object> parsed = objectMapper.readValue(json,
                    new TypeReference<LinkedHashMap<String, Object>>() {});
            Object featuresObj = parsed.get("features");
            if (!(featuresObj instanceof Map)) return Collections.emptyMap();
            @SuppressWarnings("unchecked")
            Map<String, Object> raw = (Map<String, Object>) featuresObj;
            Map<String, Map<String, Object>> result = new LinkedHashMap<>();
            for (Map.Entry<String, Object> e : raw.entrySet()) {
                if (e.getValue() instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> fm = (Map<String, Object>) e.getValue();
                    result.put(e.getKey(), fm);
                }
            }
            return result;
        } catch (Exception e) {
            log.error("读取功能开关配置失败，使用默认值, errorType={}", e.getClass().getSimpleName());
            return Collections.emptyMap();
        }
    }

    private String getConfigJson() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1) throw new BizException(503, "功能开关存在重复记录，请联系管理员核验");
            Object json = rows.get(0).get("json_text");
            return json == null ? null : String.valueOf(json);
        } catch (BizException e) {
            throw e;
        } catch (DataAccessException e) {
            log.warn("读取功能开关配置数据库访问失败，降级为默认值, errorType={}", e.getClass().getSimpleName());
            return null;
        } catch (Exception e) {
            log.error("读取功能开关配置失败, errorType={}", e.getClass().getSimpleName());
            return null;
        }
    }

    private Long findConfigRecordId() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 2",
                    MODULE_KEY, CONFIG_STATUS);
            if (rows.isEmpty()) return null;
            if (rows.size() != 1) throw new BizException(503, "功能开关存在重复记录，请联系管理员核验");
            Object idObj = rows.get(0).get("id");
            if (idObj instanceof Number n) return n.longValue();
            return null;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.warn("定位功能开关记录失败, errorType={}", e.getClass().getSimpleName());
            return null;
        }
    }

    private Map<String, Map<String, Object>> normalizeConfig(List<Map<String, Object>> features) {
        Map<String, Map<String, Object>> result = new LinkedHashMap<>();
        for (Map<String, Object> f : features) {
            if (f == null) continue;
            String key = String.valueOf(f.getOrDefault("key", "")).trim();
            if (key.isEmpty()) continue;
            Map<String, Object> m = new LinkedHashMap<>();
            for (String level : LEVELS_ASC) {
                m.put(level, boolOr(f.get(level), true));
            }
            if (f.containsKey("title")) m.put("title", f.get("title"));
            if (f.containsKey("group")) m.put("group", f.get("group"));
            result.put(key, m);
        }
        return result;
    }

    /**
     * 等级判定：用户等级 >= 要求等级 则视为满足。
     * 未知等级一律视为 normal（最低）。
     */
    public boolean levelSatisfied(String userLevel, String requiredLevel) {
        int userWeight = weightOf(userLevel);
        int requiredWeight = weightOf(requiredLevel);
        return userWeight >= requiredWeight;
    }

    private int weightOf(String level) {
        if (level == null) return 0;
        String normalized = level.trim().toLowerCase(Locale.ROOT);
        if ("svip".equals(normalized)) normalized = "svp";
        Integer w = LEVEL_WEIGHT.get(normalized);
        return w == null ? 0 : w;
    }

    /**
     * 解析用户当前等级（委托 UserProfileService，与 currentUser 接口保持一致）。
     */
    public String resolveUserLevel(Long userId) {
        if (userId == null) return "normal";
        try {
            return userProfileService.currentPlanCode(userId);
        } catch (Exception e) {
            log.warn("解析用户等级失败，降级为 normal, userId={}, errorType={}", userId, e.getClass().getSimpleName());
            return "normal";
        }
    }

    private String normalizeLevel(String level) {
        if (level == null) return "normal";
        String s = level.trim().toLowerCase(Locale.ROOT);
        if (s.isEmpty()) return "normal";
        if ("svip".equals(s)) return "svp";
        if (!LEVEL_WEIGHT.containsKey(s)) return "normal";
        return s;
    }

    private boolean isDefaultKey(String key) {
        for (Map<String, Object> def : DEFAULT_FEATURES) {
            if (String.valueOf(def.get("key")).equals(key)) return true;
        }
        return false;
    }

    private static boolean boolOr(Object v, boolean fallback) {
        if (v == null) return fallback;
        if (v instanceof Boolean b) return b;
        String s = String.valueOf(v).trim().toLowerCase(Locale.ROOT);
        if (s.isEmpty()) return fallback;
        return "true".equals(s) || "1".equals(s) || "yes".equals(s) || "on".equals(s);
    }
}
