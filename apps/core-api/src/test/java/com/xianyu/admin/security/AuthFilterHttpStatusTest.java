package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import jakarta.servlet.FilterChain;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AuthFilterHttpStatusTest {

    @Test
    void adminApiShouldReturnHttp401WhenBearerTokenIsMissing() throws Exception {
        JwtAuthFilter filter = new JwtAuthFilter(mock(JwtUtil.class), mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/admin-api/admin/dashboard/overview");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertEquals(401, response.getStatus());
        assertTrue(response.getContentAsString().contains("\"code\":401"));
    }

    @Test
    void userApiShouldReturnHttp401WhenBearerTokenIsMissing() throws Exception {
        UserJwtAuthFilter filter = new UserJwtAuthFilter(mock(JwtUtil.class), mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/xianyu/accounts");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertEquals(401, response.getStatus());
        assertTrue(response.getContentAsString().contains("\"code\":401"));
    }

    @Test
    void authenticationCapabilitiesArePublicAndDoNotInvokeJwtVerification() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/login/capabilities");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(200, response.getStatus());
        verify(chain).doFilter(request, response);
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void passwordResetCodeVerificationIsPublicForEnabledLocalDevelopmentFlow() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/login/verifyResetCode");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(200, response.getStatus());
        verify(chain).doFilter(request, response);
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void removedGlobalUserExistenceProbeIsNotAnonymous() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/login/checkUserExists");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain, jwtUtil);
    }

    @Test
    void contextPathCannotBypassUserAuthenticationFilter() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/tenant-app/api/xianyu/accounts");
        request.setContextPath("/tenant-app");
        request.setServletPath("/api/xianyu/accounts");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain, jwtUtil);
    }

    @Test
    void contextPathCannotBypassAdministratorAuthenticationFilter() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        JwtAuthFilter filter = new JwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest(
                "GET", "/tenant-app/admin-api/admin/dashboard/overview");
        request.setContextPath("/tenant-app");
        request.setServletPath("/admin-api/admin/dashboard/overview");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain, jwtUtil);
    }

    @Test
    void publicCapabilityEndpointRemainsAnonymousUnderContextPath() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/tenant-app/api/login/capabilities");
        request.setContextPath("/tenant-app");
        request.setServletPath("/api/login/capabilities");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(200, response.getStatus());
        verify(chain).doFilter(request, response);
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void userTokenCannotBeReusedAgainstAdminApi() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        when(jwtUtil.verify("user-token")).thenReturn(Map.of(
                "sub", "7", "userName", "buyer", "tenantId", "42", "tokenType", "user"));
        JwtAuthFilter filter = new JwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/admin-api/user/info");
        request.addHeader("Authorization", "Bearer user-token");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain);
    }

    @Test
    void adminTokenCannotBeReusedAgainstTenantUserApi() throws Exception {
        JwtUtil jwtUtil = mock(JwtUtil.class);
        when(jwtUtil.verify("admin-token")).thenReturn(Map.of(
                "sub", "1", "userName", "admin", "roles", "R_SUPER", "tokenType", "admin"));
        UserJwtAuthFilter filter = new UserJwtAuthFilter(jwtUtil, mock(AuthSessionValidator.class));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/xianyu/accounts");
        request.addHeader("Authorization", "Bearer admin-token");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verifyNoInteractions(chain);
    }
}
