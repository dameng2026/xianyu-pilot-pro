package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SecurityResponseHeadersFilterTest {

    @Test
    void apiResponsesDisableSniffingAndFraming() throws Exception {
        MockHttpServletResponse response = execute("/api/health");

        assertEquals("nosniff", response.getHeader("X-Content-Type-Options"));
        assertEquals("DENY", response.getHeader("X-Frame-Options"));
        assertEquals("no-referrer", response.getHeader("Referrer-Policy"));
        assertEquals("no-store, no-cache, must-revalidate, max-age=0",
                response.getHeader("Cache-Control"));
        assertEquals("no-cache", response.getHeader("Pragma"));
        assertEquals("0", response.getHeader("Expires"));
    }

    @Test
    void publicUploadsAreSandboxedIfOpenedAsDocuments() throws Exception {
        MockHttpServletResponse response = execute("/uploads/logos/20260710/logo.png");

        assertEquals("default-src 'none'; frame-ancestors 'none'; sandbox",
                response.getHeader("Content-Security-Policy"));
    }

    @Test
    void publicImageProxyCanApplyItsOwnCachePolicy() throws Exception {
        MockHttpServletResponse response = execute("/api/proxy-image/opaque-token");

        assertEquals(null, response.getHeader("Cache-Control"));
        assertEquals("default-src 'none'; frame-ancestors 'none'; sandbox",
                response.getHeader("Content-Security-Policy"));
    }

    private MockHttpServletResponse execute(String path) throws Exception {
        SecurityResponseHeadersFilter filter = new SecurityResponseHeadersFilter();
        MockHttpServletRequest request = new MockHttpServletRequest("GET", path);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
