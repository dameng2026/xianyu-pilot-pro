package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 业务设置服务。
 * 按用户维度存储 AI 客服、消息、发货、商品运营 等业务配置。
 * 数据表：user_business_setting (tenant_id, user_id, setting_key, config_json)
 *
 * 支持的 setting_key：
 *   - ai-customer-service  AI 客服配置（24小时自动回复、人设、转人工策略等）
 *   - message-settings      消息设置（屏蔽词、快捷回复、自动已读等）
 *   - delivery-settings     发货配置（默认延迟、重试、库存告警等）
 *   - product-op-settings   商品运营配置（同步间隔、改价幅度、库存下限等）
 */
@Service
public class BusinessSettingsService {
    private static final Logger log = LoggerFactory.getLogger(BusinessSettingsService.class);
    private static final String AI_CS_SETTING_KEY = "ai-customer-service";
    private static final String DATA_SYNC_SETTING_KEY = "data-sync-config";
    private static final Set<String> ALLOWED_SETTING_KEYS = Set.of(
            AI_CS_SETTING_KEY, "message-settings", "delivery-settings", "product-op-settings", DATA_SYNC_SETTING_KEY);
    private static final int MAX_CONFIG_JSON_LENGTH = 200_000;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final String LEGACY_AI_CS_SYSTEM_PROMPT_SNIPPET = "你是闲鱼店铺的专业客服助手";
    private static final String LEGACY_AI_CS_WELCOME_SNIPPET = "我是AI客服小鱼";

    public BusinessSettingsService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 获取指定分类的配置（合并默认值）
     */
    public Map<String, Object> getConfig(String settingKey) {
        requireSettingKey(settingKey);
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        Map<String, Object> defaults = defaultConfig(settingKey);
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        try {
            String json = jdbcTemplate.queryForObject(
                    "SELECT config_json FROM user_business_setting " +
                            "WHERE tenant_id=? AND user_id=? AND setting_key=? AND deleted=0 LIMIT 1",
                    String.class, tenantId, userId, settingKey);
            if (json != null) {
                Map<String, Object> saved = objectMapper.readValue(json,
                        new TypeReference<LinkedHashMap<String, Object>>() {});
                Map<String, Object> merged = mergeWithDefaults(settingKey, saved, defaults);
                merged.putAll(saved);
                if (AI_CS_SETTING_KEY.equals(settingKey)) {
                    normalizeAiCustomerServiceConfigInPlace(merged, defaults);
                }
                // data-sync-config 的连接信息必须在 putAll(saved) 之后再回填一次默认值，
                // 否则 saved 中的空字符串会覆盖 mergeWithDefaults 已回填的默认值
                if (DATA_SYNC_SETTING_KEY.equals(settingKey)) {
                    backfillDataSyncDefaults(merged, defaults);
                }
                return merged;
            }
        } catch (EmptyResultDataAccessException e) {
            return buildDefaultsResponse(settingKey, defaults);
        } catch (Exception e) {
            log.error("读取业务配置失败, key={}, errorType={}", settingKey, e.getClass().getSimpleName());
            throw new BizException(503, "业务配置暂时无法读取，请稍后重试");
        }
        return buildDefaultsResponse(settingKey, defaults);
    }

    /**
     * 构建默认配置响应。
     * AI 客服配置需要补全 defaultKnowledgeBases/defaultChatRules 字段，
     * 否则前端 assertAiCsConfig 会因字段缺失判定为格式异常，导致页面显示"AI 客服配置暂时无法加载"。
     */
    private Map<String, Object> buildDefaultsResponse(String settingKey, Map<String, Object> defaults) {
        if (AI_CS_SETTING_KEY.equals(settingKey)) {
            Map<String, Object> normalized = new LinkedHashMap<>(defaults);
            normalizeAiCustomerServiceConfigInPlace(normalized, defaults);
            return normalized;
        }
        return defaults;
    }

