package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.config.GlobalExceptionHandler;
import com.xianyu.admin.service.UserAuthCapabilityService;
import com.xianyu.admin.service.UserAuthService;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class UserAuthCapabilityControllerTest {

    @Test
    void publishesStructuredAuthenticationCapabilitiesWithoutAuthentication() throws Exception {
        UserAuthCapabilityService capabilityService = mock(UserAuthCapabilityService.class);
        when(capabilityService.current()).thenReturn(new UserAuthCapabilityService.Capabilities(
                "1", "production-safe", true,
                "生产环境不会接受调试验证码。", "请联系管理员。",
                new UserAuthCapabilityService.Capability(true, false, "密码登录可用"),
                new UserAuthCapabilityService.Capability(false, false, "邮箱SMTP未配置"),
                new UserAuthCapabilityService.Capability(false, false, "自助注册未开放"),
                new UserAuthCapabilityService.Capability(false, false, "密码找回未开放"),
                new UserAuthCapabilityService.Capability(false, false, "资料验证未开放")));
        UserAuthController controller = new UserAuthController(
                mock(UserAuthService.class), capabilityService,
                mock(com.xianyu.admin.security.MediaSessionCookieService.class));
        MockMvc mvc = MockMvcBuilders.standaloneSetup(controller).build();

        mvc.perform(get("/api/login/capabilities"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"))
                .andExpect(header().string("Pragma", "no-cache"))
                .andExpect(header().dateValue("Expires", 0))
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.failClosed").value(true))
                .andExpect(jsonPath("$.data.passwordLogin.available").value(true))
                .andExpect(jsonPath("$.data.emailVerification.available").value(false))
                .andExpect(jsonPath("$.data.selfRegistration.available").value(false))
                .andExpect(jsonPath("$.data.passwordReset.available").value(false))
                .andExpect(jsonPath("$.data.profileVerification.available").value(false));
    }

    @Test
    void directRegistrationCallUsesRealHttp503WhenCapabilityIsUnavailable() throws Exception {
        UserAuthService userAuthService = mock(UserAuthService.class);
        doThrow(new BizException(503, "自助注册依赖邮箱验证，当前不可用"))
                .when(userAuthService).register("test@example.com", "Password123", "123456", null);
        UserAuthController controller = new UserAuthController(
                userAuthService, mock(UserAuthCapabilityService.class),
                mock(com.xianyu.admin.security.MediaSessionCookieService.class));
        MockMvc mvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();

        mvc.perform(post("/api/login/register")
                        .contentType("application/json")
                        .content("{\"email\":\"test@example.com\",\"password\":\"Password123\",\"emailCode\":\"123456\"}"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503))
                .andExpect(jsonPath("$.msg").value("自助注册依赖邮箱验证，当前不可用"));
    }
}
