package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.OperationAuditService;
import com.xianyu.admin.service.XianyuAccountService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WebSocketControllerTest {

    @Mock
    private AutomationClient automationClient;

    @Mock
    private OperationAuditService auditService;

    @Mock
    private XianyuAccountService accountService;

    private WebSocketController controller;

    @BeforeEach
    void setUp() {
        controller = new WebSocketController(automationClient, auditService, accountService);
        TenantContext.setCurrentTenantId(1L);
        TenantContext.setCurrentUserId(2L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void statusReportsTransportFailureAsSafeServiceUnavailable() {
        when(automationClient.postInternal(eq("/api/websocket/status"), anyMap()))
                .thenThrow(new RuntimeException("http://internal-host:12401 secret"));

        BizException error = assertThrows(BizException.class,
                () -> controller.status(Map.of("accountId", 8L)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("internal-host"));
    }

    @Test
    void statusPreservesAuthenticationFailureInsteadOfFlatteningIt() {
        TenantContext.clear();

        BizException error = assertThrows(BizException.class,
                () -> controller.status(Map.of("accountId", 8L)));

        assertEquals(401, error.getCode());
        verifyNoInteractions(automationClient);
    }

    @Test
    void automationBusinessRejectionIsDistinctFromServiceUnavailability() {
        when(automationClient.postInternal(eq("/api/websocket/start"), anyMap()))
                .thenReturn(Map.of("code", 500, "msg", "Cookie 已过期，请重新登录"));

        BizException error = assertThrows(BizException.class,
                () -> controller.start(Map.of("accountId", 8L), null));

        assertEquals(409, error.getCode());
        assertTrue(error.getMessage().contains("重新登录"));
    }

    @Test
    void technicalFailureReturnedByDependencyIsSafe503() {
        when(automationClient.postInternal(eq("/api/websocket/status"), anyMap()))
                .thenReturn(Map.of("code", 500, "msg", "SQLException password=top-secret"));

        BizException error = assertThrows(BizException.class,
                () -> controller.status(Map.of("accountId", 8L)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("top-secret"));
    }

    @Test
    void checkLoginReturnsUnusableAccountAsSuccessfulBusinessResult() {
        AccountAuthStatusResult auth = new AccountAuthStatusResult();
        auth.setUsable(false);
        auth.setCookieStatus(0);
        auth.setLoginStatusCode("COOKIE_EXPIRED");
        auth.setLoginStatusMessage("Cookie 已失效，请重新登录");
        auth.setCheckedAt(LocalDateTime.now());
        when(accountService.checkAuthStatus(1L, 8L, "websocket-check")).thenReturn(auth);

        Result<Object> result = controller.checkLogin(Map.of("accountId", 8L));

        assertEquals(200, result.getCode());
        Map<?, ?> data = (Map<?, ?>) result.getData();
        assertEquals(false, data.get("loggedIn"));
        assertEquals("COOKIE_EXPIRED", data.get("code"));
    }

    @Test
    void checkLoginReportsDependencyFailureAs503InsteadOfLoggedOut() {
        when(accountService.checkAuthStatus(1L, 8L, "websocket-check"))
                .thenThrow(new RuntimeException("database password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> controller.checkLogin(Map.of("accountId", 8L)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("password"));
    }

    @Test
    void checkLoginRejectsMalformedAccountIdAsBadRequest() {
        BizException error = assertThrows(BizException.class,
                () -> controller.checkLogin(Map.of("accountId", "invalid")));

        assertEquals(400, error.getCode());
        verifyNoInteractions(accountService);
    }

    @Test
    void updateTokenNeverAcceptsFailedRefreshResult() {
        when(automationClient.postInternal(
                eq("/api/account/refresh/force"),
                argThat(payload -> "mh5tk".equals(payload.get("refreshType")))))
                .thenReturn(Map.of(
                        "code", 200,
                        "data", Map.of("success", false, "last_error", "Cookie 已失效")
                ));

        BizException error = assertThrows(BizException.class,
                () -> controller.updateToken(Map.of("accountId", 8L)));

        assertEquals(409, error.getCode());
    }

    @Test
    void updateTokenAcceptsRequestOnlyAfterActualRefreshSucceeds() {
        when(automationClient.postInternal(
                eq("/api/account/refresh/force"),
                argThat(payload -> "mh5tk".equals(payload.get("refreshType")))))
                .thenReturn(Map.of(
                        "code", 200,
                        "data", Map.of("success", true, "details", Map.of("mh5tk", "ok"))
                ));

        Result<Object> result = controller.updateToken(Map.of("accountId", 8L));

        assertEquals(200, result.getCode());
        Map<?, ?> data = (Map<?, ?>) result.getData();
        assertEquals(true, data.get("accepted"));
        assertEquals("online", data.get("service"));
    }

    @Test
    void refreshCookieReportsUnavailableDependencyAs503() {
        when(automationClient.postInternal(
                eq("/api/account/refresh/force"),
                argThat(payload -> "cookie".equals(payload.get("refreshType")))))
                .thenThrow(new RuntimeException("http://internal-host:12401"));

        BizException error = assertThrows(BizException.class,
                () -> controller.refreshCookie(Map.of("accountId", 8L)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("internal-host"));
    }

    @Test
    void sendMessageValidationUsesBadRequest() {
        BizException error = assertThrows(BizException.class,
                () -> controller.sendMessage(Map.of("accountId", 8L), null));

        assertEquals(400, error.getCode());
        verifyNoInteractions(automationClient);
    }

    @Test
    void sendImageValidationUsesBadRequest() {
        BizException error = assertThrows(BizException.class,
                () -> controller.sendImageMessage(Map.of("imageUrl", "http://unsafe.test/a.png"), null));

        assertEquals(400, error.getCode());
        verifyNoInteractions(automationClient);
    }

    @Test
    void updateCookiePreservesBusinessValidationAndMapsUnexpectedFailureTo503() {
        when(accountService.updateCookie(1L, 8L, "unb=8"))
                .thenThrow(new BizException(400, "Cookie缺少_m_h5_tk"));

        BizException validation = assertThrows(BizException.class,
                () -> controller.updateCookie(Map.of("accountId", 8L, "cookie", "unb=8"), null));

        assertEquals(400, validation.getCode());

        when(accountService.updateCookie(1L, 8L, "unb=8; _m_h5_tk=x"))
                .thenThrow(new RuntimeException("SQL url and password"));

        BizException unavailable = assertThrows(BizException.class,
                () -> controller.updateCookie(
                        Map.of("accountId", 8L, "cookie", "unb=8; _m_h5_tk=x"), null));

        assertEquals(503, unavailable.getCode());
        assertFalse(unavailable.getMessage().contains("password"));
    }
}
