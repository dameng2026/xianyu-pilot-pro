package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WorkflowAccountValidationServiceTest {

    @Mock
    private XianyuAccountMapper accountMapper;

    @Mock
    private XianyuAccountAuthStatusService authStatusService;

    private WorkflowAccountValidationService service;

    @BeforeEach
    void setUp() {
        service = new WorkflowAccountValidationService(accountMapper, authStatusService);
    }

    @Test
    void assertExecutionAccountsReadyRejectsInvalidAccountsBeforeRun() {
        when(accountMapper.findById(1L, 11L)).thenReturn(account(11L, "正常账号", 1, "uid-11"));
        when(authStatusService.check(1L, 11L, "workflow")).thenReturn(authResult(true, 1, "OK", "账号登录状态正常"));

        when(accountMapper.findById(1L, 12L)).thenReturn(account(12L, "失效账号", 1, "uid-12"));
        when(authStatusService.check(1L, 12L, "workflow")).thenReturn(authResult(false, 0, "COOKIE_EXPIRED", "登录已失效，请重新登录闲鱼账号"));

        BizException ex = assertThrows(BizException.class, () -> service.assertExecutionAccountsReady(
                1L,
                List.of(triggerNode(List.of(11L, 12L))),
                Map.of()
        ));

        assertEquals(400, ex.getCode());
        assertEquals("运行前账号校验失败，请先重新登录以下账号", ex.getMessage());
        assertInstanceOf(Map.class, ex.getData());
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) ex.getData();
        assertEquals(false, payload.get("ok"));
        assertEquals("ACCOUNT_LOGIN_INVALID", payload.get("reason"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> invalidAccounts = (List<Map<String, Object>>) payload.get("invalidAccounts");
        assertEquals(1, invalidAccounts.size());
        assertEquals(12L, invalidAccounts.get(0).get("accountId"));
        assertEquals("失效账号", invalidAccounts.get(0).get("nickname"));
        assertEquals("登录已失效，请重新登录闲鱼账号", invalidAccounts.get(0).get("reason"));
        assertEquals("COOKIE_EXPIRED", invalidAccounts.get(0).get("code"));
    }

    @Test
    void validateExecutionAccountsSupportsLegacySingleAccountId() {
        when(accountMapper.findById(1L, 21L)).thenReturn(account(21L, "老工作流账号", 1, "uid-21"));
        when(authStatusService.check(1L, 21L, "workflow")).thenReturn(authResult(true, 1, "OK", "账号登录状态正常"));

        List<Map<String, Object>> invalidAccounts = service.validateExecutionAccounts(
                1L,
                List.of(triggerNodeWithLegacyAccountId(21L)),
                Map.of()
        );

        assertTrue(invalidAccounts.isEmpty());
    }

    @Test
    void validateExecutionAccountsRejectsCookieWithoutMh5Token() {
        when(accountMapper.findById(1L, 31L)).thenReturn(account(31L, "缺少Token账号", 1, "uid-31"));
        when(authStatusService.check(1L, 31L, "workflow")).thenReturn(authResult(false, 0, "COOKIE_TOKEN_MISSING", "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号"));

        List<Map<String, Object>> invalidAccounts = service.validateExecutionAccounts(
                1L,
                List.of(triggerNode(List.of(31L))),
                Map.of()
        );

        assertEquals(1, invalidAccounts.size());
        assertEquals("Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号", invalidAccounts.get(0).get("reason"));
    }

    @Test
    void validateExecutionAccountsReadsAccountIdsFromInputAndDeduplicates() {
        when(accountMapper.findById(1L, 41L)).thenReturn(account(41L, "输入账号", 1, "uid-41"));
        when(authStatusService.check(1L, 41L, "workflow")).thenReturn(authResult(true, 1, "OK", "账号登录状态正常"));

        List<Map<String, Object>> invalidAccounts = service.validateExecutionAccounts(
                1L,
                List.of(triggerNode(List.of(41L))),
                Map.of("selectedAccountIds", List.of(41L, 41L))
        );

        assertTrue(invalidAccounts.isEmpty());
        verify(accountMapper).findById(1L, 41L);
        verify(accountMapper, never()).findById(1L, 42L);
    }

    @Test
    void validateExecutionAccountsIgnoresLegacySingleIdWhenArrayPresent() {
        // TRIGGER 节点同时有 selectedAccountIds 数组 [51] 和遗留 selectedAccountId=52
        // 应只校验数组中的 51，不校验遗留单值 52（避免已删除账号的残留 ID 阻塞运行）
        when(accountMapper.findById(1L, 51L)).thenReturn(account(51L, "当前账号", 1, "uid-51"));
        when(authStatusService.check(1L, 51L, "workflow")).thenReturn(authResult(true, 1, "OK", "账号登录状态正常"));

        List<Map<String, Object>> invalidAccounts = service.validateExecutionAccounts(
                1L,
                List.of(triggerNodeWithArrayAndLegacyId(List.of(51L), 52L)),
                Map.of()
        );

        assertTrue(invalidAccounts.isEmpty());
        verify(accountMapper).findById(1L, 51L);
        verify(accountMapper, never()).findById(1L, 52L);
        verify(authStatusService, never()).check(1L, 52L, "workflow");
    }

    private static Map<String, Object> triggerNode(List<Long> accountIds) {
        return Map.of(
                "type", "TRIGGER",
                "config", Map.of("selectedAccountIds", accountIds)
        );
    }

    private static Map<String, Object> triggerNodeWithLegacyAccountId(Long accountId) {
        return Map.of(
                "type", "TRIGGER",
                "config", Map.of("selectedAccountId", accountId)
        );
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> triggerNodeWithArrayAndLegacyId(List<Long> accountIds, Long legacyId) {
        // Map.of 不可变，用 java.util.HashMap 构造可变 config
        java.util.Map<String, Object> config = new java.util.HashMap<>();
        config.put("selectedAccountIds", accountIds);
        config.put("selectedAccountId", legacyId);
        java.util.Map<String, Object> node = new java.util.HashMap<>();
        node.put("type", "TRIGGER");
        node.put("config", config);
        return node;
    }

    private static XianyuAccount account(Long id, String nickname, Integer status, String externalUid) {
        XianyuAccount account = new XianyuAccount();
        account.setId(id);
        account.setNickname(nickname);
        account.setStatus(status);
        account.setExternalUid(externalUid);
        return account;
    }

    private static AccountAuthStatusResult authResult(boolean usable, int cookieStatus, String code, String message) {
        AccountAuthStatusResult result = new AccountAuthStatusResult();
        result.setUsable(usable);
        result.setCookieStatus(cookieStatus);
        result.setLoginStatusCode(code);
        result.setLoginStatusMessage(message);
        result.setSource("workflow");
        return result;
    }
}
