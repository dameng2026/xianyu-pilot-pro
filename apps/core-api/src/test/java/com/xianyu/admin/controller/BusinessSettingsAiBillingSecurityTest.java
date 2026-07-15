package com.xianyu.admin.controller;

import com.xianyu.admin.service.AiProviderService;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.BusinessSettingsService;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class BusinessSettingsAiBillingSecurityTest {

    @Test
    void ordinaryUserAiCustomerServiceProbeUsesBillableProviderPath() {
        BusinessSettingsService settings = mock(BusinessSettingsService.class);
        AiProviderService provider = mock(AiProviderService.class);
        when(settings.getConfig("ai-customer-service"))
                .thenReturn(Map.of("systemPrompt", "safe support assistant"));
        when(provider.isConfigured()).thenReturn(true);
        when(provider.generateText(
                eq("ai_customer_service_test"), eq("safe support assistant"),
                eq("hello"), eq(0.6D), eq(true)))
                .thenReturn(Map.of("ok", true, "content", "hi"));
        BusinessSettingsController controller = new BusinessSettingsController(
                settings, provider, mock(AutomationClient.class));

        controller.testAiReply(Map.of("message", "hello"));

        verify(provider).generateText(
                "ai_customer_service_test", "safe support assistant", "hello", 0.6D, true);
    }
}
