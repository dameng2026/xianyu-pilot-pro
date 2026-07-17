package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryStatementSessionService;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeliveryStatementControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private DeliveryStatementSessionService sessionService;

    private DeliveryStatementController controller;

    @BeforeEach
    void setUp() {
        controller = new DeliveryStatementController(jdbcTemplate, sessionService);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void getReturnsDefaultOnlyWhenNoStatementExists() {
        when(jdbcTemplate.queryForMap(anyString(), eq(1L)))
                .thenThrow(new EmptyResultDataAccessException(1));

        Result<Map<String, Object>> result = controller.get();

        assertEquals(200, result.getCode());
        assertEquals(false, result.getData().get("enabled"));
        assertEquals("all", result.getData().get("scope"));
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
    void saveRejectsUnsupportedScopeAsBadRequest() {
        BizException error = assertThrows(BizException.class, () -> controller.save(Map.of(
                "enabled", true,
                "content", "声明内容",
                "scope", "everywhere"
        )));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void toggleRequiresBooleanEnabledValue() {
        BizException missing = assertThrows(BizException.class, () -> controller.toggle(Map.of()));
        BizException invalid = assertThrows(BizException.class,
                () -> controller.toggle(Map.of("enabled", "sometimes")));
        BizException fractional = assertThrows(BizException.class,
                () -> controller.toggle(Map.of("enabled", 1.5)));

        assertEquals(400, missing.getCode());
        assertEquals(400, invalid.getCode());
        assertEquals(400, fractional.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void toggleCannotEnableAStatementThatHasNeverBeenConfigured() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L)))
                .thenThrow(new EmptyResultDataAccessException(1));

        BizException error = assertThrows(BizException.class,
                () -> controller.toggle(Map.of("enabled", true)));

        assertEquals(409, error.getCode());
    }

    @Test
    void saveDoesNotInsertWhenLookupItselfFails() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L)))
                .thenThrow(new RuntimeException("database password leaked"));

        BizException error = assertThrows(BizException.class, () -> controller.save(Map.of(
                "enabled", true,
                "content", "声明内容",
                "scope", "all"
        )));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("password"));
    }

    @Test
    void previewRejectsNonTextContentAsBadRequest() {
        BizException error = assertThrows(BizException.class,
                () -> controller.preview(Map.of("content", Map.of("unexpected", true))));

        assertEquals(400, error.getCode());
    }
}
