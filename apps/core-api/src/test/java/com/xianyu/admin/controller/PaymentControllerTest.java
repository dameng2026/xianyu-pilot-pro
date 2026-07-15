package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.PaymentService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PaymentControllerTest {

    @Mock
    private PaymentService paymentService;

    @AfterEach
    void tearDown() {
        UserContext.clear();
        TenantContext.clear();
        AdminContext.clear();
    }

    @Test
    void userPaymentEndpointsRequireUserAndTenantContext() {
        PaymentController controller = new PaymentController(paymentService);

        BizException missing = assertThrows(BizException.class, controller::enabledMethods);

        UserContext.set(7L, "user", 2L);
        TenantContext.setCurrentUserId(7L);
        TenantContext.setCurrentTenantId(3L);
        BizException mismatchedTenant = assertThrows(BizException.class, controller::tokenPlans);

        assertEquals(401, missing.getCode());
        assertEquals(401, mismatchedTenant.getCode());
        verifyNoInteractions(paymentService);
    }

    @Test
    void noEnabledPaymentMethodIsExplicitlyUnavailable() {
        setUserContext();
        when(paymentService.enabledMethods()).thenReturn(List.of());
        PaymentController controller = new PaymentController(paymentService);

        BizException error = assertThrows(BizException.class, controller::enabledMethods);

        assertEquals(503, error.getCode());
    }

    @Test
    void paymentDependencyFailureIsSafe503() {
        setUserContext();
        when(paymentService.tokenPlans()).thenThrow(new RuntimeException("jdbc password=top-secret"));
        PaymentController controller = new PaymentController(paymentService);

        BizException error = assertThrows(BizException.class, controller::tokenPlans);

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("top-secret"));
    }

    @Test
    void mockPayIsBlockedAtControllerWhenSandboxIsDisabled() {
        setUserContext();
        PaymentController controller = new PaymentController(paymentService);

        BizException error = assertThrows(BizException.class,
                () -> controller.mockPayOrder("PAY123"));

        assertEquals(403, error.getCode());
        verify(paymentService, never()).mockPayUserOrder(anyString());
    }

    @Test
    void mockPayDelegatesOnlyWhenSandboxIsEnabled() {
        setUserContext();
        when(paymentService.mockPayUserOrder("PAY123")).thenReturn(Map.of("orderNo", "PAY123"));
        PaymentController controller = new PaymentController(paymentService);
        ReflectionTestUtils.setField(controller, "sandboxModeEnabled", true);

        Result<Map<String, Object>> result = controller.mockPayOrder("PAY123");

        assertEquals(200, result.getCode());
        assertEquals("PAY123", result.getData().get("orderNo"));
    }

    @Test
    void adminConfigReadRequiresSuperAdministrator() {
        PaymentController controller = new PaymentController(paymentService);

        BizException unauthenticated = assertThrows(BizException.class, controller::configs);
        AdminContext.set(9L, "operator", "R_ADMIN");
        BizException forbidden = assertThrows(BizException.class, controller::configs);

        assertEquals(401, unauthenticated.getCode());
        assertEquals(403, forbidden.getCode());
        verifyNoInteractions(paymentService);
    }

    @Test
    void tenantAdministratorCannotReadCrossTenantPaymentOrders() {
        AdminContext.set(9L, "operator", "R_ADMIN");
        PaymentController controller = new PaymentController(paymentService);

        BizException forbidden = assertThrows(BizException.class,
                () -> controller.orderPage(1, 20, null, null, null));

        assertEquals(403, forbidden.getCode());
        verifyNoInteractions(paymentService);
    }

    @Test
    void callbackSuccessUsesHttp200AndPlainProviderAcknowledgement() {
        when(paymentService.handleCallback(eq("alipay"), anyMap(), anyString()))
                .thenReturn(Map.of("status", 1));
        PaymentController controller = new PaymentController(paymentService);

        Object raw = controller.callback("alipay", Map.of("orderNo", "PAY123"), null);

        ResponseEntity<?> response = assertInstanceOf(ResponseEntity.class, raw);
        assertEquals(200, response.getStatusCode().value());
        assertEquals("success", response.getBody());
    }

    @Test
    void callbackBusinessFailureUsesRealHttpStatusWithoutLeakingMessage() {
        when(paymentService.handleCallback(eq("alipay"), anyMap(), anyString()))
                .thenThrow(new BizException(400, "签名原文 secret=abc"));
        PaymentController controller = new PaymentController(paymentService);

        Object raw = controller.callback("alipay", Map.of("orderNo", "PAY123"), null);

        ResponseEntity<?> response = assertInstanceOf(ResponseEntity.class, raw);
        assertEquals(400, response.getStatusCode().value());
        assertEquals("fail", response.getBody());
        assertFalse(String.valueOf(response.getBody()).contains("secret"));
    }

    @Test
    void callbackUnexpectedFailureUsesSafeHttp503() {
        when(paymentService.handleCallback(eq("wechat"), anyMap(), anyString()))
                .thenThrow(new RuntimeException("private_key and jdbc password"));
        PaymentController controller = new PaymentController(paymentService);

        Object raw = controller.callbackForm("wechat", Map.of("orderNo", "PAY123"));

        ResponseEntity<?> response = assertInstanceOf(ResponseEntity.class, raw);
        assertEquals(503, response.getStatusCode().value());
        assertEquals("fail", response.getBody());
    }

    @Test
    void unsupportedCallbackChannelIsBadRequestWithoutCallingService() {
        PaymentController controller = new PaymentController(paymentService);

        Object raw = controller.callbackGet("unknown", Map.of("orderNo", "PAY123"));

        ResponseEntity<?> response = assertInstanceOf(ResponseEntity.class, raw);
        assertEquals(400, response.getStatusCode().value());
        assertEquals("fail", response.getBody());
        verifyNoInteractions(paymentService);
    }

    private void setUserContext() {
        UserContext.set(7L, "user", 2L);
        TenantContext.setCurrentUserId(7L);
        TenantContext.setCurrentTenantId(2L);
    }
}