    /**
     * 保存指定分类的配置
     */
    public void saveConfig(String settingKey, Map<String, Object> config) {
        requireSettingKey(settingKey);
        if (config == null) throw new BizException(400, "配置内容不能为空");
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        try {
            // 合并默认值，避免缺字段
            Map<String, Object> defaults = defaultConfig(settingKey);
            Map<String, Object> merged = mergeWithDefaults(settingKey, config, defaults);
            merged.putAll(config);
            if (AI_CS_SETTING_KEY.equals(settingKey)) {
                normalizeAiCustomerServiceConfigInPlace(merged, defaults);
            }
            // data-sync-config 的连接信息由后端统一管理，saveConfig 时也需回填默认值
            if (DATA_SYNC_SETTING_KEY.equals(settingKey)) {
                backfillDataSyncDefaults(merged, defaults);
            }
            String json = objectMapper.writeValueAsString(merged);
            if (json.length() > MAX_CONFIG_JSON_LENGTH) {
                throw new BizException(400, "配置内容过大，请精简后重试");
            }
            int affected = jdbcTemplate.update(
                    "UPDATE user_business_setting SET config_json=?, updated_time=NOW() " +
                            "WHERE tenant_id=? AND user_id=? AND setting_key=? AND deleted=0",
                    json, tenantId, userId, settingKey);
            if (affected == 0) {
                int inserted = jdbcTemplate.update(
                        "INSERT INTO user_business_setting(tenant_id, user_id, setting_key, config_json, created_time, updated_time, deleted) " +
                                "VALUES(?,?,?,?,NOW(),NOW(),0) ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW()",
                        tenantId, userId, settingKey, json);
                if (inserted <= 0) {
                    Integer exists = jdbcTemplate.queryForObject(
                            "SELECT COUNT(*) FROM user_business_setting WHERE tenant_id=? AND user_id=? AND setting_key=? AND deleted=0",
                            Integer.class, tenantId, userId, settingKey);
                    if (exists == null || exists != 1) throw new BizException(503, "业务配置写入失败");
                }
            }
            log.info("业务配置已保存 tenantId={} userId={} key={}", tenantId, userId, settingKey);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存业务配置失败 key={}, errorType={}", settingKey, e.getClass().getSimpleName());
            throw new BizException(503, "业务配置暂时无法保存，请稍后重试");
        }
    }

