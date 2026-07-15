package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiProviderServiceTruthfulnessTest {

    @AfterEach
    void clearContexts() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void unconfiguredProviderReturnsServiceUnavailableInsteadOfErrorMap() {
        AiBillingService billing = mock(AiBillingService.class);
        ModelConfigService config = mock(ModelConfigService.class);
        when(config.isGeneralTextConfigured()).thenReturn(false);
        AiProviderService service = new AiProviderService(billing, config);

        BizException error = assertThrows(BizException.class,
                () -> service.generateText("rewrite", "system", "user request", 0.2D, false));

        assertEquals(503, error.getCode());
    }

    @Test
    void billableCallChecksBillingBeforeContactingProvider() {
        AiBillingService billing = mock(AiBillingService.class);
        ModelConfigService config = mock(ModelConfigService.class);
        when(config.isGeneralTextConfigured()).thenReturn(true);
        when(config.getGeneralConfig()).thenReturn(Map.of());
        when(billing.precheck(any())).thenThrow(new BizException(402, "余额不足"));
        UserContext.set(7L, "user", 3L);
        TenantContext.setCurrentTenantId(3L);
        AiProviderService service = new AiProviderService(billing, config);

        BizException error = assertThrows(BizException.class,
                () -> service.generateText("rewrite", "system", "user request", 0.2D, true));

        assertEquals(402, error.getCode());
        verify(billing).precheck(any());
    }

    @Test
    void billableProviderCallsAreNeverRetriedAfterAmbiguousTransportFailure() {
        assertEquals(1, AiProviderService.maxProviderAttempts(true));
        assertEquals(3, AiProviderService.maxProviderAttempts(false));
    }
}
