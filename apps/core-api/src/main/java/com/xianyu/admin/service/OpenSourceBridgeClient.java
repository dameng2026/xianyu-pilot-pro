package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 开源版桥接客户端：将开源版的反馈数据转发到商业版后端。
 *
 * <p>当配置了 commercial.backend.url 和 commercial.backend.access-token 后，
 * 反馈提交、列表查询、详情查询、补充回复、统计查询都会转发到商业版的
 * /admin-api/open-source-bridge/* 接口。未配置时降级到本地数据库存储。</p>
 */
@Service
public class OpenSourceBridgeClient {
    private static final Logger logger = LoggerFactory.getLogger(OpenSourceBridgeClient.class);
    private static final String INSTANCE_TOKEN_SETTING_KEY = "_x_bridge_iid";
    private static final String INSTANCE_TOKEN_PREFIX = "osi_";
    private static final int INSTANCE_TOKEN_RANDOM_BYTES = 24;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final SecureRandom secureRandom = new SecureRandom();

    @Value("${commercial.backend.url:}")
    private String backendUrl;

    @Value("${commercial.backend.access-token:}")
    private String accessToken;

    @Value("${commercial.backend.site-code:open-source}")
    private String siteCode;

    @Value("${commercial.backend.site-name:开源版}")
    private String siteName;

    @Value("${commercial.backend.frontend-url:}")
    private String frontendUrl;

    @Value("${commercial.backend.admin-url:}")
    private String adminUrl;

    private HttpClient httpClient;
    private String instanceToken;

    public OpenSourceBridgeClient(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PostConstruct
    void init() {
        httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(8))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        instanceToken = ensureInstanceToken();
        if (isBridgeEnabled()) {
            logger.info("OpenSourceBridgeClient enabled: backendUrl={}, siteCode={}, instanceToken={}...",
                    sanitizeUrlForLog(backendUrl), siteCode, instanceToken.substring(0, Math.min(12, instanceToken.length())));
        } else {
            logger.info("OpenSourceBridgeClient disabled (commercial.backend.url not configured)");
        }
    }

    /** 桥接是否启用（配置了商业版地址和token） */
    public boolean isBridgeEnabled() {
        return backendUrl != null && !backendUrl.isBlank()
                && accessToken != null && !accessToken.isBlank();
    }

    /** 获取当前开源部署的实例token */
    public String getInstanceToken() {
        return instanceToken;
    }

    /** 获取配置的站点代码 */
    public String getSiteCode() {
        return siteCode;
    }

    /** 获取配置的站点名称 */
    public String getSiteName() {
        return siteName;
    }

    /**
     * 转发反馈提交到商业版后端。
     * @param body 反馈内容 {category, title, content, contact}
     * @return 商业版返回的反馈详情
     */
    public Map<String, Object> submitFeedback(Map<String, Object> body) {
        return postJson("/feedback", body);
    }

    /**
     * 转发反馈列表查询到商业版后端。
     */
    public Map<String, Object> listFeedback(int current, int size, String status, String category) {
        StringBuilder query = new StringBuilder("?current=" + current + "&size=" + size);
        if (status != null && !status.isBlank()) query.append("&status=").append(status.trim());
        if (category != null && !category.isBlank()) query.append("&category=").append(category.trim());
        return getJson("/feedback" + query);
    }

    /**
     * 转发反馈统计查询到商业版后端。
     */
    public Map<String, Object> feedbackStats() {
        return getJson("/feedback/stats");
    }

    /**
     * 转发反馈详情查询到商业版后端。
     */
    public Map<String, Object> feedbackDetail(long id) {
        return getJson("/feedback/" + id);
    }

