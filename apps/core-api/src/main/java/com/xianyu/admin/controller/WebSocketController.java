package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.OperationAuditService;
import com.xianyu.admin.service.XianyuAccountService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import jakarta.servlet.http.HttpServletRequest;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/websocket")
public class WebSocketController {
    private static final Logger log = LoggerFactory.getLogger(WebSocketController.class);
    private final AutomationClient automationClient;
    private final OperationAuditService auditService;
    private final XianyuAccountService accountService;

    public WebSocketController(AutomationClient automationClient,
                               OperationAuditService auditService,
                               XianyuAccountService accountService) {
        this.automationClient = automationClient;
        this.auditService = auditService;
        this.accountService = accountService;
    }

    /**
     * 查询指定账号的 WebSocket 状态。必须透传到自动化服务，而不是只探测 /health，
     * 否则账号页会把“自动化服务可达”误判成“账号已连接”。
     */
    @PostMapping("/status")
    public Result<Object> status(@RequestBody(required = false) Map<String, Object> body) {
        try {
            Map<String, Object> payload = withTenant(body);
            requireAccountId(payload);
            Object result = automationClient.postInternal("/api/websocket/status", payload);
            throwIfAutomationBusinessFailed(result, "查询连接状态失败");
            return Result.ok(unwrapAutomationResult(result));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("查询WebSocket状态异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("连接状态暂时无法查询，请稍后重试");
        }
    }

    /**
     * 启动指定账号的 WebSocket 监听。自动化服务会判断 Cookie/Token 是否遇到滑块或过期：
     * 出现验证失败时立即返回失败；未检测到验证失败时返回连接成功/已提交连接。
     */
    @PostMapping("/start")
    public Result<Object> start(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        try {
            Map<String, Object> payload = withTenant(body);
            requireAccountId(payload);
            Long tenantId = TenantContext.getCurrentTenantId();
            Object accountId = payload.getOrDefault("xianyuAccountId", payload.get("accountId"));
            log.info("Java -> Python websocket/start tenantId={}, accountId={}", tenantId, accountId);
            // 启动 WS 流程包含预检 Token（秒级）+ 等待 WS 连接结果（最多 12 秒）+
            // 若 auth_failed 会自动触发 Playwright 滑块求解（最长 180 秒）。
            // 默认 30 秒超时会在滑块求解中途触发 HttpTimeoutException，导致前端按钮卡在"处理中..."。
            // 必须给到 180 秒以覆盖滑块求解的最坏情况。
            Object result = automationClient.postInternal("/api/websocket/start", payload, 180);
            throwIfAutomationBusinessFailed(result, "连接失败，请自行提供 Cookie 或扫码重新登录");
            audit(payload, "WEBSOCKET_START", "启动闲鱼消息监听", request);
            return Result.ok(unwrapAutomationResult(result));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("启动WebSocket监听异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("启动失败，自动化服务暂时不可用");
        }
    }

    /**
     * 停止指定账号的 WebSocket 监听。
     */
    @PostMapping("/stop")
    public Result<Object> stop(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        try {
            Map<String, Object> payload = withTenant(body);
            requireAccountId(payload);
            Object result = automationClient.postInternal("/api/websocket/stop", payload);
            throwIfAutomationBusinessFailed(result, "停止失败");
            audit(payload, "WEBSOCKET_STOP", "停止闲鱼消息监听", request);
            return Result.ok(unwrapAutomationResult(result));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("停止WebSocket监听异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("停止失败，自动化服务暂时不可用");
        }
    }

    @PostMapping("/checkLogin")
    public Result<Object> checkLogin(@RequestBody(required = false) Map<String, Object> body) {
        try {
            Map<String, Object> payload = withTenant(body);
            Long accountId = requireAccountId(payload);
            AccountAuthStatusResult auth = accountService.checkAuthStatus(
                    TenantContext.getCurrentTenantId(),
                    accountId,
                    "websocket-check"
            );
            if (auth == null) {
                throw automationUnavailable("登录状态暂时无法检查，请稍后重试");
            }
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("loggedIn", auth.isUsable());
            result.put("message", auth.getLoginStatusMessage());
            result.put("code", auth.getLoginStatusCode());
            result.put("cookieStatus", auth.getCookieStatus());
            result.put("checkedAt", auth.getCheckedAt());
            result.put("status", auth);
            return Result.ok(result);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("检查登录状态异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("登录状态暂时无法检查，请稍后重试");
        }
    }

    @PostMapping("/refreshCookie")
    public Result<Object> refreshCookie(@RequestBody(required = false) Map<String, Object> body) {
        return forceCredentialRefresh(body, "cookie", "刷新Cookie");
    }

    @PostMapping("/sendMessage")
    public Result<Object> sendMessage(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        try {
            Map<String, Object> payload = withTenant(body);
            // 校验必需字段
            Long accountId = requireAccountId(payload);
            Object cid = payload.get("cid");
            Object sid = payload.getOrDefault("sid", payload.get("sId"));
            if (cid == null || String.valueOf(cid).isBlank()) {
                throw new BizException(400, "缺少必需参数：cid（会话ID）");
            }
            if (sid == null || String.valueOf(sid).isBlank()) {
                throw new BizException(400, "缺少必需参数：sid（闲鱼会话ID）");
            }
            Object content = payload.get("content");
            if (content == null || String.valueOf(content).isBlank()) {
                content = payload.get("text");
            }
            if (content == null || String.valueOf(content).isBlank()) {
                content = payload.get("message");
            }
            if (content == null || String.valueOf(content).isBlank()) {
                throw new BizException(400, "消息内容不能为空");
            }
            payload.put("content", String.valueOf(content));
            payload.putIfAbsent("text", String.valueOf(content));
            log.info("Java -> Python websocket/sendMessage tenantId={}, accountId={}",
                    TenantContext.getCurrentTenantId(),
                    accountId);
            Object result = automationClient.postInternal("/api/websocket/sendMessage", payload);
            throwIfAutomationBusinessFailed(result, "消息发送失败，请稍后重试");
            audit(payload, "MESSAGE_SEND_TEXT", "发送文本消息", request);
            return Result.ok(unwrapAutomationResult(result));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("发送消息异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("消息发送失败，自动化服务暂时不可用");
        }
    }


    @PostMapping("/sendImageMessage")
    public Result<Object> sendImageMessage(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        try {
            Map<String, Object> payload = withTenant(body);
            requireAccountId(payload);
            requireConversationId(payload);
            Object imageUrl = payload.get("imageUrl");
            String url = imageUrl == null ? "" : String.valueOf(imageUrl).trim();
            if (!(url.startsWith("https://") || url.startsWith("/uploads/"))) {
                throw new BizException(400, "图片链接仅支持 HTTPS 地址或系统上传图片地址");
            }
            Object result = automationClient.postInternal("/api/websocket/sendImageMessage", payload);
            throwIfAutomationBusinessFailed(result, "发送图片消息失败，请稍后重试");
            audit(payload, "MESSAGE_SEND_IMAGE", "发送图片消息", request);
            return Result.ok(unwrapAutomationResult(result));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("发送图片消息异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("发送图片消息失败，自动化服务暂时不可用");
        }
    }

    @PostMapping("/updateCookie")
    public Result<Object> updateCookie(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest request) {
        try {
            Map<String, Object> payload = withTenant(body);
            Long accountId = requireAccountId(payload);
            String cookie = stringOrNull(payload.get("cookie"));
            if (cookie == null) {
                throw new BizException(400, "Cookie不能为空");
            }
            Object result = accountService.updateCookie(TenantContext.getCurrentTenantId(), accountId, cookie);
            audit(payload, "ACCOUNT_COOKIE_UPDATE", "更新闲鱼账号Cookie", request);
            return Result.ok(result);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("更新Cookie异常, errorType={}", e.getClass().getSimpleName());
            throw automationUnavailable("更新Cookie失败，账号服务暂时不可用");
        }
    }

    @PostMapping("/updateToken")
    public Result<Object> updateToken(@RequestBody(required = false) Map<String, Object> body) {
        return forceCredentialRefresh(body, "mh5tk", "更新Token");
    }

    @PostMapping("/refreshToken")
    public Result<Object> refreshToken(@RequestBody(required = false) Map<String, Object> body) {
        return forceCredentialRefresh(body, "ws_token", "刷新Token");
    }

    private Result<Object> forceCredentialRefresh(Map<String, Object> body, String refreshType, String action) {
        try {
            Map<String, Object> payload = withTenant(body);
            Long accountId = requireAccountId(payload);
            // 自动化刷新接口按 accountId 执行，调用前必须在 Java 边界确认账号属于当前租户。
            accountService.detail(TenantContext.getCurrentTenantId(), accountId);
            payload.put("refreshType", refreshType);
            Object raw = automationClient.postInternal("/api/account/refresh/force", payload);
            throwIfAutomationBusinessFailed(raw, action + "失败，请稍后重试");

            Object unwrapped = unwrapAutomationResult(raw);
            if (!(unwrapped instanceof Map<?, ?> refreshResult)) {
                throw new BizException(502, "自动化服务返回了无效响应");
            }
            if (!Boolean.TRUE.equals(refreshResult.get("success"))) {
                Object reason = refreshResult.get("error");
                if (reason == null) reason = refreshResult.get("last_error");
                String fallback = action + "未成功，请检查账号登录状态后重试";
                if (reason != null && looksTechnicalOrSensitive(String.valueOf(reason))) {
                    throw automationUnavailable(action + "失败，自动化服务暂时不可用");
                }
                throw new BizException(409, safeBusinessMessage(
                        reason == null ? fallback : String.valueOf(reason),
                        fallback));
            }

            Map<String, Object> response = new LinkedHashMap<>();
            refreshResult.forEach((key, value) -> response.put(String.valueOf(key), value));
            response.put("accepted", true);
            response.put("service", "online");
            return Result.ok(response);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("{}异常, errorType={}", action, e.getClass().getSimpleName());
            throw automationUnavailable(action + "失败，自动化服务暂时不可用");
        }
    }


    private void audit(Map<String, Object> payload, String operationType, String desc, HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long accountId = numberOrNull(payload.getOrDefault("xianyuAccountId", payload.get("accountId")));
        String extra = desc + " | accountId=" + (accountId == null ? "-" : accountId);
        auditService.record(tenantId, TenantContext.getCurrentUserId(), operationType, extra, "xianyu_account", accountId, getClientIp(request));
    }

    private Long numberOrNull(Object value) {
        if (value == null) return null;
        try { return Long.parseLong(String.valueOf(value)); }
        catch (Exception ignore) { return null; }
    }

    private String stringOrNull(Object value) {
        if (value == null) return null;
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    private String getClientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }


    private String extractAutomationMessage(Object result, String fallback) {
        if (result instanceof Map<?, ?> map) {
            Object msg = map.get("msg");
            if (msg == null) msg = map.get("message");
            if (msg != null && !String.valueOf(msg).isBlank()) return String.valueOf(msg);
            Object data = map.get("data");
            if (data instanceof Map<?, ?> dataMap) {
                Object error = dataMap.get("error");
                if (error == null) error = dataMap.get("message");
                if (error != null && !String.valueOf(error).isBlank()) return String.valueOf(error);
            }
        }
        return fallback;
    }

    private void throwIfAutomationBusinessFailed(Object result, String fallback) {
        if (!(result instanceof Map<?, ?> map)) return;
        Object code = map.get("code");
        if (code == null) return;
        String codeText = String.valueOf(code);
        if ("200".equals(codeText) || "0".equals(codeText)) return;
        int upstreamCode;
        try {
            upstreamCode = Integer.parseInt(codeText);
        } catch (NumberFormatException e) {
            throw new BizException(502, "自动化服务返回了无效响应");
        }
        String rawMessage = extractAutomationMessage(result, null);
        int responseCode;
        if (upstreamCode >= 500) {
            responseCode = isKnownBusinessRejection(rawMessage) ? 409 : 503;
        } else {
            responseCode = switch (upstreamCode) {
                case 400, 404, 409, 410, 422, 429 -> upstreamCode;
                case 401, 403 -> 409;
                default -> 502;
            };
        }
        if (responseCode == 503) {
            throw automationUnavailable("自动化服务暂时不可用，请稍后重试");
        }
        String message = rawMessage == null ? fallback : rawMessage;
        throw new BizException(responseCode, safeBusinessMessage(message, fallback));
    }

    private Object unwrapAutomationResult(Object result) {
        if (result instanceof Map<?, ?> map) {
            Object code = map.get("code");
            if (code != null && String.valueOf(code).matches("200|0")) {
                return map.get("data");
            }
        }
        return result;
    }

    private Map<String, Object> withTenant(Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        // 租户 ID 必须由服务端上下文覆盖，禁止客户端请求体伪造。
        payload.put("tenantId", tenantId);
        payload.put("tenant_id", tenantId);
        return payload;
    }

    private Long requireAccountId(Map<String, Object> payload) {
        Object raw = payload.getOrDefault("xianyuAccountId", payload.get("accountId"));
        Long accountId = numberOrNull(raw);
        if (accountId == null || accountId <= 0) {
            throw new BizException(400, "accountId 必须为正整数");
        }
        payload.put("accountId", accountId);
        payload.put("xianyuAccountId", accountId);
        return accountId;
    }

    private void requireConversationId(Map<String, Object> payload) {
        Object cid = payload.get("cid");
        if (cid == null || String.valueOf(cid).isBlank()) {
            cid = payload.getOrDefault("sessionId", payload.getOrDefault("sid", payload.get("sId")));
        }
        if (cid == null || String.valueOf(cid).isBlank()) {
            throw new BizException(400, "缺少必需参数：cid（会话ID）");
        }
        payload.putIfAbsent("cid", cid);
    }

    private BizException automationUnavailable(String message) {
        return new BizException(503, message);
    }

    private String safeBusinessMessage(String message, String fallback) {
        if (message == null) return fallback;
        String normalized = message.replaceAll("[\\r\\n\\t]+", " ").trim();
        if (normalized.isBlank() || normalized.length() > 300 || looksTechnicalOrSensitive(normalized)) return fallback;
        return normalized;
    }

    private boolean isKnownBusinessRejection(String message) {
        if (message == null || looksTechnicalOrSensitive(message)) return false;
        String normalized = message.toLowerCase();
        return normalized.contains("登录")
                || normalized.contains("cookie")
                || normalized.contains("token")
                || normalized.contains("滑块")
                || normalized.contains("验证码")
                || normalized.contains("账号")
                || normalized.contains("会话")
                || normalized.contains("未连接")
                || normalized.contains("连接尚未就绪")
                || normalized.contains("不存在")
                || normalized.contains("已过期")
                || normalized.contains("已失效")
                || normalized.contains("已停用")
                || normalized.contains("无法识别")
                || normalized.contains("不能为空")
                || normalized.contains("不支持")
                || normalized.contains("库存")
                || normalized.contains("配置");
    }

    private boolean looksTechnicalOrSensitive(String message) {
        if (message == null) return false;
        String normalized = message.toLowerCase();
        return normalized.contains("jdbc")
                || normalized.contains("sql")
                || normalized.contains("database")
                || normalized.contains("mysql")
                || normalized.contains("postgres")
                || normalized.contains("redis")
                || normalized.contains("traceback")
                || normalized.contains("exception")
                || normalized.contains("stack trace")
                || normalized.contains("password=")
                || normalized.contains("connection refused")
                || normalized.contains("timed out")
                || normalized.contains("internal-host");
    }
}
