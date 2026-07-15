package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.AdminLoginAttemptGuard;
import com.xianyu.admin.service.AuthService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.mock;

@ExtendWith(MockitoExtension.class)
class AuthControllerRateLimitTest {

    @Mock AuthService authService;
    @Mock AdminLoginAttemptGuard loginAttemptGuard;

    @Test
    void failedCredentialsAreRecordedAgainstAccountAndClientIp() {
        AuthController controller = new AuthController(
                authService, loginAttemptGuard,
                mock(com.xianyu.admin.security.MediaSessionCookieService.class));
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("203.0.113.8");
        when(authService.login("admin", "wrong-password"))
                .thenThrow(new BizException(401, "用户名或密码错误"));

        assertThrows(BizException.class, () -> controller.login(
                new AuthController.LoginReq("admin", "wrong-password"), request));

        verify(loginAttemptGuard).checkAllowed("admin", "203.0.113.8");
        verify(loginAttemptGuard).recordFailure("admin", "203.0.113.8");
    }

    @Test
    void successfulCredentialsClearTheAccountFailureCounter() {
        AuthController controller = new AuthController(
                authService, loginAttemptGuard,
                mock(com.xianyu.admin.security.MediaSessionCookieService.class));
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("203.0.113.8");
        when(authService.login("admin", "correct-password")).thenReturn(Map.of("token", "jwt"));

        controller.login(new AuthController.LoginReq("admin", "correct-password"), request);

        verify(loginAttemptGuard).recordSuccess("admin");
    }
}
