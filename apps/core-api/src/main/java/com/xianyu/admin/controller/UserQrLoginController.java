package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.dto.XianyuAccountVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.XianyuAccountService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Pattern;

@RestController
@RequestMapping("/api/qrlogin")
public class UserQrLoginController {
    private static final Logger log = LoggerFactory.getLogger(UserQrLoginController.class);
    private static final Pattern SESSION_ID_PATTERN = Pattern.compile("^[A-Za-z0-9_-]{32,64}$");

    private final AutomationClient automationClient;
    private final XianyuAccountService accountService;

    public UserQrLoginController(AutomationClient automationClient, XianyuAccountService accountService) {
        this.automationClient = automationClient;
        this.accountService = accountService;
    }

    @PostMapping("/generate")
    public Result<Map<String, Object>> generate(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = buildPayload(body);
        Map<String, Object> data = automationClient.postInternalForData("/api/internal/qrlogin/generate", payload);
        if (isPythonErrorResponse(data)) {
            return Result.fail(extractPythonErrorMessage(data));
        }
        normalizeQrPayload(data);
        return Result.ok(data);
    }

    @PostMapping("/status/{sessionId}")
    public Result<Map<String, Object>> status(@PathVariable String sessionId,
                                              @RequestBody(required = false) Map<String, Object> body) {
        requireValidSessionId(sessionId);
        Map<String, Object> payload = buildPayload(body);
        Long requestedAccountId = numberOrNull(payload.get("accountId"));
        Map<String, Object> data = automationClient.postInternalForData("/api/internal/qrlogin/status/" + sessionId, payload);

        // Python 返回非 200 code 时（如 401 暂未登录），直接透传错误，避免被 Result.ok 包裹后前端嵌套解析
        if (isPythonErrorResponse(data)) {
            String errorMsg = extractPythonErrorMessage(data);
            log.warn("QR login status Python error code={}", data.get("code"));
            return Result.fail(errorMsg);
        }

        if ("confirmed".equalsIgnoreCase(String.valueOf(data.get("status")))) {
            if (requestedAccountId != null) {
                try {
                    Map<String, Object> cookieData = automationClient.postInternalForData("/api/internal/qrlogin/cookies/" + sessionId, payload);
                    if (isPythonErrorResponse(cookieData)) {
                        String errorMsg = extractPythonErrorMessage(cookieData);
                        log.warn("QR login cookies Python error code={}", cookieData.get("code"));
                        return Result.fail(errorMsg);
                    }
                    String cookieText = joinCookies(cookieData);
                    accountService.updateCookie(TenantContext.getCurrentTenantId(), requestedAccountId, cookieText);
                    data.put("accountId", requestedAccountId);
                    cleanupSessionBestEffort(sessionId, payload);
                } catch (BizException e) {
                    throw e;
                }
            }

            Long resolvedAccountId = numberOrNull(data.get("accountId"));
            if (resolvedAccountId != null) {
                XianyuAccountVO account = syncAccountAfterConfirmedLogin(resolvedAccountId);
                mergeAccountState(data, account);
                data.put("message", buildConfirmedLoginMessage(account));
            }
        }
        normalizeQrPayload(data);
        return Result.ok(data);
    }

    @PostMapping("/cleanup")
    public Result<Map<String, Object>> cleanup() {
        Map<String, Object> result = automationClient.postInternalForData(
                "/api/internal/qrlogin/cleanup",
                buildPayload(null)
        );
        if (isPythonErrorResponse(result)) {
            return Result.fail(extractPythonErrorMessage(result));
        }
        return Result.ok(result);
    }

    private void cleanupSessionBestEffort(String sessionId, Map<String, Object> payload) {
        try {
            automationClient.postInternalForData("/api/internal/qrlogin/cleanup/" + sessionId, payload);
        } catch (Exception cleanupError) {
            log.warn("qr login session cleanup failed errorType={}",
                    cleanupError.getClass().getSimpleName());
        }
    }

    private XianyuAccountVO syncAccountAfterConfirmedLogin(Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        AccountAuthStatusResult authStatus = accountService.checkAuthStatus(tenantId, accountId, "qr-login");
        XianyuAccountVO account = accountService.detail(tenantId, accountId);
        if (account == null) {
            account = buildFallbackAccount(accountId, authStatus);
        } else {
            mergeAuthStatus(account, authStatus);
        }
        if (!Boolean.TRUE.equals(account.getAuthUsable())) {
            return account;
        }

        try {
            account = accountService.refreshProfile(tenantId, accountId);
        } catch (Exception profileError) {
            log.warn("qr login profile refresh failed tenantId={} accountId={} errorType={}",
                    tenantId,
                    accountId,
                    profileError.getClass().getSimpleName());
        }

        try {
            automationClient.postInternal("/api/websocket/start", buildRealtimePayload(accountId), tenantId);
        } catch (Exception wsError) {
            log.warn("qr login websocket restart failed tenantId={} accountId={} errorType={}",
                    tenantId,
                    accountId,
                    wsError.getClass().getSimpleName());
        }
        return account;
    }

    private XianyuAccountVO buildFallbackAccount(Long accountId, AccountAuthStatusResult authStatus) {
        XianyuAccountVO account = new XianyuAccountVO();
        account.setId(accountId);
        mergeAuthStatus(account, authStatus);
        return account;
    }

