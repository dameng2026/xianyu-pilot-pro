package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.JwtUtil;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.Environment;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class UserAuthLogoutRevocationTest {

    @AfterEach
    void clearContexts() {
        UserContext.clear();
        TenantContext.clear();
    }

    @Test
    void logoutImmediatelyRevokesAllPreviouslyIssuedUserTokens() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.update(
                "UPDATE sys_user SET security_version=security_version+1, "
                        + "last_security_update_time=NOW(), updated_time=NOW() "
                        + "WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                7L,
                11L
        )).thenReturn(1);
        UserAuthService service = service(jdbcTemplate);
        UserContext.set(7L, "alice", 11L);
        TenantContext.setCurrentUserId(7L);
        TenantContext.setCurrentTenantId(11L);

        service.logout();

        verify(jdbcTemplate).update(
                "UPDATE sys_user SET security_version=security_version+1, "
                        + "last_security_update_time=NOW(), updated_time=NOW() "
                        + "WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                7L,
                11L
        );
    }

    @Test
    void logoutRejectsMismatchedTenantContextWithoutTouchingDatabase() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        UserAuthService service = service(jdbcTemplate);
        UserContext.set(7L, "alice", 11L);
        TenantContext.setCurrentUserId(7L);
        TenantContext.setCurrentTenantId(12L);

        BizException error = assertThrows(BizException.class, service::logout);

        assertEquals(401, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void logoutFailsClosedWhenAuthoritativeUserRowCannotBeUpdated() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.update(
                "UPDATE sys_user SET security_version=security_version+1, "
                        + "last_security_update_time=NOW(), updated_time=NOW() "
                        + "WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                7L,
                11L
        )).thenReturn(0);
        UserAuthService service = service(jdbcTemplate);
        UserContext.set(7L, "alice", 11L);
        TenantContext.setCurrentUserId(7L);
        TenantContext.setCurrentTenantId(11L);

        BizException error = assertThrows(BizException.class, service::logout);

        assertEquals(401, error.getCode());
    }

    private UserAuthService service(JdbcTemplate jdbcTemplate) {
        Environment environment = mock(Environment.class);
        return new UserAuthService(
                jdbcTemplate,
                mock(JwtUtil.class),
                environment,
                mock(StringRedisTemplate.class),
                mock(UserProfileService.class),
                mock(UserAuthCapabilityService.class),
                mock(EmailSenderService.class),
                mock(ApiCredentialService.class),
                false
        );
    }
}
