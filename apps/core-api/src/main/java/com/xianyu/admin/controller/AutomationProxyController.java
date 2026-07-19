package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AiProviderService;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.ModelConfigService;
import com.xianyu.admin.service.OperationAuditService;
import com.xianyu.admin.service.OpportunityDraftService;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.TenantSupportService;
import com.xianyu.admin.service.XianyuAccountService;
import com.xianyu.admin.service.ImageGenerationService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.multipart.MultipartHttpServletRequest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 前台访问 Java；Java 再按职责把执行类请求代理到 Python/爬虫服务。
 */
@RestController
@RequestMapping("/api")
public class AutomationProxyController {
    private static final Logger log = LoggerFactory.getLogger(AutomationProxyController.class);
    private final AutomationClient automationClient;
    private final JdbcTemplate jdbcTemplate;
    private final OperationAuditService auditService;
    private final AiProviderService aiProviderService;
    private final OpportunityDraftService opportunityDraftService;
    private final ImageGenerationService imageGenerationService;
    private final ModelConfigService modelConfigService;
    private final XianyuAccountService accountService;
    private final TenantSupportService tenantSupportService;
    private final OpenSourceContentService contentService;
    private static final ObjectMapper jsonMapper = new ObjectMapper();

    @Value("${xianyu.cookie.crypto-secret:dev-only-cookie-crypto-secret-change-me-32-chars}")
    private String cookieCryptoSecret;

    private static final long SSE_TICKET_TTL_SECONDS = 60L;
    private static final int MAX_SSE_TICKETS = 10_000;
    private static final int MAX_SSE_TICKETS_PER_USER = 5;
    private static final ConcurrentHashMap<String, SseTicket> SSE_TICKETS = new ConcurrentHashMap<>();

    public AutomationProxyController(AutomationClient automationClient, JdbcTemplate jdbcTemplate, OperationAuditService auditService,
                                     AiProviderService aiProviderService, OpportunityDraftService opportunityDraftService,
                                     ImageGenerationService imageGenerationService, ModelConfigService modelConfigService,
                                     XianyuAccountService accountService, TenantSupportService tenantSupportService,
                                     OpenSourceContentService contentService) {
        this.automationClient = automationClient;
        this.jdbcTemplate = jdbcTemplate;
        this.auditService = auditService;
        this.aiProviderService = aiProviderService;
        this.opportunityDraftService = opportunityDraftService;
        this.imageGenerationService = imageGenerationService;
        this.modelConfigService = modelConfigService;
        this.accountService = accountService;
        this.tenantSupportService = tenantSupportService;
        this.contentService = contentService;
    }

    @GetMapping("/automation/health")
    public Result<Object> automationHealth() {
        return Result.ok(automationClient.getInternalForData("/api/internal/health", Map.of()));
    }

    @GetMapping("/automation/bridge/health")
    public Result<Object> automationBridgeHealth() {
        boolean ok = automationClient.pingInternalHealth();
        if (!ok) {
            throw new BizException(503, "自动化桥接服务当前不可用");
        }
        return Result.ok(Map.of("ok", ok));
    }

    @PostMapping("/automation/bridge/send-message")
    public Result<Object> bridgeSendMessage(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        log.info("Java -> Python sendMessage 转发 tenantId={}, accountId={}",
                TenantContext.getCurrentTenantId(),
                payload.getOrDefault("xianyuAccountId", payload.get("accountId")));
        return Result.ok(automationClient.postInternalForData("/api/websocket/sendMessage", payload));
    }

    @PostMapping("/automation/bridge/websocket/start")
    public Result<Object> bridgeWebsocketStart(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        log.info("Java -> Python websocket/start 转发 tenantId={}, accountId={}",
                TenantContext.getCurrentTenantId(),
                payload.getOrDefault("xianyuAccountId", payload.get("accountId")));
        return Result.ok(automationClient.postInternalForData("/api/websocket/start", payload));
    }

    @PostMapping("/automation/bridge/websocket/status")
    public Result<Object> bridgeWebsocketStatus(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        return Result.ok(automationClient.postInternalForData("/api/websocket/status", payload));
    }

    @PostMapping("/automation/bridge/conversations")
    public Result<Object> bridgeConversations(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        Object accountId = payload.getOrDefault("xianyuAccountId", payload.get("accountId"));
        if (accountId == null) {
            throw new BizException(400, "请选择闲鱼账号");
        }
        Object limit = payload.getOrDefault("limit", 50);
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(automationClient.getInternalForData(
                "/api/msg/online/conversations",
                Map.of("xianyuAccountId", accountId, "limit", limit, "tenantId", tenantId),
                tenantId
        ));
    }

    @PostMapping("/automation/bridge/context")
    public Result<Object> bridgeContext(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        return Result.ok(automationClient.postInternalForData("/api/msg/context", payload));
    }

    @GetMapping("/business-opportunity/search")
    public Result<Object> businessSearch(@RequestParam(defaultValue = "") String q,
                                         @RequestParam(defaultValue = "20") int limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        try {
            return Result.ok(automationClient.getInternalForData("/api/internal/business-opportunity/search", Map.of(
                    "q", q,
                    "tenantId", tenantId,
                    "limit", limit
            )));
        } catch (Exception ex) {
            int safeLimit = Math.max(1, Math.min(limit, 50));
            if (q == null || q.isBlank()) {
                return Result.ok(jdbcTemplate.queryForList(
                        "SELECT id, external_goods_id AS itemId, title, price, stock, image_url AS imageUrl, description, category, status, updated_time AS updatedTime " +
                                "FROM xianyu_goods WHERE tenant_id=? AND deleted=0 ORDER BY updated_time DESC, id DESC LIMIT ?",
                        tenantId, safeLimit));
            }
            return Result.ok(jdbcTemplate.queryForList(
                    "SELECT id, external_goods_id AS itemId, title, price, stock, image_url AS imageUrl, description, category, status, updated_time AS updatedTime " +
                            "FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND (title LIKE CONCAT('%',?,'%') OR description LIKE CONCAT('%',?,'%') OR category LIKE CONCAT('%',?,'%')) ORDER BY updated_time DESC, id DESC LIMIT ?",
                    tenantId, q, q, q, safeLimit));
        }
    }

    @GetMapping("/business-opportunity/shop")
    public Result<Object> businessShop(@RequestParam(defaultValue = "") String url) {
        throw new BizException(410, "此入口已停用，请通过店铺采集任务入口提交并查看真实任务状态");
    }

    @PostMapping("/business-opportunity/collect-shop")
    public Result<Object> collectShop(@RequestBody(required = false) Map<String, Object> body) {
        throw new BizException(410, "此入口已停用，请使用 /api/crawler/import/goofish");
    }

