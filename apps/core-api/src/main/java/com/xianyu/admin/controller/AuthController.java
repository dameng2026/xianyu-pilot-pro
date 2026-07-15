package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.AdminLoginAttemptGuard;
import com.xianyu.admin.security.ClientIpResolver;
import com.xianyu.admin.security.MediaSessionCookieService;
import com.xianyu.admin.service.AuthService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/admin-api")
public class AuthController {
    private final AuthService authService;
    private final AdminLoginAttemptGuard loginAttemptGuard;
    private final MediaSessionCookieService mediaSessions;

    public AuthController(AuthService authService,
                          AdminLoginAttemptGuard loginAttemptGuard,
                          MediaSessionCookieService mediaSessions) {
        this.authService = authService;
        this.loginAttemptGuard = loginAttemptGuard;
        this.mediaSessions = mediaSessions;
    }

    public record LoginReq(
            @NotBlank @Size(max = 128) String userName,
            @NotBlank @Size(max = 256) String password
    ) {}

    public record ChangePasswordReq(
            @NotBlank @Size(max = 256) String oldPassword,
            @NotBlank @Size(max = 256) String newPassword
    ) {}

    @PostMapping("/auth/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginReq req,
                                             HttpServletRequest request) {
        String username = req.userName().trim();
        String clientIp = ClientIpResolver.resolve(request);
        loginAttemptGuard.checkAllowed(username, clientIp);
        try {
            Map<String, Object> result = authService.login(username, req.password());
            loginAttemptGuard.recordSuccess(username);
            return Result.ok(result);
        } catch (com.xianyu.admin.common.BizException e) {
            if (e.getCode() == 401) {
                loginAttemptGuard.recordFailure(username, clientIp);
            }
            throw e;
        }
    }

    @GetMapping("/user/info")
    public Result<Map<String, Object>> info() {
        return Result.ok(authService.userInfo(AdminContext.userId()));
    }

    @PostMapping("/auth/logout")
    public ResponseEntity<Result<Void>> logout() {
        authService.logout(AdminContext.userId());
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.PRAGMA, "no-cache")
                .header(HttpHeaders.SET_COOKIE, mediaSessions.clearAdminCookie())
                .body(Result.ok(null));
    }

    /**
     * 管理员修改自身登录密码。
     * 修改成功后既有令牌全部失效（含当前会话），前端需引导用户重新登录。
     */
    @PostMapping("/auth/change-password")
    public Result<Void> changePassword(@Valid @RequestBody ChangePasswordReq req) {
        authService.changePassword(AdminContext.userId(), req.oldPassword(), req.newPassword());
        return Result.ok(null);
    }

    @GetMapping("/health")
    public Result<Map<String, Object>> health() {
        return Result.ok(Map.of("status", "UP", "service", "core-api", "check", "liveness"));
    }

}
