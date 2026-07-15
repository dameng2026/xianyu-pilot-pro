package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class UserAuthCapabilityServiceTest {

    private NotificationConfigService mockConfigService(boolean emailConfigured) {
        NotificationConfigService svc = mock(NotificationConfigService.class);
        when(svc.isEmailConfigured()).thenReturn(emailConfigured);
        return svc;
    }

    @Test
    void productionPublishesOnlyPasswordLoginAndFailsClosedForVerificationFlows() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(false));

        UserAuthCapabilityService.Capabilities capabilities = service.current();

        assertTrue(capabilities.failClosed());
        assertTrue(capabilities.passwordLogin().available());
        assertFalse(capabilities.emailVerification().available());
        assertFalse(capabilities.selfRegistration().available());
        assertFalse(capabilities.passwordReset().available());
        assertFalse(capabilities.profileVerification().available());
        assertFalse(capabilities.securityNotice().contains("验证码已发送"));
        assertTrue(capabilities.supportMessage().contains("管理员"));
    }

    @Test
    void localDevelopmentLabelsDebugVerificationCapabilitiesAsDevOnly() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("local");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(false));

        UserAuthCapabilityService.Capabilities capabilities = service.current();

        assertTrue(capabilities.emailVerification().available());
        assertTrue(capabilities.emailVerification().devOnly());
        assertTrue(capabilities.selfRegistration().available());
        assertTrue(capabilities.selfRegistration().devOnly());
        assertTrue(capabilities.passwordReset().available());
        assertTrue(capabilities.passwordReset().devOnly());
        assertTrue(capabilities.profileVerification().available());
        assertTrue(capabilities.profileVerification().devOnly());
        assertTrue(capabilities.securityNotice().contains("仅限本地开发"));
    }

    @Test
    void productionGuardRejectsSelfRegistrationWithSafeServiceUnavailable() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(false));

        BizException error = assertThrows(BizException.class, service::requireSelfRegistration);

        assertEquals(503, error.getCode());
        assertTrue(error.getMessage().contains("自助注册"));
        assertFalse(error.getMessage().contains("prod"));
    }

    @Test
    void productionProfileOverridesAccidentallyEnabledDevelopmentProfile() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod", "dev");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(false));

        UserAuthCapabilityService.Capabilities capabilities = service.current();

        assertFalse(capabilities.emailVerification().available());
        assertFalse(capabilities.selfRegistration().available());
        assertFalse(capabilities.passwordReset().available());
        assertFalse(capabilities.profileVerification().available());
    }

    @Test
    void anyMixedEnvironmentProfileKeepsDebugVerificationFailClosed() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("dev", "staging");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(false));

        UserAuthCapabilityService.Capabilities capabilities = service.current();

        assertEquals("production-safe", capabilities.mode());
        assertFalse(capabilities.emailVerification().available());
        assertFalse(capabilities.selfRegistration().available());
        assertFalse(capabilities.passwordReset().available());
        assertFalse(capabilities.profileVerification().available());
    }

    @Test
    void productionOpensEmailCapabilitiesWhenSmtpIsConfigured() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod");
        UserAuthCapabilityService service = new UserAuthCapabilityService(environment, mockConfigService(true));

        UserAuthCapabilityService.Capabilities capabilities = service.current();

        assertEquals("production-safe", capabilities.mode());
        assertTrue(capabilities.emailVerification().available());
        assertFalse(capabilities.emailVerification().devOnly());
        assertTrue(capabilities.selfRegistration().available());
        assertTrue(capabilities.passwordReset().available());
        assertTrue(capabilities.profileVerification().available());
    }
}
