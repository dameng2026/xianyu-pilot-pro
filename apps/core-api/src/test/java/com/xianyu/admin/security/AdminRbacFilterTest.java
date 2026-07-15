package com.xianyu.admin.security;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AdminRbacFilterTest {

    private final AdminRbacFilter filter = new AdminRbacFilter();

    @AfterEach
    void clearContext() {
        AdminContext.clear();
    }

    @Test
    void regularAdminCannotResetPlatformUserPassword() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("POST", "/admin-api/system/user/42/reset-password");

        assertEquals(403, response.getStatus());
        assertTrue(response.getContentAsString().contains("\"code\":403"));
    }

    @Test
    void regularAdminCannotReadPaymentSecrets() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("GET", "/admin-api/payment/configs");

        assertEquals(403, response.getStatus());
    }

    @Test
    void regularAdminCannotMutateGenericAdminModules() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("PUT", "/admin-api/admin/modules/goods/42/status");

        assertEquals(403, response.getStatus());
    }

    @Test
    void regularAdminCannotReadModelProviderConfiguration() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("GET", "/admin-api/admin/modules/model-config-chat/page");

        assertEquals(403, response.getStatus());
    }

    @Test
    void regularAdminCannotSpendProviderCreditsThroughConnectionTest() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("POST", "/admin-api/ai-provider/test");

        assertEquals(403, response.getStatus());
    }

    @Test
    void regularAdminCannotPublishOpenSourceSiteMedia() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute(
                "POST", "/admin-api/open-source-admin/media/upload");

        assertEquals(403, response.getStatus());
    }

    @Test
    void superAdminCanUseSensitiveRoutes() throws Exception {
        AdminContext.set(1L, "root", "R_SUPER,R_ADMIN");
        MockHttpServletResponse response = execute("POST", "/admin-api/system/config");

        assertEquals(200, response.getStatus());
    }

    @Test
    void regularAdminCanHandleFeedback() throws Exception {
        AdminContext.set(7L, "operator", "R_ADMIN");
        MockHttpServletResponse response = execute("POST", "/admin-api/feedback/9/reply");

        assertEquals(200, response.getStatus());
    }

    private MockHttpServletResponse execute(String method, String uri) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest(method, uri);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }
}
