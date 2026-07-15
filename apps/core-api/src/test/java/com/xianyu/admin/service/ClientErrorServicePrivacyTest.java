package com.xianyu.admin.service;

import com.xianyu.admin.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class ClientErrorServicePrivacyTest {

    @Test
    void reportRedactsCredentialsBeforeWritingAnyClientControlledFields() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        ClientErrorService service = new ClientErrorService(jdbc, mock(JwtUtil.class));

        service.report(Map.of("events", java.util.List.of(Map.of(
                "type", "js",
                "message", "request failed: Bearer abc.def.secret",
                "route", "/settings?apiKey=top-secret",
                "password", "plain-password",
                "context", Map.of("accessToken", "nested-token")
        ))), null, "203.0.113.8", "browser cookie=session-secret");

        ArgumentCaptor<Object[]> params = ArgumentCaptor.forClass(Object[].class);
        verify(jdbc).update(anyString(), params.capture());
        String allPersistedValues = java.util.Arrays.toString(params.getValue());
        assertFalse(allPersistedValues.contains("abc.def.secret"));
        assertFalse(allPersistedValues.contains("top-secret"));
        assertFalse(allPersistedValues.contains("plain-password"));
        assertFalse(allPersistedValues.contains("nested-token"));
        assertFalse(allPersistedValues.contains("session-secret"));
        assertTrue(allPersistedValues.contains("[REDACTED]"));
    }
}
