package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.SystemConfigService;
import com.xianyu.admin.service.OutboundNotificationPolicy;
import com.xianyu.admin.service.CookieCryptoService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import org.mockito.ArgumentCaptor;

@ExtendWith(MockitoExtension.class)
class UserUtilityControllerTest {

    @Mock
    private SystemConfigService systemConfigService;

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private OutboundNotificationPolicy outboundNotificationPolicy;

    private UserUtilityController controller;

    @BeforeEach
    void setUp() {
        controller = new UserUtilityController(
                systemConfigService,
                jdbcTemplate,
                outboundNotificationPolicy,
                new CookieCryptoService("test-notification-secret-longer-than-thirty-two-characters")
        );
        TenantContext.setCurrentTenantId(1L);
        UserContext.set(2L, "tester", 1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void missingSettingsRowsReturnDefaultsWithoutRuntimeDdl() {
        when(jdbcTemplate.queryForObject(
                contains("user_notification_setting"), eq(String.class), eq(1L), eq(2L)))
                .thenThrow(new EmptyResultDataAccessException(1));
        when(jdbcTemplate.queryForObject(
                contains("admin_module_record"), eq(String.class), eq("user-notification-settings"), eq("2")))
                .thenThrow(new EmptyResultDataAccessException(1));

        Result<Map<String, Object>> result = controller.getNotificationSettings();

        assertEquals(200, result.getCode());
        assertEquals(1L, result.getData().get("tenantId"));
        assertEquals(2L, result.getData().get("userId"));
        verify(jdbcTemplate, never()).execute(anyString());
    }

    @Test
    void settingsTableFailureIs503InsteadOfDefaultSuccess() {
        when(jdbcTemplate.queryForObject(
                contains("user_notification_setting"), eq(String.class), eq(1L), eq(2L)))
                .thenThrow(new RuntimeException("SQL table missing password=secret"));

        BizException error = assertThrows(BizException.class, controller::getNotificationSettings);

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
    }

    @Test
    void saveSettingsDatabaseFailureIsSafe503() {
        when(jdbcTemplate.update(anyString(), eq(1L), eq(2L), anyString()))
                .thenThrow(new RuntimeException("jdbc password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> controller.saveNotificationSettings(Map.of("channels", java.util.List.of())));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
        verify(jdbcTemplate, never()).execute(anyString());
    }

    @Test
    void deliveryLogTableFailureIsSafe503() {
        when(jdbcTemplate.queryForObject(
                contains("notification_delivery_log"), eq(Long.class), eq(1L), eq(2L)))
                .thenThrow(new RuntimeException("table missing jdbc password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> controller.deliveryLogs(1, 20));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
        verify(jdbcTemplate, never()).execute(anyString());
    }

    @Test
    void unsafeWebhookConfigurationIsRejectedBeforePersistence() {
        org.mockito.Mockito.doThrow(new IllegalArgumentException("通知地址解析到了非公网网络"))
                .when(outboundNotificationPolicy)
                .validateWebhook("webhook", "https://metadata.example/latest");

        BizException error = assertThrows(BizException.class, () -> controller.saveNotificationSettings(Map.of(
                "channels", java.util.List.of(Map.of(
                        "key", "webhook",
                        "type", "webhook",
                        "enabled", true,
                        "webhookUrl", "https://metadata.example/latest"
                ))
        )));

        assertEquals(400, error.getCode());
        verify(jdbcTemplate, never()).update(anyString(), eq(1L), eq(2L), anyString());
    }

    @Test
    void notificationSecretsAreEncryptedAtRestAndWriteOnlyInBrowserResponses() {
        when(jdbcTemplate.queryForObject(
                contains("user_notification_setting"), eq(String.class), eq(1L), eq(2L)))
                .thenReturn(null);

        controller.saveNotificationSettings(Map.of(
                "channels", java.util.List.of(Map.of(
                        "key", "feishu",
                        "type", "feishu",
                        "enabled", true,
                        "webhookUrl", "https://open.feishu.cn/open-apis/bot/v2/hook/token",
                        "secret", "plain-signing-secret"
                ))
        ));

        ArgumentCaptor<String> storedJson = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate).update(
                contains("INSERT INTO user_notification_setting"),
                eq(1L),
                eq(2L),
                storedJson.capture()
        );
        assertFalse(storedJson.getValue().contains("plain-signing-secret"));
        assertTrue(storedJson.getValue().contains("enc:v1:"));

        org.mockito.Mockito.reset(jdbcTemplate);
        when(jdbcTemplate.queryForObject(
                contains("user_notification_setting"), eq(String.class), eq(1L), eq(2L)))
                .thenReturn(storedJson.getValue());

        Map<String, Object> browser = controller.getNotificationSettings().getData();
        @SuppressWarnings("unchecked")
        Map<String, Object> channel = ((java.util.List<Map<String, Object>>) browser.get("channels")).get(0);
        assertEquals("", channel.get("secret"));
        assertEquals(true, channel.get("secretConfigured"));
        assertFalse(browser.toString().contains("enc:v1:"));
        assertFalse(browser.toString().contains("plain-signing-secret"));
    }

    @Test
    void markingNotificationReadIsBoundToCurrentTenantAndUser() {
        when(jdbcTemplate.update(anyString(), eq(1L), eq(2L), eq(77L))).thenReturn(1);

        controller.read(77L);

        verify(jdbcTemplate).update(
                contains("tenant_id=? AND user_id=? AND id=? AND deleted=0"),
                eq(1L), eq(2L), eq(77L));
    }
}
