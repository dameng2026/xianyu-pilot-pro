package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.OpenSourceAdService;
import com.xianyu.admin.service.OpenSourceBridgeAuthService;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.TenantSupportService;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OpenSourceBridgePaymentControllerTest {

    @Mock private JdbcTemplate jdbcTemplate;
    @Mock private TenantSupportService tenantSupportService;
    @Mock private OpenSourceBridgeAuthService bridgeAuthService;
    @Mock private OpenSourceContentService contentService;
    @Mock private OpenSourceAdService adService;
    @Mock private HttpServletRequest request;

    @Test
    void bridgePaymentMethodsRequireSiteAuthenticationFirst() {
        when(bridgeAuthService.requireSiteContext(request))
                .thenThrow(new OpenSourceBridgeAuthService.BridgeAuthException(401, "桥接凭证无效"));
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.adPaymentMethods(request));

        assertEquals(401, error.getCode());
        verifyNoInteractions(adService);
    }

    @Test
    void noBridgePaymentMethodIsExplicitlyUnavailable() {
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site());
        when(adService.listEnabledPaymentMethods()).thenReturn(List.of());
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.adPaymentMethods(request));

        assertEquals(503, error.getCode());
    }

    @Test
    void bridgePaymentDependencyFailureIsSafe503() {
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site());
        when(adService.listEnabledPaymentMethods())
                .thenThrow(new RuntimeException("jdbc password=top-secret"));
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.adPaymentMethods(request));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("top-secret"));
    }

    @Test
    void invalidApplicationIdIsBadRequestAfterAuthentication() {
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site());
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.createAdPaymentOrder(0L, Map.of("paymentMethod", "alipay"), request));

        assertEquals(400, error.getCode());
        verify(adService, never()).createApplicationPaymentOrder(anyLong(), any(), any(), anyString());
    }

    @Test
    void bridgeMockPayIsBlockedWhenSandboxIsDisabled() {
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site());
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.mockPayAdPaymentOrder("PAY123", request));

        assertEquals(403, error.getCode());
        verify(adService, never()).mockPayApplicationPaymentOrder(anyString(), any());
    }

    @Test
    void bridgeMockPayDelegatesWithAuthenticatedSiteWhenSandboxEnabled() {
        OpenSourceBridgeAuthService.OpenSourceSiteContext site = site();
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site);
        when(adService.mockPayApplicationPaymentOrder("PAY123", site))
                .thenReturn(Map.of("orderNo", "PAY123"));
        OpenSourceBridgeController controller = controller();
        ReflectionTestUtils.setField(controller, "paymentSandboxEnabled", true);

        Result<Map<String, Object>> result = controller.mockPayAdPaymentOrder("PAY123", request);

        assertEquals(200, result.getCode());
        assertEquals("PAY123", result.getData().get("orderNo"));
    }

    @Test
    void blankBridgeOrderNumberIsBadRequestWithoutCallingAdService() {
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site());
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.adPaymentOrderDetail("  ", request));

        assertEquals(400, error.getCode());
        verify(adService, never()).getApplicationPaymentOrder(anyString(), any());
    }

    @Test
    void missingBridgeDependencyResultIs503InsteadOfNullSuccess() {
        OpenSourceBridgeAuthService.OpenSourceSiteContext site = site();
        when(bridgeAuthService.requireSiteContext(request)).thenReturn(site);
        when(adService.getApplicationPaymentOrder("PAY123", site)).thenReturn(null);
        OpenSourceBridgeController controller = controller();

        BizException error = assertThrows(BizException.class,
                () -> controller.adPaymentOrderDetail("PAY123", request));

        assertEquals(503, error.getCode());
    }

    private OpenSourceBridgeController controller() {
        return new OpenSourceBridgeController(
                jdbcTemplate,
                tenantSupportService,
                bridgeAuthService,
                contentService,
                adService
        );
    }

    private OpenSourceBridgeAuthService.OpenSourceSiteContext site() {
        return new OpenSourceBridgeAuthService.OpenSourceSiteContext(
                "open-source", "开源版", "https://site.test", "https://admin.test", "osi_test_instance_token");
    }
}
