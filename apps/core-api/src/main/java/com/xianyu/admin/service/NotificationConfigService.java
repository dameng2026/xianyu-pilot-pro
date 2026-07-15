package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 通知配置服务（短信、邮件）。
 * 配置存储在 sys_config 表中，通过 JSON 格式序列化。
 */
@Service
public class NotificationConfigService {
    private static final Logger log = LoggerFactory.getLogger(NotificationConfigService.class);

    private static final String SMS_CONFIG_KEY = "sms_config";
    private static final String EMAIL_CONFIG_KEY = "email_config";

    private final JdbcTemplate jdbcTemplate;
    private final CookieCryptoService cryptoService;

    public NotificationConfigService(JdbcTemplate jdbcTemplate, CookieCryptoService cryptoService) {
        this.jdbcTemplate = jdbcTemplate;
        this.cryptoService = cryptoService;
    }

    // ==================== 短信配置 ====================

    @SuppressWarnings("unchecked")
    public Map<String, Object> getSmsConfig() {
        String json = getConfig(SMS_CONFIG_KEY);
        if (json == null) return defaultSmsConfig();
        try {
            // Simple JSON parsing - return as-is
            return publicConfig((Map<String, Object>) parseJson(json),
                    "accessKeySecret", "accessKeySecretConfigured");
        } catch (Exception e) {
            return defaultSmsConfig();
        }
    }

    public void saveSmsConfig(Map<String, Object> config) {
        Map<String, Object> secured = secureForStorage(
                config, SMS_CONFIG_KEY, "accessKeySecret", "clearAccessKeySecret");
        String json = toJson(secured);
        saveConfig(SMS_CONFIG_KEY, json);
        log.info("短信配置已保存");
    }

    public void testSms(String phone) {
        throw new BizException(503, "短信服务尚未接入真实供应商，未发送测试短信");
    }

    public void testEmail(String email) {
        if (!isEmailConfigured()) {
            throw new BizException(503, "邮件 SMTP 配置不完整，请先填写并保存邮箱配置");
        }
        throw new BizException(503, "邮件测试发送尚未接入真实供应商，未发送测试邮件");
    }

