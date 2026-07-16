package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.dto.XianyuTradeOrderVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.OrderDeliveryCommandService;
import com.xianyu.admin.service.XianyuTradeOrderService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuTradeOrderControllerTest {

    @Mock
    private XianyuTradeOrderService orderService;

    @Mock
    private OrderDeliveryCommandService orderDeliveryCommandService;

    private XianyuTradeOrderController controller;

    @BeforeEach
    void setUp() {
        controller = new XianyuTradeOrderController(orderService, orderDeliveryCommandService);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void manualDeliveryShouldDelegateToCommandService() {
        OrderManualDeliveryRequest request = new OrderManualDeliveryRequest();
        request.setDeliveryMode("text");
        request.setDeliveryTiming("after_payment");
        request.setDeliveryContent("download-link");
        request.setQuantityRequested(2);

        Result<Void> result = controller.manualDelivery(55L, request);

        verify(orderDeliveryCommandService).manualDelivery(1L, 55L, request);
        assertEquals(200, result.getCode());
    }

    @Test
    void syncOneShouldDelegateToCommandService() {
        Result<java.util.Map<String, Object>> result = controller.syncOne(55L);

        verify(orderDeliveryCommandService).syncOrder(1L, 55L);
        assertEquals(200, result.getCode());
    }

    @Test
    void pageShouldRejectLegacyGetSideEffectInsteadOfReturningPossiblyStaleSuccess() {
        BizException error = assertThrows(BizException.class,
                () -> controller.page(8L, null, null, null, 1, 20, true));

        assertEquals(410, error.getCode());
        verify(orderDeliveryCommandService, never()).syncOrders(eq(1L), any(OrderSyncRequest.class));
        verify(orderService, never()).page(1L, 8L, null, null, null, 1, 20);
    }

    @Test
    void pageShouldListWithoutTriggeringSyncWhenSyncIsFalse() {
        when(orderService.page(1L, null, null, null, null, 1, 20))
                .thenReturn(new PageResult<XianyuTradeOrderVO>(java.util.List.of(), 1, 20, 0));

        Result<PageResult<XianyuTradeOrderVO>> result = controller.page(null, null, null, null, 1, 20, false);

        verify(orderDeliveryCommandService, never()).syncOrders(eq(1L), any(OrderSyncRequest.class));
        verify(orderService).page(1L, null, null, null, null, 1, 20);
        assertEquals(200, result.getCode());
    }
}
