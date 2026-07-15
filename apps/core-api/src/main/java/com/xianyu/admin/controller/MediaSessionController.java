package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.MediaSessionCookieService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** Issues the HttpOnly media cookies consumed exclusively by /uploads controllers. */
@RestController
public class MediaSessionController {
    private final MediaSessionCookieService mediaSessions;

    public MediaSessionController(MediaSessionCookieService mediaSessions) {
        this.mediaSessions = mediaSessions;
    }

    @PostMapping("/api/media/session")
    public ResponseEntity<Result<Map<String, Object>>> issueUser(HttpServletRequest request) {
        return issue(() -> mediaSessions.issueUser(request));
    }

    @DeleteMapping("/api/media/session")
    public ResponseEntity<Result<Map<String, Object>>> clearUser() {
        return cleared(mediaSessions.clearUserCookie());
    }

    @PostMapping("/admin-api/media/session")
    public ResponseEntity<Result<Map<String, Object>>> issueAdmin(HttpServletRequest request) {
        return issue(() -> mediaSessions.issueAdmin(request));
    }

    @DeleteMapping("/admin-api/media/session")
    public ResponseEntity<Result<Map<String, Object>>> clearAdmin() {
        return cleared(mediaSessions.clearAdminCookie());
    }

    private ResponseEntity<Result<Map<String, Object>>> issue(CookieIssuer issuer) {
        try {
            MediaSessionCookieService.IssuedCookie cookie = issuer.issue();
            return response(HttpStatus.OK, cookie.setCookieHeader(), Result.ok(Map.of(
                    "ready", true,
                    "issued", true,
                    "expiresInSeconds", cookie.maxAgeSeconds()
            )));
        } catch (MediaSessionCookieService.MediaSessionUnavailableException exception) {
            return response(HttpStatus.SERVICE_UNAVAILABLE, null,
                    new Result<>(503, "媒体登录状态暂时无法核验，请稍后重试", null));
        } catch (MediaSessionCookieService.InvalidMediaSessionException exception) {
            return response(HttpStatus.UNAUTHORIZED, null,
                    Result.unauthorized("登录已过期，请重新登录"));
        }
    }

    private ResponseEntity<Result<Map<String, Object>>> cleared(String setCookieHeader) {
        return response(HttpStatus.OK, setCookieHeader, Result.ok(Map.of("cleared", true)));
    }

    private ResponseEntity<Result<Map<String, Object>>> response(
            HttpStatus status,
            String setCookieHeader,
            Result<Map<String, Object>> body) {
        ResponseEntity.BodyBuilder builder = ResponseEntity.status(status)
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.PRAGMA, "no-cache");
        if (setCookieHeader != null) builder.header(HttpHeaders.SET_COOKIE, setCookieHeader);
        return builder.body(body);
    }

    @FunctionalInterface
    private interface CookieIssuer {
        MediaSessionCookieService.IssuedCookie issue();
    }
}