    private void mergeAuthStatus(XianyuAccountVO account, AccountAuthStatusResult authStatus) {
        if (account == null || authStatus == null) {
            return;
        }
        account.setCookieStatus(authStatus.getCookieStatus());
        account.setAuthUsable(authStatus.isUsable());
        account.setLoginStatusCode(authStatus.getLoginStatusCode());
        account.setLoginStatusMessage(authStatus.getLoginStatusMessage());
    }

    private Map<String, Object> buildRealtimePayload(Long accountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        Long tenantId = TenantContext.getCurrentTenantId();
        payload.put("tenantId", tenantId);
        payload.put("tenant_id", tenantId);
        payload.put("accountId", accountId);
        payload.put("xianyuAccountId", accountId);
        payload.put("forceReconnect", true);
        return payload;
    }

    private void mergeAccountState(Map<String, Object> data, XianyuAccountVO account) {
        if (data == null || account == null) {
            return;
        }
        data.put("accountId", account.getId());
        data.put("cookieStatus", account.getCookieStatus());
        data.put("loginStatusCode", account.getLoginStatusCode());
        data.put("loginStatusMessage", account.getLoginStatusMessage());
        data.put("authUsable", account.getAuthUsable());
        data.put("displayName", account.getDisplayName());
        data.put("nickname", account.getNickname());
        data.put("avatarUrl", account.getAvatarUrl());
        data.put("profileRefreshTime", account.getProfileRefreshTime());
    }

    private String buildConfirmedLoginMessage(XianyuAccountVO account) {
        if (account == null) {
            return "扫码登录成功";
        }
        if (Boolean.TRUE.equals(account.getAuthUsable())) {
            return "扫码登录成功，账号资料已同步并自动恢复连接";
        }
        return firstNonBlank(account.getLoginStatusMessage(), "扫码登录成功，但统一登录校验未通过");
    }

    private void normalizeQrPayload(Map<String, Object> data) {
        if (data == null) {
            return;
        }
        Object qrImage = data.get("qrImage");
        if (!data.containsKey("qrCodeBase64") && qrImage != null) {
            data.put("qrCodeBase64", qrImage);
        }
        Object status = data.get("status");
        if (status != null) {
            String normalized = String.valueOf(status).toLowerCase();
            if ("new".equals(normalized)) {
                data.put("status", "pending");
            } else if ("scaned".equals(normalized)) {
                data.put("status", "scanned");
            }
        }
    }

    private Map<String, Object> buildPayload(Map<String, Object> body) {
        Map<String, Object> payload = new LinkedHashMap<>();
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || tenantId <= 0 || userId == null || userId <= 0) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        payload.put("tenantId", tenantId);
        payload.put("userId", userId);
        Object rawAccountId = body == null ? null : body.get("accountId");
        Long accountId;
        try {
            accountId = numberOrNull(rawAccountId);
        } catch (NumberFormatException invalidAccountId) {
            throw new BizException(400, "accountId 必须为正整数");
        }
        if (rawAccountId != null && (accountId == null || accountId <= 0)) {
            throw new BizException(400, "accountId 必须为正整数");
        }
        if (accountId != null) {
            payload.put("accountId", accountId);
        }
        return payload;
    }

    private void requireValidSessionId(String sessionId) {
        if (sessionId == null || !SESSION_ID_PATTERN.matcher(sessionId).matches()) {
            throw new BizException(400, "扫码登录会话编号格式无效");
        }
    }

    @SuppressWarnings("unchecked")
    private String joinCookies(Map<String, Object> cookieData) {
        if (cookieData == null) {
            throw new IllegalArgumentException("扫码会话未返回 Cookie");
        }
        if (cookieData.get("cookie_text") != null) {
            String cookieText = String.valueOf(cookieData.get("cookie_text")).trim();
            if (!cookieText.isBlank()) {
                return cookieText;
            }
        }
        Object cookiesObj = cookieData.get("cookies");
        if (!(cookiesObj instanceof Map<?, ?> rawCookies)) {
            throw new IllegalArgumentException("扫码会话未返回 Cookie");
        }
        StringJoiner joiner = new StringJoiner("; ");
        rawCookies.forEach((k, v) -> {
            if (k != null && v != null) {
                joiner.add(String.valueOf(k) + "=" + v);
            }
        });
        String cookieText = joiner.toString();
        if (cookieText.isBlank()) {
            throw new IllegalArgumentException("扫码会话未返回 Cookie");
        }
        return cookieText;
    }

    private Long numberOrNull(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.longValue();
        }
        String text = String.valueOf(value).trim();
        if (text.isBlank()) {
            return null;
        }
        return Long.parseLong(text);
    }

    private String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return null;
    }

    /**
     * 检测 Python automation-service 返回的 ResultObject 是否为业务错误。
     *
     * Java AutomationClient.dataOrSelf() 在 Python 返回非 200/0 code 时会返回整个 raw 对象
     * （包含 code 和 msg 字段），而不是 data 字段。这里检测这种情况，避免把 Python 错误
     * 包裹在 Result.ok() 中导致前端嵌套解析。
     */
    private boolean isPythonErrorResponse(Map<String, Object> data) {
        if (data == null) return false;
        Object code = data.get("code");
        if (code == null) return false;
        String codeText = String.valueOf(code);
        return !("200".equals(codeText) || "0".equals(codeText));
    }

    private String extractPythonErrorMessage(Map<String, Object> data) {
        if (data == null) return "自动化服务返回失败";
        Object msg = data.get("msg");
        if (msg == null) msg = data.get("message");
        return msg != null ? String.valueOf(msg) : "自动化服务返回失败";
    }
}
