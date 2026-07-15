package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OpsMetricsAuthFilterTest {

    @Test
    void metricsFailClosedWhenScrapeTokenIsMissingFromConfiguration() throws Exception {
        MockHttpServletResponse response = execute(new OpsMetricsAuthFilter(""), null);
        assertEquals(503, response.getStatus());
    }

    @Test
    void metricsRejectWrongScrapeToken() throws Exception {
        MockHttpServletResponse response = execute(new OpsMetricsAuthFilter("metrics-secret"), "wrong");
        assertEquals(403, response.getStatus());
    }

    @Test
    void metricsAllowMatchingScrapeToken() throws Exception {
        MockHttpServletResponse response = execute(new OpsMetricsAuthFilter("metrics-secret"), "metrics-secret");
        assertEquals(200, response.getStatus());
    }

    @Test
    void filterDoesNotProtectPublicLivenessProbe() throws Exception {
        OpsMetricsAuthFilter filter = new OpsMetricsAuthFilter("metrics-secret");
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/ops/liveness");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertEquals(200, response.getStatus());
    }

    private MockHttpServletResponse execute(OpsMetricsAuthFilter filter, String token) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/ops/prometheus");
        if (token != null) request.addHeader("X-Metrics-Token", token);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
