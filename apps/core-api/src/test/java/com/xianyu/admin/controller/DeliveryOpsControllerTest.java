package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryExecutionService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeliveryOpsControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private DeliveryExecutionService deliveryExecutionService;

    private DeliveryOpsController controller;

    @BeforeEach
    void setUp() {
        controller = new DeliveryOpsController(jdbcTemplate, deliveryExecutionService);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void statsReportsDatabaseFailureAsSafeServiceUnavailable() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(1L), eq(LocalDate.now())))
                .thenThrow(new RuntimeException("jdbc:secret-host"));

        BizException error = assertThrows(BizException.class, controller::stats);

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret-host"));
    }

    @Test
    void triggerRejectsMissingAndMalformedOrderIdsAsBadRequest() {
        BizException missing = assertThrows(BizException.class, () -> controller.trigger(Map.of()));
        BizException malformed = assertThrows(BizException.class,
                () -> controller.trigger(Map.of("orderId", "not-a-number")));
        BizException fractional = assertThrows(BizException.class,
                () -> controller.trigger(Map.of("orderId", 1.5)));

        assertEquals(400, missing.getCode());
        assertEquals(400, malformed.getCode());
        assertEquals(400, fractional.getCode());
        verifyNoInteractions(jdbcTemplate, deliveryExecutionService);
    }

    @Test
    void triggerDoesNotClaimSuccessWhenOrderDoesNotExist() {
        when(jdbcTemplate.update(anyString(), eq(1L), eq(42L), eq("after_payment"), eq(1L), eq(42L)))
                .thenReturn(0);

        BizException error = assertThrows(BizException.class,
                () -> controller.trigger(Map.of("orderId", 42L)));

        assertEquals(404, error.getCode());
        verifyNoInteractions(deliveryExecutionService);
    }

    @Test
    void triggerReportsDatabaseFailureAsServiceUnavailable() {
        when(jdbcTemplate.update(anyString(), eq(1L), eq(42L), eq("after_payment"), eq(1L), eq(42L)))
                .thenThrow(new RuntimeException("insert SQL with password"));

        BizException error = assertThrows(BizException.class,
                () -> controller.trigger(Map.of("orderId", 42L)));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("password"));
    }

    @Test
    void scanDoesNotTurnQueryFailureIntoEmptySuccessfulScan() {
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(1L), eq(1L)))
                .thenThrow(new RuntimeException("database unavailable"));

        BizException error = assertThrows(BizException.class, controller::scan);

        assertEquals(503, error.getCode());
    }

    @Test
    void scanReportsDatabaseFailureWhileCreatingTasksAs503() {
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(1L), eq(1L)))
                .thenReturn(List.of(Map.of("order_id", 42L, "account_id", 9L)));
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(1L), eq(42L)))
                .thenThrow(new RuntimeException("database unavailable"));

        BizException error = assertThrows(BizException.class, controller::scan);

        assertEquals(503, error.getCode());
        verifyNoInteractions(deliveryExecutionService);
    }

    @Test
    void scanPropagatesUnavailableExecutionDependencyAs503() {
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(1L), eq(1L)))
                .thenReturn(List.of(Map.of("order_id", 42L, "account_id", 9L)));
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(1L), eq(42L)))
                .thenReturn(0);
        when(jdbcTemplate.update(anyString(), eq(1L), eq(9L), eq(42L))).thenReturn(1);
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq(1L), eq(42L)))
                .thenReturn(77L);
        when(jdbcTemplate.queryForMap(anyString(), eq(77L), eq(1L)))
                .thenReturn(Map.of("id", 77L, "tenant_id", 1L, "order_id", 42L));
        doThrow(new BizException(503, "dependency unavailable"))
                .when(deliveryExecutionService).executeDelivery(anyMap());

        BizException error = assertThrows(BizException.class, controller::scan);

        assertEquals(503, error.getCode());
    }
}
