package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class NotificationConfigServiceTest {

    @Mock JdbcTemplate jdbcTemplate;

    @Test
    void testEndpointsFailClosedUntilARealDeliveryAdapterExists() {
        NotificationConfigService service = service();

        BizException sms = assertThrows(BizException.class,
                () -> service.testSms("13800138000"));

        assertEquals(503, sms.getCode());
    }

    @Test
    void notificationSecretsAreEncryptedAtRestAndNeverReturnedToTheBrowser() {
        NotificationConfigService service = service();
        when(jdbcTemplate.queryForObject(
                "SELECT config_value FROM sys_config WHERE config_key=? AND deleted=0 LIMIT 1",
                String.class, "sms_config"
        )).thenReturn(null);
        when(jdbcTemplate.update(
                eq("UPDATE sys_config SET config_value=?, updated_time=NOW() WHERE config_key=? AND deleted=0"),
                org.mockito.ArgumentMatchers.anyString(), eq("sms_config")
        )).thenReturn(1);

        service.saveSmsConfig(Map.of(
                "provider", "aliyun",
                "accessKeyId", "operator-key-id",
                "accessKeySecret", "plain-secret-must-not-leak"
        ));

        ArgumentCaptor<String> stored = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate).update(
                eq("UPDATE sys_config SET config_value=?, updated_time=NOW() WHERE config_key=? AND deleted=0"),
                stored.capture(), eq("sms_config")
        );
        assertFalse(stored.getValue().contains("plain-secret-must-not-leak"));
        assertTrue(stored.getValue().contains("enc:v1:"));

        when(jdbcTemplate.queryForObject(
                "SELECT config_value FROM sys_config WHERE config_key=? AND deleted=0 LIMIT 1",
                String.class, "sms_config"
        )).thenReturn(stored.getValue());
        Map<String, Object> browserConfig = service.getSmsConfig();
        assertEquals("", browserConfig.get("accessKeySecret"));
        assertEquals(true, browserConfig.get("accessKeySecretConfigured"));
        assertFalse(browserConfig.toString().contains("plain-secret"));
        assertFalse(browserConfig.toString().contains("enc:v1:"));
    }

    private NotificationConfigService service() {
        return new NotificationConfigService(
                jdbcTemplate,
                new CookieCryptoService("test-cookie-secret-longer-than-thirty-two-characters")
        );
    }
}
