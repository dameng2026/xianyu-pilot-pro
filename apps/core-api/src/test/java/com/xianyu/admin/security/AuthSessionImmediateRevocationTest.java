package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import jakarta.servlet.FilterChain;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AuthSessionImmediateRevocationTest {
    private static final String SECRET = "immediate-revocation-test-secret-longer-than-thirty-two-characters";
    private static final String USER_SQL =
            "SELECT username, tenant_id, status, deleted, security_version FROM sys_user WHERE id=? LIMIT 1";
    private static final String ADMIN_SQL =
            "SELECT username, roles, status, deleted, security_version FROM sys_admin_user WHERE id=? LIMIT 1";

    private final JwtUtil jwtUtil = new JwtUtil(
            SECRET, 900, "xianyu-core-api", "xianyu-user-api");

    @Test
    void passwordVersionChangeImmediatelyRejectsPreviouslyIssuedUserToken() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.queryForList(USER_SQL, 7L)).thenReturn(List.of(Map.of(
                "username", "buyer",
                "tenant_id", 42L,
                "status", 1,
                "deleted", 0,
                "security_version", 6L
        )));
        UserJwtAuthFilter filter = new UserJwtAuthFilter(
                jwtUtil, new AuthSessionValidator(jdbcTemplate));
        MockHttpServletRequest request = protectedRequest(
                "/api/xianyu/accounts", jwtUtil.createUserToken(7L, "buyer", 42L, 5L));
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain);
    }

    @Test
    void administratorRoleChangeImmediatelyRejectsPreviouslyIssuedToken() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.queryForList(ADMIN_SQL, 1L)).thenReturn(List.of(Map.of(
                "username", "admin",
                "roles", "R_VIEWER",
                "status", 1,
                "deleted", 0,
                "security_version", 3L
        )));
        JwtAuthFilter filter = new JwtAuthFilter(
                jwtUtil, new AuthSessionValidator(jdbcTemplate));
        MockHttpServletRequest request = protectedRequest(
                "/admin-api/admin/dashboard/overview",
                jwtUtil.createAdminToken(1L, "admin", "R_SUPER,R_ADMIN", 3L));
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain);
    }

    @Test
    void matchingTenantAndSecurityVersionAllowsUserRequest() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.queryForList(USER_SQL, 7L)).thenReturn(List.of(Map.of(
                "username", "buyer",
                "tenant_id", 42L,
                "status", 1,
                "deleted", 0,
                "security_version", 5L
        )));
        UserJwtAuthFilter filter = new UserJwtAuthFilter(
                jwtUtil, new AuthSessionValidator(jdbcTemplate));
        MockHttpServletRequest request = protectedRequest(
                "/api/xianyu/accounts", jwtUtil.createUserToken(7L, "buyer", 42L, 5L));
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(200, response.getStatus());
        verify(chain).doFilter(request, response);
    }

    @Test
    void authenticationStateDatabaseFailureIsExplicit503AndFailsClosed() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.queryForList(USER_SQL, 7L))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));
        UserJwtAuthFilter filter = new UserJwtAuthFilter(
                jwtUtil, new AuthSessionValidator(jdbcTemplate));
        MockHttpServletRequest request = protectedRequest(
                "/api/xianyu/accounts", jwtUtil.createUserToken(7L, "buyer", 42L, 5L));
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(503, response.getStatus());
        assertEquals(true, response.getContentAsString().contains("\"code\":503"));
        verifyNoInteractions(chain);
    }

    private MockHttpServletRequest protectedRequest(String path, String token) {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", path);
        request.addHeader("Authorization", "Bearer " + token);
        return request;
    }
}
