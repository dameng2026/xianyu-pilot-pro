package com.xianyu.admin.service;

import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import com.xianyu.admin.mapper.XianyuAccountRuntimeMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Objects;

@Service
public class XianyuAccountAuthStatusService {
    private final XianyuAccountMapper accountMapper;
    private final XianyuAccountAuthMapper authMapper;
    private final XianyuAccountRuntimeMapper runtimeMapper;
    private final CookieCryptoService cookieCryptoService;
    private final XianyuAccountAvailabilityProbeService probeService;

    public XianyuAccountAuthStatusService(XianyuAccountMapper accountMapper,
                                         XianyuAccountAuthMapper authMapper,
                                         XianyuAccountRuntimeMapper runtimeMapper,
                                         CookieCryptoService cookieCryptoService,
                                         XianyuAccountAvailabilityProbeService probeService) {
        this.accountMapper = accountMapper;
        this.authMapper = authMapper;
        this.runtimeMapper = runtimeMapper;
        this.cookieCryptoService = cookieCryptoService;
        this.probeService = probeService;
    }

    public AccountAuthStatusResult check(Long tenantId, Long accountId, String source) {
        AccountAuthStatusResult result = evaluate(tenantId, accountId, source);
        persist(tenantId, accountId, result);
        return result;
    }

    private AccountAuthStatusResult evaluate(Long tenantId, Long accountId, String source) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        if (account == null) {
            return failed(source, 0, "ACCOUNT_NOT_FOUND", "账号不存在或已删除");
        }
        if (!Objects.equals(account.getStatus(), 1)) {
            return failed(source, 0, "ACCOUNT_DISABLED", "账号已停用，请先启用后再执行");
        }

        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        if (auth == null || isBlank(auth.getEncryptedCookie())) {
            return failed(source, 0, "AUTH_MISSING", "未找到登录信息，请重新登录闲鱼账号");
        }

        String cookie;
        try {
            cookie = cookieCryptoService.decryptIfNeeded(auth.getEncryptedCookie());
        } catch (Exception e) {
            return failed(source, 0, "COOKIE_DECRYPT_FAILED", "Cookie 解密失败，请重新登录闲鱼账号");
        }

        if (isBlank(cookie)) {
            return failed(source, 0, "COOKIE_EMPTY", "登录信息为空，请重新登录闲鱼账号");
        }
        if (!cookie.contains("_m_h5_tk=")) {
            return failed(source, 0, "COOKIE_TOKEN_MISSING", "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号");
        }

        String externalUid = firstNonBlank(
                account.getExternalUid(),
                extractCookieValue(cookie, "unb"),
                extractCookieValue(cookie, "userId"),
                extractCookieValue(cookie, "userid")
        );
        if (isBlank(externalUid)) {
            return failed(source, 0, "EXTERNAL_UID_MISSING", "账号缺少 externalUid，请重新登录闲鱼账号");
        }

        AccountAuthProbeResult probeResult = probeService.probe(cookie, externalUid);
        if (!probeResult.isAlive()) {
            return failed(source, 0, probeResult.getCode(), probeResult.getMessage());
        }
        return success(source);
    }

    private void persist(Long tenantId, Long accountId, AccountAuthStatusResult result) {
        if (tenantId == null || accountId == null || result == null) {
            return;
        }

        authMapper.updateLoginStatus(
                tenantId,
                accountId,
                result.getCookieStatus(),
                result.getLoginStatusCode(),
                result.getLoginStatusMessage(),
                result.getCheckedAt()
        );
        runtimeMapper.updateLoginStatus(
                tenantId,
                accountId,
                result.getCookieStatus(),
                result.getLoginStatusCode(),
                result.getLoginStatusMessage(),
                result.getCheckedAt()
        );
    }

    private AccountAuthStatusResult success(String source) {
        AccountAuthStatusResult result = new AccountAuthStatusResult();
        result.setUsable(true);
        result.setCookieStatus(1);
        result.setLoginStatusCode("OK");
        result.setLoginStatusMessage("账号登录状态正常");
        result.setCheckedAt(LocalDateTime.now());
        result.setSource(source);
        return result;
    }

    private AccountAuthStatusResult failed(String source, Integer cookieStatus, String code, String message) {
        AccountAuthStatusResult result = new AccountAuthStatusResult();
        result.setUsable(false);
        result.setCookieStatus(cookieStatus);
        result.setLoginStatusCode(code);
        result.setLoginStatusMessage(message);
        result.setCheckedAt(LocalDateTime.now());
        result.setSource(source);
        return result;
    }

    private String extractCookieValue(String cookie, String name) {
        if (isBlank(cookie) || isBlank(name)) {
            return null;
        }
        String prefix = name + "=";
        for (String part : cookie.split(";")) {
            String trimmed = part.trim();
            if (trimmed.startsWith(prefix)) {
                return trimmed.substring(prefix.length()).trim();
            }
        }
        return null;
    }

    private String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (!isBlank(value)) {
                return value.trim();
            }
        }
        return null;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
