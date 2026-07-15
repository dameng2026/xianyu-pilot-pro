package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.UserAuthCapabilityService;
import com.xianyu.admin.service.UserAuthService;
import com.xianyu.admin.security.MediaSessionCookieService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;

import java.util.Map;

/**
 * 前台用户认证接口，挂载在 /api（对应用户端前端的 baseURL）。
 * 登录接口无需鉴权，其他接口通过 UserJwtAuthFilter 校验 Bearer Token。
 *
 * 验证码方式已统一切换为邮箱验证码。
 */
@RestController
@RequestMapping("/api")
public class UserAuthController {

    private final UserAuthService userAuthService;
    private final UserAuthCapabilityService capabilityService;
    private final MediaSessionCookieService mediaSessions;

    public UserAuthController(UserAuthService userAuthService,
                              UserAuthCapabilityService capabilityService,
                              MediaSessionCookieService mediaSessions) {
        this.userAuthService = userAuthService;
        this.capabilityService = capabilityService;
        this.mediaSessions = mediaSessions;
    }

    /** Public, fail-closed truth for browser-visible authentication and verification flows. */
    @GetMapping("/login/capabilities")
    public Result<UserAuthCapabilityService.Capabilities> capabilities(HttpServletResponse response) {
        response.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
        response.setHeader("Pragma", "no-cache");
        response.setDateHeader("Expires", 0);
        return Result.ok(capabilityService.current());
    }

    public record LoginReq(@NotBlank String username, @NotBlank String password) {}

    /** 用户登录（支持 username/password 或 email/emailCode） */
    @PostMapping("/login/login")
    public Result<Map<String, Object>> login(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String email = body.get("email");
        String emailCode = body.get("emailCode");
        if (email != null && emailCode != null) {
            return Result.ok(userAuthService.loginByEmail(email, emailCode));
        }
        return Result.ok(userAuthService.login(body.get("username"), body.get("password"), getClientIp(request)));
    }

    /** 用户登出 */
    @PostMapping("/login/logout")
    public ResponseEntity<Result<Void>> logout() {
        userAuthService.logout();
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.PRAGMA, "no-cache")
                .header(HttpHeaders.SET_COOKIE, mediaSessions.clearUserCookie())
                .body(Result.ok(null));
    }

    /** 获取当前用户信息 */
    @PostMapping("/system/currentUser")
    public Result<Map<String, Object>> currentUser() {
        return Result.ok(userAuthService.currentUser());
    }

    /** 发送邮箱验证码 */
    @PostMapping("/login/sendEmailCode")
    public Result<Map<String, Object>> sendEmailCode(@RequestBody Map<String, String> body, HttpServletRequest request) {
        return Result.ok(userAuthService.sendEmailCode(body.get("email"), getClientIp(request)));
    }

    /** 用户注册 */
    @PostMapping("/login/register")
    public Result<Map<String, Object>> register(@RequestBody Map<String, String> body) {
        return Result.ok(userAuthService.register(
                body.get("email"), body.get("password"),
                body.get("emailCode"), body.get("inviteCode")));
    }

    /** 重置密码前置验证码校验。 */
    @PostMapping("/login/verifyResetCode")
    public Result<Void> verifyResetCode(@RequestBody Map<String, String> body) {
        userAuthService.verifyResetCode(body.get("email"), body.get("emailCode"));
        return Result.ok(null);
    }

    /** 重置密码（忘记密码） */
    @PostMapping("/login/resetPassword")
    public Result<Void> resetPassword(@RequestBody Map<String, String> body) {
        userAuthService.resetPassword(body.get("email"), body.get("emailCode"), body.get("newPassword"));
        return Result.ok(null);
    }


    private String getClientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }

    /** 健康检查 */
    @GetMapping("/health")
    public Result<Map<String, Object>> health() {
        return Result.ok(Map.of("status", "UP", "service", "core-api", "check", "liveness"));
    }
}
