package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class UserProfilePasswordSecurityTest {
    private JdbcTemplate jdbcTemplate;
    private UserSecurityAuditService securityAuditService;
    private UserProfileService service;

    @BeforeEach
    void setUp() {
        jdbcTemplate = mock(JdbcTemplate.class);
        securityAuditService = mock(UserSecurityAuditService.class);
        service = new UserProfileService(
                jdbcTemplate, mock(UserAuthCapabilityService.class), securityAuditService);
        UserContext.set(7L, "alice", 11L);
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
    }

    @Test
    void nullStoredHashCannotBeVerifiedWithLiteralNullPassword() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 7L);
        row.put("password_hash", null);
        when(jdbcTemplate.queryForMap(
                "SELECT id, password_hash FROM sys_user WHERE id=? AND deleted=0",
                7L
        )).thenReturn(row);

        BizException error = assertThrows(BizException.class, () ->
                service.changePassword("null", "SecurePass123", "203.0.113.8", "test"));

        assertEquals(400, error.getCode());
        verify(securityAuditService).recordRejectedRequired(
                11L, 7L, "change_password", "修改密码", "password", "当前密码错误",
                "203.0.113.8", "test");
    }

    @Test
    void rejectsPasswordsThatWouldExceedBcryptsByteBoundary() {
        String tooManyBytes = "A1" + "密".repeat(30);

        BizException error = assertThrows(BizException.class, () ->
                service.changePassword("old-password", tooManyBytes, "203.0.113.8", "test"));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void rejectsOverlongCurrentPasswordBeforeBcryptWork() {
        BizException error = assertThrows(BizException.class, () ->
                service.changePassword("x".repeat(257), "SecurePass123", "203.0.113.8", "test"));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }
}
