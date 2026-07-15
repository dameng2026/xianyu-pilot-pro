package com.xianyu.admin.controller;

import com.xianyu.admin.security.MediaSessionCookieService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class MediaSessionControllerTest {
    private MediaSessionCookieService service;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        service = mock(MediaSessionCookieService.class);
        mvc = MockMvcBuilders.standaloneSetup(new MediaSessionController(service)).build();
    }

    @Test
    void userAndAdminIssueEndpointsSetNoStoreCookieWithoutReturningToken() throws Exception {
        when(service.issueUser(any())).thenReturn(
                new MediaSessionCookieService.IssuedCookie("xianyu_media_user=token; Path=/uploads", 300));
        when(service.issueAdmin(any())).thenReturn(
                new MediaSessionCookieService.IssuedCookie("xianyu_media_admin=token; Path=/uploads", 200));

        mvc.perform(post("/api/media/session").header("Authorization", "Bearer access"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(header().string("Set-Cookie", "xianyu_media_user=token; Path=/uploads"))
                .andExpect(jsonPath("$.data.ready").value(true))
                .andExpect(jsonPath("$.data.issued").value(true))
                .andExpect(jsonPath("$.data.expiresInSeconds").value(300))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("access"))));

        mvc.perform(post("/admin-api/media/session").header("Authorization", "Bearer admin"))
                .andExpect(status().isOk())
                .andExpect(header().string("Set-Cookie", "xianyu_media_admin=token; Path=/uploads"))
                .andExpect(jsonPath("$.data.ready").value(true))
                .andExpect(jsonPath("$.data.expiresInSeconds").value(200));
    }

    @Test
    void issueMapsInvalidSessionTo401AndStateOutageTo503() throws Exception {
        when(service.issueUser(any())).thenThrow(
                new MediaSessionCookieService.InvalidMediaSessionException());
        when(service.issueAdmin(any())).thenThrow(
                new MediaSessionCookieService.MediaSessionUnavailableException(
                        new IllegalStateException("db")));

        mvc.perform(post("/api/media/session"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401))
                .andExpect(header().string("Cache-Control", "no-store"));

        mvc.perform(post("/admin-api/media/session"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503))
                .andExpect(header().string("Cache-Control", "no-store"));
    }

    @Test
    void clearEndpointsExpireTheCorrectCookie() throws Exception {
        when(service.clearUserCookie()).thenReturn("xianyu_media_user=; Max-Age=0; Path=/uploads");
        when(service.clearAdminCookie()).thenReturn("xianyu_media_admin=; Max-Age=0; Path=/uploads");

        mvc.perform(delete("/api/media/session"))
                .andExpect(status().isOk())
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.allOf(
                        org.hamcrest.Matchers.containsString("xianyu_media_user="),
                        org.hamcrest.Matchers.containsString("Path=/uploads"),
                        org.hamcrest.Matchers.containsString("Max-Age=0"))))
                .andExpect(jsonPath("$.data.cleared").value(true));

        mvc.perform(delete("/admin-api/media/session"))
                .andExpect(status().isOk())
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.allOf(
                        org.hamcrest.Matchers.containsString("xianyu_media_admin="),
                        org.hamcrest.Matchers.containsString("Path=/uploads"),
                        org.hamcrest.Matchers.containsString("Max-Age=0"))));
    }
}
