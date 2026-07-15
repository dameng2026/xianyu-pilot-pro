package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ClientIpResolverTest {

    @Test
    void publicDirectClientCannotSpoofForwardedHeaders() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("8.8.8.8");
        request.addHeader("X-Forwarded-For", "1.2.3.4");

        assertEquals("8.8.8.8", ClientIpResolver.resolve(request));
    }

    @Test
    void trustedReverseProxyUsesRightmostUntrustedForwardedAddress() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("127.0.0.1");
        request.addHeader("X-Forwarded-For", "1.2.3.4, 9.9.9.9, 10.0.0.8");

        assertEquals("9.9.9.9", ClientIpResolver.resolve(request));
    }

    @Test
    void malformedForwardedValueFallsBackToSocketPeer() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("127.0.0.1");
        request.addHeader("X-Forwarded-For", "not-an-ip");

        assertEquals("127.0.0.1", ClientIpResolver.resolve(request));
    }
}
