package com.xianyu.admin.service;

import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuAccountHealthSnapshotMapper;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import com.xianyu.admin.mapper.XianyuAccountMembershipMapper;
import com.xianyu.admin.mapper.XianyuAccountRuntimeMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountServiceTest {

    @Mock
    private XianyuAccountMapper accountMapper;

    @Mock
    private XianyuAccountAuthMapper authMapper;

    @Mock
    private XianyuAccountRuntimeMapper runtimeMapper;

    @Mock
    private XianyuAccountMembershipMapper membershipMapper;

    @Mock
    private XianyuAccountHealthSnapshotMapper healthSnapshotMapper;

    @Mock
    private CookieCryptoService cookieCryptoService;

    @Mock
    private AutomationClient automationClient;

    @Mock
    private XianyuAccountAuthStatusService authStatusService;

    private XianyuAccountService service;

    @BeforeEach
    void setUp() {
        service = new XianyuAccountService(
                accountMapper,
                authMapper,
                runtimeMapper,
                membershipMapper,
                healthSnapshotMapper,
                cookieCryptoService,
                automationClient,
                authStatusService
        );
    }

    @Test
    void deleteShouldStopAutomationAndSoftDeleteRelatedRecords() {
        XianyuAccount account = new XianyuAccount();
        account.setId(9L);
        account.setTenantId(1L);
        when(accountMapper.findById(1L, 9L)).thenReturn(account);

        service.delete(1L, 9L);

        verify(automationClient, times(1)).postInternal(
                eq("/api/websocket/stop"),
                eq(Map.of(
                        "tenantId", 1L,
                        "tenant_id", 1L,
                        "accountId", 9L,
                        "xianyuAccountId", 9L
                )),
                eq(1L)
        );
        verify(authMapper, times(1)).softDeleteByAccountId(1L, 9L);
        verify(runtimeMapper, times(1)).softDeleteByAccountId(1L, 9L);
        verify(accountMapper, times(1)).softDelete(1L, 9L);
    }

    @Test
    void deleteShouldContinueSoftDeleteWhenStopAutomationFails() {
        XianyuAccount account = new XianyuAccount();
        account.setId(9L);
        account.setTenantId(1L);
        when(accountMapper.findById(1L, 9L)).thenReturn(account);
        when(automationClient.postInternal(eq("/api/websocket/stop"), org.mockito.ArgumentMatchers.<Map<String, Object>>any(), anyLong()))
                .thenThrow(new RuntimeException("stop failed"));

        service.delete(1L, 9L);

        verify(authMapper, times(1)).softDeleteByAccountId(1L, 9L);
        verify(runtimeMapper, times(1)).softDeleteByAccountId(1L, 9L);
        verify(accountMapper, times(1)).softDelete(1L, 9L);
    }

    @Test
    void updateCookieShouldTriggerUnifiedAuthRecheckAfterSavingCookie() {
        XianyuAccount account = new XianyuAccount();
        account.setId(15L);
        account.setTenantId(1L);
        account.setExternalUid("uid-15");
        account.setStatus(1);
        when(accountMapper.findById(1L, 15L)).thenReturn(account);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setTenantId(1L);
        auth.setAccountId(15L);
        when(authMapper.findByAccountId(1L, 15L)).thenReturn(auth);

        service.updateCookie(1L, 15L, "unb=uid-15; _m_h5_tk=token15;");

        verify(authStatusService, times(1)).check(1L, 15L, "cookie_updated");
    }

    @Test
    void updateCookieShouldRejectCookieForAnotherAccountBeforeRecheck() {
        XianyuAccount account = new XianyuAccount();
        account.setId(16L);
        account.setTenantId(1L);
        account.setExternalUid("uid-16");
        account.setStatus(1);
        when(accountMapper.findById(1L, 16L)).thenReturn(account);

        assertThrows(RuntimeException.class, () -> service.updateCookie(1L, 16L, "unb=uid-other; _m_h5_tk=token16;"));
    }

    @Test
    void getLoginCredentialConfigShouldExposeConfiguredFlags() {
        XianyuAccount account = new XianyuAccount();
        account.setId(18L);
        account.setTenantId(1L);
        when(accountMapper.findById(1L, 18L)).thenReturn(account);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setTenantId(1L);
        auth.setAccountId(18L);
        auth.setLoginUsername("demo-user");
        auth.setEncryptedLoginPassword("enc:v1:test");
        auth.setShowBrowser(true);
        when(authMapper.findByAccountId(1L, 18L)).thenReturn(auth);

        Map<String, Object> result = service.getLoginCredentialConfig(1L, 18L);

        assertEquals(18L, result.get("accountId"));
        assertEquals("demo-user", result.get("loginUsername"));
        assertTrue(Boolean.TRUE.equals(result.get("hasLoginPassword")));
        assertTrue(Boolean.TRUE.equals(result.get("showBrowser")));
    }

    @Test
    void saveLoginCredentialConfigShouldEncryptPasswordBeforePersisting() {
        XianyuAccount account = new XianyuAccount();
        account.setId(19L);
        account.setTenantId(1L);
        when(accountMapper.findById(1L, 19L)).thenReturn(account);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setId(7L);
        auth.setTenantId(1L);
        auth.setAccountId(19L);
        when(authMapper.findByAccountId(1L, 19L)).thenReturn(auth);
        when(cookieCryptoService.encrypt("secret-pass")).thenReturn("enc:v1:secret");

        Map<String, Object> result = service.saveLoginCredentialConfig(
                1L,
                19L,
                Map.of(
                        "loginUsername", "demo-user",
                        "loginPassword", "secret-pass",
                        "showBrowser", true
                )
        );

        ArgumentCaptor<XianyuAccountAuth> captor = ArgumentCaptor.forClass(XianyuAccountAuth.class);
        verify(authMapper, times(1)).update(captor.capture());
        XianyuAccountAuth saved = captor.getValue();
        assertEquals("demo-user", saved.getLoginUsername());
        assertEquals("enc:v1:secret", saved.getEncryptedLoginPassword());
        assertTrue(Boolean.TRUE.equals(saved.getShowBrowser()));
        assertEquals("demo-user", result.get("loginUsername"));
        assertTrue(Boolean.TRUE.equals(result.get("hasLoginPassword")));
        assertTrue(Boolean.TRUE.equals(result.get("showBrowser")));
    }
}
