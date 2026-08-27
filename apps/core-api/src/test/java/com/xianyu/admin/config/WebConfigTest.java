package com.xianyu.admin.config;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.context.support.StaticApplicationContext;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.web.MockServletContext;
import org.springframework.web.filter.CorsFilter;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;

import java.io.IOException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WebConfigTest {

    private final WebConfig webConfig = new WebConfig();

    @Test
    void staticUploadsNeverBypassTheGovernedMediaController() {
        ResourceHandlerRegistry registry = new ResourceHandlerRegistry(
                new StaticApplicationContext(), new MockServletContext());

        webConfig.addResourceHandlers(registry);

        assertFalse(registry.hasMappingForPattern("/uploads/public/**"));
        assertFalse(registry.hasMappingForPattern("/uploads/logos/**"));
        assertFalse(registry.hasMappingForPattern("/uploads/**"));
        assertFalse(registry.hasMappingForPattern("/uploads/images/**"));
        assertFalse(registry.hasMappingForPattern("/uploads/cache/**"));
        assertFalse(registry.hasMappingForPattern("/uploads/avatars/**"));
    }

    @Test
    void apiCorsFilterAllowsConfiguredUserOrigin() throws ServletException, IOException {
        CorsFilter filter = webConfig.corsFilter(
                "http://localhost:3006,http://192.0.2.10:82",
                "",
                "http://localhost:5173,http://192.0.2.10:81",
                ""
        );

        MockHttpServletResponse response = applyFilter(filter, "/api/login/login", "http://192.0.2.10:81");

        assertEquals("http://192.0.2.10:81", response.getHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
        assertEquals(HttpServletResponse.SC_OK, response.getStatus());
    }

    @Test
    void adminCorsFilterAllowsConfiguredAdminOrigin() throws ServletException, IOException {
        CorsFilter filter = webConfig.corsFilter(
                "http://localhost:3006,http://192.0.2.10:82",
                "",
                "http://localhost:5173,http://192.0.2.10:81",
                ""
        );

        MockHttpServletResponse response = applyFilter(filter, "/admin-api/auth/login", "http://192.0.2.10:82");

        assertEquals("http://192.0.2.10:82", response.getHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
        assertEquals(HttpServletResponse.SC_OK, response.getStatus());
    }

    @Test
    void apiCorsFilterRejectsUnconfiguredOrigin() throws ServletException, IOException {
        CorsFilter filter = webConfig.corsFilter(
                "http://localhost:3006,http://192.0.2.10:82",
                "",
                "http://localhost:5173,http://192.0.2.10:81",
                ""
        );

        MockHttpServletResponse response = applyFilter(filter, "/api/login/login", "http://evil.example.com");

        assertEquals(HttpServletResponse.SC_FORBIDDEN, response.getStatus());
        assertTrue(response.getContentAsString().contains("Invalid CORS request"));
    }

    @Test
    void apiCorsFilterAllowsConfiguredOriginPattern() throws ServletException, IOException {
        CorsFilter filter = webConfig.corsFilter(
                "",
                "https://admin-*.example.com",
                "",
                "https://app-*.example.com"
        );

        MockHttpServletResponse response = applyFilter(filter, "/api/login/login", "https://app-prod.example.com");

        assertEquals("https://app-prod.example.com", response.getHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
        assertEquals(HttpServletResponse.SC_OK, response.getStatus());
    }

    private static MockHttpServletResponse applyFilter(CorsFilter filter, String path, String origin)
            throws ServletException, IOException {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", path);
        request.addHeader(HttpHeaders.ORIGIN, origin);
        request.addHeader(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST");
        request.setContentType("application/json");
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
