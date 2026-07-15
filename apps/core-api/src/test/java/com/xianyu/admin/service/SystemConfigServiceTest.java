package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SystemConfigServiceTest {

    @Test
    void missingConfigurationReturnsDocumentedDefaults() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        Map<String, Object> config = new SystemConfigService(jdbc).getConfig();

        assertEquals("闲鱼助手后台管理系统", config.get("siteName"));
        verify(jdbc, never()).update(anyString(), any(Object[].class));
    }

    @Test
    void databaseFailureIsUnavailableInsteadOfFakeDefaultConfiguration() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenThrow(new RuntimeException("database unavailable password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> new SystemConfigService(jdbc).getConfig());

        assertEquals(503, error.getCode());
    }

    @Test
    void zeroAffectedUpdateCannotBecomeSuccessfulConfigurationSave() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenReturn(List.of(Map.of("id", 9L)));
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(0);

        BizException error = assertThrows(BizException.class,
                () -> new SystemConfigService(jdbc).saveConfig(Map.of("siteName", "Enterprise")));

        assertEquals(409, error.getCode());
    }
}