    private Map<String, Object> defaultSmsConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("provider", "aliyun");
        config.put("apiUrl", "https://dysmsapi.aliyuncs.com/");
        config.put("accessKeyId", "");
        config.put("accessKeySecret", "");
        config.put("signName", "");
        config.put("templateCode", "");
        config.put("templateParam", "{\"code\":\"${code}\"}");
        config.put("codeLength", 6);
        config.put("validSeconds", 300);
        config.put("sendInterval", 60);
        config.put("dailyLimit", 20);
        return config;
    }

    // ==================== 邮箱配置 ====================

    @SuppressWarnings("unchecked")
    public Map<String, Object> getEmailConfig() {
        String json = getConfig(EMAIL_CONFIG_KEY);
        if (json == null) return defaultEmailConfig();
        try {
            return publicConfig((Map<String, Object>) parseJson(json),
                    "password", "passwordConfigured");
        } catch (Exception e) {
            return defaultEmailConfig();
        }
    }

    public void saveEmailConfig(Map<String, Object> config) {
        Map<String, Object> secured = secureForStorage(
                config, EMAIL_CONFIG_KEY, "password", "clearPassword");
        String json = toJson(secured);
        saveConfig(EMAIL_CONFIG_KEY, json);
        log.info("邮箱配置已保存");
    }

    /** 返回完整邮件配置（含解密后的密码），供 EmailSenderService 内部使用。 */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getEmailConfigDecrypted() {
        String json = getConfig(EMAIL_CONFIG_KEY);
        if (json == null) return defaultEmailConfig();
        try {
            Map<String, Object> config = (Map<String, Object>) parseJson(json);
            String encryptedPassword = Objects.toString(config.get("password"), "").trim();
            if (!encryptedPassword.isBlank()) {
                config.put("password", cryptoService.decryptIfNeeded(encryptedPassword));
            }
            return config;
        } catch (Exception e) {
            return defaultEmailConfig();
        }
    }

    /** 判断后台邮件 SMTP 配置是否完整（主机、发件人、用户名、密码均非空）。 */
    public boolean isEmailConfigured() {
        Map<String, Object> config = getEmailConfigDecrypted();
        return isNonEmpty(config.get("smtpHost"))
                && isNonEmpty(config.get("fromEmail"))
                && isNonEmpty(config.get("username"))
                && isNonEmpty(config.get("password"));
    }

    private boolean isNonEmpty(Object value) {
        return value != null && !Objects.toString(value, "").trim().isBlank();
    }

    private Map<String, Object> defaultEmailConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("provider", "custom");
        config.put("smtpHost", "smtp.qq.com");
        config.put("smtpPort", 465);
        config.put("encryption", "ssl");
        config.put("fromEmail", "");
        config.put("fromName", "闲鱼助手");
        config.put("username", "");
        config.put("password", "");
        config.put("subject", "【闲鱼助手】验证码通知");
        config.put("template", "");
        config.put("codeLength", 6);
        config.put("validSeconds", 300);
        config.put("sendInterval", 60);
        config.put("dailyLimit", 20);
        return config;
    }

    private Map<String, Object> secureForStorage(Map<String, Object> incoming,
                                                  String configKey,
                                                  String secretKey,
                                                  String clearFlag) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (incoming != null) result.putAll(incoming);
        result.remove(secretKey + "Configured");

        boolean clear = Boolean.TRUE.equals(result.remove(clearFlag));
        String submitted = Objects.toString(result.get(secretKey), "").trim();
        if (clear) {
            result.put(secretKey, "");
            return result;
        }

        if (submitted.isBlank() || submitted.matches("\\*{4,}")) {
            Map<String, Object> existing = rawConfig(configKey);
            submitted = Objects.toString(existing.get(secretKey), "").trim();
        }
        if (submitted.isBlank()) {
            result.put(secretKey, "");
            return result;
        }

        String plainText = cryptoService.decryptIfNeeded(submitted);
        result.put(secretKey, cryptoService.encrypt(plainText));
        return result;
    }

    private Map<String, Object> publicConfig(Map<String, Object> stored,
                                              String secretKey,
                                              String configuredKey) {
        Map<String, Object> result = new LinkedHashMap<>(stored == null ? Map.of() : stored);
        String secret = Objects.toString(result.get(secretKey), "").trim();
        result.put(secretKey, "");
        result.put(configuredKey, !secret.isBlank());
        return result;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> rawConfig(String configKey) {
        String json = getConfig(configKey);
        if (json == null || json.isBlank()) return Map.of();
        try {
            Object parsed = parseJson(json);
            return parsed instanceof Map<?, ?> ? (Map<String, Object>) parsed : Map.of();
        } catch (RuntimeException e) {
            return Map.of();
        }
    }

    // ==================== 底层方法 ====================

    /** 从 sys_config 读取配置 JSON */
    private String getConfig(String configKey) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT config_value FROM sys_config WHERE config_key=? AND deleted=0 LIMIT 1",
                    String.class, configKey);
        } catch (Exception e) {
            return null;
        }
    }

    /** 保存配置到 sys_config */
    private void saveConfig(String configKey, String configValue) {
        int updated = jdbcTemplate.update(
                "UPDATE sys_config SET config_value=?, updated_time=NOW() WHERE config_key=? AND deleted=0",
                configValue, configKey);
        if (updated == 0) {
            jdbcTemplate.update(
                    "INSERT INTO sys_config(config_key, config_value, created_time, updated_time, deleted) VALUES(?, ?, NOW(), NOW(), 0)",
                    configKey, configValue);
        }
    }

    /** 简单 JSON 序列化（不依赖第三方库） */
    private String toJson(Map<String, Object> map) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            if (!first) sb.append(",");
            sb.append("\"").append(escapeJson(entry.getKey())).append("\":");
            sb.append(toJsonValue(entry.getValue()));
            first = false;
        }
        sb.append("}");
        return sb.toString();
    }

    private String toJsonValue(Object value) {
        if (value == null) return "null";
        if (value instanceof String s) return "\"" + escapeJson(s) + "\"";
        if (value instanceof Number) return value.toString();
        if (value instanceof Boolean) return value.toString();
        return "\"" + escapeJson(value.toString()) + "\"";
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }

    /** 简单 JSON 反序列化 */
    private Object parseJson(String json) {
        json = json.trim();
        if (json.startsWith("{")) {
            Map<String, Object> map = new LinkedHashMap<>();
            // Remove outer braces
            String content = json.substring(1, json.length() - 1).trim();
            if (content.isEmpty()) return map;

            List<String> pairs = splitJson(content);
            for (String pair : pairs) {
                int colonIdx = pair.indexOf(':');
                if (colonIdx < 0) continue;
                String key = stripQuotes(pair.substring(0, colonIdx).trim());
                String value = pair.substring(colonIdx + 1).trim();
                map.put(key, parseJsonValue(value));
            }
            return map;
        }
        return json;
    }

    private List<String> splitJson(String content) {
        List<String> result = new ArrayList<>();
        int depth = 0;
        boolean inString = false;
        int start = 0;
        for (int i = 0; i < content.length(); i++) {
            char c = content.charAt(i);
            if (c == '"') {
                // Check for escaped quote
                if (i > 0 && content.charAt(i - 1) == '\\') continue;
                inString = !inString;
            } else if (!inString) {
                if (c == '{' || c == '[') depth++;
                else if (c == '}' || c == ']') depth--;
                else if (c == ',' && depth == 0) {
                    result.add(content.substring(start, i).trim());
                    start = i + 1;
                }
            }
        }
        if (start < content.length()) {
            result.add(content.substring(start).trim());
        }
        return result;
    }

    private String stripQuotes(String s) {
        if (s.startsWith("\"") && s.endsWith("\"")) {
            return s.substring(1, s.length() - 1).replace("\\\"", "\"");
        }
        return s;
    }

    private Object parseJsonValue(String value) {
        if (value.equals("null")) return null;
        if (value.equals("true")) return true;
        if (value.equals("false")) return false;
        if (value.startsWith("\"") && value.endsWith("\"")) {
            return stripQuotes(value);
        }
        try {
            if (value.contains(".")) return Double.parseDouble(value);
            return Long.parseLong(value);
        } catch (NumberFormatException e) {
            return value;
        }
    }
}
