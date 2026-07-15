package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.OpenSourceBridgeClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class UserFeedbackControllerSecurityTest {
    private JdbcTemplate jdbcTemplate;
    private OpenSourceBridgeClient bridgeClient;
    private UserFeedbackController controller;

    @BeforeEach
    void setUp() {
        jdbcTemplate = mock(JdbcTemplate.class);
        bridgeClient = mock(OpenSourceBridgeClient.class);
        when(bridgeClient.isBridgeEnabled()).thenReturn(false);
        controller = new UserFeedbackController(jdbcTemplate, bridgeClient);
        TenantContext.setCurrentTenantId(11L);
        UserContext.set(7L, "alice", 11L);
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
        TenantContext.clear();
    }

    @Test
    void commercialUserCannotSpoofOpenSourceFeedbackProvenance() {
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);

        controller.submit(Map.of(
                "title", "help",
                "content", "details",
                "siteSource", "open-source",
                "siteName", "forged site"
        ));

        ArgumentCaptor<Object[]> args = ArgumentCaptor.forClass(Object[].class);
        verify(jdbcTemplate).update(anyString(), args.capture());
        assertEquals("commercial", args.getValue()[7]);
        assertEquals("商业版", args.getValue()[8]);
    }

    @Test
    void oversizedFeedbackIsRejectedBeforeDatabaseWork() {
        BizException error = assertThrows(BizException.class, () -> controller.submit(Map.of(
                "title", "help",
                "content", "x".repeat(20_001)
        )));

        assertEquals(400, error.getCode());
        verify(jdbcTemplate, never()).update(anyString(), any(Object[].class));
    }
}
