package com.xianyu.admin.controller;

import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.AdminLoginAttemptGuard;
import com.xianyu.admin.security.MediaSessionCookieService;
import com.xianyu.admin.service.AuthService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthControllerLogoutTest {

    @AfterEach
    void clearContext() {
        AdminContext.clear();
    }

    @Test
    void logoutRevokesJwtAndClearsHttpOnlyMediaCookieInOneResponse() {
        AuthService authService = mock(AuthService.class);
        MediaSessionCookieService mediaSessions = mock(MediaSessionCookieService.class);
        when(mediaSessions.clearAdminCookie())
                .thenReturn("xya_admin_media=; Path=/uploads; Max-Age=0; HttpOnly; Secure; SameSite=Strict");
        AdminContext.set(9L, "admin", "R_ADMIN");
        AuthController controller = new AuthController(
                authService,
                mock(AdminLoginAttemptGuard.class),
                mediaSessions
        );

        var response = controller.logout();

        assertEquals(200, response.getStatusCode().value());
        assertEquals(200, response.getBody().getCode());
        assertTrue(response.getHeaders().getFirst(HttpHeaders.SET_COOKIE).contains("Max-Age=0"));
        assertTrue(response.getHeaders().getCacheControl().contains("no-store"));
        verify(authService).logout(9L);
        verify(mediaSessions).clearAdminCookie();
    }
}
