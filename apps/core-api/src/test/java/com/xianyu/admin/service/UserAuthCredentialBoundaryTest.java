package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.Environment;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class UserAuthCredentialBoundaryTest {

    @Test
    void nullPasswordHashCannotBeAuthenticatedWithLiteralNullPassword() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        JwtUtil jwtUtil = mock(JwtUtil.class);
        StringRedisTemplate redis = redisWithWritableCounters();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 3L);
        row.put("username", "broken-user");
        row.put("password_hash", null);
        row.put("status", 1);
        row.put("tenant_id", 7L);
        when(jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE username=? AND deleted=0",
                "broken-user"
        )).thenReturn(List.of(row));
        UserAuthService service = service(jdbcTemplate, jwtUtil, redis);

        BizException error = assertThrows(BizException.class,
                () -> service.login("broken-user", "null", "203.0.113.8"));

        assertEquals(401, error.getCode());
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void successfulLoginDoesNotResetTheIpWideAttackBudget() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        JwtUtil jwtUtil = mock(JwtUtil.class);
        StringRedisTemplate redis = redisWithWritableCounters();
        String hash = new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder()
                .encode("correct-password");
        when(jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE username=? AND deleted=0",
                "alice"
        )).thenReturn(List.of(Map.of(
                "id", 8L,
                "username", "alice",
                "password_hash", hash,
                "status", 1,
                "tenant_id", 7L,
                "security_version", 1L
        )));
        when(jwtUtil.createUserToken(8L, "alice", 7L, 1L)).thenReturn("token");
        UserAuthService service = service(jdbcTemplate, jwtUtil, redis);

        service.login("alice", "correct-password", "203.0.113.8");

        verify(redis).delete(org.mockito.ArgumentMatchers.<String>argThat(
                key -> key.startsWith("xya:login:fail:account:")));
        verify(redis, never()).delete(org.mockito.ArgumentMatchers.<String>argThat(
                key -> key.startsWith("xya:login:fail:ip:")));
    }

    @Test
    void unboundedCredentialsAreRejectedBeforeRedisOrDatabaseWork() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        JwtUtil jwtUtil = mock(JwtUtil.class);
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        UserAuthService service = service(jdbcTemplate, jwtUtil, redis);

        BizException error = assertThrows(BizException.class,
                () -> service.login("a".repeat(129), "password", "203.0.113.8"));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbcTemplate, jwtUtil, redis);
    }

    @SuppressWarnings("unchecked")
    private StringRedisTemplate redisWithWritableCounters() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        when(values.get(anyString())).thenReturn(null);
        when(values.increment(anyString())).thenReturn(1L);
        when(redis.expire(anyString(), any(Duration.class))).thenReturn(true);
        return redis;
    }

    private UserAuthService service(JdbcTemplate jdbcTemplate, JwtUtil jwtUtil,
                                    StringRedisTemplate redis) {
        return new UserAuthService(
                jdbcTemplate,
                jwtUtil,
                mock(Environment.class),
                redis,
                mock(UserProfileService.class),
                mock(UserAuthCapabilityService.class),
                mock(EmailSenderService.class),
                false
        );
    }
}
