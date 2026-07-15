package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.ScheduleRedeliveryRequest;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryExecutionService;
import com.xianyu.admin.service.OrderDeliveryCommandService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class AutoDeliveryRecordControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private DeliveryExecutionService deliveryExecutionService;

    @Mock
    private OrderDeliveryCommandService orderDeliveryCommandService;

    private AutoDeliveryRecordController controller;

    @BeforeEach
    void setUp() {
        controller = new AutoDeliveryRecordController(jdbcTemplate, deliveryExecutionService, orderDeliveryCommandService);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void scheduleRedeliveryShouldDelegateToCommandService() {
        ScheduleRedeliveryRequest request = new ScheduleRedeliveryRequest();
        request.setCronExpression("0 0/15 * * * ?");

        Result<Void> result = controller.scheduleRedelivery(900L, request);

        verify(orderDeliveryCommandService).scheduleRedelivery(1L, 900L, request);
        assertEquals(200, result.getCode());
    }
}
