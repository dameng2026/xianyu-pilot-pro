package com.xianyu.admin.security;

import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ClientErrorIngressFilterTest {

    @Test
    void rejectsPayloadBeforeControllerWhenBodyExceedsLimit() throws Exception {
        ClientErrorIngressFilter filter = filter(5, 1_000, 32);
        MockHttpServletRequest request = request("10.0.0.8", "{\"events\":[{\"message\":\"this body is too large\"}]}");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertEquals(413, response.getStatus());
        assertTrue(response.getContentAsString().contains("\"code\":413"));
    }

    @Test
    void rateLimitsRepeatedAnonymousReportsByRemoteAddress() throws Exception {
        ClientErrorIngressFilter filter = filter(2, 60_000, 1_024);

        assertEquals(200, execute(filter, request("203.0.113.8", "{}")));
        assertEquals(200, execute(filter, request("203.0.113.8", "{}")));
        assertEquals(429, execute(filter, request("203.0.113.8", "{}")));
        assertEquals(200, execute(filter, request("203.0.113.9", "{}")));
    }

    @Test
    void forwardsTheBoundedBodyToTheControllerChain() throws Exception {
        ClientErrorIngressFilter filter = filter(5, 60_000, 1_024);
        MockHttpServletRequest request = request("203.0.113.8", "{\"events\":[]}");
        MockHttpServletResponse response = new MockHttpServletResponse();
        BodyReadingChain chain = new BodyReadingChain();

        filter.doFilter(request, response, chain);

        assertEquals("{\"events\":[]}", chain.body);
        assertEquals(200, response.getStatus());
    }

    @Test
    void ignoresUnrelatedApiRequests() throws Exception {
        ClientErrorIngressFilter filter = filter(1, 60_000, 1);
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/login/login");
        request.setContent("a much larger login request".getBytes(StandardCharsets.UTF_8));

        assertEquals(200, execute(filter, request));
    }

    private ClientErrorIngressFilter filter(int requests, long windowMs, int maxBytes) {
        AtomicLong now = new AtomicLong(1_000L);
        return new ClientErrorIngressFilter(requests, windowMs, maxBytes, now::get);
    }

    private MockHttpServletRequest request(String remoteAddress, String body) {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/client-errors");
        request.setRemoteAddr(remoteAddress);
        request.setContentType("application/json");
        request.setContent(body.getBytes(StandardCharsets.UTF_8));
        return request;
    }

    private int execute(ClientErrorIngressFilter filter, MockHttpServletRequest request) throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response.getStatus();
    }

    private static final class BodyReadingChain extends MockFilterChain {
        private String body;

        @Override
        public void doFilter(ServletRequest request, ServletResponse response) throws java.io.IOException {
            body = new String(request.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