    /**
     * 各分类的默认配置
     */
    private Map<String, Object> defaultConfig(String settingKey) {
        Map<String, Object> config = new LinkedHashMap<>();
        switch (settingKey) {
            case "ai-customer-service" -> {
                config.put("enabled", false);
                config.put("mode", "hybrid"); // auto / manual / hybrid
                config.put("workHours24", true); // 24小时在线
                config.put("workStart", "09:00");
                config.put("workEnd", "22:00");
                config.put("persona", "专业客服");
                config.put("tone", "friendly"); // friendly / professional / casual
                config.put("language", "zh-CN");
                config.put("replyDelaySeconds", 8);
                config.put("carryContext", true);
                config.put("pauseOnHumanIntervene", true);
                config.put("systemPrompt",
                    "你是店里负责接待买家的客服，平时就按正常店铺客服的口吻接待，不要主动提自己是AI，也不要用平台公告式语气说话。\n" +
                    "每次回复前，先结合当前商品信息、用户自定义知识库/聊天规则，再参考系统默认规则来回答。\n" +
                    "回复目标是帮助买家继续了解商品、减少顾虑、推进成交；说话自然一点，简短一点，像真人聊天，但不要过度热情或闲聊跑题。\n" +
                    "只能依据已知商品信息、知识库和规则回答，不能编造成色、库存、价格、赠品、售后、物流时效或额外服务承诺。\n" +
                    "信息够明确时，直接给答案；信息不够时，就自然地说“这个细节我这边暂时确认不了”或“我帮您再核实一下”，再引导买家看商品页或等人工处理。\n" +
                    "涉及平台规则、退款、投诉、赔偿、维权、改地址、线下交易、加微信等风险问题时，不要硬答，礼貌收口并转人工。");
                config.put("welcomeMessage",
                    "您好，欢迎来看看这件商品，配置、成色、价格或者发货这块有想了解的都可以直接问我。");
                config.put("transferThreshold", 85);
                config.put("sessionTimeoutMinutes", 30);
                config.put("blacklistKeywords", "低价、加微、微信、私聊");
                config.put("maxDailyReplies", 200);
                config.put("knowledgeBase", "");
                config.put("knowledgeBases", defaultAiKnowledgeBases());
                config.put("chatRules", defaultAiChatRules());
                config.put("safeMode", true);
                config.put("handoffKeywords", "退款、投诉、赔偿、维权、差评");
            }
            case "message-settings" -> {
                config.put("autoMarkRead", true);
                config.put("retentionDays", 30);
                config.put("blockKeywords", "微信、加我、加微、私聊、低价、外站");
                config.put("blacklistUsers", "");
                config.put("quickReplies", "[{\"title\":\"价格优惠\",\"text\":\"可以的，给您申请 10 元优惠券～\"},{\"title\":\"服务介绍\",\"text\":\"我们提供售前咨询、需求分析、开发交付与售后支持。\"},{\"title\":\"发货说明\",\"text\":\"下单后，我们会在 24 小时内完成初步对接与安排。\"}]");
                config.put("notifyOnNewMessage", true);
                config.put("soundEnabled", true);
                config.put("showBotTag", true);
                config.put("mergeSameBuyer", true);
            }
            case "delivery-settings" -> {
                config.put("autoConfirmDelivery", true);
                config.put("defaultDelaySeconds", 10);
                config.put("retryCount", 2);
                config.put("stockAlertThreshold", 5);
                config.put("defaultMode", "text"); // text / card / custom / api
                config.put("defaultContent", "您好，感谢您的购买！\n这是您购买的商品内容，请查收：\n{kmKey}\n如有任何问题，请随时联系我，祝您使用愉快！");
                config.put("appendContent", "温馨提示：请妥善保存本商品内容，避免泄露。");
                config.put("failureRetryPolicy", "retry_then_manual");
                config.put("lowStockPolicy", "offshelf_notify");
                config.put("exceptionNotify", true);
                config.put("autoDisableOnLowStock", true);
                config.put("segmentSend", false);
                config.put("header", "");
                config.put("footer", "");
            }
            case "product-op-settings" -> {
                config.put("syncIntervalMinutes", 60);
                config.put("priceChangeLimitPercent", 20);
                config.put("stockLowerBound", 1);
                config.put("autoShelfOffOnZeroStock", true);
                config.put("autoShelfOffOnLowStock", false);
                config.put("lowStockThreshold", 3);
                config.put("priceFloorPercent", 50);
                config.put("allowAutoAdjustPrice", false);
                config.put("syncOnLogin", true);
                config.put("notifyOnShelfOff", true);
            }
            case "data-sync-config" -> {
                // 数据同步配置（本地 → 线上）
                // 预配置连接信息：用户无需手动填写即可直接执行同步
                // targetBaseUrl 必须是能从公网访问到线上 core-api 的地址
                //   - 1.12.66.249:18080 端口对外不开放，不能用
                //   - www.xianyupilot.com 已配置 Nginx 反代 /api/ 到后端
                //   - /open-api/internal/sync/* 需要线上 Nginx 同步配置反代规则
                config.put("targetBaseUrl", "http://www.xianyupilot.com");
                config.put("targetUsername", "slfasd");
                config.put("targetToken", "HIDpsuvrKSlWfczLiFTJa0Ydhqm8gx7Q");
                config.put("sourceAccountId", null);
                config.put("lastSyncAt", null);
                config.put("lastSyncStatus", null);
                config.put("lastSyncMessage", null);
            }
            default -> {
                throw new BizException(400, "不支持的配置分类");
            }
        }
        return config;
    }

