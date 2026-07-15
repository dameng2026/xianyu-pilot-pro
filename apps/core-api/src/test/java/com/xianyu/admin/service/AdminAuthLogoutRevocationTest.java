package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AdminAuthLogoutRevocationTest {

    @Test
    void logoutImmediatelyRevokesPreviouslyIssuedAdminTokens() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        String sql = "UPDATE sys_admin_user SET security_version=security_version+1, updated_time=NOW() "
                + "WHERE id=? AND status=1 AND deleted=0";
        when(jdbcTemplate.update(sql, 9L)).thenReturn(1);
        AuthService service = service(jdbcTemplate);

        service.logout(9L);

        verify(jdbcTemplate).update(sql, 9L);
    }

    @Test
    void logoutRejectsMissingContextWithoutDatabaseWork() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);

        BizException error = assertThrows(BizException.class,
                () -> service(jdbcTemplate).logout(null));

        assertEquals(401, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    private AuthService service(JdbcTemplate jdbcTemplate) {
        return new AuthService(
                jdbcTemplate,
                mock(JwtUtil.class),
                mock(OperationAuditService.class),
                mock(Environment.class),
                false
        );
    }
}
