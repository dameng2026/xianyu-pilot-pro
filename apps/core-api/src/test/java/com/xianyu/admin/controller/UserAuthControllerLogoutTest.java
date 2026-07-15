package com.xianyu.admin.controller;

import com.xianyu.admin.security.MediaSessionCookieService;
import com.xianyu.admin.service.UserAuthCapabilityService;
import com.xianyu.admin.service.UserAuthService;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class UserAuthControllerLogoutTest {

    @Test
    void logoutRevokesJwtAndClearsHttpOnlyMediaCookieInOneResponse() {
        UserAuthService authService = mock(UserAuthService.class);
        MediaSessionCookieService mediaSessions = mock(MediaSessionCookieService.class);
        when(mediaSessions.clearUserCookie())
                .thenReturn("xya_user_media=; Path=/uploads; Max-Age=0; HttpOnly; Secure; SameSite=Strict");
        UserAuthController controller = new UserAuthController(
                authService,
                mock(UserAuthCapabilityService.class),
                mediaSessions
        );

        var response = controller.logout();

        assertEquals(200, response.getStatusCode().value());
        assertEquals(200, response.getBody().getCode());
        assertTrue(response.getHeaders().getFirst(HttpHeaders.SET_COOKIE).contains("Max-Age=0"));
        assertTrue(response.getHeaders().getCacheControl().contains("no-store"));
        verify(authService).logout();
        verify(mediaSessions).clearUserCookie();
    }
}
