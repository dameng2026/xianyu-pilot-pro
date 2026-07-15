package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class JwtAuthFilterExposureTest {
    private final JwtAuthFilter filter = new JwtAuthFilter(new JwtUtil(
            "unit-test-admin-jwt-secret-that-is-longer-than-thirty-two-characters",
            900,
            "xianyu-core-api",
            "xianyu-user-api"
    ), org.mockito.Mockito.mock(AuthSessionValidator.class));

    @Test
    void onlyTheCredentialLoginEndpointIsPublicUnderAdminAuth() {
        assertTrue(shouldSkip("POST", "/admin-api/auth/login"));
        assertFalse(shouldSkip("POST", "/admin-api/auth/xianyu/qrcode/generate"));
        assertFalse(shouldSkip("POST", "/admin-api/auth/xianyu/qrcode/poll"));
        assertFalse(shouldSkip("GET", "/admin-api/auth/anything-else"));
    }

    private boolean shouldSkip(String method, String uri) {
        MockHttpServletRequest request = new MockHttpServletRequest(method, uri);
        request.setRequestURI(uri);
        return filter.shouldNotFilter(request);
    }
}
