package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeliveryGlobalConfigControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    private DeliveryGlobalConfigController controller;

    @BeforeEach
    void setUp() {
        controller = new DeliveryGlobalConfigController(jdbcTemplate);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void getReturnsEmptyConfigurationOnlyWhenNoRowExists() {
        when(jdbcTemplate.queryForMap(anyString(), eq(1L)))
                .thenThrow(new EmptyResultDataAccessException(1));

        Result<Map<String, Object>> result = controller.get();

        assertEquals(200, result.getCode());
        assertEquals(Map.of(), result.getData());
    }

    @Test
    void getReportsDatabaseFailureAsSafeServiceUnavailable() {
        when(jdbcTemplate.queryForMap(anyString(), eq(1L)))
                .thenThrow(new RuntimeException("jdbc:secret-host"));

        BizException error = assertThrows(BizException.class, controller::get);

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret-host"));
    }

    @Test
    void saveInsertsOnlyWhenLookupConfirmsNoExistingRow() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L)))
                .thenThrow(new EmptyResultDataAccessException(1));
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);

        Result<Void> result = controller.save(Map.of("enabled", true));

        assertEquals(200, result.getCode());
    }

    @Test
    void saveDoesNotTreatLookupFailureAsMissingConfiguration() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L)))
                .thenThrow(new RuntimeException("database password leaked"));

        BizException error = assertThrows(BizException.class,
                () -> controller.save(Map.of("enabled", true)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("password"));
        verifyNoMoreInteractions(jdbcTemplate);
    }

    @Test
    void saveRejectsMissingBodyAsBadRequest() {
        BizException error = assertThrows(BizException.class, () -> controller.save(null));

        assertEquals(400, error.getCode());
    }
}