    @PostMapping("/crawler/import/goofish")
    public Object importGoofish(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            attachCrawlerCookie(payload);
            return automationClient.postCrawler("/api/import/goofish", payload);
        } catch (Exception ex) {
            log.error("店铺抓取任务提交失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "店铺抓取服务暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/crawler/crawl-jobs/{jobId}")
    public Object crawlJob(@PathVariable("jobId") String jobId) {
        try {
            return automationClient.getCrawler("/api/crawl-jobs/" + jobId, Map.of());
        } catch (Exception ex) {
            log.error("查询抓取任务失败, jobId={}, errorType={}", jobId, ex.getClass().getSimpleName());
            throw new BizException(503, "抓取任务状态暂时无法查询，请稍后重试");
        }
    }

    @GetMapping("/crawler/goofish/stores/{userId}/items")
    public Object storeItems(@PathVariable("userId") String userId) {
        try {
            return automationClient.getCrawler("/api/goofish/stores/" + userId + "/items", Map.of());
        } catch (Exception ex) {
            log.error("获取店铺商品失败, userId={}, errorType={}", userId, ex.getClass().getSimpleName());
            throw new BizException(503, "店铺商品暂时无法查询，请稍后重试");
        }
    }

    @GetMapping("/goofish/search")
    public Result<Object> goofishSearch(
            @RequestParam String q,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "auto") String mode) {
        String keyword = q == null ? "" : q.trim();
        if (keyword.isBlank()) {
            throw new BizException(400, "请输入搜索关键词");
        }
        if (keyword.length() > 50) {
            throw new BizException(400, "关键词长度不能超过 50 个字符");
        }

        int safePage = Math.max(1, Math.min(page, 100));
        int safePageSize = Math.max(1, Math.min(pageSize, 50));
        // 搜索模式：fast=快速搜索(直调MTOP)，slow=慢速搜索(浏览器)，auto=自动降级
        String safeMode = (mode == null || mode.isBlank()) ? "auto" : mode.trim().toLowerCase();
        if (!"fast".equals(safeMode) && !"slow".equals(safeMode) && !"auto".equals(safeMode)) {
            safeMode = "auto";
        }
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("q", keyword);
        params.put("page", safePage);
        params.put("pageSize", safePageSize);
        params.put("mode", safeMode);
        if (accountId != null) {
            params.put("accountId", accountId);
        }

        try {
            // 商品关键词搜索主链路：前端 -> Java 网关 -> Python MTOP 搜索。
            // Node crawler-service 只负责店铺异步采集，避免关键词搜索绕过闲鱼登录 Cookie 与 MTOP 签名。
            // 超时 45 秒：搜索场景不求解滑块（直接 goto 搜索 URL），时间预算：
            //   - 快速搜索（直调 MTOP）：1-3s
            //   - 慢速搜索（Node Playwright + Python patchright 兜底）：最多 21s（6s MTOP 等待 + 15s Python）
            //   - 自动模式（快速失败后降级慢速）：最坏 ~30s
            // 45s 给足余量，同时避免卡死时让用户等太久。
            // 各层超时：前端 axios=180s，Java 网关→Python=45s，Python→crawler=30s。
            Map<String, Object> raw = automationClient.getInternal(
                    "/api/business-opportunity/goofish-search",
                    params,
                    45
            );
            Object code = raw.get("code");
            if (code != null && ("200".equals(String.valueOf(code)) || "0".equals(String.valueOf(code)))) {
                return Result.ok(raw.get("data"));
            }
            // Python 端已对业务错误（Cookie失效、Token过期、安全验证等）返回明确 msg + errorType
            // 直接透传 Python 的友好消息与状态码，避免覆盖导致用户看到无关的"未搜索到商品"
            String message = String.valueOf(raw.getOrDefault("msg", raw.getOrDefault("message", "商品搜索失败")));
            Object codeObj = raw.get("code");
            int bizCode = 503;
            if (codeObj != null) {
                try {
                    bizCode = Integer.parseInt(String.valueOf(codeObj));
                } catch (NumberFormatException ignored) {
                    // 保持默认 503
                }
            }
            // 从 Python 的 data 字段提取 errorType，透传给前端用于区分错误类型
            Object rawData = raw.get("data");
            String errorType = "unknown";
            if (rawData instanceof Map) {
                Object et = ((Map<?, ?>) rawData).get("errorType");
                if (et != null) {
                    errorType = String.valueOf(et);
                }
            }
            // 根据 errorType 映射到 HTTP 状态码（409 cookie失效 / 503 服务异常 / 502 其他错误）
            if ("cookie_expired".equals(errorType)) {
                throw new BizException(409, message);
            }
            if ("blocked".equals(errorType) || "captcha_failed".equals(errorType)) {
                throw new BizException(503, message);
            }
            // 兼容旧版 Python（未返回 errorType）：通过 msg 关键词识别 cookie 失效
            if (message.contains("Cookie") && (message.contains("失效") || message.contains("过期") || message.contains("_m_h5_tk"))) {
                throw new BizException(409, message);
            }
            throw new BizException(bizCode == 503 ? 503 : 502, message);
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            String detail = (ex.getMessage() != null) ? ex.getMessage() : "";
            log.warn("Python MTOP 商品搜索失败 page={}, pageSize={}, accountId={}, errorType={}",
                    safePage, safePageSize, accountId, ex.getClass().getSimpleName());

            // 1. 服务未启动：连接拒绝
            if (detail.contains("ConnectException") || detail.contains("Connection refused")
                    || detail.contains("HttpHostConnectException") || detail.contains("NoRouteToHostException")) {
                throw new BizException(503, "商品搜索服务暂时不可用，请稍后重试");
            }
            // 2. 连接超时
            if (detail.contains("timeout") || detail.contains("TimeoutException")
                    || detail.contains("connect timed out") || detail.contains("Read timed out")) {
                throw new BizException(503, "商品搜索服务响应超时，请稍后重试");
            }
            // 3. Token/Cookie 失效（Python 端业务异常传播到 HTTP 层）
            // 闲鱼 MTOP 实际返回 FAIL_SYS_TOKEN_EXOIRED（拼写错误），同时兼容正确拼写 FAIL_SYS_TOKEN_EXPIRED
            if (detail.contains("Token 已过期") || detail.contains("登录已过期")
                    || detail.contains("FAIL_SYS_TOKEN_EXOIRED") || detail.contains("FAIL_SYS_TOKEN_EXPIRED")
                    || detail.contains("FAIL_SYS_SESSION_EXPIRED")
                    || detail.contains("_m_h5_tk") || detail.contains("Cookie已失效") || detail.contains("Cookie 已失效")) {
                throw new BizException(409, "闲鱼账号登录状态已失效，请重新登录后再搜索");
            }
            // 4. HTTP 服务端错误
            if (detail.contains("HTTP 404")) {
                throw new BizException(502, "商品搜索服务接口配置异常，请联系技术支持");
            }
            if (detail.contains("HTTP 5")) {
                throw new BizException(502, "商品搜索上游服务异常，请稍后重试");
            }
            // 5. 余下所有异常统一按"调用自动化服务失败"处理
            throw new BizException(502, "商品搜索失败，请稍后重试");
        }
    }


    @PostMapping("/account/list")
    public Result<Object> accountList() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT a.id, a.external_uid, a.nickname, a.avatar_url, a.remark, a.display_name, a.introduction, " +
                        "auth.cookie_status, auth.last_login_status_code, auth.last_login_status_message, auth.last_login_check_time, " +
                        "r.ws_status, r.online_status " +
                        "FROM xianyu_account a " +
                        "LEFT JOIN xianyu_account_auth auth ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id AND auth.deleted = 0 " +
                        "LEFT JOIN xianyu_account_runtime r ON r.account_id = a.id AND (r.tenant_id = a.tenant_id OR r.tenant_id IS NULL) " +
                        "WHERE a.tenant_id=? AND a.deleted=0 ORDER BY a.id DESC",
                tenantId
        );
        List<Map<String, Object>> accounts = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> acct = new LinkedHashMap<>();
            acct.put("id", row.get("id"));
            acct.put("externalUid", row.get("external_uid"));
            acct.put("nickname", row.get("nickname"));
            acct.put("displayName", row.get("display_name") != null ? row.get("display_name") : row.get("nickname"));
            acct.put("avatarUrl", row.get("avatar_url"));
            acct.put("remark", row.get("remark"));
            acct.put("introduction", row.get("introduction"));
            acct.put("cookieStatus", row.get("cookie_status"));
            acct.put("loginStatusCode", row.get("last_login_status_code"));
            acct.put("loginStatusMessage", row.get("last_login_status_message"));
            acct.put("loginCheckTime", row.get("last_login_check_time"));
            acct.put("wsStatus", row.get("ws_status"));
            acct.put("onlineStatus", row.get("online_status"));
            Object cookieStatus = row.get("cookie_status");
            Object loginStatusCode = row.get("last_login_status_code");
            acct.put("authUsable", cookieStatus != null
                    && "1".equals(String.valueOf(cookieStatus))
                    && "OK".equalsIgnoreCase(String.valueOf(loginStatusCode)));
            accounts.add(acct);
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("accounts", accounts);
        return Result.ok(data);
    }

    @PostMapping("/account/updateCookie")
    public Result<Object> accountUpdateCookie(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        Long accountId = longValue(payload.getOrDefault("xianyuAccountId", payload.get("accountId")));
        String cookie = stringValue(payload.get("cookie"));
        if (accountId == null) {
            throw new BizException(400, "accountId 不能为空");
        }
        if (cookie == null || cookie.isBlank()) {
            throw new BizException(400, "Cookie 不能为空");
        }
        Object result = accountService.updateCookie(TenantContext.getCurrentTenantId(), accountId, cookie);
        auditAccountOperation(payload, "ACCOUNT_COOKIE_UPDATE", "更新闲鱼账号Cookie", request);
        return Result.ok(result);
    }

    @PostMapping("/opportunity/analyze")
    public Result<Object> opportunityAnalyze(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        String keyword = String.valueOf(payload.getOrDefault("keyword", "")).trim();
        if (keyword.isBlank()) {
            throw new BizException(400, "请输入关键词");
        }
        try {
            return Result.ok(automationClient.postInternalForData("/api/opportunity/analyze", payload));
        } catch (Exception ex) {
            int safeLimit = 20;
            Long tenantId = TenantContext.getCurrentTenantId();
            List<Map<String, Object>> fallback = jdbcTemplate.queryForList(
                    "SELECT id, external_goods_id AS itemId, title, price, stock, image_url AS image, description, category, status, updated_time AS updatedTime " +
                            "FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND (title LIKE CONCAT('%',?,'%') OR description LIKE CONCAT('%',?,'%') OR category LIKE CONCAT('%',?,'%')) ORDER BY updated_time DESC, id DESC LIMIT ?",
                    tenantId, keyword, keyword, keyword, safeLimit);
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("keyword", keyword);
            summary.put("totalCount", fallback.size());
            summary.put("heatLevel", fallback.size() >= 10 ? "中" : "低");
            summary.put("riskLevel", "未知");
            summary.put("actions", List.of("AI分析服务暂不可用，已返回本地商品匹配结果", "建议稍后重试完整分析"));
            return Result.ok(Map.of("items", fallback, "summary", summary, "fallback", true, "message", "AI分析服务暂不可用，已返回本地商品匹配结果"));
        }
    }

    @GetMapping("/opportunity/ai-status")
    public Result<Object> opportunityAiStatus() {
        return Result.ok(aiProviderService.status());
    }

    @PostMapping("/opportunity/rewrite")
    public Result<Object> opportunityRewrite(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        if (!aiProviderService.isConfigured()) {
            throw new BizException(503, "AI 改写功能尚未配置，当前不可用");
        }
        Map<String, Object> result = rewriteWithConfiguredProvider(payload);
        if (!Boolean.TRUE.equals(result.getOrDefault("ok", true))) {
            throw new BizException(502, "AI 改写服务未返回可用结果，请稍后重试");
        }
        Long draftId = opportunityDraftService.saveDraft(TenantContext.getCurrentTenantId(), TenantContext.getCurrentUserId(), payload, result,
                String.valueOf(result.getOrDefault("provider", result.getOrDefault("providerName", "openai-compatible"))),
                String.valueOf(result.getOrDefault("model", result.getOrDefault("modelName", ""))));
        Map<String, Object> response = new LinkedHashMap<>(result);
        response.put("draftId", draftId);
        response.put("saved", true);
        return Result.ok(response);
    }

    @GetMapping("/opportunity/image-status")
    public Result<Object> opportunityImageStatus() {
        return Result.ok(imageGenerationService.status());
    }

    @GetMapping("/opportunity/image-models")
    public Result<Object> opportunityImageModels() {
        Map<String, Object> status = imageGenerationService.status();
        List<Map<String, Object>> allModels = (List<Map<String, Object>>) status.get("models");
        List<Map<String, Object>> availableModels = new ArrayList<>();
        if (allModels != null) {
            for (Map<String, Object> model : allModels) {
                if (Boolean.TRUE.equals(model.get("configured")) && Boolean.TRUE.equals(model.get("enabled"))) {
                    availableModels.add(model);
                }
            }
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("models", availableModels);
        result.put("count", availableModels.size());
        return Result.ok(result);
    }

    @PostMapping("/opportunity/generate-images")
    public Result<Object> opportunityGenerateImages(@RequestBody(required = false) Map<String, Object> body) {
        try {
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            injectTenantId(payload);
            return Result.ok(imageGenerationService.generate(payload));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("生成图片失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "图片生成服务暂时不可用，请稍后重试");
        }
    }

    @GetMapping("/opportunity/image-history")
    public Result<Object> opportunityImageHistory(
            @RequestParam(required = false) String source,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Long workflowId,
            @RequestParam(required = false) String nodeKey,
            @RequestParam(required = false) Integer page,
            @RequestParam(required = false) Integer pageSize,
            @RequestParam(defaultValue = "20") int limit) {
        try {
            Long tenantId = TenantContext.getCurrentTenantId();
            // 向后兼容：未传 source 参数时走旧接口（返回 list 结构，商机发掘页面使用）
            if (source == null || source.isBlank()) {
                return Result.ok(imageGenerationService.listHistory(tenantId, limit));
            }
            // 新接口：传了 source 参数（all/opportunity/workflow）走分页查询
            int safePage = page == null ? 1 : Math.max(1, page);
            int safePageSize = pageSize == null ? 20 : Math.min(Math.max(pageSize, 1), 100);
            return Result.ok(imageGenerationService.listHistoryPaged(
                    tenantId, source, status, keyword, workflowId, nodeKey, safePage, safePageSize));
        } catch (Exception e) {
            log.error("查询图片生成历史失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "图片生成历史暂时无法查询，请稍后重试");
        }
    }

    @GetMapping("/opportunity/image-history/{requestId}")
    public Result<Object> opportunityImageHistoryDetail(@PathVariable("requestId") String requestId) {
        try {
            return Result.ok(imageGenerationService.getHistory(requireTenantId(), requestId));
        } catch (BizException e) {
            throw e;
        }
    }

    @PostMapping("/opportunity/image-recover/{historyId}")
    public Result<Object> opportunityImageRecover(@PathVariable("historyId") Long historyId) {
        try {
            return Result.ok(imageGenerationService.recoverImages(requireTenantId(), historyId));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("恢复图片失败, historyId={}, errorType={}", historyId, e.getClass().getSimpleName());
            throw new BizException(503, "图片暂时无法恢复，请稍后重试");
        }
    }

    @GetMapping("/opportunity/drafts")
    public Result<Object> opportunityDrafts(@RequestParam(required = false, defaultValue = "") String keyword,
                                            @RequestParam(defaultValue = "1") int current,
                                            @RequestParam(defaultValue = "20") int size) {
        return Result.ok(opportunityDraftService.listDrafts(TenantContext.getCurrentTenantId(), keyword, current, size));
    }

    @GetMapping("/opportunity/drafts/{id}")
    public Result<Object> opportunityDraftDetail(@PathVariable("id") Long id) {
        return Result.ok(opportunityDraftService.detail(TenantContext.getCurrentTenantId(), id));
    }

    @GetMapping("/opportunity/history")
    public Result<Object> opportunityHistory(@RequestParam(required = false, defaultValue = "") String keyword,
                                             @RequestParam(defaultValue = "1") int current,
                                             @RequestParam(defaultValue = "20") int size) {
        Map<String, Object> params = new LinkedHashMap<>();
        injectTenantId(params);
        params.put("keyword", keyword == null ? "" : keyword);
        params.put("current", current);
        params.put("size", size);
        try {
            return Result.ok(automationClient.getInternalForData("/api/opportunity/history", params));
        } catch (Exception ex) {
            log.error("查询商机历史失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "商机历史暂时无法查询，请稍后重试");
        }
    }


    private Map<String, Object> rewriteWithConfiguredProvider(Map<String, Object> payload) {
        Object itemObj = payload.get("item");
        if (!(itemObj instanceof Map<?, ?> rawItem)) {
            return Map.of("ok", false, "message", "请选择需要改写的商品");
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> item = (Map<String, Object>) rawItem;
        String title = String.valueOf(item.getOrDefault("title", "闲置商品"));
        String desc = String.valueOf(item.getOrDefault("description", item.getOrDefault("desc", "")));
        String style = String.valueOf(payload.getOrDefault("style", "friendly"));
        String customPrompt = String.valueOf(payload.getOrDefault("customPrompt", "")).trim();
        String styleName = switch (style) {
            case "professional" -> "专业可信";
            case "concise" -> "简洁直接";
            case "click" -> "吸引点击但不夸大";
            default -> "口语化、亲切自然";
        };
        String rewriteInstruction;
        if (!customPrompt.isEmpty() && !"null".equals(customPrompt)) {
            rewriteInstruction = customPrompt;
        } else {
            rewriteInstruction = "请根据原标题和正文，为闲鱼商品改写一版可直接编辑的商品标题和商品描述，并返回严格 JSON。" +
                "要求：改写后的内容与原标题和正文的相似度在80%以上，保留核心商品信息和卖点，但需重新表述。" +
                "必须真实、不夸大、不承诺站外交易、不包含违禁词；";
        }
        String prompt = rewriteInstruction +
                "JSON格式：{\"title\":\"不超过60字\",\"description\":\"详细描述\",\"tags\":[\"标签1\"],\"safety\":{\"blocked\":false,\"message\":\"安全提示\"}}。" +
                "风格=" + styleName + "；原标题=" + title + "；原正文=" + desc + "；完整商品=" + item;
        // 追加润色强限制（来自后台「通用模型配置」的润色关键词/禁止关键词，前台不可见、不可改）
        String systemPrompt = "你是二手电商商品文案助手，只输出合法合规的中文 JSON。";
        String polishRestriction = modelConfigService.buildPolishRestriction();
        if (!polishRestriction.isBlank()) {
            systemPrompt = systemPrompt + "\n" + polishRestriction;
        }
        Map<String, Object> ai = aiProviderService.generateText("opportunity_rewrite", systemPrompt, prompt, 0.7D);
        if (!Boolean.TRUE.equals(ai.get("ok"))) {
            return Map.of("ok", false, "message", String.valueOf(ai.getOrDefault("error", "AI改写失败")), "requestId", ai.getOrDefault("requestId", ""));
        }
        String content = String.valueOf(ai.getOrDefault("content", ""));
        Map<String, Object> rewrite = parseRewriteContent(content, title, style);
        // 检查改写结果是否与原文一致（AI 未生效）
        String rewriteTitle = String.valueOf(rewrite.getOrDefault("title", ""));
        String rewriteDesc = String.valueOf(rewrite.getOrDefault("description", ""));
        boolean titleUnchanged = normalizeForCompare(rewriteTitle).contains(normalizeForCompare(title))
            || normalizeForCompare(title).contains(normalizeForCompare(rewriteTitle));
        boolean descUnchanged = normalizeForCompare(rewriteDesc).contains(normalizeForCompare(desc))
            || normalizeForCompare(desc).contains(normalizeForCompare(rewriteDesc));
        if (titleUnchanged && descUnchanged) {
            return Map.of("ok", false, "message", "AI 改写未生效，返回内容与原文一致，请重试或调整提示词", "requestId", ai.getOrDefault("requestId", ""));
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("rewrite", rewrite);
        out.put("provider", ai.get("provider"));
        out.put("model", ai.get("model"));
        out.put("requestId", ai.get("requestId"));
        out.put("usage", ai.getOrDefault("usage", Map.of()));
        out.put("fallback", false);
        return out;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseRewriteContent(String content, String fallbackTitle, String style) {
        String json = extractJsonObject(content);
        if (!json.isBlank()) {
            try {
                Map<String, Object> parsed = jsonMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
                Map<String, Object> rewrite = new LinkedHashMap<>();
                rewrite.put("title", abbreviate(String.valueOf(parsed.getOrDefault("title", firstNonBlankLine(content, fallbackTitle))), 60));
                rewrite.put("description", String.valueOf(parsed.getOrDefault("description", content)));
                Object tags = parsed.get("tags");
                rewrite.put("tags", tags instanceof List<?> ? tags : List.of("闲置", "AI改写", style));
                Object safety = parsed.get("safety");
                rewrite.put("safety", safety instanceof Map<?, ?> ? safety : Map.of("blocked", false, "riskTags", detectRiskTags(content), "message", "AI输出，发布前请人工复核"));
                return rewrite;
            } catch (Exception ignored) {
            }
        }
        Map<String, Object> rewrite = new LinkedHashMap<>();
        rewrite.put("title", abbreviate(firstNonBlankLine(content, "自用闲置｜" + abbreviate(fallbackTitle, 42)), 60));
        rewrite.put("description", content);
        rewrite.put("tags", List.of("闲置", "AI改写", style));
        rewrite.put("safety", Map.of("blocked", false, "riskTags", detectRiskTags(content), "message", "AI输出，发布前请人工复核"));
        return rewrite;
    }

    private String extractJsonObject(String content) {
        if (content == null) return "";
        String s = content.trim();
        int start = s.indexOf('{');
        int end = s.lastIndexOf('}');
        return start >= 0 && end > start ? s.substring(start, end + 1) : "";
    }

    /** 归一化文本用于比较：去空白、去标点、转小写 */
    private String normalizeForCompare(String s) {
        if (s == null) return "";
        return s.replaceAll("[\\s\\p{P}]+", "").toLowerCase().trim();
    }

    @PostMapping("/sse/ticket")
    public Result<Map<String, Object>> createSseTicket() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        String ticket = UUID.randomUUID().toString().replace("-", "");
        long expiresAt = Instant.now().getEpochSecond() + SSE_TICKET_TTL_SECONDS;
        synchronized (SSE_TICKETS) {
            cleanupExpiredSseTickets();
            List<Map.Entry<String, SseTicket>> sameUserTickets = SSE_TICKETS.entrySet().stream()
                    .filter(entry -> userId.equals(entry.getValue().userId())
                            && tenantId.equals(entry.getValue().tenantId()))
                    .sorted(Map.Entry.comparingByValue(
                            java.util.Comparator.comparingLong(SseTicket::expiresAtEpochSecond)))
                    .toList();
            int ticketsToRemove = Math.max(0, sameUserTickets.size() - MAX_SSE_TICKETS_PER_USER + 1);
            for (int index = 0; index < ticketsToRemove; index++) {
                SSE_TICKETS.remove(sameUserTickets.get(index).getKey(), sameUserTickets.get(index).getValue());
            }
            if (SSE_TICKETS.size() >= MAX_SSE_TICKETS) {
                throw new BizException(429, "SSE 连接凭证请求过于频繁，请稍后重试");
            }
            SSE_TICKETS.put(ticket, new SseTicket(userId, tenantId, expiresAt));
        }
        return Result.ok(Map.of("ticket", ticket, "expiresInSeconds", SSE_TICKET_TTL_SECONDS));
    }

    @GetMapping(value = "/sse/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public StreamingResponseBody sseSubscribe(@RequestParam("ticket") String ticket) {
        return outputStream -> {
            try {
                // 将 consumeSseTicket 移到 lambda 内部，确保异常也以 SSE 格式返回
                SseTicket sseTicket;
                try {
                    sseTicket = consumeSseTicket(ticket);
                } catch (BizException e) {
                    String errorEvent = "event: error\ndata: {\"type\":\"error\",\"message\":\"" + escapeJson(e.getMessage()) + "\"}\n\n";
                    try {
                        outputStream.write(errorEvent.getBytes(StandardCharsets.UTF_8));
                        outputStream.flush();
                    } catch (Exception ignored) {
                        // 客户端已断开，忽略
                    }
                    return;
                }
                automationClient.streamSse("/api/sse/subscribe", Map.of(), outputStream, sseTicket.tenantId());
            } catch (Exception e) {
                String requestId = org.slf4j.MDC.get("requestId");
                log.error("SSE 订阅代理失败, requestId={}, errorType={}", requestId, e.getClass().getSimpleName());
                String safeRequestId = requestId == null ? "" : escapeJson(requestId);
                String errorEvent = "event: error\ndata: {\"type\":\"error\",\"message\":\"实时消息连接暂时不可用\",\"requestId\":\"" + safeRequestId + "\"}\n\n";
                try {
                    outputStream.write(errorEvent.getBytes(StandardCharsets.UTF_8));
                    outputStream.flush();
                } catch (Exception ignored) {
                    // 客户端已断开，忽略
                }
            }
        };
    }

    private SseTicket consumeSseTicket(String ticket) {
        if (ticket == null || ticket.isBlank()) {
            throw new BizException(401, "SSE ticket 缺失");
        }
        SseTicket value = SSE_TICKETS.remove(ticket);
        long now = Instant.now().getEpochSecond();
        if (value == null || value.expiresAtEpochSecond() <= now) {
            throw new BizException(401, "SSE ticket 无效或已过期");
        }
        return value;
    }

    private void cleanupExpiredSseTickets() {
        long now = Instant.now().getEpochSecond();
        SSE_TICKETS.entrySet().removeIf(e -> e.getValue().expiresAtEpochSecond() <= now);
    }

    private record SseTicket(Long userId, Long tenantId, long expiresAtEpochSecond) {}

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }


    private static String abbreviate(String s, int len) {
        if (s == null) return "";
        return s.length() > len ? s.substring(0, len) : s;
    }

    private static String firstNonBlankLine(String content, String fallback) {
        if (content == null) return fallback;
        for (String line : content.split("\\R")) {
            String t = line.replaceAll("^[#\\-\\s:：]+", "").trim();
            if (!t.isBlank()) return t;
        }
        return fallback;
    }

    private static List<String> detectRiskTags(String text) {
        if (text == null || text.isBlank()) return List.of();
        List<String> tags = new java.util.ArrayList<>();
        if (text.matches(".*(绝对|全网最低|稳赚|包治|官方保证).*")) tags.add("夸大/绝对化用语");
        if (text.matches(".*(微信|支付宝|站外|私下交易).*")) tags.add("平台外交易风险");
        if (text.matches(".*(退款不退货|不走平台).*")) tags.add("平台规则风险");
        return tags;
    }


    private void auditAccountOperation(Map<String, Object> payload, String operationType, String desc, HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        Long accountId = numberOrNull(payload.getOrDefault("xianyuAccountId", payload.get("accountId")));
        auditService.record(tenantId, userId, operationType, desc + " | accountId=" + (accountId == null ? "-" : accountId),
                "xianyu_account", accountId, getClientIp(request));
    }

    private Long numberOrNull(Object value) {
        if (value == null) return null;
        try { return Long.parseLong(String.valueOf(value)); }
        catch (Exception ignore) { return null; }
    }

    private Long longValue(Object value) {
        return numberOrNull(value);
    }

    private String stringValue(Object value) {
        if (value == null) return null;
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    private String getClientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }

    /**
     * 店铺抓取需要登录态才能看到完整商品。Cookie 只从服务端当前租户账号读取，
     * 不信任前端传入，也不落日志；如果旧库里是 enc:v1 格式则按 Python 同款 AES-GCM 解密。
     */
    private void attachCrawlerCookie(Map<String, Object> payload) {
        if (payload == null) return;
        payload.remove("cookie");
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) return;
        try {
            List<String> cookies = jdbcTemplate.queryForList(
                    "SELECT auth.encrypted_cookie " +
                    "FROM xianyu_account_auth auth " +
                            "JOIN xianyu_account a ON a.id = auth.account_id AND a.tenant_id = auth.tenant_id " +
                            "WHERE auth.tenant_id=? AND auth.deleted=0 AND a.deleted=0 AND a.status=1 " +
                            "AND auth.encrypted_cookie IS NOT NULL AND auth.encrypted_cookie<>'' " +
                            "ORDER BY ((auth.cookie_status = 1) AND (auth.last_login_status_code = 'OK')) DESC, auth.updated_time DESC LIMIT 1",
                    String.class,
                    tenantId
            );
            if (!cookies.isEmpty()) {
                String cookie = decryptCookieIfNeeded(cookies.get(0));
                if (cookie != null && !cookie.isBlank()) {
                    payload.put("cookie", cookie);
                }
            }
        } catch (Exception ex) {
            log.error("店铺抓取读取账号登录凭证失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "账号登录凭证暂时无法读取，已停止提交抓取任务");
        }
    }

    private String decryptCookieIfNeeded(String stored) {
        if (stored == null || !stored.startsWith("enc:v1:")) return stored;
        try {
            String[] parts = stored.split(":", 4);
            if (parts.length != 4) {
                throw new IllegalStateException("encrypted cookie format is invalid");
            }
            byte[] iv = Base64.getUrlDecoder().decode(padBase64(parts[2]));
            byte[] cipherText = Base64.getUrlDecoder().decode(padBase64(parts[3]));
            byte[] key = MessageDigest.getInstance("SHA-256").digest(
                    (cookieCryptoSecret == null || cookieCryptoSecret.isBlank()
                            ? "dev-only-cookie-crypto-secret-change-me-32-chars"
                            : cookieCryptoSecret).getBytes(StandardCharsets.UTF_8)
            );
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(cipherText), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            throw new IllegalStateException("Cookie 解密失败，请检查 COOKIE_CRYPTO_SECRET 是否一致", ex);
        }
    }

    private String padBase64(String raw) {
        int mod = raw.length() % 4;
        return mod == 0 ? raw : raw + "====".substring(mod);
    }

    // ========== 自动分类 ==========

    @PostMapping("/xianyu/accounts/{account_id}/auto-category")
    public Result<Object> autoCategory(@PathVariable("account_id") int account_id, @RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            // 封面图自动分类涉及图片下载+闲鱼CDN上传+MTOP推荐API调用，耗时较长，给120秒超时（默认30秒会误超时）
            return Result.ok(automationClient.postInternalForData("/api/xianyu/accounts/" + account_id + "/auto-category", body, 120));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("自动分类失败, accountId={}, errorType={}", account_id, ex.getClass().getSimpleName());
            throw new BizException(503, "自动分类服务暂时不可用，请稍后重试");
        }
    }

    @PostMapping("/xianyu/accounts/{account_id}/auto-category/upload")
    public Result<Object> autoCategoryUpload(@PathVariable("account_id") int account_id, HttpServletRequest request) {
        if (!(request instanceof MultipartHttpServletRequest multipartRequest)) {
            throw new BizException(400, "请求必须为 multipart/form-data 格式");
        }
        Map<String, Object> body = new LinkedHashMap<>();
        injectTenantId(body);
        try {
            MultipartFile file = multipartRequest.getFile("file");
            if (file == null || file.isEmpty()) {
                throw new BizException(400, "上传文件不能为空");
            }
            String title = multipartRequest.getParameter("title");
            String description = multipartRequest.getParameter("description");
            if (title != null) body.put("title", title);
            if (description != null) body.put("description", description);
            Object result = automationClient.uploadInternalForData(
                    "/api/xianyu/accounts/" + account_id + "/auto-category/upload",
                    file.getInputStream(),
                    file.getOriginalFilename() != null ? file.getOriginalFilename() : "upload.jpg",
                    body
            );
            return Result.ok(result);
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("自动分类上传失败, accountId={}, errorType={}", account_id, ex.getClass().getSimpleName());
            throw new BizException(503, "自动分类图片暂时无法上传，请稍后重试");
        }
    }

    @GetMapping("/xianyu/accounts/auto-category/config")
    public Result<Object> autoCategoryConfig() {
        try {
            return Result.ok(automationClient.getInternalForData("/api/xianyu/accounts/auto-category/config", Map.of()));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("获取自动分类配置失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "自动分类配置暂时无法读取，请稍后重试");
        }
    }

    // ========== 通用图片上传代理（multipart → Python automation-service） ==========
    // 前端 uploadImage() 调用 POST /api/image/upload，Java 网关代理到 Python /api/image/upload
    // Python 端将文件保存到 uploads/images/ 并返回 {url, name, size, message}
    @PostMapping("/image/upload")
    public Result<Object> imageUpload(HttpServletRequest request) {
        if (!(request instanceof MultipartHttpServletRequest multipartRequest)) {
            throw new BizException(400, "请求必须为 multipart/form-data 格式");
        }
        Map<String, Object> body = new LinkedHashMap<>();
        injectTenantId(body);
        try {
            MultipartFile file = multipartRequest.getFile("file");
            if (file == null || file.isEmpty()) {
                throw new BizException(400, "上传文件不能为空");
            }
            String accountIdStr = multipartRequest.getParameter("accountId");
            if (accountIdStr != null) body.put("accountId", accountIdStr);
            Object result = automationClient.uploadInternalForData(
                    "/api/image/upload",
                    file.getInputStream(),
                    file.getOriginalFilename() != null ? file.getOriginalFilename() : "upload.jpg",
                    body
            );
            return Result.ok(result);
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("图片上传失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "图片暂时无法上传，请稍后重试");
        }
    }

    // ========== URL 导入图片代理（JSON → Python automation-service） ==========
    // 前端 uploadImageFromUrl() 调用 POST /api/image/uploadFromUrl，Java 网关代理到 Python /api/image/uploadFromUrl
    // Python 端下载远端图片并保存到 uploads/images/，返回 {url, name, assetId, size, message}
    @PostMapping("/image/uploadFromUrl")
    public Result<Object> imageUploadFromUrl(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        injectTenantId(payload);
        // 用户私有图片导入：强制 visibility=private，避免被误标为公开资源
        payload.put("visibility", "private");
        payload.putIfAbsent("purpose", "url-import");
        Object urlValue = payload.get("url");
        if (urlValue == null || String.valueOf(urlValue).isBlank()) {
            throw new BizException(400, "图片地址不能为空");
        }
        try {
            Object result = automationClient.postInternalForData("/api/image/uploadFromUrl", payload);
            return Result.ok(result);
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("URL 图片导入失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "图片暂时无法通过 URL 导入，请稍后重试");
        }
    }

    // ========== 分类树管理 ==========

    @GetMapping("/xianyu/categories")
    public Result<Object> getCategories() {
        try {
            return Result.ok(automationClient.getInternalForData("/api/xianyu/categories", Map.of()));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("获取分类树失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "分类树暂时无法读取，请稍后重试");
        }
    }

    @PostMapping("/xianyu/categories/sync")
    public Result<Object> syncCategories(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            return Result.ok(automationClient.postInternalForData("/api/xianyu/categories/sync", body));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("同步分类树失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "分类树暂时无法同步，请稍后重试");
        }
    }

    private void injectTenantId(Map<String, Object> body) {
        Long tenantId = requireTenantId();
        // 租户 ID 只信任服务端 JWT 上下文，覆盖所有客户端提交值，避免跨租户伪造。
        body.put("tenantId", tenantId);
        body.put("tenant_id", tenantId);
    }

    private Long requireTenantId() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        return tenantId;
    }

    private Object filterRefreshStatusForTenant(Object raw, Long tenantId) {
        if (!(raw instanceof Map<?, ?> source)) return raw;
        Map<String, Object> filtered = new LinkedHashMap<>();
        source.forEach((key, value) -> filtered.put(String.valueOf(key), value));
        Object accountsValue = source.get("accounts");
        if (!(accountsValue instanceof List<?> accounts)) {
            filtered.put("accounts", List.of());
            filtered.put("accountsCount", 0);
            return filtered;
        }
        List<Object> tenantAccounts = new ArrayList<>();
        for (Object item : accounts) {
            if (item instanceof Map<?, ?> account
                    && tenantId.equals(numberOrNull(account.get("tenantId")))) {
                tenantAccounts.add(item);
            }
        }
        filtered.put("accounts", tenantAccounts);
        filtered.put("accountsCount", tenantAccounts.size());
        return filtered;
    }

    @PostMapping("/item/refresh")
    public Result<Object> itemRefresh(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/refresh", body));
    }

    @PostMapping("/item/list")
    public Result<Object> itemList(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/list", body));
    }

    @PostMapping("/item/detail")
    public Result<Object> itemDetail(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/detail", body));
    }

    @PostMapping("/item/delete")
    public Result<Object> itemDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/delete", body));
    }

    @PostMapping("/item/publish")
    public Result<Object> itemPublish(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            return Result.ok(automationClient.postInternalForDataOrThrow("/api/item/publish", body));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            // 兜底路径（AutomationClient 已把下游业务错误转成 BizException 透传，一般不会到这里）。
            // 日志带上原始异常消息便于服务端排查，但不向前端暴露可能含敏感信息的细节。
            log.error("商品发布失败, errorType={}, message={}",
                    ex.getClass().getSimpleName(),
                    ex.getMessage() == null ? "" : ex.getMessage().replaceAll("[\\r\\n]+", " "));
            throw new BizException(503, "商品暂时无法发布，请稍后重试");
        }
    }

    @PostMapping("/item/offShelf")
    public Result<Object> itemOffShelf(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/offShelf", body));
    }

    @PostMapping("/item/republish")
    public Result<Object> itemRepublish(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/republish", body));
    }

    @PostMapping("/item/remoteDelete")
    public Result<Object> itemRemoteDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/remoteDelete", body));
    }

    @PostMapping("/item/batch/delete")
    public Result<Object> itemBatchDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/batch/delete", body));
    }

    @PostMapping("/item/batch/remoteDelete")
    public Result<Object> itemBatchRemoteDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/batch/remoteDelete", body));
    }

    @PostMapping("/item/batch/offShelf")
    public Result<Object> itemBatchOffShelf(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/batch/offShelf", body));
    }

    @PostMapping("/item/updatePrice")
    public Result<Object> itemUpdatePrice(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updatePrice", body));
    }

    @PostMapping("/item/updateStock")
    public Result<Object> itemUpdateStock(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updateStock", body));
    }

    @PostMapping("/item/updateAutoDeliveryStatus")
    public Result<Object> itemUpdateAutoDelivery(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updateAutoDeliveryStatus", body));
    }

    @PostMapping("/item/updateAutoConfirmShipment")
    public Result<Object> itemUpdateAutoConfirm(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updateAutoConfirmShipment", body));
    }

    @PostMapping("/item/updateAutoReplyStatus")
    public Result<Object> itemUpdateAutoReply(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updateAutoReplyStatus", body));
    }

    @PostMapping("/item/autoDeliveryRecords")
    public Result<Object> itemAutoDeliveryRecords(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/autoDeliveryRecords", body));
    }

    // ========== Workflow AI ==========

    @PostMapping("/workflow/ai/screen")
    public Result<Object> workflowAiScreen(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            return Result.ok(automationClient.postInternalForData("/api/workflow/ai/screen", body, 60));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("AI 商品筛选失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "AI 商品筛选暂时不可用，请稍后重试");
        }
    }

    @PostMapping("/workflow/ai/rewrite")
    public Result<Object> workflowAiRewrite(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        // AI 改写需要 user_id 用于计费归集，Python 内部令牌认证时 user_id 恒为 0，
        // 必须由 Java 网关从 JWT 上下文取出当前用户 ID 注入 body，由 Python 路由优先使用。
        Long currentUserId = TenantContext.getCurrentUserId();
        if (currentUserId != null && currentUserId > 0) {
            body.put("userId", currentUserId);
            body.put("user_id", currentUserId);
        }
        try {
            return Result.ok(automationClient.postInternalForData("/api/workflow/ai/rewrite", body, 60));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("AI 工作流改写失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "AI 工作流改写暂时不可用，请稍后重试");
        }
    }

    @PostMapping("/workflow/ai/generate-images")
    public Result<Object> workflowAiGenerateImages(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            return Result.ok(automationClient.postInternalForData("/api/workflow/ai/generate-images", body, 180));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("AI 工作流生图失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "AI 工作流生图暂时不可用，请稍后重试");
        }
    }

    // ========== AI 关键词提取 ==========

    @PostMapping("/workflow/ai/extract-keywords")
    public Result<Object> workflowAiExtractKeywords(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        try {
            return Result.ok(automationClient.postInternalForData("/api/workflow/ai/extract-keywords", body, 60));
        } catch (Exception ex) {
            if (ex instanceof BizException bizException) throw bizException;
            log.error("AI 关键词提取失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "AI 关键词提取暂时不可用，请稍后重试");
        }
    }

    // ==================== 工作流商品草稿箱 ====================

    @GetMapping("/workflow/drafts")
    public Result<Object> listWorkflowDrafts(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(defaultValue = "all") String status,
            @RequestParam(required = false) Long workflowId,
            @RequestParam(required = false, defaultValue = "") String keyword,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate) {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("page", page);
        params.put("page_size", pageSize);
        params.put("status", status);
        if (workflowId != null) params.put("workflow_id", workflowId);
        params.put("keyword", keyword == null ? "" : keyword);
        if (startDate != null) params.put("start_date", startDate);
        if (endDate != null) params.put("end_date", endDate);
        try {
            return Result.ok(automationClient.getInternalForData("/api/workflow/drafts", params));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("查询草稿列表失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "草稿列表暂时无法查询，请稍后重试");
        }
    }

    @GetMapping("/workflow/drafts/stats")
    public Result<Object> getWorkflowDraftStats() {
        try {
            return Result.ok(automationClient.getInternalForData("/api/workflow/drafts/stats", Map.of()));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("查询草稿统计失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "草稿统计暂时无法查询，请稍后重试");
        }
    }

    @GetMapping("/workflow/drafts/{draftId}")
    public Result<Object> getWorkflowDraft(@PathVariable("draftId") Long draftId) {
        try {
            return Result.ok(automationClient.getInternalForData("/api/workflow/drafts/" + draftId, Map.of()));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("查询草稿详情失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
            throw new BizException(503, "草稿详情暂时无法查询，请稍后重试");
        }
    }

    @PostMapping("/workflow/drafts/{draftId}/retry-publish")
    public Result<Object> retryPublishDraft(@PathVariable("draftId") Long draftId,
                                            @RequestBody(required = false) Map<String, Object> body) {
        try {
            Map<String, Object> payload = body != null ? body : new LinkedHashMap<>();
            return Result.ok(automationClient.postInternalForData(
                    "/api/workflow/drafts/" + draftId + "/retry-publish", payload));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("重试发布失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
            throw new BizException(503, "重试发布暂时无法执行，请稍后重试");
        }
    }

    @PostMapping("/workflow/drafts/batch-retry-publish")
    public Result<Object> batchRetryPublishDrafts(@RequestBody Map<String, Object> body) {
        try {
            return Result.ok(automationClient.postInternalForData(
                    "/api/workflow/drafts/batch-retry-publish", body));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("批量重试发布失败, errorType={}", ex.getClass().getSimpleName());
            throw new BizException(503, "批量重试发布暂时无法执行，请稍后重试");
        }
    }

    @DeleteMapping("/workflow/drafts/{draftId}")
    public Result<Object> deleteWorkflowDraft(@PathVariable("draftId") Long draftId) {
        try {
            return Result.ok(automationClient.deleteInternalForData("/api/workflow/drafts/" + draftId));
        } catch (BizException e) {
            throw e;
        } catch (Exception ex) {
            log.error("删除草稿失败, draftId={}, errorType={}", draftId, ex.getClass().getSimpleName());
            throw new BizException(503, "草稿暂时无法删除，请稍后重试");
        }
    }

    @PostMapping("/item/autoReplyRecords")
    public Result<Object> itemAutoReplyRecords(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/autoReplyRecords", body));
    }

    @PostMapping("/item/getRagAutoReplyConfig")
    public Result<Object> itemRagConfig(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/getRagAutoReplyConfig", body));
    }

    @PostMapping("/item/updateRagAutoReplyConfig")
    public Result<Object> itemUpdateRagConfig(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/updateRagAutoReplyConfig", body));
    }

    @PostMapping("/item/sku-specs")
    public Result<Object> itemSkuSpecs(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/sku-specs", body));
    }

    @GetMapping("/item/syncProgress/{syncId}")
    public Result<Object> itemSyncProgress(@PathVariable("syncId") String syncId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) throw new BizException(401, "登录状态已失效");
        return Result.ok(automationClient.getInternalForData(
                "/api/item/syncProgress/" + syncId, Map.of("tenantId", tenantId), tenantId));
    }

    @GetMapping("/item/syncing/{accountId}")
    public Result<Object> itemSyncing(@PathVariable("accountId") String accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) throw new BizException(401, "登录状态已失效");
        return Result.ok(automationClient.getInternalForData(
                "/api/item/syncing/" + accountId, Map.of("tenantId", tenantId), tenantId));
    }

    @GetMapping("/item/polishProgress/{taskId}")
    public Result<Object> itemPolishProgress(@PathVariable("taskId") String taskId) {
        Long tenantId = requireTenantId();
        Object result = automationClient.getInternalForData(
                "/api/item/polishProgress/" + taskId, Map.of("tenantId", tenantId), tenantId);
        if (result instanceof Map<?, ?> map && map.get("tenantId") != null
                && !tenantId.equals(numberOrNull(map.get("tenantId")))) {
            throw new BizException(404, "擦亮任务不存在或已过期");
        }
        return Result.ok(result);
    }

    @PostMapping("/item/polish")
    public Result<Object> itemPolish(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/item/polish", body));
    }

    // ==================== Cookie/Token 自动刷新调度器 ====================
    // 透传到 Python automation-service 的 /api/account/refresh/*
    // 仅用于前台监控租户内刷新状态和手动刷新单个账号；全局调度器只由服务生命周期管理。

    @GetMapping("/account/refresh/status")
    public Result<Object> accountRefreshStatus() {
        Long tenantId = requireTenantId();
        Object result = automationClient.getInternalForData(
                "/api/account/refresh/status", Map.of("tenantId", tenantId), tenantId);
        return Result.ok(filterRefreshStatusForTenant(result, tenantId));
    }

    @PostMapping("/account/refresh/force")
    public Result<Object> accountRefreshForce(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/account/refresh/force", body));
    }

    // ==================== 滑块验证处理 ====================
    // 透传到 Python automation-service 的 /api/captcha/*
    // 智能检测验证需求 + 操作指引 + Playwright 自动拖动

    @PostMapping("/captcha/detect")
    public Result<Object> captchaDetect(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/captcha/detect", body));
    }

    @PostMapping("/captcha/instructions")
    public Result<Object> captchaInstructions(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/captcha/instructions", body));
    }

    @PostMapping("/captcha/auto-solve")
    public Result<Object> captchaAutoSolve(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        // 滑块求解涉及 Playwright 浏览器操作 + 多场景重试（加载转圈/点击重试/下载失败刷新），需 180 秒超时
        try {
            return Result.ok(automationClient.postInternalForData("/api/captcha/auto-solve", body, 180));
        } catch (BizException e) {
            // automation 宕机时仍落一条失败记录，保证记录页可追溯
            if (e.getCode() == 503) {
                persistCaptchaSolveFallbackRecord(body, "manual", e.getMessage());
            }
            throw e;
        }
    }

    @PostMapping("/captcha/handle")
    public Result<Object> captchaHandle(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        // 滑块求解涉及 Playwright 浏览器操作 + 多场景重试（加载转圈/点击重试/下载失败刷新），需 180 秒超时
        try {
            return Result.ok(automationClient.postInternalForData("/api/captcha/handle", body, 180));
        } catch (BizException e) {
            if (e.getCode() == 503) {
                String scene = stringValue(body.get("triggerScene"));
                if (scene == null || scene.isBlank()) scene = "manual";
                persistCaptchaSolveFallbackRecord(body, scene, e.getMessage());
            }
            throw e;
        }
    }

    /**
     * automation-service 不可达时，在 MySQL 直接写入一条失败记录，
     * 避免用户手动/重试求解后「记录页完全空白、无法感知操作已触发」。
     * 正常路径由 Python handle_captcha_for_account 写库，本方法仅兜底。
     */
    private void persistCaptchaSolveFallbackRecord(Map<String, Object> body, String defaultScene, String errorMessage) {
        try {
            Long tenantId = TenantContext.getCurrentTenantId();
            if (tenantId == null || tenantId <= 0) return;
            Long accountId = longValue(body.get("accountId"));
            if (accountId == null || accountId <= 0) {
                accountId = longValue(body.get("account_id"));
            }
            if (accountId == null || accountId <= 0) return;

            String scene = stringValue(body.get("triggerScene"));
            if (scene == null || scene.isBlank()) scene = defaultScene;
            String openReason = stringValue(body.get("openReason"));
            if (openReason == null || openReason.isBlank()) {
                openReason = "用户触发滑块求解（网关兜底记录）";
            }
            String solveReason = stringValue(body.get("solveReason"));
            if (solveReason == null || solveReason.isBlank()) {
                solveReason = "滑块求解请求";
            }
            String eventDesc = switch (scene) {
                case "manual_retry" -> "手动重试滑块求解";
                case "ws_connect" -> "WS 连接触发滑块验证";
                case "cookie_keepalive" -> "Cookie 保活触发滑块验证";
                case "token_refresh" -> "Token 刷新触发滑块验证";
                default -> "手动触发滑块求解";
            };

            String accountName = "";
            try {
                List<Map<String, Object>> names = jdbcTemplate.queryForList(
                        "SELECT nickname FROM xianyu_account WHERE id = ? AND tenant_id = ? AND COALESCE(deleted,0)=0 LIMIT 1",
                        accountId, tenantId
                );
                if (!names.isEmpty() && names.get(0).get("nickname") != null) {
                    accountName = String.valueOf(names.get(0).get("nickname"));
                }
            } catch (Exception ignore) {
                // 查昵称失败不影响落库
            }
            if (accountName.isBlank()) accountName = String.valueOf(accountId);

            String err = errorMessage == null || errorMessage.isBlank()
                    ? "依赖服务暂时不可用，请稍后重试"
                    : errorMessage;

            jdbcTemplate.update(
                    "INSERT INTO xianyu_captcha_solve_record "
                            + "(tenant_id, account_id, account_name, event_desc, open_reason, solve_reason, "
                            + " trigger_scene, result, status, engine, retry_count, error_message, created_at, updated_at, deleted) "
                            + "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                    tenantId,
                    accountId,
                    accountName,
                    eventDesc,
                    openReason,
                    solveReason,
                    scene,
                    "slider_fail",
                    "fail",
                    "Gateway",
                    0,
                    err
            );
            log.warn("automation 不可达，已写入滑块求解兜底失败记录 tenantId={} accountId={} scene={}",
                    tenantId, accountId, scene);
        } catch (Exception ex) {
            log.error("写入滑块求解兜底记录失败 errorType={}", ex.getClass().getSimpleName());
        }
    }

    /**
     * 滑块求解记录列表。
     * <p>
     * 直接从 MySQL 读取（与 automation-service 同库同表），不再强依赖 Python 服务在线。
     * 原先透传到 /api/captcha/records 时，只要 automation 未启动/卡在滑块求解，
     * 前端就会显示「依赖服务暂时不可用」，导致记录页整页不可用。
     */
    @GetMapping("/captcha/records")
    public Result<Object> captchaRecords(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(defaultValue = "0") int accountId,
            @RequestParam(defaultValue = "") String status,
            @RequestParam(defaultValue = "") String triggerScene) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(401, "租户上下文不能为空");
        }
        int safePage = Math.max(1, page);
        int safeSize = Math.min(100, Math.max(1, pageSize));
        int offset = (safePage - 1) * safeSize;

        StringBuilder where = new StringBuilder(" WHERE tenant_id = ? AND COALESCE(deleted, 0) = 0");
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (accountId > 0) {
            where.append(" AND account_id = ?");
            args.add(accountId);
        }
        if (status != null && !status.isBlank()) {
            where.append(" AND status = ?");
            args.add(status.trim());
        }
        if (triggerScene != null && !triggerScene.isBlank()) {
            where.append(" AND trigger_scene = ?");
            args.add(triggerScene.trim());
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM xianyu_captcha_solve_record" + where,
                Long.class,
                args.toArray()
        );
        if (total == null) total = 0L;

        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(safeSize);
        listArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, account_id, account_name, event_desc, open_reason, solve_reason, "
                        + "trigger_scene, result, status, engine, retry_count, error_message, "
                        + "created_at, updated_at "
                        + "FROM xianyu_captcha_solve_record" + where
                        + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                listArgs.toArray()
        );

        List<Map<String, Object>> items = new ArrayList<>(rows.size());
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("accountId", row.get("account_id"));
            item.put("accountName", row.get("account_name") != null ? row.get("account_name") : "");
            item.put("eventDesc", row.get("event_desc") != null ? row.get("event_desc") : "");
            item.put("openReason", row.get("open_reason") != null ? row.get("open_reason") : "");
            item.put("solveReason", row.get("solve_reason") != null ? row.get("solve_reason") : "");
            item.put("triggerScene", row.get("trigger_scene") != null ? row.get("trigger_scene") : "");
            item.put("result", row.get("result") != null ? row.get("result") : "");
            item.put("status", row.get("status") != null ? row.get("status") : "");
            item.put("engine", row.get("engine") != null ? row.get("engine") : "");
            item.put("retryCount", row.get("retry_count") != null ? row.get("retry_count") : 0);
            item.put("errorMessage", row.get("error_message") != null ? row.get("error_message") : "");
            Object createdAt = row.get("created_at");
            Object updatedAt = row.get("updated_at");
            item.put("createdAt", createdAt != null ? String.valueOf(createdAt) : "");
            item.put("updatedAt", updatedAt != null ? String.valueOf(updatedAt) : "");
            items.add(item);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("list", items);
        result.put("total", total);
        result.put("page", safePage);
        result.put("pageSize", safeSize);
        return Result.ok(result);
    }

    // ==================== RAG 知识库 ====================
    // 透传到 Python automation-service 的 /api/knowledge-base/rag/*
    // 本地 SimpleVectorStore + 阿里云 DashScope embedding

    @PostMapping("/knowledge-base/rag/add")
    public Result<Object> ragAdd(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/knowledge-base/rag/add", body));
    }

    @PostMapping("/knowledge-base/rag/query")
    public Result<Object> ragQuery(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/knowledge-base/rag/query", body));
    }

    @PostMapping("/knowledge-base/rag/chat")
    public Result<Object> ragChat(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/knowledge-base/rag/chat", body));
    }

    @PostMapping("/knowledge-base/rag/delete")
    public Result<Object> ragDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/knowledge-base/rag/delete", body));
    }

    @GetMapping("/knowledge-base/rag/stats")
    public Result<Object> ragStats() {
        return new Result<>(503, "知识库统计尚未完成租户隔离，已安全禁用跨租户聚合结果", null);
    }

    @PostMapping("/knowledge-base/rag/extract-and-add")
    public Result<Object> ragExtractAndAdd(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/knowledge-base/rag/extract-and-add", body));
    }

    // ==================== 卡密发货配置 ====================
    // 透传到 Python automation-service 的 /api/kami/*
    // 注意：Python 的 data 字段可能是数组/字符串，使用 postInternalForObject 避免 asMap 包装

    @PostMapping("/kami/config/list")
    public Result<Object> kamiConfigList(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/kami/config/list", body));
    }

    @PostMapping("/kami/config/save")
    public Result<Object> kamiConfigSave(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/kami/config/save", body));
    }

    @PostMapping("/kami/config/delete")
    public Result<Object> kamiConfigDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/kami/config/delete", body));
    }

    @PostMapping("/kami/stock/list")
    public Result<Object> kamiStockList(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/kami/stock/list", body));
    }

    @PostMapping("/kami/stock/import")
    public Result<Object> kamiStockImport(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/kami/stock/import", body));
    }

    // ==================== 自定义发货API / 自动发货 ====================
    // 透传到 Python automation-service 的 /api/autoDelivery/*

    @PostMapping("/autoDelivery/config/list")
    public Result<Object> autoDeliveryConfigList(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/config/list", body));
    }

    @PostMapping("/autoDelivery/config/save")
    public Result<Object> autoDeliveryConfigSave(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/config/save", body));
    }

    @PostMapping("/autoDelivery/config/delete")
    public Result<Object> autoDeliveryConfigDelete(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/config/delete", body));
    }

    @PostMapping("/autoDelivery/config/test")
    public Result<Object> autoDeliveryConfigTest(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/config/test", body));
    }

    @PostMapping("/autoDelivery/records")
    public Result<Object> autoDeliveryRecords(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/records", body));
    }

    @PostMapping("/autoDelivery/trigger")
    public Result<Object> autoDeliveryTrigger(@RequestBody(required = false) Map<String, Object> body) {
        if (body == null) body = new java.util.LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForObject("/api/autoDelivery/trigger", body));
    }

    @GetMapping("/item/syncTasks")
    public Result<Object> itemSyncTasks(@RequestParam(required = false) Long accountId,
                                        @RequestParam(required = false) String status,
                                        @RequestParam(defaultValue = "1") int current,
                                        @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) throw new BizException(401, "登录已过期，请重新登录");
        int page = PageUtils.normalizeCurrent(current);
        int limit = PageUtils.normalizeSize(size, 50);
        int offset = (page - 1) * limit;
        java.util.List<Object> args = new java.util.ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0 AND tenant_id=? ");
        args.add(tenantId);
        if (accountId != null) {
            where.append(" AND account_id=? ");
            args.add(accountId);
        }
        if (status != null && !status.isBlank()) {
            where.append(" AND status=? ");
            args.add(status.trim());
        }
        Integer total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM xianyu_goods_sync_task" + where, Integer.class, args.toArray());
        args.add(offset);
        args.add(limit);
        java.util.List<java.util.Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT sync_id AS syncId, tenant_id AS tenantId, account_id AS accountId, status, progress, " +
                        "total_count AS total, new_count AS newCount, updated_count AS updatedCount, skipped_count AS skippedCount, " +
                        "off_shelf_count AS offShelfCount, detail_synced_count AS detailSyncedCount, duration_seconds AS durationSeconds, " +
                        "error_message AS errorMessage, started_time AS startedTime, finished_time AS finishedTime, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM xianyu_goods_sync_task" + where + " ORDER BY created_time DESC, id DESC LIMIT ?, ?",
                args.toArray()
        );
        java.util.Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("records", records);
        result.put("current", page);
        result.put("size", limit);
        result.put("total", total == null ? 0 : total);
        return Result.ok(result);
    }

    // ==================== 快捷回复模板 ====================
    // 透传到 Python automation-service 的 /api/quickReplyTemplate/*

    @GetMapping("/quick-reply/templates")
    public Result<Object> listQuickReplyTemplates(
            @RequestParam(defaultValue = "100") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) return Result.unauthorized("登录已过期，请重新登录");
        try {
            Object data = automationClient.getInternalForData(
                    "/api/quickReplyTemplate/list?size=" + Math.max(1, Math.min(size, 500)),
                    null
            );
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("快捷回复模板查询失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "快捷回复模板暂时无法查询，请稍后重试");
        }
    }

    @PostMapping("/quick-reply/templates")
    public Result<Object> saveQuickReplyTemplate(@RequestBody Map<String, Object> body) {
        if (body == null) body = new LinkedHashMap<>();
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/quickReplyTemplate/save", body));
    }

    @org.springframework.web.bind.annotation.DeleteMapping("/quick-reply/templates/{id}")
    public Result<Object> deleteQuickReplyTemplate(@PathVariable("id") Long id) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", id);
        injectTenantId(body);
        return Result.ok(automationClient.postInternalForData("/api/quickReplyTemplate/delete?id=" + id, body));
    }

    // ==================== 前台内容管理（轮播图、公告） ====================
    // 展示型配置由 Java/MySQL 主通道读取；Python 仅负责自动化执行与受控文件处理。

    @GetMapping("/carousel/list")
    public Result<Object> carouselList() {
        return Result.ok(contentService.listCommercialHomeCarousels());
    }

    @GetMapping("/announcement/list")
    public Result<Object> announcementList() {
        return Result.ok(contentService.listCommercialHomeAnnouncements());
    }
}
