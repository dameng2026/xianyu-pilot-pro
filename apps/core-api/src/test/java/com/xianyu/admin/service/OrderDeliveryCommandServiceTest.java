package com.xianyu.admin.service;

import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.dto.ScheduleRedeliveryRequest;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.invocation.Invocation;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mockingDetails;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OrderDeliveryCommandServiceTest {

    @Mock
    private XianyuTradeOrderMapper orderMapper;

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private AutomationClient automationClient;

    @Mock
    private DeliveryExecutionService deliveryExecutionService;

    private OrderDeliveryCommandService service;

    @BeforeEach
    void setUp() {
        service = new OrderDeliveryCommandService(orderMapper, jdbcTemplate, automationClient, deliveryExecutionService);
    }

    @Test
    void manualDeliveryShouldCreateRecordAndExecuteImmediately() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(55L);
        order.setTenantId(1L);
        order.setAccountId(8L);
        order.setExternalOrderId("ORDER-55");
        when(orderMapper.findById(1L, 55L)).thenReturn(order);
        when(jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class)).thenReturn(900L);

        OrderManualDeliveryRequest request = new OrderManualDeliveryRequest();
        request.setDeliveryMode("text");
        request.setDeliveryTiming("after_payment");
        request.setDeliveryContent("download-link");
        request.setQuantityRequested(2);

        service.manualDelivery(1L, 55L, request);

        verify(jdbcTemplate).update(
                contains("INSERT INTO delivery_record"),
                eq(1L),
                eq(8L),
                eq(55L),
                eq("after_payment"),
                eq("text"),
                eq("manual_text"),
                eq("download-link"),
                eq("download-link"),
                eq(2),
                eq(0),
                eq(0),
                eq("pending")
        );
        verify(deliveryExecutionService).retryDelivery(900L, 1L);
    }

    @Test
    void syncOrderShouldForwardOrderIdentityToAutomationService() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(55L);
        order.setTenantId(1L);
        order.setAccountId(8L);
        order.setExternalOrderId("ORDER-55");
        when(orderMapper.findById(1L, 55L)).thenReturn(order);

        service.syncOrder(1L, 55L);

        List<Invocation> invocations = List.copyOf(mockingDetails(automationClient).getInvocations());
        assertEquals(1, invocations.size());
        assertEquals("postInternalForData", invocations.get(0).getMethod().getName());
        assertEquals("/api/internal/orders/sync-sold", invocations.get(0).getArguments()[0]);
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) invocations.get(0).getArguments()[1];
        assertEquals(1L, payload.get("tenantId"));
        assertEquals(8L, payload.get("accountId"));
        assertEquals("ORDER-55", payload.get("externalOrderId"));
        assertEquals(1L, invocations.get(0).getArguments()[2]);
    }

    @Test
    void syncOrderShouldReturnRedactedStructuredFailureWhenAutomationThrows() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(55L);
        order.setTenantId(1L);
        order.setAccountId(8L);
        order.setExternalOrderId("ORDER-55");
        when(orderMapper.findById(1L, 55L)).thenReturn(order);
        doThrow(new RuntimeException("automation unavailable"))
                .when(automationClient)
                .postInternalForData(eq("/api/internal/orders/sync-sold"), anyMap(), eq(Long.valueOf(1L)));

        Map<String, Object> result = service.syncOrder(1L, 55L);

        assertFalse(Boolean.TRUE.equals(result.get("ok")));
        assertEquals("订单同步失败", result.get("message"));
    }

    @Test
    void syncOrdersShouldNormalizeNestedFailurePayloadFromAutomationService() {
        doReturn(Map.of("code", 500, "msg", "订单接口返回结构异常"))
                .when(automationClient)
                .postInternalForData(eq("/api/internal/orders/sync-sold"), anyMap(), eq(Long.valueOf(1L)));

        OrderSyncRequest request = new OrderSyncRequest();
        request.setAccountId(8L);
        request.setSyncDeliveryStatus(Boolean.FALSE);

        Map<String, Object> result = service.syncOrders(1L, request);

        assertFalse(Boolean.TRUE.equals(result.get("ok")));
        assertEquals("订单接口返回结构异常", result.get("message"));
    }

    @Test
    void scheduleRedeliveryShouldCreateScheduledTaskForFailedRecord() {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("id", 900L);
        record.put("order_id", 55L);
        record.put("account_id", 8L);
        record.put("delivery_timing", "after_payment");
        when(jdbcTemplate.queryForMap(contains("FROM delivery_record"), eq(900L), eq(1L))).thenReturn(record);

        ScheduleRedeliveryRequest request = new ScheduleRedeliveryRequest();
        request.setCronExpression("0 0/15 * * * ?");

        service.scheduleRedelivery(1L, 900L, request);

        verify(jdbcTemplate).update(
                contains("INSERT INTO scheduled_task"),
                eq(1L),
                eq(8L),
                eq("redelivery"),
                argThat(taskName -> String.valueOf(taskName).contains("900")),
                eq("0 0/15 * * * ?"),
                argThat(configJson -> String.valueOf(configJson).contains("\"recordId\":900")),
                eq(1)
        );
    }
}
