package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountFeatureServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private XianyuAccountMapper accountMapper;

    private XianyuAccountFeatureService service;

    @BeforeEach
    void setUp() {
        service = new XianyuAccountFeatureService(jdbcTemplate, accountMapper);
    }

    @Test
    void getAutoRateConfigShouldReturnDefaultsWhenNoRowExists() {
        XianyuAccount account = new XianyuAccount();
        account.setId(18L);
        when(accountMapper.findById(1L, 18L)).thenReturn(account);
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(18L))).thenReturn(List.of());

        Map<String, Object> result = service.getAutoRateConfig(1L, 18L);

        assertEquals(18L, result.get("accountId"));
        assertEquals("text", result.get("rateType"));
        assertEquals("", result.get("textContent"));
        assertEquals("", result.get("apiUrl"));
        assertFalse(Boolean.TRUE.equals(result.get("enabled")));
        verify(jdbcTemplate, never()).execute(anyString());
    }

    @Test
    void autoRateTableFailureIsSafe503InsteadOfDefaultSuccess() {
        XianyuAccount account = new XianyuAccount();
        account.setId(18L);
        when(accountMapper.findById(1L, 18L)).thenReturn(account);
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(18L)))
                .thenThrow(new RuntimeException("SQL table missing password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> service.getAutoRateConfig(1L, 18L));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
    }

    @Test
    void saveAutoRateConfigShouldNormalizeAndPersistPayload() {
        XianyuAccount account = new XianyuAccount();
        account.setId(22L);
        when(accountMapper.findById(1L, 22L)).thenReturn(account);

        Map<String, Object> result = service.saveAutoRateConfig(
                1L,
                9L,
                22L,
                Map.of(
                        "enabled", true,
                        "rateType", "API",
                        "textContent", "  thanks for your order  ",
                        "apiUrl", " https://example.com/review "
                )
        );

        verify(jdbcTemplate, times(1)).update(
                anyString(),
                eq(1L),
                eq(9L),
                eq(22L),
                eq(1),
                eq("api"),
                eq("thanks for your order"),
                eq("https://example.com/review")
        );
        assertTrue(Boolean.TRUE.equals(result.get("enabled")));
        assertEquals("api", result.get("rateType"));
        assertEquals("thanks for your order", result.get("textContent"));
        assertEquals("https://example.com/review", result.get("apiUrl"));
    }

    @Test
    void saveAutoRateDatabaseFailureIsSafe503() {
        XianyuAccount account = new XianyuAccount();
        account.setId(22L);
        when(accountMapper.findById(1L, 22L)).thenReturn(account);
        when(jdbcTemplate.update(
                anyString(), eq(1L), eq(9L), eq(22L), eq(1), eq("text"), eq("thanks"), eq("")))
                .thenThrow(new RuntimeException("jdbc password=secret"));

        BizException error = assertThrows(BizException.class, () -> service.saveAutoRateConfig(
                1L,
                9L,
                22L,
                Map.of("enabled", true, "textContent", "thanks")
        ));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
    }

    @Test
    void getStrategyConfigShouldReturnDefaultsWhenAccountHasNoOverrides() {
        XianyuAccount account = new XianyuAccount();
        account.setId(26L);
        when(accountMapper.findById(1L, 26L)).thenReturn(account);

        Map<String, Object> result = service.getStrategyConfig(1L, 26L);

        assertEquals(26L, result.get("accountId"));
        assertEquals(3600, result.get("messageExpireTime"));
        assertFalse(Boolean.TRUE.equals(result.get("scheduledRedelivery")));
        assertFalse(Boolean.TRUE.equals(result.get("autoPolish")));
    }

    @Test
    void saveStrategyConfigShouldNormalizeAndPersistPayload() {
        XianyuAccount account = new XianyuAccount();
        account.setId(28L);
        when(accountMapper.findById(1L, 28L)).thenReturn(account);

        Map<String, Object> result = service.saveStrategyConfig(
                1L,
                28L,
                Map.of(
                        "messageExpireTime", " 7200 ",
                        "scheduledRedelivery", true,
                        "autoPolish", true
                )
        );

        verify(jdbcTemplate, times(1)).update(
                anyString(),
                eq(7200),
                eq(1),
                eq(1),
                eq(1L),
                eq(28L)
        );
        assertEquals(7200, result.get("messageExpireTime"));
        assertTrue(Boolean.TRUE.equals(result.get("scheduledRedelivery")));
        assertTrue(Boolean.TRUE.equals(result.get("autoPolish")));
    }

    @Test
    void pageFaceVerificationsShouldReturnAccountScopedRows() {
        XianyuAccount account = new XianyuAccount();
        account.setId(31L);
        when(accountMapper.findById(1L, 31L)).thenReturn(account);
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L), eq(9L), eq(31L))).thenReturn(1L);
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(9L), eq(31L), eq(0), eq(10)))
                .thenReturn(List.of(Map.of(
                        "id", 7L,
                        "accountId", 31L,
                        "title", "人机验证提醒",
                        "content", "请尽快处理",
                        "level", "warning",
                        "priority", 2,
                        "readFlag", 0,
                        "createdTime", LocalDateTime.of(2026, 7, 3, 12, 0)
                )));

        PageResult<Map<String, Object>> result = service.pageFaceVerifications(1L, 9L, 31L, 1, 10);

        assertEquals(1L, result.getTotal());
        assertEquals(1, result.getRecords().size());
        assertEquals(31L, result.getRecords().get(0).get("accountId"));
        assertEquals("人机验证提醒", result.getRecords().get(0).get("title"));
    }

    @Test
    void markFaceVerificationReadShouldUpdateNotificationRow() {
        when(jdbcTemplate.update(anyString(), eq(1L), eq(9L), eq(88L),
                eq("人脸验证"), eq("人脸验证"))).thenReturn(1);

        service.markFaceVerificationRead(1L, 9L, 88L);

        verify(jdbcTemplate, times(1)).update(anyString(), eq(1L), eq(9L), eq(88L),
                eq("人脸验证"), eq("人脸验证"));
    }
}