    /**
     * 转发反馈补充回复到商业版后端。
     */
    public Map<String, Object> appendFeedbackReply(long id, String content) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("content", content);
        return postJson("/feedback/" + id + "/reply", body);
    }

    // ===== 内部方法 =====

    private Map<String, Object> getJson(String path) {
        return request("GET", path, null);
    }

    private Map<String, Object> postJson(String path, Map<String, Object> body) {
        return request("POST", path, body);
    }

    private Map<String, Object> request(String method, String path, Map<String, Object> body) {
        String url = backendUrl.replaceAll("/+$", "") + "/admin-api/open-source-bridge" + path;
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(15))
                    .header("X-Open-Source-Token", encodeHeader(accessToken))
                    .header("X-Open-Source-Site-Code", encodeHeader(siteCode))
                    .header("X-Open-Source-Site-Name", encodeHeader(siteName))
                    .header("X-Open-Source-Instance-Token", encodeHeader(instanceToken));
            if (frontendUrl != null && !frontendUrl.isBlank()) {
                builder.header("X-Open-Source-Frontend-Url", encodeHeader(frontendUrl));
            }
            if (adminUrl != null && !adminUrl.isBlank()) {
                builder.header("X-Open-Source-Admin-Url", encodeHeader(adminUrl));
            }

            if ("POST".equals(method) && body != null) {
                String json = objectMapper.writeValueAsString(body);
                builder.header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8));
            } else {
                builder.GET();
            }

            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            int code = response.statusCode();
            String responseBody = response.body();
            if (code < 200 || code >= 300) {
                logger.warn("bridge request failed: method={}, path={}, httpCode={}, body={}",
                        method, path, code, truncate(responseBody, 500));
                throw new BizException(503, "商业版后端暂时不可用，请稍后重试");
            }
            return parseBridgeResponse(responseBody);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            logger.error("bridge request error: method={}, path={}, errorType={}",
                    method, path, e.getClass().getSimpleName());
            throw new BizException(503, "无法连接到商业版后端，请稍后重试");
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseBridgeResponse(String body) {
        try {
            Map<String, Object> outer = objectMapper.readValue(body, new TypeReference<>() {});
            // 商业版返回 {code, msg, data}，拆包返回 data
            Object code = outer.get("code");
            if (code instanceof Number number && number.intValue() != 200) {
                String msg = outer.getOrDefault("msg", "商业版后端返回错误").toString();
                throw new BizException(503, msg);
            }
            Object data = outer.get("data");
            if (data instanceof Map) return (Map<String, Object>) data;
            // 非 Map 类型（如分页对象）也返回外层
            return outer;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            logger.error("parse bridge response failed: body={}", truncate(body, 500));
            throw new BizException(503, "商业版后端响应格式异常");
        }
    }

    /** 生成或读取实例token，存储在 xianyu_sys_setting 表 */
    private String ensureInstanceToken() {
        try {
            // 尝试读取已有token
            String sql = "SELECT setting_value FROM xianyu_sys_setting WHERE setting_key = ? AND deleted = 0 LIMIT 1";
            try {
                String existing = jdbcTemplate.queryForObject(sql, String.class, INSTANCE_TOKEN_SETTING_KEY);
                if (existing != null && !existing.isBlank() && existing.startsWith(INSTANCE_TOKEN_PREFIX)) {
                    return existing;
                }
            } catch (Exception ignored) {
                // 表不存在或无记录，继续生成
            }
            // 生成新token
            byte[] bytes = new byte[INSTANCE_TOKEN_RANDOM_BYTES];
            secureRandom.nextBytes(bytes);
            String token = INSTANCE_TOKEN_PREFIX + HexFormat.of().formatHex(bytes);
            // 存储到数据库
            try {
                jdbcTemplate.update(
                        "INSERT INTO xianyu_sys_setting(setting_key, setting_value, description, created_time, updated_time, deleted) " +
                                "VALUES(?, ?, ?, NOW(), NOW(), 0) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_time=NOW()",
                        INSTANCE_TOKEN_SETTING_KEY, token, "开源部署实例标识，用于商业版桥接数据归属"
                );
            } catch (Exception e) {
                logger.warn("persist instance token failed, using in-memory token: {}", e.getClass().getSimpleName());
            }
            return token;
        } catch (Exception e) {
            // 兜底：生成临时token（进程重启后变化）
            byte[] bytes = new byte[INSTANCE_TOKEN_RANDOM_BYTES];
            secureRandom.nextBytes(bytes);
            return INSTANCE_TOKEN_PREFIX + HexFormat.of().formatHex(bytes);
        }
    }

    private String truncate(String value, int max) {
        if (value == null) return "";
        return value.length() > max ? value.substring(0, max) + "..." : value;
    }

    /**
     * Encode header values for HTTP transport. java.net.http.HttpRequest rejects
     * non-ASCII characters in header values per RFC 7230. URL-encode values that
     * contain non-ASCII characters so they can be safely transmitted.
     */
    private String encodeHeader(String value) {
        if (value == null || value.isEmpty()) return "";
        boolean needsEncoding = false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c > 127) {
                needsEncoding = true;
                break;
            }
        }
        if (!needsEncoding) return value;
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private String sanitizeUrlForLog(String url) {
        if (url == null || url.isBlank()) return "";
        // 只保留 scheme + host，不记录 path/query
        try {
            URI uri = URI.create(url);
            return uri.getScheme() + "://" + uri.getHost();
        } catch (Exception e) {
            return "[invalid-url]";
        }
    }
}
