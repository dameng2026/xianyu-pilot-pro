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

    // ===================== 限制模式常量 =====================
    /** 限制模式：无限制（默认，正常使用） */
    public static final String LIMIT_MODE_NONE = "none";
    /** 限制模式：预览模式（可进入页面查看，但不可执行业务操作/发送业务请求） */
    public static final String LIMIT_MODE_PREVIEW = "preview";
    /** 限制模式：不可进入（直接无法访问该页面） */
    public static final String LIMIT_MODE_BLOCKED = "blocked";
    /** 支持的限制模式集合（单选，互斥） */
    private static final Set<String> VALID_LIMIT_MODES = Set.of(LIMIT_MODE_NONE, LIMIT_MODE_PREVIEW, LIMIT_MODE_BLOCKED);
    /** 预览模式默认提示文案 */
    private static final String DEFAULT_PREVIEW_MESSAGE = "该功能当前为预览模式，可查看内容但不可执行业务操作";
    /** 不可进入模式默认提示文案 */
    private static final String DEFAULT_BLOCKED_MESSAGE = "该功能当前不可访问";

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
        list.add(feature("refunds", "退款管理", "account", true, true, true));
        list.add(feature("rates", "评价管理", "account", true, true, true));
        list.add(feature("product-publish", "商品发布", "account", true, true, true));
        // 鱼小铺专属编辑页：由商品列表「编辑」按钮进入，仅鱼小铺账号商品可访问
        list.add(feature("fish-shop-edit", "鱼小铺编辑", "account", true, true, true));
        // 数据分析（账号维度子页面）
        list.add(feature("goods-data", "商品数据分析", "account", true, true, true));
        list.add(feature("fish-shop-data", "鱼小铺数据分析", "account", true, true, true));
        // 商品改价、评价管理-自动评价
        list.add(feature("product-price-edit", "商品改价", "account", true, true, true));
        list.add(feature("auto-rate", "评价管理-自动评价", "account", true, true, true));
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
        // 系统设置：
        //   - 滑块求解记录页：默认全开（仅控制记录页可见性，与求解动作解耦）
        //   - 手动滑块求解：仅 VIP 及以上可用（AccountsPage 求解按钮）
        //   - 自动滑块求解：仅 VIP 及以上可用（Python 被动自动求解）
        list.add(feature("logs", "操作日志", "system", true, true, true));
        list.add(feature("slider-solve-records", "滑块求解记录", "system", true, true, true));
        list.add(feature("manual-slider-solve", "手动滑块求解", "system", false, true, true));
        list.add(feature("auto-slider-solve", "自动滑块求解", "system", false, true, true));
        list.add(feature("api-slider-solve", "API滑块求解", "system", true, true, true));
        list.add(feature("feedback", "反馈建议", "system", true, true, true));
        list.add(feature("settings-notify", "通知设置", "system", true, true, true));
        list.add(feature("settings-ai-cs", "AI客服配置", "system", true, true, true));
        list.add(feature("learning-kb", "学习知识库", "system", true, true, true));
        list.add(feature("settings-about", "关于", "system", true, true, true));
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
        m.put("maintenance", false);  // 维护开关：默认关闭，开启后所有用户进入该页面均弹窗拦截
        m.put("limitMode", LIMIT_MODE_NONE);  // 限制模式：默认无限制（none/preview/blocked 单选）
        return m;
    }

    /** 支持关闭原因（reason）的功能 key 集合。其他功能项忽略 reason 字段。 */
    private static final Set<String> REASON_SUPPORTED_KEYS = Set.of("manual-slider-solve");

    /** reason 字段默认值（管理员未填写时使用） */
    private static final String DEFAULT_MANUAL_REASON = "您的会员等级未开启手动滑块求解功能";

    /** 维护模式默认提示文案（reason=maintenance 时返回给前端弹窗） */
    private static final String DEFAULT_MAINTENANCE_MESSAGE = "该页面正在维护升级中，请稍后再试";

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
                // 维护开关：所有功能均支持，合并存储覆盖值
                if (override.containsKey("maintenance")) {
                    merged.put("maintenance", boolOr(override.get("maintenance"), false));
                }
                // 限制模式：所有功能均支持，合并存储覆盖值
                if (override.containsKey("limitMode")) {
                    merged.put("limitMode", normalizeLimitMode(override.get("limitMode")));
                }
                // 仅 REASON_SUPPORTED_KEYS 中的功能保留 reason 字段
                if (REASON_SUPPORTED_KEYS.contains(key) && override.containsKey("reason")) {
                    merged.put("reason", sanitizeReason(String.valueOf(override.get("reason"))));
                }
            }
            // REASON_SUPPORTED_KEYS 中的功能始终返回 reason 字段（即使为空）
            if (REASON_SUPPORTED_KEYS.contains(key) && !merged.containsKey("reason")) {
                merged.put("reason", "");
            }
            // 确保所有功能都返回 maintenance 字段（默认 false）
            if (!merged.containsKey("maintenance")) merged.put("maintenance", false);
            // 确保所有功能都返回 limitMode 字段（默认 none）
            if (!merged.containsKey("limitMode")) merged.put("limitMode", LIMIT_MODE_NONE);
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
            if (!extra.containsKey("maintenance")) extra.put("maintenance", false);
            if (!extra.containsKey("limitMode")) extra.put("limitMode", LIMIT_MODE_NONE);
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
     *     "blocked": { "<pageKey>": { "reason": "disabled|level|maintenance|blocked", "required_level": "vip", "reason_text"?: "..." } },
     *     "preview": { "<pageKey>": { "reason": "preview", "reason_text": "..." } }
     *   }
     *
     * 判定逻辑（按优先级）：
     *   1. 维护开关 maintenance=true → 所有用户拦截，reason=maintenance
     *   2. 限制模式 limitMode=blocked → 不可进入，reason=blocked
     *   3. 用户等级对应的开关为 false：
     *     - 存在更高级别开关为 true → reason=level, required_level=第一个开启的更高级别
     *     - 所有级别都为 false → reason=disabled
     *   4. 用户等级对应的开关为 true：
     *     - limitMode=preview → 可进入页面但预览模式（不可执行业务操作），记入 preview map
     *     - limitMode=none → 正常访问
     */
    public Map<String, Object> getStatusForCurrentUser(Long userId) {
        Map<String, Object> status = new LinkedHashMap<>();
        String userLevel = resolveUserLevel(userId);
        status.put("level", userLevel);

        Map<String, Map<String, Object>> stored = loadStoredFeatures();
        Map<String, Boolean> accessible = new LinkedHashMap<>();
        Map<String, Map<String, Object>> blocked = new LinkedHashMap<>();
        Map<String, Map<String, Object>> preview = new LinkedHashMap<>();

        for (Map<String, Object> def : DEFAULT_FEATURES) {
            String key = String.valueOf(def.get("key"));
            // 1. 维护开关优先级最高：开启时对所有等级用户拦截
            if (resolveMaintenance(key, def, stored)) {
                accessible.put(key, false);
                Map<String, Object> info = new LinkedHashMap<>();
                info.put("reason", "maintenance");
                info.put("required_level", normalizeLevel(userLevel));
                info.put("reason_text", DEFAULT_MAINTENANCE_MESSAGE);
                blocked.put(key, info);
                continue;
            }
            // 2. 限制模式=不可进入：对所有用户拦截（语义为管理员主动限制不可访问）
            String limitMode = resolveLimitMode(key, def, stored);
            if (LIMIT_MODE_BLOCKED.equals(limitMode)) {
                accessible.put(key, false);
                Map<String, Object> info = new LinkedHashMap<>();
                info.put("reason", "blocked");
                info.put("required_level", normalizeLevel(userLevel));
                info.put("reason_text", DEFAULT_BLOCKED_MESSAGE);
                blocked.put(key, info);
                continue;
            }
            // 3. 等级开关判定
            Map<String, Boolean> levelSwitches = resolveLevelSwitches(key, def, stored);

            boolean userAllowed = boolOr(levelSwitches.get(normalizeLevel(userLevel)), true);
            if (!userAllowed) {
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
                // 对于支持 reason 的功能（如 manual-slider-solve），返回管理员填写的关闭原因
                // 没填写时返回系统默认文案，便于前端弹窗展示
                if (REASON_SUPPORTED_KEYS.contains(key)) {
                    String reasonText = resolveReasonText(key, def, stored);
                    info.put("reason_text", reasonText);
                }
                blocked.put(key, info);
                continue;
            }
            // 4. 用户等级允许访问
            accessible.put(key, true);
            // 限制模式=预览：可进入页面但不可执行业务操作
            if (LIMIT_MODE_PREVIEW.equals(limitMode)) {
                Map<String, Object> info = new LinkedHashMap<>();
                info.put("reason", "preview");
                info.put("reason_text", DEFAULT_PREVIEW_MESSAGE);
                preview.put(key, info);
            }
        }
        status.put("accessible", accessible);
        status.put("blocked", blocked);
        status.put("preview", preview);
        return status;
    }

    /**
     * 查询单个功能对当前用户的拦截信息。
     * 返回：
     *   allowed=true, preview=false → 该功能对当前用户允许使用（正常模式）
     *   allowed=true, preview=true  → 该功能对当前用户允许进入但预览模式（不可执行业务操作）
     *   allowed=false → 该功能被拦截，附带 {reason, required_level, reason_text}
     *
     * 用于 Java 网关在 captcha/handle 入口校验 manual-slider-solve。
     */
    public Map<String, Object> getFeatureStatusForUser(Long userId, String featureKey) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("feature_key", featureKey);
        if (featureKey == null || featureKey.isBlank()) {
            result.put("allowed", true);  // 未知 key 默认放行，避免锁死
            result.put("preview", false);
            return result;
        }
        String userLevel = resolveUserLevel(userId);
        Map<String, Object> def = findDefaultFeature(featureKey);
        if (def == null) {
            result.put("allowed", true);  // 非预置功能默认放行
            result.put("preview", false);
            return result;
        }
        Map<String, Map<String, Object>> stored;
        try {
            stored = loadStoredFeatures();
        } catch (Exception e) {
            log.warn("getFeatureStatusForUser 读取存储配置失败，降级放行 featureKey={}", featureKey);
            result.put("allowed", true);
            result.put("preview", false);
            return result;
        }
        // 1. 维护开关优先级最高：开启时对所有等级用户拦截
        if (resolveMaintenance(featureKey, def, stored)) {
            result.put("allowed", false);
            result.put("preview", false);
            result.put("reason", "maintenance");
            result.put("required_level", normalizeLevel(userLevel));
            result.put("reason_text", DEFAULT_MAINTENANCE_MESSAGE);
            return result;
        }
        // 2. 限制模式=不可进入：对所有用户拦截
        String limitMode = resolveLimitMode(featureKey, def, stored);
        if (LIMIT_MODE_BLOCKED.equals(limitMode)) {
            result.put("allowed", false);
            result.put("preview", false);
            result.put("reason", "blocked");
            result.put("required_level", normalizeLevel(userLevel));
            result.put("reason_text", DEFAULT_BLOCKED_MESSAGE);
            return result;
        }
        // 3. 等级开关判定
        Map<String, Boolean> levelSwitches = resolveLevelSwitches(featureKey, def, stored);
        boolean userAllowed = boolOr(levelSwitches.get(normalizeLevel(userLevel)), true);
        if (!userAllowed) {
            result.put("allowed", false);
            result.put("preview", false);
            String firstHigherOn = findFirstHigherEnabled(userLevel, levelSwitches);
            if (firstHigherOn != null) {
                result.put("reason", "level");
                result.put("required_level", firstHigherOn);
            } else {
                result.put("reason", "disabled");
                result.put("required_level", normalizeLevel(userLevel));
            }
            if (REASON_SUPPORTED_KEYS.contains(featureKey)) {
                result.put("reason_text", resolveReasonText(featureKey, def, stored));
            }
            return result;
        }
        // 4. 用户等级允许访问
        result.put("allowed", true);
        // 限制模式=预览：可进入但不可执行业务操作
        result.put("preview", LIMIT_MODE_PREVIEW.equals(limitMode));
        if (LIMIT_MODE_PREVIEW.equals(limitMode)) {
            result.put("reason_text", DEFAULT_PREVIEW_MESSAGE);
        }
        return result;
    }

    /** 解析某功能的 reason_text：管理员填写 > 系统默认文案 */
    private String resolveReasonText(String key, Map<String, Object> def, Map<String, Map<String, Object>> stored) {
        Map<String, Object> override = stored.get(key);
        if (override != null && override.containsKey("reason")) {
            String r = String.valueOf(override.get("reason")).trim();
            if (!r.isEmpty() && !"null".equals(r)) return r;
        }
        return DEFAULT_MANUAL_REASON;
    }

    private Map<String, Object> findDefaultFeature(String key) {
        for (Map<String, Object> def : DEFAULT_FEATURES) {
            if (String.valueOf(def.get("key")).equals(key)) return def;
        }
        return null;
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
            f.put("maintenance", false);
            f.put("limitMode", LIMIT_MODE_NONE);
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
     * 解析某功能的维护开关状态（合并默认值与存储覆盖）。
     * 维护开关开启时，对所有等级用户拦截，优先级高于等级开关。
     */
    private boolean resolveMaintenance(String key, Map<String, Object> def, Map<String, Map<String, Object>> stored) {
        boolean val = boolOr(def.get("maintenance"), false);
        Map<String, Object> override = stored.get(key);
        if (override != null && override.containsKey("maintenance")) {
            val = boolOr(override.get("maintenance"), val);
        }
        return val;
    }

    /**
     * 解析某功能的限制模式（合并默认值与存储覆盖）。
     * 限制模式优先级：maintenance > limitMode=blocked > 等级开关 > limitMode=preview
     * - none：无限制（默认，正常使用）
     * - preview：预览模式（可进入页面查看，但不可执行业务操作/发送业务请求）
     * - blocked：不可进入模式（直接无法访问该页面）
     */
    private String resolveLimitMode(String key, Map<String, Object> def, Map<String, Map<String, Object>> stored) {
        String val = normalizeLimitMode(def.get("limitMode"));
        Map<String, Object> override = stored.get(key);
        if (override != null && override.containsKey("limitMode")) {
            val = normalizeLimitMode(override.get("limitMode"));
        }
        return val;
    }

    /**
     * 规范化限制模式值：非法值统一降级为 none。
     */
    private String normalizeLimitMode(Object v) {
        if (v == null) return LIMIT_MODE_NONE;
        String s = String.valueOf(v).trim().toLowerCase(Locale.ROOT);
        if (VALID_LIMIT_MODES.contains(s)) return s;
        return LIMIT_MODE_NONE;
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
            // 维护开关：所有功能均支持持久化
            m.put("maintenance", boolOr(f.get("maintenance"), false));
            // 限制模式：所有功能均支持持久化（none/preview/blocked 单选）
            m.put("limitMode", normalizeLimitMode(f.get("limitMode")));
            // 仅 REASON_SUPPORTED_KEYS 中的功能保留 reason 字段
            if (REASON_SUPPORTED_KEYS.contains(key)) {
                Object reasonVal = f.get("reason");
                m.put("reason", sanitizeReason(reasonVal == null ? "" : String.valueOf(reasonVal)));
            }
            result.put(key, m);
        }
        return result;
    }

    /**
     * reason 字段清洗：去首尾空白，截断到 200 字符，移除潜在的 HTML/脚本标签。
     * 防止管理员输入富文本导致前端展示时 XSS。
     */
    private static String sanitizeReason(String input) {
        if (input == null) return "";
        String s = input.trim();
        if (s.isEmpty()) return "";
        if (s.length() > 200) s = s.substring(0, 200);
        // 移除 < > 标签，防止 XSS（前端用 v-text 或 textarea 渲染，但保险起见后端也清洗）
        s = s.replaceAll("<[^>]+>", "");
        return s;
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
