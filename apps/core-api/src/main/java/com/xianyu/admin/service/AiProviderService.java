package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * AI Provider 抽象层。
 * 当前支持 OpenAI-compatible /chat/completions 协议；未配置时自动降级，由业务层使用本地启发式兜底。
 *
 * 冷启动优化：
 * - @PostConstruct 预热 HTTP 连接、DNS 缓存和 TLS Session
 * - 请求超时最低 60 秒，覆盖 AI 供应商冷启动延迟
 * - 指数退避重试（1s → 2s → 4s），提升首次调用成功率
 */
@Service
public class AiProviderService {
    private static final Logger log = LoggerFactory.getLogger(AiProviderService.class);
    static final int MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)  // 许多 AI 供应商/代理不支持 HTTP/2
            .followRedirects(HttpClient.Redirect.NEVER)
            .connectTimeout(Duration.ofSeconds(15))
            .build();
    private final AiBillingService aiBillingService;
    private final ModelConfigService modelConfigService;
    private final AiProviderEndpointPolicy endpointPolicy;

    @Autowired
    public AiProviderService(AiBillingService aiBillingService, ModelConfigService modelConfigService,
                             AiProviderEndpointPolicy endpointPolicy) {
        this.aiBillingService = aiBillingService;
        this.modelConfigService = modelConfigService;
        this.endpointPolicy = endpointPolicy;
    }

    AiProviderService(AiBillingService aiBillingService, ModelConfigService modelConfigService) {
        this(aiBillingService, modelConfigService, new AiProviderEndpointPolicy(""));
    }

    /**
     * 预热 HTTP 连接池、DNS 缓存和 TLS Session，消除首次调用的冷启动延迟。
     * 向 AI 供应商的 /models 端点发起一个轻量 GET 请求，不依赖具体模型配置。
     * 即使预热失败也不阻断服务启动。
     */
    @PostConstruct
    void warmUpHttpClient() {
        try {
            Map<String, Object> cfg = modelConfigService.getGeneralConfig();
            if (cfg == null || cfg.isEmpty()) return;
            Object rawUrl = cfg.get("baseUrl");
            if (rawUrl == null || String.valueOf(rawUrl).isBlank()) return;
            String warmupUrl = validatedBaseUrl(String.valueOf(rawUrl)) + "/models";
            HttpRequest req = HttpRequest.newBuilder(URI.create(warmupUrl))
                    .timeout(Duration.ofSeconds(5))
                    .GET()
                    .build();
            httpClient.send(req, HttpResponse.BodyHandlers.discarding());
            log.info("[AiProvider] 连接预热完成");
        } catch (Exception e) {
            // 预热失败不影响服务，仅记日志
            log.debug("[AiProvider] 连接预热跳过, errorType={}", e.getClass().getSimpleName());
        }
    }

    @Value("${xianyu.ai.provider.enabled:${AI_PROVIDER_ENABLED:false}}")
    private boolean enabled;

    @Value("${xianyu.ai.provider.base-url:${AI_PROVIDER_BASE_URL:}}")
    private String baseUrl;

    @Value("${xianyu.ai.provider.api-key:${AI_PROVIDER_API_KEY:}}")
    private String apiKey;

    @Value("${xianyu.ai.provider.model:${AI_PROVIDER_MODEL:gpt-4o-mini}}")
    private String model;

    @Value("${xianyu.ai.provider.timeout-seconds:${AI_PROVIDER_TIMEOUT_SECONDS:30}}")
    private int timeoutSeconds;

    public Map<String, Object> generateText(String scene, String systemPrompt, String userPrompt, double temperature) {
        return generateText(scene, systemPrompt, userPrompt, temperature, true);
    }

    public Map<String, Object> generateText(String scene, String systemPrompt, String userPrompt, double temperature, boolean billable) {
        validateRequest(scene, systemPrompt, userPrompt, temperature);
        Map<String, Object> result = new LinkedHashMap<>();
        String requestId = UUID.randomUUID().toString();
        result.put("requestId", requestId);
        result.put("scene", scene);
        Map<String, Object> cfg = effectiveTextConfig();
        String providerName = modelConfigService.textConfig(cfg, "openai-compatible", "providerName", "provider");
        String effectiveModel = modelConfigService.textConfig(cfg, model, "defaultModel", "modelName", "model");
        String effectiveBaseUrl = modelConfigService.textConfig(cfg, baseUrl, "baseUrl");
        String effectiveApiKey = modelConfigService.textConfig(cfg, apiKey, "apiKey");
        int effectiveTimeout = (int) modelConfigService.longConfig(cfg, timeoutSeconds, "requestTimeout", "timeoutSeconds", "timeout");
        result.put("provider", providerName);
        result.put("model", effectiveModel);
        result.put("configured", isConfigured());
        if (!isConfigured()) {
            throw new BizException(503, "AI 文本服务尚未配置，当前不可用");
        }
        if (billable) precheckBilling(scene, systemPrompt, userPrompt);
        try {
            String endpoint = validatedBaseUrl(effectiveBaseUrl) + "/chat/completions";
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("model", effectiveModel);
            payload.put("temperature", temperature);
            payload.put("messages", List.of(
                    Map.of("role", "system", "content", systemPrompt == null ? "" : systemPrompt),
                    Map.of("role", "user", "content", userPrompt == null ? "" : userPrompt)
            ));
            String body = objectMapper.writeValueAsString(payload);
            HttpRequest req = HttpRequest.newBuilder(URI.create(endpoint))
                    // 最小超时 60 秒，覆盖 AI 供应商冷启动/模型加载延迟
                    .timeout(Duration.ofSeconds(Math.max(effectiveTimeout, 60)))
                    .header("Authorization", "Bearer " + effectiveApiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();
            // 最多尝试 3 次（第1次 + 最多2次重试），仅对 IO 异常（Connection reset / Broken pipe / timeout 等）重试。
            // 指数退避间隔：1s → 2s，给冷启动场景更多恢复时间。
            // A reset/timeout after the provider accepted a request is
            // ambiguous. Retrying a billable generation can create duplicate
            // upstream cost without an idempotency contract, so only
            // non-billable administrative probes may retry automatically.
            int maxAttempts = maxProviderAttempts(billable);
            Exception lastException = null;
            for (int attempt = 0; attempt < maxAttempts; attempt++) {
                if (attempt > 0) {
                    long backoffMs = 1000L * (1L << (attempt - 1)); // 1s → 2s
                    try { Thread.sleep(backoffMs); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                }
                try {
                    LimitedResponse resp = sendWithLimitedBody(req);
                    result.put("httpStatus", resp.statusCode());
                    if (resp.statusCode() < 200 || resp.statusCode() >= 300) {
                        log.warn("AI Provider 请求失败, status={}, requestId={}, responseBytes={}",
                                resp.statusCode(), requestId, resp.bodyBytes());
                        if (resp.statusCode() == 429) {
                            throw new BizException(429, "AI 服务请求过于频繁，请稍后重试");
                        }
                        throw new BizException(502, "AI 上游服务响应异常，请稍后重试");
                    }
                    Map<String, Object> parsed = objectMapper.readValue(resp.body(), new TypeReference<Map<String, Object>>() {});
                    String content = extractContent(parsed);
                    if (content == null || content.isBlank()) {
                        throw new BizException(502, "AI 上游服务未返回有效内容");
                    }
                    result.put("ok", true);
                    result.put("content", content);
                    Object usage = parsed.getOrDefault("usage", Map.of());
                    result.put("usage", usage);
                    if (billable && Boolean.TRUE.equals(result.get("ok"))) {
                        result.put("billing", recordBilling(scene, requestId, usage));
                    }
                    return result;
                } catch (ProviderResponseTooLargeException tooLarge) {
                    throw new BizException(502, "AI 上游服务响应超过安全限制，请稍后重试");
                } catch (IOException ioe) {
                    lastException = ioe;
                    if (attempt < maxAttempts - 1) {
                        String msg = ioe.getMessage() != null ? ioe.getMessage().toLowerCase() : "";
                        boolean retryable = msg.contains("connection reset") || msg.contains("broken pipe")
                            || msg.contains("connection refused") || msg.contains("connection timed out")
                            || msg.contains("timeout") || msg.contains("abort");
                        if (!retryable) break;
                        continue;
                    }
                }
            }
            log.error("AI Provider 网络调用失败, requestId={}, errorType={}", requestId, lastException.getClass().getSimpleName());
            throw new BizException(503, "AI 服务网络暂时不可用，请稍后重试");
        } catch (BizException e) {
            throw e;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BizException(503, "AI 请求已中断，请稍后重试");
        } catch (Exception e) {
            log.error("AI Provider 调用失败, requestId={}, errorType={}", requestId, e.getClass().getSimpleName());
            throw new BizException(503, "AI 服务暂时不可用，请稍后重试");
        }
    }

    private LimitedResponse sendWithLimitedBody(HttpRequest request)
            throws IOException, InterruptedException {
        HttpResponse<InputStream> response = httpClient.send(
                request,
                HttpResponse.BodyHandlers.ofInputStream()
        );
        try (InputStream input = response.body()) {
            long declaredLength = response.headers().firstValueAsLong("Content-Length").orElse(-1L);
            if (declaredLength > MAX_PROVIDER_RESPONSE_BYTES) {
                throw new ProviderResponseTooLargeException();
            }
            byte[] bytes = readResponseBodyLimited(input, MAX_PROVIDER_RESPONSE_BYTES);
            return new LimitedResponse(
                    response.statusCode(),
                    new String(bytes, StandardCharsets.UTF_8),
                    bytes.length
            );
        }
    }

    static byte[] readResponseBodyLimited(InputStream input, int maxBytes) throws IOException {
        if (input == null || maxBytes <= 0) {
            throw new IllegalArgumentException("response input and maxBytes are required");
        }
        byte[] bytes = input.readNBytes(maxBytes + 1);
        if (bytes.length > maxBytes) {
            throw new ProviderResponseTooLargeException();
        }
        return bytes;
    }

    static int maxProviderAttempts(boolean billable) {
        return billable ? 1 : 3;
    }

    private record LimitedResponse(int statusCode, String body, int bodyBytes) {}

    static final class ProviderResponseTooLargeException extends IOException {
        private ProviderResponseTooLargeException() {
            super("provider response exceeded the configured byte limit");
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> recordBilling(String scene, String requestId, Object usageObj) {
        Long userId = UserContext.userId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "用户或租户登录状态已失效");
        Map<String, Object> usage = billingUsage(scene, userId, tenantId);
        usage.put("requestId", requestId);
        if (usageObj instanceof Map<?, ?> raw) {
            for (String key : List.of(
                    "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens",
                    "promptTokens", "completionTokens", "totalTokens", "cachedTokens",
                    "prompt_tokens_details")) {
                if (raw.containsKey(key)) usage.put(key, raw.get(key));
            }
            usage.put("rawUsage", raw);
        }
        Map<String, Object> charged = aiBillingService.charge(usage);
        Map<String, Object> billing = new LinkedHashMap<>();
        billing.put("charged", true);
        billing.putAll(charged);
        return billing;
    }

    private void precheckBilling(String scene, String systemPrompt, String userPrompt) {
        Long userId = UserContext.userId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "用户或租户登录状态已失效");
        Map<String, Object> usage = billingUsage(scene, userId, tenantId);
        long estimatedPromptTokens = Math.max(1L,
                ((long) (systemPrompt == null ? 0 : systemPrompt.length())
                        + (userPrompt == null ? 0 : userPrompt.length()) + 1L) / 2L);
        usage.put("promptTokens", estimatedPromptTokens);
        usage.put("completionTokens", 0L);
        aiBillingService.precheck(usage);
    }

    private Map<String, Object> billingUsage(String scene, Long userId, Long tenantId) {
        Map<String, Object> usage = new LinkedHashMap<>();
        usage.put("tenantId", tenantId);
        usage.put("userId", userId);
        usage.put("scene", scene);
        Map<String, Object> cfg = effectiveTextConfig();
        usage.put("providerName", modelConfigService.textConfig(cfg, "openai-compatible", "providerName", "provider"));
        usage.put("modelName", modelConfigService.textConfig(cfg, model, "defaultModel", "modelName", "model"));
        usage.put("modelType", "chat");
        return usage;
    }

    private void validateRequest(String scene, String systemPrompt, String userPrompt, double temperature) {
        if (scene == null || scene.isBlank() || scene.length() > 80
                || !scene.matches("[A-Za-z0-9._:-]+")) {
            throw new BizException(400, "AI 场景标识非法");
        }
        if (systemPrompt != null && systemPrompt.length() > 20_000) {
            throw new BizException(400, "系统提示词过长");
        }
        if (userPrompt == null || userPrompt.isBlank()) {
            throw new BizException(400, "AI 请求内容不能为空");
        }
        if (userPrompt.length() > 50_000) {
            throw new BizException(400, "AI 请求内容过长");
        }
        if (!Double.isFinite(temperature) || temperature < 0D || temperature > 2D) {
            throw new BizException(400, "temperature 必须在 0 到 2 之间");
        }
    }

    public boolean isConfigured() {
        // Runtime AI rewrite is controlled strictly by admin-web 通用模型配置.
        // Environment variables are not enough to open the frontend feature, avoiding accidental use when backend has not enabled it.
        return modelConfigService.isGeneralTextConfigured();
    }

    public Map<String, Object> status() {
        Map<String, Object> general = modelConfigService.getGeneralConfig();
        Map<String, Object> image = modelConfigService.getImageConfig();
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("configured", isConfigured());
        res.put("rewriteEnabled", isConfigured());
        res.put("provider", modelConfigService.textConfig(general, "openai-compatible", "providerName", "provider"));
        res.put("model", modelConfigService.textConfig(general, model, "defaultModel", "modelName", "model"));
        res.put("imageConfigured", modelConfigService.isImageConfigured());
        res.put("imageModel", modelConfigService.textConfig(image, "", "modelName", "defaultModel", "model"));
        res.put("imageSize", modelConfigService.textConfig(image, "1024x1024", "imageSize"));
        res.put("imageTokensPerImage", modelConfigService.longConfig(image, 0, "tokensPerImage", "tokenCostPerImage", "imageTokenCost"));
        res.put("imageDefaultPrompt", modelConfigService.textConfig(image, "生成一张真实、干净、适合闲鱼商品发布的商品主图。突出商品主体，背景简洁，避免文字水印和夸大宣传。", "defaultSystemPrompt", "systemPrompt", "defaultPrompt"));
        return res;
    }

    private Map<String, Object> effectiveTextConfig() {
        return modelConfigService.getGeneralConfig();
    }

    private String normalizedBaseUrl(String raw) {
        String s = raw == null ? "" : raw.trim();
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        if (s.endsWith("/v1")) return s;
        return s + "/v1";
    }

    private String validatedBaseUrl(String raw) {
        return normalizedBaseUrl(endpointPolicy.validateBaseUrl(raw));
    }

    @SuppressWarnings("unchecked")
    private String extractContent(Map<String, Object> parsed) {
        Object choicesObj = parsed.get("choices");
        if (!(choicesObj instanceof List<?> choices) || choices.isEmpty()) return "";
        Object first = choices.get(0);
        if (!(first instanceof Map<?, ?> choice)) return "";
        Object messageObj = choice.get("message");
        if (messageObj instanceof Map<?, ?> message) {
            Object content = message.get("content");
            return content == null ? "" : String.valueOf(content);
        }
        Object text = choice.get("text");
        return text == null ? "" : String.valueOf(text);
    }

    private String abbreviate(String s, int len) {
        if (s == null) return "";
        return s.length() > len ? s.substring(0, len) : s;
    }
}