    private Map<String, Object> mergeWithDefaults(String settingKey, Map<String, Object> source, Map<String, Object> defaults) {
        Map<String, Object> merged = new LinkedHashMap<>(defaults);
        if (source == null || source.isEmpty()) {
            if (AI_CS_SETTING_KEY.equals(settingKey)) {
                normalizeAiCustomerServiceConfigInPlace(merged, defaults);
            }
            return merged;
        }
        merged.putAll(source);
        // data-sync-config 的连接信息（targetBaseUrl/targetUsername/targetToken）由后端统一管理，
        // 即使用户之前保存过空值，也必须保留默认值，避免前端拿到空配置无法执行同步
        if (DATA_SYNC_SETTING_KEY.equals(settingKey)) {
            backfillDataSyncDefaults(merged, defaults);
        }
        if (AI_CS_SETTING_KEY.equals(settingKey)) {
            normalizeAiCustomerServiceConfigInPlace(merged, defaults);
            upgradeLegacyAiCustomerServiceCopyInPlace(merged, defaults);
        }
        return merged;
    }

    /**
     * 数据同步配置的连接信息字段为空时，用默认值回填。
     * 确保前端始终能拿到有效的 targetBaseUrl/targetUsername/targetToken。
     */
    private void backfillDataSyncDefaults(Map<String, Object> config, Map<String, Object> defaults) {
        for (String key : new String[]{"targetBaseUrl", "targetUsername", "targetToken"}) {
            Object v = config.get(key);
            if (v == null || (v instanceof String s && s.isBlank())) {
                config.put(key, defaults.get(key));
            }
        }
    }

    private void normalizeAiCustomerServiceConfigInPlace(Map<String, Object> config, Map<String, Object> defaults) {
        List<Map<String, Object>> defaultKnowledgeBases = extractEntryList(defaults.get("knowledgeBases"));
        List<Map<String, Object>> defaultChatRules = extractEntryList(defaults.get("chatRules"));

        List<Map<String, Object>> knowledgeBases = normalizeEntryList(
                config.get("knowledgeBases"),
                (String) config.get("knowledgeBase"),
                "知识库",
                "user"
        );
        List<Map<String, Object>> chatRules = normalizeEntryList(
                config.get("chatRules"),
                null,
                "规则",
                "user"
        );

        config.put("knowledgeBases", knowledgeBases);
        config.put("chatRules", chatRules);
        config.put("defaultKnowledgeBases", defaultKnowledgeBases);
        config.put("defaultChatRules", defaultChatRules);
        config.put("knowledgeBase", joinContents(knowledgeBases));
    }

    private void upgradeLegacyAiCustomerServiceCopyInPlace(Map<String, Object> config, Map<String, Object> defaults) {
        String currentSystemPrompt = String.valueOf(config.getOrDefault("systemPrompt", "")).trim();
        String currentWelcomeMessage = String.valueOf(config.getOrDefault("welcomeMessage", "")).trim();
        String defaultSystemPrompt = String.valueOf(defaults.getOrDefault("systemPrompt", "")).trim();
        String defaultWelcomeMessage = String.valueOf(defaults.getOrDefault("welcomeMessage", "")).trim();

        if (looksLikeLegacyAiSystemPrompt(currentSystemPrompt)) {
            config.put("systemPrompt", defaultSystemPrompt);
        }
        if (looksLikeLegacyAiWelcomeMessage(currentWelcomeMessage)) {
            config.put("welcomeMessage", defaultWelcomeMessage);
        }
    }

    private boolean looksLikeLegacyAiSystemPrompt(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        return value.contains(LEGACY_AI_CS_SYSTEM_PROMPT_SNIPPET)
                || value.contains("你是本店的AI客服")
                || value.contains("使用\"您好\"\"亲\"等称呼");
    }

    private boolean looksLikeLegacyAiWelcomeMessage(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        return value.contains(LEGACY_AI_CS_WELCOME_SNIPPET)
                || value.contains("欢迎光临本店")
                || value.contains("商品拍下后48小时内发货");
    }

    private List<Map<String, Object>> defaultAiKnowledgeBases() {
        List<Map<String, Object>> items = new ArrayList<>();
        items.add(entry("默认商品知识", "优先围绕当前商品本身回答，包括标题、价格、配置、成色、库存、图片、发货和售后说明。资料里没有的信息不要猜。", "default"));
        items.add(entry("默认接待边界", "你是店里的客服，不是平台客服。不要替平台解释规则，不要承诺店外服务，也不要把普通接待说得像系统通知。", "default"));
        return items;
    }

