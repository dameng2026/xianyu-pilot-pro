package com.xianyu.admin.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.SystemConfigService;
import com.xianyu.admin.service.NotificationConfigService;
import com.xianyu.admin.service.OutboundNotificationPolicy;
import com.xianyu.admin.service.CookieCryptoService;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URI;
import java.net.URLEncoder;
import java.io.InputStream;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

@RestController
@RequestMapping("/api")
public class UserUtilityController {
    private static final Logger logger = LoggerFactory.getLogger(UserUtilityController.class);
    private static final String NOTIFY_MODULE_KEY = "user-notification-settings";
    private final SystemConfigService systemConfigService;
    private final NotificationConfigService notificationConfigService;
    private final JdbcTemplate jdbcTemplate;
    private final OutboundNotificationPolicy outboundNotificationPolicy;
    private final CookieCryptoService sensitiveValueCrypto;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(8))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    public UserUtilityController(SystemConfigService systemConfigService,
                                 NotificationConfigService notificationConfigService,
                                 JdbcTemplate jdbcTemplate,
                                 OutboundNotificationPolicy outboundNotificationPolicy,
                                 CookieCryptoService sensitiveValueCrypto) {
        this.systemConfigService = systemConfigService;
        this.notificationConfigService = notificationConfigService;
        this.jdbcTemplate = jdbcTemplate;
        this.outboundNotificationPolicy = outboundNotificationPolicy;
        this.sensitiveValueCrypto = sensitiveValueCrypto;
    }

    @GetMapping("/system/runtime-config")
    public Result<Map<String, Object>> runtimeConfig() {
        Map<String, Object> cfg = systemConfigService.getConfig();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("siteName", cfg.getOrDefault("siteName", "闲鱼助手"));
        result.put("contactPhone", cfg.getOrDefault("contactPhone", ""));
        result.put("contactEmail", cfg.getOrDefault("contactEmail", ""));
        result.put("workHours", cfg.getOrDefault("workHours", ""));
        result.put("companyAddress", cfg.getOrDefault("companyAddress", ""));
        result.put("defaultCity", safe(cfg.get("defaultCity")));
        result.put("defaultAddress", safe(cfg.get("companyAddress")));
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("enabled", true);
        map.put("defaultCity", safe(cfg.get("defaultCity")));
        map.put("defaultAddress", safe(cfg.get("companyAddress")));
        result.put("map", map);
        Map<String, Object> ai = new LinkedHashMap<>();
        ai.put("enabled", hasText(cfg.get("aiProvider")) || hasText(cfg.get("aiModel")));
        ai.put("provider", hasText(cfg.get("aiProvider")) ? String.valueOf(cfg.get("aiProvider")) : "backend");
        ai.put("model", hasText(cfg.get("aiModel")) ? String.valueOf(cfg.get("aiModel")) : "backend-default");
        result.put("ai", ai);
        return Result.ok(result);
    }

    @GetMapping("/notification-settings")
    public Result<Map<String, Object>> getNotificationSettings() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        try {
            Map<String, Object> settings = loadRawNotificationSettings(tenantId, userId);
            migrateLegacyNotificationSecrets(tenantId, userId, settings);
            settings.put("tenantId", tenantId);
            settings.put("userId", userId);
            return Result.ok(publicNotificationSettings(settings));
        } catch (Exception e) {
            throw unavailable("通知设置", e);
        }
    }

    /**
     * 用户级通知页面查询平台腾讯云 SES 是否可用。
     *
     * 设计文档 §9：用户级通知页面需要显示「平台腾讯云 SES 可用 / 暂不可用」，
     * 但不暴露 SecretId / SecretKey / TemplateID 等凭据字段。
     *
     * 返回结构：
     *   tencentSesAvailable  boolean  平台是否已完整配置腾讯云 SES
     *   provider             string   平台当前邮件发送方式（smtp / tencent_ses）
     *   smtpEnabled          boolean  SMTP 模式是否可用（用于在 SES 不可用时降级提示）
     */
    @GetMapping("/notification-settings/email-capabilities")
    public Result<Map<String, Object>> emailCapabilities() {
        try {
            Map<String, Object> caps = new LinkedHashMap<>();
            caps.put("tencentSesAvailable", notificationConfigService.isTencentSesAvailable());
            caps.put("smtpEnabled", notificationConfigService.isEmailConfigured());
            // 仅返回 provider 字符串，不返回任何凭据
            Map<String, Object> emailConfig = notificationConfigService.getEmailConfigDecrypted();
            String provider = String.valueOf(emailConfig.getOrDefault("provider", "smtp")).trim().toLowerCase(java.util.Locale.ROOT);
            caps.put("provider", "tencent_ses".equals(provider) ? "tencent_ses" : "smtp");
            return Result.ok(caps);
        } catch (Exception e) {
            // 出错时按 SES 不可用降级返回，避免阻塞用户加载通知设置
            Map<String, Object> caps = new LinkedHashMap<>();
            caps.put("tencentSesAvailable", false);
            caps.put("smtpEnabled", false);
            caps.put("provider", "smtp");
            return Result.ok(caps);
        }
    }

    @PostMapping("/notification-settings")
    public Result<Void> saveNotificationSettings(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        try {
            Map<String, Object> normalized = normalizeNotificationSettings(body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body));
            validateNotificationSettings(normalized);
            Map<String, Object> existing = loadRawNotificationSettings(tenantId, userId);
            Map<String, Object> secured = secureNotificationSettings(normalized, existing);
            secured.put("tenantId", tenantId);
            secured.put("userId", userId);
            String json = objectMapper.writeValueAsString(secured);
            jdbcTemplate.update(
                    "INSERT INTO user_notification_setting(tenant_id, user_id, config_json, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,NOW(),NOW(),0) ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW(), deleted=0",
                    tenantId, userId, json);
            return Result.ok(null);
        } catch (JsonProcessingException e) {
            throw new BizException(400, "通知设置格式不正确");
        } catch (IllegalArgumentException e) {
            throw new BizException(400, e.getMessage());
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("保存通知设置", e);
        }
    }

    @GetMapping("/notifications")
    public Result<PageResult<Map<String, Object>>> notifications(@RequestParam(defaultValue = "1") int current,
                                                                 @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        try {
            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM notification WHERE tenant_id=? AND deleted=0 AND (user_id=? OR user_id IS NULL)",
                    Long.class,
                    tenantId,
                    userId);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, notice_type AS type, title, content, priority, is_read AS readFlag, created_time AS createdTime FROM notification WHERE tenant_id=? AND deleted=0 AND (user_id=? OR user_id IS NULL) ORDER BY created_time DESC LIMIT ?, ?",
                    tenantId, userId, offset, safeSize);
            return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
        } catch (Exception e) {
            throw unavailable("通知列表", e);
        }
    }

    @PostMapping("/notifications/{id}/read")
    public Result<Void> read(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        if (id == null || id <= 0) {
            throw new BizException(400, "通知 ID 非法");
        }
        try {
            int affected = jdbcTemplate.update(
                    "UPDATE notification SET is_read=1, read_time=NOW(), updated_time=NOW() " +
                            "WHERE tenant_id=? AND user_id=? AND id=? AND deleted=0",
                    tenantId, userId, id);
            if (affected != 1) {
                throw new BizException(404, "通知不存在或无权操作");
            }
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("通知状态更新", e);
        }
    }

    @PostMapping("/notifications/test")
    public Result<Map<String, Object>> test(@RequestBody(required = false) Map<String, Object> body) {
        try {
            Long tenantId = TenantContext.getCurrentTenantId();
            Long userId = UserContext.userId();
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            String title = String.valueOf(payload.getOrDefault("title", "测试通知"));
            String content = String.valueOf(payload.getOrDefault("content", "通知通道测试"));
            Map<String, Object> settings = notificationSettingsForDelivery(tenantId, userId);
            List<Map<String, Object>> channels = castList(settings.get("channels"));
            List<Map<String, Object>> targets = channels.stream().filter(c -> Boolean.TRUE.equals(c.get("enabled"))).toList();
            if (targets.isEmpty() && !channels.isEmpty()) targets = List.of(channels.get(0));
            if (targets.isEmpty()) targets = defaultChannels().stream().limit(1).toList();

            List<Map<String, Object>> results = new ArrayList<>();
            for (Map<String, Object> channel : targets) {
                results.add(sendOneNotification(tenantId, userId, channel, title, content));
            }
            boolean allOk = results.stream().allMatch(r -> Boolean.TRUE.equals(r.get("success")));
            jdbcTemplate.update("INSERT INTO notification(tenant_id, user_id, notice_type, notification_type, title, content, level, priority, is_read, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,?,?,0,NOW(),NOW(),0)",
                    tenantId, userId, "test", "test", title, content, allOk ? "info" : "warn", allOk ? 0 : 2);
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("success", allOk);
            res.put("results", results);
            return Result.ok(res);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("通知测试", e);
        }
    }

    @GetMapping("/notifications/delivery-logs")
    public Result<PageResult<Map<String, Object>>> deliveryLogs(@RequestParam(defaultValue = "1") int current,
                                                                @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        try {
            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM notification_delivery_log WHERE tenant_id=? AND user_id=?",
                    Long.class,
                    tenantId,
                    userId);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, channel_key AS channelKey, channel_name AS channelName, event_type AS eventType, success, status_code AS statusCode, cost_ms AS costMs, message, retry_count AS retryCount, created_time AS createdTime FROM notification_delivery_log WHERE tenant_id=? AND user_id=? ORDER BY created_time DESC LIMIT ?, ?",
                    tenantId, userId, offset, safeSize);
            return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
        } catch (Exception e) {
            throw unavailable("通知发送记录", e);
        }
    }


    private Map<String, Object> sendOneNotification(Long tenantId, Long userId, Map<String, Object> channel, String title, String content) {
        long start = System.currentTimeMillis();
        String channelKey = safe(channel.getOrDefault("key", "webhook"));
        String channelName = safe(channel.getOrDefault("name", channelKey));
        String type = safe(channel.get("type"));
        String url = safe(channel.get("webhookUrl"));
        int statusCode = 0;
        boolean success = false;
        String message = "";
        String requestBody = "";
        String responseBody = "";
        int retryCount = Math.max(0, parseInt(channel.get("retryCount"), 0));
        try {
            String rendered = renderTemplate(safe(channel.get("template")), title, content);
            switch (type) {
                case "feishu": {
                    if (!url.startsWith("http")) throw new RuntimeException("Webhook URL 未配置");
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("msg_type", "text");
                    body.put("content", Map.of("text", rendered));
                    requestBody = objectMapper.writeValueAsString(body);
                    String finalUrl = url;
                    String secret = safe(channel.get("secret"));
                    if (!secret.isEmpty()) {
                        long timestamp = System.currentTimeMillis() / 1000;
                        String sign = genFeishuSign(timestamp, secret);
                        finalUrl = url + (url.contains("?") ? "&" : "?") + "timestamp=" + timestamp + "&sign=" + sign;
                    }
                    OutboundHttpResponse resp = httpPost(type, finalUrl, requestBody, channel);
                    statusCode = resp.statusCode();
                    responseBody = resp.body();
                    success = parseFeishuResponse(statusCode, responseBody);
                    message = success ? "飞书发送成功" : ("飞书发送失败: HTTP " + statusCode);
                    break;
                }
                case "dingtalk": {
                    if (!url.startsWith("http")) throw new RuntimeException("Webhook URL 未配置");
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("msgtype", "text");
                    body.put("text", Map.of("content", rendered));
                    requestBody = objectMapper.writeValueAsString(body);
                    String finalUrl = url;
                    String secret = safe(channel.get("secret"));
                    if (!secret.startsWith("SEC")) secret = "";
                    if (!secret.isEmpty()) {
                        long timestamp = System.currentTimeMillis();
                        String sign = genDingtalkSign(timestamp, secret);
                        finalUrl = url + (url.contains("?") ? "&" : "?") + "timestamp=" + timestamp + "&sign=" + sign;
                    }
                    OutboundHttpResponse resp = httpPost(type, finalUrl, requestBody, channel);
                    statusCode = resp.statusCode();
                    responseBody = resp.body();
                    success = parseDingtalkResponse(statusCode, responseBody);
                    message = success ? "钉钉发送成功" : ("钉钉发送失败: HTTP " + statusCode);
                    break;
                }
                case "wechat_work": {
                    if (!url.startsWith("http")) throw new RuntimeException("Webhook URL 未配置");
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("msgtype", "text");
                    body.put("text", Map.of("content", rendered));
                    requestBody = objectMapper.writeValueAsString(body);
                    OutboundHttpResponse resp = httpPost(type, url, requestBody, channel);
                    statusCode = resp.statusCode();
                    responseBody = resp.body();
                    success = parseWechatWorkResponse(statusCode, responseBody);
                    message = success ? "企业微信发送成功" : ("企业微信发送失败: HTTP " + statusCode);
                    break;
                }
                case "pushplus": {
                    String token = safe(channel.get("receiver"));
                    if (token.isEmpty()) throw new RuntimeException("PushPlus Token 未配置");
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("token", token);
                    body.put("title", title);
                    body.put("content", rendered);
                    body.put("template", "txt");
                    requestBody = objectMapper.writeValueAsString(body);
                    OutboundHttpResponse resp = httpPost("pushplus", "https://www.pushplus.plus/send", requestBody, channel);
                    statusCode = resp.statusCode();
                    responseBody = resp.body();
                    success = parsePushPlusResponse(statusCode, responseBody);
                    message = success ? "PushPlus 发送成功" : ("PushPlus 发送失败: HTTP " + statusCode);
                    break;
                }
                case "email": {
                    String smtpHost = safe(channel.get("smtpHost"));
                    int smtpPort = parseInt(channel.get("smtpPort"), 465);
                    String smtpUser = safe(channel.get("smtpUser"));
                    String smtpPass = safe(channel.get("smtpPass"));
                    String fromEmail = safe(channel.get("fromEmail"));
                    String toEmail = safe(channel.get("receiver"));
                    if (smtpHost.isEmpty() || smtpUser.isEmpty() || smtpPass.isEmpty() || toEmail.isEmpty()) {
                        throw new RuntimeException("邮箱 SMTP 配置不完整（需要主机/端口/用户名/授权码/收件人）");
                    }
                    outboundNotificationPolicy.validateSmtp(smtpHost, smtpPort);
                    if (fromEmail.isEmpty()) fromEmail = smtpUser;
                    requestBody = "to=" + toEmail + "&subject=" + title + "&body=" + rendered;
                    sendEmail(smtpHost, smtpPort, smtpUser, smtpPass, fromEmail, toEmail, title, rendered);
                    statusCode = 250;
                    responseBody = "SMTP sent OK";
                    success = true;
                    message = "邮箱发送成功";
                    break;
                }
                case "webhook":
                default: {
                    if (!url.startsWith("http")) throw new RuntimeException("Webhook URL 未配置");
                    String method = safe(channel.get("method"));
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("title", title);
                    body.put("content", rendered);
                    body.put("channel", channelKey);
                    body.put("time", java.time.LocalDateTime.now().toString());
                    requestBody = objectMapper.writeValueAsString(body);
                    OutboundHttpResponse resp;
                    if ("GET".equalsIgnoreCase(method)) {
                        resp = httpGet(type, url, channel);
                    } else {
                        resp = httpPost(type, url, requestBody, channel);
                    }
                    statusCode = resp.statusCode();
                    responseBody = resp.body();
                    success = statusCode >= 200 && statusCode < 300;
                    message = success ? "Webhook 发送成功" : ("Webhook 返回 HTTP " + statusCode);
                    break;
                }
            }
        } catch (Exception e) {
            success = false;
            message = e instanceof IllegalArgumentException
                    ? "通知目标不安全或未获管理员授权"
                    : "通知发送失败，请检查通道配置";
            responseBody = "";
            logger.warn("notification delivery failed tenantId={} userId={} channelType={} errorType={}",
                    tenantId, userId, type, e.getClass().getSimpleName());
        }
        long cost = System.currentTimeMillis() - start;
        jdbcTemplate.update("INSERT INTO notification_delivery_log(tenant_id, user_id, channel_key, channel_name, event_type, success, status_code, cost_ms, message, request_body, response_body, retry_count, created_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NOW())",
                tenantId, userId, channelKey, channelName, "test", success ? 1 : 0, statusCode, cost, truncate(message, 500), "", "", retryCount);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("channelKey", channelKey);
        result.put("channelName", channelName);
        result.put("success", success);
        result.put("statusCode", statusCode);
        result.put("costMs", cost);
        result.put("message", message);
        return result;
    }

    private OutboundHttpResponse httpPost(String channelType, String url, String body, Map<String, Object> channel) throws Exception {
        URI safeUri = outboundNotificationPolicy.validateWebhook(channelType, url);
        HttpRequest request = HttpRequest.newBuilder(safeUri)
                .timeout(Duration.ofSeconds(boundedTimeoutSeconds(channel)))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        return sendBounded(request);
    }

    private OutboundHttpResponse httpGet(String channelType, String url, Map<String, Object> channel) throws Exception {
        URI safeUri = outboundNotificationPolicy.validateWebhook(channelType, url);
        HttpRequest request = HttpRequest.newBuilder(safeUri)
                .timeout(Duration.ofSeconds(boundedTimeoutSeconds(channel)))
                .GET().build();
        return sendBounded(request);
    }

    private OutboundHttpResponse sendBounded(HttpRequest request) throws Exception {
        HttpResponse<InputStream> response = httpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());
        try (InputStream stream = response.body()) {
            byte[] bytes = stream.readNBytes(65_537);
            if (bytes.length > 65_536) {
                throw new IllegalStateException("notification provider response is too large");
            }
            return new OutboundHttpResponse(
                    response.statusCode(),
                    new String(bytes, StandardCharsets.UTF_8)
            );
        }
    }

    private int boundedTimeoutSeconds(Map<String, Object> channel) {
        return Math.max(1, Math.min(parseInt(channel.get("timeoutSeconds"), 10), 15));
    }

    private record OutboundHttpResponse(int statusCode, String body) {}

    /** 飞书：HTTP 2xx + 响应 JSON code==0 视为成功 */
    private boolean parseFeishuResponse(int statusCode, String body) {
        if (statusCode < 200 || statusCode >= 300) return false;
        if (body == null) return true;
        try {
            Map<?, ?> json = objectMapper.readValue(body, Map.class);
            Object code = json.get("code");
            return code != null ? code.toString().equals("0") : true;
        } catch (Exception e) {
            // 解析失败说明飞书返回的不是预期 JSON 结构，可能为错误响应或风控页面，应判失败而非成功
            logger.warn("parseFeishuResponse failed statusCode={} bodyLen={} errorType={}",
                statusCode, body == null ? 0 : body.length(), e.getClass().getSimpleName());
            return false;
        }
    }

    /** 钉钉：HTTP 2xx + errcode==0 视为成功 */
    private boolean parseDingtalkResponse(int statusCode, String body) {
        if (statusCode < 200 || statusCode >= 300) return false;
        if (body == null) return true;
        try {
            Map<?, ?> json = objectMapper.readValue(body, Map.class);
            Object code = json.get("errcode");
            return code != null ? code.toString().equals("0") : true;
        } catch (Exception e) {
            logger.warn("parseDingtalkResponse failed statusCode={} bodyLen={} errorType={}",
                statusCode, body == null ? 0 : body.length(), e.getClass().getSimpleName());
            return false;
        }
    }

    /** 企业微信：HTTP 2xx + errcode==0 视为成功 */
    private boolean parseWechatWorkResponse(int statusCode, String body) {
        if (statusCode < 200 || statusCode >= 300) return false;
        if (body == null) return true;
        try {
            Map<?, ?> json = objectMapper.readValue(body, Map.class);
            Object code = json.get("errcode");
            return code != null ? code.toString().equals("0") : true;
        } catch (Exception e) {
            logger.warn("parseWechatWorkResponse failed statusCode={} bodyLen={} errorType={}",
                statusCode, body == null ? 0 : body.length(), e.getClass().getSimpleName());
            return false;
        }
    }

    /** PushPlus：HTTP 2xx + code==200 视为成功 */
    private boolean parsePushPlusResponse(int statusCode, String body) {
        if (statusCode < 200 || statusCode >= 300) return false;
        if (body == null) return true;
        try {
            Map<?, ?> json = objectMapper.readValue(body, Map.class);
            Object code = json.get("code");
            return code != null ? code.toString().equals("200") : true;
        } catch (Exception e) {
            logger.warn("parsePushPlusResponse failed statusCode={} bodyLen={} errorType={}",
                statusCode, body == null ? 0 : body.length(), e.getClass().getSimpleName());
            return false;
        }
    }

    private String extractErrMsg(String body) {
        if (body == null) return "";
        try {
            Map<?, ?> json = objectMapper.readValue(body, Map.class);
            Object msg = json.get("msg");
            if (msg == null) msg = json.get("errmsg");
            if (msg == null) msg = json.get("message");
            return msg != null ? msg.toString() : body;
        } catch (Exception e) { return body.length() > 200 ? body.substring(0, 200) : body; }
    }

    /**
     * 生成飞书自定义机器人签名。
     * 算法：将 "timestamp\nsecret" 作为 HMAC-SHA256 的 key，对空字符串做 HMAC，再 base64 编码。
     */
    private String genFeishuSign(long timestamp, String secret) throws Exception {
        String stringToSign = timestamp + "\n" + secret;
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(stringToSign.getBytes("UTF-8"), "HmacSHA256"));
        byte[] hmacBytes = mac.doFinal();
        return Base64.getEncoder().encodeToString(hmacBytes);
    }

    /**
     * 生成钉钉自定义机器人加签。
     * 算法：HMAC-SHA256(key=secret, message="timestamp\nsecret")，再 URLEncode(Base64)。
     */
    private String genDingtalkSign(long timestamp, String secret) throws Exception {
        String stringToSign = timestamp + "\n" + secret;
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes("UTF-8"), "HmacSHA256"));
        byte[] hmacBytes = mac.doFinal(stringToSign.getBytes("UTF-8"));
        return URLEncoder.encode(Base64.getEncoder().encodeToString(hmacBytes), "UTF-8");
    }

    /** 通过 SMTP 发送一封邮件 */
    private void sendEmail(String host, int port, String user, String pass, String from, String to, String subject, String body) throws Exception {
        java.util.Properties props = new java.util.Properties();
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.host", host);
        props.put("mail.smtp.port", String.valueOf(port));
        if (port == 465) {
            props.put("mail.smtp.ssl.enable", "true");
            props.put("mail.smtp.socketFactory.class", "javax.net.ssl.SSLSocketFactory");
            props.put("mail.smtp.socketFactory.port", String.valueOf(port));
        } else if (port == 587) {
            props.put("mail.smtp.starttls.enable", "true");
        }
        jakarta.mail.Session session = jakarta.mail.Session.getInstance(props, new jakarta.mail.Authenticator() {
            @Override
            protected jakarta.mail.PasswordAuthentication getPasswordAuthentication() {
                return new jakarta.mail.PasswordAuthentication(user, pass);
            }
        });
        jakarta.mail.internet.MimeMessage msg = new jakarta.mail.internet.MimeMessage(session);
        msg.setFrom(new jakarta.mail.internet.InternetAddress(from));
        msg.setRecipients(jakarta.mail.Message.RecipientType.TO, jakarta.mail.internet.InternetAddress.parse(to));
        msg.setSubject(subject, "UTF-8");
        msg.setText(body, "UTF-8");
        msg.setSentDate(new java.util.Date());
        jakarta.mail.Transport.send(msg);
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> castList(Object value) {
        if (!(value instanceof List<?> list)) return new ArrayList<>();
        List<Map<String, Object>> res = new ArrayList<>();
        for (Object item : list) {
            if (item instanceof Map<?, ?> map) {
                Map<String, Object> row = new LinkedHashMap<>();
                map.forEach((k, v) -> row.put(String.valueOf(k), v));
                res.add(row);
            }
        }
        return res;
    }

    private String renderTemplate(String template, String title, String content) {
        String source = hasText(template) ? template : "{title}\n{content}";
        return source.replace("{title}", title).replace("{content}", content).replace("{time}", java.time.LocalDateTime.now().toString());
    }

    private String truncate(String value, int max) {
        if (value == null) return "";
        return value.length() <= max ? value : value.substring(0, max);
    }

    private int parseInt(Object value, int def) {
        try { return Integer.parseInt(String.valueOf(value)); } catch (Exception e) { return def; }
    }

    private String loadLegacyNotificationSettings(Long userId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id DESC LIMIT 1",
                    String.class,
                    NOTIFY_MODULE_KEY,
                    String.valueOf(userId));
        } catch (EmptyResultDataAccessException noLegacySetting) {
            return null;
        }
    }

    private BizException unavailable(String operation, Exception cause) {
        if (cause instanceof BizException bizException) {
            return bizException;
        }
        logger.error("{}不可用, errorType={}", operation, cause.getClass().getSimpleName());
        return new BizException(503, operation + "暂时不可用，请稍后重试");
    }

    private Map<String, Object> loadRawNotificationSettings(Long tenantId, Long userId) throws Exception {
        Map<String, Object> settings = defaultNotificationSettings();
        String json;
        try {
            json = jdbcTemplate.queryForObject(
                    "SELECT config_json FROM user_notification_setting WHERE tenant_id=? AND user_id=? AND deleted=0 LIMIT 1",
                    String.class, tenantId, userId);
        } catch (EmptyResultDataAccessException noCurrentSetting) {
            json = loadLegacyNotificationSettings(userId);
        }
        mergeJson(settings, json);
        return normalizeNotificationSettings(settings);
    }

    private Map<String, Object> notificationSettingsForDelivery(Long tenantId, Long userId) throws Exception {
        Map<String, Object> settings = loadRawNotificationSettings(tenantId, userId);
        Map<String, Object> result = new LinkedHashMap<>(settings);
        List<Map<String, Object>> channels = new ArrayList<>();
        for (Map<String, Object> channel : castList(settings.get("channels"))) {
            Map<String, Object> copy = new LinkedHashMap<>(channel);
            for (String field : sensitiveFields(copy)) {
                String stored = safe(copy.get(field)).trim();
                copy.put(field, stored.isBlank() ? "" : sensitiveValueCrypto.decryptIfNeeded(stored));
            }
            channels.add(copy);
        }
        result.put("channels", channels);
        return result;
    }

    private Map<String, Object> publicNotificationSettings(Map<String, Object> settings) {
        Map<String, Object> result = new LinkedHashMap<>(settings);
        List<Map<String, Object>> channels = new ArrayList<>();
        for (Map<String, Object> channel : castList(settings.get("channels"))) {
            Map<String, Object> copy = new LinkedHashMap<>(channel);
            for (String field : sensitiveFields(copy)) {
                String stored = safe(copy.get(field)).trim();
                String plain = stored.isBlank() ? "" : sensitiveValueCrypto.decryptIfNeeded(stored);
                copy.put(field, "");
                copy.put(field + "Configured", !plain.isBlank());
                copy.put(field + "Last4", lastFour(plain));
                copy.remove(clearFlag(field));
            }
            channels.add(copy);
        }
        result.put("channels", channels);
        return result;
    }

    private Map<String, Object> secureNotificationSettings(Map<String, Object> incoming,
                                                            Map<String, Object> existingSettings) {
        Map<String, Map<String, Object>> existingByKey = new LinkedHashMap<>();
        for (Map<String, Object> channel : castList(existingSettings.get("channels"))) {
            existingByKey.put(safe(channel.get("key")), channel);
        }

        Map<String, Object> result = new LinkedHashMap<>(incoming);
        List<Map<String, Object>> channels = new ArrayList<>();
        for (Map<String, Object> channel : castList(incoming.get("channels"))) {
            Map<String, Object> copy = new LinkedHashMap<>(channel);
            Map<String, Object> existing = existingByKey.getOrDefault(safe(copy.get("key")), Map.of());
            for (String field : sensitiveFields(copy)) {
                boolean clear = Boolean.TRUE.equals(copy.remove(clearFlag(field)));
                copy.remove(field + "Configured");
                copy.remove(field + "Last4");
                String submitted = safe(copy.get(field)).trim();
                String existingStored = safe(existing.get(field)).trim();
                if (clear) {
                    copy.put(field, "");
                } else if (submitted.isBlank() || submitted.matches("\\*{4,}")) {
                    copy.put(field, existingStored);
                } else {
                    String plain = sensitiveValueCrypto.decryptIfNeeded(submitted);
                    copy.put(field, sensitiveValueCrypto.encrypt(plain));
                }
            }
            channels.add(copy);
        }
        result.put("channels", channels);
        return result;
    }

    private void migrateLegacyNotificationSecrets(Long tenantId,
                                                  Long userId,
                                                  Map<String, Object> settings) throws Exception {
        boolean hasPlaintext = castList(settings.get("channels")).stream()
                .flatMap(channel -> sensitiveFields(channel).stream()
                        .map(field -> safe(channel.get(field)).trim()))
                .anyMatch(value -> !value.isBlank() && !value.startsWith("enc:v1:"));
        if (!hasPlaintext) return;

        Map<String, Object> secured = secureNotificationSettings(settings, settings);
        String json = objectMapper.writeValueAsString(secured);
        jdbcTemplate.update(
                "INSERT INTO user_notification_setting(tenant_id, user_id, config_json, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,NOW(),NOW(),0) ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW(), deleted=0",
                tenantId, userId, json);
    }

    private List<String> sensitiveFields(Map<String, Object> channel) {
        List<String> fields = new ArrayList<>(List.of("secret", "smtpPass", "verificationToken", "encryptKey"));
        if ("pushplus".equalsIgnoreCase(safe(channel.get("type")))) {
            fields.add("receiver");
        }
        return fields;
    }

    private String clearFlag(String field) {
        return "clear" + Character.toUpperCase(field.charAt(0)) + field.substring(1);
    }

    private String lastFour(String value) {
        if (value == null || value.isBlank()) return "";
        return value.length() <= 4 ? "" : value.substring(value.length() - 4);
    }

    private void mergeJson(Map<String, Object> target, String json) throws Exception {
        if (json == null || json.isBlank()) return;
        Map<String, Object> stored = objectMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
        target.putAll(stored);
    }

    @SuppressWarnings("unchecked")
    private void validateNotificationSettings(Map<String, Object> settings) {
        for (Map<String, Object> channel : castList(settings.get("channels"))) {
            String type = safe(channel.get("type")).trim().toLowerCase(java.util.Locale.ROOT);
            boolean enabled = Boolean.TRUE.equals(channel.get("enabled"));
            if (List.of("webhook", "feishu", "dingtalk", "wechat_work").contains(type)) {
                String webhookUrl = safe(channel.get("webhookUrl"));
                if (webhookUrl.isBlank()) {
                    if (enabled) throw new IllegalArgumentException("已启用的通知通道缺少 Webhook 地址");
                } else {
                    outboundNotificationPolicy.validateWebhook(type, webhookUrl);
                }
            } else if ("email".equals(type)) {
                String smtpHost = safe(channel.get("smtpHost"));
                int smtpPort = parseInt(channel.get("smtpPort"), 465);
                if (smtpHost.isBlank()) {
                    if (enabled) throw new IllegalArgumentException("已启用的邮件通道缺少 SMTP 主机");
                } else {
                    outboundNotificationPolicy.validateSmtp(smtpHost, smtpPort);
                }
            }
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> normalizeNotificationSettings(Map<String, Object> input) {
        Map<String, Object> result = defaultNotificationSettings();
        if (input != null) result.putAll(input);
        if (!(result.get("channels") instanceof List<?> list) || list.isEmpty()) {
            result.put("channels", defaultChannels());
        }
        if (!(result.get("events") instanceof List<?> events) || events.isEmpty()) {
            result.put("events", defaultEvents());
        } else {
            // 增量合并：把默认事件中存在但已保存配置缺失的事件补进去（默认启用），避免新增事件类型在旧配置上不显示
            List<Map<String, Object>> merged = new ArrayList<>((List<Map<String, Object>>) events);
            java.util.Set<String> existing = new java.util.HashSet<>();
            for (Map<String, Object> e : merged) {
                Object name = e.get("event");
                if (name != null) existing.add(name.toString());
            }
            for (Map<String, Object> d : defaultEvents()) {
                Object name = d.get("event");
                if (name != null && !existing.contains(name.toString())) {
                    merged.add(new LinkedHashMap<>(d));
                }
            }
            result.put("events", merged);
        }
        result.putIfAbsent("sendMode", "single");
        result.putIfAbsent("inApp", true);
        return result;
    }

    private Map<String, Object> defaultNotificationSettings() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("inApp", true);
        map.put("email", false);
        map.put("sms", false);
        map.put("deliveryError", true);
        map.put("accountOffline", true);
        map.put("stockWarning", true);
        map.put("sendMode", "single");
        map.put("channels", defaultChannels());
        map.put("events", defaultEvents());
        return map;
    }

    private List<Map<String, Object>> defaultChannels() {
        List<Map<String, Object>> list = new ArrayList<>();
        list.add(channel("webhook", "通用 Webhook", "webhook", false));
        list.add(channel("feishu", "飞书机器人", "feishu", false));
        list.add(channel("dingtalk", "钉钉机器人", "dingtalk", false));
        list.add(channel("wechat_work", "企业微信群机器人", "wechat_work", false));
        list.add(channel("pushplus", "Push Plus", "pushplus", false));
        list.add(channel("email", "邮箱 SMTP", "email", false));
        return list;
    }

    private Map<String, Object> channel(String key, String name, String type, boolean enabled) {
        Map<String, Object> c = new LinkedHashMap<>();
        c.put("key", key);
        c.put("name", name);
        c.put("type", type);
        c.put("enabled", enabled);
        c.put("method", "POST");
        c.put("contentType", "application/json");
        c.put("webhookUrl", "");
        c.put("receiver", "");
        c.put("secret", "");
        c.put("timeoutSeconds", 10);
        c.put("retryCount", 3);
        c.put("template", "{title}\n{content}");
        return c;
    }

    private List<Map<String, Object>> defaultEvents() {
        List<Map<String, Object>> list = new ArrayList<>();
        for (String name : List.of("激活提醒", "新订单提醒", "自动发货成功", "自动发货失败", "代发货提醒", "库存预警", "整点报表", "账号掉线", "Cookie 到期", "人机验证", "人机验证成功", "应用内通知")) {
            Map<String, Object> e = new LinkedHashMap<>();
            e.put("event", name);
            e.put("enabled", true);
            e.put("app", true);
            list.add(e);
        }
        return list;
    }

    private boolean hasText(Object value) { return value != null && !String.valueOf(value).isBlank(); }
    private String safe(Object value) { return value == null ? "" : String.valueOf(value); }
}
