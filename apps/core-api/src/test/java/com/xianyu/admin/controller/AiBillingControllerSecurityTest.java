package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.AiBillingService;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AiBillingControllerSecurityTest {

    @Test
    void internalChargeFailsClosedWhenInternalTokenIsNotConfigured() {
        AiBillingService service = mock(AiBillingService.class);
        AiBillingController controller = new AiBillingController(service);
        ReflectionTestUtils.setField(controller, "internalToken", "");

        BizException error = assertThrows(BizException.class,
                () -> controller.internalCharge(Map.of("tenantId", 1), new MockHttpServletRequest()));

        assertEquals(503, error.getCode());
        verifyNoInteractions(service);
    }

    @Test
    void internalChargeRejectsWrongToken() {
        AiBillingService service = mock(AiBillingService.class);
        AiBillingController controller = new AiBillingController(service);
        ReflectionTestUtils.setField(controller, "internalToken", "a-strong-internal-token-value");
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-Internal-Token", "wrong-token");

        BizException error = assertThrows(BizException.class,
                () -> controller.internalCharge(Map.of("tenantId", 1), request));

        assertEquals(403, error.getCode());
        verifyNoInteractions(service);
    }

    @Test
    void internalChargeAcceptsMatchingToken() {
        AiBillingService service = mock(AiBillingService.class);
        AiBillingController controller = new AiBillingController(service);
        ReflectionTestUtils.setField(controller, "internalToken", "a-strong-internal-token-value");
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-Internal-Token", "a-strong-internal-token-value");
        Map<String, Object> usage = Map.of("tenantId", 1L, "chargeTokens", 5L);
        when(service.charge(usage)).thenReturn(Map.of("charged", true));

        assertEquals(Boolean.TRUE, controller.internalCharge(usage, request).getData().get("charged"));
        verify(service).charge(usage);
    }
}
