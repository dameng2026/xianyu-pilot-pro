package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Java -> Python 自动化服务内部客户端。
 *
 * Java 侧只保留主数据、权限和前台网关；扫码、自动回复、自动发货、爬虫/商机等执行动作转交 Python。
 */
@Service
public class AutomationClient {
    private static final Logger log = LoggerFactory.getLogger(AutomationClient.class);
    private static final String DEV_INTERNAL_TOKEN = "dev-only-internal-api-token-change-me-32-chars";
    static final int MAX_MULTIPART_FILE_BYTES = 20 * 1024 * 1024;
    static final int MAX_MULTIPART_FIELDS = 32;
    static final int MAX_MULTIPART_FIELD_BYTES = 64 * 1024;
    static final int MAX_MULTIPART_METADATA_BYTES = 256 * 1024;
    static final int MAX_JSON_REQUEST_BYTES = 8 * 1024 * 1024;
    static final int MAX_JSON_RESPONSE_BYTES = 8 * 1024 * 1024;
    private static final int MAX_ERROR_RESPONSE_BYTES = 64 * 1024;
    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)  // Python uvicorn 不支持 HTTP/2
            .connectTimeout(Duration.ofSeconds(8))
            .build();

    @Value("${xianyu.automation.base-url:http://localhost:12401}")
    private String automationBaseUrl;

    @Value("${xianyu.automation.crawler-base-url:http://localhost:3001}")
    private String crawlerBaseUrl;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public Map<String, Object> postInternalForData(String path, Map<String, Object> body) {
        return asMap(dataOrSelf(postJson(normalizeBase(automationBaseUrl), path, body, true)));
    }

    public Map<String, Object> putInternalForData(String path, Map<String, Object> body) {
        return asMap(dataOrSelf(putJson(normalizeBase(automationBaseUrl), path, body, true)));
    }

    public Map<String, Object> putInternalForData(String path, Map<String, Object> body, Long tenantId) {
        return asMap(dataOrSelf(putJson(normalizeBase(automationBaseUrl), path, body, true, tenantId)));
    }

    public Map<String, Object> deleteInternalForData(String path) {
        return asMap(dataOrSelf(delete(normalizeBase(automationBaseUrl), path, true)));
    }

    public Map<String, Object> deleteInternalForData(String path, Long tenantId) {
        return asMap(dataOrSelf(delete(normalizeBase(automationBaseUrl), path, true, tenantId)));
    }

    public Map<String, Object> postInternalForData(String path, Map<String, Object> body, Long tenantId) {
        return asMap(dataOrSelf(postJson(normalizeBase(automationBaseUrl), path, body, true, 30, tenantId)));
    }

    /**
     * 用于发布、删除等高风险动作：下游业务 code 不是 200/0 时直接抛错，
     * 避免 Java 外层再包一层 code=200 造成前端误判成功。
     */
    public Map<String, Object> postInternalForDataOrThrow(String path, Map<String, Object> body) {
        Map<String, Object> raw = postJson(normalizeBase(automationBaseUrl), path, body, true);
        assertBusinessSuccess(raw);
        return asMap(dataOrSelf(raw));
    }

    public Map<String, Object> postInternal(String path, Map<String, Object> body) {
        return postJson(normalizeBase(automationBaseUrl), path, body, true);
    }

    public Map<String, Object> postInternal(String path, Map<String, Object> body, Long tenantId) {
        return postJson(normalizeBase(automationBaseUrl), path, body, true, 30, tenantId);
    }

    /**
     * 用于工作流执行等长耗时操作：允许调用方指定超时秒数，避免默认 30 秒触发 HttpTimeoutException。
     * 超时秒数会被夹在 [1, 180] 范围内，与 GET 方法的上限保持一致。
     */
    public Map<String, Object> postInternalForData(String path, Map<String, Object> body, long timeoutSeconds) {
        return asMap(dataOrSelf(postJson(normalizeBase(automationBaseUrl), path, body, true, timeoutSeconds)));
    }

    public Map<String, Object> postInternalForData(String path, Map<String, Object> body, long timeoutSeconds, Long tenantId) {
        return asMap(dataOrSelf(postJson(normalizeBase(automationBaseUrl), path, body, true, timeoutSeconds, tenantId)));
    }

    public Object getInternalForData(String path, Map<String, ?> query) {
        return dataOrSelf(get(normalizeBase(automationBaseUrl), path, query, true));
    }

    public Object getInternalForData(String path, Map<String, ?> query, Long tenantId) {
        return dataOrSelf(get(normalizeBase(automationBaseUrl), path, query, true, 30, tenantId));
    }

    /**
     * 与 postInternalForData 类似，但返回 Object 而非 Map。
     * 用于 Python 服务返回的 data 字段是数组、字符串或原始值的场景
     * （如 /autoDelivery/config/list 返回数组，/autoDelivery/config/save 返回字符串）。
     * 避免 asMap 把数组/字符串包成 {"value": ...} 导致前端取不到数据。
     */
    public Object postInternalForObject(String path, Map<String, Object> body) {
        return dataOrSelf(postJson(normalizeBase(automationBaseUrl), path, body, true));
    }

    public Object getInternalForData(String path, Map<String, ?> query, long timeoutSeconds) {
        return dataOrSelf(get(normalizeBase(automationBaseUrl), path, query, true, timeoutSeconds));
    }

    public Object getInternalForData(String path, Map<String, ?> query, long timeoutSeconds, Long tenantId) {
        return dataOrSelf(get(normalizeBase(automationBaseUrl), path, query, true, timeoutSeconds, tenantId));
    }

    public Map<String, Object> getInternal(String path, Map<String, ?> query) {
        return get(normalizeBase(automationBaseUrl), path, query, true);
    }

    public Map<String, Object> getInternal(String path, Map<String, ?> query, Long tenantId) {
        return get(normalizeBase(automationBaseUrl), path, query, true, 30, tenantId);
    }

    public Map<String, Object> getInternal(String path, Map<String, ?> query, long timeoutSeconds) {
        return get(normalizeBase(automationBaseUrl), path, query, true, timeoutSeconds);
    }

    public Map<String, Object> getInternal(String path, Map<String, ?> query, long timeoutSeconds, Long tenantId) {
        return get(normalizeBase(automationBaseUrl), path, query, true, timeoutSeconds, tenantId);
    }

    public Object postCrawler(String path, Map<String, Object> body) {
        return dataOrSelf(postJson(normalizeBase(crawlerBaseUrl), path, body, true));
    }

    public Object getCrawler(String path, Map<String, ?> query) {
        return dataOrSelf(get(normalizeBase(crawlerBaseUrl), path, query, true));
    }

    public void streamSse(String path, Map<String, ?> query, java.io.OutputStream outputStream) {
        streamSse(path, query, outputStream, com.xianyu.admin.security.TenantContext.getCurrentTenantId());
    }

    public void streamSse(String path, Map<String, ?> query, java.io.OutputStream outputStream, Long tenantId) {
        try {
            String url = normalizeBase(automationBaseUrl) + ensureSlash(path) + toQuery(query);
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .GET();
            applyInternalHeaders(builder, tenantId);
            HttpResponse<java.io.InputStream> resp = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofInputStream());
            if (resp.statusCode() >= 400) {
                String body = readResponseText(resp.body(), MAX_ERROR_RESPONSE_BYTES);
                ensureSuccessStatus(resp.statusCode(), body);
            }
            try (java.io.InputStream input = resp.body()) {
                input.transferTo(outputStream);
                outputStream.flush();
            }
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "实时消息服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("订阅自动化 SSE 失败, path={}, errorType={}", path, e.getClass().getSimpleName());
            throw new BizException(503, "实时消息服务暂时不可用，请稍后重试");
        }
    }

    /**
     * 上传文件到自动化服务（multipart/form-data）。
     *
     * @param path  目标路径，如 /api/xianyu/accounts/{id}/auto-category/upload
     * @param file  上传的文件
     * @param body  额外的表单字段（如 title, description 等）
     * @return 解析后的响应对象
     */
    public Map<String, Object> uploadInternalForData(String path, java.io.InputStream fileStream, String fileName, Map<String, Object> body) {
        return uploadInternalForData(path, fileStream, fileName, body, null);
    }

    public Map<String, Object> uploadInternalForData(String path, java.io.InputStream fileStream, String fileName, Map<String, Object> body, Long tenantId) {
        try {
            if (fileStream == null) {
                throw new BizException(400, "上传文件不能为空");
            }
            validateMultipartFields(body);
            String boundary = "Boundary-" + java.util.UUID.randomUUID();
            var byteStream = new java.io.ByteArrayOutputStream();

            // 写入额外的表单字段
            if (body != null) {
                for (var entry : body.entrySet()) {
                    if (entry.getValue() != null) {
                        writeFormField(byteStream, boundary, entry.getKey(), String.valueOf(entry.getValue()));
                    }
                }
            }

            // 写入文件字段
            byte[] fileBytes = readBounded(fileStream, MAX_MULTIPART_FILE_BYTES, "上传文件不能超过 20MB");
            writeFileField(byteStream, boundary, "file", sanitizeMultipartFileName(fileName), fileBytes);

            // 写入结束边界
            byteStream.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));

            byte[] multipartBody = byteStream.toByteArray();

            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(normalizeBase(automationBaseUrl) + ensureSlash(path)))
                    .header(HttpHeaders.CONTENT_TYPE, "multipart/form-data; boundary=" + boundary)
                    .timeout(Duration.ofSeconds(120))
                    .POST(HttpRequest.BodyPublishers.ofByteArray(multipartBody));
            applyInternalHeaders(builder, resolveTenantId(tenantId));
            TextResponse resp = sendText(builder.build());
            ensureSuccessStatus(resp.statusCode(), resp.body());
            // 与 postInternalForData 保持一致：拆包 Python ResultObject {code,msg,data}，只返回 data 字段
            // 否则 Java 外层 Result.ok 再包一层会造成双重嵌套，前端 res.data.url 取不到值
            return asMap(dataOrSelf(parseJsonObject(resp.body())));
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "文件处理服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("调用自动化服务上传失败, path={}, errorType={}", path, e.getClass().getSimpleName());
            throw new BizException(503, "文件处理服务暂时不可用，请稍后重试");
        }
    }

    private void writeFormField(java.io.OutputStream os, String boundary, String name, String value) throws Exception {
        if (name == null || !name.matches("[A-Za-z0-9_.-]{1,80}")) {
            throw new BizException(400, "multipart 字段名非法");
        }
        os.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        os.write(("Content-Disposition: form-data; name=\"" + name + "\"\r\n").getBytes(StandardCharsets.UTF_8));
        os.write("Content-Type: text/plain; charset=UTF-8\r\n".getBytes(StandardCharsets.UTF_8));
        os.write("\r\n".getBytes(StandardCharsets.UTF_8));
        os.write(value.getBytes(StandardCharsets.UTF_8));
        os.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    private void writeFileField(java.io.OutputStream os, String boundary, String name, String fileName, byte[] data) throws Exception {
        os.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        os.write(("Content-Disposition: form-data; name=\"" + name + "\"; filename=\"" + fileName + "\"\r\n").getBytes(StandardCharsets.UTF_8));
        String extension = fileName != null && fileName.contains(".")
                ? fileName.substring(fileName.lastIndexOf('.') + 1).toLowerCase(java.util.Locale.ROOT)
                : "";
        String contentType = switch (extension) {
            case "jpg", "jpeg" -> "image/jpeg";
            case "png" -> "image/png";
            case "gif" -> "image/gif";
            case "webp" -> "image/webp";
            case "bmp" -> "image/bmp";
            default -> "application/octet-stream";
        };
        os.write(("Content-Type: " + contentType + "\r\n").getBytes(StandardCharsets.UTF_8));
        os.write("\r\n".getBytes(StandardCharsets.UTF_8));
        os.write(data);
        os.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    static String sanitizeMultipartFileName(String rawName) {
        String candidate = rawName == null ? "" : rawName.trim().replace('\\', '/');
        int slash = candidate.lastIndexOf('/');
        if (slash >= 0) candidate = candidate.substring(slash + 1);
        candidate = candidate.replaceAll("[^A-Za-z0-9._-]", "_")
                .replaceAll("^[.]+", "")
                .replaceAll("_{2,}", "_");
        if (candidate.isBlank()) candidate = "upload.bin";
        if (candidate.length() > 160) {
            int dot = candidate.lastIndexOf('.');
            String extension = dot > 0 && candidate.length() - dot <= 16 ? candidate.substring(dot) : "";
            int stemLength = Math.max(1, 160 - extension.length());
            candidate = candidate.substring(0, Math.min(stemLength, candidate.length())) + extension;
        }
        return candidate;
    }

    static byte[] readBounded(java.io.InputStream input, int maximum, String message) throws java.io.IOException {
        byte[] bytes = input.readNBytes(maximum + 1);
        if (bytes.length > maximum) {
            throw new BizException(413, message);
        }
        return bytes;
    }

    private void validateMultipartFields(Map<String, Object> body) {
        if (body == null || body.isEmpty()) return;
        if (body.size() > MAX_MULTIPART_FIELDS) {
            throw new BizException(400, "multipart 字段数量过多");
        }
        int totalBytes = 0;
        for (Map.Entry<String, Object> entry : body.entrySet()) {
            String name = entry.getKey();
            if (name == null || !name.matches("[A-Za-z0-9_.-]{1,80}")) {
                throw new BizException(400, "multipart 字段名非法");
            }
            if (entry.getValue() == null) continue;
            int bytes = String.valueOf(entry.getValue()).getBytes(StandardCharsets.UTF_8).length;
            if (bytes > MAX_MULTIPART_FIELD_BYTES) {
                throw new BizException(413, "multipart 字段内容过长");
            }
            totalBytes = Math.addExact(totalBytes, bytes);
            if (totalBytes > MAX_MULTIPART_METADATA_BYTES) {
                throw new BizException(413, "multipart 元数据过大");
            }
        }
    }

    public boolean pingInternalHealth() {
        try {
            Map<String, Object> health = get(normalizeBase(automationBaseUrl), "/health", Map.of(), false);
            log.info("Python 网关健康检查成功 baseUrl={}, keys={}", normalizeBase(automationBaseUrl), health.keySet());
            return true;
        } catch (Exception e) {
            log.warn("Python 网关健康检查失败 baseUrl={}, errorType={}", normalizeBase(automationBaseUrl), e.getClass().getSimpleName());
            return false;
        }
    }

    private Map<String, Object> postJson(String base, String path, Map<String, Object> body, boolean internal) {
        return postJson(base, path, body, internal, 30);
    }

    private Map<String, Object> postJson(String base, String path, Map<String, Object> body, boolean internal, long timeoutSeconds) {
        return postJson(base, path, body, internal, timeoutSeconds, null);
    }

    private Map<String, Object> postJson(String base, String path, Map<String, Object> body, boolean internal, long timeoutSeconds, Long tenantId) {
        try {
            byte[] json = encodeJsonRequest(body);
            long safeTimeout = Math.max(1, Math.min(timeoutSeconds, 180));
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(base + ensureSlash(path)))
                    .header(HttpHeaders.CONTENT_TYPE, "application/json")
                    .timeout(Duration.ofSeconds(safeTimeout))
                    .POST(HttpRequest.BodyPublishers.ofByteArray(json));
            if (internal) {
                applyInternalHeaders(builder, resolveTenantId(tenantId));
            }
            TextResponse resp = sendText(builder.build());
            ensureSuccessStatus(resp.statusCode(), resp.body());
            return parseJsonObject(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("调用依赖服务失败, method=POST, base={}, path={}, errorType={}", base, path, e.getClass().getSimpleName());
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        }
    }

    private Map<String, Object> putJson(String base, String path, Map<String, Object> body, boolean internal) {
        return putJson(base, path, body, internal, null);
    }

    private Map<String, Object> putJson(String base, String path, Map<String, Object> body, boolean internal, Long tenantId) {
        try {
            byte[] json = encodeJsonRequest(body);
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(base + ensureSlash(path)))
                    .header(HttpHeaders.CONTENT_TYPE, "application/json")
                    .timeout(Duration.ofSeconds(30))
                    .PUT(HttpRequest.BodyPublishers.ofByteArray(json));
            if (internal) {
                applyInternalHeaders(builder, resolveTenantId(tenantId));
            }
            TextResponse resp = sendText(builder.build());
            ensureSuccessStatus(resp.statusCode(), resp.body());
            return parseJsonObject(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("调用依赖服务失败, method=PUT, base={}, path={}, errorType={}", base, path, e.getClass().getSimpleName());
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        }
    }

    private Map<String, Object> get(String base, String path, Map<String, ?> query, boolean internal) {
        return get(base, path, query, internal, 30);
    }

    private Map<String, Object> get(String base, String path, Map<String, ?> query, boolean internal, long timeoutSeconds) {
        return get(base, path, query, internal, timeoutSeconds, null);
    }

    private Map<String, Object> get(String base, String path, Map<String, ?> query, boolean internal, long timeoutSeconds, Long tenantId) {
        try {
            String url = base + ensureSlash(path) + toQuery(query);
            long safeTimeout = Math.max(1, Math.min(timeoutSeconds, 180));
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(safeTimeout))
                    .GET();
            if (internal) {
                applyInternalHeaders(builder, resolveTenantId(tenantId));
            }
            TextResponse resp = sendText(builder.build());
            ensureSuccessStatus(resp.statusCode(), resp.body());
            return parseJsonObject(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("调用依赖服务失败, method=GET, base={}, path={}, errorType={}", base, path, e.getClass().getSimpleName());
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        }
    }

    private Map<String, Object> delete(String base, String path, boolean internal) {
        return delete(base, path, internal, null);
    }

    private Map<String, Object> delete(String base, String path, boolean internal, Long tenantId) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(base + ensureSlash(path)))
                    .timeout(Duration.ofSeconds(30))
                    .DELETE();
            if (internal) {
                applyInternalHeaders(builder, resolveTenantId(tenantId));
            }
            TextResponse resp = sendText(builder.build());
            ensureSuccessStatus(resp.statusCode(), resp.body());
            return parseJsonObject(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        } catch (Exception e) {
            log.error("调用依赖服务失败, method=DELETE, base={}, path={}, errorType={}", base, path, e.getClass().getSimpleName());
            throw new BizException(503, "依赖服务暂时不可用，请稍后重试");
        }
    }


    private void applyInternalHeaders(HttpRequest.Builder builder, Long tenantId) {
        String token = effectiveInternalToken();
        if (token == null || token.isBlank()) {
            throw new IllegalStateException("INTERNAL_API_TOKEN 未配置，拒绝调用内部服务");
        }
        if (tenantId == null) {
            throw new IllegalStateException("租户上下文为空，拒绝调用内部服务");
        }
        builder.header("X-Internal-Token", token);
        builder.header("X-Internal-Tenant-Id", String.valueOf(tenantId));
        String requestId = MDC.get("requestId");
        if (requestId != null && !requestId.isBlank()) {
            builder.header("X-Request-Id", requestId);
        }
    }

    private byte[] encodeJsonRequest(Map<String, Object> body) throws Exception {
        byte[] bytes = objectMapper.writeValueAsBytes(body == null ? Map.of() : body);
        if (bytes.length > MAX_JSON_REQUEST_BYTES) {
            throw new BizException(413, "请求内容过大");
        }
        return bytes;
    }

    private TextResponse sendText(HttpRequest request) throws java.io.IOException, InterruptedException {
        HttpResponse<java.io.InputStream> response = httpClient.send(
                request,
                HttpResponse.BodyHandlers.ofInputStream()
        );
        return new TextResponse(
                response.statusCode(),
                readResponseText(response.body(), MAX_JSON_RESPONSE_BYTES)
        );
    }

    static String readResponseText(java.io.InputStream input, int maximum) throws java.io.IOException {
        try (java.io.InputStream stream = input) {
            byte[] bytes = stream.readNBytes(maximum + 1);
            if (bytes.length > maximum) {
                throw new BizException(502, "依赖服务响应超过安全上限");
            }
            return new String(bytes, StandardCharsets.UTF_8);
        }
    }

    private record TextResponse(int statusCode, String body) {}

    private Long resolveTenantId(Long tenantId) {
        return tenantId != null ? tenantId : com.xianyu.admin.security.TenantContext.getCurrentTenantId();
    }

    /**
     * 本地开发兜底：有些启动方式会把 INTERNAL_API_TOKEN 注入为空字符串，导致
     * application.yml 的默认值不会生效。生产/预发环境已由 StartupSecurityGuard
     * 阻断弱令牌，这里仅避免 dev 环境因为空 env 造成 Java 无法调用 Python。
     */
    private String effectiveInternalToken() {
        if (internalToken != null && !internalToken.isBlank()) {
            return internalToken.trim();
        }
        log.warn("INTERNAL_API_TOKEN 为空，当前按本地开发模式使用默认内部令牌。生产环境会在启动门禁中拒绝该配置。");
        return DEV_INTERNAL_TOKEN;
    }

    private Map<String, Object> parseJsonObject(String body) throws Exception {
        if (body == null || body.isBlank()) return new LinkedHashMap<>();
        String trimmed = body.strip();
        if (!(trimmed.startsWith("{") || trimmed.startsWith("["))) {
            throw new BizException(502, "依赖服务返回了无法识别的数据格式");
        }
        JsonNode node = objectMapper.readTree(trimmed);
        if (node.isObject()) {
            return objectMapper.convertValue(node, new TypeReference<LinkedHashMap<String, Object>>() {});
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("data", objectMapper.convertValue(node, Object.class));
        return result;
    }

    private void ensureSuccessStatus(int statusCode, String body) {
        if (statusCode >= 400) {
            int safeStatus = switch (statusCode) {
                case 400, 404, 409, 410, 422, 429 -> statusCode;
                case 401, 403 -> 503;
                default -> statusCode >= 500 ? 503 : 502;
            };
            throw new BizException(safeStatus, downstreamMessage(safeStatus));
        }
    }

    private String abbreviate(String text) {
        if (text == null) return "";
        String normalized = text.replaceAll("\\s+", " ").trim();
        return normalized.length() > 300 ? normalized.substring(0, 300) + "..." : normalized;
    }

    private Object dataOrSelf(Map<String, Object> raw) {
        assertBusinessSuccess(raw);
        Object code = raw.get("code");
        if (code != null && String.valueOf(code).matches("200|0")) {
            return raw.get("data");
        }
        return raw;
    }

    private void assertBusinessSuccess(Map<String, Object> raw) {
        if (raw == null || !raw.containsKey("code")) return;
        Object code = raw.get("code");
        if (code == null || String.valueOf(code).matches("200|0")) return;
        Object msg = raw.get("msg");
        if (msg == null) msg = raw.get("message");
        String downstreamMsg = msg == null ? "" : String.valueOf(msg).trim();
        int status;
        try {
            status = Integer.parseInt(String.valueOf(code));
        } catch (NumberFormatException ignored) {
            status = 502;
        }
        if (status == 401 || status == 403) status = 409;
        else if (status >= 500) status = 503;
        else if (status < 400 || status > 499) status = 502;
        String baseMsg = downstreamMessage(status);
        // 业务拒绝（422）下游已经返回面向用户的中文原因（如"商品发布被平台拒绝：xxx"），
        // 直接透传避免被"依赖服务暂时不可用"误导成服务故障；
        // 仅当下游没有给出可读消息时才退回到通用 baseMsg。
        String fullMsg;
        if (status == 422 && !downstreamMsg.isEmpty()) {
            fullMsg = downstreamMsg;
        } else {
            fullMsg = downstreamMsg.isEmpty() ? baseMsg : baseMsg + ": " + downstreamMsg;
        }
        log.warn("下游服务返回业务错误, code={}, status={}, downstreamMsg={}", code, status, downstreamMsg);
        throw new BizException(status, fullMsg);
    }

    private String downstreamMessage(int status) {
        return switch (status) {
            case 400 -> "依赖服务拒绝了请求参数";
            case 404 -> "请求的下游资源不存在";
            case 409 -> "请求与下游资源当前状态冲突";
            case 410 -> "该下游能力已停止提供";
            case 422 -> "依赖服务无法处理当前请求";
            case 429 -> "依赖服务请求过于频繁，请稍后重试";
            case 503 -> "依赖服务暂时不可用，请稍后重试";
            default -> "依赖服务返回了无效响应";
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((k, v) -> result.put(String.valueOf(k), v));
            return result;
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("value", value);
        return result;
    }

    private String toQuery(Map<String, ?> query) {
        if (query == null || query.isEmpty()) return "";
        String q = query.entrySet().stream()
                .filter(e -> e.getValue() != null)
                .map(e -> URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8) + "="
                        + URLEncoder.encode(String.valueOf(e.getValue()), StandardCharsets.UTF_8))
                .collect(Collectors.joining("&"));
        return q.isBlank() ? "" : "?" + q;
    }

    private String normalizeBase(String base) {
        if (base == null || base.isBlank()) return "http://localhost:12401";
        String normalized = base.trim();
        return normalized.endsWith("/") ? normalized.substring(0, normalized.length() - 1) : normalized;
    }

    private String ensureSlash(String path) {
        if (path == null || path.isBlank()) return "/";
        return path.startsWith("/") ? path : "/" + path;
    }
}
