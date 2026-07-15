package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AdminNotificationLogControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Test
    void requestPathNeverExecutesSchemaDdl() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), any(Object[].class))).thenReturn(0L);
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());
        AdminNotificationLogController controller = new AdminNotificationLogController(jdbcTemplate);

        Result<PageResult<Map<String, Object>>> result = controller.adminDeliveryLogs(1, 20, null, null, null);

        assertEquals(200, result.getCode());
        assertEquals(0L, result.getData().getTotal());
        verify(jdbcTemplate, never()).execute(anyString());
    }

    @Test
    void missingOrUnavailableLogTableIsSafe503() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), any(Object[].class)))
                .thenThrow(new RuntimeException("SQL table missing password=secret"));
        AdminNotificationLogController controller = new AdminNotificationLogController(jdbcTemplate);

        BizException error = assertThrows(BizException.class,
                () -> controller.adminDeliveryLogs(1, 20, null, null, null));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret"));
    }
}
