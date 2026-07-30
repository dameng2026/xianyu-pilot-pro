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
        // 实际发送由 EmailSenderService.sendTestEmail 处理，本方法仅保留接口占位。
        // 实现细节见 EmailSenderService，根据当前 provider 路由到 SMTP 或腾讯云 SES。
        if (!isEmailConfigured()) {
            throw new BizException(503, "邮件配置不完整，请先填写并保存邮箱配置");
        }
        // 由 EmailSenderService 完成实际发送，此处不再抛出"未接入"错误。
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
            Map<String, Object> stored = (Map<String, Object>) parseJson(json);
            return publicEmailConfig(stored);
        } catch (Exception e) {
            return defaultEmailConfig();
        }
    }

    public void saveEmailConfig(Map<String, Object> config) {
        // 同时处理 SMTP 密码与腾讯云 SES SecretKey 两个敏感字段
        Map<String, Object> secured = secureForStorage(
                config, EMAIL_CONFIG_KEY, "password", "clearPassword");
        secured = secureForStorage(
                secured, EMAIL_CONFIG_KEY, "tencentSecretKey", "clearTencentSecretKey");
        // SecretId 也视为敏感字段：保存时若提交明文则原样保存（不加密），
        // 留空且未勾选清除时保留已有值；返回时按脱敏规则输出。
        secured = secureSecretId(secured, EMAIL_CONFIG_KEY);
        String json = toJson(secured);
        saveConfig(EMAIL_CONFIG_KEY, json);
        log.info("邮箱配置已保存 provider={}", secured.get("provider"));
    }

    /** 返回完整邮件配置（含解密后的密码与 SecretKey），供 EmailSenderService 内部使用。 */
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
            String encryptedSecretKey = Objects.toString(config.get("tencentSecretKey"), "").trim();
            if (!encryptedSecretKey.isBlank()) {
                config.put("tencentSecretKey", cryptoService.decryptIfNeeded(encryptedSecretKey));
            }
            return config;
        } catch (Exception e) {
            return defaultEmailConfig();
        }
    }

    /**
     * 判断后台邮件配置是否完整。
     * 根据当前 provider 判断：
     *  - smtp：需要 smtpHost、fromEmail、username、password 均非空
     *  - tencent_ses：需要 tencentSecretId、tencentSecretKey、tencentRegion、tencentFromEmailAddress、tencentTemplateId 均有效
     *  - 缺失或未识别的 provider 按 SMTP 兼容
     */
    public boolean isEmailConfigured() {
        Map<String, Object> config = getEmailConfigDecrypted();
        String provider = Objects.toString(config.get("provider"), "smtp").trim().toLowerCase(Locale.ROOT);
        if ("tencent_ses".equals(provider)) {
            return isNonEmpty(config.get("tencentSecretId"))
                    && isNonEmpty(config.get("tencentSecretKey"))
                    && isNonEmpty(config.get("tencentRegion"))
                    && isNonEmpty(config.get("tencentFromEmailAddress"))
                    && parseLong(config.get("tencentTemplateId")) > 0;
        }
        // 默认按 SMTP 兼容
        return isNonEmpty(config.get("smtpHost"))
                && isNonEmpty(config.get("fromEmail"))
                && isNonEmpty(config.get("username"))
                && isNonEmpty(config.get("password"));
    }

    /**
     * 判断腾讯云 SES 是否已配置可用（用于用户级通知页面显示 SES 选项是否可用）。
     */
    public boolean isTencentSesAvailable() {
        try {
            Map<String, Object> config = getEmailConfigDecrypted();
            return isNonEmpty(config.get("tencentSecretId"))
                    && isNonEmpty(config.get("tencentSecretKey"))
                    && isNonEmpty(config.get("tencentRegion"))
                    && isNonEmpty(config.get("tencentFromEmailAddress"))
                    && parseLong(config.get("tencentTemplateId")) > 0;
        } catch (Exception e) {
            return false;
        }
    }

    private boolean isNonEmpty(Object value) {
        return value != null && !Objects.toString(value, "").trim().isBlank();
    }

    private long parseLong(Object value) {
        if (value == null) return 0L;
        if (value instanceof Number n) return n.longValue();
        try {
            return Long.parseLong(String.valueOf(value).trim());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private Map<String, Object> defaultEmailConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        // provider 缺失时按 smtp 兼容
        config.put("provider", "smtp");
        config.put("smtpHost", "smtp.qq.com");
        config.put("smtpPort", 465);
        config.put("encryption", "ssl");
        config.put("fromEmail", "");
        config.put("fromName", "闲鱼助手");
        config.put("username", "");
        config.put("password", "");
        // 腾讯云 SES 默认配置（空值，等待管理员填写）
        config.put("tencentSecretId", "");
        config.put("tencentSecretKey", "");
        config.put("tencentRegion", "ap-hongkong");
        config.put("tencentFromEmailAddress", "");
        config.put("tencentTemplateId", 0);
        // 验证码业务字段
        config.put("subject", "【闲鱼助手】验证码通知");
        config.put("template", "");
        config.put("codeLength", 6);
        config.put("validSeconds", 300);
        config.put("sendInterval", 60);
        config.put("dailyLimit", 20);
        return config;
    }

    /**
     * 构造对外返回的邮件配置：
     *  - password / tencentSecretKey 字段不返回明文，仅返回 *Configured 标记
     *  - tencentSecretId 返回脱敏值（保留前4位 + ****），不返回完整凭据
     *  - 增加 tencentConfigured 标记供前端判断 SES 是否可用
     */
    private Map<String, Object> publicEmailConfig(Map<String, Object> stored) {
        Map<String, Object> result = new LinkedHashMap<>(stored == null ? Map.of() : stored);

        // SMTP 密码脱敏
        String password = Objects.toString(result.get("password"), "").trim();
        result.put("password", "");
        result.put("passwordConfigured", !password.isBlank());

        // 腾讯云 SecretKey 脱敏（不返回明文）
        String secretKey = Objects.toString(result.get("tencentSecretKey"), "").trim();
        result.put("tencentSecretKey", "");
        result.put("tencentSecretKeyConfigured", !secretKey.isBlank());

        // 腾讯云 SecretId 脱敏：保留前 4 位 + ****
        String secretId = Objects.toString(result.get("tencentSecretId"), "").trim();
        if (secretId.isBlank()) {
            result.put("tencentSecretId", "");
            result.put("tencentSecretIdMasked", "");
        } else if (secretId.length() <= 4) {
            result.put("tencentSecretId", "****");
            result.put("tencentSecretIdMasked", "****");
        } else {
            String masked = secretId.substring(0, 4) + "****";
            result.put("tencentSecretId", masked);
            result.put("tencentSecretIdMasked", masked);
        }

        // 腾讯云 SES 是否已完整配置
        boolean tencentConfigured = !secretId.isBlank()
                && !secretKey.isBlank()
                && isNonEmpty(result.get("tencentRegion"))
                && isNonEmpty(result.get("tencentFromEmailAddress"))
                && parseLong(result.get("tencentTemplateId")) > 0;
        result.put("tencentConfigured", tencentConfigured);

        // 兼容字段：清除前端的 clear 标记，避免回显
        result.remove("clearPassword");
        result.remove("clearTencentSecretKey");

        return result;
    }

    /**
     * SecretId 保存逻辑：
     *  - 留空且未勾选清除时保留已有值
     *  - 提交 *{4,} 占位符时保留已有值（前端脱敏值回传）
     *  - 勾选清除时保存空值
     *  - 提交其他值时原样保存（不加密，腾讯云 SecretId 不属于可逆加密敏感字段）
     */
    private Map<String, Object> secureSecretId(Map<String, Object> incoming, String configKey) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (incoming != null) result.putAll(incoming);
        result.remove("tencentSecretIdConfigured");
        result.remove("tencentSecretIdMasked");

        String submitted = Objects.toString(result.get("tencentSecretId"), "").trim();
        if (submitted.isBlank() || submitted.matches("\\*{4,}")) {
            Map<String, Object> existing = rawConfig(configKey);
            submitted = Objects.toString(existing.get("tencentSecretId"), "").trim();
        }
        result.put("tencentSecretId", submitted);
        return result;
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
