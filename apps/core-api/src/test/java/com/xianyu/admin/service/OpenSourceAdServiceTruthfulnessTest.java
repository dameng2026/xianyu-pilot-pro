package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class OpenSourceAdServiceTruthfulnessTest {

    @Test
    void missingPlanConfigurationDoesNotCreateHardCodedCommercialPrices() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        OpenSourceAdService service = service(jdbc);

        assertTrue(service.listEnabledAdPlans().isEmpty());
    }

    @Test
    void corruptedPlanConfigurationIsUnavailableInsteadOfFallingBackToDefaults() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForObject(anyString(), eq(String.class), any(Object[].class)))
                .thenReturn("{not-json");
        OpenSourceAdService service = service(jdbc);

        BizException error = assertThrows(BizException.class, service::listEnabledAdPlans);

        assertEquals(503, error.getCode());
    }

    @Test
    void applicationRejectsUnsafeLandingUrlBeforeWriting() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForObject(anyString(), eq(String.class), any(Object[].class)))
                .thenReturn("[{\"id\":1,\"code\":\"sidebar-plan\",\"positionType\":\"sidebar_text\",\"title\":\"Plan\",\"priceCent\":100,\"enabled\":true}]");
        OpenSourceAdService service = service(jdbc);
        OpenSourceBridgeAuthService.OpenSourceSiteContext site =
                new OpenSourceBridgeAuthService.OpenSourceSiteContext(
                        "open-source", "Open Source", "https://site.example", "https://admin.example", "osi_test_instance_token");

        BizException error = assertThrows(BizException.class, () -> service.createApplication(site, Map.of(
                "positionType", "sidebar_text",
                "planCode", "sidebar-plan",
                "contact", "contact@example.com",
                "companyName", "Example Ltd",
                "title", "Ad",
                "landingUrl", "http://127.0.0.1/internal"
        )));

        assertEquals(400, error.getCode());
    }

    private OpenSourceAdService service(JdbcTemplate jdbc) {
        TenantSupportService tenantSupport = mock(TenantSupportService.class);
        when(tenantSupport.resolveCurrentOrDefaultTenantId()).thenReturn(1L);
        return new OpenSourceAdService(
                jdbc,
                tenantSupport,
                mock(OpenSourceContentService.class),
                mock(PaymentService.class)
        );
    }
}
