package com.xianyu.admin.controller;

import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AiProviderService;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.ImageGenerationService;
import com.xianyu.admin.service.ModelConfigService;
import com.xianyu.admin.service.OperationAuditService;
import com.xianyu.admin.service.OpportunityDraftService;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.FeatureSwitchService;
import com.xianyu.admin.service.TenantSupportService;
import com.xianyu.admin.service.XianyuAccountService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import org.springframework.web.bind.annotation.PostMapping;

class AutomationProxyTenantIsolationTest {

    @AfterEach
    void clearTenant() {
        TenantContext.clear();
    }

    @Test
    void conversationBridgePassesServerTenantInQueryAndInternalIdentityHeader() {
        AutomationClient client = mock(AutomationClient.class);
        AutomationProxyController controller = controller(client);
        TenantContext.setCurrentTenantId(42L);
        TenantContext.setCurrentUserId(7L);
        controller.bridgeConversations(Map.of(
                "xianyuAccountId", 99L,
                "tenantId", 999L,
                "limit", 20
        ));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> query = ArgumentCaptor.forClass(Map.class);
        verify(client).getInternalForData(
                eq("/api/msg/online/conversations"), query.capture(), org.mockito.ArgumentMatchers.isA(Long.class));
        assertEquals(42L, query.getValue().get("tenantId"));
        assertEquals(99L, query.getValue().get("xianyuAccountId"));
    }

    @Test
    void refreshStatusNeverReturnsAnotherTenantsAccounts() {
        AutomationClient client = mock(AutomationClient.class);
        AutomationProxyController controller = controller(client);
        TenantContext.setCurrentTenantId(42L);
        doReturn(Map.of(
                "running", true,
                "accountsCount", 2,
                "accounts", java.util.List.of(
                        Map.of("accountId", 1L, "tenantId", 42L),
                        Map.of("accountId", 2L, "tenantId", 99L)
                )
        )).when(client).getInternalForData(
                eq("/api/account/refresh/status"), anyMap(), org.mockito.ArgumentMatchers.isA(Long.class));

        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) controller.accountRefreshStatus().getData();

        assertEquals(1, data.get("accountsCount"));
        assertEquals(1, ((java.util.List<?>) data.get("accounts")).size());
    }

    @Test
    void globalRagStatsAreFailClosedUntilDownstreamSupportsTenantIsolation() {
        AutomationClient client = mock(AutomationClient.class);
        AutomationProxyController controller = controller(client);

        assertEquals(503, controller.ragStats().getCode());
        verifyNoInteractions(client);
    }

    @Test
    void globalRefreshLifecycleIsNotExposedToTenantUsers() {
        boolean exposesLifecycle = java.util.Arrays.stream(AutomationProxyController.class.getDeclaredMethods())
                .map(method -> method.getAnnotation(PostMapping.class))
                .filter(java.util.Objects::nonNull)
                .flatMap(mapping -> java.util.Arrays.stream(mapping.value()))
                .anyMatch(path -> "/account/refresh/start".equals(path) || "/account/refresh/stop".equals(path));

        assertFalse(exposesLifecycle);
    }

    private AutomationProxyController controller(AutomationClient client) {
        return new AutomationProxyController(
                client,
                mock(JdbcTemplate.class),
                mock(OperationAuditService.class),
                mock(AiProviderService.class),
                mock(OpportunityDraftService.class),
                mock(ImageGenerationService.class),
                mock(ModelConfigService.class),
                mock(XianyuAccountService.class),
                mock(TenantSupportService.class),
                mock(OpenSourceContentService.class),
                mock(FeatureSwitchService.class)
        );
    }
}
