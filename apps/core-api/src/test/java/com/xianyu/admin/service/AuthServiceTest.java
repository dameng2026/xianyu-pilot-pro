package com.xianyu.admin.service;

import com.xianyu.admin.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private JwtUtil jwtUtil;

    @Mock
    private OperationAuditService auditService;

    @Mock
    private Environment environment;

    @Test
    void loginDoesNotReturnAccessTokenAgainAsFakeRefreshToken() {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);
        when(jdbcTemplate.queryForList(
                "SELECT * FROM sys_admin_user WHERE username=? AND deleted=0 LIMIT 1",
                "admin"
        )).thenReturn(List.of(Map.of(
                "id", 1L,
                "username", "admin",
                "password_hash", encoder.encode("secure-password"),
                "roles", "R_ADMIN",
                "status", 1
        )));
        when(jwtUtil.createAdminToken(1L, "admin", "R_ADMIN", 1L)).thenReturn("access-token");

        Map<String, Object> result = service.login("admin", "secure-password");

        assertEquals("access-token", result.get("token"));
        assertFalse(result.containsKey("refreshToken"));
    }

    @Test
    void userInfoDoesNotGrantMutationButtonsToReadOnlyRole() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);
        when(jdbcTemplate.queryForMap("SELECT * FROM sys_admin_user WHERE id=?", 7L))
                .thenReturn(Map.of(
                        "id", 7L,
                        "username", "auditor",
                        "roles", "R_VIEWER",
                        "email", "auditor@example.com"
                ));

        Map<String, Object> result = service.userInfo(7L);

        assertEquals(List.of("view", "export"), result.get("buttons"));
    }

    @Test
    void userInfoDoesNotAdvertiseWritesThatRAdminWillReceive403For() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);
        when(jdbcTemplate.queryForMap("SELECT * FROM sys_admin_user WHERE id=?", 8L))
                .thenReturn(Map.of(
                        "id", 8L,
                        "username", "operator-admin",
                        "roles", "R_ADMIN",
                        "email", "operator@example.com"
                ));

        Map<String, Object> result = service.userInfo(8L);

        assertEquals(List.of("view", "export"), result.get("buttons"));
    }

    @Test
    void disabledAdminDoesNotLeakWhetherTheAccountExists() {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);
        when(jdbcTemplate.queryForList(
                "SELECT * FROM sys_admin_user WHERE username=? AND deleted=0 LIMIT 1",
                "disabled-admin"
        )).thenReturn(List.of(Map.of(
                "id", 2L,
                "username", "disabled-admin",
                "password_hash", encoder.encode("correct-password"),
                "roles", "R_ADMIN",
                "status", 0
        )));

        com.xianyu.admin.common.BizException error = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.login("disabled-admin", "correct-password")
        );

        assertEquals(401, error.getCode());
        assertEquals("用户名或密码错误", error.getMessage());
    }

    @Test
    void nullPasswordHashCannotBeAuthenticatedWithLiteralNullPassword() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 3L);
        row.put("username", "broken-admin");
        row.put("password_hash", null);
        row.put("roles", "R_ADMIN");
        row.put("status", 1);
        when(jdbcTemplate.queryForList(
                "SELECT * FROM sys_admin_user WHERE username=? AND deleted=0 LIMIT 1",
                "broken-admin"
        )).thenReturn(List.of(row));

        com.xianyu.admin.common.BizException error = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.login("broken-admin", "null")
        );

        assertEquals(401, error.getCode());
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void loginRejectsUnboundedCredentialPayloadsBeforeDatabaseAccess() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);

        com.xianyu.admin.common.BizException error = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.login("a".repeat(129), "password")
        );

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void seedAdminShouldResetLegacyAdminPasswordTo123456() {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, true);
        when(environment.getActiveProfiles()).thenReturn(new String[0]);

        when(jdbcTemplate.queryForList(
                "SELECT id, username, password_hash, deleted FROM sys_admin_user WHERE username=? LIMIT 1",
                "admin"
        )).thenReturn(List.of(Map.of(
                "id", 1L,
                "username", "admin",
                "password_hash", encoder.encode("admin123456"),
                "deleted", 0
        )));

        service.seedAdmin();

        verify(jdbcTemplate).update(
                contains("UPDATE sys_admin_user SET username=?, password_hash=?"),
                eq("admin"),
                argThat((String hash) -> encoder.matches("123456", hash)),
                eq("超级管理员"),
                eq("admin@xianyu.local"),
                eq("R_SUPER,R_ADMIN"),
                eq(1L)
        );
    }

    @Test
    void seedAdminShouldCreateAdminWhenAdminRowIsMissing() {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, true);
        when(environment.getActiveProfiles()).thenReturn(new String[0]);

        when(jdbcTemplate.queryForList(
                "SELECT id, username, password_hash, deleted FROM sys_admin_user WHERE username=? LIMIT 1",
                "admin"
        )).thenReturn(List.of());

        service.seedAdmin();

        verify(jdbcTemplate).update(
                contains("INSERT INTO sys_admin_user(username,password_hash,nickname,email,roles,status,created_time,updated_time,deleted)"),
                eq("admin"),
                argThat((String hash) -> encoder.matches("123456", hash)),
                eq("超级管理员"),
                eq("admin@xianyu.local"),
                eq("R_SUPER,R_ADMIN")
        );
    }

    @Test
    void seedAdminShouldNotTouchAdminAccountsWhenSeedIsDisabled() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, false);

        service.seedAdmin();

        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void seedAdminShouldNotTouchAdminAccountsInProduction() {
        AuthService service = new AuthService(jdbcTemplate, jwtUtil, auditService, environment, true);
        when(environment.getActiveProfiles()).thenReturn(new String[]{"prod"});

        service.seedAdmin();

        verifyNoInteractions(jdbcTemplate);
    }
}
