package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.config.UploadPathConfig;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import javax.imageio.ImageIO;
import javax.net.ssl.SSLContext;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.concurrent.TimeUnit;

/**
 * 优化后的 AI 生图服务。
 *
 * 核心改进：
 * 1. 多重生成方法自动切换 (Proxy → Async+Poll → Direct Sync)
 * 2. 图片有效性验证（非空白检测）
 * 3. 超时检测与合理延长（默认200秒轮询，前端超时240秒）
 * 4. 自动重试与异常降级
 * 5. 历史图片记录与恢复
 */
@Service
public class ImageGenerationService {
    private static final Logger log = LoggerFactory.getLogger(ImageGenerationService.class);

    private final ModelConfigService modelConfigService;
    private final JdbcTemplate jdbcTemplate;
    private final AiProviderService aiProviderService;
    private final ImageProxyService imageProxyService;
    private final ImageCacheService imageCacheService;
    private final CookieCryptoService sensitiveValueCrypto;
    private final UploadPathConfig uploadPaths;
    private final UploadedImageValidator uploadedImageValidator;
    private final UploadStorageGovernanceService storageGovernance;
    private final AiProviderEndpointPolicy endpointPolicy;
    private final TransactionTemplate transactionTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient httpClient = createHttpClient();

    private static HttpClient createHttpClient() {
        try {
            // 限制 TLS 1.2（部分 AI 供应商/代理不支持 TLS 1.3，会 reset 连接）
            SSLContext sslContext = SSLContext.getInstance("TLSv1.2");
            sslContext.init(null, null, null);
            return HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)   // 许多 AI 供应商/代理不支持 HTTP/2
                    .sslContext(sslContext)
                    .followRedirects(HttpClient.Redirect.NEVER)
                    .connectTimeout(Duration.ofSeconds(30))
                    .build();
        } catch (Exception e) {
            log.warn("[生图] 创建 SSLContext 失败，使用默认配置, errorType={}", e.getClass().getSimpleName());
            return HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .followRedirects(HttpClient.Redirect.NEVER)
                    .connectTimeout(Duration.ofSeconds(30))
                    .build();
        }
    }

    private LimitedResponse sendLimited(HttpRequest request) throws IOException, InterruptedException {
        HttpResponse<InputStream> response = httpClient.send(
                request, HttpResponse.BodyHandlers.ofInputStream());
        try (InputStream input = response.body()) {
            byte[] bytes = input.readNBytes(MAX_PROVIDER_RESPONSE_BYTES + 1);
            if (bytes.length > MAX_PROVIDER_RESPONSE_BYTES) {
                throw new IOException("image provider response exceeds the size limit");
            }
            return new LimitedResponse(
                    response.statusCode(), new String(bytes, StandardCharsets.UTF_8));
        }
    }

    private record LimitedResponse(int statusCode, String body) {}

    /** 图片最小有效字节数（低于此值视为空白/无效图片） */
    private static final long MIN_VALID_IMAGE_BYTES = 1024;

    /** 每张图片最大下载字节数 */
    private static final long MAX_IMAGE_DOWNLOAD_BYTES = 5L * 1024 * 1024;
    private static final int MAX_PROVIDER_RESPONSE_BYTES = 16 * 1024 * 1024;

    /** 轮询最大等待毫秒数（实际平均100秒，设200秒足够） */
    private static final long POLL_MAX_WAIT_MS = 230_000;

    /** 轮询间隔 */
    private static final long POLL_INTERVAL_MS = 2_000;

    /** 方法间切换重试间隔 */
    private static final long METHOD_SWITCH_DELAY_MS = 1_000;

    /** 每个方法的内部重试次数 */
    private static final int METHOD_RETRY_COUNT = 2;

    /** 最大生成图片数 */
    private static final int MAX_IMAGE_COUNT = 9;

    /** 默认每张图片Token消耗 */
    private static final long DEFAULT_TOKENS_PER_IMAGE = 50;

    @Autowired
    public ImageGenerationService(ModelConfigService modelConfigService, JdbcTemplate jdbcTemplate,
                                   AiProviderService aiProviderService,
                                   ImageProxyService imageProxyService, ImageCacheService imageCacheService,
                                   CookieCryptoService sensitiveValueCrypto,
                                   PlatformTransactionManager transactionManager,
                                   UploadPathConfig uploadPaths,
                                   UploadedImageValidator uploadedImageValidator,
                                   UploadStorageGovernanceService storageGovernance,
                                   AiProviderEndpointPolicy endpointPolicy) {
        this.modelConfigService = modelConfigService;
        this.jdbcTemplate = jdbcTemplate;
        this.aiProviderService = aiProviderService;
        this.imageProxyService = imageProxyService;
        this.imageCacheService = imageCacheService;
        this.sensitiveValueCrypto = sensitiveValueCrypto;
        this.uploadPaths = uploadPaths;
        this.uploadedImageValidator = uploadedImageValidator;
        this.storageGovernance = storageGovernance;
        this.endpointPolicy = endpointPolicy;
        this.transactionTemplate = transactionManager == null ? null : new TransactionTemplate(transactionManager);
    }

    ImageGenerationService(ModelConfigService modelConfigService, JdbcTemplate jdbcTemplate,
                           AiProviderService aiProviderService,
                           ImageProxyService imageProxyService, ImageCacheService imageCacheService,
                           CookieCryptoService sensitiveValueCrypto) {
        this(modelConfigService, jdbcTemplate, aiProviderService, imageProxyService, imageCacheService,
                sensitiveValueCrypto, null, new UploadPathConfig("uploads"),
                new UploadedImageValidator(), null, new AiProviderEndpointPolicy(""));
    }

    ImageGenerationService(ModelConfigService modelConfigService, JdbcTemplate jdbcTemplate,
                           AiProviderService aiProviderService,
                           ImageProxyService imageProxyService, ImageCacheService imageCacheService,
                           CookieCryptoService sensitiveValueCrypto,
                           PlatformTransactionManager transactionManager) {
        this(modelConfigService, jdbcTemplate, aiProviderService, imageProxyService, imageCacheService,
                sensitiveValueCrypto, transactionManager,
                new UploadPathConfig("uploads"), new UploadedImageValidator(), null,
                new AiProviderEndpointPolicy(""));
    }

    // ==================== 公开接口 ====================

    /** 查询生图配置状态 */
    public Map<String, Object> status() {
        List<Map<String, Object>> models = new ArrayList<>();
        List<Map<String, Object>> allConfigs = modelConfigService.getAllImageConfigs();

        for (Map<String, Object> cfg : allConfigs) {
            String moduleKey = (String) cfg.get("moduleKey");
            boolean enabled = modelConfigService.isEnabled(cfg);
            String configuredProviderMode = normalizeProviderMode(modelConfigService.textConfig(cfg, "openai-compatible", "providerMode"));
            String resolvedProviderMode = resolveProviderMode(cfg);
            Map<String, Object> modelInfo = new LinkedHashMap<>();
            modelInfo.put("moduleKey", moduleKey);
            modelInfo.put("configured", enabled && hasText(cfg.get("baseUrl")) && hasText(cfg.get("apiKey")) && hasText(modelConfigService.first(cfg, "modelName", "defaultModel", "model")));
            modelInfo.put("enabled", enabled);
            modelInfo.put("model", modelConfigService.textConfig(cfg, "", "modelName", "defaultModel", "model"));
            modelInfo.put("size", normalizeSize(modelConfigService.textConfig(cfg, "1024x1024", "imageSize")));
            modelInfo.put("tokensPerImage", tokensPerImage(cfg));
            modelInfo.put("defaultPrompt", defaultPrompt(cfg));
            modelInfo.put("providerName", modelConfigService.textConfig(cfg, "", "providerName"));
            modelInfo.put("providerMode", configuredProviderMode);
            modelInfo.put("resolvedProviderMode", resolvedProviderMode);
            modelInfo.put("asyncRecommended", !"chat-completions-image".equals(configuredProviderMode) && !configuredProviderMode.equals(resolvedProviderMode));
            modelInfo.put("providerDocUrl", modelConfigService.textConfig(cfg, "", "providerDocUrl"));
            modelInfo.put("providerDocText", modelConfigService.textConfig(cfg, "", "providerDocText"));
            modelInfo.put("name", getModelDisplayName(moduleKey));
            models.add(modelInfo);
        }

        Map<String, Object> res = new LinkedHashMap<>();
        res.put("models", models);
        // 向后兼容
        if (!models.isEmpty()) {
            Map<String, Object> first = models.get(0);
            res.put("configured", first.get("configured"));
            res.put("model", first.get("model"));
            res.put("size", first.get("size"));
            res.put("tokensPerImage", first.get("tokensPerImage"));
            res.put("defaultPrompt", first.get("defaultPrompt"));
        } else {
            res.put("configured", false);
        }
        return res;
    }

    private String getModelDisplayName(String moduleKey) {
        return switch (moduleKey) {
            case "model-config-image" -> "生图模型1";
            case "model-config-image-2" -> "生图模型2";
            case "model-config-image-3" -> "生图模型3";
            default -> moduleKey;
        };
    }

    /**
     * 核心生图方法（含多重生成、图片验证、重试机制）。
     *
     * 方法切换链：
     *   1) Proxy模式（使用分发服务器地址，最稳定）
     *   2) Async+Poll模式（原始方式，异步提交+轮询）
     *   3) Direct Sync模式（同步等待，直接返回）
     */
    public Map<String, Object> generate(Map<String, Object> body) {
        String modelKey = text(body.get("modelKey"), ModelConfigService.IMAGE);
        return generateWithModel(modelKey, body);
    }

    private Map<String, Object> generateWithModel(String modelKey, Map<String, Object> body) {
        Map<String, Object> cfg = modelConfigService.getImageConfigByKey(modelKey);
        if (!modelConfigService.isEnabled(cfg)) {
            throw new BizException(503, "图片生成功能尚未配置，当前不可用");
        }
        Long userId = UserContext.userId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) tenantId = UserContext.getTenantId();
        if (userId == null) throw new BizException(401, "请先登录");
        if (tenantId == null) throw new BizException(401, "租户登录状态已失效");

        int count = parseImageCount(body.get("count"));
        String size = normalizeSize(text(body.get("size"),
                modelConfigService.textConfig(cfg, "1024x1024", "imageSize")));
        String prompt = text(body.get("prompt"), "").trim();
        String itemTitle = text(body.get("itemTitle"), "");
        String itemDesc = text(body.get("itemDescription"), "");
        String promptMode = text(body.get("promptMode"), "default");
        String customPrompt = text(body.get("customPrompt"), "");
        String systemPrompt = text(body.get("systemPrompt"), defaultPrompt(cfg));
        List<Map<String, Object>> promptConfigs = modelConfigService.getEnabledImagePromptConfigs();
        String resolvedSystemPrompt = resolveImagePromptWithAi(
                promptMode,
                customPrompt,
                systemPrompt,
                itemTitle,
                itemDesc,
                promptConfigs
        );
        String finalPrompt = buildPrompt(resolvedSystemPrompt, prompt, itemTitle, itemDesc);
        if (finalPrompt.isBlank()) throw new BizException(400, "请输入生图提示词");

        long perImage = tokensPerImage(cfg);
        long chargeTokens = perImage * count;
        // 成本（分）= 每张成本(元) × 张数 × 100；用于 AI 调用日志展示精准费用
        long costCent = calcCostCent(cfg, count);
        String baseUrl = modelConfigService.textConfig(cfg, "", "baseUrl");
        String apiKey = modelConfigService.textConfig(cfg, "", "apiKey");
        String model = modelConfigService.textConfig(cfg, "", "modelName", "defaultModel", "model");
        int configTimeout = (int) Math.min(modelConfigService.longConfig(cfg, 120, "requestTimeout", "timeoutSeconds", "timeout"), 200);
        String requestId = UUID.randomUUID().toString();
        long start = System.currentTimeMillis();
        long before = 0;
        boolean billingCommitted = false;

        try {
            // 检查余额
            before = currentBalance(userId);
            if (chargeTokens > 0 && before < chargeTokens) {
                throw new BizException(402, "Token 余额不足，生成 " + count + " 张图片需要 " + chargeTokens + " Token");
            }

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("model", model);
            payload.put("prompt", finalPrompt);
            payload.put("n", count);
            payload.put("size", size);
            payload.put("response_format", "url");
            String quality = modelConfigService.textConfig(cfg, "", "quality");
            if (!quality.isBlank() && !quality.contains("标准")) payload.put("quality", "hd");

            // ==================== 多重生图方法链 ====================
            // 根据 providerMode 选择主策略，其余方法保留作为兜底，确保高可用：
            //   openai-compatible -> 优先 Direct Sync（标准 OpenAI 兼容同步接口）
            //   async-poll       -> 优先 Proxy / Async+Poll（异步提交 + 轮询）
            //   webhook-callback -> 优先 异步兜底（异步提交，依赖服务端回调/轮询）
            String configuredProviderMode = normalizeProviderMode(modelConfigService.textConfig(cfg, "openai-compatible", "providerMode"));
            String providerMode = resolveProviderMode(cfg);
            if (!configuredProviderMode.equals(providerMode)) {
                log.info("[生图] 自动切换 providerMode: {} -> {}, modelKey={}", configuredProviderMode, providerMode, modelKey);
            }
            List<String> methodChain = buildMethodChain(providerMode, cfg, baseUrl);

            List<Map<String, Object>> images = null;
            String methodUsed = "";
            List<String> errors = new ArrayList<>();

            for (int i = 0; i < methodChain.size(); i++) {
                if (images != null && !images.isEmpty()) break;
                String methodName = methodChain.get(i);
                if (i > 0) sleepMs(METHOD_SWITCH_DELAY_MS);
                try {
                    List<Map<String, Object>> result = runMethodByName(methodName, cfg, baseUrl, apiKey, model, payload, configTimeout);
                    if (result != null && !result.isEmpty()) {
                        images = result;
                        methodUsed = methodName;
                        log.info("[生图] 方法{}({})成功: providerMode={}, requestId={}, count={}", i + 1, methodName, providerMode, requestId, images.size());
                    }
                } catch (Exception e) {
                    String err = "方法" + (i + 1) + "(" + methodName + ")失败: " + e.getClass().getSimpleName();
                    errors.add(err);
                    log.warn("[生图] {} - providerMode={}, requestId={}", err, providerMode, requestId);
                }
            }

            // 所有方法都失败
            if (images == null || images.isEmpty()) {
                throw new BizException(502, "图片生成上游服务未返回可用结果，请稍后重试");
            }

            // ==================== 图片有效性验证 ====================
            List<Map<String, Object>> validImages = validateImages(images);
            if (validImages.isEmpty()) {
                throw new BizException(502, "图片生成结果无效，请稍后重试");
            }
            if (validImages.size() < images.size()) {
                log.warn("[生图] 部分图片无效: requestId={}, total={}, valid={}", requestId, images.size(), validImages.size());
            }

            // ==================== 扣费 ====================
            String rawResponse = "{\"method\":\"" + methodUsed + "\",\"count\":" + validImages.size() + "}";
            BillingResult billing = recordSuccessfulBilling(
                    tenantId, userId, requestId, model, validImages.size(), size,
                    chargeTokens, costCent, rawResponse);
            before = billing.beforeBalance();
            long after = billing.afterBalance();
            billingCommitted = true;

            // ==================== 保存历史记录（用于恢复） ====================
            // V1.25: 工作流调用生图时通过 payload 携带 source/workflowId 等溯源字段
            String historySource = text(body.get("source"), "opportunity");
            Long historyWorkflowId = body.get("workflowId") instanceof Number n ? n.longValue() : null;
            Long historyWorkflowExecutionId = body.get("workflowExecutionId") instanceof Number n ? n.longValue() : null;
            String historyWorkflowNodeKey = body.get("workflowNodeKey") == null ? null : String.valueOf(body.get("workflowNodeKey"));
            boolean historySaved = true;
            try {
                saveGenerationHistory(tenantId, userId, requestId, model, finalPrompt, size, validImages, methodUsed,
                        historySource, historyWorkflowId, historyWorkflowExecutionId, historyWorkflowNodeKey);
            } catch (Exception historyError) {
                historySaved = false;
                log.error("图片已生成并完成扣费，但历史记录保存失败, requestId={}, errorType={}", requestId, historyError.getClass().getSimpleName());
            }

            Map<String, Object> res = new LinkedHashMap<>();
            res.put("ok", true);
            res.put("requestId", requestId);
            res.put("provider", modelConfigService.textConfig(cfg, "openai-compatible-image", "providerName", "provider"));
            res.put("model", model);
            res.put("images", publicImageCopies(validImages));
            res.put("count", validImages.size());
            res.put("size", size);
            res.put("prompt", prompt);
            res.put("finalPrompt", finalPrompt);
            res.put("tokensPerImage", perImage);
            res.put("chargedTokens", chargeTokens);
            res.put("costCent", costCent);
            res.put("costYuan", BigDecimal.valueOf(costCent).divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP));
            res.put("balanceBefore", before);
            res.put("balanceAfter", after);
            res.put("durationMs", System.currentTimeMillis() - start);
            res.put("methodUsed", methodUsed);
            res.put("methodsAttempted", errors.size() + 1);
            res.put("historySaved", historySaved);
            return res;

        } catch (BizException e) {
            if (!billingCommitted) {
                recordFailureSafely(tenantId, userId, requestId, model, count, size,
                        chargeTokens, costCent, before, e.getMessage());
            }
            throw e;
        } catch (Exception e) {
            String msg = e.getClass().getSimpleName() + ", requestId=" + requestId;
            if (!billingCommitted) {
                recordFailureSafely(tenantId, userId, requestId, model, count, size,
                        chargeTokens, costCent, before, msg);
            }
            log.error("图片生成失败, requestId={}, errorType={}", requestId, e.getClass().getSimpleName());
            throw new BizException(503, "图片生成服务暂时不可用，请稍后重试");
        }
    }

    /**
     * 历史图片恢复 - 根据requestId查询历史生图记录。
     */
    public Map<String, Object> getHistory(Long tenantId, String requestId) {
        try {
            Map<String, Object> row = new LinkedHashMap<>(jdbcTemplate.queryForMap(
                    "SELECT id, tenant_id, user_id, request_id, model, prompt, image_size, image_count, " +
                        "result_images, method_used, status, CASE WHEN error_message IS NULL OR error_message='' THEN NULL ELSE '生成失败，请按 requestId 查询服务端日志' END AS error_message, created_time " +
                        "FROM opportunity_image_history WHERE tenant_id=? AND request_id=? AND deleted=0 LIMIT 1",
                    tenantId, requestId));
            String imagesJson = row.get("result_images") == null ? "" : String.valueOf(row.get("result_images"));
            if (!imagesJson.isBlank()) {
                List<Map<String, Object>> stored = objectMapper.readValue(imagesJson,
                        new TypeReference<List<Map<String, Object>>>() {});
                row.put("result_images", objectMapper.writeValueAsString(restoreHistoryImages(stored)));
            }
            return row;
        } catch (EmptyResultDataAccessException e) {
            throw new BizException(404, "未找到生图记录");
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("查询图片生成记录失败, requestId={}, errorType={}", requestId, e.getClass().getSimpleName());
            throw new BizException(503, "图片生成记录暂时无法查询，请稍后重试");
        }
    }

    /**
     * 历史图片恢复 - 查询最近的生图记录列表（向后兼容重载）。
     * 商机发掘页面使用，仅按 limit 返回最近记录。
     */
    public List<Map<String, Object>> listHistory(Long tenantId, int limit) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, request_id, model, image_size, image_count, method_used, " +
                    "status, CASE WHEN error_message IS NULL OR error_message='' THEN NULL ELSE '生成失败，请按 requestId 查询服务端日志' END AS error_message, created_time " +
                    "FROM opportunity_image_history WHERE tenant_id=? AND deleted=0 " +
                    "ORDER BY created_time DESC LIMIT ?",
                    tenantId, Math.min(Math.max(limit, 1), 50));
            return rows;
        } catch (Exception e) {
            log.error("查询图片生成历史失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "图片生成历史暂时无法查询，请稍后重试");
        }
    }

    /**
     * 查询生图历史（支持来源/分页/关键词过滤）。
     * 用于「工作流 → 图片生成记录」页面，返回精简字段以便前端直接展示图片预览。
     *
     * 性能优化（避免加载慢）：
     *  1. 列表查询不再返回 prompt（TEXT 大字段）、error_message（TEXT）、raw_response（TEXT）
     *     —— 这些字段仅在详情接口 getHistory() 返回
     *  2. result_images 仍需返回（前端列表卡片需要展示缩略图），但该字段已通过 V1.8 表结构控制大小
     *  3. 之前返回 18 个字段中有 3 个 TEXT，单条记录可能超过 10KB，24 条记录即 240KB+；
     *     精简后单条 < 1KB，列表接口数据量降低 95%+
     *
     * @param source "all" 或 null=所有来源；"opportunity"=商机发掘；"workflow"=工作流
     * @return { records, total, page, pageSize }
     */
    public Map<String, Object> listHistoryPaged(Long tenantId, String source, String status, String keyword,
                                                 Long workflowId, String nodeKey,
                                                 int page, int pageSize) {
        try {
            int safePage = Math.max(1, page);
            int safePageSize = Math.min(Math.max(pageSize, 1), 100);
            int offset = (safePage - 1) * safePageSize;

            StringBuilder where = new StringBuilder("WHERE tenant_id=? AND deleted=0");
            List<Object> args = new ArrayList<>();
            args.add(tenantId);
            if (source != null && !source.isBlank() && !"all".equalsIgnoreCase(source)) {
                where.append(" AND source=?");
                args.add(source);
            }
            if (status != null && !status.isBlank()) {
                where.append(" AND status=?");
                args.add(status);
            }
            if (keyword != null && !keyword.isBlank()) {
                where.append(" AND (prompt LIKE ? OR model LIKE ?)");
                args.add("%" + keyword + "%");
                args.add("%" + keyword + "%");
            }
            if (workflowId != null) {
                where.append(" AND workflow_id=?");
                args.add(workflowId);
            }
            if (nodeKey != null && !nodeKey.isBlank()) {
                where.append(" AND workflow_node_key=?");
                args.add(nodeKey);
            }

            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM opportunity_image_history " + where, Long.class, args.toArray());
            if (total == null) total = 0L;

            List<Object> pagedArgs = new ArrayList<>(args);
            pagedArgs.add(safePageSize);
            pagedArgs.add(offset);

            // 列表查询精简字段：去掉 prompt / error_message / raw_response / workflow_execution_id 等 TEXT 大字段
            // 保留 result_images 用于列表缩略图展示；详情接口 getHistory() 仍返回完整字段
            List<Map<String, Object>> records = jdbcTemplate.queryForList(
                    "SELECT id,tenant_id,user_id,request_id,model,image_size,image_count,result_images," +
                    "method_used,status,source,workflow_id,workflow_node_key,created_time " +
                    "FROM opportunity_image_history " + where +
                    " ORDER BY created_time DESC LIMIT ? OFFSET ?",
                    pagedArgs.toArray());

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("records", records);
            result.put("total", total);
            result.put("page", safePage);
            result.put("pageSize", safePageSize);
            return result;
        } catch (Exception e) {
            log.error("查询图片生成历史（分页）失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "图片生成历史暂时无法查询，请稍后重试");
        }
    }

    /**
     * 生图记录统计聚合（后端 SQL 聚合，避免前端拉取 1000 条循环计算）。
     *
     * 性能优化：原前端 loadStats() 拉取 pageSize=1000 的全量记录到浏览器循环统计，
     * 单次请求返回 1000 条 × 18 字段（含 3 个 TEXT）= 数 MB 数据，加载耗时 5-10s。
     * 改为后端 COUNT 聚合，3 个标量查询，<50ms。
     *
     * @param source "all" 或 null=所有来源
     * @return { total, success, failed, thisMonth }
     */
    public Map<String, Object> getHistoryStats(Long tenantId, String source) {
        try {
            StringBuilder where = new StringBuilder("WHERE tenant_id=? AND deleted=0");
            List<Object> args = new ArrayList<>();
            args.add(tenantId);
            if (source != null && !source.isBlank() && !"all".equalsIgnoreCase(source)) {
                where.append(" AND source=?");
                args.add(source);
            }

            // 总数
            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM opportunity_image_history " + where, Long.class, args.toArray());
            if (total == null) total = 0L;

            // 成功数
            List<Object> successArgs = new ArrayList<>(args);
            successArgs.add("success");
            Long success = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM opportunity_image_history " + where + " AND status=?",
                    Long.class, successArgs.toArray());
            if (success == null) success = 0L;

            // 失败数
            List<Object> failedArgs = new ArrayList<>(args);
            failedArgs.add("failed");
            Long failed = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM opportunity_image_history " + where + " AND status=?",
                    Long.class, failedArgs.toArray());
            if (failed == null) failed = 0L;

            // 本月数（按 created_time 当月 1 日 00:00:00 起算）
            LocalDate now = LocalDate.now();
            LocalDateTime monthStart = now.withDayOfMonth(1).atStartOfDay();
            List<Object> monthArgs = new ArrayList<>(args);
            monthArgs.add(monthStart);
            Long thisMonth = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM opportunity_image_history " + where + " AND created_time>=?",
                    Long.class, monthArgs.toArray());
            if (thisMonth == null) thisMonth = 0L;

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("total", total);
            result.put("success", success);
            result.put("failed", failed);
            result.put("thisMonth", thisMonth);
            return result;
        } catch (Exception e) {
            log.error("查询生图记录统计失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "生图记录统计暂时无法查询，请稍后重试");
        }
    }

    /**
     * 查询指定生图记录中的图片URL列表（用于图片恢复）。
     */
    public List<Map<String, Object>> recoverImages(Long tenantId, Long historyId) {
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT result_images, image_count FROM opportunity_image_history WHERE tenant_id=? AND id=? AND deleted=0",
                    tenantId, historyId);
            String imagesJson = (String) row.get("result_images");
            if (imagesJson == null || imagesJson.isBlank()) return List.of();

            List<Map<String, Object>> images = objectMapper.readValue(imagesJson,
                    new TypeReference<List<Map<String, Object>>>() {});
            List<Map<String, Object>> restored = restoreHistoryImages(images);
            if (!images.isEmpty() && restored.isEmpty()) {
                throw new BizException(410, "该历史记录中的图片源已失效");
            }
            return restored;
        } catch (EmptyResultDataAccessException e) {
            throw new BizException(404, "图片生成历史记录不存在");
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("恢复历史图片失败, historyId={}, errorType={}", historyId, e.getClass().getSimpleName());
            throw new BizException(503, "历史图片暂时无法恢复，请稍后重试");
        }
    }

    private List<Map<String, Object>> restoreHistoryImages(List<Map<String, Object>> images) {
        List<Map<String, Object>> restored = new ArrayList<>();
        if (images == null) return restored;
        for (Map<String, Object> stored : images) {
            Map<String, Object> safe = new LinkedHashMap<>(stored);
            Object encrypted = safe.remove("encryptedOriginalUrl");
            Object legacyPlaintext = safe.remove("originalUrl");
            String original = encrypted != null
                    ? sensitiveValueCrypto.decryptIfNeeded(String.valueOf(encrypted))
                    : (legacyPlaintext == null ? "" : String.valueOf(legacyPlaintext));
            if (!original.isBlank()) {
                try {
                    safe.put("url", "/api/proxy-image/" + imageProxyService.register(original));
                } catch (Exception e) {
                    log.warn("[生图恢复] 原始图片已不可用, errorType={}", e.getClass().getSimpleName());
                    continue;
                }
            }
            Object url = safe.get("url");
            if (url != null && !String.valueOf(url).isBlank()) restored.add(safe);
        }
        return restored;
    }

    /** 连接测试（保持原有逻辑） */
    public Map<String, Object> testConnection(Map<String, Object> payload) {
        Map<String, Object> cfg = new LinkedHashMap<>();
        if (payload != null) cfg.putAll(payload);
        if (!modelConfigService.isEnabled(cfg)) return Map.of("ok", false, "message", "配置未启用");
        String baseUrl = modelConfigService.textConfig(cfg, "", "baseUrl");
        String apiKey = modelConfigService.textConfig(cfg, "", "apiKey");
        String model = modelConfigService.textConfig(cfg, "", "modelName", "defaultModel", "model");
        String providerMode = normalizeProviderMode(modelConfigService.textConfig(cfg, "openai-compatible", "providerMode"));
        if (baseUrl.isBlank() || apiKey.isBlank() || model.isBlank())
            return Map.of("ok", false, "message", "缺少必要配置：baseUrl、apiKey、modelName");
        long start = System.currentTimeMillis();
        try {
            String testPrompt = "连接测试：生成一个纯白背景上的蓝色圆点图标";
            String url;
            String reqBody;

            if ("chat-completions-image".equals(providerMode)) {
                // chat/completions 模式测试
                url = normalizedBaseUrl(baseUrl) + "/chat/completions";
                Map<String, Object> chatBody = new LinkedHashMap<>();
                chatBody.put("model", model);
                chatBody.put("messages", List.of(Map.of("role", "user", "content", testPrompt)));
                chatBody.put("modalities", List.of("text", "image"));
                chatBody.put("stream", false);
                reqBody = objectMapper.writeValueAsString(chatBody);
            } else {
                // 标准 images/generations 模式测试
                url = normalizedBaseUrl(baseUrl) + "/images/generations";
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("model", model);
                body.put("prompt", testPrompt);
                body.put("n", 1);
                body.put("size", "1024x1024");
                body.put("response_format", "url");
                reqBody = objectMapper.writeValueAsString(body);
            }

            HttpRequest.Builder reqBuilder = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(60))
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json");
            if ("chat-completions-image".equals(providerMode)) {
                reqBuilder.header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
                reqBuilder.header("Accept", "*/*");
            }
            HttpRequest req = reqBuilder
                    .POST(HttpRequest.BodyPublishers.ofString(reqBody, StandardCharsets.UTF_8))
                    .build();
            LimitedResponse resp = sendLimited(req);
            if (resp.statusCode() < 200 || resp.statusCode() >= 300)
                return Map.of("ok", false, "durationMs", System.currentTimeMillis() - start,
                        "message", "生图提供商返回异常状态（HTTP " + resp.statusCode() + "），请检查配置和服务状态");
            return Map.of("ok", true, "durationMs", System.currentTimeMillis() - start,
                    "message", "生图模型连接成功", "responseSummary", "已成功返回图片生成响应");
        } catch (Exception e) {
            log.warn("生图模型连接测试失败, errorType={}", e.getClass().getSimpleName());
            return Map.of("ok", false, "durationMs", System.currentTimeMillis() - start,
                    "message", "生图模型连接失败，请检查配置和服务状态");
        }
    }

    // ==================== 多方法生图实现 ====================

    /** 规范化 providerMode，未配置或非法值回退为 openai-compatible（保证历史配置向后兼容） */
    private String normalizeProviderMode(String raw) {
        String mode = raw == null ? "" : raw.trim();
        return switch (mode) {
            case "openai-compatible", "async-poll", "webhook-callback", "chat-completions-image" -> mode;
            default -> "openai-compatible";
        };
    }

    private String resolveProviderMode(Map<String, Object> cfg) {
        String configuredMode = normalizeProviderMode(modelConfigService.textConfig(cfg, "openai-compatible", "providerMode"));
        if (!"openai-compatible".equals(configuredMode)) {
            return configuredMode;
        }
        return looksLikeAsyncImageProvider(cfg) ? "async-poll" : configuredMode;
    }

    private boolean looksLikeAsyncImageProvider(Map<String, Object> cfg) {
        String signal = String.join("\n",
                modelConfigService.textConfig(cfg, "", "baseUrl"),
                modelConfigService.textConfig(cfg, "", "proxyBaseUrl"),
                modelConfigService.textConfig(cfg, "", "providerName"),
                modelConfigService.textConfig(cfg, "", "providerDocUrl"),
                modelConfigService.textConfig(cfg, "", "providerDocText"))
                .toLowerCase();
        return signal.contains("65535.space")
                || signal.contains("x-async-mode")
                || signal.contains("async-generations")
                || signal.contains("异步图片生成");
    }

    /**
     * 根据 providerMode 构建方法执行顺序。
     * 原始顺序：proxy-async-poll, async-poll, direct-sync, async-fallback
     * 配置的主策略会被提到最前，其余方法按原始顺序保留作为兜底，确保多重生成方法链不被破坏。
     */
    private List<String> buildMethodChain(String providerMode, Map<String, Object> cfg, String baseUrl) {
        List<String> chain = new ArrayList<>();
        boolean hasDistinctProxy = hasDistinctProxyBaseUrl(cfg, baseUrl);
        switch (providerMode) {
            case "openai-compatible":
                // 标准 OpenAI 兼容同步接口优先
                chain.add("direct-sync");
                if (hasDistinctProxy) chain.add("proxy-async-poll");
                chain.add("async-poll");
                chain.add("async-fallback");
                break;
            case "async-poll":
                // 异步提交 + 轮询优先
                if (hasDistinctProxy) chain.add("proxy-async-poll");
                chain.add("async-poll");
                chain.add("direct-sync");
                break;
            case "webhook-callback":
                chain.add("async-fallback");
                // 异步兜底（异步提交，依赖服务端回调/轮询）优先
                chain.add("async-fallback");
                if (hasDistinctProxy) chain.add("proxy-async-poll");
                chain.add("async-poll");
                chain.add("direct-sync");
                break;
            case "chat-completions-image":
                chain.add("chat-completions-image");
                // chat/completions + modalities 方式（如 Gemini 图片生成模型）
                chain.add("chat-completions-image");
                chain.add("direct-sync");
                if (hasDistinctProxy) chain.add("proxy-async-poll");
                chain.add("async-poll");
                chain.add("async-fallback");
                break;
            default:
                if (hasDistinctProxy) chain.add("proxy-async-poll");
                chain.add("async-poll");
                chain.add("direct-sync");
                chain.add("async-fallback");
                break;
        }
        return chain;
    }

    private boolean hasDistinctProxyBaseUrl(Map<String, Object> cfg, String baseUrl) {
        String proxyBaseUrl = modelConfigService.textConfig(cfg, "", "proxyBaseUrl");
        if (proxyBaseUrl.isBlank()) {
            return false;
        }
        return !normalizedBaseUrl(proxyBaseUrl).equalsIgnoreCase(normalizedBaseUrl(baseUrl));
    }

    /**
     * 按方法名分发生图执行逻辑，保持与原多重方法链完全一致的行为。
     */
    private List<Map<String, Object>> runMethodByName(String methodName, Map<String, Object> cfg,
                                                       String baseUrl, String apiKey, String model,
                                                       Map<String, Object> payload, int configTimeout) throws Exception {
        switch (methodName) {
            case "proxy-async-poll": {
                // 默认使用主地址作为proxy（没有额外proxy配置时）
                String proxyBaseUrl = modelConfigService.textConfig(cfg, "", "proxyBaseUrl");
                if (proxyBaseUrl.isBlank()) proxyBaseUrl = baseUrl;
                return tryMethodGenerate("proxy-async-poll", proxyBaseUrl, apiKey, model, payload, configTimeout);
            }
            case "async-poll":
                return tryMethodGenerate("async-poll", baseUrl, apiKey, model, payload, configTimeout);
            case "direct-sync":
                return trySyncGenerate(baseUrl, apiKey, model, payload, configTimeout);
            case "chat-completions-image":
                return doChatCompletionsImageGenerate(baseUrl, apiKey, model, payload, configTimeout);
            case "async-fallback": {
                // 优先使用分发服务器地址（稳定性更高）
                String asyncBaseUrl = normalizedBaseUrl(baseUrl);
                String proxyBaseUrl = modelConfigService.textConfig(cfg, "", "proxyBaseUrl");
                if (!proxyBaseUrl.isBlank()) asyncBaseUrl = normalizedBaseUrl(proxyBaseUrl);
                return doAsyncPollGenerate(asyncBaseUrl, apiKey, model, payload, 300);
            }
            default:
                throw new IllegalArgumentException("未知生图方法: " + methodName);
        }
    }

    /**
     * 方法1&2: Async提交 + 轮询模式（支持普通地址和proxy地址）
     * 内部含重试逻辑。
     */
    private List<Map<String, Object>> tryMethodGenerate(String method, String baseUrl, String apiKey,
                                                         String model, Map<String, Object> payload,
                                                         int configTimeout) throws Exception {
        Exception lastException = null;
        for (int attempt = 0; attempt < METHOD_RETRY_COUNT; attempt++) {
            if (attempt > 0) sleepMs(2000);
            try {
                return doAsyncPollGenerate(baseUrl, apiKey, model, payload, configTimeout);
            } catch (BizException e) {
                if (isNonRetryableError(e.getMessage()) || isAsyncJobStillRunningTimeout(e.getMessage())) {
                // 对于非可恢复错误（内容拒绝、鉴权等），不重试
                if (isNonRetryableError(e.getMessage()) || isAsyncJobStillRunningTimeout(e.getMessage())) {
                    throw e;
                }
                }
                lastException = e;
                log.warn("[生图] {} 第{}次重试, errorType={}", method, attempt + 1, e.getClass().getSimpleName());
            } catch (Exception e) {
                lastException = e;
                log.warn("[生图] {} 第{}次重试异常, errorType={}", method, attempt + 1, e.getClass().getSimpleName());
            }
        }
        if (lastException != null) throw lastException;
        return null;
    }

    /**
     * 方法3: Direct Sync模式（同步等待直接返回）。
     */
    private List<Map<String, Object>> trySyncGenerate(String baseUrl, String apiKey,
                                                       String model, Map<String, Object> payload,
                                                       int configTimeout) throws Exception {
        Exception lastException = null;
        for (int attempt = 0; attempt < METHOD_RETRY_COUNT; attempt++) {
            if (attempt > 0) sleepMs(2000);
            try {
                return doSyncGenerate(baseUrl, apiKey, model, payload, configTimeout);
            } catch (BizException e) {
                if (isNonRetryableError(e.getMessage())) throw e;
                lastException = e;
            } catch (Exception e) {
                lastException = e;
            }
        }
        if (lastException != null) throw lastException;
        return null;
    }

    // ==================== 具体生图操作 ====================

    /**
     * 异步提交 + 轮询模式。
     * 提交带 X-Async-Mode: true，然后轮询 job 直到 done/failed。
     */
    private List<Map<String, Object>> doAsyncPollGenerate(String baseUrl, String apiKey,
                                                           String model, Map<String, Object> payload,
                                                           int configTimeout) throws Exception {
        String submitUrl = normalizedBaseUrl(baseUrl) + "/images/generations";
        String reqBody = objectMapper.writeValueAsString(payload);

        // 提交异步任务
        HttpRequest req = HttpRequest.newBuilder(URI.create(submitUrl))
                .timeout(Duration.ofSeconds(Math.max(30, configTimeout)))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .header("X-Async-Mode", "true")
                .POST(HttpRequest.BodyPublishers.ofString(reqBody, StandardCharsets.UTF_8))
                .build();

        LimitedResponse resp = sendLimited(req);
        if (resp.statusCode() < 200 || resp.statusCode() >= 300) {
            log.warn("图片生成异步提交失败, status={}, responseBytes={}", resp.statusCode(), resp.body() == null ? 0 : resp.body().length());
            throw new BizException(502, "图片生成上游服务响应异常");
        }

        Map<String, Object> parsed = objectMapper.readValue(resp.body(),
                new TypeReference<LinkedHashMap<String, Object>>() {});
        String jobId = (String) parsed.get("job_id");
        if (jobId == null || jobId.isBlank()) {
            // 尝试从 status_url 提取
            String statusUrl = (String) parsed.get("status_url");
            if (statusUrl != null && !statusUrl.isBlank()) {
                jobId = statusUrl.substring(statusUrl.lastIndexOf('/') + 1);
            }
        }
        if (jobId == null || jobId.isBlank()) {
            log.warn("图片生成异步响应缺少 jobId, responseBytes={}", resp.body() == null ? 0 : resp.body().length());
            throw new BizException(502, "图片生成上游服务返回了无效任务信息");
        }

        // 轮询结果
        return pollJobResult(baseUrl, apiKey, jobId);
    }

    /**
     * 同步模式（不加 X-Async-Mode，直接等待返回）。
     * 这种方式后端会阻塞最多5分钟，适合兜底使用。
     */
    private List<Map<String, Object>> doSyncGenerate(String baseUrl, String apiKey,
                                                      String model, Map<String, Object> payload,
                                                      int configTimeout) throws Exception {
        String submitUrl = normalizedBaseUrl(baseUrl) + "/images/generations";
        String reqBody = objectMapper.writeValueAsString(payload);

        // 同步模式：不加 X-Async-Mode，服务端阻塞直到完成（最多5分钟）
        HttpRequest req = HttpRequest.newBuilder(URI.create(submitUrl))
                .timeout(Duration.ofSeconds(Math.max(120, configTimeout + 60)))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(reqBody, StandardCharsets.UTF_8))
                .build();

        LimitedResponse resp = sendLimited(req);
        if (resp.statusCode() < 200 || resp.statusCode() >= 300) {
            log.warn("图片生成同步调用失败, status={}, responseBytes={}", resp.statusCode(), resp.body() == null ? 0 : resp.body().length());
            throw new BizException(502, "图片生成上游服务响应异常");
        }

        Map<String, Object> parsed = objectMapper.readValue(resp.body(),
                new TypeReference<LinkedHashMap<String, Object>>() {});
        return extractImages(parsed);
    }

    /**
     * chat/completions + modalities 方式生图（如 Gemini 图片生成模型）。
     * 使用 /chat/completions 端点，设置 modalities: ["text", "image"]，
     * 从 choices[0].message.content 中提取 base64 图片数据。
     */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> doChatCompletionsImageGenerate(String baseUrl, String apiKey,
                                                                      String model, Map<String, Object> payload,
                                                                      int configTimeout) throws Exception {
        String submitUrl = normalizedBaseUrl(baseUrl) + "/chat/completions";

        // chat/completions 模式下，Gemini 图片生成不支持 size 参数，必须在提示词中明确要求正方形
        // 在 prompt 末尾追加尺寸约束，确保生成 1:1 正方形封面图
        String originalPrompt = String.valueOf(payload.get("prompt"));
        String sizeHint = "\n\n----------------------------\n\nIMAGE SIZE CONSTRAINT\nThe output image MUST be a perfect square (1:1 aspect ratio, e.g. 1024x1024).\nDo NOT generate portrait or landscape images.\nAspect ratio: 1:1 (width equals height).\n";
        String finalPrompt = originalPrompt.endsWith(sizeHint) ? originalPrompt : (originalPrompt + sizeHint);

        // 构建 chat/completions 专用 payload
        Map<String, Object> chatPayload = new LinkedHashMap<>();
        chatPayload.put("model", model);
        chatPayload.put("messages", List.of(Map.of("role", "user", "content", finalPrompt)));
        chatPayload.put("modalities", List.of("text", "image"));
        chatPayload.put("stream", false);

        String reqBody = objectMapper.writeValueAsString(chatPayload);

        HttpRequest req = HttpRequest.newBuilder(URI.create(submitUrl))
                .timeout(Duration.ofSeconds(Math.max(120, configTimeout + 60)))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                .header("Accept", "*/*")
                .POST(HttpRequest.BodyPublishers.ofString(reqBody, StandardCharsets.UTF_8))
                .build();

        LimitedResponse resp = sendLimited(req);
        if (resp.statusCode() < 200 || resp.statusCode() >= 300) {
            log.warn("图片生成 chat-completions 调用失败, status={}, responseBytes={}", resp.statusCode(), resp.body() == null ? 0 : resp.body().length());
            throw new BizException(502, "图片生成上游服务响应异常");
        }

        Map<String, Object> parsed = objectMapper.readValue(resp.body(),
                new TypeReference<LinkedHashMap<String, Object>>() {});

        // 从 choices[0].message.content 提取 base64 图片（markdown 格式: ![...](data:image/jpeg;base64,...))
        return extractImagesFromChatResponse(parsed);
    }

    /**
     * 从 chat/completions 响应中提取图片。
     * 响应格式: choices[0].message.content 包含 ![...](data:image/jpeg;base64,...)
     */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractImagesFromChatResponse(Map<String, Object> parsed) {
        List<Map<String, Object>> images = new ArrayList<>();
        Object choicesObj = parsed.get("choices");
        if (!(choicesObj instanceof List<?> choices) || choices.isEmpty()) {
            return images;
        }
        Object firstChoice = choices.get(0);
        if (!(firstChoice instanceof Map<?, ?> choice)) return images;
        Object messageObj = choice.get("message");
        if (!(messageObj instanceof Map<?, ?> message)) return images;
        Object content = message.get("content");
        if (content == null) return images;

        String contentStr = String.valueOf(content);
        // 匹配 data:image/xxx;base64,... 格式
        Pattern pattern = Pattern.compile("data:image/(\\w+);base64,([A-Za-z0-9+/=]+)");
        Matcher matcher = pattern.matcher(contentStr);

        int idx = 0;
        while (matcher.find()) {
            String imageType = matcher.group(1); // jpeg, png, etc.
            String b64Data = matcher.group(2);
            try {
                long maxBase64Chars = ((MAX_IMAGE_DOWNLOAD_BYTES + 2L) / 3L) * 4L;
                if (b64Data.length() > maxBase64Chars) {
                    throw new IllegalArgumentException("generated image exceeds the size limit");
                }
                byte[] imgBytes = Base64.getDecoder().decode(b64Data);
                if (imgBytes.length < 100) continue;
                UploadedImageValidator.ValidatedImage validated =
                        uploadedImageValidator.validate(imgBytes, MAX_IMAGE_DOWNLOAD_BYTES);

                Long tenantId = TenantContext.getCurrentTenantId();
                if (tenantId == null) tenantId = UserContext.getTenantId();
                Long userId = UserContext.userId();
                if (storageGovernance == null || tenantId == null || tenantId <= 0
                        || userId == null || userId <= 0) {
                    throw new BizException(503, "图片资产治理服务不可用");
                }
                String fileName = UUID.randomUUID().toString().replace("-", "") + validated.extension();
                String relativePath = "tenant-" + tenantId + "/" + fileName;
                String localUrl = "/uploads/cache/" + relativePath;
                storageGovernance.store(
                        tenantId, userId, "cache/" + relativePath, localUrl,
                        validated.contentType(), "ai-generated", validated.bytes());

                Map<String, Object> one = new LinkedHashMap<>();
                one.put("index", idx++);
                one.put("url", localUrl);
                images.add(one);

                log.info("[生图] chat/completions 图片提取成功: {} ({} bytes)", localUrl, imgBytes.length);
            } catch (Exception e) {
                log.warn("[生图] chat/completions base64 解码失败, errorType={}", e.getClass().getSimpleName());
            }
        }
        return images;
    }

    /**
     * 轮询异步任务直到终态。
     */
    private List<Map<String, Object>> pollJobResult(String baseUrl, String apiKey, String jobId) throws Exception {
        String pollUrl = normalizedBaseUrl(baseUrl) + "/images/async-generations/" + jobId;
        long pollStart = System.currentTimeMillis();
        List<String> resultUrls = null;

        while (System.currentTimeMillis() - pollStart < POLL_MAX_WAIT_MS) {
            sleepMs(POLL_INTERVAL_MS);

            HttpRequest pollReq = HttpRequest.newBuilder(URI.create(pollUrl))
                    .timeout(Duration.ofSeconds(30))
                    .header("Authorization", "Bearer " + apiKey)
                    .GET()
                    .build();

            LimitedResponse pollResp = sendLimited(pollReq);
            if (pollResp.statusCode() < 200 || pollResp.statusCode() >= 300) {
                // 非200：后端可能短暂重启，继续轮询
                log.warn("[生图] 轮询返回 HTTP {}, 继续等待", pollResp.statusCode());
                continue;
            }

            Map<String, Object> pollParsed = objectMapper.readValue(pollResp.body(),
                    new TypeReference<LinkedHashMap<String, Object>>() {});
            Map<String, Object> jobData = pollParsed;
            if (pollParsed.containsKey("data") && pollParsed.get("data") instanceof Map) {
                jobData = (Map<String, Object>) pollParsed.get("data");
            }

            String status = (String) jobData.get("status");
            if ("done".equals(status)) {
                Object urlsObj = jobData.get("result_urls");
                if (urlsObj instanceof List<?>) {
                    resultUrls = new ArrayList<>();
                    for (Object u : (List<?>) urlsObj) {
                        if (u != null) resultUrls.add(String.valueOf(u));
                    }
                }
                break;
            } else if ("failed".equals(status)) {
                String errMsg = String.valueOf(jobData.getOrDefault("error_message",
                        jobData.getOrDefault("error", "未知错误")));
                String errCode = String.valueOf(jobData.getOrDefault("error_code", ""));
                // 判断是否为可恢复错误
                if (isRetryableErrorCode(errCode)) {
                    throw new Exception("可恢复错误 " + errCode + ": " + errMsg);
                }
                log.warn("图片生成任务失败, errorCode={}", errCode);
                throw new BizException(502, "图片生成任务执行失败，请稍后重试");
            }
            // pending / running → 继续轮询
        }

        if (resultUrls == null) {
            // 超时未完成 - 对于超时但后台仍在运行的情况，
            // 尝试最后一次查询job状态（可能刚刚完成）
            try {
                HttpRequest finalReq = HttpRequest.newBuilder(URI.create(pollUrl))
                        .timeout(Duration.ofSeconds(30))
                        .header("Authorization", "Bearer " + apiKey)
                        .GET()
                        .build();
                LimitedResponse finalResp = sendLimited(finalReq);
                if (finalResp.statusCode() == 200) {
                    Map<String, Object> finalParsed = objectMapper.readValue(finalResp.body(),
                            new TypeReference<LinkedHashMap<String, Object>>() {});
                    Map<String, Object> finalData = finalParsed;
                    if (finalParsed.containsKey("data") && finalParsed.get("data") instanceof Map) {
                        finalData = (Map<String, Object>) finalParsed.get("data");
                    }
                    if ("done".equals(finalData.get("status"))) {
                        Object urlsObj = finalData.get("result_urls");
                        if (urlsObj instanceof List<?>) {
                            resultUrls = new ArrayList<>();
                            for (Object u : (List<?>) urlsObj) {
                                if (u != null) resultUrls.add(String.valueOf(u));
                            }
                        }
                    }
                }
            } catch (Exception e) {
                log.warn("[生图] 超时后最终查询也失败, errorType={}", e.getClass().getSimpleName());
            }
        }

        if (resultUrls == null || resultUrls.isEmpty()) {
            throw new BizException(504, "图片生成任务处理超时，请先通过历史记录确认结果后再重试");
        }

        return processResultUrls(resultUrls);
    }

    // ==================== 图片处理与验证 ====================

    /**
     * 将 result_urls 转为标准图片列表。
     *
     * 优先使用代理 URL（/api/proxy-image/{token}）；若代理注册因 URL 策略校验失败
     * （如中转站返回 HTTP/非标端口/内网域名等），降级返回原始 URL，避免因代理
     * 注册异常导致整个方法被判定失败、触发方法链切换与重复生图。
     */
    private List<Map<String, Object>> processResultUrls(List<String> resultUrls) {
        List<Map<String, Object>> images = new ArrayList<>();
        for (int i = 0; i < resultUrls.size(); i++) {
            Map<String, Object> one = new LinkedHashMap<>();
            one.put("index", i);
            String originalUrl = resultUrls.get(i);
            // 内部缓存（加速代理下载），不依赖返回值
            try {
                imageCacheService.cache(originalUrl);
            } catch (Exception e) {
                log.debug("[生图] 内部缓存忽略异常, errorType={}", e.getClass().getSimpleName());
            }
            // 优先使用代理 URL（适配 Vite 和前端跨域场景）；
            // 代理注册失败时降级使用原始 URL，确保图片能返回给前端
            String resolvedUrl;
            try {
                String token = imageProxyService.register(originalUrl);
                resolvedUrl = "/api/proxy-image/" + token;
            } catch (Exception e) {
                log.warn("[生图] 图片代理注册失败，降级使用原始 URL, errorType={}, reason={}",
                        e.getClass().getSimpleName(), e.getMessage());
                resolvedUrl = originalUrl;
            }
            one.put("url", resolvedUrl);
            one.put("originalUrl", originalUrl);
            if (!one.isEmpty()) images.add(one);
        }
        return images;
    }

    private List<Map<String, Object>> publicImageCopies(List<Map<String, Object>> images) {
        List<Map<String, Object>> safe = new ArrayList<>();
        if (images == null) return safe;
        for (Map<String, Object> image : images) {
            Map<String, Object> copy = new LinkedHashMap<>(image);
            copy.remove("originalUrl");
            copy.remove("encryptedOriginalUrl");
            safe.add(copy);
        }
        return safe;
    }

    /**
     * 图片有效性验证 - 检查图片是否非空白。
     * 通过下载图片并检查文件大小和图像内容。
     */
    private List<Map<String, Object>> validateImages(List<Map<String, Object>> images) {
        List<Map<String, Object>> valid = new ArrayList<>();
        for (Map<String, Object> img : images) {
            try {
                String url = (String) img.get("url");
                if (url == null || url.isBlank()) continue;

                // 对于本地缓存URL，直接读取文件
                if (url.startsWith("/uploads/cache/") || url.startsWith("uploads/cache/")) {
                    String relativePath = url.startsWith("/")
                            ? url.substring("/uploads/cache/".length())
                            : url.substring("uploads/cache/".length());
                    Long tenantId = TenantContext.getCurrentTenantId();
                    if (tenantId == null) tenantId = UserContext.getTenantId();
                    if (tenantId == null || !relativePath.matches(
                            "tenant-" + tenantId + "/[A-Za-z0-9_-]{1,180}\\.(?:jpg|jpeg|png|gif|webp)")) {
                        continue;
                    }
                    Path file = uploadPaths.resolve("cache", relativePath);
                    if (Files.exists(file) && Files.size(file) > MIN_VALID_IMAGE_BYTES) {
                        // 额外检查：尝试解码图片
                        BufferedImage bi = ImageIO.read(file.toFile());
                        if (bi != null && bi.getWidth() > 10 && bi.getHeight() > 10) {
                            valid.add(img);
                            continue;
                        }
                    }
                    // 本地缓存文件无效，尝试通过URL重新下载验证
                    if (img.containsKey("originalUrl")) {
                        String originalUrl = (String) img.get("originalUrl");
                        if (originalUrl != null && !originalUrl.isBlank()) {
                            if (validateRemoteImage(originalUrl)) {
                                // 重新注册代理 URL
                                try { imageCacheService.cache(originalUrl); } catch (Exception ignored) {}
                                try {
                                    img.put("url", "/api/proxy-image/" + imageProxyService.register(originalUrl));
                                } catch (Exception e) {
                                    log.warn("[生图验证] 图片代理注册失败，保留原始 URL, errorType={}, reason={}",
                                            e.getClass().getSimpleName(), e.getMessage());
                                    img.put("url", originalUrl);
                                }
                                valid.add(img);
                                continue;
                            }
                        }
                    }
                } else if (url.startsWith("/api/proxy-image/")) {
                    // 代理图片信任通过（实际加载时才验证）
                    valid.add(img);
                } else if (url.startsWith("http://") || url.startsWith("https://")) {
                    // 远程URL，验证；若因代理策略无法下载验证，信任中转站返回的 URL
                    if (validateRemoteImage(url)) {
                        // 注册代理 URL
                        try { imageCacheService.cache(url); } catch (Exception ignored) {}
                        try {
                            img.put("url", "/api/proxy-image/" + imageProxyService.register(url));
                        } catch (Exception e) {
                            // 代理注册失败，保留原始 URL
                            log.warn("[生图验证] 图片代理注册失败，保留原始 URL, errorType={}, reason={}",
                                    e.getClass().getSimpleName(), e.getMessage());
                        }
                        valid.add(img);
                    } else {
                        // 远程图片无法下载验证（可能因 URL 策略限制），信任中转站返回的 URL
                        log.warn("[生图验证] 远程图片无法下载验证，信任上游返回的 URL");
                        valid.add(img);
                    }
                } else {
                    valid.add(img);
                }
            } catch (Exception e) {
                log.warn("[生图验证] 图片验证异常, errorType={}", e.getClass().getSimpleName());
            }
        }
        return valid;
    }

    /**
     * 验证远程图片是否有效（非空白）。
     */
    private boolean validateRemoteImage(String url) {
        try {
            ImageCacheService.CacheResult cached = imageCacheService.cache(url);
            return cached != null && cached.success()
                    && Files.size(Path.of(cached.filePath())) >= MIN_VALID_IMAGE_BYTES;
        } catch (Exception e) {
            log.warn("[生图验证] 远程图片验证失败, errorType={}", e.getClass().getSimpleName());
            return false;
        }
    }

    // ==================== 历史记录管理 ====================

    /**
     * 保存生图历史记录到数据库，用于异常恢复。
     * 向后兼容重载：未传 source 时默认 'opportunity'（商机发掘）。
     */
    private void saveGenerationHistory(Long tenantId, Long userId, String requestId,
                                        String model, String prompt, String size,
                                        List<Map<String, Object>> images, String method) {
        saveGenerationHistory(tenantId, userId, requestId, model, prompt, size, images, method,
                "opportunity", null, null, null);
    }

    /**
     * 供 Python automation-service 通过内部接口回传工作流生图历史。
     * 与本地 generate() 流程不同：自动化端直接调用 AI 提供商 API 生图，
     * 生图成功后异步回传到 Java 端统一落库到 opportunity_image_history 表。
     *
     * @param tenantId            租户ID
     * @param userId              用户ID（计费主体）
     * @param requestId           请求ID（用于幂等与追踪）
     * @param model               生图模型名
     * @param prompt              最终使用的生图提示词
     * @param size                图片尺寸，如 "1024x1024"
     * @param imageUrl            生图结果URL（已保存到本地的可访问URL）
     * @param method              生图方法标识：chat-completions-image / images-generations / provider-mode
     * @param source              生图来源：opportunity / workflow
     * @param workflowId          工作流定义ID（source=workflow 时）
     * @param workflowExecutionId 工作流执行记录ID（source=workflow 时）
     * @param workflowNodeKey     生图节点key（source=workflow 时）
     * @param status              记录状态：success / failed
     * @param errorMessage        失败原因（status=failed 时）
     */
    public void recordExternalGenerationHistory(Long tenantId, Long userId, String requestId,
                                                 String model, String prompt, String size,
                                                 String imageUrl, String method,
                                                 String source, Long workflowId,
                                                 Long workflowExecutionId, String workflowNodeKey,
                                                 String status, String errorMessage) {
        List<Map<String, Object>> images = new ArrayList<>();
        if (imageUrl != null && !imageUrl.isBlank()) {
            Map<String, Object> img = new LinkedHashMap<>();
            img.put("url", imageUrl);
            img.put("index", 0);
            images.add(img);
        }
        try {
            String imagesJson = objectMapper.writeValueAsString(images);
            String safeSource = (source == null || source.isBlank()) ? "opportunity" : source;
            String safeStatus = (status == null || status.isBlank()) ? "success" : status;
            String safeError = (errorMessage == null) ? "" : errorMessage;
            jdbcTemplate.update(
                    "INSERT INTO opportunity_image_history(tenant_id,user_id,request_id,model,prompt,image_size," +
                    "image_count,result_images,method_used,status,error_message,raw_response,source,workflow_id," +
                    "workflow_execution_id,workflow_node_key,created_time,updated_time,deleted) " +
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    tenantId, userId, requestId, model, prompt, size,
                    images.size(), imagesJson, method, safeStatus, safeError, "{}",
                    safeSource, workflowId, workflowExecutionId, workflowNodeKey);
        } catch (Exception e) {
            log.warn("[生图历史] 外部回传保存失败, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 保存生图历史记录到数据库（支持来源溯源字段）。
     * @param source 生图来源：opportunity=商机发掘 / workflow=工作流
     */
    private void saveGenerationHistory(Long tenantId, Long userId, String requestId,
                                        String model, String prompt, String size,
                                        List<Map<String, Object>> images, String method,
                                        String source, Long workflowId,
                                        Long workflowExecutionId, String workflowNodeKey) {
        try {
            // 只保存url信息，不保存b64内容
            List<Map<String, Object>> saveImages = new ArrayList<>();
            for (Map<String, Object> img : images) {
                Map<String, Object> saveImg = new LinkedHashMap<>();
                if (img.containsKey("url")) saveImg.put("url", img.get("url"));
                if (img.containsKey("originalUrl")) {
                    saveImg.put("encryptedOriginalUrl",
                            sensitiveValueCrypto.encrypt(String.valueOf(img.get("originalUrl"))));
                }
                if (img.containsKey("index")) saveImg.put("index", img.get("index"));
                saveImages.add(saveImg);
            }
            String imagesJson = objectMapper.writeValueAsString(saveImages);

            jdbcTemplate.update(
                    "INSERT INTO opportunity_image_history(tenant_id,user_id,request_id,model,prompt,image_size," +
                    "image_count,result_images,method_used,status,raw_response,source,workflow_id," +
                    "workflow_execution_id,workflow_node_key,created_time,updated_time,deleted) " +
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    tenantId, userId, requestId, model, prompt, size,
                    saveImages.size(), imagesJson, method, "success", "{}",
                    source == null ? "opportunity" : source, workflowId,
                    workflowExecutionId, workflowNodeKey);
        } catch (Exception e) {
            log.warn("[生图历史] 保存失败, errorType={}", e.getClass().getSimpleName());
        }
    }

    // ==================== 工具方法 ====================

    /** 检查错误码是否为可恢复类型 */
    private boolean isRetryableErrorCode(String errorCode) {
        if (errorCode == null || errorCode.isBlank()) return false;
        return switch (errorCode) {
            case "rate_limited", "upstream_5xx", "upstream_error", "queue_timeout",
                 "no_images", "client_gone" -> true;
            default -> false;
        };
    }

    /** 判断是否不可恢复错误 */
    private boolean isNonRetryableError(String msg) {
        if (msg == null) return false;
        String lower = msg.toLowerCase();
        return lower.contains("content_refused") || lower.contains("safety_rejected")
                || lower.contains("auth_failed") || lower.contains("forbidden")
                || lower.contains("余额不足") || lower.contains("not_found")
                || lower.contains("content refused") || lower.contains("safety rejected");
    }

    private boolean isAsyncJobStillRunningTimeout(String msg) {
        if (msg == null) return false;
        return msg.contains("任务超时") || msg.contains("后台任务可能仍在运行");
    }

    private boolean hasText(Object v) {
        return v != null && !String.valueOf(v).trim().isBlank();
    }

    private void sleepMs(long ms) {
        try { TimeUnit.MILLISECONDS.sleep(ms); }
        catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
    }

    private long currentBalance(Long userId) {
        Long n = jdbcTemplate.queryForObject(
                "SELECT COALESCE(token_balance,0) FROM sys_user WHERE id=? AND deleted=0",
                Long.class, userId);
        if (n == null) throw new BizException(404, "用户不存在");
        return n;
    }

    private Long insertUsageLog(Long tenantId, Long userId, String requestId, String model,
                                 int count, String size, long chargeTokens, long costCent,
                                 long before, long after,
                                 String err, String raw) {
        int inserted = jdbcTemplate.update(
                "INSERT INTO ai_usage_log(tenant_id,user_id,scene,provider_name,model_name,model_type," +
                "request_id,prompt_tokens,completion_tokens,total_tokens,image_count,spec_key,cost_cent," +
                "charge_tokens,balance_before,balance_after,status,error_message,raw_usage_json," +
                "created_time,updated_time,deleted) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId, userId, "opportunity_image", "openai-compatible-image", model, "image",
                requestId, 0, 0, 0, count, size, costCent, chargeTokens, before, after,
                err == null ? 1 : 0, err, raw == null ? "{}" : raw);
        if (inserted != 1) throw new BizException(503, "图片生成计费日志写入失败");
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (id == null) throw new BizException(503, "图片生成计费日志编号无法确认");
        return id;
    }

    BillingResult recordSuccessfulBilling(Long tenantId, Long userId, String requestId,
                                          String model, int count, String size,
                                          long chargeTokens, long costCent, String rawResponse) {
        if (transactionTemplate == null) {
            throw new BizException(503, "计费服务暂时不可用，请稍后重试");
        }
        BillingResult result = transactionTemplate.execute(status -> {
            List<Map<String, Object>> existing = jdbcTemplate.queryForList(
                    "SELECT status, balance_before, balance_after FROM ai_usage_log WHERE request_id=? AND deleted=0 LIMIT 1",
                    requestId);
            if (!existing.isEmpty()) {
                Map<String, Object> row = existing.get(0);
                if (!"1".equals(String.valueOf(row.get("status")))) {
                    throw new BizException(409, "该图片生成请求已记录为失败，不能重复扣费");
                }
                return new BillingResult(numberValue(row.get("balance_before")), numberValue(row.get("balance_after")));
            }

            Long lockedBalance;
            try {
                lockedBalance = jdbcTemplate.queryForObject(
                        "SELECT COALESCE(token_balance,0) FROM sys_user WHERE id=? AND deleted=0 FOR UPDATE",
                        Long.class,
                        userId);
            } catch (EmptyResultDataAccessException e) {
                throw new BizException(404, "用户不存在");
            }
            if (lockedBalance == null) throw new BizException(404, "用户不存在");
            long beforeBalance = lockedBalance;
            if (chargeTokens > 0 && beforeBalance < chargeTokens) {
                throw new BizException(402, "Token 余额不足，请先充值");
            }
            long afterBalance = beforeBalance - Math.max(0, chargeTokens);
            if (chargeTokens > 0) {
                int updated = jdbcTemplate.update(
                        "UPDATE sys_user SET token_balance=?, updated_time=NOW() WHERE id=? AND deleted=0",
                        afterBalance,
                        userId);
                if (updated != 1) throw new BizException(409, "用户余额状态已变化，请稍后重试");
            }
            Long usageLogId = insertUsageLog(
                    tenantId, userId, requestId, model, count, size, chargeTokens, costCent,
                    beforeBalance, afterBalance, null, rawResponse);
            if (chargeTokens > 0) {
                int ledgerInserted = jdbcTemplate.update(
                        "INSERT INTO token_balance_ledger(tenant_id,user_id,change_type,change_amount,before_balance,after_balance,ref_type,ref_id,ref_no,remark,created_time) VALUES(?,?,?,?,?,?,?,?,?,?,NOW())",
                        tenantId, userId, "ai_image_charge", -chargeTokens, beforeBalance, afterBalance,
                        "ai_usage", usageLogId, requestId, "商机发掘生图扣费");
                if (ledgerInserted != 1) throw new BizException(503, "图片生成计费流水写入失败");
            }
            return new BillingResult(beforeBalance, afterBalance);
        });
        if (result == null) throw new BizException(503, "计费服务暂时不可用，请稍后重试");
        return result;
    }

    private void recordFailureSafely(Long tenantId, Long userId, String requestId, String model,
                                     int count, String size, long chargeTokens, long costCent,
                                     long balance, String safeError) {
        try {
            insertUsageLog(tenantId, userId, requestId, model, count, size, chargeTokens, costCent,
                    balance, balance, truncate(safeError, 500), "{}");
        } catch (Exception logError) {
            log.error("记录图片生成失败日志失败, requestId={}, errorType={}", requestId, logError.getClass().getSimpleName());
        }
    }

    private long numberValue(Object value) {
        if (value instanceof Number number) return number.longValue();
        if (value == null) return 0L;
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            throw new BizException(503, "计费记录数据异常");
        }
    }

    record BillingResult(long beforeBalance, long afterBalance) {}

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractImages(Map<String, Object> parsed) {
        Object data = parsed.get("data");
        List<Map<String, Object>> images = new ArrayList<>();
        if (data instanceof List<?> list) {
            int idx = 0;
            for (Object it : list) {
                if (it instanceof Map<?, ?> m) {
                    Map<String, Object> one = new LinkedHashMap<>();
                    one.put("index", idx++);
                    Object url = m.get("url");
                    Object b64 = m.get("b64_json");
                    if (url != null) {
                        String originalUrl = String.valueOf(url);
                        ImageCacheService.CacheResult cacheResult = imageCacheService.cache(originalUrl);
                        if (cacheResult != null && cacheResult.success()) {
                            one.put("url", cacheResult.localUrl());
                        } else {
                            // 代理注册失败时降级使用原始 URL，避免因 URL 策略校验失败
                            // 导致整个方法被判定失败、触发方法链切换与重复生图
                            try {
                                String token = imageProxyService.register(originalUrl);
                                one.put("url", "/api/proxy-image/" + token);
                            } catch (Exception e) {
                                log.warn("[生图] 图片代理注册失败，降级使用原始 URL, errorType={}, reason={}",
                                        e.getClass().getSimpleName(), e.getMessage());
                                one.put("url", originalUrl);
                            }
                        }
                        one.put("originalUrl", originalUrl);
                    }
                    if (b64 != null) one.put("b64Json", String.valueOf(b64));
                    if (!one.isEmpty()) images.add(one);
                }
            }
        }
        return images;
    }

    private String resolveImagePromptWithAi(String promptMode,
                                            String customPrompt,
                                            String fallbackPrompt,
                                            String itemTitle,
                                            String itemDesc,
                                            List<Map<String, Object>> promptConfigs) {
        String mode = text(promptMode, "default").trim().toLowerCase();
        if ("custom".equals(mode) && !text(customPrompt, "").isBlank()) {
            return modelConfigService.renderImagePromptTemplate(customPrompt, itemTitle, itemDesc);
        }
        Map<String, Object> aiMatched = matchImagePromptCategoryWithAi(itemTitle, itemDesc, promptConfigs);
        if (aiMatched != null) {
            String template = modelConfigService.textConfig(aiMatched, "", "promptTemplate", "template", "prompt");
            if (!template.isBlank()) {
                return modelConfigService.renderImagePromptTemplate(template, itemTitle, itemDesc);
            }
        }
        return modelConfigService.resolveImagePrompt(mode, customPrompt, fallbackPrompt, itemTitle, itemDesc, promptConfigs);
    }

    private Map<String, Object> matchImagePromptCategoryWithAi(String itemTitle,
                                                               String itemDesc,
                                                               List<Map<String, Object>> promptConfigs) {
        if (promptConfigs == null || promptConfigs.isEmpty() || !aiProviderService.isConfigured()) {
            return null;
        }
        List<Map<String, String>> options = new ArrayList<>();
        for (Map<String, Object> cfg : promptConfigs) {
            String categoryKey = modelConfigService.textConfig(cfg, "", "categoryKey", "name");
            if (categoryKey.isBlank()) continue;
            Map<String, String> option = new LinkedHashMap<>();
            option.put("categoryKey", categoryKey);
            option.put("name", modelConfigService.textConfig(cfg, categoryKey, "name", "categoryKey"));
            option.put("matchKeywords", modelConfigService.textConfig(cfg, "", "matchKeywords", "keywords"));
            options.add(option);
        }
        if (options.isEmpty()) {
            return null;
        }
        StringBuilder optionsText = new StringBuilder();
        for (Map<String, String> option : options) {
            if (!optionsText.isEmpty()) optionsText.append("\n");
            optionsText.append("- categoryKey=").append(option.get("categoryKey"))
                    .append(" | name=").append(option.get("name"))
                    .append(" | keywords=").append(truncate(option.get("matchKeywords"), 120));
        }
        String systemPrompt = "你是闲鱼商品主图类目提示词选择器。根据商品标题和正文，从候选类目中选择最适合用于商品封面提示词的 categoryKey。必须只从候选列表中选择。严格返回 JSON，例如 {\"categoryKey\":\"game_cdk\"}；无法判断时返回 {\"categoryKey\":\"\"}。";
        String userPrompt = "商品标题：" + text(itemTitle, "") + "\n"
                + "商品正文：" + truncate(text(itemDesc, ""), 1200) + "\n\n"
                + "候选类目：\n" + optionsText;
        try {
            Map<String, Object> aiResult = aiProviderService.generateText(
                    "workflow_image_prompt_select",
                    systemPrompt,
                    userPrompt,
                    0.1,
                    false
            );
            if (!Boolean.TRUE.equals(aiResult.get("ok"))) {
                return null;
            }
            String selectedKey = extractImagePromptCategoryKey(String.valueOf(aiResult.getOrDefault("content", "")), promptConfigs);
            if (selectedKey.isBlank()) {
                return null;
            }
            for (Map<String, Object> cfg : promptConfigs) {
                String key = modelConfigService.textConfig(cfg, "", "categoryKey", "name");
                if (key.equalsIgnoreCase(selectedKey)) {
                    return cfg;
                }
            }
        } catch (Exception e) {
            log.debug("[image-prompt] AI category selection fallback, errorType={}", e.getClass().getSimpleName());
        }
        return null;
    }

    private String extractImagePromptCategoryKey(String content, List<Map<String, Object>> promptConfigs) {
        String raw = content == null ? "" : content.trim();
        if (raw.isBlank()) return "";
        String cleaned = raw.replace("```json", "").replace("```", "").trim();
        Map<String, String> candidates = new LinkedHashMap<>();
        for (Map<String, Object> cfg : promptConfigs) {
            String key = modelConfigService.textConfig(cfg, "", "categoryKey", "name");
            if (!key.isBlank()) {
                candidates.put(key.toLowerCase(), key);
            }
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(cleaned, new TypeReference<Map<String, Object>>() {});
            for (String field : List.of("categoryKey", "key", "category", "category_key")) {
                String value = text(parsed.get(field), "").trim().toLowerCase();
                if (candidates.containsKey(value)) {
                    return candidates.get(value);
                }
            }
        } catch (Exception ignored) {
        }
        String lowered = cleaned.toLowerCase();
        if (candidates.containsKey(lowered)) {
            return candidates.get(lowered);
        }
        for (String key : candidates.keySet()) {
            Pattern pattern = Pattern.compile("(?<![a-z0-9_])" + Pattern.quote(key) + "(?![a-z0-9_])");
            Matcher matcher = pattern.matcher(lowered);
            if (matcher.find()) {
                return candidates.get(key);
            }
        }
        return "";
    }

    private String buildPrompt(String systemPrompt, String userPrompt,
                                String itemTitle, String itemDesc) {
        // 如果系统提示词包含 {{TITLE}} 或 {{CONTENT}} 占位符，则直接替换
        if (systemPrompt.contains("{{TITLE}}") || systemPrompt.contains("{{CONTENT}}")) {
            String prompt = systemPrompt
                    .replace("{{TITLE}}", itemTitle != null ? itemTitle.trim() : "")
                    .replace("{{CONTENT}}", itemDesc != null ? truncate(itemDesc.trim(), 3000) : "");
            if (!userPrompt.isBlank()) {
                prompt += "\n\n用户生图要求：" + userPrompt.trim();
            }
            return prompt.trim();
        }
        // 兼容旧格式：系统提示词 + 追加标题/描述
        StringBuilder sb = new StringBuilder();
        if (!systemPrompt.isBlank()) sb.append(systemPrompt.trim()).append("\n");
        if (!itemTitle.isBlank()) sb.append("商品标题：").append(itemTitle.trim()).append("\n");
        if (!itemDesc.isBlank()) sb.append("商品描述：").append(truncate(itemDesc.trim(), 600)).append("\n");
        if (!userPrompt.isBlank()) sb.append("用户生图要求：").append(userPrompt.trim()).append("\n");
        sb.append("【重要提醒】禁止水印、店铺名、签名、联系方式、QQ/微信/网址、二维码。聚焦商品核心主体，电商广告扁平海报风格，高对比度深色背景+亮色点缀，主体大而居中。禁止3D渲染、霓虹光效、科幻场景、粒子特效、多设备堆叠。");
        return sb.toString().trim();
    }

    private long tokensPerImage(Map<String, Object> cfg) {
        long fromCfg = Math.max(0, modelConfigService.longConfig(cfg, DEFAULT_TOKENS_PER_IMAGE,
                "tokensPerImage", "tokenCostPerImage", "imageTokenCost"));
        if (fromCfg > 0) return fromCfg;
        // 兜底：从 ai_model_price_config 表读取
        String moduleKey = String.valueOf(cfg.getOrDefault("moduleKey", ModelConfigService.IMAGE));
        try {
            Long fromDb = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(tokens_per_image,0) FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND module_key=? ORDER BY id DESC LIMIT 1",
                    Long.class, moduleKey);
            return fromDb == null ? 0 : Math.max(0, fromDb);
        } catch (Exception e) {
            return 0;
        }
    }

    /**
     * 读取每张图片成本（元）。
     * 优先从配置项读取，兜底从 ai_model_price_config.cost_per_image 读取。
     */
    private BigDecimal costPerImage(Map<String, Object> cfg) {
        Object v = cfg.get("cost");
        if (v == null) v = cfg.get("costPerImage");
        if (v != null && !String.valueOf(v).isBlank()) {
            try {
                BigDecimal bd = new BigDecimal(String.valueOf(v).trim().replace("¥", "").replace(",", ""));
                if (bd.compareTo(BigDecimal.ZERO) > 0) return bd;
            } catch (Exception ignored) {
            }
        }
        String moduleKey = String.valueOf(cfg.getOrDefault("moduleKey", ModelConfigService.IMAGE));
        try {
            BigDecimal fromDb = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(cost_per_image,0) FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND module_key=? ORDER BY id DESC LIMIT 1",
                    BigDecimal.class, moduleKey);
            return fromDb == null ? BigDecimal.ZERO : fromDb.max(BigDecimal.ZERO);
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    /** 计算本次生图成本（分）= 每张成本(元) × 张数 × 100。 */
    private long calcCostCent(Map<String, Object> cfg, int count) {
        if (count <= 0) return 0;
        BigDecimal perImage = costPerImage(cfg);
        if (perImage.compareTo(BigDecimal.ZERO) <= 0) return 0;
        return perImage.multiply(BigDecimal.valueOf(count))
                .multiply(BigDecimal.valueOf(100))
                .setScale(0, RoundingMode.CEILING)
                .longValue();
    }

    private String defaultPrompt(Map<String, Object> cfg) {
        return modelConfigService.textConfig(cfg,
                "生成一张闲鱼/淘宝风格的电商商品主图（正方形1:1）。要求：①扁平广告海报设计风格，禁止3D渲染、赛博朋克霓虹光效、科幻元素、粒子特效、真实照片风格；②商品核心主体大而居中突出，占画面60%以上；③使用高对比度深色或纯色背景（深蓝/深紫/黑色/深灰），搭配高饱和度亮色（红/黄/蓝/橙/白）色块、圆角边框、彩色标签徽章、横幅装饰条等电商设计元素；④构图简洁有力，视觉焦点集中，一眼看清卖什么，禁止多设备堆叠、复杂场景、多余装饰元素；⑤整体效果类似淘宝/拼多多爆款商品首图，有强烈的点击吸引力和促销广告感；⑥严禁任何水印、店铺名、签名、联系方式、QQ/微信/网址；⑦如包含文字，使用粗大醒目的无衬线字体，文字简短有力（2-4字以内），不生成大段中文文字。",
                "defaultSystemPrompt", "systemPrompt", "defaultPrompt");
    }

    private String normalizeSize(String raw) {
        String s = raw == null ? "" : raw.trim();
        if (s.contains(" ")) s = s.split(" ")[0];
        if (!s.matches("\\d{3,4}x\\d{3,4}")) return "1024x1024";
        return s;
    }

    private String normalizedBaseUrl(String raw) {
        String s = endpointPolicy.validateBaseUrl(raw);
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        if (s.endsWith("/v1")) return s;
        return s + "/v1";
    }

    private int parseImageCount(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return 1;
        try {
            int n = Integer.parseInt(String.valueOf(value));
            if (n < 1 || n > MAX_IMAGE_COUNT) {
                throw new BizException(400, "图片数量必须在 1 到 " + MAX_IMAGE_COUNT + " 之间");
            }
            return n;
        } catch (NumberFormatException ignored) {
            throw new BizException(400, "图片数量必须为整数");
        }
    }

    private String text(Object value, String fallback) {
        if (value == null) return fallback;
        String s = String.valueOf(value).trim();
        return s.isBlank() ? fallback : s;
    }

    private String truncate(String s, int max) {
        if (s == null) return "";
        return s.length() <= max ? s : s.substring(0, max);
    }
}