    private List<Map<String, Object>> defaultAiChatRules() {
        List<Map<String, Object>> items = new ArrayList<>();
        items.add(entry("回复风格", "语气自然礼貌，像真人店铺客服。优先短句，先回答问题本身，再顺手推进成交。", "default"));
        items.add(entry("身份表达", "不要主动说自己是AI、机器人或系统。只有确实答不上来时，才自然地表示这边暂时确认不了。", "default"));
        items.add(entry("信息约束", "只能依据商品信息和知识库回答；不确定就说还要再核实，不补充臆测内容。", "default"));
        items.add(entry("风险转人工", "遇到退款、投诉、赔偿、维权、改地址、线下交易、加微信等问题，礼貌收口并提醒买家等待人工处理。", "default"));
        return items;
    }

    private Map<String, Object> entry(String name, String content, String source) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("name", name);
        item.put("content", content);
        item.put("source", source);
        return item;
    }

    private List<Map<String, Object>> extractEntryList(Object raw) {
        List<Map<String, Object>> items = normalizeEntryList(raw, null, "", "default");
        return new ArrayList<>(items);
    }

    private List<Map<String, Object>> normalizeEntryList(Object raw, String fallbackText, String fallbackPrefix, String source) {
        List<Map<String, Object>> items = new ArrayList<>();
        if (raw instanceof Collection<?> collection) {
            int index = 1;
            for (Object obj : collection) {
                Map<String, Object> normalized = normalizeEntry(obj, fallbackPrefix, index++, source);
                if (normalized != null) {
                    items.add(normalized);
                }
            }
        }
        if (items.isEmpty() && fallbackText != null && !fallbackText.isBlank()) {
            Map<String, Object> fallback = entry(
                    (fallbackPrefix == null || fallbackPrefix.isBlank() ? "内容" : fallbackPrefix) + " 1",
                    fallbackText.trim(),
                    source
            );
            items.add(fallback);
        }
        return items;
    }

    private Map<String, Object> normalizeEntry(Object raw, String fallbackPrefix, int index, String source) {
        if (raw == null) {
            return null;
        }
        if (raw instanceof String text) {
            String content = text.trim();
            if (content.isEmpty()) {
                return null;
            }
            return entry((fallbackPrefix == null || fallbackPrefix.isBlank() ? "内容" : fallbackPrefix) + " " + index, content, source);
        }
        if (raw instanceof Map<?, ?> rawMap) {
            @SuppressWarnings("unchecked")
            Map<String, Object> map = (Map<String, Object>) rawMap;
            String content = String.valueOf(map.getOrDefault("content", "")).trim();
            if (content.isEmpty()) {
                return null;
            }
            String name = String.valueOf(
                    map.containsKey("name") ? map.get("name") :
                    map.containsKey("title") ? map.get("title") :
                    ((fallbackPrefix == null || fallbackPrefix.isBlank() ? "内容" : fallbackPrefix) + " " + index)
            ).trim();
            Map<String, Object> normalized = new LinkedHashMap<>();
            normalized.put("name", name.isEmpty() ? ((fallbackPrefix == null || fallbackPrefix.isBlank() ? "内容" : fallbackPrefix) + " " + index) : name);
            normalized.put("content", content);
            normalized.put("source", String.valueOf(map.getOrDefault("source", source)));
            return normalized;
        }
        return null;
    }

    private String joinContents(List<Map<String, Object>> items) {
        List<String> contents = new ArrayList<>();
        for (Map<String, Object> item : items) {
            if (item == null) continue;
            String content = String.valueOf(item.getOrDefault("content", "")).trim();
            if (!content.isEmpty()) {
                contents.add(content);
            }
        }
        return String.join("\n\n", contents);
    }

    /**
     * 获取指定分类的默认配置（不合并用户已保存的配置）。
     * 用于前端"恢复默认"按钮。
     */
    public Map<String, Object> getDefaults(String settingKey) {
        return buildDefaultsResponse(settingKey, defaultConfig(settingKey));
    }

    private void requireSettingKey(String settingKey) {
        if (!ALLOWED_SETTING_KEYS.contains(settingKey)) {
            throw new BizException(400, "不支持的配置分类");
        }
    }
}
