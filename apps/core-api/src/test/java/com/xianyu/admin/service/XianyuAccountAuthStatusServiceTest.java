package com.xianyu.admin.service;

import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import com.xianyu.admin.mapper.XianyuAccountRuntimeMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountAuthStatusServiceTest {

    @Mock
    private XianyuAccountMapper accountMapper;

    @Mock
    private XianyuAccountAuthMapper authMapper;

    @Mock
    private CookieCryptoService cookieCryptoService;

    @Mock
    private XianyuAccountAvailabilityProbeService probeService;

    @Mock
    private XianyuAccountRuntimeMapper runtimeMapper;

    private XianyuAccountAuthStatusService service;

    @BeforeEach
    void setUp() {
        service = new XianyuAccountAuthStatusService(accountMapper, authMapper, runtimeMapper, cookieCryptoService, probeService);
    }

    @Test
    void checkReturnsStructuredFailureWhenCookieTokenIsMissing() {
        when(accountMapper.findById(1L, 31L)).thenReturn(account(31L, "缺 token 账号", 1, "uid-31"));
        when(authMapper.findByAccountId(1L, 31L)).thenReturn(auth(31L, "encrypted-cookie-31"));
        when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-31")).thenReturn("unb=uid-31; cookie2=abc;");

        AccountAuthStatusResult result = service.check(1L, 31L, "test");

        assertFalse(result.isUsable());
        assertEquals(0, result.getCookieStatus());
        assertEquals("COOKIE_TOKEN_MISSING", result.getLoginStatusCode());
        assertEquals("Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号", result.getLoginStatusMessage());
        assertEquals("test", result.getSource());
    }

    private static XianyuAccount account(Long id, String nickname, Integer status, String externalUid) {
        XianyuAccount account = new XianyuAccount();
        account.setId(id);
        account.setNickname(nickname);
        account.setStatus(status);
        account.setExternalUid(externalUid);
        return account;
    }

    private static XianyuAccountAuth auth(Long accountId, String encryptedCookie) {
        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setAccountId(accountId);
        auth.setEncryptedCookie(encryptedCookie);
        return auth;
    }
}
