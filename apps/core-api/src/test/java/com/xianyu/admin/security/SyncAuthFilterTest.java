package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SyncAuthFilterTest {

    @Test
    void syncFailClosedWhenTokenIsMissingFromConfiguration() throws Exception {
        MockHttpServletResponse response = execute(new SyncAuthFilter(""), "any-token");
        assertEquals(503, response.getStatus());
    }

    @Test
    void syncFailClosedWhenTokenIsBlank() throws Exception {
        MockHttpServletResponse response = execute(new SyncAuthFilter("   "), "any-token");
        assertEquals(503, response.getStatus());
    }

    @Test
    void syncRejectWrongToken() throws Exception {
        MockHttpServletResponse response = execute(new SyncAuthFilter("sync-secret"), "wrong");
        assertEquals(403, response.getStatus());
    }

    @Test
    void syncRejectMissingTokenHeader() throws Exception {
        MockHttpServletResponse response = execute(new SyncAuthFilter("sync-secret"), null);
        assertEquals(403, response.getStatus());
    }

    @Test
    void syncAllowMatchingTokenViaXSyncTokenHeader() throws Exception {
        MockHttpServletResponse response = execute(new SyncAuthFilter("sync-secret"), "sync-secret");
        assertEquals(200, response.getStatus());
    }

    @Test
    void syncAllowMatchingTokenViaAuthorizationBearer() throws Exception {
        SyncAuthFilter filter = new SyncAuthFilter("sync-secret");
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/sync/receive");
        request.addHeader("Authorization", "Bearer sync-secret");
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        assertEquals(200, response.getStatus());
    }

    @Test
    void filterDoesNotProtectOtherPaths() throws Exception {
        SyncAuthFilter filter = new SyncAuthFilter("sync-secret");
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/ops/liveness");
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        assertEquals(200, response.getStatus());
    }

    @Test
    void filterProtectsPingEndpoint() throws Exception {
        SyncAuthFilter filter = new SyncAuthFilter("sync-secret");
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/sync/ping");
        request.addHeader("X-Sync-Token", "sync-secret");
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        assertEquals(200, response.getStatus());
    }

    private MockHttpServletResponse execute(SyncAuthFilter filter, String token) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/sync/receive");
        if (token != null) request.addHeader("X-Sync-Token", token);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
