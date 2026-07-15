package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.dto.XianyuAccountVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.XianyuAccountService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class UserQrLoginControllerTest {
    private static final String RESCAN_SESSION = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
    private static final String NEW_SESSION = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB";

    @Mock
    private AutomationClient automationClient;

    @Mock
    private XianyuAccountService accountService;

    private UserQrLoginController controller;

    @BeforeEach
    void setUp() {
        controller = new UserQrLoginController(automationClient, accountService);
        TenantContext.setCurrentTenantId(1L);
        TenantContext.setCurrentUserId(2L);
        UserContext.set(2L, "tester", 1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void statusShouldRefreshProfileAndRestartRealtimeFlowAfterRescan() {
        when(automationClient.postInternalForData(
                eq("/api/internal/qrlogin/status/" + RESCAN_SESSION),
                eq(Map.of("tenantId", 1L, "userId", 2L, "accountId", 18L))
        )).thenReturn(new LinkedHashMap<>(Map.of(
                "status", "confirmed",
                "message", "qr ok"
        )));
        when(automationClient.postInternalForData(
                eq("/api/internal/qrlogin/cookies/" + RESCAN_SESSION),
                eq(Map.of("tenantId", 1L, "userId", 2L, "accountId", 18L))
        )).thenReturn(new LinkedHashMap<>(Map.of(
                "cookies", Map.of(
                        "unb", "uid-18",
                        "_m_h5_tk", "token18"
                )
        )));

        XianyuAccountVO updated = new XianyuAccountVO();
        updated.setId(18L);
        updated.setCookieStatus(1);
        updated.setAuthUsable(true);
        updated.setLoginStatusCode("OK");
        updated.setLoginStatusMessage("auth-ok");
        when(accountService.updateCookie(eq(1L), eq(18L), anyString())).thenReturn(updated);

        AccountAuthStatusResult auth = new AccountAuthStatusResult();
        auth.setUsable(true);
        auth.setCookieStatus(1);
        auth.setLoginStatusCode("OK");
        auth.setLoginStatusMessage("auth-ok");
        when(accountService.checkAuthStatus(1L, 18L, "qr-login")).thenReturn(auth);

        XianyuAccountVO refreshed = new XianyuAccountVO();
        refreshed.setId(18L);
        refreshed.setCookieStatus(1);
        refreshed.setAuthUsable(true);
        refreshed.setLoginStatusCode("OK");
        refreshed.setLoginStatusMessage("auth-ok");
        refreshed.setDisplayName("fresh-profile");
        when(accountService.refreshProfile(1L, 18L)).thenReturn(refreshed);

        Result<Map<String, Object>> result = controller.status(RESCAN_SESSION, Map.of("accountId", 18L));

        verify(accountService, times(1)).updateCookie(
                eq(1L),
                eq(18L),
                argThat(cookie -> cookie != null
                        && cookie.contains("unb=uid-18")
                        && cookie.contains("_m_h5_tk=token18"))
        );
        verify(accountService, times(1)).checkAuthStatus(1L, 18L, "qr-login");
        verify(accountService, times(1)).refreshProfile(1L, 18L);
        verify(automationClient, times(1)).postInternal(
                eq("/api/websocket/start"),
                eq(Map.of(
                        "tenantId", 1L,
                        "tenant_id", 1L,
                        "accountId", 18L,
                        "xianyuAccountId", 18L,
                        "forceReconnect", true
                )),
                eq(1L)
        );
        verify(automationClient, times(1)).postInternalForData(
                eq("/api/internal/qrlogin/cleanup/" + RESCAN_SESSION),
                eq(Map.of("tenantId", 1L, "userId", 2L, "accountId", 18L))
        );
        assertNotNull(result.getData());
        assertEquals("confirmed", result.getData().get("status"));
        assertEquals(18L, result.getData().get("accountId"));
        assertEquals(1, result.getData().get("cookieStatus"));
        assertEquals("OK", result.getData().get("loginStatusCode"));
        assertEquals("fresh-profile", result.getData().get("displayName"));
    }

    @Test
    void statusShouldRecheckNewQrLoginBeforeRefreshingProfile() {
        when(automationClient.postInternalForData(
                eq("/api/internal/qrlogin/status/" + NEW_SESSION),
                eq(Map.of("tenantId", 1L, "userId", 2L))
        )).thenReturn(new LinkedHashMap<>(Map.of(
                "status", "confirmed",
                "accountId", 28L,
                "cookieStatus", 1,
                "message", "saved"
        )));

        AccountAuthStatusResult auth = new AccountAuthStatusResult();
        auth.setUsable(false);
        auth.setCookieStatus(0);
        auth.setLoginStatusCode("COOKIE_EXPIRED");
        auth.setLoginStatusMessage("expired");
        when(accountService.checkAuthStatus(1L, 28L, "qr-login")).thenReturn(auth);

        XianyuAccountVO detail = new XianyuAccountVO();
        detail.setId(28L);
        detail.setCookieStatus(0);
        detail.setAuthUsable(false);
        detail.setLoginStatusCode("COOKIE_EXPIRED");
        detail.setLoginStatusMessage("expired");
        when(accountService.detail(1L, 28L)).thenReturn(detail);

        Result<Map<String, Object>> result = controller.status(NEW_SESSION, null);

        verify(accountService, times(1)).checkAuthStatus(1L, 28L, "qr-login");
        verify(accountService, times(1)).detail(1L, 28L);
        verify(accountService, never()).refreshProfile(1L, 28L);
        verify(automationClient, never()).postInternal(
                eq("/api/websocket/start"),
                org.mockito.ArgumentMatchers.<Map<String, Object>>any(),
                eq(1L)
        );
        assertNotNull(result.getData());
        assertEquals(28L, result.getData().get("accountId"));
        assertEquals(0, result.getData().get("cookieStatus"));
        assertEquals("COOKIE_EXPIRED", result.getData().get("loginStatusCode"));
    }

    @Test
    void statusShouldRejectMalformedSessionBeforeCallingAutomationService() {
        BizException error = assertThrows(
                BizException.class,
                () -> controller.status("../not-a-session", null)
        );

        assertEquals(400, error.getCode());
        verify(automationClient, never()).postInternalForData(
                anyString(),
                org.mockito.ArgumentMatchers.<Map<String, Object>>any()
        );
    }
}
