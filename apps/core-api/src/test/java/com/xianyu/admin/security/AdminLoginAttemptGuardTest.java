package com.xianyu.admin.security;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AdminLoginAttemptGuardTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private AdminLoginAttemptGuard guard;

    @BeforeEach
    void setUp() {
        lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        guard = new AdminLoginAttemptGuard(redisTemplate);
    }

    @Test
    void blocksAnAccountAfterFiveFailures() {
        when(valueOperations.get(argThat((String key) -> key.startsWith("xya:admin-login:account:"))))
                .thenReturn("5");

        BizException error = assertThrows(BizException.class,
                () -> guard.checkAllowed("admin@example.com", "203.0.113.8"));

        assertEquals(429, error.getCode());
    }

    @Test
    void failureCounterUsesHashedKeysAndGetsATtl() {
        when(valueOperations.increment(any())).thenReturn(1L);
        when(redisTemplate.expire(anyString(), any(Duration.class))).thenReturn(true);

        guard.recordFailure("admin@example.com", "203.0.113.8");

        verify(valueOperations, never()).increment(argThat(key ->
                key.contains("admin@example.com") || key.contains("203.0.113.8")));
        verify(redisTemplate).expire(
                argThat(key -> key.startsWith("xya:admin-login:account:")),
                eq(Duration.ofMinutes(15))
        );
        verify(redisTemplate).expire(
                argThat(key -> key.startsWith("xya:admin-login:ip:")),
                eq(Duration.ofMinutes(15))
        );
    }

    @Test
    void successfulLoginClearsOnlyTheAccountCounter() {
        guard.recordSuccess("admin@example.com");

        verify(redisTemplate).delete(startsWith("xya:admin-login:account:"));
        verify(redisTemplate, never()).delete(startsWith("xya:admin-login:ip:"));
    }

    @Test
    void redisOutageFailsClosedInsteadOfDisablingBruteForceProtection() {
        when(valueOperations.get(any())).thenThrow(new IllegalStateException("redis down"));

        BizException error = assertThrows(BizException.class,
                () -> guard.checkAllowed("admin", "203.0.113.8"));

        assertEquals(503, error.getCode());
    }
}
