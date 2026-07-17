package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Reads admin model configuration from admin_module_record.
 * Model configuration is maintained in admin-web -> 模型配置 and is the source of truth
 * for frontend AI rewrite and image generation feature switches.
 */
@Service
public class ModelConfigService {
    private static final Logger log = LoggerFactory.getLogger(ModelConfigService.class);
    public static final String GENERAL = "model-config-general";
    public static final String IMAGE = "model-config-image";
    public static final String IMAGE_2 = "model-config-image-2";
    public static final String IMAGE_3 = "model-config-image-3";
    public static final String CHAT = "model-config-chat";
    public static final String PROMPT = "model-config-image-prompts";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final SensitiveWordService sensitiveWordService;

    public ModelConfigService(JdbcTemplate jdbcTemplate, SensitiveWordService sensitiveWordService) {
        this.jdbcTemplate = jdbcTemplate;
        this.sensitiveWordService = sensitiveWordService;
    }

    public Map<String, Object> getConfig(String moduleKey) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id,status,json_text,updated_time FROM admin_module_record " +
                            "WHERE module_key=? AND deleted=0 ORDER BY id DESC LIMIT 1",
                    moduleKey
            );
            if (rows.isEmpty()) return new LinkedHashMap<>();
            Map<String, Object> row = rows.get(0);
            Map<String, Object> cfg = new LinkedHashMap<>();
            Object json = row.get("json_text");
            if (json != null && !String.valueOf(json).isBlank()) {
                cfg.putAll(objectMapper.readValue(String.valueOf(json), new TypeReference<LinkedHashMap<String, Object>>() {}));
            }
            cfg.put("id", row.get("id"));
            cfg.putIfAbsent("status", row.get("status"));
            return cfg;
        } catch (Exception error) {
            log.error("load model configuration failed moduleKey={} errorType={}",
                    moduleKey, error.getClass().getSimpleName());
            throw new BizException(503, "AI 模型配置暂时无法读取，请稍后重试");
        }
    }

    public Map<String, Object> getGeneralConfig() {
        return getConfig(GENERAL);
    }

    public Map<String, Object> getImageConfig() {
        Map<String, Object> image = getConfig(IMAGE);
        Map<String, Object> general = getGeneralConfig();
        // Image config may intentionally inherit Base URL / API Key from general config.
        copyIfBlank(image, general, "baseUrl");
        copyIfBlank(image, general, "apiKey");
        return image;
    }

    public boolean isEnabled(Map<String, Object> cfg) {
        if (cfg == null || cfg.isEmpty()) return false;
        Object enabled = cfg.get("enabled");
        Object status = cfg.get("status");
        if (enabled != null && ("false".equalsIgnoreCase(String.valueOf(enabled)) || "0".equals(String.valueOf(enabled)))) return false;
        if (status != null) {
            String s = String.valueOf(status).trim();
            if ("禁用".equals(s) || "0".equals(s) || "false".equalsIgnoreCase(s)) return false;
        }
        return true;
    }

    public boolean isGeneralTextConfigured() {
        Map<String, Object> cfg = getGeneralConfig();
        return isEnabled(cfg) && hasText(first(cfg, "baseUrl")) && hasText(first(cfg, "apiKey")) && hasText(first(cfg, "defaultModel", "modelName", "model"));
    }

    public boolean isImageConfigured() {
        Map<String, Object> cfg = getImageConfig();
        return isEnabled(cfg) && hasText(first(cfg, "baseUrl")) && hasText(first(cfg, "apiKey")) && hasText(first(cfg, "modelName", "defaultModel", "model"));
    }

    /**
     * 构建润色强限制提示词片段。
     *
     * 三个来源按顺序合并到禁止词列表（去重保序）：
     *   1) 默认禁止词「盗版、破解版、毕设」（始终生效）
     *   2) 通用模型配置中的「polishForbiddenKeywords」（管理员在模型配置中维护）
     *   3) 后台「敏感词策略」模块中 scene=polish 或 scene=all 的敏感词
     *
     * 必含词仅来自通用模型配置的「polishKeywords」。
     * 前台用户不可见、不可改。返回可直接拼接到 system prompt 的字符串；无任何限制时返回空字符串。
     */
    public String buildPolishRestriction() {
        Map<String, Object> cfg = getGeneralConfig();
        // 默认禁止词始终生效
        List<String> forbidden = new ArrayList<>(List.of("盗版", "破解版", "毕设"));
        List<String> required = new ArrayList<>();

        Object rawForbidden = cfg.get("polishForbiddenKeywords");
        if (rawForbidden != null) {
            String s = String.valueOf(rawForbidden).trim();
            if (!s.isBlank() && !"null".equalsIgnoreCase(s)) {
                for (String kw : s.split("[,\\n\\r，、\\s]+")) {
                    String k = kw.trim();
                    if (!k.isEmpty() && !forbidden.contains(k)) forbidden.add(k);
                }
            }
        }

        // 追加后台「敏感词策略」中 scene=polish 或 scene=all 的敏感词
        try {
            for (String w : sensitiveWordService.listWordsByScene(SensitiveWordService.SCENE_POLISH)) {
                if (!forbidden.contains(w)) forbidden.add(w);
            }
        } catch (Exception e) {
            log.warn("append sensitive words to polish restriction failed errorType={}",
                    e.getClass().getSimpleName());
        }

        Object rawRequired = cfg.get("polishKeywords");
        if (rawRequired != null) {
            String s = String.valueOf(rawRequired).trim();
            if (!s.isBlank() && !"null".equalsIgnoreCase(s)) {
                for (String kw : s.split("[,\\n\\r，、\\s]+")) {
                    String k = kw.trim();
                    if (!k.isEmpty() && !required.contains(k)) required.add(k);
                }
            }
        }

        StringBuilder sb = new StringBuilder();
        if (!required.isEmpty()) {
            sb.append("【必须包含的关键词】润色结果（标题和正文）中必须出现以下关键词：")
              .append(String.join("、", required)).append('\n');
        }
        if (!forbidden.isEmpty()) {
            sb.append("【绝对禁止的关键词】润色结果（标题和正文）中绝对不得出现以下关键词及其变体：")
              .append(String.join("、", forbidden))
              .append("。若生成内容包含这些词，必须立即重新生成，确保完全不含。");
        }
        return sb.toString().trim();
    }

    public List<Map<String, Object>> getAllImageConfigs() {
        List<Map<String, Object>> configs = new ArrayList<>();
        List<String> keys = List.of(IMAGE, IMAGE_2, IMAGE_3);
        Map<String, Object> general = getGeneralConfig();
        for (String key : keys) {
            Map<String, Object> cfg = getConfig(key);
            copyIfBlank(cfg, general, "baseUrl");
            copyIfBlank(cfg, general, "apiKey");
            cfg.put("moduleKey", key);
            configs.add(cfg);
        }
        return configs;
    }

    public List<Map<String, Object>> getEnabledImageConfigs() {
        List<Map<String, Object>> all = getAllImageConfigs();
        List<Map<String, Object>> enabled = new ArrayList<>();
        for (Map<String, Object> cfg : all) {
            if (isEnabled(cfg)) {
                enabled.add(cfg);
            }
        }
        return enabled;
    }

    public Map<String, Object> getImageConfigByKey(String modelKey) {
        if (!List.of(IMAGE, IMAGE_2, IMAGE_3).contains(modelKey)) {
            return getImageConfig();
        }
        Map<String, Object> cfg = getConfig(modelKey);
        Map<String, Object> general = getGeneralConfig();
        copyIfBlank(cfg, general, "baseUrl");
        copyIfBlank(cfg, general, "apiKey");
        return cfg;
    }

    public List<Map<String, Object>> getImagePromptConfigs() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id,status,json_text,updated_time FROM admin_module_record " +
                            "WHERE module_key=? AND deleted=0 ORDER BY id ASC",
                    PROMPT
            );
            List<Map<String, Object>> result = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Map<String, Object> cfg = new LinkedHashMap<>();
                Object json = row.get("json_text");
                if (json != null && !String.valueOf(json).isBlank()) {
                    cfg.putAll(objectMapper.readValue(String.valueOf(json), new TypeReference<LinkedHashMap<String, Object>>() {}));
                }
                cfg.put("id", row.get("id"));
                cfg.putIfAbsent("status", row.get("status"));
                result.add(cfg);
            }
            result.sort(Comparator
                    .comparingLong((Map<String, Object> cfg) -> longConfig(cfg, Long.MAX_VALUE, "sortOrder", "sort"))
                    .thenComparingLong(cfg -> longConfig(cfg, Long.MAX_VALUE, "id")));
            return result;
        } catch (Exception error) {
            log.error("load image prompt configuration failed errorType={}",
                    error.getClass().getSimpleName());
            throw new BizException(503, "生图提示词配置暂时无法读取，请稍后重试");
        }
    }

    public List<Map<String, Object>> getEnabledImagePromptConfigs() {
        List<Map<String, Object>> enabled = new ArrayList<>();
        for (Map<String, Object> cfg : getImagePromptConfigs()) {
            if (isEnabled(cfg)) {
                enabled.add(cfg);
            }
        }
        return enabled;
    }

    public Map<String, Object> matchImagePromptCategory(String title, String description, List<Map<String, Object>> promptConfigs) {
        String text = (textOrEmpty(title) + " " + textOrEmpty(description)).toLowerCase();
        Map<String, Object> best = null;
        int bestScore = 0;
        for (Map<String, Object> cfg : promptConfigs) {
            String keywords = textOrEmpty(first(cfg, "matchKeywords", "keywords", "matchs"));
            if (keywords.isBlank()) continue;
            int score = 0;
            for (String rawKeyword : keywords.split("[,，\\n\\r\\s]+")) {
                String keyword = rawKeyword.trim().toLowerCase();
                if (keyword.isEmpty()) continue;
                if (text.contains(keyword)) {
                    score += Math.max(2, keyword.length());
                }
            }
            if (score > bestScore) {
                bestScore = score;
                best = cfg;
            }
        }
        return bestScore > 0 ? best : null;
    }

    public String resolveImagePrompt(String promptMode,
                                     String customPrompt,
                                     String fallbackPrompt,
                                     String title,
                                     String description,
                                     List<Map<String, Object>> promptConfigs) {
        String mode = textOrEmpty(promptMode).trim().toLowerCase();
        if ("custom".equals(mode) && hasText(customPrompt)) {
            return renderImagePromptTemplate(customPrompt, title, description);
        }
        Map<String, Object> matched = matchImagePromptCategory(title, description, promptConfigs);
        if (matched != null) {
            String template = textOrEmpty(first(matched, "promptTemplate", "template", "prompt"));
            if (!template.isBlank()) {
                return renderImagePromptTemplate(template, title, description);
            }
        }
        return renderImagePromptTemplate(fallbackPrompt, title, description);
    }

    public String renderImagePromptTemplate(String template, String title, String description) {
        String raw = textOrEmpty(template);
        if (raw.isBlank()) return "";
        return raw.replace("{{TITLE}}", textOrEmpty(title).trim())
                .replace("{{CONTENT}}", truncateText(textOrEmpty(description).trim(), 3000))
                .trim();
    }

    public String textConfig(Map<String, Object> cfg, String fallback, String... keys) {
        Object v = first(cfg, keys);
        String s = v == null ? "" : String.valueOf(v).trim();
        return s.isBlank() ? fallback : s;
    }

    public long longConfig(Map<String, Object> cfg, long fallback, String... keys) {
        Object v = first(cfg, keys);
        if (v == null || String.valueOf(v).isBlank()) return fallback;
        try { return Long.parseLong(String.valueOf(v).replaceAll("[^0-9-]", "")); }
        catch (Exception ignored) { return fallback; }
    }

    public double doubleConfig(Map<String, Object> cfg, double fallback, String... keys) {
        Object v = first(cfg, keys);
        if (v == null || String.valueOf(v).isBlank()) return fallback;
        try { return Double.parseDouble(String.valueOf(v)); }
        catch (Exception ignored) { return fallback; }
    }

    public Object first(Map<String, Object> cfg, String... keys) {
        if (cfg == null) return null;
        for (String k : keys) if (cfg.containsKey(k)) return cfg.get(k);
        return null;
    }

    private void copyIfBlank(Map<String, Object> target, Map<String, Object> source, String key) {
        if (!hasText(target.get(key)) && hasText(source.get(key))) target.put(key, source.get(key));
    }

    private boolean hasText(Object v) {
        return v != null && !String.valueOf(v).trim().isBlank();
    }

    private String textOrEmpty(Object v) {
        return v == null ? "" : String.valueOf(v);
    }

    private String truncateText(String text, int max) {
        if (text == null) return "";
        return text.length() <= max ? text : text.substring(0, max);
    }
}
