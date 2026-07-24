package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.Environment;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;

class VerificationDeliveryAvailabilityTest {

    private NotificationConfigService mockConfigService(boolean emailConfigured) {
        NotificationConfigService svc = mock(NotificationConfigService.class);
        when(svc.isEmailConfigured()).thenReturn(emailConfigured);
        return svc;
    }

    private UserAuthService buildProdUserService(Environment environment, JdbcTemplate jdbcTemplate,
                                                 StringRedisTemplate redisTemplate,
                                                 UserAuthCapabilityService capabilityService) {
        return new UserAuthService(
                jdbcTemplate, mock(JwtUtil.class), environment, redisTemplate,
                mock(UserProfileService.class), capabilityService,
                mock(EmailSenderService.class), mock(ApiCredentialService.class), false);
    }

    @Test
    void userEmailEndpointDoesNotClaimDeliveryOutsideLocalDevelopment() {
        Environment environment = mock(Environment.class);
        when(environment.getActiveProfiles()).thenReturn(new String[]{"prod"});
        UserAuthService service = buildProdUserService(environment, mock(JdbcTemplate.class),
                mock(StringRedisTemplate.class),
                new UserAuthCapabilityService(environment, mockConfigService(false)));

        BizException error = assertThrows(BizException.class,
                () -> service.sendEmailCode("test@example.com", "203.0.113.8"));

        assertEquals(503, error.getCode());
    }

    @Test
    void productionRegistrationIsRejectedBeforeDatabaseOrVerificationStateIsRead() {
        Environment environment = mock(Environment.class);
        when(environment.getActiveProfiles()).thenReturn(new String[]{"prod"});
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        UserAuthService service = buildProdUserService(environment, jdbcTemplate, redisTemplate,
                new UserAuthCapabilityService(environment, mockConfigService(false)));

        BizException error = assertThrows(BizException.class,
                () -> service.register("test@example.com", "Password123", "123456", null));

        assertEquals(503, error.getCode());
        verifyNoInteractions(jdbcTemplate, redisTemplate);
    }

    @Test
    void productionEmailLoginIsRejectedBeforeDatabaseOrVerificationStateIsRead() {
        Environment environment = mock(Environment.class);
        when(environment.getActiveProfiles()).thenReturn(new String[]{"prod"});
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        UserAuthService service = buildProdUserService(environment, jdbcTemplate, redisTemplate,
                new UserAuthCapabilityService(environment, mockConfigService(false)));

        BizException error = assertThrows(BizException.class,
                () -> service.loginByEmail("test@example.com", "123456"));

        assertEquals(503, error.getCode());
        verifyNoInteractions(jdbcTemplate, redisTemplate);
    }

    @Test
    void productionPasswordResetIsRejectedBeforeDatabaseOrVerificationStateIsRead() {
        Environment environment = mock(Environment.class);
        when(environment.getActiveProfiles()).thenReturn(new String[]{"prod"});
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        UserAuthService service = buildProdUserService(environment, jdbcTemplate, redisTemplate,
                new UserAuthCapabilityService(environment, mockConfigService(false)));

        BizException error = assertThrows(BizException.class,
                () -> service.resetPassword("test@example.com", "123456", "Password456"));

        assertEquals(503, error.getCode());
        verifyNoInteractions(jdbcTemplate, redisTemplate);
    }

    @Test
    void emailLoginCannotAutoCreateAccountWhenSelfRegistrationIsClosed() {
        Environment environment = mock(Environment.class);
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(values);
        when(values.get(anyString())).thenAnswer(invocation -> {
            String key = invocation.getArgument(0, String.class);
            return key.contains(":code:") ? "123456" : null;
        });
        UserAuthCapabilityService capabilityService = mock(UserAuthCapabilityService.class);
        UserAuthCapabilityService.Capability fakeCap = new UserAuthCapabilityService.Capability(true, false, "可用");
        UserAuthCapabilityService.Capabilities fakeCapabilities = new UserAuthCapabilityService.Capabilities(
                "1", "production-safe", true, "notice", "support",
                fakeCap, fakeCap, fakeCap, fakeCap, fakeCap);
        when(capabilityService.current()).thenReturn(fakeCapabilities);
        doThrow(new BizException(503, "自助注册未开放"))
                .when(capabilityService).requireSelfRegistration();
        UserAuthService service = new UserAuthService(
                jdbcTemplate, mock(JwtUtil.class), environment, redisTemplate,
                mock(UserProfileService.class), capabilityService,
                mock(EmailSenderService.class), mock(ApiCredentialService.class), false);

        BizException error = assertThrows(BizException.class,
                () -> service.loginByEmail("test@example.com", "123456"));

        assertEquals(503, error.getCode());
        verify(capabilityService).requireEmailVerification();
        verify(capabilityService).requireSelfRegistration();
        verify(jdbcTemplate, never()).update(anyString(), any(Object[].class));
    }
}
